#!/bin/bash
set -e

echo "📝 Creating workflow .env file..."

SUBSCRIPTION_ID=$(azd env get-value AZURE_SUBSCRIPTION_ID)
PROJECT_ENDPOINT=$(azd env get-value PROJECT_ENDPOINT)
APIM_API_URL=$(azd env get-value APIM_API_URL)
APIM_NAME=$(azd env get-value APIM_NAME)
RESOURCE_GROUP=$(azd env get-value AZURE_RESOURCE_GROUP)

echo "🔑 Retrieving APIM subscription key..."

# Create or get the built-in all-access subscription
# APIM creates a built-in subscription by default, but we'll ensure one exists
APIM_SUB_ID=$(az rest \
  --method GET \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.ApiManagement/service/${APIM_NAME}/subscriptions?api-version=2024-10-01-preview" \
  --query "value[0].name" -o tsv 2>/dev/null || echo "")

# Get the primary key
APIM_SUBSCRIPTION_KEY=$(az rest \
  --method POST \
  --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.ApiManagement/service/${APIM_NAME}/subscriptions/${APIM_SUB_ID}/listSecrets?api-version=2024-10-01-preview" \
  --query "primaryKey" -o tsv)

# Create .env file
cat > workflow/.env << EOF
AZURE_SUBSCRIPTION_ID="${SUBSCRIPTION_ID}"
PROJECT_ENDPOINT="${PROJECT_ENDPOINT}"
APIM_API_URL="${APIM_API_URL}"
APIM_SUBSCRIPTION_KEY="${APIM_SUBSCRIPTION_KEY}"
EOF

echo "✅ Created workflow/.env with environment configuration"
echo "   Subscription ID: ${SUBSCRIPTION_ID}"
echo "   Project Endpoint: ${PROJECT_ENDPOINT}"
echo "   API URL: ${APIM_API_URL}"
echo "   Subscription Key: ${APIM_SUBSCRIPTION_KEY:0:10}..."
