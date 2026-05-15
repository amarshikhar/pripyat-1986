"""
PRIPYAT-1986 Historical Timeline Data
Reconstructed from INSAG-7 report, World Nuclear Association, and IAEA documents.

Each event is a timestamped snapshot of reactor state + what actually happened.
The simulator streams these as if they were live sensor telemetry.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReactorState:
    """Snapshot of RBMK-1000 Reactor #4 at a point in time."""
    timestamp: str                    # ISO format: 1986-04-26T01:00:00
    power_mw: float                   # Thermal power (MW)
    control_rods_inserted: int        # Number of rods in core (of 211 total)
    coolant_flow_m3h: float           # Primary coolant flow
    steam_pressure_mpa: float         # Steam drum pressure
    temperature_c: float              # Core outlet temperature
    radiation_mrem_h: float           # Local radiation level
    eccs_active: bool                 # Emergency Core Cooling System on/off
    event_description: str            # What happened at this moment
    actual_human_decision: str        # What operators/Dyatlov actually did
    tags: list[str] = field(default_factory=list)  # Classification tags


# ── THE CHERNOBYL TIMELINE ─────────────────────────────────────────
# April 25-26, 1986 — Reactor #4, Chernobyl Nuclear Power Plant
#
# This is the real sequence of events that led to the worst nuclear
# disaster in history. Each entry represents a key moment where
# different decisions could have prevented catastrophe.

