import unittest

from agents import AgentAction, AlertLevel, RecommendationAgent
from governance import SafetyKernel
from orchestrator import Orchestrator
from timeline_data import ReactorState


def reactor_state(**overrides) -> ReactorState:
    values = {
        "timestamp": "1986-04-26T00:30:00",
        "power_mw": 700.0,
        "control_rods_inserted": 100,
        "coolant_flow_m3h": 8000.0,
        "steam_pressure_mpa": 6.5,
        "temperature_c": 280.0,
        "radiation_mrem_h": 0.01,
        "eccs_active": True,
        "event_description": "",
        "actual_human_decision": "",
        "tags": ["manual"],
    }
    values.update(overrides)
    return ReactorState(**values)


class SafetyKernelTests(unittest.TestCase):
    def test_safe_telemetry_does_not_trip(self):
        kernel = SafetyKernel()
        self.assertIsNone(kernel.evaluate(reactor_state()))
        self.assertFalse(kernel.reactor_scrammed)

    def test_raw_critical_telemetry_trips_once_and_is_not_overridable(self):
        kernel = SafetyKernel()
        action = kernel.evaluate(reactor_state(control_rods_inserted=10))

        self.assertIsNotNone(action)
        self.assertEqual(action.agent, "SafetyKernel")
        self.assertTrue(action.metadata["executed"])
        self.assertFalse(action.metadata["overridable"])
        self.assertEqual(action.metadata["execution_authority"], "deterministic_sis")
        self.assertIsNone(kernel.evaluate(reactor_state(control_rods_inserted=5)))

    def test_disabled_eccs_at_critical_low_power_trips_without_ai_score(self):
        action = SafetyKernel().evaluate(
            reactor_state(power_mw=30, control_rods_inserted=70, eccs_active=False)
        )
        self.assertIsNotNone(action)
        self.assertIn("ECCS unavailable", action.reasoning)


class HumanReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_high_risk_output_is_inert_pending_review(self):
        agent = RecommendationAgent(llm_client=None)
        proposals = await agent.process(reactor_state(), 90, [])

        self.assertTrue(any("SCRAM" in proposal.action for proposal in proposals))
        self.assertTrue(all(p.metadata["status"] == "pending_review" for p in proposals))
        self.assertTrue(all(not p.metadata["executed"] for p in proposals))
        self.assertFalse(agent.reactor_scrammed)

    async def test_rejection_is_final_and_executes_nothing(self):
        orchestrator = Orchestrator()
        proposal = AgentAction(
            agent="RecommendationAgent", timestamp="1986-04-26T00:30:00",
            action="ABORT TEST", reasoning="Unsafe test envelope",
            alert_level=AlertLevel.CRITICAL,
            metadata={"source": "rule", "status": "pending_review", "executed": False},
        )
        recommendation = orchestrator._register_recommendations([proposal])[0]
        result = orchestrator.review_recommendation(
            recommendation.id, "reject", "Akimov", "Telemetry cross-check requested"
        )

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(orchestrator._reviewed_actions, [])
        with self.assertRaises(RuntimeError):
            orchestrator.review_recommendation(recommendation.id, "approve", "Dyatlov")

    async def test_human_approval_is_the_only_proposal_execution_path(self):
        orchestrator = Orchestrator()
        proposal = AgentAction(
            agent="RecommendationAgent", timestamp="1986-04-26T00:30:00",
            action="ABORT TEST", reasoning="Unsafe test envelope",
            alert_level=AlertLevel.CRITICAL,
            metadata={"source": "rule", "status": "pending_review", "executed": False},
        )
        recommendation = orchestrator._register_recommendations([proposal])[0]
        orchestrator.review_recommendation(
            recommendation.id, "approve", "Akimov", "Confirmed against procedure"
        )
        self.assertFalse(orchestrator.store.get_case(recommendation.id)["executed"])

        summary = await orchestrator.process_tick(reactor_state())
        executed = [d for d in summary["decisions"] if d["action"] == "ABORT TEST"]
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0]["source"], "human_approved")
        self.assertEqual(executed[0]["status"], "approved")
        self.assertTrue(orchestrator.store.get_case(recommendation.id)["executed"])

    async def test_safety_trip_does_not_wait_for_human_review(self):
        orchestrator = Orchestrator()
        summary = await orchestrator.process_tick(
            reactor_state(
                power_mw=30, control_rods_inserted=70, eccs_active=False,
                tags=["manual"],
            )
        )

        trips = [d for d in summary["decisions"] if d["source"] == "safety_kernel"]
        self.assertEqual(len(trips), 1)
        self.assertTrue(summary["state"]["reactor_scrammed"])
        self.assertEqual(summary["pending_recommendations"], [])


if __name__ == "__main__":
    unittest.main()
