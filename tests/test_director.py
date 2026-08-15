from shorts_factory.agents import MockAgent
from shorts_factory.director import normalize, production_budgets, validate_budgets
from shorts_factory.models import DirectorPlan, EpisodeBrief, ProjectSettings
from shorts_factory.pipeline import generate_director_plan, generate_narration
from shorts_factory.project import ProjectStore
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


def test_zero_generated_budget_does_not_cascade_into_all_talking_head(tmp_path: Path):
    agent = MockAgent({"episode_id": "budget-regression"})
    plan = agent.run(stage="director", prompt="", output_model=DirectorPlan, request_dir=tmp_path)
    plan = plan.model_copy(update={
        "budgets": plan.budgets.model_copy(update={"max_generated_assets": 0}),
    })

    normalized = normalize(plan)

    assert normalized.scenes[1].type == "talking_head"  # HyperFrames scene safely falls back.
    assert normalized.scenes[2].type == "screen_recording"  # Later non-generated visual survives.
    assert any(scene.type == "screen_recording" for scene in normalized.scenes)


def test_project_can_disable_all_talking_head_scenes(tmp_path: Path):
    agent = MockAgent({"episode_id": "visual-only"})
    plan = agent.run(stage="director", prompt="", output_model=DirectorPlan, request_dir=tmp_path)
    budgets = production_budgets(duration_seconds=plan.duration_seconds, include_talking_head=False)

    normalized = normalize(plan.model_copy(update={"budgets": budgets}), include_talking_head=False)

    assert all(scene.type not in {"talking_head", "cta"} for scene in normalized.scenes)
    assert all(scene.renderer not in {"manual_talking_head", "infinite_talk"} for scene in normalized.scenes)
    assert validate_budgets(normalized) == []


def test_pipeline_owns_budgets_and_applies_project_wide_visual_only_policy(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    store.save_settings(ProjectSettings(include_talking_head=False))
    store.create(EpisodeBrief(
        episode_id="visual-pipeline", title="Visual workflow",
        pain_point="Manual review delays every invoice.", industry="Operations", role="Owner",
    ))
    generate_narration(store, "visual-pipeline", agent_kind="mock")

    plan = generate_director_plan(store, "visual-pipeline", agent_kind="mock")

    expected = production_budgets(duration_seconds=58, include_talking_head=False)
    assert plan.budgets == expected
    assert all(scene.type not in {"talking_head", "cta"} for scene in plan.scenes)
    assert all(scene.renderer not in {"manual_talking_head", "infinite_talk"} for scene in plan.scenes)
