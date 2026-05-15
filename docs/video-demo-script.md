# PRIPYAT-1986 — Demo Cue Card (~8:30 min)

> **Hit Play before you speak.** Speed 60x · intervention ON.

---

## INTRO (0:00 – 1:30)
*Sim running in background.*

"I've started the simulation — the reactor is coming online behind me. I'll come back to it.

We are **WattAgents**.

 We picked a project, we wanted real stakes — not a chatbot, not a productivity tool. An AI safety agent that works under pressure and protects our most critical infrastructure.

So we picked the worst industrial disaster in history.

**Chernobyl. April 26, 1986.** Dyatlov disabled every safety system, ignored every alarm, and overrode every operator who told him to stop. His exact words: *'I'll have every one of you fired if you stop this test.'*

At 1:23 AM, the reactor exploded. 40 dead. Over a thousand irradiated. $800 billion in damage. The political fallout brought down the Soviet Union.

The safety systems existed. Emergency shutdown existed. But one man with authority could override all of it.

**Our question: what if he couldn't?**

That's what we built."

---

## DASHBOARD (1:30 – 2:15)
*Point to each section as you name it.*

"Two lines on every chart — red is 1986, blue is what our agents do differently. Real reactor physics.

Six things tracked: power output, control rods *(the brakes)*, coolant, temperature, radiation, risk.

Risk gauge — two scores every tick: hard physics rules, and a live GPT-4o reasoning layer. System always takes the maximum — agents can only raise danger, never lower it.

Five agents in a pipeline — Sensor feeds Risk feeds Decision feeds Evacuation feeds Comms — every tick. 95% rule-based. LLM only fires when context matters. Full simulation: **ten cents**.

Dyatlov — adversarial agent, real Soviet quotes — fighting every safety call. Every override: BLOCKED."

---

## SIM: CALM (2:15 – 3:00)
*Point at pipeline firing.*

"Full power, brakes inserted, everything stable. Agents always watching, never overreacting.

Rules tell you when a threshold breaks. Agents reason about *where things are heading* before it breaks. That gap is where Chernobyl happened. That's the gap we close."

---

## SIM: ESCALATION → SCRAM (3:00 – 5:00)
*Let the dashboard talk. Hit these 4 beats:*

**Beat 1 — Agent watches:** "Power dropping. Rules see nothing alarming. But the agent detects the reactor becoming unstable at low power — calls risk 40. Watching, not acting yet."

**Beat 2 — Agent acts early:** "Near-zero power. Toxic gas buildup imminent. Emergency cooling manually disabled — last safety barrier gone. Agent calls risk 76 and issues **ABORT TEST**. Hard rules are still at 30. The agent understood what was *coming*, not just what had happened."

**Beat 3 — Dyatlov blocks:** *'That reading is noise.'* "He blocks it. Our architecture allows that — ABORT can be contested."

**Beat 4 — Escalation:** "Next tick. Same reactor. The agent escalates: **EMERGENCY SHUTDOWN — SCRAM.** All brakes drop. Reaction stops."

> *SCRAM badge fires. 3 seconds. Say nothing.*

"SCRAM cannot be contested. That's the design — minimum force first, then non-negotiable. **Guardrail-Union Pattern**: rules are the floor, agents reason above them, final action is always the union. Agent fails — rules still fire. System degrades toward safety.

Red line: 30,000 MW, reactor gone. Blue line: controlled shutdown, everyone goes home. Same reactor. Same man. He couldn't stop it."

> *3 seconds. Silence.*

---

## MANUAL MODE (5:00 – 7:30)
*Switch to Manual Control.*

"Now the real test. I'm the operator. These sliders control the reactor directly — not a mockup. Starting nominal — risk zero, everything green."

> *Pull rods to ~8. Disable ECCS.*

"I'm pulling the brakes out. Power surging — watch the chart. Temperature climbing. Risk jumping — yellow... red...

Agent log flooding with warnings. RiskAgent calling Azure OpenAI — you can see the LLM calls ticking up.

Risk at 70... 80... **85 — SCRAM. Automatic.** I didn't press anything. The guardrail fired.

Now watch this —"

> *Wiggle both sliders aggressively.*

"I'm yanking these sliders. Rods down. Coolant off. Nothing happens. **The agents took over.** Power decaying. Rods inserting. Reactor shutting down safely.

I. Cannot. Stop. It.

Risk dropping... 40... 20... normal. Reactor safe. Despite everything I did.

In 1986, Dyatlov overrode the safety systems. In our architecture, **that is architecturally impossible.** I just proved it live."

---

## ARCHITECTURE + VALUE (7:30 – 8:00)

"**Azure AI Foundry** — GPT-4o, structured JSON outputs. Every agent call returns a guaranteed schema — no parsing failures, no hallucination risk in the action path.

**Cosmos DB** — every decision, every blocked override, every sensor reading. Immutable audit trail. Scroll that log — that's regulatory compliance, built in from day one.

**The Guardrail-Union Pattern** is the reusable architecture. Swap ReactorState for GridState — power grids. WellState — oil rigs. FlightState — aircraft. Microsoft and MISO deployed this exact pattern on Azure AI Foundry managing grids for **45 million people**. We proved it against the worst industrial disaster in history.

Ten cents per run. LLM fails — rules still fire. System gets safer when AI fails, not weaker."

---

## CLOSE (8:00 – 8:30)

"Three numbers.

**35 hours** — how long 49,000 people waited for evacuation in 1986. Our agents order it in minutes.

**6 agents. Zero single points of failure.**

**Ten cents per run.**

The architecture is the product. The disaster is just the proof.

We are WattAgents."

---

| Phase | Time |
|-------|------|
| Intro | 0:00–1:30 |
| Dashboard | 1:30–2:15 |
| Sim: Calm | 2:15–3:00 |
| Sim: SCRAM | 3:00–5:00 |
| Manual | 5:00–7:30 |
| Arch + Value | 7:30–8:00 |
| Close | 8:00–8:30 |
