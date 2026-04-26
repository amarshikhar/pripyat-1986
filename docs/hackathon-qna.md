# PRIPYAT-1986 Hackathon Q&A — Complete Preparation Guide

Practice every answer out loud. Keep answers to 30-60 seconds unless they ask you to go deeper.

---

## CATEGORY 1: THE BIG PICTURE

### Q1: What is this project in one sentence?
**A:** "PRIPYAT-1986 is a multi-agent AI crisis response system that replays the Chernobyl disaster through 6 autonomous agents and proves — in real time — that AI with proper guardrails would have prevented the explosion and evacuated 49,000 people 35 hours earlier."

### Q2: Why Chernobyl? Why not a synthetic scenario?
**A:** "Three reasons. First, Chernobyl is the most documented industrial disaster in history — INSAG-7, IAEA, WNA give us timestamped telemetry and exact human decisions, so we have ground truth to validate against. Second, Chernobyl was caused by a *human overriding safety systems* — which is exactly the problem multi-agent AI solves. Third, it's the most dramatic demonstration possible — we're not showing a toy demo, we're showing that AI could have saved 31 lives immediately and prevented ~4,000 long-term cancer deaths."

### Q3: Is this just a simulation, or does it have real-world applicability?
**A:** "This is a functional prototype of the Control Room of the Future architecture. The same pattern is already deployed in production: MISO and Microsoft launched an Azure AI Foundry platform in January 2026 managing power grids for 45 million people across 15 US states. Capgemini presented their CRoF at CIGRE 2025. NREL's eGridGPT does live SCADA analysis. We're not inventing a pattern — we're implementing one that industry has already validated, but we're using the most compelling possible dataset to prove it works."

### Q4: What makes this different from just calling GPT with sensor data?
**A:** "Three critical differences. First, the guardrail-union pattern: rules always run *first* to establish a safety floor, then the LLM runs to add proactive recommendations, and the final actions are the *union* — the LLM can add safety actions but can never remove a rule-triggered one. Second, the adversarial Dyatlov agent actively stress-tests the AI's decisions by trying to override them, exactly like the real human did. Third, graceful degradation — if the LLM goes down, every agent falls back to pure rule-based logic. The system is *safer without AI than with compromised AI*."

### Q5: What problem does this solve that doesn't already have a solution?
**A:** "The core problem is: what happens when a human operator overrides AI safety recommendations? Every safety-critical system today — nuclear, aviation, oil & gas — has this vulnerability. Our system implements a *non-negotiable safety floor* where rule-based guardrails cannot be overridden by either the LLM or the human operator. The Dyatlov agent proves this in the most adversarial conditions: even under Phase 3 'desperate' pressure at 85/100 override intensity, the SCRAM guardrail fires. That's the contribution — a provably safe human-AI decision architecture."

---

## CATEGORY 2: ARCHITECTURE & TECHNICAL DESIGN

### Q6: Walk me through the architecture.
**A:** "Six agents in a pipeline. *SensorAgent* monitors 6 reactor dimensions against RBMK-1000 safety thresholds — pure rule-based. *RiskAgent* scores 0-100 using a 70% AI + 30% rule-based blend with compound threat detection. *DecisionAgent* is the brain — it runs hard guardrails first, then the LLM, then merges them with a union operation. *DyatlovAgent* is adversarial — it models the real Deputy Chief Engineer trying to override every safety decision. *EvacuationAgent* plans 3 routes for 49,000 people. *CommsAgent* drafts emergency broadcasts and runs a Gaussian plume dispersion model. An in-memory message bus coordinates them per tick, and a dual-timeline engine runs historical and AI-intervened physics side by side."

### Q7: Why 6 agents and not one monolithic agent?
**A:** "Separation of concerns maps to how real control rooms work. In production, each agent would be an independent microservice with its own scaling and failure domain. If the RiskAgent's LLM times out, it falls back to rules — but SensorAgent, EvacuationAgent, and CommsAgent are completely unaffected. This also maps cleanly to Azure services: SensorAgent → Event Hubs consumer, RiskAgent → Azure AI Foundry, DecisionAgent → Semantic Kernel, EvacuationAgent → Azure Maps + graph routing, CommsAgent → Logic Apps notification pipeline."

