What It Is
A multi-agent AI crisis response simulation that replays the Chernobyl disaster (April 25-26, 1986) and shows how autonomous AI agents with safety guardrails could have detected and prevented the explosion. It's a functional prototype of the Control Room of the Future (CRoF) architecture — the same pattern MISO + Microsoft deployed in Jan 2026 for real US power grid ops.

Stack: Python 3.10+, FastAPI, WebSocket, Vanilla JS, Plotly.js, Rich TUI

The 6-Agent Pipeline
Agent	LLM?	Role
SensorAgent	No	Monitors 6 reactor dimensions (power, rods, coolant, steam, temp, radiation) against RBMK-1000 limits
RiskAgent	Yes	Scores risk 0-100 using 70% AI + 30% rule-based blend; detects compound threats
DecisionAgent	Yes	Hard guardrail pattern: rules → LLM reasoning → merge (rules are non-negotiable)
DyatlovAgent	Yes	Adversarial agent — historically-accurate pushback across 5 escalation phases
EvacuationAgent	No	Plans 3 routes for 49,000 Pripyat residents using 1,200 buses
CommsAgent	No	Emergency broadcasts + Gaussian plume radiation modeling
The Guardrail Pattern (Key Innovation)

Step 1: hard_actions = _rule_based_actions()   # Safety floor — ALWAYS runs
Step 2: llm_actions  = _llm_decide()           # AI reasoning
Step 3: final = hard_actions ∪ llm_actions     # Merge — no duplicates
Invariant: LLM can ADD safety actions but NEVER REMOVE them.

Auto-SCRAM: risk >= 85 → AZ-5 EMERGENCY SHUTDOWN
Auto-Evacuate: radiation >= 100 mrem/h → IMMEDIATE EVACUATION
Dyatlov can delay LLM decisions (2-3 ticks) but never override rule-based ones
Dual Timeline Engine
Runs two parallel realities simultaneously:

Historical: What actually happened (from INSAG-7 records) — 20 reconstructed events
Intervened: What the AI would have done — branches off when AI triggers SCRAM/ABORT
Physics models: SCRAM decay (power halves in 2.5s, rods insert over 18s), test abort (5 MW/min ramp-down), evacuation logistics (2 bus trips, 30-min round trips).

Dyatlov Adversarial Agent
Models Deputy Chief Engineer Dyatlov's actual behavior in 5 phases:

Phase	Behavior	Pressure
0: Calm	Cooperative	10
1: Dismissive	"Just instrument noise"	40
2: Authoritarian	Threatens careers	65
3: Desperate	"Two more minutes!"	85
4: Denial	Refuses explosion reality	30
Quotes sourced from INSAG-7 depositions. Ambient + adversarial quote systems with 6-second minimum display.

Risk Scoring (70/30 Blend)

rule_score = Σ(dimension × weight) × compound_multiplier + eccs_penalty
final = 0.7 × llm_score + 0.3 × rule_score
Weights: power (30%) > rods (25%) > coolant (15%) > steam (15%) > temp (10%) > radiation (5%)

Surge detection: power > 500 AND rods < 15 → instant score 100 (catches the actual explosion scenario).

LLM Cost Optimization
LLM is only called when:

Event has tags (real timeline event, not interpolation)
Event has a description
Risk crossed a threshold boundary (30, 60, 85)
Result: ~5% of ticks trigger LLM, ~95% pure rule-based. ~20x cost reduction.

Graceful degradation: every LLM call returns None on failure → agents fall back to rules. Works perfectly without API keys.

Web Dashboard
Backend: FastAPI + WebSocket at 15 FPS broadcasting, batched ticks at high speeds
Frontend: 6 live Plotly.js charts (WebGL scattergl), three-tier throttling (charts 10 FPS, DOM 5 FPS, quotes 2 FPS)
Controls: Play/Pause/Reset, speed slider (1-2500x), intervention toggle, timeline scrubber
Layout: 2x3 chart grid + right panel (risk gauge, pipeline viz, Dyatlov override, agent log, transcript)
REST API: POST /api/control (play, pause, reset, step, set_speed, toggle_intervention, seek)

