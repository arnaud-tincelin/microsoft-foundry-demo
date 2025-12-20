# Microsoft Foundry Demo Repository

## Deployment

Note: hosted agents are only available in **North Central US** region at the moment

1. Deploy the infrastructure with AZD

    ```bash
    azd up
    ```

## Demo

All demo can be run independently

### Demo: Microsoft Agent Framework

> How do I get started with agents?

1. Review the content of [./selfHostedAgent/hostedAgent.py](./selfHostedAgent/hostedAgent.py): with 3 lines of code we can create an agent and expose it as an API
1. Call the agent from a local docker container:

    ```bash
    docker build -t myagent --file selfHostedAgent/Dockerfile selfHostedAgent/. # you may skip this and use the image in ACR
    docker run -d --name myagent -p 8088:8088 --gpus all myagent
    curl -X POST http://localhost:8088/responses -H "Content-Type: application/json" -d '{"input": "Where is Paris?", "stream": false}'
    ```

### Demo: Hosted Agent

> I have an agent, how to host it?

1. Review the content of [./hooks/deploy_agents.py](./hooks/deploy_agents.py) to show how to leverage the Azure AI Foundry SDK to create different Agents
1. From Azure portal, go to the **ollama-agent**, start it and play with it as any other agent
1. Demonstrate the traces & publish 
1. From **App Insights**, select **Agents** from the menu and review the metrics

### Demo: Workflows

> I have several agents running in Foundry, how to make them work together?

1. Showcase the **gameMaster** and the **player** agents from the playground
1. Explain the **guess-my-number** workflow and run it with the **Preview** button
1. Using the [Microsoft Foundry extension for vscode](https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.vscode-ai-foundry), load the workflow in vs code and click on **Generate code** to translate the visual workflow to python (or .net) code with Microsoft Agent Framework
1. Run the workflow from vscode:

    ```bash
    cd workflow
    uv sync
    uv run run_agent.py
    ```

### Demo: AI Gateway x Microsoft Foundry

1. From Foundry project portal, in **Operate**/**Admin**/**AI Gateway**, connect the APIM with your project. Review the options in **Token management** (limits & quotas) on the gpt-4.1 model deployment

### Demo: leverage MCP tool

> I want my agents to use some of my APIs, how to achieve that?

1. From the APIM portal, create a new MCP Server from the **Game Session Tracker API**. Add the following description:

    > API to perform operations about Guessing Games, such as to create a session or retrieve the last played games

1. From the Foundry project portal, create a new MCP tool (MCP), using the MCP Server from the previous step
1. Click on **Use in agent** and select the **mcpClient** agent
1. From the **mcpClient** agent playground, ask *what is the result of the latest game played?*. The agent shall prompt you for approval to call the MCP tool