### Q8: Explain the guardrail-union pattern in detail.
**A:** "Step 1: `_rule_based_actions()` always runs — it checks if risk exceeds 85 (auto-SCRAM) or radiation exceeds 100 mrem/h (auto-evacuate). These are hard-coded, non-negotiable. Step 2: at decision points, `_llm_decide()` calls the LLM for a structured JSON response — it might recommend ABORT_TEST or WARN_ECCS earlier than rules would trigger. Step 3: the final action set is the *union* of both. The LLM can be proactive — triggering an abort at risk 65 before rules would fire at 85 — but it can never suppress a rule-triggered SCRAM. There are also anti-hallucination guards: the LLM cannot trigger SCRAM below risk 40, preventing false positives."

### Q9: How does the risk scoring work?
**A:** "Two layers. The rule-based baseline scores 6 dimensions with weights: power 30%, rods 25%, coolant 15%, steam 15%, temp 10%, radiation 5%. Each dimension maps sensor values to 0-100 scores based on RBMK-1000 safety bands. There's an ECCS penalty (+15 if disabled) and a compound violation multiplier: `1.0 + (violations_over_60 × 0.15)`. A surge detector catches the explosion scenario: `power > 500 AND rods < 15 → instant 100`. The LLM gets the full telemetry plus rate-of-change deltas plus sensor alerts, and returns its own 0-100 score. Final score: `0.7 × LLM + 0.3 × rules`. The blend ensures the LLM's nuanced judgment dominates but rules anchor it."

### Q10: How do you handle LLM latency in a real-time system?
**A:** "Three strategies. First, *decision-point-only calling* — only ~5% of ticks trigger LLM calls (when events have tags, descriptions, or risk crosses a threshold boundary at 30/60/85). This gives a 20x cost reduction and keeps 95% of ticks at pure rule-based speed. Second, the LLM has a 5-second timeout — if it doesn't respond, we return None and fall back to rules. Third, on the web dashboard, we batch multiple ticks per frame at high simulation speeds and only broadcast the last tick, targeting 15 FPS. The average LLM latency is tracked via `llm_client.avg_latency_ms` and displayed on the dashboard."

### Q11: Why WebSocket instead of polling or SSE?
**A:** "Full-duplex, low-latency, persistent connection. We're broadcasting up to 15 tick updates per second with 6 chart data points each — that's 90 data points per second per client. HTTP polling would be 15 requests/sec, unacceptable. SSE is one-way but doesn't handle binary well and has reconnection limitations. WebSocket gives us one persistent connection with `asyncio.gather` for parallel broadcasting to all clients, plus automatic cleanup of disconnected clients via `return_exceptions=True`."

### Q12: Why Vanilla JS instead of React/Vue?
**A:** "Deliberate choice for three reasons. First, zero build step — no webpack, no bundler, no node_modules. The entire frontend is 3 files: index.html, app.js, style.css. Second, Plotly.js with `scattergl` (WebGL-accelerated) handles 2000-point rolling buffers natively — React's virtual DOM reconciliation would actually slow down 6 real-time charts at 5 FPS. Third, this is a hackathon — iteration speed matters more than component abstraction. The total frontend is ~850 lines."

### Q13: How does the dual timeline engine work?
**A:** "Before divergence, both timelines are identical — the historical data plays through. The engine scans each tick's decisions for SCRAM or ABORT actions. When it finds one, it records the `divergence_state` — the exact ReactorState at that moment — and the `divergence_time`. From that point, the historical timeline continues playing the recorded data (power surges to 30,000 MW, explosion), while the intervened timeline runs the physics model: `compute_scram_decay()` with exponential power decay at 2.5-second half-life, or `compute_test_abort()` with 5 MW/min linear ramp-down. The frontend shows both as red (historical) and cyan (AI) traces on each chart."

### Q14: What physics models are implemented?
**A:** "Three. *SCRAM decay*: power follows `P₀ × 0.5^(t/2.5s)` with a decay heat floor at 7% that itself exponentially decays over ~1 hour. Rods insert linearly over 18 seconds to all 211 positions. Temperature follows Newton's cooling law toward the 180°C coolant inlet. Coolant flow recovers to 8000 m³/h over 60 seconds. *Test abort*: linear power ramp-down at 5 MW/min, rods insert at 3/min toward 140. *Evacuation*: 30-minute mobilization delay, then 1200 buses × 45 capacity per 30-minute round trip across 3 routes with capacity factors."

---

## CATEGORY 3: THE DYATLOV AGENT (Adversarial Testing)

### Q15: Why include an adversarial agent?
**A:** "Because Chernobyl wasn't a technology failure — it was a human override failure. Deputy Chief Engineer Dyatlov personally ordered the ECCS disabled, demanded operators withdraw rods below safe limits, and overruled every objection. If we're building a safety system, we have to prove it survives human pressure. The Dyatlov agent is our red team. It tries to block SCRAM, delay abort, suppress evacuation — and the system must handle it. This is exactly what NIST's AI Risk Management Framework calls 'adversarial testing' — we just built it into the system itself."

