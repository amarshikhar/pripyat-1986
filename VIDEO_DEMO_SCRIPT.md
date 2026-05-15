# PRIPYAT-1986 — Video Demo Script (Recorded, 5–10 min)

> **This is a pre-recorded demo video — no live judges.** You can do retakes, cut between takes, and pre-stage moments. Use that to your advantage.

---

## 🎥 RECORDING SETUP

- **Screen recorder**: OBS Studio or Windows Game Bar (`Win+G`)
- **Resolution**: 1920×1080 minimum. Record at native res.
- **Audio**: Use a decent mic. Quiet room. No fan noise.
- **Webcam** (optional but recommended): Small picture-in-picture in bottom-left corner during narration. Full screen during the hook and close.
- **Browser**: Dashboard at `localhost:8000`, fullscreen (`F11`). Clear all bookmarks bar / tabs clutter.
- **Second tab**: Azure Portal with Cosmos DB Data Explorer pre-loaded and a query ready to run.
- **Simulation pre-loaded**: Speed at **60x**, intervention toggle **ON**, paused at the start.
- **Close all notifications**, Slack, Teams, email — nothing pops up mid-recording.

### Recording Strategy
Record each phase as a **separate take**. Edit them together. This lets you:
- Nail the voiceover without time pressure
- Cut dead air while waiting for the simulation to reach key moments
- Speed up the calm phase in post (2x playback for ~15 seconds of calm charts)
- Slow down / zoom into the SCRAM moment

---

## 🎬 PHASE 0 — TITLE CARD + HOOK (0:00 – 0:50)

> **[SCREEN: Black background or a simple title slide]**
> `PRIPYAT-1986`
> `Multi-Agent AI Crisis Response System`
> `Azure AI Hackathon — Track A`
> Hold for 3 seconds, then cut to webcam or dashboard.

**VOICEOVER:**

"On April 26, 1986, Deputy Chief Engineer Anatoly Dyatlov overrode every safety system in Chernobyl Reactor 4. He disabled emergency cooling. He pulled control rods below minimum safe limits. He ignored every operator who tried to stop him.

The explosion killed 31 people immediately and caused an estimated 4,000 cancer deaths. It wasn't a technology failure — it was a **human override failure**.

PRIPYAT-1986 answers one question: what if AI with proper guardrails had been in that control room?

Let me show you."

> **[CUT TO: Dashboard, fullscreen. Simulation paused at start.]**

---

## 🎬 PHASE 1 — THE DASHBOARD & AGENTS (0:50 – 2:15)

> **[SCREEN: Dashboard visible. Move your mouse slowly to highlight areas as you describe them.]**

**VOICEOVER (click Play at "Let's start the simulation"):**

"This is our real-time control room dashboard. Six autonomous AI agents are monitoring Chernobyl Reactor 4, processing the actual reconstructed timeline from the INSAG-7 report — the official post-disaster investigation.

Let me walk you through what you're seeing.

On the left — six live charts tracking reactor dimensions: power output, control rod position, coolant flow, steam pressure, temperature, and radiation. These are real RBMK-1000 parameters.

On the right — the risk gauge. This is scored 0 to 100 by our **RiskAgent**, which uses a 70% AI, 30% rule-based blend. Azure OpenAI gpt-4o provides contextual reasoning — detecting compound threats, understanding rate-of-change — while the rule-based component anchors the score to hard physics thresholds.

Below that — the agent action log, showing every decision in real time. And this panel here is our **Dyatlov Agent** — an adversarial AI that models the real deputy chief engineer, using quotes sourced from the official Soviet inquiry.

Let's start the simulation. Speed is 60x — one simulated hour passes every real minute."

> **[Click Play. Let it run for ~10 seconds showing calm phase. Charts stable, risk green (~15-25).]**

"Everything's nominal. Reactor at 1600 megawatts, 140 control rods in, emergency cooling active. Risk is green. Dyatlov is calm — *'The test has been delayed long enough. We run it tonight.'*

That's about to change."

> **[TIP: In post-editing, you can speed up the next 20-30 seconds of calm phase at 2x to save time. Add a subtle fast-forward indicator.]**

---

## 🎬 PHASE 2 — THE ESCALATION (2:15 – 3:45)

