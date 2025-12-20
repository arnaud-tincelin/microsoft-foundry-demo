targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources but AI Foundry.')
@allowed(['northcentralus'])
param location string

#disable-next-line no-unused-vars
var resourceToken = toLower(uniqueString(resourceGroup().id, environmentName, location))

var tags = {
  'azd-env-name': environmentName
}

module foundryModule 'foundry.bicep' = {
  name: 'foundry'
  params: {
    resourceToken: resourceToken
    location: location
    appInsightsName: monitoringModule.outputs.appInsightsName
    acrName: registryModule.outputs.acrName
    tags:tags
  }
}

module monitoringModule 'monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    resourceToken: resourceToken
    tags:tags
  }
}

module registryModule 'registry.bicep' = {
  name: 'registry'
  params: {
    resourceToken: resourceToken
    location: location
    tags:tags
  }
}

module cosmosModule 'cosmos.bicep' = {
  name: 'cosmos'
  params: {
    resourceToken: resourceToken
    location: location
    tags:tags
  }
}

module containerAppsModule 'containerApps.bicep' = {
  name: 'containerApps'
  params: {
    location: location
    resourceToken: resourceToken
    cosmosAccountName: cosmosModule.outputs.cosmosAccountName
    cosmosDatabaseName: cosmosModule.outputs.databaseName
    cosmosContainerName: cosmosModule.outputs.containerName
    acrName: registryModule.outputs.acrName
    appInsightsName: monitoringModule.outputs.appInsightsName
    lawName: monitoringModule.outputs.lawName
    tags:tags
  }
}

module apimModule 'apim.bicep' = {
  name: 'apim'
  params: {
    location: location
    resourceToken: resourceToken
    gameTrackerServiceUrl: containerAppsModule.outputs.gameSessionTrackerAppUrl
    tags:tags
  }
}

output PROJECT_ENDPOINT string = foundryModule.outputs.projectEndpoint
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoringModule.outputs.appInsightsConnectionString
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registryModule.outputs.loginServer
output MODEL_DEPLOYMENT string = foundryModule.outputs.gpt41DeploymentName
output APIM_GATEWAY_URL string = apimModule.outputs.apimGatewayUrl
output APIM_API_URL string = apimModule.outputs.gameSessionsApiUrl
output APIM_NAME string = apimModule.outputs.apimName
output AZURE_RESOURCE_GROUP string = resourceGroup().name