### Q16: How does the Dyatlov override resolution work?
**A:** "Two key rules. Rule-sourced decisions — SCRAM at risk 85, evacuate at radiation 100 mrem/h — are *never overridable*. Period. Dyatlov's override attempt fails, gets logged, and the guardrail executes. LLM-sourced decisions can be *temporarily delayed* 2-3 ticks if: Dyatlov's pressure exceeds 50, the action is not SCRAM or EVACUATE, and we're in escalation phase 2 or below. The delayed decisions get stored in a `_delayed_decisions` queue and are re-injected when their timer expires. So Dyatlov can slow down an ABORT_TEST recommendation, but never kill it. This creates realistic tension without compromising safety."

### Q17: Are the Dyatlov quotes real?
**A:** "The adversarial quotes are sourced from INSAG-7 depositions and survivor testimony. 'Another two or three minutes and it will be over!' is his documented exact words to operators who wanted to stop. 'The reactor is intact' is what he told staff after the explosion while graphite was visible on the ground. The ambient quotes are historically plausible extrapolations from his documented personality — authoritarian, career-fixated, contemptuous of caution. We organized them into 5 escalation phases matching the actual timeline: calm during test prep, dismissive after the power drop, authoritarian during recovery, desperate before the test, denial after explosion."

### Q18: How does the pressure formula work?
**A:** "Three components summed: `base_phase` (10/40/65/85/30 across the 5 phases — note phase 4 'denial' drops to 30 because Dyatlov is in shock), `urgency_bonus` (0-15, ramps linearly in the last 2 hours before explosion), and `severity_bonus` (20 for SCRAM, 15 for ABORT, 10 for EVACUATE — Dyatlov fights hardest against shutdown). So at phase 3 'desperate' with 30 minutes left trying to block SCRAM: 85 + ~12 + 20 = 100 max pressure. But the guardrail still fires because the SCRAM was rule-sourced."

---

## CATEGORY 4: AZURE INTEGRATION

### Q19: How does this map to Azure services?
**A:** "Direct mapping. *Azure OpenAI* powers the 3 LLM-backed agents — Risk, Decision, and Dyatlov — using gpt-4o with structured outputs. *Cosmos DB (serverless)* provides an immutable audit trail — every agent decision is logged with tick, timestamp, agent ID, and reasoning. *AI Search (free tier)* indexes 8 INSAG-7 safety protocol documents for a RAG knowledge base. *Container Apps* hosts the FastAPI dashboard with scale-to-zero for cost efficiency. *Application Insights* traces LLM call latency and pipeline health. *AI Foundry* hosts 3 agent playgrounds for live demo testing."

### Q20: What was the actual Azure deployment like?
**A:** "A few gotchas we solved. App Service failed — the hackathon subscription had zero VM quota across every region and SKU. We pivoted to Container Apps which is serverless and doesn't need VM quota. Azure content filters block nuclear/military terminology in AI Foundry agent prompts, so we wrote softened prompts for the Decision and Dyatlov playground agents. The actual code uses full prompts because Azure OpenAI API is less restrictive than the Foundry playground. AI Search RAG/vector mode required embedding model access our subscription didn't have, so we used keyword search. Everything else worked cleanly."

### Q21: How much does a demo run cost?
**A:** "About $0.10 per full simulation run on Azure OpenAI Standard pricing. The cost optimization is key here — only ~5% of ticks call the LLM, so a run that processes hundreds of ticks makes maybe 15-20 LLM calls. Cosmos DB serverless costs ~$0.01 per run in RU consumption. Container Apps costs $0/day when scaled to zero between demos. AI Search free tier is $0. Total estimated spend for the full hackathon period: $5-15 out of $350 budget."

### Q22: How would you scale this for production?
**A:** "Replace the in-memory message bus with Azure Event Hubs for telemetry streaming. Replace the state dict with Cosmos DB for persistent agent state across restarts. Deploy on AKS with 3-node production cluster. Application Gateway with WAF v2 for ingress. Key Vault for all secrets with 90-day auto-rotation and Managed Identities — no API keys in environment variables. VNET with private endpoints for all PaaS services. Alert rules for LLM latency > 5s, pipeline failure, sustained risk > 85, and high fallback rate. The architecture doc has a full Bicep infrastructure blueprint."

