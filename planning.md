<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# i want to build an ai agent that can save us in model from the chernobyl disaster. come up with a detailed plan. based on real time relisient system project from capgemini and microsoft agaentic ai hackathon 2026.

This is an excellent hackathon concept — a **real-time nuclear crisis response multi-agent simulation** based on the Chernobyl disaster, perfectly aligned with the Capgemini × Microsoft Agentic AI Hackathon (May 26–27, 2026). Here is a full, detailed plan.

***

## Project Title: **PRIPYAT-1986**

### *An Agentic AI Crisis Response Simulation to Rewrite History*

The core idea: feed the real Chernobyl timeline (April 25–26, 1986) as a **live data stream** into a multi-agent system and let AI make decisions in real-time — demonstrating what autonomous agents could have done differently to save lives. This directly targets the **Best Multi-Agent System** and **Best Enterprise Solution** categories of the Microsoft Agentic AI Hackathon 2026.[^1]

***

## Why This Wins the Hackathon

The Microsoft AI Dev Days Hackathon 2026 evaluates on **real-world impact, multi-agent sophistication, A2A protocols, and MCP server usage**. Capgemini's Agentic Industry Studio with Microsoft focuses on turning AI into measurable enterprise outcomes. A nuclear crisis response agent scores on all axes:[^2][^1]

- **Best Multi-Agent System**: Multi-agent orchestration with A2A handoffs
- **Best Enterprise Solution**: Directly applicable to industrial safety, nuclear, and disaster response sectors
- **Best Azure Integration**: Foundry + Event Hubs + Cosmos DB + Azure Maps

***

## System Architecture

The system is built as a **multi-agent pipeline** where each agent has a specialized role, communicating via **MCP (Model Context Protocol)** servers. Think of it as a virtual Chernobyl control room staffed by autonomous AI agents.

```
┌──────────────────────────────────────────────────────────────────┐
│         PRIPYAT-1986: AGENT ORCHESTRATION LAYER                  │
│         (Azure AI Foundry + Microsoft Agent Framework)           │
│                                                                  │
│   [Sensor Agent] ──▶ [Risk Agent] ──▶ [Decision Orchestrator]   │
│         │                                    │                   │
│   [Historical    [Radiation               [Evacuation Agent]     │
│    Replay Engine] Dispersion Agent]            │                 │
│                                        [Comms/Alert Agent]       │
└──────────────────────────────────────────────────────────────────┘
```


***

## The 6 Core Agents

Each agent is implemented using **Semantic Kernel** or **AutoGen** inside Azure AI Foundry, communicating over A2A (Agent-to-Agent) protocols.[^1]

### 1. 🟡 Historical Replay Engine (Data Spine)

This is not an agent but the **real-time simulation backbone**. It replays the exact Chernobyl timeline — starting at **01:00 AM, April 26, 1986** — streaming timestamped events into **Azure Event Hubs** as if they were live sensor telemetry.[^3]

- Data includes: reactor power levels (dropped from 1600 MW → 30 MW at 00:28), control rod positions, coolant flow, steam pressure
- Based on declassified INSAG-7 documents and the World Nuclear Association sequence of events[^3]
- Simulation speed: configurable (real-time = 1:1, accelerated = 60x)


### 2. 🔴 Sensor Monitoring Agent

Continuously ingests the streamed reactor telemetry from Event Hubs. Its job is anomaly detection — identifying when readings deviate from safe thresholds.

- **Tools via MCP**: Azure Event Hubs reader, threshold config store (Azure Cosmos DB)
- **Trigger**: Fires alert to Risk Agent when power drops below 200 MW (the actual danger threshold ignored by Dyatlov)
- **ReAct Loop**: Observe → Threshold Check → Annotate → Escalate


### 3. 🟠 Risk Assessment Agent

Receives alerts from the Sensor Agent and performs probabilistic hazard scoring using **Azure AI Search** over a knowledge base of nuclear safety protocols (IAEA standards, RBMK reactor manuals).

