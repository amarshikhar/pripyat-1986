# Pripyat-1986 x Microsoft Hackathon Integration Plan
7-step integration plan:

Azure Subscription — activate hackathon credits, create resource group
Azure OpenAI — deploy a model (gpt-4o), get endpoint + key
Connect Pripyat — just flip USE_AZURE=true in .env (already supported!)
Azure AI Foundry — create a project, test your 3 system prompts in Playground, set up evaluation + tracing
Deploy to Azure — App Service (simplest) or Container Apps
GitHub Copilot — use for dev acceleration (chat, code completion, PR summaries)
Bonus — Cosmos DB audit trail, AI Search RAG, Application Insights
The good news: your codebase is already Azure-ready. The llm_client.py already has AsyncAzureOpenAI support, and config.py is fully parameterized. The core integration is literally just setting 4 environment variables.
## Context
Pripyat-1986 is a multi-agent Chernobyl crisis simulation. The codebase already has Azure OpenAI client support (`USE_AZURE` flag, `AsyncAzureOpenAI` in `llm_client.py`), Bicep IaC in `infra/`, and migration annotations throughout. This plan connects it to a Microsoft hackathon environment (Azure subscription, GitHub Copilot, Azure AI Foundry).

---

## Step 1: Claim & Configure Azure Hackathon Subscription

1. Go to the hackathon portal and activate your Azure subscription/credits
2. Note your **Subscription ID** and **Tenant ID**
3. Install Azure CLI if not already:
   ```bash
   brew install azure-cli
   az login
   az account set --subscription "<HACKATHON_SUBSCRIPTION_ID>"
   ```
4. Create a resource group:
   ```bash
   az group create --name rg-pripyat-1986 --location eastus2
   ```

---

## Step 2: Deploy Azure OpenAI Resource

1. Create the Azure OpenAI resource:
   ```bash
   az cognitiveservices account create \
     --name pripyat-openai \
     --resource-group rg-pripyat-1986 \
     --kind OpenAI \
     --sku S0 \
     --location eastus2
   ```
2. Deploy a model (gpt-4o-mini or gpt-4o):
   ```bash
   az cognitiveservices account deployment create \
     --name pripyat-openai \
     --resource-group rg-pripyat-1986 \
     --deployment-name pripyat-gpt4o \
     --model-name gpt-4o \
     --model-version "2024-11-20" \
     --model-format OpenAI \
     --sku-capacity 10 \
     --sku-name Standard
   ```
3. Get endpoint and key:
   ```bash
   az cognitiveservices account show \
     --name pripyat-openai -g rg-pripyat-1986 \
     --query properties.endpoint -o tsv

   az cognitiveservices account keys list \
     --name pripyat-openai -g rg-pripyat-1986 \
     --query key1 -o tsv
   ```

---

## Step 3: Connect Pripyat-1986 to Azure OpenAI

Update your `.env` file (the codebase already supports this):

```bash
# .env
USE_AZURE=true
OPENAI_BASE_URL=https://pripyat-openai.openai.azure.com/
OPENAI_API_KEY=<key-from-step-2>
OPENAI_MODEL=pripyat-gpt4o          # deployment name, not model name
AZURE_API_VERSION=2024-12-01-preview
```

That's it — `llm_client.py` already switches to `AsyncAzureOpenAI` when `USE_AZURE=true`.

Test it:
```bash
cd pripyat-1986
python main.py --smoke-test
```

---

## Step 4: Set Up Azure AI Foundry (formerly AI Studio)

Azure AI Foundry is the hub for model management, prompt engineering, and evaluation.

