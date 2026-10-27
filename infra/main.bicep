targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for Foundry and application resources; AI Gateway and Automation have their own locations.')
param location string

@description('Logic Apps Automation preview region, independent of Foundry and AI Gateway.')
param automationLocation string = 'westus'

@description('AI Gateway preview region, independent of the Foundry/hosted-agent region.')
@allowed([
  'eastus2'
  'swedencentral'
])
param aiGatewayLocation string = 'eastus2'

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
    gatewayPrincipalId: aiGatewayModule.outputs.principalId
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

module aiGatewayModule 'aiGateway.bicep' = {
  name: 'aiGateway'
  params: {
    location: aiGatewayLocation
    resourceToken: resourceToken
    tags:tags
  }
}

// The preview project PUT is create-only in practice; the azd hook checks before creating.
resource automationProject 'Microsoft.Logic/automationProjects@2026-04-01-preview' existing = {
  name: automationLocation == location ? 'automation-${resourceToken}' : 'automation-${resourceToken}-${automationLocation}'
}

output PROJECT_ENDPOINT string = foundryModule.outputs.projectEndpoint
output FOUNDRY_ACCOUNT_RESOURCE_ID string = foundryModule.outputs.accountResourceId
output FOUNDRY_ACCOUNT_ENDPOINT string = foundryModule.outputs.accountEndpoint
output FOUNDRY_PROJECT_RESOURCE_ID string = foundryModule.outputs.projectResourceId
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoringModule.outputs.appInsightsConnectionString
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registryModule.outputs.loginServer
output MODEL_DEPLOYMENT string = foundryModule.outputs.gpt41DeploymentName
output AI_GATEWAY_URL string = aiGatewayModule.outputs.gatewayUrl
output AI_GATEWAY_NAME string = aiGatewayModule.outputs.gatewayName
output AI_GATEWAY_RESOURCE_ID string = aiGatewayModule.outputs.gatewayResourceId
output GAME_TRACKER_API_URL string = containerAppsModule.outputs.gameSessionTrackerAppUrl
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output AUTOMATION_PROJECT_NAME string = automationProject.name
output AUTOMATION_PROJECT_RESOURCE_ID string = automationProject.id
output AUTOMATION_LOCATION string = automationLocation
