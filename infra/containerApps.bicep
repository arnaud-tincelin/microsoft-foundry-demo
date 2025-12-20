targetScope = 'resourceGroup'

param location string
param resourceToken string
param cosmosAccountName string
param cosmosDatabaseName string
param cosmosContainerName string
param lawName string
param appInsightsName string

@description('Tags that will be applied to all resources')
param tags object = {}

@description('Name for the Azure Container Registry')
param acrName string

resource acr 'Microsoft.ContainerRegistry/registries@2025-11-01' existing = {
  name: acrName
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2025-11-01-preview' existing = {
  name: cosmosAccountName
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-07-01' existing = {
  name: lawName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

// User-assigned managed identity for Container App
resource gameSessionTrackerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview' = {
  name: 'game-session-tracker-${resourceToken}'
  location: location
  tags: tags
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2025-10-02-preview' = {
  name: 'ca-env-${resourceToken}'
  location: location
  tags: tags
  properties: {
    zoneRedundant: false
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    appInsightsConfiguration: {
      connectionString: appInsights.properties.ConnectionString
    }
  }
}

resource gameSessionTrackerApp 'Microsoft.App/containerApps@2025-10-02-preview' = {
  name: 'tracker-api-${resourceToken}'
  location: location
  tags: union(tags, { 'azd-service-name': 'game-session-tracker-api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${gameSessionTrackerIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: gameSessionTrackerIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp-game-server'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'AZURE_CLIENT_ID'
              value: gameSessionTrackerIdentity.properties.clientId
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosAccount.properties.documentEndpoint
            }
            {
              name: 'COSMOS_DATABASE_NAME'
              value: cosmosDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER_NAME'
              value: cosmosContainerName
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }

  dependsOn: [
    acrPullRole
  ]
}

// Assign Cosmos DB Data Contributor role to Container App managed identity
resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-11-01-preview' = {
  name: guid(gameSessionTrackerIdentity.id, cosmosAccount.id, 'dataContributor')
  parent: cosmosAccount
  properties: {
    roleDefinitionId: resourceId(
      'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions',
      cosmosAccount.name,
      '00000000-0000-0000-0000-000000000002'
    )
    principalId: gameSessionTrackerIdentity.properties.principalId
    scope: cosmosAccount.id
  }
}

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(gameSessionTrackerIdentity.id, acr.id, 'acrPull')
  scope: acr
  properties: {
    roleDefinitionId: acrPullRoleDefinition.id
    principalId: gameSessionTrackerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Assign ACR Pull role to Container App managed identity'
  }
}

@description('This is the built-in ACR Pull role. See https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/containers#acrpull')
resource acrPullRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
}

output gameSessionTrackerAppUrl string = 'https://${gameSessionTrackerApp.properties.configuration.ingress.fqdn}'
output gameSessionTrackerAppIdentityPrincipalId string = gameSessionTrackerIdentity.properties.principalId
output gameSessionTrackerAppIdentityId string = gameSessionTrackerIdentity.id