Azure Deployment Blueprint
Service	Purpose
Azure OpenAI (gpt-4o-mini)	Agent LLM calls
Cosmos DB	Agent state + audit trail
Event Hubs	Telemetry stream
AI Search	IAEA knowledge base
Key Vault	Secrets
AKS Cluster	3 nodes prod, 1 node staging
Container Registry	Docker images
Application Gateway + WAF v2	Ingress + security
CI/CD: GitHub Actions → smoke test → Docker build to ACR → kubectl rollout staging → manual approval → prod.

Key Hackathon Talking Points
Safety by design — rule-based guardrails that LLM cannot override
Production pattern — same CRoF architecture MISO/Microsoft use for real grid ops
Dual timeline — see what happened vs. what AI would have prevented
Adversarial testing — Dyatlov agent stress-tests the AI's safety decisions
Graceful degradation — works without API keys (pure rule-based fallback)
Cost efficient — 20x reduction via decision-point-only LLM calls
Historical accuracy — reconstructed from INSAG-7, IAEA, WNA documents
Regulatory compliance — maps to NERC TPL-001, CIP-014, IEC 61850
Known Bug (Terminal Mode Only)
main.py:89 — missing await on orchestrator.process_tick(state). LLM calls silently fail in terminal mode (agents fall back to rules). Does not affect web mode — web.py correctly awaits.

Here's the complete subsystem-by-subsystem deep dive:

PRIPYAT-1986: All 12 Subsystems — Deep Dive
SUBSYSTEM 1: Configuration Layer
File: config.py

The single source of truth. Everything is parameterized via env vars, making it Azure-portable without code changes.

6 config blocks:

LLM_CONFIG: API key, base URL, model, Azure toggle (USE_AZURE=true), temperatures (0.2 for decisions, 0.3 for risk), timeout 5s, decision_points_only: True (cost optimization)
SIMULATION: speed multiplier (60x default), start time (1986-04-25T23:00), explosion time (01:23:40), tick interval 1s. Web UI starts earlier at 18:00 for full context
THRESHOLDS: RBMK-1000 safety limits — power (nominal 3200, danger_low 200, critical_low 30), rods (minimum_safe 30, critical_low 15), coolant, steam, temp, radiation bands
RISK_CONFIG: escalation at 85, warning at 60, weighted scoring (power 30% > rods 25% > coolant 15% > steam 15% > temp 10% > radiation 5%)
EVACUATION: 49,000 population, 1,200 buses, 45-seat capacity, 3 routes with distance/capacity factors
DYATLOV_CONFIG: 5 phase transitions with timestamps + base pressures (10→40→65→85→30), max delay 3 ticks, temp 0.7
SECURITY: Azure Entra ID RBAC (Operator/Supervisor/Admin/Auditor), Key Vault, alert rules for latency/failure/risk/fallback
SUBSYSTEM 2: Timeline Data (The Historical Record)
File: timeline_data.py

ReactorState dataclass — 10 fields:


timestamp, power_mw, control_rods_inserted, coolant_flow_m3h,
steam_pressure_mpa, temperature_c, radiation_mrem_h, eccs_active,
event_description, actual_human_decision, tags[]
20 reconstructed events across 5 phases from INSAG-7/IAEA/WNA:

Phase 1 — Test Prep (6 events, Apr 25 13:00–23:10): Power at 1600 MW, 140 rods, stable. Key: 9-hour delay from Kiev grid, shift changes, xenon buildup begins
Phase 2 — Power Drop (2 events, Apr 26 00:05–00:28): Power crashes to 30 MW, ECCS disabled. Tags: critical, xenon_poisoning, eccs_disabled, decision_point
Phase 3 — Dangerous Recovery (3 events, 00:32–01:00): Rods withdrawn to 30, power at 200 MW. Tags: rods_withdrawn, unstable, operator_objection
Phase 4 — Test & Catastrophe (6 events, 01:03–01:23:40): Rods drop to 8, power surges to 30,000 MW, explosion
Phase 5 — Aftermath (3 events, 01:30–14:00): Firefighters, denial, 36-hour evacuation delay
AI_COUNTERFACTUAL_DECISIONS — 5 entries mapping timestamps to what AI should have done, with reasoning and lives_saved estimates.

SUBSYSTEM 3: Event Simulator (Time Machine)
File: simulator.py

Converts the 20 discrete events into a smooth continuous stream via linear interpolation.

Interpolation logic (simulator.py:44-101):