- Retrieves relevant safety docs using **Agentic Retrieval** from Azure AI Search[^4]
- Outputs a **Risk Score (0–100)** with reasoning chain exposed via Thought Trace
- At risk score > 85 → mandatory escalation to Decision Orchestrator, overriding human override (exactly what Dyatlov prevented in real life)


### 4. 🔵 Decision Orchestrator Agent (The Brain)

The central agent, built on **Microsoft Agent Framework** with full **Chain-of-Thought reasoning**. This is where history gets rewritten.[^1]


| Real Decision (1986) | AI Agent Decision |
| :-- | :-- |
| Dyatlov overrides abort at 30 MW | Agent presses AZ-5 emergency shutdown at 01:19 AM |
| ECCS disabled for test | Agent flags ECCS removal as unacceptable risk |
| No evacuation until 36 hours later | Agent triggers Pripyat evacuation at 03:00 AM |
| Radiation levels lied about | Agent broadcasts truthful radiation data to authorities |

- Uses **dynamic replanning** — every new sensor reading causes re-evaluation of the action plan
- Maintains full **state in Azure Cosmos DB** for auditability[^5]


### 5. 🟢 Evacuation Planner Agent

Once evacuation is triggered, this agent optimizes the movement of Pripyat's **49,000 residents** using graph-based routing.

- **Tools**: Azure Maps API (road network), NetworkX for graph-based pathfinding (right in your wheelhouse, Saksham!)
- Calculates evacuation routes avoiding radiation hotspots (fed by the Dispersion Agent)
- Outputs: number of buses needed, priority zones, estimated completion time
- Compares AI-optimized outcome vs actual 1986 36-hour delay


### 6. 🟣 Radiation Dispersion + Comms Agent

A dual-purpose agent:

- **Dispersion Modeling**: Uses historical wind data (April 26, 1986, NW wind) to simulate radiation spread across Ukraine, Belarus, and Europe using a simplified Gaussian plume model
- **Communications**: Auto-drafts alerts for plant management, Moscow authorities, WHO, and neighboring countries — showing the contrast with the actual Soviet cover-up
- Generates outputs via Azure AI Foundry connected to an Azure Logic Apps notification pipeline

***

## Tech Stack

| Component | Technology |
| :-- | :-- |
| Agent orchestration | Azure AI Foundry + Microsoft Agent Framework [^1] |
| Agent reasoning | Semantic Kernel / AutoGen (Python) |
| Tool integration | MCP (Model Context Protocol) servers |
| Real-time data stream | Azure Event Hubs |
| Agent state \& memory | Azure Cosmos DB [^5] |
| Knowledge retrieval | Azure AI Search (Agentic Retrieval) |
| Evacuation routing | Azure Maps + NetworkX / GraphFrames |
| UI / Dashboard | Blazor or React with real-time streaming [^6] |
| Deployment | Azure Kubernetes Service (AKS) |


***

## UI: The "Alternate History" Dashboard

Build a live dashboard showing a **split screen**:

- **Left panel**: What actually happened (red timeline — deaths, delayed evacuation)
- **Right panel**: What the AI agent decided (green timeline — early shutdown, 3AM evacuation)

A "Thought Trace" panel (from Agentic AI hackathon judging criteria ) shows every agent's real-time reasoning — exactly what Capgemini and Microsoft judges want to see.[^7]

***

## 4-Day Hackathon Sprint Plan

1. **Day 0 (Pre-hack)**: Set up Azure AI Foundry project, Cosmos DB, Event Hubs. Load INSAG-7 data into AI Search knowledge base. Define MCP server schemas for all 5 tools.
2. **Day 1**: Build the Historical Replay Engine + Sensor Monitoring Agent. Get the data pipeline flowing end-to-end.
3. **Day 2**: Build Risk Assessment Agent + Decision Orchestrator with ReAct loop. Test against the 01:23 AM explosion window.
4. **Day 3**: Build Evacuation Planner + Dispersion Agent. Wire up the full A2A communication chain.
5. **Day 4 (Demo)**: Polish the dashboard, record a 3-minute live demo showing the split-screen alternate history. Write the Thought Trace walkthrough for judges.

