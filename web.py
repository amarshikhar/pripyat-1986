"""
PRIPYAT-1986 Web Dashboard Server
FastAPI + WebSocket for real-time simulation visualization.

Usage:
    python web.py                  # Start server on port 8000
    python web.py --port 9000      # Custom port
"""

import asyncio
import json
import logging
import os
import sys
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

# Configure logging so LLM calls are visible in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Reduce noise from other libraries
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal, Optional

from timeline_engine import DualTimelineEngine
from config import SIMULATION
from orchestrator import Orchestrator
from physics import compute_manual_state, compute_scram_decay, NOMINAL_COOLANT_FLOW
from evaluation import run_evaluation

app = FastAPI(title="PRIPYAT-1986")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# ── Simulation State ──────────────────────────────────────────────

engine = DualTimelineEngine()
sim_state = {
    "playing": False,
    "speed": SIMULATION["web_default_speed"],
    "tick_interval": SIMULATION["tick_interval_sec"],
}
connected_clients: set[WebSocket] = set()
sim_task: Optional[asyncio.Task] = None


# ── WebSocket Broadcast ──────────────────────────────────────────

async def broadcast(message: dict):
    """Send message to all connected WebSocket clients in parallel."""
    if not connected_clients:
        return
    data = json.dumps(message, default=str)
    
    # Run all sends in parallel
    tasks = [ws.send_text(data) for ws in connected_clients]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Identify failed connections
    disconnected = set()
    for ws, res in zip(connected_clients, results):
        if isinstance(res, Exception):
            disconnected.add(ws)
    
    if disconnected:
        connected_clients.difference_update(disconnected)


async def broadcast_state():
    """Broadcast current simulation control state."""
    await broadcast({
        "type": "state_update",
        "data": {
            "playing": sim_state["playing"],
            "speed": sim_state["speed"],
            "intervention_enabled": engine.intervention_enabled,
            "total_ticks": engine.total_ticks,
            "current_tick": engine.current_tick,
        },
    })


# ── Simulation Loop ──────────────────────────────────────────────

async def simulation_loop():
    """Main simulation loop — processes ticks and broadcasts."""
    TARGET_FPS = 15  # Max broadcasts per second to keep UI responsive
    # One tick is one simulated minute, so playback runs at speed/60 ticks per
    # second. The fractional remainder carries between frames, which is what
    # makes speeds below one tick per frame actually slow the replay down
    # (integer truncation used to collapse every speed under 900x to the same
    # 15 ticks/s).
    tick_budget = 0.0
    while sim_state["playing"]:
        ticks_per_second = max(sim_state["speed"], 1) / 60.0
        tick_budget += ticks_per_second / TARGET_FPS
        ticks_this_frame = int(tick_budget)
        tick_budget -= ticks_this_frame

        if ticks_this_frame == 0:
            await asyncio.sleep(1.0 / TARGET_FPS)
            continue

        # At high speeds, batch multiple ticks but only broadcast the last one
        tick_data = None
        for _ in range(ticks_this_frame):
            tick_data = await engine.process_tick()
            if tick_data is None:
                break

        if tick_data is None:
            sim_state["playing"] = False
            report = engine.get_final_report()
            await broadcast({"type": "simulation_complete", "data": report})
            await broadcast_state()
            break

        await broadcast(tick_data)
        pending = tick_data.get("data", {}).get("pending_recommendations", [])
        if pending:
            # Freeze the replay at the human checkpoint. Hard SafetyKernel trips
            # have already executed before this point and never wait for review.
            sim_state["playing"] = False
            await broadcast_state()
            break
        await asyncio.sleep(1.0 / TARGET_FPS)


def start_simulation():
    """Start or resume the simulation loop."""
    global sim_task
    if sim_task and not sim_task.done():
        return  # Already running
    sim_state["playing"] = True
    sim_task = asyncio.create_task(simulation_loop())


async def stop_simulation():
    """Pause the simulation and wait for in-flight tick to complete."""
    global sim_task
    sim_state["playing"] = False
    if sim_task and not sim_task.done():
        sim_task.cancel()
        try:
            await sim_task
        except (asyncio.CancelledError, Exception):
            pass
    sim_task = None


# ── Control API ──────────────────────────────────────────────────

