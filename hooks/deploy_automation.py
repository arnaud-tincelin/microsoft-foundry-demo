#!/usr/bin/env python3
"""Publish AI Gateway assets and Logic Apps Automation after the tracker deploys."""

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from azure.identity import AzureCliCredential
from dotenv import set_key

ROOT = Path(__file__).resolve().parent.parent
ARM = "https://management.azure.com"
ARM_SCOPE = "https://management.azure.com/.default"
AUTOMATION_SCOPE = "api://de712aed-bfe7-4949-9833-aacfebd5fd5b/.default"
GATEWAY_API = "2026-09-01-preview"
AUTOMATION_API = "2026-04-01-preview"
FOUNDRY_USER_ROLE = "53ca6127-db72-4b80-b1b0-d745d6d5456d"


def required(name):
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing deployment output: {name}")
    return value


class AzureRequestError(RuntimeError):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


def request_json(url, method="GET", body=None, headers=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = Request(url, data=data, method=method, headers=request_headers)
    try:
        with urlopen(request, timeout=120) as response:
            response_headers = dict(response.headers)
            if "text/event-stream" in response.headers.get("Content-Type", ""):
                for line in response:
                    if line.startswith(b"data:"):
                        event = json.loads(line[5:])
                        if "result" in event or "error" in event:
                            return event, response_headers
                raise RuntimeError("The MCP stream closed without a JSON-RPC result.")
            content = response.read()
            return (json.loads(content) if content else {}), response_headers
    except HTTPError as error:
        # Do not expose request bodies, signed query strings, or runtime credentials.
        content = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(content)
            detail = payload.get("error", payload)
            message = detail.get("message", str(detail))
            for item in detail.get("details", []):
                message += f" {item.get('target', item.get('code', ''))}: {item.get('message', '')}"
        except (json.JSONDecodeError, AttributeError):
            message = content[:1000]
        raise AzureRequestError(error.code,
            f"{method} {urlsplit(url).path}: HTTP {error.code}: {message}"
        ) from None


class AzureApi:
    def __init__(self):
        self.credential = AzureCliCredential(process_timeout=60)
        self.tokens = {}

    def request(self, url, method="GET", body=None, scope=ARM_SCOPE):
        token = self.tokens.get(scope)
        if token is None or token.expires_on < time.time() + 120:
            token = self.credential.get_token(scope)
            self.tokens[scope] = token
        return request_json(
            url, method, body, {"Authorization": f"Bearer {token.token}"}
        )

    def put(self, resource_id, properties):
        url = f"{ARM}{resource_id}?api-version={GATEWAY_API}"
        result, headers = self.request(url, "PUT", {"properties": properties})
        operation = next(
            (value for key, value in headers.items()
             if key.lower() == "azure-asyncoperation"), None
        )
        if operation:
            self.wait(operation, ARM_SCOPE)
            result, _ = self.request(url)
        elif result.get("properties", {}).get("provisioningState", "").lower() not in {"", "succeeded"}:
            self.wait(url, ARM_SCOPE)
        return self.request(url)[0]

    def wait(self, url, scope, timeout=900):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result, _ = self.request(url, scope=scope)
            status = result.get("status", result.get("properties", {}).get("provisioningState"))
            if status and status.lower() == "succeeded":
                return result
            if status and status.lower() in {"failed", "canceled", "cancelled"}:
                raise RuntimeError(f"Azure operation failed: {json.dumps(result)}")
            time.sleep(10)
        raise TimeoutError("Azure operation did not succeed within the deployment timeout.")


def runtime_endpoints(gateway_url):
    endpoint = urlsplit(gateway_url)
    if (endpoint.scheme != "https" or not endpoint.hostname
            or endpoint.username or endpoint.password
            or endpoint.path not in {"", "/"} or endpoint.query or endpoint.fragment):
        raise ValueError("AI_GATEWAY_URL must be the assigned HTTPS gateway origin.")
    origin = gateway_url.rstrip("/")
    return (f"{origin}/default/models/openai/v1",
            f"{origin}/default/toolservers/game-sessions/mcp")


def tracker_openapi(document, tracker_url):
    operations = {"/sessions": {"get", "post"}, "/sessions/last": {"get"}}
    document["servers"] = [{"url": tracker_url}]
    document["paths"] = {
        path: {method: value for method, value in document["paths"][path].items()
               if method in methods}
        for path, methods in operations.items()
    }
    return document


def publish_workflow_artifacts(api, url, files):
    deadline = time.monotonic() + 300
    while True:
        try:
            return api.request(url, "POST", {"files": files}, AUTOMATION_SCOPE)
        except AzureRequestError as error:
            conflict = error.status_code == 409 or (
                error.status_code == 502 and "status 'Conflict'" in str(error)
            )
            host_timeout = error.status_code == 503 and "The request timed out." in str(error)
            if not (conflict or host_timeout) or time.monotonic() >= deadline:
                raise
            print("Automation host is updating; retrying the idempotent artifact publication...")
            time.sleep(10)


def configure_gateway(api):
    gateway_id = required("AI_GATEWAY_RESOURCE_ID")
    account_id = required("FOUNDRY_ACCOUNT_RESOURCE_ID")
    model = required("MODEL_DEPLOYMENT")
    model_base, mcp_url = runtime_endpoints(required("AI_GATEWAY_URL"))
    workspace = f"{gateway_id}/workspaces/default"
    provider_id = f"{workspace}/modelProviders/foundry"
    print("Registering Foundry model provider and routing alias...")
    api.put(provider_id, {
        "kind": "Foundry",
        "name": "Foundry",
        "foundry": {
            "endpoint": required("FOUNDRY_ACCOUNT_ENDPOINT").rstrip("/"),
            "resourceIds": [account_id],
            "authentication": {"kind": "ManagedIdentity"},
        },
    })
    model_id = f"{provider_id}/models/gpt-41"
    api.put(model_id, {
        "name": "GPT-4.1",
        "deployment": {
            "resourceId": f"{account_id}/deployments/{model}",
            "modelName": "gpt-4.1",
            "modelVersion": "2025-04-14",
        },
        "supportedEndpoints": ["/v1/chat/completions", "/v1/responses"],
    })
    api.put(f"{workspace}/aliases/gpt-41", {
        "aliasName": model,
        "backendModels": [{"resourceId": model_id, "priority": 0, "weight": 1}],
        "selectionOrder": ["routing"],
    })
    key_id = f"{gateway_id}/apiKeys/demo"
    api.put(key_id, {"displayName": "Demo runtime access", "state": "active"})
    secrets, _ = api.request(
        f"{ARM}{key_id}/listSecrets?api-version={GATEWAY_API}", "POST", {}
    )
    runtime_key = secrets["primaryKey"]

    tracker_url = required("GAME_TRACKER_API_URL").rstrip("/")
    document, _ = request_json(f"{tracker_url}/openapi.json")
    document = tracker_openapi(document, tracker_url)
    print("Importing the three tracker operations as MCP tools...")
    api.put(f"{workspace}/toolServers/game-sessions", {
        "name": "Game Sessions Tracker",
        "type": "openApi",
        "subscriptionRequired": True,
        "endpoints": [{
            "id": "tracker",
            "namespace": "game-sessions",
            "kind": "openApi",
            "openApi": {"specSource": {
                "type": "inline",
                "contentBase64": base64.b64encode(json.dumps(document).encode()).decode(),
            }},
            "credentials": {"type": "none"},
            "required": True,
        }],
    })
    connection_url = (
        f"{ARM}{required('FOUNDRY_PROJECT_RESOURCE_ID')}/connections/"
        "game-sessions-tracker?api-version=2025-10-01-preview"
    )
    api.request(connection_url, "PUT", {"properties": {
        "category": "RemoteTool", "target": mcp_url,
        "authType": "CustomKeys", "isSharedToAll": True,
        "credentials": {"keys": {"api-key": runtime_key}},
        "metadata": {"type": "custom_MCP"},
    }})
    return model_base.rstrip("/"), mcp_url


def ensure_foundry_access(api, app):
    principal = app.get("identity", {}).get("principalId")
    if not principal:
        raise RuntimeError("The Automation application has no system-assigned managed identity.")
    scope = required("FOUNDRY_PROJECT_RESOURCE_ID")
    role_url = f"{ARM}{scope}/providers/Microsoft.Authorization/roleAssignments"
    query = quote(f"principalId eq '{principal}'", safe="")
    url = f"{role_url}?api-version=2022-04-01&$filter={query}"
    while url:
        assignments, _ = api.request(url)
        for assignment in assignments["value"]:
            properties = assignment["properties"]
            if (properties["roleDefinitionId"].rsplit("/", 1)[-1] == FOUNDRY_USER_ROLE
                    and properties["scope"].lower() == scope.lower()
                    and properties["principalId"].lower() == principal.lower()):
                return
        url = assignments.get("nextLink")
    assignment_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{scope}/{principal}/{FOUNDRY_USER_ROLE}")
    print("Granting the Automation application Foundry User access on its Foundry project...")
    api.request(f"{role_url}/{assignment_id}?api-version=2022-04-01", "PUT", {
        "properties": {
            "roleDefinitionId": (
                f"/subscriptions/{required('AZURE_SUBSCRIPTION_ID')}/providers/"
                f"Microsoft.Authorization/roleDefinitions/{FOUNDRY_USER_ROLE}"
            ),
            "principalId": principal,
            "principalType": "ServicePrincipal",
        },
    })


def publish_automation(api):
    region = required("AUTOMATION_LOCATION")
    project = quote(required("AUTOMATION_PROJECT_NAME"), safe="")
    app_url = f"https://auto.{region}.logic.azure.com/automationProjects/{project}/applications/guessing-game"
    app_query = f"?api-version={AUTOMATION_API}"
    project_url = f"{ARM}{required('AUTOMATION_PROJECT_RESOURCE_ID')}{app_query}"
    try:
        project_resource, _ = api.request(project_url)
        if project_resource.get("properties", {}).get("provisioningState", "").lower() != "succeeded":
            api.wait(project_url, ARM_SCOPE)
        print("Using the existing Logic Apps Automation project...")
    except AzureRequestError as error:
        if error.status_code != 404:
            raise
        print("Creating the Logic Apps Automation project...")
        _, headers = api.request(project_url, "PUT", {
            "location": region,
            "identity": {"type": "SystemAssigned"},
            "tags": {"azd-env-name": required("AZURE_ENV_NAME")},
            "properties": {"description": "Logic Apps Automation guessing-game demo."},
        })
        operation = next(
            (value for key, value in headers.items()
             if key.lower() == "azure-asyncoperation"), project_url
        )
        api.wait(operation, ARM_SCOPE)
    try:
        app, headers = api.request(app_url + app_query, scope=AUTOMATION_SCOPE)
        print("Using the existing Logic Apps Automation application...")
    except AzureRequestError as error:
        if error.status_code != 404:
            raise
        print("Creating the Logic Apps Automation application...")
        app, headers = api.request(app_url + app_query, "PUT", {}, AUTOMATION_SCOPE)
    operation = next(
        (value for key, value in headers.items()
         if key.lower() == "azure-asyncoperation"), None
    )
    if operation:
        api.wait(operation, AUTOMATION_SCOPE)
    elif app.get("properties", {}).get("provisioningState", "").lower() != "succeeded":
        api.wait(app_url + app_query, AUTOMATION_SCOPE)

    app, _ = api.request(app_url + app_query, scope=AUTOMATION_SCOPE)
    ensure_foundry_access(api, app)
    workflow = json.loads((ROOT / "automation" / "workflow.json").read_text(encoding="utf-8"))
    parameters = {
        "foundryProjectEndpoint": {
            "type": "String", "value": required("PROJECT_ENDPOINT").rstrip("/")
        },
        "playerAgentVersion": {"type": "String", "value": required("PLAYER_AGENT_VERSION")},
        "gameMasterAgentVersion": {
            "type": "String", "value": required("GAME_MASTER_AGENT_VERSION")
        },
        "gameTrackerApiUrl": {
            "type": "String", "value": required("GAME_TRACKER_API_URL").rstrip("/")
        },
    }
    print("Validating guessing-game with the Automation service...")
    api.request(f"{app_url}/workflows/guessing-game/validate{app_query}", "POST", {
        "properties": {
            "definition": workflow["definition"], "kind": workflow["kind"],
            "parameters": {
                key: parameters[key] for key in workflow["definition"]["parameters"]
            },
        },
    }, AUTOMATION_SCOPE)
    print("Publishing the shared-conversation Automation workflow...")
    publish_workflow_artifacts(api, f"{app_url}/deployWorkflowArtifacts{app_query}", {
        "guessing-game/workflow.json": workflow,
        "parameters.json": parameters,
    })
    return wait_for_workflow(api, app_url, app_query, "guessing-game", workflow)


def wait_for_workflow(api, app_url, app_query, name, workflow):
    print(f"Waiting for {name} and its HTTP trigger to become available...")
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            deployed, _ = api.request(
                f"{app_url}/workflows/{name}{app_query}", scope=AUTOMATION_SCOPE
            )
            properties = deployed.get("properties", {})
            if (properties.get("health", {}).get("state") != "Healthy"
                    or properties.get("files", {}).get("workflow.json") != workflow):
                time.sleep(5)
                continue
            callback, _ = api.request(
                f"{app_url}/workflows/{name}/triggers/When_an_HTTP_request_is_received/"
                f"listCallbackUrl{app_query}", "POST", {}, AUTOMATION_SCOPE
            )
            break
        except AzureRequestError as error:
            if error.status_code != 404:
                raise
        time.sleep(5)
    else:
        raise TimeoutError("The expected Automation workflow and HTTP trigger did not become ready.")
    url = callback["value"]
    if urlsplit(url).scheme != "https":
        raise ValueError("Automation returned a non-HTTPS callback URL.")
    return url


def save_outputs(values):
    env_file = ROOT / ".azure" / required("AZURE_ENV_NAME") / ".env"
    if not env_file.is_file():
        raise FileNotFoundError("The selected azd environment file does not exist.")
    subprocess.run(
        ["git", "check-ignore", "--quiet", str(env_file)],
        cwd=ROOT, check=True,
    )
    for name, value in values.items():
        set_key(str(env_file), name, value)
        os.environ[name] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", nargs="?", choices=["gateway", "automation", "all"], default="all")
    phase = parser.parse_args().phase
    api = AzureApi()
    if phase in {"gateway", "all"}:
        model_base, mcp_url = configure_gateway(api)
        save_outputs({
            "AI_GATEWAY_MODEL_BASE_URL": model_base,
            "MCP_SERVER_URL": mcp_url,
            "MCP_CONNECTION_CONFIGURED": "true",
        })
        print("Gateway and Foundry MCP connection configured.")
    if phase in {"automation", "all"}:
        callback_url = publish_automation(api)
        save_outputs({"LOGIC_APPS_WORKFLOW_URL": callback_url})
        print("Automation workflow and managed-identity Foundry access configured.")
        print("The signed workflow callback is saved only in ignored azd state.")


if __name__ == "__main__":
    main()
