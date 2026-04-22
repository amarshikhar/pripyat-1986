"""
PRIPYAT-1986 Terminal Dashboard
Split-screen view: actual history vs AI agent decisions.

Uses the Rich library for terminal UI.
Azure Migration: Replace with Blazor/React web dashboard.
"""

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.progress import Progress, BarColumn, TextColumn
from rich.align import Align
from rich import box

console = Console()


def get_alert_color(level: str) -> str:
    return {
        "NORMAL": "green",
        "WARNING": "yellow",
        "CRITICAL": "red",
        "EMERGENCY": "bold white on red",
    }.get(level, "white")


def get_risk_bar(score: int) -> str:
    """Visual risk bar."""
    filled = score // 5
    empty = 20 - filled
    if score >= 85:
        color = "red"
    elif score >= 60:
        color = "yellow"
    elif score >= 30:
        color = "cyan"
    else:
        color = "green"
    return f"[{color}]{'█' * filled}{'░' * empty}[/{color}] {score}/100"


def build_header(tick_data: dict, progress_pct: float) -> Panel:
    """Top banner with simulation status."""
    ts = tick_data.get("timestamp", "—")
    state = tick_data.get("state", {})

    status_parts = [f"[bold cyan]PRIPYAT-1986[/bold cyan]  |  Simulation Time: [bold]{ts}[/bold]"]

    if state.get("reactor_scrammed"):
        status_parts.append("  |  [bold green]✓ REACTOR SCRAMMED[/bold green]")
    if state.get("evacuation_ordered"):
        status_parts.append("  |  [bold green]✓ EVACUATION ORDERED[/bold green]")

    bar_len = 40
    filled = int(progress_pct / 100 * bar_len)
    bar = f"[cyan]{'━' * filled}[/cyan][dim]{'━' * (bar_len - filled)}[/dim]"
    status_parts.append(f"  |  Progress: {bar} {progress_pct:.0f}%")

    return Panel(
        Text.from_markup(" ".join(status_parts)),
        box=box.HEAVY,
        style="bold",
        height=3,
    )


def build_reactor_panel(tick_data: dict) -> Panel:
    """Reactor telemetry gauges."""
    r = tick_data.get("reactor", {})

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold", width=18)
    table.add_column("Value", width=15)
    table.add_column("Status", width=12)

    # Power
    power = r.get("power_mw", 0)
    if power > 3200:
        pstyle = "bold white on red"
        pstatus = "⚠ SURGE"
    elif power <= 30:
        pstyle = "bold red"
        pstatus = "⚠ CRITICAL"
    elif power <= 200:
        pstyle = "yellow"
        pstatus = "⚠ LOW"
    else:
        pstyle = "green"
        pstatus = "OK"
    table.add_row("Thermal Power", f"[{pstyle}]{power:.0f} MW[/{pstyle}]", pstatus)

    # Rods
    rods = r.get("control_rods", 0)
    if rods <= 15:
        rstyle, rstatus = "bold red", "⚠ CRITICAL"
    elif rods <= 30:
        rstyle, rstatus = "yellow", "⚠ LOW"
    else:
        rstyle, rstatus = "green", "OK"
    table.add_row("Control Rods", f"[{rstyle}]{rods}/211[/{rstyle}]", rstatus)

    # Coolant
    coolant = r.get("coolant_flow", 0)
    if coolant <= 4000:
        cstyle, cstatus = "bold red", "⚠ CRITICAL"
    elif coolant <= 6000:
        cstyle, cstatus = "yellow", "⚠ LOW"
    else:
        cstyle, cstatus = "green", "OK"
    table.add_row("Coolant Flow", f"[{cstyle}]{coolant:.0f} m³/h[/{cstyle}]", cstatus)

    # Steam
    steam = r.get("steam_pressure", 0)
    table.add_row("Steam Pressure", f"{steam:.2f} MPa", "OK" if steam < 7.0 else "⚠ HIGH")

    # Temperature
    temp = r.get("temperature_c", 0)
    if temp >= 320:
        tstyle = "bold red"
    elif temp >= 300:
        tstyle = "yellow"
    else:
        tstyle = "green"
    table.add_row("Core Temp", f"[{tstyle}]{temp:.0f}°C[/{tstyle}]", "")

    # Radiation
    rad = r.get("radiation", 0)
    if rad >= 10000:
        radstyle = "bold white on red"
    elif rad >= 100:
        radstyle = "bold red"
    elif rad >= 1:
        radstyle = "yellow"
    else:
        radstyle = "green"
    table.add_row("Radiation", f"[{radstyle}]{rad:.4f} mrem/h[/{radstyle}]", "")

    # ECCS
    eccs = r.get("eccs_active", True)
    eccs_text = "[green]ACTIVE[/green]" if eccs else "[bold red]DISABLED[/bold red]"
    table.add_row("ECCS", eccs_text, "")

    return Panel(table, title="[bold cyan]⚛ REACTOR #4 TELEMETRY[/bold cyan]", border_style="cyan")


