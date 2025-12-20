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
}

output apimGatewayUrl string = apim.properties.gatewayUrl
output apimName string = apim.name
output gameSessionsApiUrl string = '${apim.properties.gatewayUrl}/${apim::gameTrackerAPI.properties.path}'
