# PRIPYAT-1986 — Environment Track Declaration

## Track A: GitHub + Azure (+ optional Microsoft Fabric)

This submission is built on **Track A**, using GitHub for source control and CI/CD,
with Azure services for all cloud infrastructure.

## Azure Services Used

| Service | Role |
|---------|------|
| **Azure OpenAI** (gpt-4o-mini) | LLM reasoning for RiskAgent and DecisionAgent |
| **Azure Event Hubs** | Real-time reactor telemetry streaming |
| **Azure Cosmos DB** | Agent state, decision audit trail, tick history |
| **Azure AI Search** | Agentic retrieval over IAEA safety knowledge base |
| **Azure Key Vault** | Secret management (API keys, connection strings) |
| **Azure Monitor + Log Analytics** | Observability, alerting, agent pipeline health |
| **Azure Kubernetes Service (AKS)** | Container hosting for FastAPI backend + React dashboard |
| **Azure Container Registry** | Docker image storage |

## Not Used (Clarification)

- **Copilot Studio**: Not used in the current implementation. Identified as a
  future extension for building a low-code operator copilot for field workers.
- **Azure AI Foundry**: Referenced in early design as the orchestration framework.
  Current implementation uses a custom Python orchestrator with the same
  architectural pattern (pipeline agents with guardrails).
- **ADLS / Microsoft Fabric**: Not used. Data is streamed in-memory via Event Hubs
  and persisted to Cosmos DB. Fabric could be used for long-term analytics.

## Local Development

The prototype runs locally with `python main.py --web` using:
- OpenAI API (or Azure OpenAI with `USE_AZURE=true`)
- In-memory event bus (maps to Event Hubs)
- Local file state (maps to Cosmos DB)
- FastAPI + static HTML/JS dashboard (maps to AKS + React)

Every module has inline comments mapping local components to their Azure equivalents.
