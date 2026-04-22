# PRIPYAT-1986 — Infrastructure & Deployment Blueprint

## Architecture Overview

```
┌─────────────────── Azure (East US 2) ───────────────────────────┐
│                                                                  │
│  ┌─── AKS Cluster ────────────────────────────────────────────┐ │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐ │ │
│  │  │ FastAPI Pod │  │ Dashboard  │  │ Timeline Engine Pod  │ │ │
│  │  │ (API + WS)  │  │ (static)   │  │ (Simulation Loop)    │ │ │
│  │  └──────┬──────┘  └────────────┘  └──────────┬───────────┘ │ │
│  │         │                                     │             │ │
│  └─────────┼─────────────────────────────────────┼─────────────┘ │
│            │                                     │               │
│  ┌─────────▼──────────────────────────────────────▼────────────┐ │
│  │                    Azure Services                           │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌───────────────────┐ │ │
│  │  │ Azure OpenAI  │  │ Cosmos DB   │  │ Event Hubs        │ │ │
│  │  │ (gpt-4o-mini) │  │ (state +    │  │ (telemetry        │ │ │
│  │  │               │  │  audit)     │  │  stream)          │ │ │
│  │  └──────────────┘  └─────────────┘  └───────────────────┘ │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌───────────────────┐ │ │
│  │  │ AI Search     │  │ Key Vault   │  │ Azure Monitor +   │ │ │
│  │  │ (IAEA docs)   │  │ (secrets)   │  │ Log Analytics     │ │ │
│  │  └──────────────┘  └─────────────┘  └───────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Azure Container Registry (ACR) — Docker image storage       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Application Gateway + WAF v2 — TLS termination + firewall   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## Resource Definitions (Bicep)

```bicep
// main.bicep — PRIPYAT-1986 Infrastructure
// Deploy: az deployment group create -g rg-pripyat-1986 -f main.bicep

param location string = 'eastus2'
param env string = 'staging' // 'staging' | 'production'

// ── Azure OpenAI ──────────────────────────────────────
resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'oai-pripyat-${env}'
  location: location
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: 'pripyat-${env}'
    publicNetworkAccess: 'Disabled'
  }
}

// ── Cosmos DB (agent state + immutable audit trail) ───
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'cosmos-pripyat-${env}'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    publicNetworkAccess: 'Disabled'
  }
}

// ── Event Hubs (telemetry stream) ─────────────────────
resource eventhubs 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: 'evh-pripyat-${env}'
  location: location
  sku: { name: env == 'production' ? 'Standard' : 'Basic', capacity: 1 }
}

// ── AI Search (IAEA knowledge base) ───────────────────
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: 'srch-pripyat-${env}'
  location: location
  sku: { name: 'basic' }
}

// ── Key Vault (secrets) ───────────────────────────────
resource keyvault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-pripyat-${env}'
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableSoftDelete: true
    enablePurgeProtection: true
    publicNetworkAccess: 'disabled'
  }
}

// ── Log Analytics + Monitor ───────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-pripyat-${env}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 90
  }
}

// ── AKS Cluster ───────────────────────────────────────
resource aks 'Microsoft.ContainerService/managedClusters@2024-05-01' = {
  name: 'aks-pripyat-${env}'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    dnsPrefix: 'pripyat-${env}'
    agentPoolProfiles: [{
      name: 'default'
      count: env == 'production' ? 3 : 1
      vmSize: 'Standard_D2s_v5'
      mode: 'System'
    }]
    networkProfile: {
      networkPlugin: 'azure'
      serviceCidr: '10.0.0.0/16'
      dnsServiceIP: '10.0.0.10'
    }
  }
}

// ── Container Registry ────────────────────────────────
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acrpripyat${env}'
  location: location
  sku: { name: 'Basic' }
}
```

---

## Environment Topology

| Environment | AKS Nodes | Cosmos Tier | OpenAI Tier | Purpose |
|-------------|-----------|-------------|-------------|---------|
| **Local (Dev)** | N/A | In-memory | OpenAI API | Developer testing (`python main.py --web`) |
| **Staging** | 1 node | Serverless | S0 (Basic) | Integration testing, smoke tests |
| **Production** | 3 nodes | Provisioned (400 RU) | S0 (Standard) | Live demonstration, hackathon demo |

---

## CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: PRIPYAT-1986 Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: python main.py --smoke-test    # Validate agent pipeline

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/docker-login@v2
        with:
          login-server: acrpripyatstaging.azurecr.io
          username: ${{ secrets.ACR_USERNAME }}
          password: ${{ secrets.ACR_PASSWORD }}
      - run: |
          docker build -t acrpripyatstaging.azurecr.io/pripyat:${{ github.sha }} .
          docker push acrpripyatstaging.azurecr.io/pripyat:${{ github.sha }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: azure/aks-set-context@v4
        with:
          resource-group: rg-pripyat-1986
          cluster-name: aks-pripyat-staging
      - run: kubectl set image deployment/pripyat pripyat=acrpripyatstaging.azurecr.io/pripyat:${{ github.sha }}
      - run: kubectl rollout status deployment/pripyat --timeout=120s

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production    # Requires manual approval
    steps:
      - uses: azure/aks-set-context@v4
        with:
          resource-group: rg-pripyat-1986
          cluster-name: aks-pripyat-production
      - run: kubectl set image deployment/pripyat pripyat=acrpripyatstaging.azurecr.io/pripyat:${{ github.sha }}
```

---

## Quick Start (Local)

```bash
# Clone and setup
git clone https://github.com/team/pripyat-1986.git
cd pripyat-1986
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your OpenAI API key

# Run
python main.py --smoke-test    # Validate pipeline (5 ticks)
python main.py --web           # Full simulation at http://localhost:8000
```
