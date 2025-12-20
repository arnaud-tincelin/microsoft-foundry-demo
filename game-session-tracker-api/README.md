# Game Session Tracker API - Container Apps Deployment

FastAPI REST API for game session tracking, deployed to Azure Container Apps with Cosmos DB backend and exposed via Azure API Management.

## Deployment

1. Deploy Infrastructure (from root)

1. Configuration

    ```bash
    export ACR_NAME="aidemohostedagents7"
    export CONTAINER_APP_NAME="mcp-game-server"
    export APIM_NAME="ai-demo-ati7"
    export RESOURCE_GROUP="ai-demo7"
    ```

1. Build & Push Docker Image

    ```bash
    az acr build --registry $ACR_NAME --image mcp-game-server:latest --file mcp-game-server/Dockerfile mcp-game-server/.
    ```

1. Update Container App Image
    ```bash
    az containerapp update \
      --name $CONTAINER_APP_NAME \
      --resource-group $RESOURCE_GROUP \
      --image ${ACR_NAME}.azurecr.io/mcp-game-server:latest
    ```

1. Import API to APIM

    ```bash
    export CONTAINER_APP_URL=$(az containerapp show \
      --name $CONTAINER_APP_NAME \
      --resource-group $RESOURCE_GROUP \
      --query properties.configuration.ingress.fqdn -o tsv)
    
    az apim api import \
      --resource-group $RESOURCE_GROUP \
      --service-name $APIM_NAME \
      --path game-sessions \
      --api-id game-session-api \
      --specification-format OpenApi \
      --specification-url https://${CONTAINER_APP_URL}/openapi.json \
      --service-url https://${CONTAINER_APP_URL}
    ```

1. Get API Gateway URL

    ```bash
    az apim show \
      --name $APIM_NAME \
      --resource-group $RESOURCE_GROUP \
      --query gatewayUrl -o tsv
    ```

## API Endpoints

- **POST /sessions** - Record a completed game session
- **GET /sessions** - Retrieve recent game sessions (query param: `limit`)
- **GET /sessions/last** - Get the most recent game session
- **GET /health** - Health check endpoint
- **GET /openapi.json** - OpenAPI specification
- **GET /docs** - Swagger UI documentation

## Configuration

- **Managed Identity**: Container App uses system-assigned identity with Cosmos DB Data Contributor role
- **Authentication**: No credentials needed - DefaultAzureCredential uses managed identity
- **Environment Variables**: Automatically injected via Bicep
  - `COSMOS_ENDPOINT`
  - `COSMOS_DATABASE_NAME`
  - `COSMOS_CONTAINER_NAME`

## Example Usage

**Record a game session:**
```
Use the record_game_session tool with:
- conversation_id: "session-001"
- number_picked: 7
- status: "won"
```

**Get recent sessions:**
```
Use the get_recent_sessions tool with limit: 5
```

**Check last game outcome:**
```
Use the get_last_game_outcome tool (no parameters needed)
```
