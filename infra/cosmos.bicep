targetScope = 'resourceGroup'

param resourceToken string

@description('Main location for the resources')
param location string

@description('Tags that will be applied to all resources')
param tags object = {}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2025-11-01-preview' = {
  name: 'cosmos-${resourceToken}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    enableFreeTier: false
  }

  resource database 'sqlDatabases' = {
    name: 'game-sessions-db'
    properties: {
      resource: {
        id: 'game-sessions-db'
      }
    }

    resource container 'containers' = {
      name: 'sessions'
      properties: {
        resource: {
          id: 'sessions'
          partitionKey: {
            paths: [
              '/conversation_id'
            ]
            kind: 'Hash'
          }
          indexingPolicy: {
            indexingMode: 'consistent'
            includedPaths: [
              {
                path: '/*'
              }
            ]
          }
        }
      }
    }
  }
}

output cosmosAccountName string = cosmosAccount.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = cosmosAccount::database.name
output containerName string = cosmosAccount::database::container.name
output cosmosAccountId string = cosmosAccount.id