For each pair of adjacent events, calculates gap_seconds / speed / tick_interval
Generates that many intermediate ReactorState objects with linearly interpolated numeric values
Only the first step in each gap carries the event_description, actual_human_decision, and tags — the rest are blank interpolated ticks
Boolean fields (like eccs_active) hold the current event's value (no interpolation)
Playback modes:

run() — async streaming with asyncio.sleep between ticks, supports pause/resume
step() — advance exactly one tick (for single-step debugging)
seek(index) — jump to any position
set_speed() — dynamic speed changes
SUBSYSTEM 4: LLM Client (AI Brain)
File: llm_client.py

Dual SDK support: AsyncOpenAI or AsyncAzureOpenAI — selected by USE_AZURE env var. Same interface, swap-in deployment.

Two call modes:

call_structured(system_prompt, user_prompt, schema) → Optional[dict] — uses OpenAI JSON Schema mode with strict: true
call_text(system_prompt, user_prompt) → Optional[str] — free-text for CommsAgent
3 JSON Schemas (all with additionalProperties: false):

RISK_ASSESSMENT_SCHEMA: risk_score (0-100), trend (escalating/stable/de-escalating), primary_concern, compound_risks[], recommendation (continue/warn/escalate), reasoning
DECISION_SCHEMA: action (CONTINUE_MONITORING/WARN_ECCS/ABORT_TEST/SCRAM/EVACUATE), urgency, reasoning, safety_violations[], override_operator (bool), additional_actions[]
DYATLOV_OVERRIDE_SCHEMA: dialogue, override_action (BLOCK_SCRAM/BLOCK_ABORT/DEMAND_POWER_INCREASE/DISMISS_WARNING/SUPPRESS_EVACUATION/RELUCTANT_COMPLIANCE), intensity (1-10), reasoning
3 System Prompts — domain-expert-level instructions:

Risk prompt: Teaches RBMK-1000 physics (positive void coefficient, xenon-135, compound risks)
Decision prompt: Includes "NORMAL OPERATIONS" section to prevent false-positive SCAMs at 1600 MW / 140 rods
Dyatlov prompt: Full personality reconstruction from INSAG-7 depositions — authoritarian, dismissive, desperate
Observability: call_count, total_latency_ms, avg_latency_ms tracked per session.

Graceful degradation: Every call is wrapped in try/except → return None. Agents always fall back to rules.

SUBSYSTEM 5: Agent Pipeline (The 6 Agents)
File: agents.py (1,258 lines — the biggest file)

Agent 1: SensorAgent (Rule-based)
Checks 6 dimensions against THRESHOLDS
Produces AgentMessage objects with AlertLevel (NORMAL/WARNING/CRITICAL/EMERGENCY)
Multi-tier alerts: power (4 tiers), rods (2 tiers), ECCS (on/off), coolant (2 tiers), steam, radiation (3 tiers)
Feeds directly into RiskAgent
Agent 2: RiskAgent (AI-powered, 70/30 blend)
Decision point filter (agents.py:207-221):

LLM called only when: event has tags, event has description, or risk crossed boundary (30/60/85)
~5% of ticks trigger LLM calls
Rule-based score (agents.py:223-302):


raw = Σ(dimension_score × weight) + eccs_penalty(15)
compound_mult = 1.0 + (violations_over_60 × 0.15)
rule_score = min(100, raw × compound_mult)
Surge detector: power > 500 AND rods < 15 → instant 100

AI blending: final = 0.7 × llm_score + 0.3 × rule_score

Rate-of-change context: Feeds the LLM delta information (power change, rod change, coolant change between ticks) so it can detect trends, not just snapshots.

Agent 3: DecisionAgent (AI-powered, guardrailed)
The guardrail-union pattern (agents.py:605-641):


Step 1: hard_actions = _rule_based_actions()    # ALWAYS runs
Step 2: llm_actions = _llm_decide() if decision_point
Step 3: merged = hard_actions ∪ llm_actions     # Union, no dupes
Step 4: rule_based_extras() if nothing triggered # ECCS warning, abort
Hard guardrails (non-negotiable):

risk >= 85 AND not scrammed → AZ-5 SCRAM
radiation >= 100 mrem/h AND not evacuated → EVACUATE
Anti-hallucination guards:

