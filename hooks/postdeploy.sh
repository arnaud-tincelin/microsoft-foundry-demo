#!/bin/bash
set -e

echo "Post-deployment: Creating and deploying agents..."
echo ""

# Load Bicep outputs into environment variables
echo "Loading Bicep outputs into environment..."
eval "$(azd env get-values)"
echo ""

echo "Building hosted agent container..."
AGENT_IMAGE_TAG="latest"
az acr build \
  --registry ${AZURE_CONTAINER_REGISTRY_ENDPOINT} \
  --image hostedagent:$AGENT_IMAGE_TAG \
  --file hostedAgent/Dockerfile \
  hostedAgent/ \
  --no-logs &

export CONTAINER_IMAGE="${AZURE_CONTAINER_REGISTRY_ENDPOINT}/hostedagent:${AGENT_IMAGE_TAG}"
echo ""

echo "Deploying agents to Foundry..."
cd hooks
uv sync
uv run deploy_agents.py
cd ..
echo ""

echo "Creating workflow environment file..."
./hooks/create_workflow_env.sh
echo ""

echo "Post-deployment complete!"
