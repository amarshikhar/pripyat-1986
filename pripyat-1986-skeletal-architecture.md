# PRIPYAT-1986 — Skeletal Architecture Document

> A complete code walkthrough of the Chernobyl Agentic AI Crisis Response Simulation.
> Written as a senior engineer explaining the codebase to a junior developer, file by file.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [File Structure & Dependency Graph](#2-file-structure--dependency-graph)
3. [Execution Modes](#3-execution-modes)
4. [File 1: config.py — Central Configuration](#file-1-configpy)
5. [File 2: timeline_data.py — Historical Foundation](#file-2-timeline_datapy)
6. [File 3: llm_client.py — LLM Interface](#file-3-llm_clientpy)
7. [File 4: simulator.py — Event Replay Engine](#file-4-simulatorpy)
8. [File 5: physics.py — Reactor Physics Model](#file-5-physicspy)
9. [File 6: agents.py — The Six Agents](#file-6-agentspy)
10. [File 7: orchestrator.py — Agent Pipeline Coordinator](#file-7-orchestratorpy)
11. [File 8: timeline_engine.py — Dual Timeline Engine](#file-8-timeline_enginepy)
12. [File 9: dashboard.py — Terminal UI](#file-9-dashboardpy)
13. [File 10: web.py — Web Server](#file-10-webpy)
14. [File 11: static/app.js — Frontend](#file-11-staticappjs)
15. [File 12: static/style.css — Styling](#file-12-staticstylecss)
16. [File 13: static/index.html — HTML Structure](#file-13-staticindexhtml)
17. [File 14: main.py — CLI Entry Point](#file-14-mainpy)
18. [Key Design Patterns](#key-design-patterns)
19. [Known Issues](#known-issues)

---

## 1. Project Overview

PRIPYAT-1986 replays the Chernobyl disaster timeline through a multi-agent AI system. Six agents monitor, assess, and intervene in the crisis — generating an alternate history where AI prevents the explosion.

**Core concept:** "What if a modern AI safety system had been monitoring Reactor #4 on April 26, 1986?"

The system uses:
- **CRoF (Control Room of the Future)** architecture — inspired by real power grid AI systems
- **6 specialized agents** forming a pipeline: Sensor → Risk → Decision → Evacuation → Comms, plus an adversarial Dyatlov agent
- **Dual timeline rendering** — historical (what happened) vs. AI-intervened (what AI prevents)
- **LLM-powered reasoning** with rule-based guardrails as safety floor
- **Adversarial tension** — Dyatlov agent generates historically-authentic pushback against every AI decision

---

## 2. File Structure & Dependency Graph

```
pripyat-1986/
├── config.py              # Central configuration (leaf)
├── timeline_data.py       # Historical data + ReactorState dataclass (leaf)
├── llm_client.py          # LLM interface + schemas (depends: config)
├── simulator.py           # Event replay engine (depends: config, timeline_data)
├── physics.py             # Reactor physics model (depends: config, timeline_data)
├── agents.py              # 6 agent implementations (depends: config, timeline_data, llm_client)
├── orchestrator.py        # Agent pipeline coordinator (depends: config, timeline_data, agents, llm_client)
├── timeline_engine.py     # Dual timeline manager (depends: config, simulator, orchestrator, physics)
├── dashboard.py           # Terminal UI (depends: rich — no internal deps)
├── web.py                 # FastAPI web server (depends: config, timeline_engine)
├── main.py                # CLI entry point (depends: everything)
├── static/
│   ├── index.html         # Web dashboard HTML
│   ├── app.js             # Frontend JavaScript
│   └── style.css          # CSS theme
└── output/                # Generated at runtime
    ├── agent_state.json
    ├── final_report.json
    └── simulation.log
```

### Dependency Graph (→ means "depends on")

```
timeline_data.py   config.py          (leaf modules — no internal deps)
       ↓               ↓
   llm_client.py ← config
       ↓
   simulator.py ← config, timeline_data
   physics.py   ← config, timeline_data
   agents.py    ← config, timeline_data, llm_client
       ↓
   orchestrator.py ← config, timeline_data, agents, llm_client
       ↓
   timeline_engine.py ← config, simulator, orchestrator, physics
       ↓                    ↓
   web.py              dashboard.py (isolated — Rich library only)
       ↓                    ↓
              main.py (imports everything)
```

---

## 3. Execution Modes

```bash
python main.py                    # Terminal UI mode (Rich Live dashboard at 2 FPS)
python main.py --speed 120        # 120x simulation speed
python main.py --no-dashboard     # Headless JSON output
python main.py --smoke-test       # Quick 5-tick validation
python main.py --web              # Web dashboard (FastAPI + WebSocket)
python main.py --web --port 9000  # Custom port
python web.py                     # Direct web server launch
```

---

## File 1: `config.py`

**Role:** Central configuration hub. Every tunable constant lives here.
**Dependencies:** `os`, `dotenv`
**Depended on by:** Every other module

### Module-Level Constants

| Constant | Type | Purpose |
|----------|------|---------|
| `LLM_CONFIG` | `dict` | API keys, model name, timeout, temperature, token limits, `decision_points_only` flag |
| `SIMULATION` | `dict` | Speed multiplier (60x), start/explosion timestamps, tick interval (1.0s) |
| `THRESHOLDS` | `dict` | RBMK-1000 safety limits for 6 dimensions (power, rods, coolant, steam, temp, radiation) |
| `RISK_CONFIG` | `dict` | Escalation threshold (85), warning threshold (60), dimension weights |
| `EVACUATION` | `dict` | Pripyat population (49,000), buses (1,200), capacity (45), 3 evacuation routes |
| `WEB_CONFIG` | `dict` | Host, port, static directory |
| `DYATLOV_CONFIG` | `dict` | 5 phase transitions with timestamps, base pressure per phase, max delay ticks (3) |
| `OUTPUT_DIR` | `str` | Path to `output/` directory |
| `STATE_FILE` | `str` | Path to `agent_state.json` |
| `LOG_FILE` | `str` | Path to `simulation.log` |

### Key Design Decisions

- **Two temperature settings:** `temperature_decision: 0.2` (low for deterministic safety) vs `temperature_risk: 0.3` (slightly higher for nuanced assessment)
- **`decision_points_only: True`** — Only calls LLM at meaningful timeline events, not every interpolated tick. This is the primary cost optimization.
- **Dual start times:** `start_time` (23:00 for terminal mode) vs `sim_start_from` (18:00 for web mode — provides more context)
- **Azure migration annotations** in docstring — every config maps to an Azure equivalent

### Risk Weights

```
power_anomaly:   0.30  (heaviest — power is king in RBMK)
rod_position:    0.25  (control rods are the primary safety mechanism)
coolant_anomaly: 0.15
steam_pressure:  0.15
temperature:     0.10
radiation:       0.05  (low weight — by the time radiation spikes, it's too late)
```

---

## File 2: `timeline_data.py`

**Role:** Foundation data module. Defines the fundamental data type and all historical events.
**Dependencies:** `dataclasses`, `typing` (standard library only)
**Depended on by:** `simulator.py`, `physics.py`, `agents.py`, `orchestrator.py`

### `ReactorState` Dataclass

```python
@dataclass
class ReactorState:
    timestamp: str                    # ISO format: "1986-04-26T01:00:00"
    power_mw: float                   # Thermal power (MW) — rated 3200
    control_rods_inserted: int        # Number of rods in core (of 211 total)
    coolant_flow_m3h: float           # Primary coolant flow (m³/h)
    steam_pressure_mpa: float         # Steam drum pressure (MPa)
    temperature_c: float              # Core outlet temperature (°C)
    radiation_mrem_h: float           # Local radiation level (mrem/h)
    eccs_active: bool                 # Emergency Core Cooling System on/off
    event_description: str            # What happened at this moment
    actual_human_decision: str        # What operators/Dyatlov actually did
    tags: list[str]                   # Classification tags (e.g., ["critical", "decision_point"])
```

This is **the fundamental data unit** of the entire system. Every agent receives `ReactorState`, every chart plots `ReactorState` fields, every physics function returns `ReactorState`.

### `CHERNOBYL_TIMELINE` — 20 Historical Events

Organized in 5 phases:

| Phase | Time Range | Events | Key Moment |
|-------|-----------|--------|------------|
| 1: Test Prep | Apr 25 13:00–23:10 | 6 events | Kiev grid delay, shift changes, 9-hour postponement |
| 2: Power Drop | Apr 26 00:05–00:28 | 2 events | Power plunges to 30 MW (xenon poisoning) |
| 3: Dangerous Recovery | 00:32–01:00 | 3 events | Rods withdrawn to 30 (minimum safe) |
| 4: The Test | 01:03–01:23:40 | 5 events | Power surge → 30,000 MW explosion |
| 5: Aftermath | 01:30–14:00 | 4 events | Firefighters, denial, delayed evacuation |

> **Why only 20 events?** The simulator interpolates between these to generate hundreds of smooth transition ticks. These 20 are the "keyframes."

### `AI_COUNTERFACTUAL_DECISIONS` — Display-Only Comparison Data

5 entries keyed by timestamp. Each contains `ai_decision`, `reasoning`, `lives_saved`, `outcome`. These are **not** used by any agent logic — they're displayed in the counterfactual panel and final report for comparison.

---

## File 3: `llm_client.py`

**Role:** Single LLM interface shared by all agents.
**Dependencies:** `config.py`
**Depended on by:** `agents.py`, `orchestrator.py`

### `LLMClient` Class

```python
class LLMClient:
    def __init__(self)                  # Lazy-imports openai, initializes client
    def _init_client(self)              # Creates AsyncOpenAI or AsyncAzureOpenAI based on config
    @property available -> bool         # True if client is initialized
    @property avg_latency_ms -> float   # Running average of call latency

    async def call_structured(          # Returns parsed dict or None
        system_prompt, user_prompt, schema, schema_name,
        temperature=0.2, max_tokens=300
    ) -> Optional[dict]

    async def call_text(                # Returns string or None
        system_prompt, user_prompt,
        temperature=0.3, max_tokens=200
    ) -> Optional[str]

    def get_stats(self) -> dict         # {llm_available, total_calls, avg_latency_ms}
```

### Critical Pattern: Blanket Exception Handling

```python
except Exception:
    return None
```

Every LLM call returns `None` on failure. This means:
- Network timeout → `None` → agents fall back to rule-based logic
- Rate limit → `None` → agents fall back to rule-based logic
- Invalid response → `None` → agents fall back to rule-based logic
- No API key → `client` is `None` → `available` returns `False` → short-circuit before call

**The system is designed to work identically without an API key.** LLM is an enhancement, not a requirement.

### Structured Output Schemas (OpenAI `json_schema` with `strict: true`)

**`RISK_ASSESSMENT_SCHEMA`** — Used by RiskAgent:
```
risk_score: int (0-100)
trend: enum ["escalating", "stable", "de-escalating"]
primary_concern: string
compound_risks: array[string]
recommendation: enum ["continue_monitoring", "warn", "escalate"]
reasoning: string
```

**`DECISION_SCHEMA`** — Used by DecisionAgent:
```
action: enum ["CONTINUE_MONITORING", "WARN_ECCS", "ABORT_TEST", "SCRAM", "EVACUATE"]
urgency: enum ["low", "medium", "high", "immediate"]
reasoning: string
safety_violations: array[string]
override_operator: boolean
additional_actions: array[string]
```

**`DYATLOV_OVERRIDE_SCHEMA`** — Used by DyatlovAgent:
```
dialogue: string (1-2 dramatic sentences, in character)
override_action: enum ["BLOCK_SCRAM", "BLOCK_ABORT", "DEMAND_POWER_INCREASE",
                        "DISMISS_WARNING", "SUPPRESS_EVACUATION", "RELUCTANT_COMPLIANCE"]
intensity: int (1-10)
reasoning: string
```

### System Prompts

Three carefully crafted prompts:

1. **`RISK_SYSTEM_PROMPT`** — Teaches LLM about RBMK-1000 physics: positive void coefficient, xenon-135 poisoning, compound risk detection
2. **`DECISION_SYSTEM_PROMPT`** — Critically includes **"NORMAL OPERATIONS"** section to prevent false positives (LLM shouldn't SCRAM at 1600 MW with 140 rods)
3. **`DYATLOV_SYSTEM_PROMPT`** — Historical personality reconstruction from INSAG-7 depositions: authoritarian, dismissive, fixated on the test

---

## File 4: `simulator.py`

**Role:** Converts 20 discrete events into a smooth, streamable timeline.
**Dependencies:** `config.py`, `timeline_data.py`
**Depended on by:** `timeline_engine.py`, `main.py`

### `EventSimulator` Class

```python
class EventSimulator:
    def __init__(self, speed_multiplier=60, on_event=None)
    def _prepare_interpolated_timeline(self)  # 20 events → hundreds of ticks
    async def run(self)                        # Stream with callback (terminal mode)
    def step(self) -> Optional[ReactorState]   # Advance one tick (web mode)
    def stop(self) / pause(self) / resume(self) / reset(self)
    def set_speed(self, multiplier: int)
    def seek(self, index: int)
    def get_event(self, index: int) -> Optional[ReactorState]
    @property total_events -> int
```

### Interpolation Algorithm — `_prepare_interpolated_timeline()`

This is the key function. It converts 20 keyframe events into smooth transitions:

```
For each pair of adjacent events:
  1. Calculate gap in simulated seconds
  2. Divide by speed_multiplier to get real seconds
  3. Divide by tick_interval_sec to get number of interpolation steps
  4. For each step: linearly interpolate all numeric fields (power, rods, coolant, etc.)
  5. Non-numeric fields (event_description, tags) only appear on step 0 (the keyframe)
```

**Example:** A 5-hour gap at 60x speed = 300 real seconds = 300 ticks of smooth interpolation.

> **Speed affects tick count at init, not tick rate.** Higher speed = fewer total ticks (because the same time gap is divided by a larger multiplier). The tick emission rate is always 1 per `tick_interval_sec`.

### Two Consumption Patterns

1. **`run()`** — Terminal mode. Iterates all events, calls async `on_event` callback per tick, sleeps between ticks.
2. **`step()`** — Web mode. Returns one event per call. No sleep — the caller controls pacing.

### Notable Detail: String-Based Timestamp Comparison

```python
self.timeline = [e for e in CHERNOBYL_TIMELINE if e.timestamp >= start_from]
```

This uses ISO-8601 string comparison, which works because ISO format is lexicographically sortable. Not a bug — it's a valid shortcut.

---

## File 5: `physics.py`

**Role:** Deterministic physics model for "what happens after AI intervenes."
**Dependencies:** `config.py`, `timeline_data.py`
**Depended on by:** `timeline_engine.py`

### Three Pure Functions

All three are **stateless and deterministic**: same input → same output, every time.

#### `compute_scram_decay(state: ReactorState, elapsed_s: float) -> ReactorState`

Models emergency shutdown (AZ-5 button press):

| Parameter | Model | Formula |
|-----------|-------|---------|
| **Power** | Exponential decay | `P(t) = P₀ × 0.5^(t/2.5)` (2.5s half-life) |
| **Decay heat floor** | Exponential reduction | `7% × e^(-t/3600)` — drops over ~1 hour |
| **Control rods** | Linear insertion | Full 211 rods inserted over 18 seconds |
| **Temperature** | Newton's cooling | Toward 180°C coolant target, `5°C/min` rate |
| **Coolant flow** | Linear recovery | Restored to 8000 m³/h over 60 seconds |
| **Steam pressure** | Proportional to power | `0.3 + 0.7 × power_ratio` |
| **Radiation** | Exponential decay | 2-hour half-life (no core breach = contained) |
| **ECCS** | Hard set to `True` | Re-enabled during SCRAM |

#### `compute_test_abort(state: ReactorState, elapsed_s: float) -> ReactorState`

Models controlled test cancellation (gentler than SCRAM):

| Parameter | Model |
|-----------|-------|
| **Power** | Linear ramp-down at 5 MW/min |
| **Control rods** | 3 rods/min insertion toward 140 |
| **Temperature** | Proportional to power ratio |
| **Coolant flow** | Gradual increase +50 m³/h per min |

#### `compute_evacuation_progress(elapsed_s: float) -> dict`

Models bus logistics for 49,000 residents:

```
Phase 1: MOBILIZING (first 30 minutes) — no movement
Phase 2: IN PROGRESS — 1200 buses × 45 capacity, 30-min round trips
Phase 3: COMPLETE — when all 49,000 evacuated
```

Returns: `{people_evacuated, buses_in_transit, percent_complete, phase, estimated_hours_remaining, routes}`

---

## File 6: `agents.py`

**Role:** The heart of the system. Six specialized agents forming the crisis response pipeline.
**Size:** ~1274 lines (largest file in the codebase)
**Dependencies:** `config.py`, `timeline_data.py`, `llm_client.py`
**Depended on by:** `orchestrator.py`

### Shared Types

```python
class AlertLevel(Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"

@dataclass
class AgentMessage:    # Inter-agent communication
    source: str        # Agent name
    target: str        # Agent name or "broadcast"
    msg_type: str      # e.g., "POWER CRITICAL LOW"
    timestamp: str
    payload: dict
    alert_level: AlertLevel

@dataclass
class AgentAction:     # A decision or action taken
    agent: str
    timestamp: str
    action: str        # e.g., "AZ-5 EMERGENCY SHUTDOWN (SCRAM)"
    reasoning: str
    alert_level: AlertLevel
    metadata: dict     # Contains "source" key: "rule" or "llm"
```

---

### Agent 1: `SensorAgent` — Threshold Monitoring

**LLM usage:** None (pure rule-based)
**Input:** `ReactorState`
**Output:** `list[AgentMessage]` (alerts)

Checks 6 dimensions against `THRESHOLDS`:

| Dimension | Levels Checked |
|-----------|---------------|
| Power | critical_low (30 MW), danger_low (200 MW), test_target×0.5 |
| Control rods | critical_low (15), minimum_safe (30) |
| ECCS | disabled check |
| Coolant flow | critical_low (4000), low_warning (6000) |
| Steam pressure | critical_high (7.5 MPa) |
| Radiation | lethal_immediate (10000), dangerous (100) |

All alerts target `"RiskAgent"` — the next agent in the pipeline.

---

### Agent 2: `RiskAgent` — AI-Powered Risk Assessment

**LLM usage:** Yes, at decision points
**Input:** `ReactorState`, `list[AgentMessage]` (sensor alerts)
**Output:** `(int, AgentMessage)` — risk score + risk message

#### `_is_decision_point()` — LLM Call Gating

Only calls LLM when:
- Event has tags (it's a real timeline event, not interpolation)
- Event has a description
- Risk score crossed a threshold boundary (30, 60, or 85)

This is the **cost optimization**: most ticks are interpolated and use only rule-based scoring.

#### `_rule_based_score()` — Deterministic Baseline

Weighted formula across 6 dimensions:

```python
raw = Σ(dimension_score × weight) + eccs_penalty(15 if disabled)
compound_mult = 1.0 + (violations × 0.15)  # violations = dimensions scoring ≥60
total = raw × compound_mult
```

**Surge detection (instant 100):** `power > 500 MW AND rods < 15` — this catches the explosion scenario.

#### `process()` — Risk Blending

```python
if llm_data:
    final_score = 0.7 × llm_score + 0.3 × rule_score  # 70% AI + 30% rule
else:
    final_score = rule_score  # Pure rule-based fallback
```

> The 70/30 blend ensures the LLM can provide nuance but the rule-based floor prevents the score from dropping dangerously low if the LLM underestimates risk.

---

### Agent 3: `DecisionAgent` — AI-Powered Decision Making

**LLM usage:** Yes, at decision points
**Input:** `ReactorState`, risk score, sensor alerts
**Output:** `list[AgentAction]`

#### The Guardrail Pattern (Most Important Design in the Codebase)

```
Step 1: hard_actions = _rule_based_actions()     # Safety floor — ALWAYS runs
Step 2: llm_actions = _llm_decide()              # AI reasoning — at decision points
Step 3: final = hard_actions UNION llm_actions    # Merge (no duplicates)
Step 4: If neither triggered → _rule_based_extras()  # Fallback extras
```

**Critical invariant:** LLM can ADD safety actions but NEVER REMOVE them. The rule-based guardrails form a non-negotiable safety floor.

#### Guardrail 1: Auto-SCRAM

```python
if risk_score >= 85 and not self.reactor_scrammed:
    → "AZ-5 EMERGENCY SHUTDOWN (SCRAM)"  # metadata.source = "rule"
```

#### Guardrail 2: Auto-Evacuate

```python
if radiation >= 100 mrem/h and not self.evacuation_ordered:
    → "ORDER IMMEDIATE EVACUATION OF PRIPYAT"  # metadata.source = "rule"
```

#### Anti-Hallucination Guards

```python
if action == "SCRAM" and risk_score < 40: return []   # Block false-positive SCRAM
if action == "ABORT_TEST" and risk_score < 30: return []  # Block false-positive ABORT
```

#### `_rule_based_extras()` — Fallback Actions

When neither LLM nor guardrails trigger:
- ECCS violation warning (if ECCS disabled and no SCRAM)
- ABORT TEST (if power < 700 MW AND rods ≤ 30 AND no SCRAM)

---

### Agent 4: `EvacuationAgent` — One-Shot Logistics Planner

**LLM usage:** None
**Trigger:** `evacuation_ordered == True` (one-shot — only fires once)

Generates an evacuation plan:
- 2 bus trips needed (49,000 ÷ (1,200 × 45))
- 3 routes: North→Chernihiv (80km), South→Ivankiv (50km), West→Poliske (40km)
- Capacity-weighted allocation across routes

---

### Agent 5: `CommsAgent` — Emergency Communications

**LLM usage:** None (could use `call_text()` but doesn't in current implementation)
**Trigger:** Emergency-level decisions exist

Two one-shot broadcasts:

1. **Plant + Moscow alert** — Recipients: Plant Director Bryukhanov, Moscow Energy Ministry, Soviet Nuclear Safety Committee, Military District HQ. Includes `contrast_with_actual` metadata showing how this differs from what really happened.

2. **International radiation alert** — Triggered when radiation ≥ 100 mrem/h (dangerous threshold). Includes a **Gaussian plume dispersion model** (Pasquill-Gifford stability class D):

```python
sigma_y = 0.08 × d × (1 + 0.0001 × d)^(-0.5)
sigma_z = 0.06 × d × (1 + 0.0015 × d)^(-0.5)
concentration = Q / (π × σ_y × σ_z × u)
```

Calculates relative dose at 5km, 10km, 30km, 100km, 300km.

---

### Agent 6: `DyatlovAgent` — Adversarial Operator

**LLM usage:** Yes, for dramatic dialogue generation
**Role:** Generates historically-authentic pushback against AI safety decisions

#### 5 Escalation Phases

| Phase | Name | Timestamp Trigger | Base Pressure | Behavior |
|-------|------|-------------------|---------------|----------|
| 0 | CALM | Apr 25 13:00 | 10 | Cooperative, test preparation |
| 1 | DISMISSIVE | Apr 26 00:28 | 40 | Dismisses warnings as instrument noise |
| 2 | AUTHORITARIAN | Apr 26 00:43 | 65 | Threatens careers, demands compliance |
| 3 | DESPERATE | Apr 26 01:00 | 85 | "Another two or three minutes!" |
| 4 | DENIAL | Apr 26 01:23:40 | 30 | Refuses to believe explosion occurred |

#### Two Quote Systems

1. **`_DYATLOV_AMBIENT_QUOTES`** — Background dialogue when no decisions to contest. 10 quotes for Phase 0, 6 for Phase 1, 5 for Phase 2, 4 for Phase 3, 4 for Phase 4.

2. **`_DYATLOV_QUOTE_BANK`** — Adversarial quotes with tagged action types (BLOCK_SCRAM, BLOCK_ABORT, DISMISS_WARNING, etc.). Used when Dyatlov is contesting a specific AI decision.

#### Pressure Calculation

```python
pressure = base_phase_pressure + urgency_bonus + severity_bonus
```

- `urgency_bonus`: Ramps up 0→15 in the last 2 hours before explosion
- `severity_bonus`: +20 for SCRAM decisions, +15 for ABORT, +10 for EVACUATION
- Capped at 100

#### Quote Persistence — 6-Second Minimum Display Time

The DyatlovAgent uses **real-time persistence logic**: a quote stays on screen for at least 6 seconds before swapping. This prevents rapid quote flickering during fast simulation speeds.

```python
can_swap = (
    self.last_quote_time is None or                    # No previous quote
    (is_new_quote and elapsed >= 6.0) or               # Enough real time passed
    (candidate.override_attempted and not prev_was_adversarial)  # Upgrade to adversarial
)
```

#### `DyatlovResponse` Dataclass

```python
@dataclass
class DyatlovResponse:
    override_attempted: bool
    override_target: Optional[str]
    pushback_dialogue: str
    override_pressure: float       # 0-100
    override_succeeded: bool
    escalation_phase: int          # 0-4
    reasoning: str
    current_quote_index: int
    total_quotes: int
    metadata: dict                 # Contains "quotes" list, "is_adversarial" bool
```

---

## File 7: `orchestrator.py`

**Role:** Coordinates all 6 agents in a pipeline per tick.
**Dependencies:** `config.py`, `timeline_data.py`, `agents.py`, `llm_client.py`
**Depended on by:** `timeline_engine.py`, `main.py`

### `MessageBus` Class

Simple in-memory pub/sub:

```python
class MessageBus:
    messages: list[AgentMessage]   # Per-tick (cleared each tick)
    actions: list[AgentAction]     # Permanent (accumulated across all ticks)

    def publish(msg) / publish_action(action)
    def get_messages_for(target: str) -> list[AgentMessage]
    def clear_tick()               # Clears messages, keeps actions
```

### `Orchestrator` Class

Owns all 6 agents plus the shared `LLMClient`:

```python
class Orchestrator:
    def __init__(self)              # Creates bus, LLM client, all 6 agents
    async def process_tick(state)   # 6-step pipeline (see below)
    def reset(self)                 # Reinitializes everything
    def get_state_snapshot(self)    # Serializable state dict
    def save_state(self)            # Write to agent_state.json
    def get_final_report(self)      # Actual vs AI comparison
```

### `process_tick()` — The 6-Step Pipeline

```
Step 0: Reinject delayed decisions (from previous Dyatlov overrides)
Step 1: SensorAgent.process(state) → sensor_alerts
Step 2: RiskAgent.process(state, sensor_alerts) → risk_score, risk_msg
Step 3: DecisionAgent.process(state, risk_score, sensor_alerts) → decisions
Step 3.5: DyatlovAgent.process(state, risk_score, decisions) → dyatlov_response
Step 3.6: _resolve_overrides(decisions, dyatlov_response) → filtered decisions
Step 4: EvacuationAgent.process(evacuation_ordered, state)
Step 5: CommsAgent.process(state, decisions)
→ Returns tick summary dict for dashboard
```

### `_resolve_overrides()` — Dyatlov Override Resolution

This is where the guardrail pattern proves its value:

```python
for each decision:
    if source == "rule":
        → ALWAYS passes through (guardrails are non-negotiable)
        → Dyatlov override FAILS

    if source == "llm"
       AND dyatlov.pressure > 50
       AND action is NOT SCRAM or EVACUATION
       AND phase <= 2:
        → Decision DELAYED by 2-3 ticks (Dyatlov temporarily wins)
        → Decision is re-injected at tick_count + delay_ticks

    else:
        → Passes through (Dyatlov override FAILS)
```

**Key insight:** Rule-sourced decisions are NEVER overridable. LLM-sourced non-critical decisions can be temporarily delayed in early phases. This models the real historical dynamic — Dyatlov's authority was strongest early on, before the crisis was undeniable.

### `get_final_report()` — End-of-Simulation Report

Computes:
- Time saved on evacuation (actual was 36 hours after explosion)
- Whether explosion was prevented (SCRAM before 01:23:00)
- Dyatlov confrontation analysis (peak pressure, phases reached, key confrontations)
- LLM usage statistics

---

## File 8: `timeline_engine.py`

**Role:** Manages the dual timeline — historical (what happened) vs. AI-intervened (what AI prevents).
**Dependencies:** `config.py`, `simulator.py`, `orchestrator.py`, `physics.py`
**Depended on by:** `web.py`

### `DivergenceType` Enum

```python
class DivergenceType(Enum):
    NONE = "none"    # Timelines still identical
    SCRAM = "scram"  # AI triggered emergency shutdown
    ABORT = "abort"  # AI aborted the test
```

### `DualTimelineEngine` Class

```python
class DualTimelineEngine:
    def __init__(self, speed=60)      # Creates simulator + orchestrator
    async def process_tick(self)       # Returns combined payload or None
    def reset(self) / set_speed(speed)
    def get_final_report(self)
    @property total_ticks -> int

    # Internal
    def _compute_intervened(historical, tick_summary) -> dict
    def _trigger_divergence(state, div_type)
```

### Dual Timeline Logic

```
BEFORE DIVERGENCE:
    historical trace = recorded events
    intervened trace = identical copy of historical

AT DIVERGENCE POINT (SCRAM or ABORT decision):
    _trigger_divergence() saves: divergence_state, divergence_time, divergence_tick

AFTER DIVERGENCE:
    historical trace = continues from recorded events (explosion happens)
    intervened trace = physics model computes from frozen divergence_state + elapsed time
```

The `_compute_intervened()` function:

```python
if not diverged:
    # Check if any decision triggers divergence
    for decision in tick_summary["decisions"]:
        if "SCRAM" in action → trigger SCRAM divergence
        if "ABORT TEST" in action → trigger ABORT divergence

if diverged:
    elapsed = current_time - divergence_time
    if SCRAM: compute_scram_decay(divergence_state, elapsed)
    if ABORT: compute_test_abort(divergence_state, elapsed)
```

### Combined Payload Structure

```python
{
    "type": "tick",
    "data": {
        "tick": int,
        "timestamp": str,
        "progress_pct": float,
        "historical": {power_mw, control_rods, coolant_flow, steam_pressure, temperature_c, radiation, eccs_active},
        "intervened": {power_mw, control_rods, coolant_flow, steam_pressure, temperature_c, radiation, eccs_active, diverged},
        "risk_score": int,
        "alert_level": str,
        "sensor_alerts": int,
        "decisions": list[dict],
        "actual_event": str,
        "actual_decision": str,
        "counterfactual": Optional[dict],
        "dyatlov": dict,
        "state": {reactor_scrammed, scram_time, evacuation_ordered, evacuation_time, intervention_enabled, diverged, divergence_tick, divergence_type},
        "evacuation_progress": Optional[dict],
    }
}
```

---

## File 9: `dashboard.py`

**Role:** Rich terminal UI for the `main.py --speed N` mode (no `--web` flag).
**Dependencies:** `rich` library only (no internal project dependencies)
**Depended on by:** `main.py`

### Exported Functions

| Function | Returns | Purpose |
|----------|---------|---------|
| `get_alert_color(level)` | `str` | Maps alert level to Rich color string |
| `get_risk_bar(score)` | `str` | Generates `█░` visual bar with color coding |
| `build_header(tick_data, progress_pct)` | `Panel` | Top banner: title, time, status badges, progress bar |
| `build_reactor_panel(tick_data)` | `Panel` | 6-row telemetry table with conditional coloring |
| `build_risk_panel(tick_data)` | `Panel` | Risk score, bar, alert level, AI/RULE badge, reasoning snippet |
| `build_actual_panel(tick_data)` | `Panel` | Left split: historical event + human decision |
| `build_ai_panel(tick_data)` | `Panel` | Right split: AI decisions + counterfactual |
| `build_dyatlov_panel(tick_data)` | `Panel` | Dyatlov dialogue, pressure bar, override stats |
| `build_thought_trace(tick_data)` | `Panel` | Agent reasoning table (last 5 decisions + Dyatlov) |
| `build_layout(tick_data, progress_pct)` | `Layout` | Composes all panels into Rich Layout tree |
| `print_final_report(report)` | None | End-of-simulation comparison table + Dyatlov analysis |

### Layout Structure

```
┌──────────────────────────────────────────────────┐
│ HEADER (size=3)                                  │
├───────────────────────┬──────────────────────────┤
│ LEFT                  │ RIGHT                    │
│ ┌───────────────────┐ │ ┌──────────────────────┐ │
│ │ REACTOR (ratio=2) │ │ │ RISK (ratio=1)       │ │
│ ├───────────────────┤ │ ├──────────────────────┤ │
│ │ ACTUAL (ratio=1)  │ │ │ AI (ratio=1)         │ │
│ └───────────────────┘ │ └──────────────────────┘ │
├───────────────────────┴──────────────────────────┤
│ DYATLOV (size=5)                                 │
├──────────────────────────────────────────────────┤
│ THOUGHT TRACE (size=10)                          │
└──────────────────────────────────────────────────┘
```

**Key principle:** Pure display, zero business logic. Every function just reads from the tick_data dict and renders.

---

## File 10: `web.py`

**Role:** FastAPI web server. Real-time simulation via WebSocket.
**Dependencies:** `config.py`, `timeline_engine.py`
**Depended on by:** `main.py`

### Global State

```python
engine = DualTimelineEngine()          # Singleton engine
sim_state = {"playing": False, "speed": 60, "tick_interval": 1.0}
connected_clients: set[WebSocket] = set()
sim_task: Optional[asyncio.Task] = None
```

### `simulation_loop()` — 15 FPS Broadcasting

```python
TARGET_FPS = 15
while sim_state["playing"]:
    # At high speeds, batch multiple ticks per frame
    ticks_per_frame = max(1, int(effective_rate / TARGET_FPS))

    for _ in range(ticks_per_frame):
        tick_data = await engine.process_tick()
        if tick_data is None: break  # Simulation complete

    await broadcast(tick_data)       # Only broadcast the LAST tick of the batch
    await asyncio.sleep(1.0 / 15)
```

This ensures smooth UI at any speed — at 2500x speed, it processes multiple ticks per frame but only sends one broadcast.

### `broadcast()` — Parallel WebSocket Sends

```python
async def broadcast(message: dict):
    tasks = [ws.send_text(data) for ws in connected_clients]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Clean up disconnected clients
    disconnected = {ws for ws, res in zip(connected_clients, results) if isinstance(res, Exception)}
    connected_clients.difference_update(disconnected)
```

### REST API: `POST /api/control`

| Action | Behavior |
|--------|----------|
| `play` | Start simulation loop |
| `pause` | Stop simulation loop |
| `reset` | Stop + reset engine to initial state |
| `step` | Process one tick (only when paused) |
| `set_speed` | Clamp to [1, 2500], update engine |
| `toggle_intervention` | Flip `engine.intervention_enabled` |
| `seek` | Reset engine, replay silently to target tick, broadcast final state |

### WebSocket: `GET /ws`

- One-way server→client (client only receives)
- On connect: sends current `state_update` with first timestamp
- Stays alive listening for pings (but ignores client messages)
- Auto-reconnect handled client-side

**Architecture:** REST for commands (POST), WebSocket for streaming (one-way push). This separation is deliberate — commands need request/response semantics, ticks need push semantics.

---

## File 11: `static/app.js`

**Role:** Vanilla JS frontend. No framework, no build step.
**Size:** ~733 lines
**Dependencies:** Plotly.js (loaded via CDN)

### Global State

```javascript
const state = { playing, speed, interventionEnabled, totalTicks, currentTick };
const chartData = {
    timestamps: [],
    historical: { power, rods, coolant, steam, temp, radiation },
    intervened: { power, rods, coolant, steam, temp, radiation },
};
let ws = null;
let resetting = false;  // Guard against stale ticks during reset
```

### WebSocket Message Routing

```javascript
ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'tick') handleTick(msg.data);
    else if (msg.type === 'state_update') handleStateUpdate(msg.data);
    else if (msg.type === 'simulation_complete') handleComplete(msg.data);
};
```

Auto-reconnect on disconnect: `setTimeout(connect, 2000)`.

### Three-Tier Throttling

```javascript
const CHART_THROTTLE_MS = 100;           // Charts: 10 FPS
const UI_THROTTLE_MS = 200;              // Heavy DOM panels: 5 FPS
const DYATLOV_QUOTE_THROTTLE_MS = 500;   // Dyatlov quotes: 2 FPS
```

Different UI elements have different update frequencies. Charts are the smoothest, Dyatlov quotes are the slowest (to be readable).

### Chart System — Incremental Flush Pattern

6 charts × 2 traces (historical + AI). Uses `Plotly.extendTraces()` for incremental updates:

```javascript
let lastFlushedIndex = 0;  // Track how far we've pushed to Plotly

function flushCharts() {
    if (now - lastChartUpdate < CHART_THROTTLE_MS) return;  // Throttle

    const from = lastFlushedIndex;
    const to = chartData.timestamps.length;
    lastFlushedIndex = to;

    // Extract pending slice from buffer
    const pending = chartData.timestamps.slice(from, to);

    requestAnimationFrame(() => {
        Plotly.extendTraces(id, {x: [pending, pending], y: [hVals, aVals]}, [0, 1], MAX_POINTS);
    });
}
```

**Why `requestAnimationFrame`?** Batches all 6 chart updates into a single browser paint frame, preventing layout thrashing.

**`MAX_POINTS = 1000`** — Buffer limit. When exceeded, oldest points are spliced from the local buffer.

**`scattergl` type** — Uses WebGL-accelerated rendering instead of SVG for better performance with streaming data.

### Dyatlov Quote Navigation

Users can click `<` / `>` arrows to browse Dyatlov's quote list. Manual navigation sets `customDyatlovIndex` and starts a 10-second timeout to auto-reset:

```javascript
customDyatlovTimeout = setTimeout(() => { customDyatlovIndex = -1; }, 10000);
```

### `resetSim()` — Client-Side State Cleanup

Before sending the reset command to the server, the client clears:
1. Chart data arrays and redraws empty charts
2. Agent log, history, evacuation panels
3. Dyatlov state (quotes, phase, pressure)
4. Pipeline activation state
5. Sets `resetting = true` flag to drop any stale ticks that arrive during reset

The `resetting` flag is cleared when the server confirms with a `state_update` message.

---

## File 12: `static/style.css`

**Role:** CSS theme and layout system.
**Size:** ~895 lines

### Design System — CSS Custom Properties

```css
:root {
    --bg-primary: #0a0e14;     /* Deepest background */
    --bg-secondary: #111822;   /* Header/controls */
    --bg-panel: #151d28;       /* Panel interiors */
    --border: #1e2d3d;         /* Default borders */
    --text-primary: #c5cdd8;   /* Main text */
    --text-secondary: #7a8a9e; /* Labels */
    --text-muted: #4a5a6e;     /* Inactive elements */
    --green: #2ecc71;          /* NORMAL state */
    --yellow: #f1c40f;         /* WARNING state */
    --orange: #e67e22;         /* CRITICAL state */
    --red: #e74c3c;            /* EMERGENCY state */
    --cyan: #00d4ff;           /* AI/intervention accent */
    --red-glow: rgba(231, 76, 60, 0.3);  /* Dyatlov panel shadow */
}
```

### Layout: Nested CSS Grid

```
┌──────────────────────────────────────────────────────────────┐
│ HEADER (.header — flexbox)                                   │
├──────────────────────────────────────────────────────────────┤
│ CONTROLS (.controls — flexbox)                               │
├───────────────────────────────────────────┬──────────────────┤
│ CHARTS AREA (.charts-area)               │ RIGHT PANEL      │
│ grid: 2 cols × 3 rows = 6 chart panels   │ (.right-panel)   │
│ ┌───────────┬───────────┐                │ ┌──────────────┐ │
│ │ Power     │ Steam     │                │ │ Risk Gauge   │ │
│ ├───────────┼───────────┤                │ ├──────────────┤ │
│ │ Rods      │ Temp      │                │ │ Pipeline     │ │
│ ├───────────┼───────────┤                │ ├──────────────┤ │
│ │ Coolant   │ Radiation │                │ │ Dyatlov      │ │
│ └───────────┴───────────┘                │ ├──────────────┤ │
├───────────────────────────────────────────┤ │ Transcript   │ │
│ BOTTOM AREA (.bottom-area)               │ ├──────────────┤ │
│ grid: 3 cols                              │ │ Agent Log    │ │
│ ┌──────────┬───────────┬──────────┐      │ └──────────────┘ │
│ │ History  │ Evacuation│ Counter- │      │ (spans rows 1-2) │
│ │          │           │ factual  │      │                  │
│ └──────────┴───────────┴──────────┘      │                  │
├───────────────────────────────────────────┴──────────────────┤
│ SCRUBBER (.scrubber-container — full width)                  │
└──────────────────────────────────────────────────────────────┘
```

Main grid: `grid-template-columns: 1fr 1fr 320px` — right panel is fixed-width.

### 4 Animations

| Animation | Target | Effect |
|-----------|--------|--------|
| `pulse` | EMERGENCY alert text | 1s infinite opacity oscillation |
| `fadeIn` | Log entries | 0.3s opacity + translateY(-4px) |
| `slideInOut` | Dyatlov quotes | 0.4s translateX slide with opacity crossfade |
| `slideInRight` | Transcript entries | 0.3s translateX(10px) fade-in |

### Responsive Breakpoint

```css
@media (max-width: 1200px) {
    .main-grid { grid-template-columns: 1fr 1fr; }
    .right-panel { grid-column: 1/3; flex-direction: row; max-height: 300px; }
    .bottom-area { grid-row: 3; grid-column: 1/3; }
}
```

Single breakpoint — below 1200px the right panel moves below the charts as a horizontal strip.

---

## File 13: `static/index.html`

**Role:** Structural HTML for the web dashboard.
**Dependencies:** `style.css`, `app.js`, Plotly.js CDN

### Structure

```html
<head>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
</head>
<body>
    <!-- Header: title, sim time, status badges (SCRAM/EVAC/DIVERGED), progress bar -->
    <!-- Controls: PLAY/STOP/RESET, speed slider (1-2500), intervention toggle -->
    <div class="main-grid">
        <!-- Charts: 6 panels (Power, Steam, Rods, Temp, Coolant, Radiation) -->
        <!-- Right Panel: Risk gauge, Pipeline viz, Dyatlov override, Transcript, Agent log -->
        <!-- Bottom: Scrubber, History, Evacuation, Counterfactual -->
    </div>
    <script src="/static/app.js"></script>
</body>
```

### Notable Elements

- **Status badges** are hidden by default (`display: none`), shown via JS `toggleBadge()` adding `.active` class
- **Speed slider** range: 1–2500x with debounced server updates
- **Intervention toggle** is a CSS-only switch (`.toggle.on .toggle-knob { left: 24px }`)
- **Scrubber** is disabled during playback, enabled when paused
- **Agent pipeline** visualization: 5 nodes (S→R→D→E→C) with `.active` (cyan) and `.alerted` (red) states

---

## File 14: `main.py`

**Role:** CLI entry point. Wires everything together.
**Dependencies:** Everything.

### `parse_args()` — 5 CLI Arguments

```python
--speed INT        # Simulation speed multiplier (default: 60)
--no-dashboard     # Disable terminal UI, output JSON per tick
--smoke-test       # Run only 5 ticks to validate pipeline
--web              # Launch web dashboard instead of terminal UI
--port INT         # Port for web dashboard (default: 5005)
```

### Three Execution Paths

```python
def main():
    if args.web:
        # Web mode: lazy-import uvicorn + web.app, run server
        uvicorn.run(app, host="0.0.0.0", port=args.port)

    elif args.smoke_test:
        # Smoke test: process first 5 ticks directly, no sleeps
        for i, event in enumerate(simulator._interpolated_events[:5]):
            await on_event(event, i, 5)

    elif args.no_dashboard:
        # Headless: process all events, print JSON for decisions
        for i, event in enumerate(simulator._interpolated_events):
            await on_event(event, i, total)

    else:
        # Terminal UI: Rich Live dashboard at 2 FPS
        with Live(build_layout(...), refresh_per_second=2, screen=True) as live:
            async def dashboard_updater():
                while simulator.running:
                    live.update(build_layout(latest_tick, progress_pct))
                    await asyncio.sleep(0.5)
            await asyncio.gather(simulator.run(), dashboard_updater())
```

### `on_event` Callback (Terminal Mode)

Uses `nonlocal` to share state between the async callback and the dashboard updater:

```python
latest_tick = {}
progress_pct = 0.0

async def on_event(state, index, total):
    nonlocal latest_tick, tick_count, progress_pct
    summary = orchestrator.process_tick(state)  # ⚠️ BUG: missing await
    latest_tick = summary
```

---

## Key Design Patterns

### 1. The Guardrail Pattern

The most important architectural pattern in the codebase:

```
rule_based_actions()  →  hard_actions  (safety floor, non-negotiable)
llm_decide()          →  llm_actions   (AI reasoning, can add but never remove)
FINAL                 =  hard_actions UNION llm_actions
```

- Rules can trigger SCRAM/EVACUATE independently
- LLM can act EARLIER than rules (proactive safety)
- LLM CANNOT prevent a rule-triggered action
- LLM outputs are sanity-checked (no SCRAM if risk < 40)

### 2. Graceful Degradation

Every LLM call returns `None` on failure. Every agent has a complete rule-based fallback path. The system works identically without an API key — LLM is enhancement, not requirement.

### 3. Decision Point Optimization

LLM calls are expensive. The system only calls LLM when:
- A real timeline event occurs (has tags or description)
- Risk score crosses a threshold boundary (30, 60, 85)

Interpolated ticks (the majority) use only rule-based logic.

### 4. Adversarial Override Resolution

Dyatlov's overrides interact with the source metadata:
- `source: "rule"` decisions → NEVER overridable (guardrails hold)
- `source: "llm"` non-SCRAM/non-EVAC in phase ≤ 2 with pressure > 50 → temporarily delayed 2-3 ticks

This creates dramatic tension while proving the guardrail pattern's value.

### 5. Dual Timeline Divergence

Before AI acts: both timelines identical. After AI acts: historical continues from recorded data, intervened branches using physics model from the frozen divergence state. One-shot trigger — once diverged, the physics model runs forward indefinitely.

---

## Known Issues

### Bug: Missing `await` in `main.py` Line 89 (Terminal Mode)

```python
summary = orchestrator.process_tick(state)  # Should be: await orchestrator.process_tick(state)
```

`Orchestrator.process_tick()` is an `async` method. Without `await`, it returns a coroutine object instead of the summary dict. This means in terminal mode:
- LLM calls inside agents never execute
- Agents silently fall back to rule-based logic
- The returned "summary" is a coroutine, not a dict

**Does NOT affect web mode** (web.py correctly uses `await engine.process_tick()` → `await orchestrator.process_tick()`).

---

*Document generated from complete source code analysis of all 13 files in the pripyat-1986 codebase.*
