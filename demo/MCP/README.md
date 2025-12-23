# MCP Tool in Microsoft Foundry with AI Gateway

> I want my agents to use some of my APIs, how to achieve that?

1. From the APIM portal, create a new MCP Server from the **Game Session Tracker API**. Add the following description:

    > API to perform operations about Guessing Games, such as to create a session or retrieve the last played games

1. From the Foundry project portal, create a new MCP tool (MCP), using the MCP Server from the previous step
1. Click on **Use in agent** and select the **mcpClient** agent
1. From the **mcpClient** agent playground, ask *what is the result of the latest game played?*. The agent shall prompt you for approval to call the MCP tool
