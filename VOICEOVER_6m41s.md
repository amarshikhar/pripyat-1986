# PRIPYAT-1986 — Voiceover Script (6:41)

> **Read at 130–140 words/minute. Each section has a word count and estimated time.**
> Cue markers: `[ACTION]` = what to do on screen. `[PAUSE]` = silence for drama.

---

## 0:00 – 0:50 | HOOK (≈130 words)

`[SCREEN: Title card or black screen for first 3 seconds]`

"On April 26th, 1986 — Deputy Chief Engineer Anatoly Dyatlov overrode every safety system in Chernobyl Reactor 4.

He disabled emergency cooling.
He pulled control rods below minimum safe limits.
He ignored every operator who tried to stop him.

The explosion killed 31 people immediately, caused an estimated 4,000 cancer deaths, and contaminated 150,000 square kilometres.

It wasn't a technology failure.
It was a **human override failure**.

The safety systems existed. Emergency shutdown existed. Every procedure existed. But one man with authority could override all of it.

PRIPYAT-1986 asks one question: what if he couldn't?

We built a six-agent AI system where safety decisions are non-negotiable. No human — no matter how senior — can override a guardrail once triggered.

Let me show you."

`[CUT TO: Dashboard, fullscreen, paused at simulation start]`

---

## 0:50 – 2:15 | DASHBOARD TOUR (≈195 words)

`[SCREEN: Dashboard. Move mouse slowly to each section as you name it.]`

"This is our real-time control room dashboard. Six autonomous AI agents are monitoring Chernobyl Reactor 4 — processing the actual reconstructed timeline from the INSAG-7 report, the official Soviet post-disaster investigation.

On the left — six live charts: power output, control rods, coolant flow, temperature, radiation, and risk. Two lines per chart — **red** is the historical record, **blue** is what our AI does differently. These are driven by real RBMK-1000 reactor physics equations.

On the right — the risk gauge, scored zero to one hundred. Two independent scores computed every tick: a rule-based floor from hard physics thresholds, and an LLM assessment from Azure OpenAI GPT-4o. The system always takes the **maximum** of the two. AI can only raise risk above what rules calculate — never lower it. That's our core safety guarantee.

Below that — the agent pipeline: Sensor, Risk, Decision, Evacuation, Communications. Five agents. Deterministic order. Every tick.

And down here — our **Dyatlov Agent**. An adversarial AI modelling the real deputy chief engineer, using quotes sourced directly from Soviet inquiry transcripts."

`[Click Play. Simulation starts. Let it run ~8 seconds showing calm charts.]`

"Everything's nominal. Reactor at 1,600 megawatts. Risk is green — eleven out of a hundred. That's about to change."

---

## 2:15 – 3:45 | ESCALATION (≈190 words)

`[SCREEN: Dashboard running. Risk starts climbing. Point to relevant panels.]`

"It's midnight. The Kiev grid demanded a nine-hour delay. Xenon-135 — a reactor poison — has been building up in the core. The night shift is on. The test is nine hours overdue.

An operator crashes power. Watch it fall — 1,600 megawatts... 500... 270.

`[PAUSE — 2 seconds as power drops]`

Our Sensor Agent fires a warning immediately. Rule-based risk at fourteen — still in yellow. The rules see decline but nothing alarming yet.

Then power hits 180 megawatts. The LLM fires for the first time. Risk jumps to forty — the AI already sees the instability from the positive void coefficient.

Power keeps falling. 120... 90... 30 megawatts.

Now Dyatlov orders the ECCS disabled — Emergency Core Cooling System. The last safety barrier.

`[Mouse hovers on Dyatlov panel as quote appears]`

Watch the Dyatlov panel: *'The instruments are unreliable at low power. Ignore them.'* That's from his actual deposition testimony.

Risk is climbing through 60... 70. The agent log is flooding. Azure OpenAI is now recommending **ABORT TEST** — the AI is stepping in 20 minutes before hard rules alone would fire.

This is where the architecture matters."

---

