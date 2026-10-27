# Demo: AI Gateway preview x Microsoft Foundry

This repo provisions the dedicated `Microsoft.ApiManagement/aigateways@2026-09-01-preview` resource with a system-assigned identity, not `BasicV2` or the retired APIM service `AIGateway` SKU. `AI_GATEWAY_LOCATION` defaults to `eastus2`, independently of the Foundry region; `swedencentral` is also supported.

## Deploy models and MCP tools

Run `azd up`. After deploying the tracker, the post-deploy hook:

1. Registers the Foundry account and its `gpt-4.1` deployment using managed-identity authentication. Bicep assigns the gateway identity **Azure AI User** on the Foundry account.
1. Creates a `gpt-4.1` routing alias and obtains its OpenAI-compatible invocation endpoint from the service response.
1. Creates a runtime access key.
1. Imports the deployed tracker's `/openapi.json`, using the actual Container App URL and exposing only the three session operations: record a session, retrieve recent sessions, and get the last game outcome. `/health` is not an agent tool.
1. Retrieves the MCP invocation URL and configures the Foundry project's `game-sessions-tracker` connection, the `mcpClient` agent, and the Automation application.

No separate portal import or reprovisioning step is needed. Do not use classic `az apim api import`, APIM subscription APIs, old MCP paths, or a guessed runtime hostname against this dedicated resource.

The model endpoint accepts a runtime key in its authorization header or `api-key`. The MCP endpoint requires `api-key`; authorization-scheme and classic APIM subscription headers are rejected there. The Foundry MCP connection stores the runtime key in a custom `api-key` header. Automation instead invokes the real Foundry agents through its managed-identity project connection; those calls do not traverse the gateway or require a gateway key.

The preview API does not return per-asset invocation URLs. Deployment uses the service-assigned `properties.frontend.defaultHostname` with the [documented runtime routes](https://learn.microsoft.com/azure/api-management/ai-gateway-manage-models-tools): `/default/models/openai/v1` and `/default/toolservers/game-sessions/mcp`.

`MCP_SERVER_URL` and `AI_GATEWAY_MODEL_BASE_URL` are saved in ignored azd state. Keep `.azure` private: it also contains the signed Automation callback URL. Runtime keys grant access to all published gateway assets, so use separate gateways when isolation is required.

The demo tracker backend uses **None** authentication and remains directly accessible; gateway authentication does not secure direct REST access. Configure backend authentication and network restrictions before production use.

## Demonstrate governance

Open [AI Gateway](https://ai.gateway.azure.com/) and select the resource named by `azd env get-value AI_GATEWAY_NAME`. Use `AI_GATEWAY_RESOURCE_ID` to distinguish it from an old APIM service.

Call the imported model from the gateway playground to generate model traffic. Run [Logic Apps Automation](../Automation/README.md) to record a game, then query it with `mcpClient` to exercise gateway MCP traffic. Review supported token/request limits and configure a telemetry destination before expecting token metrics. Foundry's Application Insights connection does not automatically configure gateway telemetry.

Verify MCP tool discovery and a representative tool call before opening [the Foundry MCP demo](../MCP/README.md). Direct MCP clients must perform initialization and use supported streamable HTTP transport; a bare `tools/list` POST is not a complete handshake.

Existing deployments are not automatically deleted or migrated. Validate new endpoints, credentials, aliases, and tools before removing old resources. The dedicated gateway has different limitations, including no private endpoints and no gateway content-safety policy at migration time; use Foundry guardrails where required.

References: [dedicated-resource migration and authentication](https://learn.microsoft.com/azure/api-management/ai-gateway-resource), [model and MCP setup](https://learn.microsoft.com/azure/api-management/ai-gateway-manage-models-tools). Older examples may show legacy hosts and headers; use the dedicated-resource contract and service-returned URLs.