def build_risk_panel(tick_data: dict) -> Panel:
    """Risk score display with AI/RULE source indicator."""
    score = tick_data.get("risk_score", 0)
    level = tick_data.get("alert_level", "NORMAL")
    color = get_alert_color(level)
    risk_source = tick_data.get("risk_source", "rule")

    # Source badge
    if risk_source == "llm":
        source_badge = "[bold cyan][AI][/bold cyan]"
    else:
        source_badge = "[yellow][RULE][/yellow]"

    content = Text()
    content.append(f"\n  Risk Score: ", style="bold")
    content.append(f"\n\n  {get_risk_bar(score)}\n", style="")
    content.append(f"\n  Alert Level: ")
    content.append(f" {level} ", style=color)
    content.append(f"\n  Sensor Alerts: {tick_data.get('sensor_alerts', 0)}")
    content.append(f"  |  Source: ")

    # AI reasoning snippet
    ai_reasoning = tick_data.get("risk_ai_reasoning")
    if ai_reasoning:
        snippet = ai_reasoning[:120] + "..." if len(ai_reasoning) > 120 else ai_reasoning
        content.append(f"\n  [dim cyan]AI: {snippet}[/dim cyan]")

    content.append("\n")

    border_color = color.split()[-1] if " " in color else color
    title = f"[bold {color}]⚠ RISK ASSESSMENT {source_badge}[/bold {color}]"
    return Panel(content, title=title, border_style=border_color)


def build_actual_panel(tick_data: dict) -> Panel:
    """What actually happened (left side of split)."""
    event = tick_data.get("actual_event", "")
    decision = tick_data.get("actual_decision", "")

    content = Text()
    if event:
        content.append("EVENT:\n", style="bold red")
        content.append(f"{event}\n\n", style="white")
    if decision:
        content.append("HUMAN DECISION:\n", style="bold red")
        content.append(f"{decision}\n", style="white")
    if not event and not decision:
        content.append("[dim]Interpolating between events...[/dim]")

    return Panel(
        content,
        title="[bold red]✗ ACTUAL HISTORY (1986)[/bold red]",
        border_style="red",
        height=12,
    )


def build_ai_panel(tick_data: dict) -> Panel:
    """What the AI decided (right side of split)."""
    decisions = tick_data.get("decisions", [])
    counterfactual = tick_data.get("counterfactual")
    state = tick_data.get("state", {})

    content = Text()

    if decisions:
        for d in decisions[-3:]:  # Show last 3 decisions
            level_color = get_alert_color(d.get("level", "NORMAL"))
            source = d.get("source", "rule")
            source_tag = "[bold cyan][AI][/bold cyan] " if source == "llm" else "[yellow][RULE][/yellow] "
            content.append(source_tag)
            content.append(f"[{d['agent']}] ", style="bold cyan")
            content.append(f"{d['action']}\n", style=level_color)
            # Truncate reasoning for display
            reasoning = d.get("reasoning", "")
            if len(reasoning) > 150:
                reasoning = reasoning[:147] + "..."
            content.append(f"  {reasoning}\n\n", style="dim")

    if counterfactual:
        content.append("COUNTERFACTUAL:\n", style="bold green")
        content.append(f"{counterfactual['ai_decision']}\n", style="green")
        content.append(f"Lives saved: {counterfactual['lives_saved']}\n", style="bold green")

    if not decisions and not counterfactual:
        if state.get("reactor_scrammed"):
            content.append("[bold green]Reactor safely shut down. Crisis averted.[/bold green]\n")
        else:
            content.append("[dim]Monitoring... No action needed yet.[/dim]")

    return Panel(
        content,
        title="[bold green]✓ AI AGENT DECISIONS[/bold green]",
        border_style="green",
        height=12,
    )