CHERNOBYL_TIMELINE: list[ReactorState] = [

    # ── PHASE 1: TEST PREPARATION (April 25, 13:00 - 23:00) ──────

    ReactorState(
        timestamp="1986-04-25T13:00:00",
        power_mw=1600,
        control_rods_inserted=140,
        coolant_flow_m3h=8000,
        steam_pressure_mpa=6.5,
        temperature_c=280,
        radiation_mrem_h=0.01,
        eccs_active=True,
        event_description="Power reduction begins for turbine test. Reactor at 50% power.",
        actual_human_decision="Planned reduction from 3200 MW to 700 MW for safety test.",
        tags=["normal", "test_prep"],
    ),

    ReactorState(
        timestamp="1986-04-25T14:00:00",
        power_mw=1600,
        control_rods_inserted=140,
        coolant_flow_m3h=8000,
        steam_pressure_mpa=6.5,
        temperature_c=280,
        radiation_mrem_h=0.01,
        eccs_active=True,
        event_description="Kiev grid controller requests delay — power still needed for evening demand.",
        actual_human_decision="Power reduction halted. Test postponed ~9 hours.",
        tags=["delay", "grid_demand"],
    ),

    ReactorState(
        timestamp="1986-04-25T18:00:00",
        power_mw=1600,
        control_rods_inserted=140,
        coolant_flow_m3h=8000,
        steam_pressure_mpa=6.5,
        temperature_c=280,
        radiation_mrem_h=0.01,
        eccs_active=True,
        event_description=(
            "Evening shift arrives. Reactor held at 1600 MW per grid dispatcher order. "
            "Test crew waiting for grid demand to drop. Xenon-135 beginning slow buildup."
        ),
        actual_human_decision="Day shift briefs evening crew on postponed test. Reactor held at 50% power.",
        tags=["shift_change", "delay"],
    ),

    ReactorState(
        timestamp="1986-04-25T20:00:00",
        power_mw=1600,
        control_rods_inserted=140,
        coolant_flow_m3h=8000,
        steam_pressure_mpa=6.5,
        temperature_c=280,
        radiation_mrem_h=0.01,
        eccs_active=True,
        event_description=(
            "Reactor maintained at 50% power for 6 hours. Waiting for Kiev grid approval. "
            "Xenon-135 concentration rising — will complicate test at lower power."
        ),
        actual_human_decision="Operators maintain steady state. No action taken on xenon buildup.",
        tags=["delay", "xenon_buildup"],
    ),

    ReactorState(
        timestamp="1986-04-25T22:00:00",
        power_mw=1600,
        control_rods_inserted=140,
        coolant_flow_m3h=8000,
        steam_pressure_mpa=6.5,
        temperature_c=280,
        radiation_mrem_h=0.01,
        eccs_active=True,
        event_description=(
            "Night shift arrives: Shift foreman Akimov and operator Toptunov take control. "
            "Neither has performed this turbine test before. Grid approval expected soon."
        ),
        actual_human_decision=(
            "Night crew briefed on test procedure. Dyatlov will supervise. "
            "Crew less experienced with this specific test than the day shift."
        ),
        tags=["shift_change", "test_prep"],
    ),

    ReactorState(
        timestamp="1986-04-25T23:10:00",
        power_mw=1600,
        control_rods_inserted=140,
        coolant_flow_m3h=8000,
        steam_pressure_mpa=6.5,
        temperature_c=280,
        radiation_mrem_h=0.01,
        eccs_active=True,
        event_description="Kiev grid gives clearance. Power reduction resumes after 9-hour delay.",
        actual_human_decision="Dyatlov orders power reduction to begin. Target: 700 MW for turbine test.",
        tags=["test_prep", "power_reduction"],
    ),

    # ── PHASE 2: POWER DROP & XENON POISONING (April 26, 00:00 - 00:30) ──

    ReactorState(
        timestamp="1986-04-26T00:05:00",
        power_mw=720,
        control_rods_inserted=100,
        coolant_flow_m3h=7500,
        steam_pressure_mpa=6.4,
        temperature_c=282,
        radiation_mrem_h=0.01,
        eccs_active=True,
        event_description="Power approaching test level of 700 MW. Xenon-135 building up.",
        actual_human_decision="Operators continue reduction toward 700 MW target.",
        tags=["normal", "test_prep"],
    ),

    ReactorState(
        timestamp="1986-04-26T00:28:00",
        power_mw=30,
        control_rods_inserted=70,
        coolant_flow_m3h=7000,
        steam_pressure_mpa=6.2,
        temperature_c=275,
        radiation_mrem_h=0.01,
        eccs_active=False,
        event_description=(
            "CRITICAL: Power plunges to 30 MW due to operator error "
            "(local automatic regulation switched to wrong set of channels). "
            "Massive xenon-135 poisoning begins. ECCS disconnected for test."
        ),
        actual_human_decision=(
            "Dyatlov orders operators to raise power despite extreme xenon poisoning. "
            "ECCS deliberately disabled to prevent it interfering with the test. "
            "INSAG-7: This was the point of no return."
        ),
        tags=["critical", "xenon_poisoning", "eccs_disabled", "decision_point"],
    ),

    # ── PHASE 3: DANGEROUS RECOVERY (00:30 - 01:00) ──────────────

    ReactorState(
        timestamp="1986-04-26T00:32:00",
        power_mw=30,
        control_rods_inserted=50,
        coolant_flow_m3h=6800,
        steam_pressure_mpa=6.1,
        temperature_c=274,
        radiation_mrem_h=0.02,
        eccs_active=False,
        event_description="Operators withdraw control rods trying to raise power against xenon poison.",
        actual_human_decision="Rods pulled out far beyond safe limits. Regulations required shutdown.",
        tags=["critical", "rods_withdrawn", "violation"],
    ),

    ReactorState(
        timestamp="1986-04-26T00:43:00",
        power_mw=160,
        control_rods_inserted=35,
        coolant_flow_m3h=6500,
        steam_pressure_mpa=6.0,
        temperature_c=278,
        radiation_mrem_h=0.02,
        eccs_active=False,
        event_description="Power slowly recovers to ~160 MW but reactor deeply unstable.",
        actual_human_decision="Dyatlov insists on continuing to raise power for the test.",
        tags=["warning", "unstable", "decision_point"],
    ),

    ReactorState(
        timestamp="1986-04-26T01:00:00",
        power_mw=200,
        control_rods_inserted=30,
        coolant_flow_m3h=6200,
        steam_pressure_mpa=6.1,
        temperature_c=282,
        radiation_mrem_h=0.03,
        eccs_active=False,
        event_description=(
            "Power stabilized at ~200 MW. Only 30 rods inserted — minimum safe is 30. "
            "Reactor in extremely unstable state with strong positive void coefficient."
        ),
        actual_human_decision=(
            "Dyatlov orders test to proceed despite: (1) power far below 700 MW target, "
            "(2) ECCS disabled, (3) rods at absolute minimum. Multiple operators object."
        ),
        tags=["critical", "decision_point", "operator_objection"],
    ),

    # ── PHASE 4: THE TEST & CATASTROPHE (01:00 - 01:24) ──────────

    ReactorState(
        timestamp="1986-04-26T01:03:00",
        power_mw=200,
        control_rods_inserted=28,
        coolant_flow_m3h=6000,
        steam_pressure_mpa=6.0,
        temperature_c=284,
        radiation_mrem_h=0.03,
        eccs_active=False,
        event_description="Additional coolant pumps activated for test. Increased coolant flow.",
        actual_human_decision="Extra pumps create steam void instability risk.",
        tags=["warning", "test_begin"],
    ),

    ReactorState(
        timestamp="1986-04-26T01:07:00",
        power_mw=200,
        control_rods_inserted=24,
        coolant_flow_m3h=5800,
        steam_pressure_mpa=5.8,
        temperature_c=286,
        radiation_mrem_h=0.04,
        eccs_active=False,
        event_description=(
            "Steam drum pressure and water level dropping. Automatic shutdown signals "
            "blocked by operators to continue test."
        ),
        actual_human_decision="Safety systems manually overridden to prevent auto-shutdown.",
        tags=["critical", "safety_override", "decision_point"],
    ),

    ReactorState(
        timestamp="1986-04-26T01:19:00",
        power_mw=200,
        control_rods_inserted=18,
        coolant_flow_m3h=5500,
        steam_pressure_mpa=5.6,
        temperature_c=290,
        radiation_mrem_h=0.05,
        eccs_active=False,
        event_description=(
            "Only 18 control rods remain — far below the 30-rod minimum. "
            "Reactor extremely unstable. Operators aware of danger."
        ),
        actual_human_decision=(
            "Senior engineer Akimov and operator Toptunov express concern. "
            "Dyatlov: 'Another two or three minutes and it will be over. Continue!'"
        ),
        tags=["critical", "minimum_rods_violated", "decision_point"],
    ),

    ReactorState(
        timestamp="1986-04-26T01:22:30",
        power_mw=200,
        control_rods_inserted=8,
        coolant_flow_m3h=5000,
        steam_pressure_mpa=5.4,
        temperature_c=295,
        radiation_mrem_h=0.06,
        eccs_active=False,
        event_description=(
            "Turbine test begins. Steam to turbine #8 cut off. "
            "Only 6-8 control rods inserted. Reactor almost completely uncontrolled."
        ),
        actual_human_decision="Test proceeds. Coolant flow decreasing as pumps lose power.",
        tags=["critical", "test_active", "minimum_rods_violated"],
    ),

    ReactorState(
        timestamp="1986-04-26T01:23:04",
        power_mw=530,
        control_rods_inserted=8,
        coolant_flow_m3h=4000,
        steam_pressure_mpa=6.8,
        temperature_c=310,
        radiation_mrem_h=1.0,
        eccs_active=False,
        event_description=(
            "EMERGENCY: Power surging uncontrollably. Positive void coefficient "
            "causing runaway chain reaction. Power rising exponentially."
        ),
        actual_human_decision="Akimov presses AZ-5 (emergency shutdown). It's too late.",
        tags=["emergency", "power_surge", "az5_pressed"],
    ),

    ReactorState(
        timestamp="1986-04-26T01:23:40",
        power_mw=30000,
        control_rods_inserted=0,
        coolant_flow_m3h=0,
        steam_pressure_mpa=0,
        temperature_c=4000,
        radiation_mrem_h=50000,
        eccs_active=False,
        event_description=(
            "EXPLOSION. Power spikes to ~30,000 MW (100x rated capacity). "
            "Steam explosion destroys reactor. Graphite fire begins. "
            "1200-ton reactor lid (Elena) blown off. Radioactive plume rises 1km."
        ),
        actual_human_decision=(
            "Dyatlov initially refuses to believe reactor has exploded. "
            "Tells staff 'the reactor is intact' despite visible graphite on the ground."
        ),
        tags=["explosion", "catastrophe"],
    ),

    # ── PHASE 5: AFTERMATH (01:24 - 14:00, April 26) ─────────────

    ReactorState(
        timestamp="1986-04-26T01:30:00",
        power_mw=0,
        control_rods_inserted=0,
        coolant_flow_m3h=0,
        steam_pressure_mpa=0,
        temperature_c=2000,
        radiation_mrem_h=100000,
        eccs_active=False,
        event_description=(
            "Firefighters arrive. Radiation at reactor site: 5.6 roentgen/sec "
            "(20,000 mrem/h). Graphite blocks scattered. Roof of turbine hall on fire."
        ),
        actual_human_decision=(
            "Dyatlov sends operators to manually lower control rods — into a reactor "
            "that no longer exists. Firefighters given no radiation warnings."
        ),
        tags=["aftermath", "fire", "denial"],
    ),

    ReactorState(
        timestamp="1986-04-26T05:00:00",
        power_mw=0,
        control_rods_inserted=0,
        coolant_flow_m3h=0,
        steam_pressure_mpa=0,
        temperature_c=1500,
        radiation_mrem_h=80000,
        eccs_active=False,
        event_description=(
            "Fire mostly contained. 28 firefighters will die from acute radiation "
            "syndrome within weeks. Pripyat residents still asleep, unaware."
        ),
        actual_human_decision="Moscow not yet fully informed. No evacuation order.",
        tags=["aftermath", "no_evacuation"],
    ),

    ReactorState(
        timestamp="1986-04-26T14:00:00",
        power_mw=0,
        control_rods_inserted=0,
        coolant_flow_m3h=0,
        steam_pressure_mpa=0,
        temperature_c=1200,
        radiation_mrem_h=50000,
        eccs_active=False,
        event_description=(
            "Pripyat: 36 hours after explosion. Children playing outside. "
            "No evacuation. Government commission finally arrives."
        ),
        actual_human_decision=(
            "Evacuation not ordered until April 27, 14:00 — 36 hours after explosion. "
            "49,000 people exposed to radiation for over a day."
        ),
        tags=["aftermath", "delayed_evacuation", "decision_point"],
    ),
]


