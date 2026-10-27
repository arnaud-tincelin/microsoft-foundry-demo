# Game Session Tracker API - Container Apps Deployment

FastAPI REST API for game session tracking, deployed to Azure Container Apps with Cosmos DB. Logic Apps Automation records completed games through the REST endpoint; agents access selected operations as MCP tools through the dedicated AI Gateway.

## Deployment

1. Run `azd up` from the repository root to provision infrastructure and build/deploy this service.
1. Read the backend URL with `azd env get-value GAME_TRACKER_API_URL`.
1. Follow [AI Gateway setup](../demo/AIGateway/README.md) to import the live `/openapi.json` as MCP tools. Classic `az apim api import` is not used with the dedicated gateway.

## API Endpoints

- **POST /sessions** - Record a completed game session
- **GET /sessions** - Retrieve recent game sessions (query param: `limit`)
- **GET /sessions/last** - Get the most recent game session
- **GET /health** - Health check endpoint
- **GET /openapi.json** - OpenAPI specification
- **GET /docs** - Swagger UI documentation

## Configuration

- **Managed Identity**: Container App uses system-assigned identity with Cosmos DB Data Contributor role
- **Cosmos DB authentication**: DefaultAzureCredential uses the Container App's managed identity.
- **Inbound authentication**: The demo REST backend is public and unauthenticated. The gateway authenticates MCP clients, but does not protect direct backend HTTP calls. Add backend authentication/network restrictions before production use.
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