LLM cannot trigger SCRAM if risk < 40
LLM cannot trigger ABORT if risk < 30
Deduplication: won't repeat an action already taken
LLM prompt includes: full reactor state, risk score, sensor alerts (up to 6), previous 3 decisions, SCRAM/evacuation status. The system prompt has a "NORMAL OPERATIONS" section to prevent false positives.

Agent 4: EvacuationAgent (Rule-based)
Triggered once when evacuation_ordered flag is set
Calculates: trips needed = ceil(49000 / (1200 × 45)) = 1 trip
Allocates across 3 routes by capacity factor
Returns a single AgentAction with the full plan
Agent 5: CommsAgent (Rule-based + Gaussian plume)
Triggers on EMERGENCY-level decisions
First alert: Plant + Moscow — lists recipients (Bryukhanov, Energy Ministry, Nuclear Safety Committee, Military HQ) + contrast with what actually happened
International alert: When radiation ≥ 100 mrem/h — runs Gaussian plume dispersion model (Pasquill-Gifford stability class D, 5 m/s NW wind) at 5/10/30/100/300 km — alerts IAEA, WHO, Belarus, Poland, Sweden + contrast ("Soviet Union didn't acknowledge for 2 days, Sweden detected on April 28")
Agent 6: DyatlovAgent (AI-powered adversarial)
5 escalation phases with timestamp-based transitions:

Phase 0 (Calm, 10 ambient quotes) → Phase 1 (Dismissive, 6 quotes) → Phase 2 (Authoritarian, 5 quotes) → Phase 3 (Desperate, 4 quotes) → Phase 4 (Denial, 4 quotes)
Quote bank — two systems:

Ambient quotes: Background dialogue when no decisions to contest. Rotated deterministically based on simulation seconds (every 20s for calm, every 15s for tension). Each quote emits only once per phase (no cycling).
Adversarial quotes: Contextual pushback tagged with action types (BLOCK_SCRAM, BLOCK_ABORT, DISMISS_WARNING, DEMAND_POWER_INCREASE, SUPPRESS_EVACUATION)
Override pressure formula:


pressure = base_phase + urgency_bonus(0-15, ramps in last 2h) + severity_bonus(SCRAM=20, ABORT=15, EVAC=10)
Target selection priority: SCRAM > ABORT > EVACUATE > ECCS WARNING

SUBSYSTEM 6: Orchestrator (Message Bus + Pipeline Coordinator)
File: orchestrator.py

MessageBus: In-memory pub/sub — messages[] (per-tick, cleared) + actions[] (accumulated history). Agents publish AgentMessage and AgentAction objects.

Pipeline per tick (orchestrator.py:158-277):


Step 0: Re-inject delayed decisions (from Dyatlov overrides)
Step 1: SensorAgent.process(state) → sensor_alerts
Step 2: RiskAgent.process(state, alerts) → risk_score, risk_msg
Step 3: DecisionAgent.process(state, risk, alerts) → decisions
Step 3.5: DyatlovAgent.process(state, risk, decisions, scrammed)
Step 3.6: _resolve_overrides(decisions, dyatlov_response)
Step 4: EvacuationAgent.process(evacuation_ordered, state)
Step 5: CommsAgent.process(state, decisions)
→ Build tick summary dict
Override resolution (orchestrator.py:94-148):

source: "rule" decisions → NEVER overridable → override_succeeded = False, total_override_failures++
source: "llm" + pressure > 50 + non-SCRAM/non-EVAC + phase ≤ 2 → Delayed 2-3 ticks → stored in _delayed_decisions[] as (reinject_at_tick, action)
Delayed decisions are re-injected at the start of the tick when their timer expires
State tracking: reactor_scrammed, evacuation_ordered, scram_timestamp, evacuation_timestamp, override_history[]

Final report: Actual vs AI comparison — explosion time, evacuation delay, deaths, Dyatlov confrontation analysis (peak pressure, key confrontations), LLM stats.

SUBSYSTEM 7: Dual Timeline Engine
File: timeline_engine.py

The glue between the Simulator, Orchestrator, and Physics model.

Two parallel realities:

Historical: Always plays from the interpolated timeline data
Intervened: Mirrors historical until a SCRAM or ABORT decision → then branches using physics model
Divergence trigger (timeline_engine.py:135-168):

