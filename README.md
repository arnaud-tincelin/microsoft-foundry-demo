# Microsoft Foundry Demo Repository

This repository aims to demonstrate Microsoft Foundry features through quick demo.

## Deployment

Note: hosted agents are only available in **North Central US** region at the moment

1. Deploy the infrastructure with [AZD](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd)

    ```bash
    azd auth login
    azd up
    ```

## Demo

All demo can be run independently

- [Demo: Microsoft Agent Framework (MAF)](./demo/MAF/README.md)
- [Demo: Microsoft Foundry Hosted Agent](./demo/HostedAgent/README.md)
- [Demo: Microsoft Foundry Workflow](./demo/Workflow/README.md)
- [Demo: AI Gateway](./demo/AIGateway/README.md)
- [Demo: MCP](./demo/MCP/README.md)
