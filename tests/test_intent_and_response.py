import unittest

from planning_agent.intent import route_request
from planning_agent.models import ScheduledTask, ScheduleResult
from planning_agent.rag import Passage
from planning_agent.responses import compose_response


class FakeModel:
    def __init__(self, response):
        self.response = response

    def chat(self, *_args, **_kwargs):
        return self.response


class IntentAndResponseTests(unittest.TestCase):
    def test_router_supports_rag_and_planning_together(self):
        decision = route_request(FakeModel('{"general":false,"rag":true,"planning":true}'), "schedule welding using the SOP")
        self.assertFalse(decision.general)
        self.assertTrue(decision.rag)
        self.assertTrue(decision.planning)

    def test_router_handles_malformed_json_with_conservative_fallback(self):
        decision = route_request(FakeModel("not json"), "Schedule welding according to the PPE SOP")
        self.assertTrue(decision.planning)
        self.assertTrue(decision.rag)
        self.assertEqual(decision.method, "rule-fallback")

    def test_composer_contains_structured_schedule_metadata(self):
        task = ScheduledTask("A", 8, 10, ("W3",), "M2", None, "high", 12, True, "optimized")
        result = ScheduleResult((task,), (), 2, {"workers": (), "machines": (), "vehicles": ()}, {"status": "OPTIMAL"})
        passage = Passage("Wear face protection", "Welding_SOP.pdf", "page 14", 0.9)
        response = compose_response(
            "Schedule created", route_request(FakeModel('{"general":false,"rag":true,"planning":true}'), "plan"),
            [passage], {"solver_seconds": 0.2}, result, "draft-1",
        )
        self.assertEqual(response["schedule"]["solver_status"], "OPTIMAL")
        self.assertEqual(response["schedule"]["approval_status"], "draft")
        self.assertEqual(response["sources"][0]["location"], "page 14")
        self.assertEqual(response["timing"]["total_seconds"], 0.2)


if __name__ == "__main__":
    unittest.main()
