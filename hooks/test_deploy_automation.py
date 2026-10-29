import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from deploy_automation import (
    ARM, FOUNDRY_USER_ROLE, ROOT, AzureRequestError, configure_gateway,
    ensure_foundry_access, main, publish_automation, publish_workflow_artifacts,
    request_json, runtime_endpoints, tracker_openapi, wait_for_workflow,
)


class GatewayContractTests(unittest.TestCase):
    def test_publishes_version_pinned_foundry_agents_without_a_secret_parameter(self):
        api = Mock()
        app = {"properties": {"provisioningState": "Succeeded"}}
        api.request.side_effect = [
            ({"properties": {"provisioningState": "Succeeded"}}, {}),
            (app, {}),
            (app, {}),
            ({}, {}),
            ({}, {}),
        ]
        environment = {
            "AUTOMATION_LOCATION": "westus",
            "AUTOMATION_PROJECT_NAME": "test-project",
            "AUTOMATION_PROJECT_RESOURCE_ID": "/automationProjects/test-project",
            "PROJECT_ENDPOINT": "https://foundry.example/api/projects/demo/",
            "PLAYER_AGENT_VERSION": "2",
            "GAME_MASTER_AGENT_VERSION": "3",
            "GAME_TRACKER_API_URL": "https://tracker.example",
        }
        with patch.dict("os.environ", environment), patch(
                "deploy_automation.ensure_foundry_access") as access, patch(
                "deploy_automation.wait_for_workflow", return_value="https://workflow.example/invoke?sig=test") as ready:
            publish_automation(api)
        access.assert_called_once_with(api, app)
        ready.assert_called_once()
        self.assertEqual(ready.call_args.args[3], "guessing-game")
        self.assertEqual(api.request.call_count, 5)
        files = api.request.call_args_list[4].args[2]["files"]
        self.assertEqual(set(files), {"guessing-game/workflow.json", "parameters.json"})
        validation = api.request.call_args_list[3].args[2]["properties"]
        self.assertEqual(set(validation["parameters"]), set(validation["definition"]["parameters"]))
        for key, binding in validation["parameters"].items():
            self.assertEqual(binding, files["parameters.json"][key])
        self.assertEqual(files["parameters.json"]["foundryProjectEndpoint"]["value"],
                         "https://foundry.example/api/projects/demo")
        self.assertEqual(files["parameters.json"]["playerAgentVersion"], {
            "type": "String", "value": "2",
        })
        self.assertEqual(files["parameters.json"]["gameMasterAgentVersion"]["value"], "3")
        self.assertNotIn("gatewayRuntimeKey", files["parameters.json"])
        self.assertNotIn("modelName", files["parameters.json"])
        self.assertNotIn("appsetting(", json.dumps(files))
        self.assertNotIn('"type": "Workflow"', json.dumps(files))

    @patch("deploy_automation.time.sleep")
    def test_waits_for_the_expected_definition_not_just_a_healthy_old_workflow(self, sleep):
        workflow = json.loads((ROOT / "automation" / "workflow.json").read_text(encoding="utf-8"))
        api = Mock()
        api.request.side_effect = [
            ({"properties": {"health": {"state": "Healthy"}, "files": {"workflow.json": {}}}}, {}),
            ({"properties": {
                "health": {"state": "Healthy"}, "files": {"workflow.json": workflow},
            }}, {}),
            ({"value": "https://workflow.example/invoke?sig=test"}, {}),
        ]
        result = wait_for_workflow(api, "https://automation.example/app", "?api-version=test",
                                   "guessing-game", workflow)
        self.assertEqual(result, "https://workflow.example/invoke?sig=test")
        sleep.assert_called_once_with(5)
        self.assertIn("/triggers/When_an_HTTP_request_is_received/listCallbackUrl",
                      api.request.call_args.args[0])

    def test_foundry_access_is_scoped_to_the_actual_application_identity_and_project(self):
        api = Mock()
        scope = "/subscriptions/test/providers/Microsoft.CognitiveServices/accounts/account/projects/demo"
        app = {"identity": {"principalId": "app-principal"}}
        environment = {"FOUNDRY_PROJECT_RESOURCE_ID": scope, "AZURE_SUBSCRIPTION_ID": "test"}
        role = {
            "properties": {
                "roleDefinitionId": f"/roleDefinitions/{FOUNDRY_USER_ROLE}",
                "scope": scope, "principalId": "app-principal",
            },
        }
        api.request.return_value = ({"value": [role]}, {})
        with patch.dict("os.environ", environment):
            ensure_foundry_access(api, app)
        api.request.assert_called_once()
        self.assertIn(scope + "/providers/Microsoft.Authorization/roleAssignments", api.request.call_args.args[0])

        role["properties"]["principalId"] = "another-principal"
        with patch.dict("os.environ", environment):
            ensure_foundry_access(api, app)
        url, method, body = api.request.call_args.args
        self.assertTrue(url.startswith(ARM + scope + "/providers/Microsoft.Authorization/roleAssignments/"))
        self.assertEqual(method, "PUT")
        self.assertEqual(body["properties"]["principalId"], "app-principal")
        self.assertEqual(body["properties"]["principalType"], "ServicePrincipal")
        self.assertTrue(body["properties"]["roleDefinitionId"].endswith(FOUNDRY_USER_ROLE))

    def test_missing_application_identity_is_an_explicit_failure(self):
        api = Mock()
        with self.assertRaisesRegex(RuntimeError, "no system-assigned"):
            ensure_foundry_access(api, {})
        api.request.assert_not_called()

    def test_gateway_phase_does_not_publish_before_foundry_agents_exist(self):
        with patch("sys.argv", ["deploy_automation.py", "gateway"]), patch(
                "deploy_automation.AzureApi"), patch(
                "deploy_automation.configure_gateway", return_value=("https://model.example", "https://mcp.example")), patch(
                "deploy_automation.save_outputs") as save, patch(
                "deploy_automation.publish_automation") as publish:
            main()
        publish.assert_not_called()
        self.assertEqual(save.call_args.args[0]["MCP_CONNECTION_CONFIGURED"], "true")

    @patch("deploy_automation.time.sleep")
    def test_artifact_publication_retries_only_transient_host_conflicts(self, sleep):
        api = Mock()
        conflict = AzureRequestError(502, "ARM request failed with status 'Conflict'.")
        api.request.side_effect = [conflict, ({}, {})]
        files = {"game/workflow.json": {"kind": "Stateful"}}
        publish_workflow_artifacts(api, "https://automation.example/deploy", files)
        self.assertEqual(api.request.call_count, 2)
        self.assertEqual(api.request.call_args_list[0], api.request.call_args_list[1])
        sleep.assert_called_once_with(10)

        sleep.reset_mock()
        api.request.side_effect = [AzureRequestError(503, "The request timed out."), ({}, {})]
        publish_workflow_artifacts(api, "https://automation.example/deploy", files)
        sleep.assert_called_once_with(10)

        sleep.reset_mock()
        api.request.side_effect = AzureRequestError(502, "Workflow validation failed.")
        with self.assertRaisesRegex(AzureRequestError, "validation failed"):
            publish_workflow_artifacts(api, "https://automation.example/deploy", files)
        sleep.assert_not_called()

    @patch("deploy_automation.time.monotonic", side_effect=[0, 300])
    @patch("deploy_automation.time.sleep")
    def test_artifact_conflict_retries_have_a_deadline(self, sleep, monotonic):
        api = Mock()
        api.request.side_effect = AzureRequestError(409, "Conflict")
        with self.assertRaises(AzureRequestError):
            publish_workflow_artifacts(api, "https://automation.example/deploy", {})
        api.request.assert_called_once()
        sleep.assert_not_called()

    def test_http_errors_include_field_diagnostics_without_signed_urls_or_request_bodies(self):
        payload = {"error": {
            "message": "Invalid fields.",
            "details": [{"target": "supportedEndpoints[0]", "message": "Must start with '/'."}],
        }}
        url = "https://gateway.example/models?sig=private-signature"
        error = HTTPError(url, 400, "Bad Request", {}, io.BytesIO(json.dumps(payload).encode()))
        with patch("deploy_automation.urlopen", side_effect=error):
            with self.assertRaises(AzureRequestError) as raised:
                request_json(url, "PUT", {"key": "private-key"})
        message = str(raised.exception)
        self.assertIn("supportedEndpoints[0]: Must start with '/'", message)
        self.assertNotIn("private-signature", message)
        self.assertNotIn("private-key", message)

    def test_registers_native_model_paths_and_mcp_key_header(self):
        api = Mock()
        api.request.side_effect = [
            ({"primaryKey": "test-runtime-key"}, {}),
            ({}, {}),
        ]
        environment = {
            "AI_GATEWAY_RESOURCE_ID": "/gateway",
            "AI_GATEWAY_URL": "https://assigned.gateway.example",
            "FOUNDRY_ACCOUNT_RESOURCE_ID": "/account",
            "FOUNDRY_PROJECT_RESOURCE_ID": "/account/projects/demo",
            "FOUNDRY_ACCOUNT_ENDPOINT": "https://foundry.example",
            "MODEL_DEPLOYMENT": "gpt-4.1",
            "GAME_TRACKER_API_URL": "https://tracker.example",
        }
        document = {"paths": {"/sessions": {"get": {}, "post": {}},
                              "/sessions/last": {"get": {}}}}
        with patch.dict("os.environ", environment), patch(
                "deploy_automation.request_json", return_value=(document, {})):
            configure_gateway(api)
        properties = api.put.call_args_list[1].args[1]
        self.assertEqual(properties["supportedEndpoints"],
                         ["/v1/chat/completions", "/v1/responses"])
        connection = api.request.call_args.args[2]["properties"]
        self.assertEqual(connection["credentials"]["keys"], {"api-key": "test-runtime-key"})

    def test_uses_assigned_origin_and_documented_runtime_routes(self):
        self.assertEqual(runtime_endpoints("https://assigned.gateway.example/"), (
            "https://assigned.gateway.example/default/models/openai/v1",
            "https://assigned.gateway.example/default/toolservers/game-sessions/mcp",
        ))

    def test_rejects_invalid_gateway_origins(self):
        for url in ["", "http://gateway.example", "https://gateway.example/path",
                    "https://gateway.example?key=secret", "https://user:pass@gateway.example"]:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    runtime_endpoints(url)

    def test_imports_only_the_three_session_operations(self):
        document = {
            "openapi": "3.1.0", "info": {"title": "Tracker", "version": "1"},
            "servers": [{"url": "https://placeholder.example"}],
            "paths": {
                "/health": {"get": {"operationId": "health"}},
                "/sessions": {
                    "get": {"operationId": "list"}, "post": {"operationId": "record"},
                    "delete": {"operationId": "delete"},
                },
                "/sessions/last": {"get": {"operationId": "last"}},
            },
        }
        imported = tracker_openapi(document, "https://tracker.example")
        self.assertEqual(imported["servers"], [{"url": "https://tracker.example"}])
        self.assertEqual(set(imported["paths"]), {"/sessions", "/sessions/last"})
        self.assertEqual(set(imported["paths"]["/sessions"]), {"get", "post"})
        self.assertEqual(set(imported["paths"]["/sessions/last"]), {"get"})


if __name__ == "__main__":
    unittest.main()
