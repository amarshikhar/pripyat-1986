# PRIPYAT-1986 — FINAL VOICEOVER (6:41)
# Read at 130 wpm. Pauses marked explicitly. Record in one take if possible.
# Timestamps match your actual recording.

---

## 0:00 – 0:15 | HOOK (over paused dashboard)

"April 26th, 1986. Chernobyl Reactor 4.
One man — Deputy Chief Engineer Dyatlov — overrode every safety system
and triggered the worst nuclear disaster in history.
What if AI had been in that control room?"

---

## 0:15 – 1:00 | DASHBOARD TOUR (paused then simulation starts)

"This is PRIPYAT-1986. Six autonomous AI agents
monitoring the exact reconstructed Chernobyl timeline
from the INSAG-7 report — the official Soviet post-disaster investigation.

Left side: six real-time charts — power, control rods, coolant flow,
temperature, steam pressure, radiation.
Two lines on each chart — red is what actually happened in 1986,
cyan is what our AI prevents.

Right side: risk gauge — zero to a hundred.
Below that — the agent pipeline: Sensor, Risk, Decision, Evacuation, Communications.
And the Dyatlov Agent — an adversarial AI using his exact documented quotes
from Soviet inquiry transcripts.

Let's run it."

---

## 1:00 – 1:18 | ESCALATION (simulation running, risk climbing toward SCRAM)

"April 26th, midnight. The test is nine hours overdue.
Power dropping — 1,500 megawatts... 700... 330.
Xenon-135 poisoning the core. Risk climbing.
The agent pipeline firing every single tick."

---

## 1:18 – 1:20 | [PAUSE 2 SECONDS — let SCRAM badge flash]

---

## 1:20 – 2:00 | SCRAM + DIVERGING CHARTS (risk 62, red spike vs cyan flat)

"REACTOR SCRAMMED. The hard guardrail fired.

Look at the charts.
Red line — 1986.
Power surges to 30,000 megawatts. Temperature hits 4,000 degrees.
Steam explosion. Reactor destroyed.

Cyan line — AI intervention.
Exponential decay. Controlled shutdown. Everyone goes home.

Same reactor. Same night. Same Dyatlov.
Different outcome.
Because the safety floor was non-negotiable.

Watch the Dyatlov panel — every override attempt:
logged, audited, rejected."

---

## 2:00 – 2:45 | EVACUATION ORDERED (risk 96, Dyatlov desperate)

"Risk at 96 — EMERGENCY. Evacuation ordered.

The Evacuation Agent mobilizes 1,200 buses for 49,000 residents.
Three routes. 30-kilometre exclusion zone.

In 1986, people waited 35 hours for evacuation —
including children playing outside in radioactive fallout.
Our system ordered it within minutes of the core breach.

Dyatlov is at desperate phase — his exact words from Soviet testimony:
'Another two or three minutes and it will be over.'

It doesn't matter. The system already acted. He cannot stop it."

---

## 2:45 – 2:48 | [PAUSE 3 SECONDS — let the full divergence sink in, risk 99]

---

## 2:48 – 3:15 | ARCHITECTURE EXPLAINED (risk 99, all three badges lit)

"This is the Guardrail-Union Pattern — our core architecture.

Two independent risk scores every tick:
rule-based floor from hard physics thresholds,
LLM assessment from Azure OpenAI GPT-4o.

Final score is always the maximum of both.
AI can only raise risk — never lower it.

If the LLM hallucinates — rules still fire.
If the LLM goes down entirely —
every agent falls back to pure rule logic.
The system degrades toward safety. Not away from it."

---

## 3:15 – 3:50 | MANUAL MODE INTRO (risk 16, stable, sliders visible)

"Now the real test.

I'm in Manual Control.
Direct access to the reactor through real physics equations.
Control rods. Coolant flow. Emergency cooling system.

Risk at 16. Everything green. Reactor completely healthy.

I'm going to try to cause a meltdown."

---

## 3:50 – 4:28 | PULLING RODS (risk climbing, 58 WARNING, LLM calls firing)

"Pulling rods out.
Power rising — 1,000 megawatts... 2,000... 2,500.
Temperature climbing — 400... 500... 600 degrees.

Watch the risk gauge — yellow. WARNING. Risk at 58.

The RiskAgent is calling Azure OpenAI live right now —
you can see the LLM calls ticking up on the right.
That latency is real. This is hitting Azure production.

Agent log flooding. Sensor detecting. Risk scoring. Decision evaluating.
Every tick."

---

## 4:28 – 4:30 | [PAUSE 2 SECONDS — let SCRAM fire]

---

## 4:30 – 5:10 | SCRAM IN MANUAL (reactor scrammed, power falling, user fights it)

"REACTOR SCRAMMED. Automatic.

I didn't press anything.

Power dropping — 3,000... 2,000... 500 megawatts.
Temperature falling. Radiation spiked — AI is containing it.

Now watch — I'm still moving the sliders.
Yanking them. Trying to override it.

Nothing happens.
The AI took over.
Rods inserting. Power decaying. Reactor shutting down safely.

I. Cannot. Stop. It.

That is the design."

---

## 5:10 – 6:05 | RECOVERY + ARCHITECTURE CLOSE (risk back to 13, NORMAL)

"Risk at 20... 15... 13. Normal. Reactor safe.
Despite everything I just did.

In 1986, Dyatlov overrode the safety systems.
In our architecture — that is architecturally impossible.

Here's how it works:

Rules run first. Deterministic. Non-negotiable.
Risk exceeds 85 — auto-SCRAM.
ECCS disabled at critical power — auto-SCRAM.
No human, no AI, no one overrides this.

LLM runs second.
It catches compound threats that rules alone miss.
It can act earlier — before the hard rules would fire.

Final action is always the union of both.
AI can add safety actions. It can never remove a rule-triggered one.

This is what just happened — twice."

---

## 6:05 – 6:41 | CLOSE (audit log visible, 295 entries)

"Three numbers.

35 hours — how long 49,000 people waited for evacuation in 1986.
Our system: minutes.

Six agents. Zero single points of failure.

Ten cents per full simulation run on Azure.

PRIPYAT-1986 is the Control Room of the Future —
proven against the worst industrial disaster in history.

The architecture is the product.
The disaster is just the proof."

---

# RECORDING TIPS

1. **Don't rush the SCRAM moments** — at 1:18 and 4:28, say the line just BEFORE the badge appears, then pause.
2. **"I. Cannot. Stop. It."** — one beat per word. Slowest line in the script.
3. **"The disaster is just the proof."** — flat, final, no upward inflection. Then stop talking.
4. **Pauses are written in** — respect them. 3 seconds of silence after risk-99 divergence is more powerful than words.
5. **LLM latency on screen** — if it shows 7000ms+ latency during manual mode, use it: "That latency is real. This is hitting Azure production." Already written in.
6. **Total word count: ~820 words at 130 wpm = 6:18** — gives you ~23 seconds of breathing room for natural pauses.
