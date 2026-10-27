# MCP Tool in Microsoft Foundry with AI Gateway

> I want my agents to use some of my APIs, how to achieve that?

Run `azd up` first. Its post-deploy hook completes [AI Gateway setup](../AIGateway/README.md), including OpenAPI-to-MCP registration, the runtime key, and the Foundry connection.

The **Game Session Tracker API** exposes three selected MCP tools through the dedicated AI Gateway. Use the `MCP_SERVER_URL` saved in ignored azd state. The **mcpClient** Foundry agent uses the `GuessingGameTracker` MCP tool and the project's `game-sessions-tracker` connection, which sends the runtime key in the `api-key` header. The preview MCP endpoint rejects Bearer authentication and classic APIM subscription headers.

1. Run [Logic Apps Automation](../Automation/README.md) once to persist a game result.
1. From the Foundry project portal, open the **mcpClient** agent playground.
1. Ask *what is the result of the latest game played?*. The agent should call the gateway's last-game tool and return the recorded result. If no game has been recorded, the tracker returns 404; this is not a gateway authentication failure.
