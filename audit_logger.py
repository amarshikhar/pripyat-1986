"""
PRIPYAT-1986 Audit Logger
Lightweight in-memory audit trail for every agent, LLM, guardrail,
and physics calculation. Designed for zero-latency impact — just
appends dicts to a list per tick, drained after each tick.

Deduplication: Consecutive identical entries (same agent, type, detail)
are collapsed into a single entry with a repeat count, keeping the log
readable without losing information.
"""

import threading
from typing import Optional


class AuditLogger:
    """
    Per-tick audit log buffer. Accumulates log entries during a tick,
    then drains them into the tick summary for broadcast.
    Thread-safe via a simple lock (LLM calls may resolve on different threads).

    Deduplication across ticks:
    - Tracks the last emitted "signature" per agent+type
    - If the current tick produces an identical entry, it increments a
      suppression counter instead of emitting a new row
    - A summary line is emitted when the repeated state ends or every
      N ticks (configurable via DEDUP_SUMMARY_INTERVAL)
    """

    DEDUP_SUMMARY_INTERVAL = 30  # Emit a "still ongoing" summary every N suppressed ticks

    def __init__(self):
        self._entries: list[dict] = []
        self._lock = threading.Lock()
        self._tick: int = 0
        self._timestamp: str = ""
        # Deduplication state: key = (agent, log_type) → {detail, count, first_tick, first_ts}
        self._dedup_state: dict[tuple[str, str], dict] = {}

    def set_tick(self, tick: int, timestamp: str):
        """Set current tick context (called at start of each tick)."""
        self._tick = tick
        self._timestamp = timestamp

    def _dedup_key(self, agent: str, log_type: str, detail: str = "") -> tuple:
        # For SENSOR_ALERT, use the alert category as part of the key
        # so each sensor type (POWER, RADIATION, etc.) deduplicates independently
        if log_type == "SENSOR_ALERT" and ":" in detail:
            category = detail.split(":")[0]  # e.g. "[CRITICAL] LOW POWER"
            return (agent, log_type, category)
        return (agent, log_type)

    def _should_deduplicate(self, agent: str, log_type: str, detail: str) -> bool:
        """Check if this entry is a repeat of the previous one for this agent+type."""
        # Never deduplicate these important entry types
        if log_type in ("LLM_CALL", "STATE_CHANGE", "OPERATOR_PRESSURE",
                        "REINJECT", "EVACUATION", "COMMS"):
            return False
        # Only deduplicate if direction is OUTPUT (routine checks)
        key = self._dedup_key(agent, log_type, detail)
        prev = self._dedup_state.get(key)
        if prev and prev["detail"] == detail:
            return True
        return False

    def _emit_dedup_summary(self, key: tuple):
        """Emit a summary entry for suppressed duplicates."""
        state = self._dedup_state.get(key)
        if not state or state["count"] <= 0:
            return
        agent = key[0]
        log_type = key[1]
        count = state["count"]
        first_tick = state["first_tick"]
        last_tick = state["last_tick"]
        entry = {
            "ts": self._timestamp,
            "tick": self._tick,
            "agent": agent,
            "type": log_type,
            "direction": "OUTPUT",
            "source": state.get("source", "rule"),
            "status": "ok",
            "detail": f"[×{count} ticks {first_tick}–{last_tick}] {state['detail']}",
        }
        self._entries.append(entry)

    def log(
        self,
        agent: str,
        log_type: str,
        direction: str,
        detail: str,
        source: str = "rule",
        status: str = "ok",
        data: Optional[dict] = None,
    ):
        """
        Append one audit entry (with deduplication for repeated routine entries).

        Args:
            agent: Component name (SensorAgent, RiskAgent, LLM, Guardrail, etc.)
            log_type: Category (SENSOR_CHECK, RISK_CALC, LLM_CALL, DECISION, etc.)
            direction: INPUT / OUTPUT / DECISION
            detail: Human-readable summary
            source: rule / llm / physics
            status: ok / fail / blocked / delayed
            data: Optional structured data dict
        """
        key = self._dedup_key(agent, log_type, detail)

        # Check for deduplication
        if self._should_deduplicate(agent, log_type, detail):
            state = self._dedup_state[key]
            state["count"] += 1
            state["last_tick"] = self._tick
            # Emit periodic summary so the log isn't totally silent
            if state["count"] % self.DEDUP_SUMMARY_INTERVAL == 0:
                with self._lock:
                    self._emit_dedup_summary(key)
            return

        # Not a duplicate — flush any previous dedup state for this key
        prev = self._dedup_state.get(key)
        if prev and prev["count"] > 0:
            with self._lock:
                self._emit_dedup_summary(key)

        # Update dedup tracking
        self._dedup_state[key] = {
            "detail": detail,
            "count": 0,
            "first_tick": self._tick,
            "last_tick": self._tick,
            "source": source,
        }

        entry = {
            "ts": self._timestamp,
            "tick": self._tick,
            "agent": agent,
            "type": log_type,
            "direction": direction,
            "source": source,
            "status": status,
            "detail": detail,
        }
        if data:
            entry["data"] = data
        with self._lock:
            self._entries.append(entry)

    def drain(self) -> list[dict]:
        """Return and clear all entries for this tick."""
        with self._lock:
            entries = self._entries
            self._entries = []
        return entries

    def flush_dedup(self):
        """Flush all pending dedup summaries (call at end of simulation)."""
        with self._lock:
            for key in list(self._dedup_state.keys()):
                self._emit_dedup_summary(key)
            self._dedup_state.clear()

    def clear(self):
        """Discard all buffered entries (used on reset)."""
        with self._lock:
            self._entries.clear()
        self._dedup_state.clear()
