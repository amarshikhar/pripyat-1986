"""
PRIPYAT-1986 Web Dashboard Server
FastAPI + WebSocket for real-time simulation visualization.

Usage:
    python web.py                  # Start server on port 8000
    python web.py --port 9000      # Custom port
"""

import asyncio
import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from timeline_engine import DualTimelineEngine
from config import SIMULATION

app = FastAPI(title="PRIPYAT-1986")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# ── Simulation State ──────────────────────────────────────────────

engine = DualTimelineEngine()
sim_state = {
    "playing": False,
    "speed": SIMULATION["speed_multiplier"],
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
    while sim_state["playing"]:
        # At high speeds, batch multiple ticks but only broadcast the last one
        effective_rate = sim_state["speed"] / SIMULATION["speed_multiplier"]
        ticks_per_frame = max(1, int(effective_rate / TARGET_FPS))

        tick_data = None
        for _ in range(ticks_per_frame):
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
            # Replay up to target tick silently
            for _ in range(target):
                tick_data = await engine.process_tick()
                if tick_data is None:
                    break
            # Send the final tick to update the UI
            if tick_data:
                await broadcast(tick_data)

    await broadcast_state()
    return {"status": "ok", "state": sim_state}


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