1. Go to [ai.azure.com](https://ai.azure.com) → sign in with hackathon account
2. Create a **Project**:
   - Name: `pripyat-1986`
   - Hub: create new or use existing in your hackathon subscription
   - Region: same as your OpenAI resource (eastus2)
   - Connect your Azure OpenAI resource from Step 2
3. **Prompt Playground** — test your 3 system prompts directly:
   - Paste `RISK_SYSTEM_PROMPT` from `llm_client.py` → test with sample reactor states
   - Paste `DECISION_SYSTEM_PROMPT` → verify structured output works
   - Paste `DYATLOV_SYSTEM_PROMPT` → test adversarial dialogue generation
4. **Evaluation** (optional but impressive for hackathon):
   - Create evaluation datasets from `timeline_data.py` events
   - Run safety evaluations on agent outputs
   - Generate evaluation reports showing the guardrail pattern works
5. **Tracing** — enable Azure AI Inference tracing to log all LLM calls:
   ```bash
   pip install azure-ai-inference azure-monitor-opentelemetry
   ```
   Add to `llm_client.py`:
   ```python
   # At top of file
   from azure.monitor.opentelemetry import configure_azure_monitor
   configure_azure_monitor(connection_string="<APP_INSIGHTS_CONN_STRING>")
   ```

---

## Step 5: Deploy to Azure (Web Dashboard)

### Option A: Azure App Service (simplest for hackathon)

```bash
# Create App Service Plan
az appservice plan create \
  --name pripyat-plan \
  --resource-group rg-pripyat-1986 \
  --sku B1 --is-linux

# Create Web App
az webapp create \
  --name pripyat-1986-demo \
  --resource-group rg-pripyat-1986 \
  --plan pripyat-plan \
  --runtime "PYTHON:3.11"

# Set env vars
az webapp config appsettings set \
  --name pripyat-1986-demo \
  --resource-group rg-pripyat-1986 \
  --settings \
    USE_AZURE=true \
    OPENAI_BASE_URL=https://pripyat-openai.openai.azure.com/ \
    OPENAI_API_KEY=<key> \
    OPENAI_MODEL=pripyat-gpt4o

# Deploy code
az webapp up --name pripyat-1986-demo --runtime "PYTHON:3.11"
```

**Startup command** (set in Azure Portal → Configuration → General Settings):
```
gunicorn -k uvicorn.workers.UvicornWorker web:app --bind 0.0.0.0:8000
```

Note: App Service supports WebSockets — enable it in Configuration → General Settings → Web Sockets: ON.

### Option B: Azure Container Apps (if you want containers)

```bash
# Build and push to ACR
az acr create --name pripyatacr --resource-group rg-pripyat-1986 --sku Basic
az acr build --registry pripyatacr --image pripyat-1986:latest .

# Deploy
az containerapp create \
  --name pripyat-1986 \
  --resource-group rg-pripyat-1986 \
  --image pripyatacr.azurecr.io/pripyat-1986:latest \
  --target-port 5005 \
  --ingress external
```

---

## Step 6: GitHub Copilot Integration

GitHub Copilot is a dev tool, not a runtime integration. Here's how to leverage it for the hackathon:

1. **Copilot in VS Code** — should already be active with hackathon GitHub access
   - Use it to write new agents, extend physics models, add evaluation logic
2. **Copilot Chat** — ask it questions about the codebase
   - `@workspace explain the guardrail pattern in agents.py`
3. **Copilot for PRs** — if demoing on GitHub, Copilot auto-generates PR summaries
4. **GitHub Copilot Workspace** — if available in hackathon, use it to plan feature branches

---

## Step 7: Optional Enhancements (Hackathon Bonus Points)

### 7a. Azure Cosmos DB for Audit Trail
Replace `output/agent_state.json` with immutable Cosmos DB records:
```bash
az cosmosdb create --name pripyat-cosmos --resource-group rg-pripyat-1986
az cosmosdb sql database create --account-name pripyat-cosmos -g rg-pripyat-1986 --name pripyat
az cosmosdb sql container create --account-name pripyat-cosmos -g rg-pripyat-1986 \
  --database-name pripyat --name decisions \
  --partition-key-path /tick_agent_ts
```

### 7b. Azure AI Search for IAEA Knowledge Base
Add retrieval-augmented generation (RAG) for the risk/decision agents:
```bash
az search service create --name pripyat-search -g rg-pripyat-1986 --sku free
```

### 7c. Application Insights for Observability
```bash
az monitor app-insights component create \
  --app pripyat-insights -g rg-pripyat-1986 --location eastus2
```

---

## Quick Reference: Files to Modify

| File | What to Change |
|------|---------------|
| `.env` | Set `USE_AZURE=true` + Azure endpoint/key/model |
| `requirements.txt` | Uncomment Azure packages if using Cosmos/Search |
| `llm_client.py` | Add Foundry tracing (optional) |
| `config.py` | No changes needed — already parameterized |
| New: `Dockerfile` | If using Container Apps (Option B) |
| New: `startup.sh` | If using App Service (Option A) |

---

## Verification

1. `python main.py --smoke-test` — confirms Azure OpenAI connection works
2. `python main.py --web` — local web dashboard with Azure backend
3. Open Azure AI Foundry → Tracing → verify LLM calls appear
4. Access deployed URL → full demo running on Azure