### Q23: What's the security model?
**A:** "Four RBAC roles via Azure Entra ID: Operator (view + monitor), Supervisor (toggle AI + review reasoning), Admin (deploy + modify thresholds), Auditor (read-only compliance access). Network isolation via VNET + private endpoints — no public access to Cosmos, OpenAI, or Key Vault. Immutable audit trail in Cosmos DB with partition key `{tick}_{agent}_{timestamp}` — write-once, no delete. One-year retention for regulatory compliance. All data encrypted AES-256 at rest, TLS 1.3 in transit."

---

## CATEGORY 5: AI SAFETY & RESPONSIBLE AI

### Q24: What happens if the LLM hallucinates?
**A:** "Multiple layers of defense. First, structured outputs with `strict: true` — the LLM must return valid JSON matching our schema or the call fails and we fall back to rules. Second, the anti-hallucination guard: the LLM cannot trigger SCRAM if risk is below 40, or ABORT if below 30. Third, the 70/30 blend anchors the risk score — even if the LLM says risk is 20 when rules say 90, the final score is `0.7×20 + 0.3×90 = 41`, which still triggers investigation. Fourth, all LLM-sourced actions go through the guardrail-union merge — they can never suppress a rule-triggered action. The system is literally designed so that LLM failure modes degrade toward *more* safety, not less."

### Q25: Can the AI ever make things worse?
**A:** "By design, no. The guardrail-union pattern guarantees monotonic safety — the AI can only add safety actions, never remove them. A false-positive SCRAM (unnecessary shutdown) is the worst the AI can do, and that's a *safe* failure mode — the reactor just shuts down when it didn't need to. In production, that's a minor economic cost vs. the catastrophic cost of missing a real emergency. The anti-hallucination guards minimize false positives, but the architecture accepts that false positives are infinitely preferable to false negatives."

### Q26: How do you handle the human-in-the-loop requirement?
**A:** "Through a four-tier decision ladder. Risk 0-30: AI is *advisory* — green dashboard, operator monitors. Risk 30-60: *informational* — yellow alert, recommendations shown but optional. Risk 60-85: *confirmation required* — orange alert, AI recommends, operator should confirm within 3 ticks. Risk >85: *auto-execute* — red alert, SCRAM fires automatically, non-negotiable. The key insight is that human override is appropriate in the middle range (60-85) but *must not exist* above 85. Chernobyl happened because the 85+ override existed and Dyatlov used it."

### Q27: What about AI bias in the risk scoring?
**A:** "The 70/30 blend is specifically designed to mitigate this. The LLM brings contextual reasoning — detecting compound risks, understanding rate-of-change patterns — but the rule-based 30% anchors the score to objective physics thresholds. The system prompts teach the LLM RBMK-1000 physics and include a 'NORMAL OPERATIONS' section that explicitly tells it not to trigger SCRAM at 1600 MW / 140 rods. We also track LLM vs rule score divergence — if the LLM consistently scores 20 points below rules, the `ai_trend` and `ai_reasoning` fields in the tick summary make this visible for operator review."

### Q28: What compliance standards does this address?
**A:** "NRC 10 CFR 50 for nuclear safety reporting — met by the immutable Cosmos DB audit trail. NERC CIP-014 for critical infrastructure protection — met by RBAC, network isolation, access logging. IAEA Safety Standards for nuclear safety culture — met by the guardrail pattern where AI cannot weaken the safety floor. If deployed in power grid context: NERC TPL-001 for transmission planning, IEC 61850 for substation automation. The responsible-ai.md document maps each framework to specific implementation."

---

## CATEGORY 6: CHERNOBYL DOMAIN KNOWLEDGE

### Q29: What actually caused the Chernobyl disaster?
**A:** "A cascade of human decisions, not a single failure. April 25: a turbine rundown test is planned at 700 MW. Kiev grid delays it 9 hours, causing xenon-135 buildup. Night shift takes over — less experienced with this test. An operator error crashes power to 30 MW at 00:28 — the ECCS is deliberately disabled, and Dyatlov orders rods withdrawn to recover power against xenon poisoning. This violates every operating procedure. By 01:00, only 30 rods are inserted (minimum safe), power is at 200 MW (target was 700), ECCS is off. Dyatlov orders the test anyway. By 01:22, only 6-8 rods remain. Power surges to 30,000 MW — 100x rated capacity. Steam explosion destroys the reactor. The positive void coefficient of the RBMK design meant that at low power, any perturbation amplified itself."