## 3:45 – 5:15 | THE GUARDRAIL-UNION PATTERN (≈180 words)

`[SCREEN: Dashboard still running. You can pause the sim briefly here if needed.]`

"The key innovation is what we call the **Guardrail-Union Pattern**.

Step one: hard rules run first. Always. Non-negotiable. If risk exceeds 85 — auto-SCRAM, emergency shutdown. If ECCS is disabled *and* power is critical — auto-SCRAM. These are the safety floor. No AI, no human, no one overrides them.

Step two: the LLM runs second. It can recommend actions *earlier* than rules would trigger — like the ABORT TEST it just issued at risk 65, a full 20 points before the hard rule fires.

Step three: the final action is the **union** of both. The LLM can add safety actions. It can never remove a rule-triggered one.

What does this mean in practice? If the LLM hallucinates — rules still fire. If the LLM goes offline entirely — every agent falls back to pure rule logic. The system is **safer without AI** than with compromised AI. It degrades toward safety, not away from it.

Now watch what happens when Dyatlov tries to override all of this."

`[Resume simulation if paused]`

---

## 5:15 – 6:41 | THE SCRAM (≈175 words)

`[SCREEN: Risk gauge climbing — 70... 80... 83... This is the money shot. Don't rush it.]`

"Risk is at 70... 80...

`[PAUSE — 3 seconds as risk climbs to 85]`

83... 85 —"

`[SCRAM badge fires. "REACTOR SCRAMMED" appears. Dual timeline begins — red vs cyan]`

"**Auto-SCRAM.** The hard guardrail just fired. Emergency shutdown. Non-negotiable.

`[Mouse to Dyatlov panel — desperate phase quotes]`

Look at Dyatlov — Phase 4, maximum pressure: *'Another two or three minutes and it will be over!'* — those are his exact documented words. He's trying everything.

**It doesn't matter.** The guardrail was rule-sourced. His override attempt is logged, audited — and rejected.

`[Mouse traces the diverging chart lines. PAUSE — 3 full seconds of silence here.]`

Now look at the dual timeline.

The **red line** — that's 1986. Power surges to 30,000 megawatts. Steam explosion. Reactor core destroyed. Lethal radiation across Europe.

The **blue line** — that's the AI. Exponential power decay. Control rods inserting. Reactor cooling down. Everyone goes home.

Same reactor. Same night. Same Dyatlov.

**Different outcome.**

Because the safety floor was non-negotiable.

The architecture is the product. The disaster is just the proof."

`[HOLD on diverged charts — 3 seconds of silence. End recording.]`

---

## ⏱ TIMING BREAKDOWN

| Section | Time | Words | Key screen action |
|---------|------|-------|-------------------|
| Hook | 0:00 – 0:50 | ~130 | Title card → Dashboard |
| Dashboard Tour | 0:50 – 2:15 | ~195 | Mouse traces panels. Hit Play. |
| Escalation | 2:15 – 3:45 | ~190 | Power drops. LLM fires. Dyatlov hostile. |
| Guardrail-Union | 3:45 – 5:15 | ~180 | Can pause sim. Core architecture. |
| SCRAM | 5:15 – 6:41 | ~175 | Risk hits 85. Timelines diverge. |

**Total: ~870 words at 130 wpm = ~6:41**

---

## DELIVERY NOTES

1. **Slow down for the power numbers.** "1,600… 500… 270… 180…" — let each land.
2. **The three lines before SCRAM** ("83... 85 —") deserve silence between each number. Don't rush.
3. **3 seconds of silence after the dual timeline diverges.** In a recording, silence = weight. Trust it.
4. **"Different outcome."** — two-word sentence, full stop. Pause before and after.
5. **Closing line is flat and final.** No rise in your voice. State it like it's already fact.
6. **Dyatlov quotes**: lower your pace slightly, small shift in register — but don't do an accent. Let the words carry it.
7. If the LLM call latency shows on screen during escalation — name it: *"You can see real latency here — this is hitting Azure OpenAI live."* Turns a potential weakness into proof of authenticity.
