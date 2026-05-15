# PRIPYAT-1986

**Agentic AI Crisis Response Simulation — Chernobyl, Reimagined**

A multi-agent AI system that replays the Chernobyl disaster timeline (April 25–26, 1986) and demonstrates how autonomous AI agents with safety guardrails could have detected, intervened, and prevented the catastrophe — hours before the explosion.

Built as a functional prototype of the **Control Room of the Future (CRoF)** architecture used in modern utility grid operations.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-WebSocket-009688?logo=fastapi)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What It Does

The simulation processes **real historical reactor telemetry** through 5 specialized AI agents that run concurrently:

| Agent | Role | AI-Powered? |
|-------|------|:-----------:|
| **SensorAgent** | Monitors reactor telemetry against RBMK-1000 safety thresholds | Rule-based |
| **RiskAgent** | Compound risk assessment with rate-of-change analysis | ✅ LLM + rules |
| **DecisionAgent** | Autonomous safety decisions with hard guardrails | ✅ LLM + rules |
| **EvacuationAgent** | Logistics planning for 49,000 Pripyat residents | Rule-based |
| **CommsAgent** | Emergency communications + Gaussian plume radiation modeling | Rule-based |
| **DyatlovAgent** | Adversarial operator — fights AI decisions (historically accurate) | ✅ LLM + rules |

**Key design principle**: Rule-based safety guardrails (SCRAM, evacuation) **cannot** be overridden by AI output. LLM decisions can act *earlier* than rules but never *weaker*. Dyatlov's overrides can delay LLM decisions but never bypass hard guardrails.

---

## Quick Start

### Prerequisites

- Python 3.10+
- An OpenAI-compatible API key (OpenAI, Azure OpenAI, or OpenRouter)

### 1. Clone & Install

```bash
git clone https://github.com/amarshikhar/pripyat-1986.git
cd pripyat-1986
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your API key:

```env
# Option A: OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini

# Option B: Azure OpenAI
USE_AZURE=true
OPENAI_BASE_URL=https://your-resource.openai.azure.com/
OPENAI_API_KEY=your-azure-key
OPENAI_MODEL=your-deployment-name

# Option C: OpenRouter (or any OpenAI-compatible provider)
OPENAI_API_KEY=sk-or-v1-your-key
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=google/gemini-2.0-flash-001
```

> **No API key?** The simulation still runs fully — AI agents fall back to rule-based logic automatically.

### 3. Run

**Terminal dashboard** (Rich UI):
```bash
python main.py
```

**Web dashboard** (browser UI with real-time WebSocket):
```bash
python main.py --web
# Open http://localhost:8000
```

**Headless mode** (JSON output):
```bash
python main.py --no-dashboard
```

**Smoke test** (validate pipeline in 5 ticks):
```bash
python main.py --smoke-test
```

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--speed N` | Simulation speed multiplier | `60` (1 min = 1 simulated hour) |
| `--web` | Launch browser dashboard | off |
| `--port N` | Web dashboard port | `8000` |
| `--no-dashboard` | JSON output only | off |
| `--smoke-test` | Run 5 ticks to validate | off |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    main.py (Entry Point)                 │
│         CLI args → Simulator → Orchestrator → UI        │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              orchestrator.py (Message Bus)               │
│     In-memory pub/sub — routes events between agents    │
└──┬──────┬──────┬──────┬──────┬──────┬───────────────────┘
   │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼
Sensor  Risk  Decision  Evac  Comms  Dyatlov
Agent   Agent  Agent    Agent Agent  Agent
(rule)  (AI)   (AI)     (rule)(rule) (AI/adversarial)
   │      │      │
   │      │      └──► llm_client.py (OpenAI / Azure OpenAI)
   │      └──────────►
   └──────────────────► config.py (thresholds, weights)
                        timeline_data.py (historical events)
                        simulator.py (event replay engine)

┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
├──────────────────────┬──────────────────────────────────┤
│  dashboard.py (Rich) │  web.py + static/ (FastAPI+WS)  │
│  Terminal TUI        │  Browser dashboard               │
└──────────────────────┴──────────────────────────────────┘
```

### File Structure

```
pripyat-1986/
├── main.py              # Entry point — CLI, simulation loop
├── agents.py            # 6 agent implementations (Sensor, Risk, Decision, Evac, Comms, Dyatlov)
├── orchestrator.py      # Message bus + agent coordination pipeline
├── simulator.py         # Historical event replay engine with interpolation
├── timeline_data.py     # Chernobyl timeline events + reactor state data
├── timeline_engine.py   # Dual-timeline engine (historical vs AI counterfactual)
├── llm_client.py        # LLM client (OpenAI / Azure OpenAI compatible)
├── config.py            # Thresholds, weights, simulation parameters
├── physics.py           # RBMK-1000 reactor physics model
├── dashboard.py         # Rich terminal UI
├── web.py               # FastAPI + WebSocket server
├── static/              # Browser dashboard (HTML/CSS/JS + Plotly)
├── docs/                # Security model, responsible AI, operator UX, reusability
├── infra/               # Azure deployment guide
├── .env.example         # Environment template
└── requirements.txt     # Python dependencies
```

---

## How the Simulation Works

1. **Timeline replay**: The simulator replays 30+ historical events from April 25–26, 1986, interpolating reactor state between key moments.

2. **Agent pipeline** (each tick):
   - `SensorAgent` checks telemetry against RBMK thresholds → emits alerts
   - `RiskAgent` scores risk (0–100) using 70% AI + 30% rule-based blending
   - `DecisionAgent` makes safety decisions — hard guardrails UNION LLM recommendations
   - `DyatlovAgent` generates adversarial pushback (historically accurate dialogue)
   - `EvacuationAgent` plans logistics when evacuation is ordered
   - `CommsAgent` drafts emergency notifications + radiation plume modeling

3. **Dual timeline**: The dashboard shows what *actually happened* alongside what the AI *would have done* — highlighting divergence points where AI intervention could have prevented the disaster.

---

## Azure / Microsoft Integration

The architecture maps directly to Azure services for production deployment:

| Component | Current (Prototype) | Azure (Production) |
|-----------|-------------------|-------------------|
| Event stream | In-memory bus | Azure Event Hubs |
| State store | JSON files | Azure Cosmos DB |
| LLM reasoning | OpenAI API | Azure OpenAI Service |
| Agent framework | Custom Python | Semantic Kernel / AI Foundry |
| Dashboard | FastAPI + static | Blazor / React on App Service |
| Routing | In-memory graph | Azure Maps |
| Auth | None (demo) | Azure Entra ID |
| Secrets | `.env` file | Azure Key Vault |
| Monitoring | Console logs | Azure Monitor + Log Analytics |

To switch to Azure OpenAI, set these in `.env`:

```env
USE_AZURE=true
OPENAI_BASE_URL=https://your-resource.openai.azure.com/
OPENAI_API_KEY=your-azure-key
OPENAI_MODEL=your-deployment-name
AZURE_API_VERSION=2024-12-01-preview
```

See [infra/README.md](infra/README.md) for the full Azure deployment guide.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/security-model.md](docs/security-model.md) | RBAC, audit trails, network isolation, Key Vault integration |
| [docs/responsible-ai.md](docs/responsible-ai.md) | Guardrail design, AI transparency, override governance |
| [docs/operator-ux.md](docs/operator-ux.md) | Operator experience design, alert fatigue prevention |
| [docs/reusability.md](docs/reusability.md) | How to adapt this for other industries (grid, water, telecom) |
| [infra/README.md](infra/README.md) | Azure infrastructure and deployment reference |

---

## Real-World Applicability

This prototype directly maps to production systems already being deployed:

- **MISO + Microsoft** (Jan 2026): Azure AI Foundry platform for real-time grid operations across 15 US states
- **Capgemini CRoF**: Control Room of the Future framework presented at CIGRE 2025
- **NREL eGridGPT**: GenAI system for live SCADA data analysis on the US grid
- **ACWA Power + Azure**: Predictive maintenance and safety monitoring in production

The architecture is industry-standard compliant (NERC TPL-001, CIP-014, IEC 61850, IEEE C37.118).

---

## License

MIT — use freely for research, education, and commercial applications.

---

## Author:WattAgents

**Shikhar Amar** — [GitHub](https://github.com/amarshikhar)