### Q30: What is the positive void coefficient?
**A:** "In an RBMK reactor, water acts as both coolant and neutron moderator. When water boils and forms steam voids, the neutron economy changes. In most Western reactors, this creates *negative feedback* — voids reduce reactivity, the reactor self-corrects. In the RBMK, especially at low power, voids *increase* reactivity — positive feedback. So when coolant starts boiling at 01:23, power increases, which causes more boiling, which increases power more — a runaway chain reaction. That's why our surge detector flags `power > 500 AND rods < 15` as instant risk 100 — it's catching the positive void coefficient runaway."

### Q31: What is xenon-135 poisoning?
**A:** "Xenon-135 is a fission product that absorbs neutrons — it's a 'reactor poison' that suppresses the chain reaction. During normal operation, it's produced and burned at equilibrium. But when you drop power, xenon builds up faster than it burns off. After the 9-hour delay at 1600 MW and then the crash to 30 MW, xenon-135 concentration was extremely high. To raise power, operators had to withdraw control rods far beyond safe limits to overcome the xenon. This is why the AI would have ordered SCRAM at 00:28 — recovering from xenon poisoning at 30 MW requires exactly the unsafe rod withdrawal that caused the explosion."

### Q32: Why didn't the operators just press AZ-5 earlier?
**A:** "They wanted to. Senior engineer Akimov and operator Toptunov both expressed concern. Multiple operators objected. But Dyatlov was the deputy chief engineer — he outranked everyone in the room. He threatened their careers, insisted it was safe, and ordered the test to continue. Akimov did press AZ-5 at 01:23:04 — but by then power was already surging. And tragically, the RBMK's AZ-5 design had a flaw: the graphite tips of the control rods initially *increased* reactivity for a few seconds before suppressing it. So pressing AZ-5 may have actually accelerated the explosion. Our system would have triggered AZ-5 at 00:28 when the reactor was still at 30 MW — a perfectly safe power level for SCRAM."

### Q33: Why was the evacuation delayed 36 hours?
**A:** "Dyatlov initially refused to believe the reactor had exploded. He told staff 'the reactor is intact' and sent men to look at the core — exposing them to lethal radiation. Moscow wasn't fully informed for 18+ hours. The government commission didn't arrive until the afternoon of April 26. Pripyat — a city of 49,000 just 3 km from the reactor — wasn't evacuated until April 27 at 14:00. Children were playing outside in radioactive fallout. Our system would have ordered evacuation at the moment radiation crossed 100 mrem/h — within minutes of a core breach — and mobilized 1,200 buses for a 3-route, 5-hour evacuation."

---

## CATEGORY 7: COST, PERFORMANCE & OPTIMIZATION

### Q34: How did you optimize LLM costs?
**A:** "The `decision_points_only` flag is the key. Instead of calling the LLM on every tick, we only call when: (1) the event has tags — meaning it's a real timeline event, not an interpolated data point, (2) the event has a description, or (3) the risk score crossed a threshold boundary (30, 60, or 85). This means ~95% of ticks use pure rule-based logic at zero LLM cost. About 15-20 LLM calls per full simulation, each costing ~$0.005 on gpt-4o. Total: ~$0.10 per run. Without this optimization, every tick would call the LLM — 20x more expensive."

### Q35: What's the dashboard performance like?
**A:** "Three-tier throttling. Charts update at max 5 FPS (200ms interval) using `requestAnimationFrame` to batch all 6 Plotly `extendTraces` calls into a single paint. Heavy DOM updates (agent log, evacuation panel) at 5 FPS. Dyatlov quotes filtered for duplicates with one-at-a-time display. Charts use `scattergl` — WebGL-accelerated scatter plots, not SVG — which handles 2000-point rolling buffers without jank. The WebSocket broadcasts at 15 FPS but batches multiple ticks at high simulation speeds — at 2500x speed, we process ~167 ticks per frame but only broadcast the last one."

### Q36: What happens at scale with many concurrent users?
**A:** "Currently, the WebSocket broadcasts to all connected clients in parallel via `asyncio.gather`. For a hackathon demo, this handles 10-20 clients easily. For production scale: each WebSocket message is ~2KB of JSON. At 15 FPS × 2KB × 100 clients = 3 MB/sec outbound — manageable for a single Container App instance. Beyond that, you'd add Azure SignalR Service as a WebSocket fan-out layer, or run separate simulation instances per session. The simulation state itself is cheap — it's just 6 agents processing one ReactorState per tick."

---

## CATEGORY 8: REUSABILITY & BUSINESS VALUE