# ── WHAT SHOULD HAVE HAPPENED (AI Agent counterfactual) ───────────
# These are the key decision points where AI agents would intervene

AI_COUNTERFACTUAL_DECISIONS = {
    "1986-04-26T00:28:00": {
        "ai_decision": "IMMEDIATE SHUTDOWN — SCRAM reactor",
        "reasoning": (
            "Power at 30 MW is 96% below test target. Xenon-135 poisoning makes "
            "safe power recovery impossible. RBMK operating rules mandate shutdown "
            "below 700 MW. ECCS disconnection is a compounding violation."
        ),
        "lives_saved": "31 immediate deaths prevented, ~4000 long-term cancer deaths avoided",
        "outcome": "Test postponed. Reactor safely shut down. No explosion.",
    },
    "1986-04-26T00:43:00": {
        "ai_decision": "REJECT power increase — maintain shutdown",
        "reasoning": (
            "Attempting to raise power against xenon poisoning requires withdrawing "
            "rods below safe minimum. Positive void coefficient at low power makes "
            "any fluctuation potentially catastrophic."
        ),
        "lives_saved": "Same as above — this is a second chance to prevent disaster",
        "outcome": "Controlled shutdown continues. Xenon decays over 24-48 hours.",
    },
    "1986-04-26T01:00:00": {
        "ai_decision": "ABORT TEST — conditions do not meet any safety criteria",
        "reasoning": (
            "Power at 200 MW (target was 700 MW). Only 30 rods inserted (minimum). "
            "ECCS disabled. Multiple operators expressing concern. Zero conditions "
            "met for safe test execution."
        ),
        "lives_saved": "Final chance before point of no return",
        "outcome": "Test cancelled. Reactor enters controlled cooling.",
    },
    "1986-04-26T01:23:04": {
        "ai_decision": "AZ-5 ALREADY PRESSED 4 MINUTES AGO at 01:19",
        "reasoning": (
            "AI would have triggered emergency shutdown when rods dropped below 15. "
            "At 01:19 with only 18 rods, the AI Decision Agent would have overridden "
            "Dyatlov's authority and initiated AZ-5."
        ),
        "lives_saved": "Explosion may still occur if delayed to this point — too late",
        "outcome": "If AZ-5 at 01:19: possible safe shutdown. At 01:23: uncertain.",
    },
    "1986-04-26T01:30:00": {
        "ai_decision": "IMMEDIATE EVACUATION of Pripyat + 30km zone",
        "reasoning": (
            "Radiation levels confirm core breach. Wind direction NW will carry "
            "fallout over Pripyat within hours. Every minute of delay increases "
            "population exposure dose."
        ),
        "lives_saved": "49,000 residents evacuated 35 hours earlier than actual",
        "outcome": "Buses mobilized by 03:00. Pripyat evacuated by 08:00.",
    },
}
