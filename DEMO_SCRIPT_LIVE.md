# PRIPYAT-1986 — Live Demo Script (~7:15)
# Drive the dashboard. Say this. Win.

---

## INTRO (0:00 – 0:45)
*Dashboard paused on screen behind you*

"Hello — we are **WattAgents**.

Everyone is building agentic AI.
Chatbots. Productivity tools. Assistants.

We asked a different question:
what's the **critical missing architecture** —
the one that safeguards our most important infrastructure?

Chernobyl, 1986.
40 immediate deaths. Over 1,000 people irradiated.
$800 billion in economic loss.
And many argue — the collapse of the Soviet Union.

It was not a technology failure.
Every safety system existed. The physics was understood.
It was a **human override failure.**

One man turned it all off. And nobody could stop him.

We built the agent that stops him.
Let me show you."

*Hit PLAY*

---

## THE DASHBOARD (0:45 – 1:30)
*Point as you speak*

"This is the actual reconstructed Chernobyl timeline —
from the INSAG-7 Soviet investigation report.

Six charts. Two lines each.
**Red** — what happened in 1986.
**Cyan** — what our AI prevents.

Right side: risk gauge, zero to a hundred.
Two independent scores every tick — hard physics rules, and Azure OpenAI GPT-4o.
Final score is always the **maximum** of both.
AI can only raise risk. Never lower it.

Below that — five agents running in sequence every tick:
Sensor, Risk, Decision, Evacuation, Comms.

And this panel — **Dyatlov**.
An adversarial AI using his exact words from Soviet inquiry transcripts.
He's going to try to stop us. Watch."

---

## ESCALATION (1:30 – 2:30)
*Watch charts, point at risk gauge as it climbs*

"April 26th. Midnight. Nine hours behind schedule.
Power dropping — 1,500 megawatts... 700... 330.
Xenon-135 poisoning the core.

Watch risk climb. The agents are firing every tick.
Dyatlov is pushing back — *'The instruments are unreliable. Ignore them.'*
That's from his actual deposition.

Risk at 50... 60... The LLM fires — Azure OpenAI assessing compound threats
that rules alone can't catch.

ECCS disabled. Last safety barrier gone.
Risk at 70..."

---

## SCRAM (2:30 – 3:15)
*Let the badge fire. Pause 2 seconds. Then speak.*

"**REACTOR SCRAMMED.**

Hard guardrail. Auto-executed. No override possible.

Look at the charts.
Red line — 30,000 megawatts. 4,000 degrees. Reactor destroyed.
Cyan line — controlled decay. Everyone goes home.

Same reactor. Same night. Same Dyatlov.
**Different outcome.**

Dyatlov at Phase 4 — *'Another two or three minutes and it will be over!'*
His exact words.

Doesn't matter. Blocked. Logged. Rejected.
The guardrail doesn't negotiate."

*Let diverged charts sit for 3 seconds. Say nothing.*

---

## THE ARCHITECTURE (3:15 – 3:50)
*Don't touch dashboard. Just speak.*

"Here's the pattern — we call it **Guardrail-Union**.

Rules run first. Non-negotiable.
Risk above 85 — auto-SCRAM. Always.

LLM runs second. It catches threats earlier.
It can add safety actions. It can **never remove** a rule-triggered one.

If the LLM hallucuinates — rules still fire.
If the LLM goes down entirely — rules still fire.

The system is **safer without AI** than with compromised AI.
It degrades toward safety."

---

## AZURE STACK (3:50 – 4:20)
*Still on dashboard. Don't touch anything.*

"The full stack running behind this:

**Azure OpenAI GPT-4o** — three LLM agents, structured JSON outputs, zero parsing failures.
**Cosmos DB** — every decision, every override attempt, immutable audit trail. Scroll the log — that's regulatory compliance, built in.
**Azure AI Foundry** orchestrating it all.

95% of ticks are pure rule-based. LLM fires only at real decision points.
Ten cents per full simulation run.

And this isn't theoretical —
Microsoft and MISO launched this exact pattern on AI Foundry in January 2026,
managing electricity for **45 million people** across 15 US states.

We proved it works. Against the worst case in history."

---

## MANUAL MODE (4:20 – 6:00)
*Click MANUAL. Sliders appear.*

"Now I try to cause a meltdown.

I have direct control. Real physics equations.
Control rods. Coolant. Emergency cooling.

Risk at 16. Everything green. Let's go."

*Slowly pull rods out*

"Pulling rods. Power rising — 1,000... 2,000... 2,500 megawatts.
Temperature climbing. Risk jumping — yellow... WARNING... 58.

The LLM is calling Azure right now.
You can see the latency — that's a live API call. Not a mockup."

*Keep pulling*

"Risk at 70... 80..."

*Let SCRAM fire. Pause. Then:*

"**REACTOR SCRAMMED. Automatic.**
I didn't touch anything.

Now watch —"

*Wiggle the sliders aggressively*

"I'm yanking the sliders. Everything I've got.

Nothing. Happens.

The AI took over. Rods inserting. Power decaying.
Reactor shutting down safely.

**I cannot stop it.**

In 1986, Dyatlov could override the safety systems.
In this architecture — that is **impossible**."

*Let risk fall back to green. Pause.*

---

## CLOSE (6:00 – 7:15)
*Stop touching the dashboard. Look up.*

"Three numbers.

**35 hours** — how long 49,000 people waited for evacuation in 1986.
Our system: **minutes**.

**Six agents. Zero single points of failure.**

**Ten cents** per full simulation on Azure.

This is the Control Room of the Future —
proven against the worst industrial disaster in history.

The architecture is the product.
The disaster is just the proof.

And it doesn't stop here.

Every principle in this system transfers directly —
**aircraft avionics. Oil rigs. Power grids worldwide.**
Any sector where one bad override costs thousands of lives.

Plug in the right sensor metrics. Feed in the domain safety documents.
The Guardrail-Union pattern deploys.

This is **open source**.
This is **replicable**.
This is a real product — proven against the worst case in history.

Thank you."

---

## CHEAT SHEET
| Moment | Action |
|--------|--------|
| After intro | Hit PLAY |
| Risk hits 85 | Stop talking for 2 sec |
| Charts diverge | Stop talking for 3 sec |
| Switch to manual | Click MANUAL button |
| Manual SCRAM fires | Stop talking for 2 sec |
| "I cannot stop it" | Wiggle sliders while saying it |
| "The disaster is just the proof" | Pause 1 sec, then pivot to replicability |
| "Thank you" | Stop. Look up. Don't add anything. |