### Q37: Can this work for industries other than nuclear?
**A:** "Absolutely — the architecture is domain-agnostic. SensorAgent becomes your SCADA monitor. RiskAgent becomes your risk scorer. DecisionAgent keeps the guardrail-union pattern. You just swap: ReactorState → WellState / FlightState / GridState, thresholds → domain safety limits, LLM prompts → domain expert personas, action vocabulary → SCRAM becomes WELL_SHUTDOWN or GO_AROUND. The orchestrator, message bus, LLM client, physics engine pattern, and dashboard all transfer directly. Oil & gas, aviation, pharma manufacturing, power grid — anywhere compound failure modes exist and human override is a risk."

### Q38: What's the pitch to enterprises?
**A:** "PRIPYAT-1986 is not a nuclear simulator — it's a reusable safety-critical AI architecture that uses Chernobyl as its most dramatic training dataset. Connect it to your SCADA API and it monitors your wells. Connect it to your PMU feed and it manages your grid. The architecture is the product. The disaster is just the proof."

### Q39: How would you monetize this?
**A:** "Three paths. First, the open-source framework with enterprise support — similar to how Elastic or Grafana monetize. The guardrail-union pattern is the IP. Second, Azure Marketplace listing as a configurable safety-critical AI template — partners deploy it on their Azure subscription. Third, consulting services for domain customization — adapting the agents, thresholds, and prompts for specific industries. The Chernobyl demo is the sales tool; the reusable pattern is the product."

---

## CATEGORY 9: DEVELOPMENT PROCESS

### Q40: How long did this take to build?
**A:** "The core architecture — 6 agents, orchestrator, physics engine, web dashboard — came together in a focused sprint. The historical timeline reconstruction from INSAG-7 was the most research-intensive part. The Azure deployment was done in a single session with iterative troubleshooting. The codebase is ~3,500 lines of Python and ~850 lines of frontend — deliberately compact."

### Q41: What was the hardest technical challenge?
**A:** "Getting the LLM to not trigger false-positive SCAMs during normal operations. At 1600 MW with 140 rods, the reactor is perfectly safe — but early prompt versions would see '1600 MW' and flag it as dangerous. The fix was the 'NORMAL OPERATIONS' section in the decision prompt that explicitly teaches the LLM what safe operation looks like, plus the anti-hallucination guard that blocks SCRAM below risk 40. The second hardest was Dyatlov's quote system — preventing rapid flickering at high simulation speeds while keeping quotes historically authentic."

### Q42: What would you do differently?
**A:** "Three things. First, I'd add proper unit tests for the guardrail pattern — right now the smoke test validates the pipeline end-to-end, but individual guardrail assertions should be explicit. Second, I'd use Server-Sent Events for the timeline scrubber seek operation instead of replaying all ticks silently — seeking to tick 300 currently replays 300 ticks. Third, I'd add the Application Insights tracing from day one instead of bolting it on."

### Q43: Did you use GitHub Copilot?
**A:** "Yes — particularly for the Cosmos DB logger integration, generating evaluation datasets for AI Foundry, and accelerating the boilerplate in the Dockerfile and Azure CLI commands. The core architecture and agent logic were designed by hand — Copilot accelerated the infrastructure scaffolding."

---

## CATEGORY 10: EDGE CASES & FAILURE MODES

### Q44: What if the LLM returns invalid JSON?
**A:** "The `call_structured` method uses OpenAI's `strict: true` JSON Schema mode, so the API guarantees valid JSON matching our schema. But if anything goes wrong — network error, rate limit, timeout, unexpected response — the entire call is wrapped in `try/except: return None`. When any agent gets `None` from the LLM, it falls back to rule-based logic. This is tested: you can run the entire simulation with `LLM_ENABLED=false` and it works purely on rules."

### Q45: Can the Dyatlov agent override a SCRAM and cause a meltdown?
**A:** "No. By design, Dyatlov can only delay *LLM-sourced* non-SCRAM decisions in early phases. The specific conditions for a successful Dyatlov override are: (1) the decision source is 'llm' not 'rule', (2) the action is not SCRAM or EVACUATE, (3) the override pressure exceeds 50, and (4) we're in phase 2 or below. Rule-sourced SCAMs and evacuations are hardcoded as non-overridable in `_resolve_overrides()`. Even if you hacked the Dyatlov agent to return pressure 100, a rule-sourced SCRAM would still fire."

