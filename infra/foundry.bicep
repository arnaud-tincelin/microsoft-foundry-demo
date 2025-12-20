targetScope = 'resourceGroup'

param resourceToken string

@description('Tags that will be applied to all resources')
param tags object = {}

@description('Main location for the resources')
param location string = 'northcentralus'

@description('Application Insights resource name')
param appInsightsName string

@description('Name for the Azure Container Registry')
param acrName string

resource acr 'Microsoft.ContainerRegistry/registries@2025-11-01' existing = {
  name: acrName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' = {
  name: 'foundry-${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: 'foundry-${resourceToken}'
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }

  resource gpt41Deployment 'deployments' = {
    name: 'gpt-4.1'
    sku: {
      name: 'GlobalStandard'
      capacity: 50
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: 'gpt-4.1'
        version: '2025-04-14'
      }
      versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
      currentCapacity: 50
      raiPolicyName: 'Microsoft.DefaultV2'
    }
  }

  resource project 'projects' = {
    name: 'demo-project'
    location: location
    identity: {
      type: 'SystemAssigned'
    }
    properties: {
      description: 'Demo Project'
      displayName: 'Demo Project'
    }

    resource appInsightConnection 'connections' = {
      name: 'appinsights'
      properties: {
        category: 'AppInsights'
        target: appInsights.id
        authType: 'ApiKey'
        isSharedToAll: true
        credentials: {
          key: appInsights.properties.ConnectionString
        }
        metadata: {
          ApiType: 'Azure'
          ResourceId: appInsights.id
        }
      }
    }
  }

  // resource agentsCapabilityHost 'capabilityHosts' = {
  //   name: 'agents'
  //   properties: {
  //     capabilityHostKind: 'Agents'
  //     #disable-next-line BCP037
  //     enablePublicHostingEnvironment: true
  //   }
  // }
}

resource aiFoundryProjectCanPullFromAcr 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, foundry::project.id, acrPullRoleDefinition.id)
  properties: {
    roleDefinitionId: acrPullRoleDefinition.id
    principalId: foundry::project.identity.principalId
    principalType: 'ServicePrincipal'
    description: 'Allow AI Foundry Project to pull images from ACR'
  }
}

resource currentUserCanPerformDataActionsOnFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, deployer().objectId, azureAiUserRoleDefinition.id)
  properties: {
    roleDefinitionId: azureAiUserRoleDefinition.id
    principalId: deployer().objectId
    principalType: 'User'
    description: 'Allow deployer to perfom Data actions on Foundry resource'
  }
}

@description('This is the built-in ACR Pull role. See https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/containers#acrpull')
resource acrPullRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
}

@description('This is the built-in Azure AI User role. See https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-azure-ai-foundry?view=foundry#azure-ai-user')
resource azureAiUserRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}

output projectEndpoint string = foundry::project.properties.endpoints['AI Foundry API']
output gpt41DeploymentName string = foundry::gpt41Deployment.name
