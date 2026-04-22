"""
PRIPYAT-1986 Configuration
Centralized config for the Chernobyl crisis response simulation.

Azure Migration Notes:
- OPENAI_BASE_URL → Azure OpenAI endpoint
- OPENAI_API_KEY → Azure OpenAI key
- EVENT_BUS → Azure Event Hubs connection string
- STATE_STORE → Azure Cosmos DB connection string
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM Configuration ──────────────────────────────────────────────
# Works with both OpenAI and Azure OpenAI (same SDK)
LLM_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    # For Azure OpenAI, set:
    # OPENAI_BASE_URL=https://<resource>.openai.azure.com/
    # OPENAI_API_KEY=<azure-key>
    # OPENAI_MODEL=<deployment-name>
    "azure_api_version": os.getenv("AZURE_API_VERSION", "2024-12-01-preview"),
    "use_azure": os.getenv("USE_AZURE", "false").lower() == "true",
    # AI reasoning settings
    "enabled": os.getenv("LLM_ENABLED", "true").lower() == "true",
    "timeout_s": float(os.getenv("LLM_TIMEOUT", "5.0")),
    "max_retries": 1,
    "temperature_decision": 0.2,   # Low for deterministic safety decisions
    "temperature_risk": 0.3,       # Slightly higher for nuanced risk assessment
    "max_tokens_decision": 300,
    "max_tokens_risk": 250,
    "decision_points_only": True,  # Only call LLM at meaningful timeline events
}

# ── Simulation Parameters ──────────────────────────────────────────
SIMULATION = {
    "speed_multiplier": int(os.getenv("SIM_SPEED", "60")),  # 60x = 1 min per real hour
    "start_time": "1986-04-25T23:00:00",  # Test begins at 23:00
    "sim_start_from": "1986-04-25T18:00:00",  # Web UI starts playback from 18:00
    "explosion_time": "1986-04-26T01:23:40",
    "tick_interval_sec": 1.0,  # How often simulator emits events
}

# ── Reactor Safety Thresholds (RBMK-1000) ─────────────────────────
# Based on INSAG-7 report and RBMK operating manuals
THRESHOLDS = {
    "power_mw": {
        "nominal": 3200,       # Full rated power
        "test_target": 700,    # Planned test power level
        "danger_low": 200,     # Below this = xenon poisoning risk
        "critical_low": 30,    # Near-zero → positive void coefficient
        "scram_trigger": 100,  # AI should trigger AZ-5 below this
    },
    "control_rods": {
        "minimum_safe": 30,    # Minimum rods inserted for safe operation
        "critical_low": 15,    # INSAG-7: below 15 = immediate danger
        "actual_at_explosion": 6,  # Only 6-8 rods were inserted
    },
    "coolant_flow_m3h": {
        "nominal": 8000,
        "low_warning": 6000,
        "critical_low": 4000,
    },
    "steam_pressure_mpa": {
        "nominal": 6.5,
        "high_warning": 7.0,
        "critical_high": 7.5,
    },
    "temperature_c": {
        "nominal": 280,
        "high_warning": 300,
        "critical_high": 320,
    },
    "radiation_mrem_h": {
        "background": 0.01,
        "elevated": 1.0,
        "dangerous": 100,
        "lethal_immediate": 10000,
    },
}

# ── Risk Scoring ───────────────────────────────────────────────────
RISK_CONFIG = {
    "escalation_threshold": 85,   # Auto-escalate to Decision Agent
    "warning_threshold": 60,      # Yellow alert
    "weights": {
        "power_anomaly": 0.30,
        "rod_position": 0.25,
        "coolant_anomaly": 0.15,
        "steam_pressure": 0.15,
        "temperature": 0.10,
        "radiation": 0.05,
    },
}

# ── Evacuation Parameters ──────────────────────────────────────────
EVACUATION = {
    "pripyat_population": 49000,
    "buses_available": 1200,     # Actual number mobilized (eventually)
    "bus_capacity": 45,
    "pripyat_coords": (51.4045, 30.0542),
    "safe_radius_km": 30,       # Initial exclusion zone
    "routes": [
        {"name": "North → Chernihiv", "distance_km": 80, "capacity_factor": 1.0},
        {"name": "South → Ivankiv", "distance_km": 50, "capacity_factor": 0.8},
        {"name": "West → Poliske", "distance_km": 40, "capacity_factor": 0.6},
    ],
}

# ── Web Dashboard ─────────────────────────────────────────────────
WEB_CONFIG = {
    "host": os.getenv("WEB_HOST", "0.0.0.0"),
    "port": int(os.getenv("WEB_PORT", "8000")),
    "static_dir": os.path.join(os.path.dirname(__file__), "static"),
}

# ── Dyatlov Adversarial Agent ─────────────────────────────────────
# Simulates Deputy Chief Engineer Anatoly Dyatlov's override attempts.
# Phase transitions align with CHERNOBYL_TIMELINE decision points.
DYATLOV_CONFIG = {
    "enabled": True,
    # Escalation phase transitions (Dyatlov's behavior changes at these timestamps)
    "phase_transitions": {
        0: "1986-04-25T13:00:00",   # Calm — test preparation, cooperative
        1: "1986-04-26T00:28:00",   # Dismissive — after power drop to 30 MW
        2: "1986-04-26T00:43:00",   # Authoritarian — demands compliance
        3: "1986-04-26T01:00:00",   # Desperate — test must continue at all costs
        4: "1986-04-26T01:23:40",   # Denial — refuses to accept explosion
    },
    # Base override pressure (0-100) per phase
    "phase_pressure": {0: 10, 1: 40, 2: 65, 3: 85, 4: 30},
    # Maximum ticks a Dyatlov override can delay an LLM-sourced decision
    "max_delay_ticks": 3,
    # LLM settings (higher temp for dramatic variation in dialogue)
    "temperature": 0.7,
    "max_tokens": 150,
}

# ── Security & Governance (Azure Production) ──────────────────────
# Reference: docs/security-model.md for full details
SECURITY = {
    "auth_provider": "Azure Entra ID",  # Identity provider
    "rbac_roles": ["Operator", "Supervisor", "Admin", "Auditor"],
    "secret_store": "Azure Key Vault",  # No .env in production
    "audit_retention_days": 365,         # 1 year for compliance
    "audit_partition_key": "{tick}_{agent}_{timestamp}",  # Immutable Cosmos DB records
    "network": "VNET + Private Endpoints",  # No public PaaS access
    "monitoring": "Azure Monitor + Log Analytics",
    "alert_rules": {
        "llm_latency_breach": "avg(llm_latency_ms) > 5000 over 1 min",
        "pipeline_failure": "unhandled exception in agent pipeline",
        "risk_critical": "risk_score > 85 sustained 3+ ticks",
        "high_fallback_rate": "llm_fallback / total_ticks > 0.5 over 5 min",
    },
}

# ── Output ─────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
STATE_FILE = os.path.join(OUTPUT_DIR, "agent_state.json")
LOG_FILE = os.path.join(OUTPUT_DIR, "simulation.log")