***

## What Makes This Stand Out

The strongest projects in previous Capgemini agentic hackathons used agentic AI to address **real-world business/industrial needs** with measurable outcomes. PRIPYAT-1986 is immediately compelling because it:[^8][^9]

- Uses **real historical data** as its simulation backbone — making the demo viscerally engaging
- Demonstrates **counterfactual reasoning** — agents that can prove they would have saved 30+ lives and prevented a \$700 billion economic catastrophe
- Is directly transferable to **enterprise nuclear safety, oil \& gas, and industrial IoT** — which is exactly the Capgemini client use case framing that wins hackathons[^2]

The Microsoft AI Dev Days Hackathon 2026 specifically prizes solutions showing "real-world impact and innovative use of Microsoft AI platform"  — and nothing says real-world impact louder than rewriting the worst nuclear disaster in history.[^1]
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29]</span>

<div align="center">⁂</div>

[^1]: https://developer.microsoft.com/en-us/reactor/events/26647/

[^2]: https://www.capgemini.com/solutions/agentic-industry-studio-with-microsoft/

[^3]: https://world-nuclear.org/information-library/appendices/chernobyl-accident-appendix-1-sequence-of-events

[^4]: https://www.linkedin.com/posts/ragnarpitla_microsoftbuild-azureai-foundry-activity-7330604248692314112-qZIk

[^5]: https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/agent-service-disaster-recovery

[^6]: https://www.linkedin.com/posts/justinyoo_build-a-real-world-example-with-microsoft-activity-7436991275209424896-FS4v

[^7]: https://unstop.com/hackathons/agentic-ai-hackathon-maharaja-agrasen-institute-of-technology-mait-new-delhi-1649729/amp

[^8]: https://www.capgemini.com/insights/expert-perspectives/agentic-ai-in-action-lessons-from-the-capgemini-and-google-cloud-hackathon/

[^9]: https://agentichackathon.onova.io

[^10]: https://www.capgemini.com/news/events/microsoft-ignite/

[^11]: https://microsoft.github.io/AI_Agents_Hackathon/

[^12]: https://skilling-hub.com/en-US/listing/t::fy26-aah-05

[^13]: https://www.ibm.com/think/news/ibm-microsoft-hackathon-agentic-ai

[^14]: https://ruyaai-hackathon-2026.devpost.com

[^15]: https://developer.microsoft.com/en-us/reactor/series/s-1576/

[^16]: https://agentic-hackathon-atlanta.devpost.com

[^17]: https://vslive.com/events/microsofthq-2026/hackathon.aspx

[^18]: https://techcommunity.microsoft.com/blog/skills-hub-blog/you’re-invited-microsoft-ai-power-days-agent-a-thon-february-19-2026/4470719

[^19]: https://luma.com/li841jkv

[^20]: https://ignite.microsoft.com/en-US/sessions/a1f684c2-ba38-42c0-a696-cce34102bf4c

[^21]: https://github.com/microsoft/AI_Agents_Hackathon

[^22]: https://awsagentichackathon.onova.io/overview

[^23]: https://www.youtube.com/watch?v=6rkdflwL5us

[^24]: https://www.capgemini.com/us-en/insights/expert-perspectives/agentic-ai-in-action-lessons-from-the-capgemini-and-google-cloud-hackathon/

[^25]: https://www.youtube.com/watch?v=dMJTxm1Kdj4

[^26]: https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/agent-service-disaster-recovery?view=foundry-classic

[^27]: http://www.chernobylgallery.com/chernobyl-disaster/timeline/

[^28]: https://odsc.ai/east/hackathon/

[^29]: https://www.youtube.com/watch?v=mvNWJnLEMg0

