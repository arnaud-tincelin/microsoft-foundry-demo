# Demo: Workflows

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

More information on [my blog](https://medium.com/@arnaud.tincelin/ai-foundry-workflows-your-workflow-your-way-91fcb997de04).
