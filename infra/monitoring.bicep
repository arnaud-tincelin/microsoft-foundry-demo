targetScope = 'resourceGroup'

param resourceToken string

@description('Main location for the resources')
param location string

@description('Tags that will be applied to all resources')
param tags object = {}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-07-01' = {
  name: 'law-${resourceToken}'
  location: location
  tags:tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appinsights-${resourceToken}'
  location: location
  tags:tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

output appInsightsId string = appInsights.id
output appInsightsName string = appInsights.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output lawName string = logAnalytics.name
