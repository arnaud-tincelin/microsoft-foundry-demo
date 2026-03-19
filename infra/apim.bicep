targetScope = 'resourceGroup'

param resourceToken string
param location string
param publisherEmail string = 'admin@contoso.com'
param publisherName string = 'Contoso'
param gameTrackerServiceUrl string

@description('Tags that will be applied to all resources')
param tags object = {}

resource apim 'Microsoft.ApiManagement/service@2024-10-01-preview' = {
  name: 'apim-${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'BasicV2'
    capacity: 1
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
  }

  resource gameTrackerAPI 'apis' = {
    name: 'game-session-api'
    properties: {
      displayName: 'Game Session Tracker API'
      apiRevision: '1'
      subscriptionRequired: true
      format: 'openapi'
      value: loadTextContent('../game-session-tracker-api/openapi.yaml')
      serviceUrl: gameTrackerServiceUrl
      path: 'game-sessions'
      protocols: [
        'https'
      ]
      subscriptionKeyParameterNames: {
        header: 'Ocp-Apim-Subscription-Key'
        query: 'subscription-key'
      }
      isCurrent: true
    }
  }

  resource gameTrackerMcpServer 'apis' = {
    name: 'game-sessions-tracker'
    properties: {
      #disable-next-line BCP037
      type: 'mcp'
      displayName: 'Game Sessions Tracker'
      description: 'Track the sessions of the games played by agents'
      subscriptionRequired: true
      path: 'game-sessions-tracker'
      subscriptionKeyParameterNames: {
        header: 'Ocp-Apim-Subscription-Key'
        query: 'subscription-key'
      }
      protocols: [
        'https'
      ]
      #disable-next-line BCP037
      mcpTools: [
        {
          name: 'getTheMostRecentGameSession'
          description: 'Check if the player won or lost their most recent game. Returns details of the last game session including outcome, number picked, and timestamp.'
          operationId: '${gameTrackerAPI.id}/operations/get_last_game_outcome_sessions_last_get'
        }
        {
          name: 'recordACompletedGameSession'
          description: 'Record a completed game session with the conversation ID, number picked, and outcome.'
          operationId: '${gameTrackerAPI.id}/operations/record_game_session_sessions_post'
        }
        {
          name: 'retrieveRecentGameSessions'
          description: 'Retrieve the last N game sessions with all details.'
          operationId: '${gameTrackerAPI.id}/operations/get_recent_sessions_sessions_get'
        }
      ]
    }
  }

  resource mcpSubscription 'subscriptions' = {
    name: 'mcp-subscription'
    properties: {
      displayName: 'MCP Subscription'
      scope: '/apis'
      state: 'active'
    }
  }
}

output apimGatewayUrl string = apim.properties.gatewayUrl
output apimName string = apim.name
output gameSessionsApiUrl string = '${apim.properties.gatewayUrl}/${apim::gameTrackerAPI.properties.path}'
output mcpServerUrl string = '${apim.properties.gatewayUrl}/${apim::gameTrackerMcpServer.properties.path}/mcp'
output mcpServerCredentialKey string = apim::gameTrackerMcpServer.properties.subscriptionKeyParameterNames.header

@secure()
output mcpServerCredentialValue string = apim::mcpSubscription.listSecrets().primaryKey
