targetScope = 'resourceGroup'

param resourceToken string
param location string

@description('Tags that will be applied to all resources')
param tags object = {}

resource gateway 'Microsoft.ApiManagement/aigateways@2026-09-01-preview' = {
  name: 'aigw-${resourceToken}'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// Read the assigned hostname from ARM; it cannot be derived from the gateway name.
output gatewayUrl string = 'https://${gateway.properties.frontend.defaultHostname}'
output gatewayName string = gateway.name
output gatewayResourceId string = gateway.id
output principalId string = gateway.identity.principalId
