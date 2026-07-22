import tempfile
import unittest
from pathlib import Path

from case_store import CaseAuditStore
from evaluation import LABELS, run_evaluation
from orchestrator import Orchestrator
from timeline_data import ReactorState


def state(**overrides):
    values = {
        "timestamp": "1986-04-26T00:40:00",
        "power_mw": 500.0,
        "control_rods_inserted": 70,
        "coolant_flow_m3h": 8000.0,
        "steam_pressure_mpa": 6.5,
        "temperature_c": 280.0,
        "radiation_mrem_h": 0.01,
        "eccs_active": False,
        "event_description": "ECCS disabled during test",
        "actual_human_decision": "Continue test",
        "tags": ["manual"],
    }
    values.update(overrides)
    return ReactorState(**values)


class CaseAndAuditPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_case_contains_agent_input_and_review_is_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CaseAuditStore(str(Path(directory) / "test.db"))
            orchestrator = Orchestrator(store=store, scope="manual")

            summary = await orchestrator.process_tick(state())
            case_id = summary["pending_recommendations"][0]["id"]
            case = store.get_case(case_id)

            self.assertEqual(case["status"], "pending_review")
            self.assertEqual(case["scope"], "manual")
            self.assertEqual(case["agent_input"]["reactor"]["power_mw"], 500.0)
            self.assertIn("component_scores", case["agent_input"]["risk"])
            self.assertTrue(case["trace"])
            self.assertFalse(case["evidence"]["authority_boundary"]["agent_actuator_authority"])

            orchestrator.review_recommendation(
                case_id, "reject", "Shift Supervisor", "ECCS must be restored first",
            )
            reviewed = store.get_case(case_id)
            self.assertEqual(reviewed["status"], "rejected")
            self.assertEqual(reviewed["reviewer"], "Shift Supervisor")
            self.assertFalse(reviewed["executed"])

            event_types = {event["event_type"] for event in store.list_audit(entity_id=case_id)}
            self.assertEqual(event_types, {"case_created", "case_reviewed"})
            self.assertGreater(len(store.list_audit(run_id=orchestrator.run_id)), 2)


class EvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_has_explainable_confusion_matrix(self):
        report = await run_evaluation()

        self.assertEqual(report["labels"], list(LABELS))
        self.assertEqual(report["summary"]["scenario_count"], len(report["results"]))
        self.assertEqual(
            sum(sum(row.values()) for row in report["confusion_matrix"].values()),
            len(report["results"]),
        )
        self.assertTrue(all(item["explanation"]["authority"] for item in report["results"]))
        self.assertEqual(report["methodology"]["model_calls"], "disabled")


if __name__ == "__main__":
    unittest.main()
