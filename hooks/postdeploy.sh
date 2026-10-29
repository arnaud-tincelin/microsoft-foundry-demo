#!/bin/bash
set -euo pipefail

# Git Bash must not rewrite ARM resource IDs as Windows filesystem paths.
export MSYS_NO_PATHCONV=1
export MSYS2_ENV_CONV_EXCL="${MSYS2_ENV_CONV_EXCL:+${MSYS2_ENV_CONV_EXCL};}AI_GATEWAY_RESOURCE_ID;FOUNDRY_ACCOUNT_RESOURCE_ID;FOUNDRY_PROJECT_RESOURCE_ID;AUTOMATION_PROJECT_RESOURCE_ID"

echo "Post-deployment: Configuring AI assets and Automation..."
echo ""

load_outputs() {
  set -a
  eval "$(azd env get-values)"
  set +a
}

echo "Loading Bicep outputs into environment..."
load_outputs
echo ""

echo "Configuring AI Gateway and the Foundry MCP connection..."
cd hooks
uv sync --frozen
uv run --frozen deploy_automation.py gateway
load_outputs
echo "Deploying the Foundry prompt and MCP agents..."
uv run --frozen deploy_agents.py managed
load_outputs
echo "Publishing the shared-conversation Logic Apps Automation workflow..."
uv run --frozen deploy_automation.py automation
load_outputs
echo "Verifying a completed and recorded Automation game..."
uv run --frozen ../automation/run_workflow.py
cd ..
echo ""

echo "Building hosted agent container..."
AGENT_IMAGE_TAG="$(date -u +%Y%m%d%H%M%S)"
az acr build \
  --subscription "${AZURE_SUBSCRIPTION_ID}" \
  --registry "${AZURE_CONTAINER_REGISTRY_ENDPOINT}" \
  --image hostedagent:$AGENT_IMAGE_TAG \
  --file hostedAgent/Dockerfile \
  hostedAgent/ \
  --no-logs

export CONTAINER_IMAGE="${AZURE_CONTAINER_REGISTRY_ENDPOINT}/hostedagent:${AGENT_IMAGE_TAG}"
echo ""

echo "Deploying and verifying the hosted Foundry agent..."
cd hooks
uv run --frozen deploy_agents.py hosted
cd ..
echo ""

echo "Infrastructure, gateway assets, Foundry agents, and Logic Apps Automation deployed."