class ControlCommand(BaseModel):
    action: str
    value: Optional[float] = None


ALLOWED_REVIEW_ACTIONS = {
    "AZ-5 EMERGENCY SHUTDOWN (SCRAM)",
    "ORDER IMMEDIATE EVACUATION OF PRIPYAT",
    "ABORT TEST",
    "ECCS VIOLATION WARNING",
}


class ReviewCommand(BaseModel):
    decision: Literal["approve", "reject", "edit"]
    reviewer: str = Field(min_length=2, max_length=80)
    note: str = Field(default="", max_length=500)
    edited_action: Optional[str] = None
    scope: Literal["timeline", "manual"] = "timeline"


@app.get("/api/recommendations")
async def recommendations(scope: str = "timeline"):
    orchestrator = manual_orchestrator if scope == "manual" else engine.orchestrator
    if orchestrator is None:
        return []
    return orchestrator.pending_recommendations()


@app.get("/api/cases")
async def cases(status: Optional[str] = None, limit: int = 100):
    allowed = {"pending_review", "approved", "approved_with_edits", "rejected"}
    if status and status not in allowed:
        raise HTTPException(422, "invalid case status")
    return engine.orchestrator.store.list_cases(status=status, limit=limit)


@app.get("/api/cases/{case_id}")
async def case_detail(case_id: str):
    case = engine.orchestrator.store.get_case(case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    return case


@app.get("/api/audit")
async def audit_events(
    limit: int = 250, run_id: Optional[str] = None, entity_id: Optional[str] = None,
):
    return engine.orchestrator.store.list_audit(
        limit=limit, run_id=run_id, entity_id=entity_id,
    )


@app.get("/api/evals")
async def eval_report():
    return await run_evaluation()


def _archived_case_review(recommendation_id: str, cmd: ReviewCommand) -> dict:
    """Record a decision on a case whose live session no longer exists.

    Cases outlive the run that produced them (the manual lab is reset, the
    timeline is replayed).  The decision must still be recordable and
    attributable; it simply cannot queue an action, so it is never executed.
    """
    store = engine.orchestrator.store
    case = store.get_case(recommendation_id)
    if case is None:
        raise HTTPException(404, "case not found")
    if case["status"] != "pending_review":
        raise HTTPException(409, f"recommendation already decided ({case['status']})")

    final_action = case["action"]
    if cmd.decision == "edit":
        if cmd.edited_action not in ALLOWED_REVIEW_ACTIONS:
            raise HTTPException(422, "edited action is not in the approved control vocabulary")
        final_action = cmd.edited_action
        status = "approved_with_edits"
    else:
        status = "approved" if cmd.decision == "approve" else "rejected"

    review = {
        "status": status,
        "action": final_action,
        "reviewer": cmd.reviewer.strip(),
        "note": cmd.note.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "executed": False,
    }
    try:
        store.update_case_review(recommendation_id, review)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc

    store.add_audit_event(
        case["run_id"], case["sim_timestamp"], case.get("tick", 0) or 0,
        f"human:{review['reviewer']}", "case_reviewed", "case", recommendation_id,
        status, {**review, "live_session": False},
    )
    return {**review, "id": recommendation_id, "live_session": False}


@app.post("/api/recommendations/{recommendation_id}/decision")
async def review_recommendation(recommendation_id: str, cmd: ReviewCommand):
    orchestrator = manual_orchestrator if cmd.scope == "manual" else engine.orchestrator
    if orchestrator is None or recommendation_id not in orchestrator.recommendations:
        # The case belongs to a session that has since been reset. Persist the
        # signed decision anyway rather than dropping it on the floor.
        return _archived_case_review(recommendation_id, cmd)
    try:
        result = orchestrator.review_recommendation(
            recommendation_id=recommendation_id,
            decision=cmd.decision,
            reviewer=cmd.reviewer,
            note=cmd.note,
            edited_action=cmd.edited_action,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return result


@app.post("/api/control")
async def control(cmd: ControlCommand):
    """Handle simulation control commands."""
    if cmd.action == "play":
        start_simulation()
    elif cmd.action == "pause":
        await stop_simulation()
    elif cmd.action == "reset":
        await stop_simulation()
        engine.reset()
    elif cmd.action == "step":
        if not sim_state["playing"]:
            tick_data = await engine.process_tick()
            if tick_data:
                await broadcast(tick_data)
    elif cmd.action == "set_speed":
        speed = max(1, min(2500, int(cmd.value or 60)))
        sim_state["speed"] = speed
        engine.set_speed(speed)
    elif cmd.action == "toggle_intervention":
        engine.intervention_enabled = not engine.intervention_enabled
    elif cmd.action == "seek":
        if not sim_state["playing"] and cmd.value is not None:
            await stop_simulation()
            target = int(cmd.value)
            engine.reset()
            # Replay up to the target tick silently. Model calls are suspended
            # for the fast-forward so scrubbing stays instant.
            engine.orchestrator.llm.suspended = True
            tick_data = None
            try:
                for _ in range(target):
                    tick_data = await engine.process_tick()
                    if tick_data is None:
                        break
            finally:
                engine.orchestrator.llm.suspended = False
            # Send the final tick to update the UI
            if tick_data:
                await broadcast(tick_data)

    await broadcast_state()
    return {"status": "ok", "state": sim_state}


# ── Manual Control Mode ──────────────────────────────────────────

manual_orchestrator: Optional[Orchestrator] = None
manual_active = False
_manual_tick_lock = asyncio.Lock()

# Gradual ramp state — simulates real reactor inertia
MANUAL_DEFAULT_RODS = 100.0
manual_actual_rods: float = MANUAL_DEFAULT_RODS
manual_actual_coolant: float = NOMINAL_COOLANT_FLOW
MANUAL_TICK_SECONDS = 1.0   # Must match MANUAL_TICK_RATE_MS in static/app.js
RODS_RAMP_RATE = 7.0        # rods moved per tick (~30 s for full 211-rod travel)
COOLANT_RAMP_RATE = 700.0   # m³/h change per tick (~11 s across the full range)

# SCRAM state for manual mode
manual_scram_active = False
manual_scram_state = None  # ReactorState at moment of SCRAM
manual_scram_tick = 0      # tick when SCRAM was triggered


class ManualTickCommand(BaseModel):
    control_rods: int
    coolant_flow: float
    eccs_active: bool


@app.post("/api/manual_tick")
async def manual_tick(cmd: ManualTickCommand):
    """Process a manual operator input through the physics model + agent pipeline."""
    async with _manual_tick_lock:
        return await _process_manual_tick(cmd)


async def _process_manual_tick(cmd: ManualTickCommand):
    global manual_orchestrator, manual_active, manual_actual_rods, manual_actual_coolant
    global manual_scram_active, manual_scram_state, manual_scram_tick

    if manual_orchestrator is None:
        manual_orchestrator = Orchestrator(
            store=engine.orchestrator.store, scope="manual",
        )
        manual_active = True
        manual_actual_rods = float(cmd.control_rods)
        manual_actual_coolant = float(cmd.coolant_flow)

    if manual_scram_active and manual_scram_state:
        ticks_since_scram = manual_orchestrator.tick_count - manual_scram_tick + 1
        elapsed_s = ticks_since_scram * MANUAL_TICK_SECONDS
        state = compute_scram_decay(manual_scram_state, elapsed_s)
        state.tags = ["manual", "scram"]
        state.event_description = None
        state.actual_human_decision = None
    else:
        target_rods = float(cmd.control_rods)
        target_coolant = float(cmd.coolant_flow)
        if manual_actual_rods < target_rods:
            manual_actual_rods = min(target_rods, manual_actual_rods + RODS_RAMP_RATE)
        elif manual_actual_rods > target_rods:
            manual_actual_rods = max(target_rods, manual_actual_rods - RODS_RAMP_RATE)
        if manual_actual_coolant < target_coolant:
            manual_actual_coolant = min(target_coolant, manual_actual_coolant + COOLANT_RAMP_RATE)
        elif manual_actual_coolant > target_coolant:
            manual_actual_coolant = max(target_coolant, manual_actual_coolant - COOLANT_RAMP_RATE)
        state = compute_manual_state(round(manual_actual_rods), manual_actual_coolant, cmd.eccs_active)

    tick_summary = await manual_orchestrator.process_tick(state)

    if not manual_scram_active and manual_orchestrator.reactor_scrammed:
        manual_scram_active = True
        manual_scram_state = state
        manual_scram_tick = manual_orchestrator.tick_count

    decisions = tick_summary["decisions"]
    if not decisions:
        risk_score = tick_summary["risk_score"]
        if risk_score >= 60:
            assessment = f"Risk {risk_score}/100 — CRITICAL. Approaching emergency threshold."
        elif risk_score >= 30:
            assessment = f"Risk {risk_score}/100 — ELEVATED. Monitoring reactor parameters."
        else:
            assessment = f"Risk {risk_score}/100 — Parameters within acceptable bounds."
        ai_reasoning = tick_summary.get("risk_ai_reasoning")
        if ai_reasoning:
            assessment += f" AI: {ai_reasoning}"
        decisions = [{
            "agent": "RiskAgent",
            "action": "RISK ASSESSMENT",
            "reasoning": assessment,
            "level": tick_summary["alert_level"],
            "source": tick_summary.get("risk_source", "rule"),
        }]

    risk_score = tick_summary["risk_score"]

    tick_data = {
        "type": "tick",
        "data": {
            "tick": manual_orchestrator.tick_count,
            "timestamp": state.timestamp,
            "progress_pct": 0,
            "historical": {
                "power_mw": state.power_mw,
                "control_rods": state.control_rods_inserted,
                "coolant_flow": state.coolant_flow_m3h,
                "steam_pressure": state.steam_pressure_mpa,
                "temperature_c": state.temperature_c,
                "radiation": state.radiation_mrem_h,
            },
            # Manual mode plots exactly one line: the live reactor. There is no
            # counterfactual timeline to compare against here.
            "intervened": None,
            "risk_score": risk_score,
            "alert_level": tick_summary["alert_level"],
            "decisions": decisions,
            "recommendations": tick_summary.get("recommendations", []),
            "pending_recommendations": tick_summary.get("pending_recommendations", []),
            "dyatlov": tick_summary["dyatlov"],
            "llm_stats": tick_summary["llm_stats"],
            "audit_log": tick_summary.get("audit_log", []),
            "actual_event": state.event_description,
            "actual_decision": state.actual_human_decision,
            "counterfactual": None,
            "state": {
                **tick_summary["state"],
                "diverged": False,
                "scram_pending_review": bool(tick_summary.get("pending_recommendations")),
            },
            "source": "manual",
        },
    }

    await broadcast(tick_data)

    return {
        "status": "ok",
        "derived": {
            "power_mw": state.power_mw,
            "temperature_c": state.temperature_c,
            "steam_pressure_mpa": state.steam_pressure_mpa,
            "radiation_mrem_h": state.radiation_mrem_h,
        },
        "actual_rods": round(manual_actual_rods),
        "actual_coolant": round(manual_actual_coolant),
        "risk_score": tick_summary["risk_score"],
        "alert_level": tick_summary["alert_level"],
        "decisions": decisions,
        "pending_recommendations": tick_summary.get("pending_recommendations", []),
    }
@app.post("/api/manual_reset")
async def manual_reset():
    """Reset the manual mode orchestrator."""
    global manual_orchestrator, manual_active, manual_actual_rods, manual_actual_coolant
    global manual_scram_active, manual_scram_state, manual_scram_tick
    manual_orchestrator = None
    manual_active = False
    manual_actual_rods = MANUAL_DEFAULT_RODS
    manual_actual_coolant = NOMINAL_COOLANT_FLOW
    manual_scram_active = False
    manual_scram_state = None
    manual_scram_tick = 0
    return {"status": "ok"}


# ── WebSocket Endpoint ──────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    try:
        # Send current state on connect
        first_ts = engine.simulator.get_event(0)
        await ws.send_text(json.dumps({
            "type": "state_update",
            "data": {
                "playing": sim_state["playing"],
                "speed": sim_state["speed"],
                "intervention_enabled": engine.intervention_enabled,
                "total_ticks": engine.total_ticks,
                "current_tick": engine.current_tick,
                "first_timestamp": first_ts.timestamp if first_ts else None,
            },
        }))
        # Keep connection alive
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)


# ── Static Files ─────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="PRIPYAT-1986 Web Dashboard")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    print(f"\n  PRIPYAT-1986 Web Dashboard")
    print(f"  http://localhost:{args.port}\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