> **[SCREEN: Dashboard running. Move mouse to highlight risk gauge, charts, Dyatlov quotes as they change.]**

**VOICEOVER:**

"The Kiev power grid demanded a 9-hour delay. Xenon-135 — a reactor poison — built up. The night shift took over. Now watch..."

> **[Power drops. Risk starts climbing.]**

"An operator crashes power to 30 megawatts. Our SensorAgent immediately flags the anomaly. Risk crosses 30 — yellow alert."

> **[Mouse hovers over risk gauge as it turns yellow/orange.]**

"Now Dyatlov orders the ECCS — Emergency Core Cooling System — disabled. Watch the risk jump."

> **[ECCS disables. Risk spikes. Dyatlov quotes turn hostile.]**

"ECCS off. That's a hard safety violation. Dyatlov is escalating — *'The instruments are unreliable at low power. Ignore them.'* That's from his actual deposition testimony.

Risk is pushing through 60... 70... Our compound violation multiplier is kicking in — multiple safety parameters are degrading at the same time. And look at the agent log..."

> **[Mouse moves to agent action log.]**

"The DecisionAgent — powered by Azure OpenAI — is already recommending **ABORT_TEST** at risk 65. The AI is being *proactive*, stepping in before the hard safety rules would fire.

This is where our core innovation comes in."

---

## 🎬 PHASE 3 — THE GUARDRAIL-UNION PATTERN (3:45 – 5:15)

> **[SCREEN: Dashboard still running in background, risk climbing. You can pause the sim briefly here if needed to explain without rushing, then resume.]**

**VOICEOVER:**

"The key innovation in PRIPYAT-1986 is what we call the **Guardrail-Union Pattern**. Here's how it works.

**Step one**: hard rules run first. Always. Non-negotiable. If risk exceeds 85 — auto-SCRAM. Emergency shutdown. If radiation exceeds 100 millirem per hour — auto-evacuate. These form the **safety floor**. No AI, no human, no one can override them.

**Step two**: the LLM runs second. It can recommend actions *earlier* than rules would trigger — like the ABORT_TEST it just recommended at risk 65, a full 20 points before the hard rule fires.

**Step three**: the final action set is the **union** of both. The LLM can *add* safety actions. It can **never remove** a rule-triggered one.

What does this mean in practice? If the LLM hallucinates — rules still fire. If the LLM goes down entirely — every agent falls back to pure rule-based logic. The system is literally **safer without AI than with compromised AI**.

And there's an anti-hallucination guard — the LLM cannot trigger a SCRAM if risk is below 40. No false positives.

Now, let's see what happens when Dyatlov tries to override all of this."

> **[Resume simulation if paused.]**

---

## 🎬 PHASE 4 — THE SCRAM MOMENT (5:15 – 7:00)

> **[SCREEN: This is the money shot. Risk hits 85. SCRAM fires. Charts diverge. Record this cleanly — do a retake if needed.]**

**VOICEOVER (as risk approaches 85):**

"Risk is at 80... 83... 85 —"

> **[SCRAM fires. "REACTOR SCRAMMED" badge appears. Dual timeline begins — red vs cyan.]**

"**Auto-SCRAM.** The hard guardrail just fired. Emergency shutdown, non-negotiable.

Now watch the Dyatlov panel."

> **[Mouse on Dyatlov quotes — desperate phase.]**

"*'Another two or three minutes and it will be over!'* — those are Dyatlov's **exact documented words** to the operators who wanted to stop. He's at Phase 3, maximum pressure, fighting with everything to block the shutdown.

**It doesn't matter.** The SCRAM was rule-sourced. Dyatlov's override attempt is logged, audited — and rejected. The guardrail executes regardless.

Now — this is the part I want you to focus on."

> **[Mouse traces the diverging chart lines. Pause here for 3 seconds of silence to let the visual land.]**

"Look at the dual timeline.

The **red line** — that's what actually happened in 1986. Power surges to 30,000 megawatts. A hundred times rated capacity. Steam explosion. Reactor destroyed. Graphite burning. Lethal radiation.

The **cyan line** — that's the AI's intervention. Exponential power decay. 2.5-second half-life. Control rods inserting. Reactor cooling down safely.

Same starting conditions. Same human pressure. Same Dyatlov. **Different outcome.** Because the safety floor was non-negotiable."