Scans each tick's decisions for "SCRAM"/"SHUTDOWN" or "ABORT TEST"
Records divergence_state (ReactorState at branch point), divergence_time, divergence_type
From that point forward: compute_scram_decay(divergence_state, elapsed_s) or compute_test_abort(divergence_state, elapsed_s) runs every tick
Combined payload: Every tick emits {historical: {6 params}, intervened: {6 params + diverged flag}, risk_score, decisions, dyatlov, evacuation_progress, counterfactual}

SUBSYSTEM 8: Physics Engine
File: physics.py

Three deterministic models:

compute_scram_decay(state, elapsed_s)
Power: Exponential decay P₀ × 0.5^(t/2.5s) with decay heat floor 7% × e^(-t/3600)
Rods: Linear insertion over 18s toward all 211
Temperature: Newton's cooling law toward 180°C coolant inlet
Coolant flow: Recovery to 8000 m³/h over 60s
Steam pressure: Drops proportionally to power ratio
Radiation: 2-hour exponential decay (no core breach)
ECCS: Re-enabled automatically
compute_test_abort(state, elapsed_s)
Power: Linear ramp-down at 5 MW/min
Rods: Gradual insertion at ~3 rods/min toward 140
Temperature: Gradual cooling proportional to power ratio
Coolant: Slow recovery at 50 m³/h·min
compute_evacuation_progress(elapsed_s)
30-minute mobilization delay
30-minute round trips per bus
trips_per_bus × buses × capacity = people evacuated
Route allocation by capacity factor
Returns: {people_evacuated, buses_in_transit, percent_complete, phase, estimated_hours_remaining, routes[]}
SUBSYSTEM 9: Web Server (FastAPI + WebSocket)
File: web.py

Architecture: FastAPI app + single WebSocket endpoint + REST control API.

Simulation loop (web.py:81-103):

Target 15 FPS broadcasting
At high speeds, batches multiple ticks per frame (ticks_per_frame = max(1, effective_rate/15))
Only broadcasts the last tick of each batch (reduces network traffic)
On completion: broadcasts simulation_complete with full final report
REST API (POST /api/control):

Action	Behavior
play	Starts async simulation loop
pause	Cancels running task
reset	Stop + engine.reset()
step	Process one tick (only when paused)
set_speed	Clamp [1, 2500]
toggle_intervention	Flip engine.intervention_enabled
seek	Reset + replay to target tick silently
WebSocket (GET /ws):

On connect: sends state_update with current state + first timestamp
One-way server→client broadcasting
Auto-cleanup of disconnected clients via asyncio.gather(return_exceptions=True)
SUBSYSTEM 10: Frontend Dashboard
Files: index.html, app.js, style.css

Layout (CSS Grid)

┌─────────────────────────────────────────────────────┐
│ HEADER (title, sim time, badges, progress bar)      │
├─────────────────────────────────────────────────────┤
│ CONTROLS (play/pause/reset, speed slider, toggle)   │
├──────────────────────────────┬──────────────────────┤
│ CHARTS (2×3 grid)            │ RIGHT PANEL (320px)  │
│ Power    │ Steam Pressure    │ Risk Gauge (48px num) │
│ Rods     │ Temperature       │ Pipeline viz (S→R→D→E→C)│
│ Coolant  │ Radiation         │ Dyatlov chat log      │
│                              │ Agent action log       │
├──────────────────────────────┴──────────────────────┤
│ SCRUBBER (timeline slider)                          │
├──────────────┬──────────────┬───────────────────────┤
│ History      │ Evacuation   │ Counterfactual        │
│ (actual 1986)│ Status       │ Comparison            │
└──────────────┴──────────────┴───────────────────────┘
Chart System (app.js:486-621)
Plotly.js with scattergl (WebGL-accelerated, not SVG)
6 charts, each with 2 traces: Historical (red, solid) + AI Timeline (cyan, dotted)
Incremental rendering: Points buffered in pendingPoints, flushed via Plotly.extendTraces at max 5 FPS (200ms throttle)
requestAnimationFrame batches all 6 chart updates into single paint
MAX_POINTS = 2000 rolling buffer with auto-shift
Dyatlov Panel
Chat log with column-reverse flex (newest at top visually)
Pressure bar fills red, phases color-coded (muted→yellow→orange→red→dim red)
Quotes colored by pressure: >80 red, >50 orange
Duplicate consecutive quotes filtered
Max 30 entries in chat log
Design System (style.css)
Colors: Dark nuclear theme — #0a0e14 primary bg, cyan accent (#00d4ff), red alerts (#e74c3c), yellow warnings, green safe
Font: JetBrains Mono / Fira Code / Consolas
Animations: pulse (1s infinite for EMERGENCY), fadeIn (0.3s for log entries), chatFadeIn (0.3s for Dyatlov quotes)
Responsive: Single breakpoint at 1200px — right panel goes horizontal, bottom area takes full width
SUBSYSTEM 11: Terminal Dashboard (Rich TUI)
File: dashboard.py

