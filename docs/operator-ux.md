# PRIPYAT-1986 — Operator UX Workflow

## Overview

The PRIPYAT-1986 dashboard is designed for **control room operators** who must
monitor reactor state, understand AI recommendations, and take action under
pressure. This document describes the operator experience, alert design, and
intervention points.

---

## 1. Operator Journey Map

```
┌─────────────┐    ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│   MONITOR   │───▶│    ALERT     │───▶│    DECIDE         │───▶│   REVIEW    │
│             │    │              │    │                    │    │             │
│ View gauges │    │ Risk rises   │    │ Confirm or let    │    │ Counterfact │
│ Track trends│    │ Color shifts │    │ AI auto-execute   │    │ comparison  │
│ Watch agents│    │ Badge appears│    │                    │    │ Audit trail │
└─────────────┘    └──────────────┘    └──────────────────┘    └──────────────┘
     ▲                                                              │
     └──────────────────── continuous loop ──────────────────────────┘
```

### Phase 1: Monitor (Risk 0–30)
- Dashboard in default state: green risk gauge, all charts streaming calmly
- Agent Pipeline shows Sensor (S) and Risk (R) nodes active (cyan)
- Operator observes: power, rods, coolant, steam, temperature, radiation charts
- Dyatlov panel shows calm dialogue ("The test has been delayed long enough")
- **Operator action**: None required. Passive monitoring.

### Phase 2: Alert (Risk 30–85)
- Risk gauge turns yellow (30–60) then orange (60–85)
- Alert Level badge changes: NORMAL → WARNING → CRITICAL
- Agent Pipeline activates Decision (D) node (red glow)
- Agent Log starts populating with AI recommendations
- Dyatlov panel escalates: DISMISSIVE → AUTHORITARIAN pressure
- **Operator action**: Review AI reasoning in Agent Log. At 60–85, operator can
  toggle AI Intervention off to take manual control.

### Phase 3: Decide (Risk >85)
- Risk gauge turns red, EMERGENCY badge pulses
- Auto-SCRAM triggers (hard guardrail — cannot be prevented)
- REACTOR SCRAMMED badge appears in header
- If radiation >100 mrem/h: EVACUATION ORDERED badge appears
- Evacuation panel shows bus deployment, routes, ETA
- CommsAgent drafts emergency broadcasts
- **Operator action**: Acknowledge SCRAM. Monitor evacuation progress.
  Review Dyatlov's adversarial response.

### Phase 4: Review (Post-incident)
- Counterfactual panel shows side-by-side: What Happened (1986) vs AI Decision
- Timeline scrubber allows seeking to any point for post-mortem
- Agent Log preserves full decision history (scrollable)
- Final report shows: AI SCRAM time, evacuation hours saved, cost estimate

---

## 2. Alert Design Principles

### Visual Hierarchy
| Element | Normal | Warning | Critical | Emergency |
|---------|--------|---------|----------|-----------|
| Risk Score Color | Green | Yellow | Orange | Red (pulsing) |
| Risk Bar | Green fill | Yellow fill | Orange fill | Red fill |
| Alert Badge | Hidden | "WARNING" | "CRITICAL" | "EMERGENCY" (pulsing) |
| Pipeline Nodes | Cyan (S,R only) | Cyan (S,R) | Red (D active) | Red (D,E,C all active) |
| Dashboard Border | None | None | Subtle orange glow | Red glow on Dyatlov panel |

### Information Architecture
- **Primary focus**: Risk score (largest element, center-right)
- **Secondary**: Charts (left 2/3 of screen, 6 panels)
- **Tertiary**: Agent Log + Dyatlov panel (right column, scrollable)
- **Context**: Timeline scrubber + historical events (bottom)

### Alert Priority Rules
1. Only the **highest-severity** condition determines the dashboard state
2. Multiple simultaneous warnings do NOT stack visually (avoids alarm fatigue)
3. The Agent Log preserves all individual alerts for review
4. Dyatlov's dialogue provides emotional/narrative context for the pressure

---

## 3. Intervention Points

Operators interact with the simulation through these controls:

| Control | Location | Effect |
|---------|----------|--------|
| **PLAY / PAUSE** | Top control bar | Start/stop simulation progression |
| **Speed Slider** (1x–2500x) | Top control bar | Adjust simulation speed |
| **AI Intervention Toggle** | Top control bar | Enable/disable AI recommendations. When OFF, agents report but don't trigger actions. |
| **Timeline Scrubber** | Bottom bar | Seek to any tick. Only works when paused. |
| **RESET** | Top control bar | Restart simulation from beginning |

### Decision Ladder Indicator (Dashboard Element)

A visual indicator showing the current AI decision mode:

```
┌─────────────────────────────────────────┐
│  Decision Mode:  [ADVISORY]             │  ← Risk < 60
│  Decision Mode:  [CONFIRM REQUIRED]     │  ← Risk 60-85
│  Decision Mode:  [AUTO-EXECUTE ⚡]      │  ← Risk > 85
└─────────────────────────────────────────┘
```

This tells the operator at a glance whether the AI is observing, recommending,
or acting autonomously.

---

## 4. Trust Calibration

### Why the Dyatlov Panel Matters
The adversarial Dyatlov agent serves a UX purpose: it shows operators **why
human override of safety systems is dangerous**. As Dyatlov's pressure escalates
from CALM → DESPERATE → DENIAL, operators viscerally understand the historical
human factor that caused the disaster.

### Counterfactual Validation
The split-screen counterfactual comparison at simulation end provides **evidence
that the AI's decisions would have worked**:
- AI SCRAM time vs actual explosion time
- AI evacuation start vs actual 36-hour delay
- Lives saved estimate

This builds trust through historical validation rather than abstract claims.

---

## 5. Accessibility Considerations

| Feature | Implementation |
|---------|---------------|
| Color-blind safe | Risk levels use shape + text + color (not color alone) |
| Keyboard navigation | All controls accessible via Tab + Enter |
| Screen reader | ARIA labels on risk score, alert level, agent pipeline |
| High contrast | Dashboard uses high-contrast dark theme by default |
| Text scaling | All text in relative units (rem/em), responsive layout |