def get_pressure_bar(pressure: float) -> str:
    """Visual override pressure bar (red tones)."""
    filled = int(pressure // 5)
    empty = 20 - filled
    if pressure >= 80:
        color = "bold white on red"
    elif pressure >= 60:
        color = "bold red"
    elif pressure >= 40:
        color = "red"
    else:
        color = "dim red"
    return f"[{color}]{'█' * filled}{'░' * empty}[/{color}] {pressure:.0f}/100"


def build_dyatlov_panel(tick_data: dict) -> Panel:
    """Adversarial operator override attempts — Dyatlov vs AI."""
    dyatlov = tick_data.get("dyatlov", {})
    phase = dyatlov.get("escalation_phase", 0)
    pressure = dyatlov.get("override_pressure", 0)
    dialogue = dyatlov.get("pushback_dialogue", "")
    attempted = dyatlov.get("override_attempted", False)
    succeeded = dyatlov.get("override_succeeded", False)
    target = dyatlov.get("override_target", "")
    total_attempts = dyatlov.get("total_attempts", 0)
    total_failures = dyatlov.get("total_failures", 0)
    total_delays = dyatlov.get("total_delays", 0)

    phase_names = {
        0: "[dim]CALM[/dim]",
        1: "[yellow]DISMISSIVE[/yellow]",
        2: "[bold yellow]AUTHORITARIAN[/bold yellow]",
        3: "[bold red]DESPERATE[/bold red]",
        4: "[dim red]DENIAL[/dim red]",
    }

    content = Text()

    # Dialogue line — the dramatic centerpiece
    if dialogue:
        content.append('  "', style="dim")
        content.append(dialogue, style="bold white")
        content.append('"\n', style="dim")
    else:
        content.append("  [dim]...[/dim]\n")

    # Pressure bar + stats on same line
    content.append(f"  Pressure: {get_pressure_bar(pressure)}  ")
    content.append(f"  Phase: {phase_names.get(phase, str(phase))}")

    if attempted:
        result_style = "bold red" if succeeded else "bold green"
        result_text = "DELAYED" if succeeded else "BLOCKED"
        content.append(f"  |  [{result_style}]{result_text}[/{result_style}]")
        if target:
            content.append(f" → {target[:30]}", style="dim")

    content.append(f"\n  Blocked: {total_failures}  |  Delayed: {total_delays}  |  ")
    content.append(f"Total attempts: {total_attempts}")

    return Panel(
        content,
        title="[bold red]⚡ OPERATOR OVERRIDE — DYATLOV[/bold red]",
        border_style="red",
        height=5,
    )


def build_thought_trace(tick_data: dict) -> Panel:
    """Agent reasoning trace — what hackathon judges want to see."""
    decisions = tick_data.get("decisions", [])

    if not decisions:
        return Panel(
            "[dim]Awaiting agent actions...[/dim]",
            title="[bold magenta]🧠 THOUGHT TRACE[/bold magenta]",
            border_style="magenta",
        )

    table = Table(box=box.SIMPLE, show_edge=False)
    table.add_column("Src", width=6)
    table.add_column("Agent", style="cyan", width=18)
    table.add_column("Action", style="bold", width=28)
    table.add_column("Reasoning", width=55)

    for d in decisions[-5:]:
        level_color = get_alert_color(d.get("level", "NORMAL"))
        source = d.get("source", "rule")
        source_text = Text("AI", style="bold cyan") if source == "llm" else Text("RULE", style="yellow")
        reasoning = d.get("reasoning", "")
        if len(reasoning) > 70:
            reasoning = reasoning[:67] + "..."
        table.add_row(
            source_text,
            d["agent"],
            Text(d["action"], style=level_color),
            reasoning,
        )

    # Add Dyatlov entry if override was attempted
    dyatlov = tick_data.get("dyatlov", {})
    if dyatlov.get("override_attempted"):
        dialogue = dyatlov.get("pushback_dialogue", "")
        if len(dialogue) > 70:
            dialogue = dialogue[:67] + "..."
        result = "DELAYED" if dyatlov.get("override_succeeded") else "BLOCKED"
        target = dyatlov.get("override_target", "")
        if len(target) > 25:
            target = target[:22] + "..."
        table.add_row(
            Text("OPPR", style="bold red"),
            "DyatlovAgent",
            Text(f"{result} → {target}", style="bold red"),
            dialogue,
        )

    return Panel(table, title="[bold magenta]🧠 THOUGHT TRACE[/bold magenta]", border_style="magenta")


def build_layout(tick_data: dict, progress_pct: float) -> Layout:
    """Compose the full dashboard layout."""
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="dyatlov", size=5),
        Layout(name="footer", size=10),
    )

    layout["body"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1),
    )

    layout["left"].split_column(
        Layout(name="reactor", ratio=2),
        Layout(name="actual", ratio=1),
    )

    layout["right"].split_column(
        Layout(name="risk", ratio=1),
        Layout(name="ai", ratio=1),
    )

    layout["header"].update(build_header(tick_data, progress_pct))
    layout["reactor"].update(build_reactor_panel(tick_data))
    layout["risk"].update(build_risk_panel(tick_data))
    layout["actual"].update(build_actual_panel(tick_data))
    layout["ai"].update(build_ai_panel(tick_data))
    layout["dyatlov"].update(build_dyatlov_panel(tick_data))
    layout["footer"].update(build_thought_trace(tick_data))

    return layout


