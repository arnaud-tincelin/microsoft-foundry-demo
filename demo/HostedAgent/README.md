# Demo: Hosted Agent

This example demonstrates how an agent can be hosted on Microsoft Foundry with Hosted Agents. More information on [my blog](https://medium.com/@arnaud.tincelin/deploy-hosted-agents-on-microsoft-foundry-complete-guide-0de13e4f835f).

> I have an agent, how to host it?

1. Review the content of [./hooks/deploy_agents.py](./hooks/deploy_agents.py) to show how to leverage the Azure AI Foundry SDK to create different Agents. This script creates 3 kinds of agents:

    - Managed agents
    - Hosted agents (from a container)
    - Workflows agents : integration of managed and hosted agents to handle more complex use cases

1. From Azure portal, go to the **ollama-agent**, start it and play with it as any other agent. For instance, you may use the same prompt as before: *where is Paris?*
1. Review the **Traces** & **Publish** functionalities 
1. From **App Insights**, select **Agents** from the menu and review the metrics
