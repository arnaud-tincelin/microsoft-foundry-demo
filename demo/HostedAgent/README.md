# Demo: Hosted Agent

This example demonstrates how an agent can be hosted on Microsoft Foundry with Hosted Agents. More information on [my blog](https://medium.com/@arnaud.tincelin/deploy-hosted-agents-on-microsoft-foundry-complete-guide-0de13e4f835f).

> I have an agent, how to host it?

1. Review [hooks/deploy_agents.py](../../hooks/deploy_agents.py) to show how the Foundry SDK creates two kinds of agents:

    - Managed agents
    - Hosted agents (from a container)

    Orchestration is demonstrated separately with [Logic Apps Automation](../Automation/README.md), not a Foundry Workflow agent.

1. `azd up` builds a version-tagged image and creates **ollama-agent** with `container_configuration`, the supported **4 CPU / 8 GiB** tier, and the Responses **2.0.0** protocol. The CPU-only image omits Ollama's unused GPU libraries and package caches to fit the platform's image limit while retaining the baked-in `llama3.2:3b` model. Foundry provisions the container automatically; there is no separate start command. Deployment waits for the version to become active and requires a completed response from its agent-scoped OpenAI endpoint. Provisioning failures include the service's error code and message. From Azure portal, open its playground and try *where is Paris?*

   Model weights are baked into `/opt/ollama/models`, with `OLLAMA_MODELS` set during both build and runtime. They must not depend on `$HOME`: Foundry replaces it with a per-session home directory.

1. Review the **Traces** & **Publish** functionalities 
1. From **App Insights**, select **Agents** from the menu and review the metrics
