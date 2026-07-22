"""Reproducible, explainable policy evaluation for the governed control loop.

The benchmark intentionally disables network LLM calls. It evaluates the
authority boundary that must remain deterministic: monitor, route a proposal
to human review, or execute a narrow non-overridable protective trip.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from agents import RecommendationAgent, RiskAgent, SensorAgent
from governance import SafetyKernel
from timeline_data import ReactorState


LABELS = ("monitor", "human_review", "protective_trip")
EVAL_VERSION = "authority-boundary-v1"


@dataclass(frozen=True)
class EvalScenario:
    id: str
    title: str
    expected: str
    rationale: str
    state: ReactorState


def _state(**overrides) -> ReactorState:
    values = {
        "timestamp": "1986-04-26T01:00:00",
        "power_mw": 700,
        "control_rods_inserted": 80,
        "coolant_flow_m3h": 8000,
        "steam_pressure_mpa": 6.5,
        "temperature_c": 280,
        "radiation_mrem_h": 0.01,
        "eccs_active": True,
        "event_description": "Frozen evaluation fixture",
        "actual_human_decision": "None",
        "tags": ["manual", "eval"],
    }
    values.update(overrides)
    return ReactorState(**values)


SCENARIOS = (
    EvalScenario("nominal", "Nominal test envelope", "monitor",
                 "No safety threshold or review rule is active.", _state()),
    EvalScenario("early_reduction", "Controlled power reduction", "monitor",
                 "A controlled reduction with safety systems available remains observable.",
                 _state(power_mw=500, control_rods_inserted=70)),
    EvalScenario("coolant_warning", "Coolant warning band", "monitor",
                 "A warning is visible but remains below the hard-trip boundary.",
                 _state(coolant_flow_m3h=5500)),
    EvalScenario("eccs_disabled", "ECCS disabled", "human_review",
                 "Disabling a safety barrier creates an attributable supervisor case.",
                 _state(eccs_active=False, power_mw=500)),
    EvalScenario("test_envelope_breach", "Unsafe test envelope", "human_review",
                 "Low power and minimum shutdown margin require an abort recommendation.",
                 _state(power_mw=150, control_rods_inserted=30)),
    EvalScenario("radiation_release", "Dangerous radiation release", "human_review",
                 "Population action is a major decision and must be reviewed by a human.",
                 _state(radiation_mrem_h=100)),
    EvalScenario("low_power_no_eccs", "Low power without ECCS", "protective_trip",
                 "The final cooling barrier is unavailable in the unsafe low-power region.",
                 _state(power_mw=30, eccs_active=False)),
    EvalScenario("shutdown_margin_lost", "Shutdown margin lost", "protective_trip",
                 "Critical control-rod position directly activates the safety kernel.",
                 _state(control_rods_inserted=15)),
    EvalScenario("coolant_critical", "Critical coolant loss", "protective_trip",
                 "Critical coolant flow directly activates the safety kernel.",
                 _state(coolant_flow_m3h=4000)),
    EvalScenario("pressure_critical", "Critical steam pressure", "protective_trip",
                 "Critical steam pressure directly activates the safety kernel.",
                 _state(steam_pressure_mpa=7.5)),
    EvalScenario("temperature_critical", "Critical core temperature", "protective_trip",
                 "Critical core temperature directly activates the safety kernel.",
                 _state(temperature_c=320)),
)


async def run_evaluation() -> dict:
    matrix = {truth: {predicted: 0 for predicted in LABELS} for truth in LABELS}
    results = []

    for scenario in SCENARIOS:
        sensor = SensorAgent()
        risk = RiskAgent(llm_client=None)
        recommender = RecommendationAgent(llm_client=None)
        safety = SafetyKernel()

        alerts = sensor.process(scenario.state)
        risk_score, risk_message = await risk.process(scenario.state, alerts)
        trip = safety.evaluate(scenario.state)
        proposals = [] if trip else await recommender.process(scenario.state, risk_score, alerts)
        predicted = "protective_trip" if trip else ("human_review" if proposals else "monitor")
        matrix[scenario.expected][predicted] += 1

        results.append({
            "id": scenario.id,
            "title": scenario.title,
            "expected": scenario.expected,
            "predicted": predicted,
            "correct": predicted == scenario.expected,
            "expected_rationale": scenario.rationale,
            "telemetry": asdict(scenario.state),
            "explanation": {
                "risk_score": risk_score,
                "rule_score": risk_message.payload.get("rule_score"),
                "component_scores": risk_message.payload.get("component_scores", {}),
                "sensor_alerts": [
                    {"level": item.alert_level.value, "type": item.msg_type,
                     "detail": item.payload.get("detail", "")}
                    for item in alerts
                ],
                "safety_trip_reasons": trip.metadata.get("trip_reasons", []) if trip else [],
                "recommendations": [
                    {"action": item.action, "reasoning": item.reasoning,
                     "source": item.metadata.get("source", "rule")}
                    for item in proposals
                ],
                "authority": (
                    "deterministic_safety_kernel" if trip else
                    "human_supervisor_required" if proposals else "observation_only"
                ),
            },
        })

    total = len(results)
    correct = sum(item["correct"] for item in results)
    per_class = {}
    for label in LABELS:
        true_positive = matrix[label][label]
        support = sum(matrix[label].values())
        predicted_count = sum(matrix[truth][label] for truth in LABELS)
        per_class[label] = {
            "precision": round(true_positive / predicted_count, 3) if predicted_count else None,
            "recall": round(true_positive / support, 3) if support else None,
            "support": support,
        }

    non_trip_total = total - per_class["protective_trip"]["support"]
    false_trips = sum(matrix[truth]["protective_trip"] for truth in LABELS if truth != "protective_trip")
    return {
        "version": EVAL_VERSION,
        "labels": list(LABELS),
        "summary": {
            "scenario_count": total,
            "correct": correct,
            "accuracy": round(correct / total, 3),
            "protective_trip_recall": per_class["protective_trip"]["recall"],
            "human_review_recall": per_class["human_review"]["recall"],
            "false_protective_trip_rate": round(false_trips / non_trip_total, 3) if non_trip_total else 0,
        },
        "confusion_matrix": matrix,
        "per_class": per_class,
        "results": results,
        "methodology": {
            "model_calls": "disabled",
            "scope": "Frozen authority-routing and deterministic safety policy fixtures",
            "caveat": (
                "This is a software regression benchmark, not a nuclear safety certification. "
                "It does not establish physical-model validity or operational fitness."
            ),
        },
    }
