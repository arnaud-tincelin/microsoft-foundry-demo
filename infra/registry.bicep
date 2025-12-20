targetScope = 'resourceGroup'

@minLength(2)
param resourceToken string

@description('Main location for the resources')
param location string

@description('Tags that will be applied to all resources')
param tags object = {}

resource acr 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: 'acr${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource currentUserCanPushToAcr 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, deployer().objectId, acrPushRoleDefinition.id)
  properties: {
    roleDefinitionId: acrPushRoleDefinition.id
    principalId: deployer().objectId
    principalType: 'User'
    description: 'Allow deployer to push images to ACR'
  }
}

@description('This is the built-in ACR Push role. See https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/containers#acrpush')
resource acrPushRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '8311e382-0749-4cb8-b61a-304f252e45ec'
}

output loginServer string = acr.properties.loginServer
output acrId string = acr.id
output acrName string = acr.name
