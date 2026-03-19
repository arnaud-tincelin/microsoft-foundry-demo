# MCP Tool in Microsoft Foundry with AI Gateway

> I want my agents to use some of my APIs, how to achieve that?

The MCP server and tool are automatically deployed by `azd up`:

- The **Game Session Tracker API** is exposed as an MCP server in APIM at `<APIM_GATEWAY_URL>/game-session-mcp/mcp`
- The **mcpClient** agent in Foundry is configured with the `GuessingGameTracker` MCP tool pointing to the APIM MCP server

1. From the Foundry project portal, open the **mcpClient** agent playground
1. Ask *what is the result of the latest game played?*. The agent shall use the MCP tool to call the APIM MCP server and return the results
