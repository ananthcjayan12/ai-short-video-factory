from pathlib import Path

import pytest

from shorts_factory.agents import MockAgent
from shorts_factory.io import write_json
from shorts_factory.models import DirectorPlan, EpisodeBrief, GraphicsPlan
from shorts_factory.pipeline import generate_graphics_plan, generate_narration
from shorts_factory.project import ProjectStore
from shorts_factory.rendering.composition import build


def test_graphics_stage_creates_contracts_scene_previews_and_master(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    store.create(EpisodeBrief(
        episode_id="graphics-01", title="Invoice flow",
        pain_point="Invoices are lost between intake channels and project records.",
        industry="Test", role="Owner",
    ))
    generate_narration(store, "graphics-01", agent_kind="mock")
    project = store.project_dir("graphics-01")
    director = MockAgent({"episode_id": "graphics-01"}).run(
        stage="director", prompt="", output_model=DirectorPlan, request_dir=project / "_requests",
    )
    write_json(project / "03_director/director_plan.approved.json", director)

    plan = generate_graphics_plan(store, "graphics-01", agent_kind="mock")
    composition = build(project, preview=True, width=1080, height=1920)

    expected = {scene.scene_id for scene in director.scenes if scene.renderer in {"hyperframes", "static"}}
    assert {scene.scene_id for scene in plan.scenes} == expected
    assert (project / "08_graphics/graphics_manifest.json").is_file()
    assert (project / "08_graphics/master.html").is_file()
    assert (project / "09_composition/preview/index.html").is_file()
    assert all((project / f"08_graphics/scenes/{scene_id}.html").is_file() for scene_id in expected)
    assert "generated-graphic" in composition.read_text(encoding="utf-8")
    assert "timeline-controls" in composition.read_text(encoding="utf-8")
    assert "master-audio" in composition.read_text(encoding="utf-8")


def test_graphics_contract_rejects_actions_for_unknown_objects():
    with pytest.raises(ValueError, match="unknown object"):
        GraphicsPlan.model_validate({
            "episode_id": "bad-graphics",
            "duration_seconds": 5,
            "creative_thesis": "Explain the workflow",
            "warnings": [],
            "scenes": [{
                "scene_id": "S01", "start": 0, "end": 5,
                "scene_shell": "flow_stage", "motion_grammar": "flow",
                "layout_variant": "two-step", "visual_thesis": "A to B",
                "headline": "A to B", "support": "", "continuity_object": None,
                "objects": [{
                    "object_id": "a", "object_type": "process", "role": "source",
                    "label": "A", "detail": "Start", "slot": "left",
                }],
                "actions": [{
                    "at_seconds": 1, "action": "reveal", "target": "missing",
                    "value": None, "source": None,
                }],
            }],
        })