> **[Hold on the diverged charts for 3-4 seconds. Let the image breathe.]**

---

## 🎬 PHASE 5 — AZURE STACK & REUSABILITY (7:00 – 8:30)

> **[CUT TO: Azure Portal — Cosmos DB Data Explorer. Run the pre-loaded query to show audit records.]**

**VOICEOVER:**

"Every agent decision is persisted to **Azure Cosmos DB** — tick number, timestamp, agent ID, action taken, full reasoning chain. Immutable. Write-once. One-year retention. This is your regulatory compliance audit trail."

> **[Show a few rows of the query result — point out agent names, actions, timestamps.]**

> **[CUT BACK TO: Dashboard.]**

"Here's the full Azure stack. **Azure OpenAI** gpt-4o powers the three LLM-backed agents — Risk, Decision, and Dyatlov — with structured JSON outputs. **Cosmos DB serverless** for the audit trail. **AI Search** indexes INSAG-7 safety protocols for RAG retrieval. **Container Apps** hosts the dashboard serverless — scales to zero, costs nothing between runs. **Application Insights** traces every LLM call latency.

And the cost story — only **5% of ticks** actually call the LLM. We invoke it only at real decision points: when events carry tags, when descriptions change, when risk crosses a threshold boundary. The other 95% is pure rule-based at zero LLM cost. A full simulation run costs **ten cents** on Azure."

> **[Brief pause. Then shift tone — this is the business case.]**

"But here's the important part. **This is not a nuclear simulator.** This is a reusable safety-critical AI architecture.

Swap `ReactorState` for `WellState` and it monitors oil wells. Swap it for `GridState` and it manages power grids. The orchestrator, the guardrail-union pattern, the adversarial testing, the audit trail, the dashboard — they all transfer directly.

And this isn't theoretical. Microsoft and MISO launched exactly this pattern on Azure AI Foundry in January 2026 — managing electricity for **45 million people** across 15 US states. Capgemini presented their Control Room of the Future at CIGRE 2025 with the same three-layer architecture.

We proved the pattern works — using the most dramatic dataset in industrial history."

---

## 🎬 PHASE 6 — THE CLOSE (8:30 – 9:30)

> **[CUT TO: Dashboard showing the fully diverged dual timeline. Or webcam full-frame for the final delivery.]**

**VOICEOVER:**

"I'll leave you with three numbers.

**35 hours.** That's how long 49,000 people in Pripyat — including children playing outside in radioactive fallout — waited for evacuation. Our system orders it within minutes of a core breach.

**Six agents, zero single points of failure.** If any LLM call fails, that agent falls back to rules. The system degrades toward *more* safety, not less.

**Ten cents per run.** Six agents, hundreds of ticks, LLM reasoning, physics models, an immutable audit trail — a dime on Azure.

PRIPYAT-1986 is the Control Room of the Future, proven against the worst industrial disaster in history.

The architecture is the product. The disaster is just the proof."

> **[Hold for 2 seconds. Then cut to end card.]**

> **[SCREEN: End title card — black background or dashboard freeze-frame]**
> `PRIPYAT-1986`
> `github.com/[your-repo]`
> `Built on Azure AI — Track A`
> Hold for 4 seconds. End recording.

---

## ✂️ POST-PRODUCTION TIPS

### Editing Cuts
| Where | What to do |
|-------|------------|
| Calm phase (Phase 1) | Speed up 15-20 sec of stable charts to **2x** with a subtle ⏩ overlay |
| Between Phase 2 → 3 | If risk climbs slowly, cut forward to risk ~60. Nobody needs to watch a gauge creep. |
| SCRAM moment (Phase 4) | **Do NOT speed up.** Play at real-time. This is the payoff. |
| Azure Portal (Phase 5) | Keep this to **30 seconds max** on screen. Just enough to show the audit rows. |

### Audio
- Record voiceover and screen separately if possible — lets you re-record narration without re-running the sim.
- If recording live (voice + screen together), do Phase 4 last after you've warmed up — it needs the cleanest delivery.
- Add subtle background music (low, ambient, tension-building) if you have time. Remove before the SCRAM moment for dramatic silence.