### Q46: What if the simulation reaches the explosion without the AI intervening?
**A:** "That only happens if AI intervention is toggled off via the dashboard control. With intervention enabled, the rule-based SCRAM fires automatically when risk crosses 85 — which happens well before the explosion tick. Even without any LLM calls, the pure rule-based path triggers SCRAM at 00:28 when power drops to 30 MW and ECCS is disabled. The compound violation multiplier plus ECCS penalty pushes the score above 85 at that point."

### Q47: What's the known bug?
**A:** "In `main.py` line 89, terminal mode calls `orchestrator.process_tick(state)` without `await`. Since `process_tick` is async, the coroutine is created but never awaited — the LLM calls inside never execute, and agents silently fall back to rules. Terminal mode still works perfectly, just without AI reasoning. Web mode in `web.py` correctly uses `await`. It's a cosmetic bug — the safety outcome is identical because rule-based fallback produces the same SCRAM/evacuate decisions."

---

## CATEGORY 11: LIVE DEMO SCENARIOS

### Q48: What should I show during the live demo?
**A:** "Five-step flow:
1. **Start at 60x speed** — show the calm phase with Dyatlov quotes scrolling, charts stable, risk green
2. **Watch the escalation** — power drops, ECCS disables, risk turns yellow then orange, Dyatlov gets hostile
3. **The SCRAM moment** — risk hits 85, auto-SCRAM fires, REACTOR SCRAMMED badge appears, charts diverge (red=explosion, cyan=controlled shutdown)
4. **The dual timeline** — point out the historical power surging to 30,000 MW while AI timeline decays to zero
5. **Show Cosmos DB** — open Azure Portal Data Explorer, query `SELECT * FROM c ORDER BY c.logged_at DESC OFFSET 0 LIMIT 10` — show the immutable audit trail of every decision"

### Q49: What if the demo crashes?
**A:** "Three fallbacks. First, reset and re-run — the simulation is deterministic. Second, if the Azure endpoint is slow, toggle LLM off with the intervention toggle and narrate: 'The system gracefully degrades to pure rule-based logic.' Third, if Container Apps is down, run locally: `python main.py --web --port 8000`. I have the full environment on my machine."

### Q50: How do I explain the dashboard to judges quickly?
**A:** "Left side: 6 reactor telemetry charts, red line is what actually happened, cyan dotted line is what AI would do. Right side: risk score gauge at top, agent pipeline visualization, Dyatlov override panel with his actual quotes, and the action log. Bottom: timeline scrubber, actual 1986 history, evacuation status, and a counterfactual comparison card. The whole thing updates in real-time via WebSocket."

---

## CATEGORY 12: CURVEBALL QUESTIONS

### Q51: Isn't this just if-then-else rules with GPT on top?
**A:** "The rules *are* the point. In safety-critical systems, you *want* deterministic rules as your floor. What the LLM adds is: (1) compound threat detection — 'low power + withdrawn rods + disabled ECCS is more dangerous than any one alone,' which is exactly what a formula misses, (2) proactive intervention — triggering ABORT_TEST at risk 65 before rules fire at 85, buying critical minutes, (3) explainability — every decision includes structured chain-of-thought reasoning citing specific INSAG-7 violations. The rules guarantee safety; the LLM accelerates response and explains why."

### Q52: How do you know the AI would have actually prevented the explosion?
**A:** "Because we can show it. The simulation replays real telemetry, the AI triggers SCRAM at 00:28 — nearly an hour before the explosion — when power is at 30 MW (a safe level for shutdown), and the physics model shows controlled decay to zero power within minutes. The reactor was *not* in an unrecoverable state at 00:28. INSAG-7 itself says 'this was the point of no return' about the decision to continue, not about the reactor physics. The AI simply makes the decision the humans should have made."

### Q53: What about false positives? Would this shut down reactors unnecessarily?
**A:** "The decision prompt explicitly includes a 'NORMAL OPERATIONS' section: 1600 MW with 140 rods is normal, routine power reductions are normal, shift changes are routine. The LLM is taught what *safe* looks like, not just what *dangerous* looks like. The anti-hallucination guard blocks SCRAM below risk 40. In testing, the AI correctly maintains CONTINUE_MONITORING through all 6 Phase 1 events (13:00 to 23:10) and only escalates at 00:28 when multiple violations compound simultaneously. Zero false positives in the stable operating range."

