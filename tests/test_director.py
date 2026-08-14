from shorts_factory.agents import MockAgent
from shorts_factory.director import normalize, validate_budgets
from shorts_factory.models import DirectorPlan
from pathlib import Path


def test_pain001_director_plan_passes_budgets(tmp_path: Path):
    agent = MockAgent({"episode_id": "pain-001"})
    plan = agent.run(stage="director", prompt="", output_model=DirectorPlan, request_dir=tmp_path)
    plan = normalize(plan)
    assert validate_budgets(plan) == []
    assert plan.scenes[0].type == "talking_head"
    assert plan.scenes[-1].type == "cta"
    assert any(s.type == "screen_recording" for s in plan.scenes)
    assert any(s.type == "diagram" for s in plan.scenes)