### Zoom / Highlight
- Use OBS zoom plugin or edit-time crop to **zoom into the risk gauge** when it crosses 85.
- **Zoom into the dual timeline divergence** — red vs cyan — for 3-4 seconds. This single visual wins the video.
- Highlight Dyatlov's quotes with a quick zoom when you mention them.

### Captions
- Add **burned-in captions** for key technical terms: "Guardrail-Union Pattern", "Auto-SCRAM", "70% AI / 30% Rules". Viewers may watch on mute initially.

---

## ⏱️ TIMING CHEAT SHEET

| Phase | Time | Content |
|-------|------|---------|
| 0 — Title + Hook | 0:00 – 0:50 | Title card. Chernobyl story. "Let me show you." |
| 1 — Dashboard Tour | 0:50 – 2:15 | Press play. Explain 6 agents. Calm phase running. |
| 2 — Escalation | 2:15 – 3:45 | Power drop, ECCS off, risk climbs, Dyatlov hostile. |
| 3 — Innovation | 3:45 – 5:15 | Guardrail-union pattern explained. Core IP. |
| 4 — SCRAM | 5:15 – 7:00 | Auto-SCRAM fires. Dyatlov blocked. Dual timeline diverges. **Hero moment.** |
| 5 — Azure + Business | 7:00 – 8:30 | Cosmos audit, cost, MISO/Capgemini, reusability. |
| 6 — Close + End Card | 8:30 – 9:30 | Three numbers. Soundbite. End card. |

> **Total: ~9:30** — within the 10-minute cap with room for editing.

---

## 🔁 RECORDING ORDER (Recommended)

Don't record in chronological order. Record in order of difficulty:

1. **Phase 5 (Azure Portal)** — Easiest. Just show Cosmos DB and narrate. Good warm-up.
2. **Phase 1 (Dashboard Tour)** — Easy. Calm charts, explaining the layout.
3. **Phase 2 (Escalation)** — Medium. Need to time narration with rising risk.
4. **Phase 3 (Innovation)** — Medium. Pure narration. Can pause the sim.
5. **Phase 0 (Hook)** — Hard. Needs to be compelling. Record after warm-up.
6. **Phase 4 (SCRAM)** — Hardest. The climax. Do this when you're in the zone.
7. **Phase 6 (Close)** — Hard. Final impression. Record right after Phase 4 while energy is up.

---

## 🛡️ IF THINGS GO WRONG

| Problem | Fix |
|---------|-----|
| LLM calls slow/failing | Toggle intervention OFF. Narrate: *"Watch — the system gracefully degrades to pure rule-based logic. Same SCRAM. Same evacuation. That's the design."* This actually **helps** your demo. |
| Simulation doesn't reach SCRAM in time | Pre-run once, note the tick count. Use the timeline scrubber to **seek** to ~2 minutes before SCRAM when paused. Start recording from there for Phase 4. |
| Charts jank at 60x | Drop to 30x. Add a text overlay in editing: *"Simulation running at 30x real-time"* |
| Dashboard won't load | Run locally: `python main.py --web --port 8000`. All self-contained. |
| Azure Portal query fails | Screenshot the Cosmos DB results beforehand. Paste the screenshot in editing. |
| Your voice cracks/you stutter | **It's a recording. Do another take.** That's the whole advantage. |

---

## 💡 VIDEO-SPECIFIC TIPS

1. **First 15 seconds decide if people keep watching.** Open with Dyatlov's story, not "Hi, my name is..." — no introductions until after the hook lands.
2. **Move your mouse deliberately.** In a video, random cursor movement is distracting. Point at what you're talking about, then park the cursor.
3. **The dual timeline divergence is your thumbnail.** If they let you pick a thumbnail, screenshot the red-vs-cyan divergence moment. If not, make sure it's visually prominent.
4. **Don't narrate what's obvious on screen.** Don't say "as you can see, the chart is going up." Say *why* it matters: "Power is surging — this is the positive void coefficient, the design flaw that made the RBMK lethal."
5. **Silence is powerful.** After the SCRAM fires and the timelines diverge, give 3 seconds of silence. In a video, silence = dramatic weight.
6. **Say "ten cents per run" twice.** Once in Phase 5, once in the close. Cost sticks.
7. **End clean.** Don't trail off with "yeah, so that's basically it." End on the soundbite: *"The architecture is the product. The disaster is just the proof."* Then stop talking. Cut to end card.