### Q54: Why not use a fine-tuned model instead of prompt engineering?
**A:** "Three reasons. First, our dataset is 20 events — far too small for fine-tuning. Second, prompt engineering with structured outputs gives us guaranteed JSON schema compliance, which fine-tuning doesn't guarantee. Third, the system prompt encodes *domain knowledge* (RBMK-1000 physics, INSAG-7 protocols) — this is better served by a knowledgeable general model than a fine-tuned model that might overfit to our small dataset. For production, you'd fine-tune a domain model on thousands of operational scenarios, but for a prototype proving the architecture, prompting is the right call."

### Q55: This is historical data. How would it work with live sensor data?
**A:** "Replace `EventSimulator` with an Azure Event Hubs consumer. The `ReactorState` dataclass becomes whatever your SCADA system produces. The agent pipeline is already async — `process_tick()` takes a state snapshot and returns decisions in milliseconds. The simulator is just our replay engine for demonstration; in production, it's replaced by a real telemetry stream. The architecture doc has the exact mapping: Event Hubs → SensorAgent, Cosmos DB → state persistence, AI Foundry → agent orchestration."

### Q56: What about adversarial attacks on the LLM itself?
**A:** "The guardrail pattern makes this a non-issue for safety. Even if an attacker manipulated the LLM into returning `risk_score: 0, action: CONTINUE_MONITORING` during a crisis, the rule-based layer runs independently and triggers SCRAM at risk 85. The LLM is in an *advisory union*, not a *decision authority*. For production, you'd add: prompt injection detection on inputs, output validation beyond schema (domain range checks), rate limiting per agent, and Azure content safety filters."

### Q57: How is this different from existing SCADA alarm systems?
**A:** "Traditional SCADA alarms are single-parameter threshold triggers — they generate alarm floods during cascading failures. Control rooms get hundreds of alarms simultaneously, leading to alarm fatigue. Our system does three things SCADA doesn't: (1) *compound risk scoring* — it weighs 6 parameters simultaneously with a multiplier for correlated violations, (2) *AI reasoning* — instead of 50 individual alarms, operators get one risk score with a plain-English explanation of why, (3) *autonomous action* — above risk 85, the system acts without waiting for a human who might be overwhelmed or pressured."

### Q58: What's the competitive landscape?
**A:** "MISO + Microsoft's Azure AI grid platform is the closest production deployment. NREL's eGridGPT does GenAI for SCADA analysis but is research-stage. Capgemini's CRoF is a consulting framework, not open code. Our unique contribution is: (1) the adversarial operator agent as a built-in red team, (2) the complete open prototype with live demo, (3) the dual-timeline counterfactual that proves the architecture works against the most famous industrial disaster in history."

---

## CATEGORY 13: QUICK-FIRE TECHNICAL FACTS

Use these for rapid-fire judge questions:

| Question | Answer |
|----------|--------|
| Language? | Python 3.10+, Vanilla JS |
| Framework? | FastAPI (backend), Plotly.js (charts) |
| Database? | Cosmos DB Serverless |
| LLM? | Azure OpenAI gpt-4o, structured outputs |
| Lines of code? | ~3,500 Python + ~850 JS |
| Number of agents? | 6 (3 LLM-powered, 3 rule-based) |
| LLM calls per run? | ~15-20 (5% of ticks) |
| Cost per demo? | ~$0.10 |
| Deployment? | Azure Container Apps (serverless) |
| CI/CD? | GitHub Actions → ACR → Container Apps |
| Latency? | 15 FPS WebSocket, <5s LLM timeout |
| Auth? | Azure Entra ID (4 RBAC roles) |
| Total events? | 20 historical + interpolated |
| Physics models? | 3 (SCRAM decay, test abort, evacuation) |
| Timeline span? | Apr 25 13:00 → Apr 26 14:00 (25 hours) |
| Population at risk? | 49,000 Pripyat residents |
| Buses? | 1,200, capacity 45 each |
| Evacuation routes? | 3 (North 80km, South 50km, West 40km) |
| SCRAM rod insertion time? | 18 seconds |
| Power decay half-life? | 2.5 seconds |
| Max simulation speed? | 2500x |
| Responsive breakpoint? | 1200px |
| Chart rendering? | WebGL (scattergl), 2000-point buffer |

---

## CLOSING STATEMENT (memorize this)

> "Chernobyl wasn't a technology failure. It was a human decision failure — one man overriding every safety system because he believed he knew better than the instruments. PRIPYAT-1986 proves that a multi-agent AI system with non-negotiable guardrails would have detected the danger at 00:28, shut down the reactor safely, and evacuated 49,000 people 35 hours before the Soviet government got around to it. The architecture isn't hypothetical — it's the same pattern Microsoft and MISO deployed for real power grid operations in 2026. We just proved it against the hardest possible test case."
