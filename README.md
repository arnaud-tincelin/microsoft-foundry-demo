# Microsoft Foundry Demo Repository

This repository demonstrates Microsoft Foundry agents, Azure Logic Apps Automation, and the Azure API Management AI Gateway preview.

## Deployment

The orchestration demo uses [Logic Apps Automation](https://auto.azure.com/), not the deprecated Foundry Workflow agent feature.

1. Install [AZD](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd), Azure CLI, and [uv](https://docs.astral.sh/uv/). The post-deploy hook runs in Bash and uses `uv` with Python 3.13 to deploy the Foundry prompt and hosted agents.
1. Deploy the infrastructure:

    ```powershell
    azd auth login
    az login
    azd up
    ```

    Choose a region supporting your Foundry model and hosted agents (this demo originally targets **North Central US**). The gateway has an independent `AI_GATEWAY_LOCATION`, defaulting to **East US 2**; **Sweden Central** is also supported by the preview.
    Logic Apps Automation also has an independent `AUTOMATION_LOCATION`, defaulting to **West US**. Changing it does not relocate Foundry, the tracker, or the gateway.
1. The post-deploy hook imports the model and three tracker MCP tools, configures a runtime key and Foundry MCP connection, and deploys the Foundry prompt agents. It creates an Automation-side managed-identity connection to that Foundry project and publishes the [Logic Apps Automation workflow](./demo/Automation/README.md), pinned to those agent versions. It then requires a completed, recorded game before building and verifying the hosted agent. No portal import or separate reprovisioning step is needed.

`azd up` provisions the dedicated `Microsoft.ApiManagement/aigateways` resource, an Automation project/application, Foundry, Container Apps, Cosmos DB, ACR, and monitoring. Gateway assets use the service's supported management API; workflow publication uses the Automation regional API used by `auto.azure.com`.

Python restores use Microsoft's protected CFS feed, configured in each `pyproject.toml`. Checked-in `uv.lock` files make local and container restores reproducible; use `uv sync --frozen`. Hosted agents use the current Responses 2.0 protocol and automatic provisioning, not the retired container-start API.

Automation invokes the real Foundry `player` and `gameMaster` agents through its project connection. Its **application** managed identity receives **Foundry User** only on that Foundry project. These agent calls do not traverse AI Gateway; the gateway provides the separate model endpoint and the MCP tools used by `mcpClient`.

The main `guessing-game` workflow has an explicit top-level loop: **player -> gameMaster -> increment turn count -> win, ten-turn loss, or repeat**. It checks wins before the turn limit, preserves the original final messages, and records the outcome before responding.

The gateway uses API version `2026-09-01-preview`, its assigned `properties.frontend.defaultHostname`, and `Authorization: Bearer <runtime-key>`. It does not use classic APIM APIs, subscriptions, or `Ocp-Apim-Subscription-Key`. The old APIM `AIGateway` SKU is also [deprecated](https://learn.microsoft.com/azure/api-management/ai-gateway-resource); this repo targets its dedicated-resource successor.

The MCP connection specifically sends the runtime key in an `api-key` header; the preview MCP endpoint does not accept the model endpoint's Bearer authentication.

For an existing deployment, provisioning is incremental: old APIM resources and the old `guess-my-number` Foundry agent are **not** automatically deleted. Verify the new model, MCP tools, workflow, and recorded sessions before retiring old resources and credentials yourself.

## Demo

All demo can be run independently

- [Demo: Microsoft Agent Framework (MAF)](./demo/MAF/README.md)
- [Demo: Microsoft Foundry Hosted Agent](./demo/HostedAgent/README.md)
- [Demo: Logic Apps Automation](./demo/Automation/README.md)
- [Demo: AI Gateway](./demo/AIGateway/README.md)
- [Demo: MCP](./demo/MCP/README.md)