Alternative UI using Python's Rich library for terminal display at 2 FPS.

Layout: Header → split body (left: reactor telemetry + actual history | right: risk panel + AI decisions) → Dyatlov panel → Thought Trace footer

Key panels:

Reactor panel: Color-coded readings — green/yellow/red for each metric, ECCS status
Risk panel: ASCII bar chart █░ (20 blocks), source badge [AI] or [RULE], AI reasoning snippet (120 chars)
Dyatlov panel: Quote, pressure bar, phase name, override result (BLOCKED/DELAYED), stats
Thought Trace: Table of last 5 agent decisions + Dyatlov entry — shows Source (AI/RULE), Agent, Action, Reasoning
Final Report: Rich table comparing Actual vs AI timeline — SCRAM timing, evacuation, deaths, Dyatlov analysis
SUBSYSTEM 12: Azure Deployment & Infrastructure
Files: docs/azure-hackathon-full-integration.md, docs/security-model.md, docs/responsible-ai.md

Deployed Stack
Azure Service	How Used	Cost
Azure OpenAI (gpt-4o, Standard S0)	Powers Risk/Decision/Dyatlov agents	~$0.10/demo run
AI Foundry	3 playground agents + evaluation datasets	$0 (included)
Container Apps (Consumption)	Hosts FastAPI + dashboard, scale-to-zero	~$0/day idle
Container Registry (Basic)	Docker images	~$0.17/day
Cosmos DB (Serverless)	Immutable audit trail (decisions container) + INSAG-7 knowledge base (insag7 container)	~$0.01/run
AI Search (Free tier)	Keyword index over INSAG-7 safety protocols	$0
Application Insights	LLM call tracing, latency monitoring	~$0
Deployment Pipeline

local smoke-test → az acr build → Container Registry → az containerapp create/update
Scale to 0 when not demoing, scale to 1 for live demo.

Security Model (Production Blueprint)
Identity: Azure Entra ID, 4 RBAC roles (Operator/Supervisor/Admin/Auditor)
Secrets: Key Vault, 90-day auto-rotation, Managed Identities
Network: VNET + Private Endpoints, Application Gateway + WAF v2, no public PaaS endpoints
Audit: Immutable Cosmos DB records, partition key {tick}_{agent}_{timestamp}, 1-5 year retention
Monitoring: Alert rules for LLM latency > 5s, pipeline failure, risk > 85 sustained, high fallback rate, unauthorized access
Responsible AI Framework
Decision Ladder: Advisory (0-30) → Informational (30-60) → Confirmation Required (60-85) → Auto-Execute (85+)
Guardrail-Union Pattern: LLM adds but never removes safety actions
Anti-hallucination: LLM can't SCRAM below risk 40
Failure modes: All degrade toward deterministic safety (safer without AI than with compromised AI)
Compliance: NRC 10 CFR 50, NERC CIP, IAEA Safety Standards
File Dependency Graph

config.py ─────────────┐
timeline_data.py ──┐   │
                   │   │
llm_client.py ◄────┼───┘
    │              │
    ▼              ▼
agents.py ◄── config + timeline_data + llm_client
    │
    ▼
orchestrator.py ◄── agents + llm_client + config + timeline_data
    │
    ▼
simulator.py ◄── timeline_data + config
physics.py ◄── timeline_data + config
    │              │
    ▼              ▼
timeline_engine.py ◄── simulator + orchestrator + physics
    │
    ├──► web.py (FastAPI + WebSocket) ──► static/{index.html, app.js, style.css}
    └──► main.py ──► dashboard.py (Rich TUI)
That's every file, every function, every data flow.