def print_final_report(report: dict):
    """Print the final comparison report after simulation ends."""
    console.print()
    console.print(Panel(
        "[bold cyan]PRIPYAT-1986 — ALTERNATE HISTORY REPORT[/bold cyan]",
        box=box.DOUBLE,
        style="bold cyan",
    ))

    # Comparison table
    table = Table(title="Actual vs AI Timeline", box=box.ROUNDED)
    table.add_column("", style="bold", width=25)
    table.add_column("Actual (1986)", style="red", width=35)
    table.add_column("AI Agent", style="green", width=35)

    actual = report["actual_timeline"]
    ai = report["ai_timeline"]

    table.add_row(
        "Reactor Shutdown",
        "01:23:40 (AZ-5 — TOO LATE)",
        ai["scram_ordered"],
    )
    table.add_row(
        "Evacuation Ordered",
        f"{actual['evacuation_ordered']} ({actual['evacuation_delay_hours']}h delay)",
        f"{ai['evacuation_ordered']}"
        + (f" ({ai['evacuation_hours_earlier']}h earlier)" if ai["evacuation_hours_earlier"] else ""),
    )
    table.add_row(
        "Explosion Prevented?",
        "[bold red]NO — 30,000 MW spike[/bold red]",
        "[bold green]YES[/bold green]" if ai["explosion_prevented"] else "[yellow]UNCERTAIN[/yellow]",
    )
    table.add_row(
        "Immediate Deaths",
        f"[red]{actual['immediate_deaths']}[/red]",
        "[green]0[/green]" if ai["explosion_prevented"] else "[yellow]Reduced[/yellow]",
    )
    table.add_row(
        "Long-term Deaths",
        f"[red]~{actual['estimated_longterm_deaths']:,}[/red]",
        "[green]0[/green]" if ai["explosion_prevented"] else "[yellow]Significantly reduced[/yellow]",
    )

    console.print(table)

    # Evacuation plan
    evac = report.get("evacuation_plan")
    if evac:
        console.print()
        evac_table = Table(title="AI Evacuation Plan", box=box.ROUNDED)
        evac_table.add_column("Route", width=25)
        evac_table.add_column("Distance", width=12)
        evac_table.add_column("People", width=12)
        evac_table.add_column("Buses", width=10)

        for route in evac.get("routes", []):
            evac_table.add_row(
                route["route"],
                f"{route['distance_km']} km",
                f"{route['people_allocated']:,}",
                str(route["buses_assigned"]),
            )
        evac_table.add_row(
            "[bold]TOTAL[/bold]",
            "",
            f"[bold]{evac['population']:,}[/bold]",
            f"[bold]{evac['total_buses']}[/bold]",
        )
        console.print(evac_table)
        console.print(f"\n  Estimated evacuation time: [bold green]{evac['estimated_hours']} hours[/bold green]")

    console.print()
    console.print(f"  Total agent actions taken: [bold]{report['total_agent_actions']}[/bold]")
    console.print(f"  Peak risk score: [bold red]{report['peak_risk_score']}/100[/bold red]")

    # Dyatlov analysis
    dyatlov = report.get("dyatlov_analysis", {})
    if dyatlov.get("total_override_attempts", 0) > 0:
        console.print()
        console.print(Panel(
            f"[bold red]DYATLOV OVERRIDE ANALYSIS[/bold red]",
            box=box.ROUNDED,
        ))
        console.print(f"  Override attempts: [bold red]{dyatlov['total_override_attempts']}[/bold red]")
        console.print(f"  Blocked by guardrails: [bold green]{dyatlov['overrides_blocked_by_guardrails']}[/bold green]")
        console.print(f"  Temporarily delayed: [yellow]{dyatlov['overrides_delayed']}[/yellow]")
        console.print(f"  Peak override pressure: [bold red]{dyatlov['peak_override_pressure']:.0f}/100[/bold red]")
        console.print(f"  Escalation phases reached: [bold]{dyatlov['escalation_phases_reached']}/4[/bold]")

        confrontations = dyatlov.get("key_confrontations", [])
        if confrontations:
            console.print()
            conf_table = Table(title="Key Confrontations", box=box.SIMPLE)
            conf_table.add_column("Time", width=22)
            conf_table.add_column("Phase", width=6)
            conf_table.add_column("Pressure", width=10)
            conf_table.add_column("Target", width=20)
            conf_table.add_column("Dialogue", width=50)
            conf_table.add_column("Result", width=8)
            for c in confrontations:
                result_style = "red" if c.get("succeeded") else "green"
                result_text = "DELAYED" if c.get("succeeded") else "BLOCKED"
                dialogue = c.get("dialogue", "")
                if len(dialogue) > 50:
                    dialogue = dialogue[:47] + "..."
                conf_table.add_row(
                    c.get("timestamp", ""),
                    str(c.get("phase", "")),
                    f"{c.get('pressure', 0):.0f}",
                    str(c.get("target", ""))[:20],
                    dialogue,
                    Text(result_text, style=result_style),
                )
            console.print(conf_table)

    # LLM stats
    llm_stats = report.get("llm_stats")
    if llm_stats:
        if llm_stats.get("llm_available"):
            console.print(
                f"  AI reasoning calls: [bold cyan]{llm_stats['total_calls']}[/bold cyan]"
                f"  |  Avg latency: [cyan]{llm_stats['avg_latency_ms']:.0f}ms[/cyan]"
            )
        else:
            console.print("  AI reasoning: [yellow]Disabled (no API key)[/yellow]")
    console.print()
    console.print(Panel(
        "[bold]The Chernobyl disaster was not inevitable. "
        "It was a cascade of human decisions that an AI safety system "
        "would have interrupted at multiple points — even when the operator "
        "fought to override every safeguard.[/bold]",
        border_style="cyan",
    ))
