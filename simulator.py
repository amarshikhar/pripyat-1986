"""
PRIPYAT-1986 Event Simulator
Replays the Chernobyl timeline as a real-time data stream.

Azure Migration: Replace emit() with Azure Event Hubs producer.
"""

import time
import asyncio
from datetime import datetime
from dataclasses import asdict
from typing import Callable, Optional

from timeline_data import CHERNOBYL_TIMELINE, ReactorState
from config import SIMULATION


class EventSimulator:
    """
    Streams Chernobyl timeline events at configurable speed.
    Acts as the Historical Replay Engine from the architecture.

    Azure equivalent: Azure Event Hubs producer publishing to a topic.
    """

    def __init__(
        self,
        speed_multiplier: int = SIMULATION["speed_multiplier"],
        on_event: Optional[Callable] = None,
    ):
        self.speed = speed_multiplier
        self.on_event = on_event  # Callback when event fires
        start_from = SIMULATION.get("sim_start_from")
        if start_from:
            self.timeline = [e for e in CHERNOBYL_TIMELINE if e.timestamp >= start_from]
        else:
            self.timeline = CHERNOBYL_TIMELINE
        self.current_index = 0
        self.running = False
        self.paused = False
        self._interpolated_events: list[ReactorState] = []
        self._prepare_interpolated_timeline()

    def _prepare_interpolated_timeline(self):
        """
        Generate interpolated events between major timeline points
        so the simulation has smooth transitions (1 event per tick).
        """
        self._interpolated_events = []

        for i in range(len(self.timeline) - 1):
            current = self.timeline[i]
            next_evt = self.timeline[i + 1]

            t_current = datetime.fromisoformat(current.timestamp)
            t_next = datetime.fromisoformat(next_evt.timestamp)
            gap_seconds = (t_next - t_current).total_seconds()

            # How many ticks fit in this gap at current speed
            real_seconds = gap_seconds / self.speed
            num_steps = max(int(real_seconds / SIMULATION["tick_interval_sec"]), 1)

            for step in range(num_steps):
                frac = step / num_steps
                # Linear interpolation of numeric values
                interp = ReactorState(
                    timestamp=datetime.fromtimestamp(
                        t_current.timestamp() + gap_seconds * frac
                    ).strftime("%Y-%m-%dT%H:%M:%S"),
                    power_mw=round(
                        current.power_mw + (next_evt.power_mw - current.power_mw) * frac, 1
                    ),
                    control_rods_inserted=round(
                        current.control_rods_inserted
                        + (next_evt.control_rods_inserted - current.control_rods_inserted) * frac
                    ),
                    coolant_flow_m3h=round(
                        current.coolant_flow_m3h
                        + (next_evt.coolant_flow_m3h - current.coolant_flow_m3h) * frac, 1
                    ),
                    steam_pressure_mpa=round(
                        current.steam_pressure_mpa
                        + (next_evt.steam_pressure_mpa - current.steam_pressure_mpa) * frac, 2
                    ),
                    temperature_c=round(
                        current.temperature_c
                        + (next_evt.temperature_c - current.temperature_c) * frac, 1
                    ),
                    radiation_mrem_h=round(
                        current.radiation_mrem_h
                        + (next_evt.radiation_mrem_h - current.radiation_mrem_h) * frac, 4
                    ),
                    eccs_active=current.eccs_active,
                    event_description=current.event_description if step == 0 else "",
                    actual_human_decision=current.actual_human_decision if step == 0 else "",
                    tags=current.tags if step == 0 else [],
                )
                self._interpolated_events.append(interp)

        # Add final event (the explosion or last aftermath event)
        self._interpolated_events.append(self.timeline[-1])

    async def run(self):
        """Stream events at simulation speed."""
        self.running = True
        self.current_index = 0

        for event in self._interpolated_events:
            if not self.running:
                break

            while self.paused:
                await asyncio.sleep(0.1)

            if self.on_event:
                await self.on_event(event, self.current_index, len(self._interpolated_events))

            self.current_index += 1
            await asyncio.sleep(SIMULATION["tick_interval_sec"])

        self.running = False

    def stop(self):
        self.running = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def reset(self):
        """Reset simulator to beginning."""
        self.current_index = 0
        self.running = False
        self.paused = False

    def set_speed(self, multiplier: int):
        """Change simulation speed dynamically (affects tick interval)."""
        self.speed = max(1, multiplier)

    def step(self) -> Optional[ReactorState]:
        """Advance exactly one tick and return the event."""
        if self.current_index < len(self._interpolated_events):
            event = self._interpolated_events[self.current_index]
            self.current_index += 1
            return event
        return None

    def seek(self, index: int):
        """Jump to a specific position in the timeline."""
        self.current_index = max(0, min(index, len(self._interpolated_events) - 1))

    @property
    def total_events(self) -> int:
        return len(self._interpolated_events)

    def get_event(self, index: int) -> Optional[ReactorState]:
        if 0 <= index < len(self._interpolated_events):
            return self._interpolated_events[index]
        return None
