#!/usr/bin/env python3
"""
PRIPYAT-1986 — Agentic AI Crisis Response Simulation
Entry point. Replays the Chernobyl timeline through a multi-agent system.

Usage:
    python main.py                    # Full simulation at 60x speed
    python main.py --speed 120        # 120x speed (faster demo)
    python main.py --speed 1          # Real-time (very slow)
    python main.py --no-dashboard     # Headless mode (JSON output only)
    python main.py --smoke-test       # Quick 5-tick validation

Azure Migration:
    Replace this with Azure Functions trigger or AKS deployment.
    Swap EventSimulator → Event Hubs consumer.
    Swap Orchestrator state → Cosmos DB.
    Swap Dashboard → Blazor/React web app.
"""

import asyncio
import argparse
import json
import sys
import os

# Ensure imports work when running from project dir
sys.path.insert(0, os.path.dirname(__file__))

from config import SIMULATION, OUTPUT_DIR
from simulator import EventSimulator
from orchestrator import Orchestrator
from dashboard import build_layout, print_final_report, console
from timeline_data import ReactorState

from rich.live import Live


def parse_args():
    parser = argparse.ArgumentParser(
        description="PRIPYAT-1986: Agentic AI Crisis Response Simulation"
    )
    parser.add_argument(
        "--speed", type=int, default=SIMULATION["speed_multiplier"],
        help=f"Simulation speed multiplier (default: {SIMULATION['speed_multiplier']}x)"
    )
    parser.add_argument(
        "--no-dashboard", action="store_true",
        help="Disable terminal UI, output JSON per tick"
    )
    parser.add_argument(
        "--smoke-test", action="store_true",
        help="Run only 5 ticks to validate pipeline"
    )
    parser.add_argument(
        "--web", action="store_true",
        help="Launch web dashboard instead of terminal UI"
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for web dashboard (default: 8000)"
    )
    return parser.parse_args()


async def run_simulation(args):
    """Main simulation loop."""
    orchestrator = Orchestrator()
    tick_count = 0
    max_ticks = 5 if args.smoke_test else None

    # Latest tick data for dashboard
    latest_tick = {
        "tick": 0, "timestamp": "—", "reactor": {},
        "risk_score": 0, "alert_level": "NORMAL",
        "sensor_alerts": 0, "decisions": [],
        "actual_event": "", "actual_decision": "",
        "counterfactual": None,
        "state": {"reactor_scrammed": False, "evacuation_ordered": False},
    }
    progress_pct = 0.0

    async def on_event(state: ReactorState, index: int, total: int):
        nonlocal latest_tick, tick_count, progress_pct

        tick_count += 1
        progress_pct = (index + 1) / total * 100

        # Run through agent pipeline
        summary = await orchestrator.process_tick(state)
        latest_tick = summary

        if args.no_dashboard:
            # JSON output mode
            if summary["decisions"] or summary["actual_event"]:
                print(json.dumps(summary, indent=2, default=str))

    simulator = EventSimulator(speed_multiplier=args.speed, on_event=on_event)

    if max_ticks:
        # Smoke test — just process first N events directly
        for i, event in enumerate(simulator._interpolated_events[:max_ticks]):
            await on_event(event, i, max_ticks)
        console.print(f"[green]Smoke test passed — {max_ticks} ticks processed.[/green]")
        orchestrator.save_state()
        return orchestrator

    if args.no_dashboard:
        console.print("[bold cyan]PRIPYAT-1986[/bold cyan] — Running headless...")
        # Skip sleeps in headless mode — process all events instantly
        for i, event in enumerate(simulator._interpolated_events):
            await on_event(event, i, len(simulator._interpolated_events))
    else:
        # Rich Live dashboard
        console.print("[bold cyan]PRIPYAT-1986[/bold cyan] — Initializing simulation...")
        console.print(f"Speed: [bold]{args.speed}x[/bold] | Events: [bold]{simulator.total_events}[/bold]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        await asyncio.sleep(1)

        with Live(
            build_layout(latest_tick, 0),
            console=console,
            refresh_per_second=2,
            screen=True,
        ) as live:
            # Update task to refresh dashboard
            async def dashboard_updater():
                while simulator.running:
                    live.update(build_layout(latest_tick, progress_pct))
                    await asyncio.sleep(0.5)

            # Run simulator and dashboard concurrently
            updater_task = asyncio.create_task(dashboard_updater())
            try:
                await simulator.run()
            except KeyboardInterrupt:
                simulator.stop()
            finally:
                updater_task.cancel()
                try:
                    await updater_task
                except asyncio.CancelledError:
                    pass

    # Save state and show report
    orchestrator.save_state()
    return orchestrator


def main():
    args = parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Web dashboard mode
    if args.web:
        import uvicorn
        from web import app
        print(f"\n  PRIPYAT-1986 Web Dashboard")
        print(f"  http://localhost:{args.port}\n")
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
        return

    try:
        orchestrator = asyncio.run(run_simulation(args))
    except KeyboardInterrupt:
        console.print("\n[yellow]Simulation interrupted.[/yellow]")
        return

    # Final report
    if not args.smoke_test:
        report = orchestrator.get_final_report()
        print_final_report(report)

        # Save report
        report_path = os.path.join(OUTPUT_DIR, "final_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        console.print(f"\n[dim]Report saved to {report_path}[/dim]")
        console.print(f"[dim]State saved to {os.path.join(OUTPUT_DIR, 'agent_state.json')}[/dim]")


if __name__ == "__main__":
    main()
