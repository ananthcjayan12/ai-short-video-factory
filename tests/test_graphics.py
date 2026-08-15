import json
import math
from pathlib import Path

import pytest

from shorts_factory.agents import MockAgent
from shorts_factory.io import write_json
from shorts_factory.models import (
    DirectorPlan, EpisodeBrief, GraphicsPlan, WordTimestamp, WordTimestampBundle,
)
from shorts_factory import pipeline
from shorts_factory.pipeline import (
    _align_graphics_actions_to_words,
    _default_graphics_plan,
    _validate_graphics_storytelling_quality,
    generate_graphics_plan,
    generate_narration,
)
from shorts_factory.project import ProjectStore
from shorts_factory.rendering.composition import build


def test_graphics_stage_creates_contracts_scene_previews_and_master(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    store.create(EpisodeBrief(
        episode_id="graphics-01", title="Invoice flow",
        pain_point="Invoices are lost between intake channels and project records.",
        industry="Test", role="Owner", graphics_theme="whiteboard",
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
    assert plan.theme == "whiteboard"
    assert (project / "08_graphics/graphics_manifest.json").is_file()
    assert (project / "08_graphics/master.html").is_file()
    assert (project / "09_composition/preview/index.html").is_file()
    visual_report = json.loads((project / "_requests/graphics_visual_qa.json").read_text(encoding="utf-8"))
    graphics_manifest = json.loads((project / "08_graphics/graphics_manifest.json").read_text(encoding="utf-8"))
    assert visual_report["ok"] is True
    assert visual_report["fps"] == 60
    assert graphics_manifest["fps"] == 60
    assert graphics_manifest["total_frames"] == math.ceil(plan.duration_seconds * 60)
    assert all((project / f"08_graphics/scenes/{scene_id}.html").is_file() for scene_id in expected)
    assert all(scene.visual_world and scene.opening_state and scene.payoff_state for scene in plan.scenes)
    assert all(any(item.initially_visible for item in scene.objects) for scene in plan.scenes)
    assert all(len(scene.review_checkpoints) >= 2 for scene in plan.scenes)
    assert all(sum(item.frame is not None for item in scene.objects) >= 1 for scene in plan.scenes)
    rendered = composition.read_text(encoding="utf-8")
    assert "generated-graphic" in rendered
    assert "data-visual-world" in rendered
    assert "data-camera-move" in rendered
    assert "data-review-checkpoints" in rendered
    assert "has-frame" in rendered
    assert 'data-initially-visible="true"' in rendered
    assert 'data-initially-visible="false"' in rendered
    assert 'data-visibility-contract="explicit"' in rendered
    assert 'data-graphics-theme="whiteboard"' in rendered
    assert "object-index" not in rendered
    assert "timeline-controls" in rendered
    assert "master-audio" in rendered
    assert "function playbackFrame()" in rendered
    assert 'data-fps="60"' in rendered
    opening_findings = [item for item in visual_report["findings"] if item["moment"] == "opening frame"]
    assert len(opening_findings) == len(plan.scenes)
    assert all(not item["issues"] for item in opening_findings)


def test_graphics_quality_rejects_a_future_object_without_an_explicit_reveal(tmp_path: Path):
    director = MockAgent({"episode_id": "visibility-contract"}).run(
        stage="director", prompt="", output_model=DirectorPlan, request_dir=tmp_path,
    )
    graphics_scenes = [scene for scene in director.scenes if scene.renderer in {"hyperframes", "static"}]
    plan = _default_graphics_plan("visibility-contract", director, graphics_scenes)
    scene = plan.scenes[0]
    future = next(item for item in scene.objects if not item.initially_visible)
    broken_scene = scene.model_copy(update={
        "actions": [
            action for action in scene.actions
            if not (action.target == future.object_id and action.action == "reveal")
        ],
    })
    broken_plan = plan.model_copy(update={"scenes": [broken_scene, *plan.scenes[1:]]})

    with pytest.raises(RuntimeError, match="needs exactly one reveal"):
        _validate_graphics_storytelling_quality(broken_plan, require_anchors=False)


def test_graphics_quality_reports_global_and_scene_defects_together(tmp_path: Path):
    director = MockAgent({"episode_id": "quality-report"}).run(
        stage="director", prompt="", output_model=DirectorPlan, request_dir=tmp_path,
    )
    graphics_scenes = [scene for scene in director.scenes if scene.renderer in {"hyperframes", "static"}]
    plan = _default_graphics_plan("quality-report", director, graphics_scenes)
    first, second, *remaining = plan.scenes
    compressed_objects = [
        item.model_copy(update={
            "frame": item.frame.model_copy(update={"y": 10 + index * 4, "height": 10}),
        })
        for index, item in enumerate(first.objects)
    ]
    broken = plan.model_copy(update={
        "scenes": [
            first.model_copy(update={"objects": compressed_objects}),
            second.model_copy(update={"scene_shell": first.scene_shell}),
            *remaining,
        ],
    })

    with pytest.raises(RuntimeError) as exc_info:
        _validate_graphics_storytelling_quality(broken, require_anchors=False)

    message = str(exc_info.value)
    assert "Adjacent graphics scenes repeat" in message
    assert f"Graphics scene {first.scene_id} under-fills the portrait stage" in message


def test_graphics_quality_uses_second_bounded_repair_for_a_remaining_defect(tmp_path: Path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    store.create(EpisodeBrief(
        episode_id="quality-repairs", title="Invoice flow",
        pain_point="Invoices are lost between intake channels and project records.",
        industry="Test", role="Owner",
    ))
    generate_narration(store, "quality-repairs", agent_kind="mock")
    project = store.project_dir("quality-repairs")
    director = MockAgent({"episode_id": "quality-repairs"}).run(
        stage="director", prompt="", output_model=DirectorPlan, request_dir=project / "_requests",
    )
    write_json(project / "03_director/director_plan.approved.json", director)
    graphics_scenes = [scene for scene in director.scenes if scene.renderer in {"hyperframes", "static"}]
    good = _default_graphics_plan("quality-repairs", director, graphics_scenes)
    first, second, *remaining = good.scenes
    compressed_objects = [
        item.model_copy(update={
            "frame": item.frame.model_copy(update={"y": 10 + index * 4, "height": 10}),
        })
        for index, item in enumerate(first.objects)
    ]
    underfilled_scene = first.model_copy(update={"objects": compressed_objects})
    initial = good.model_copy(update={
        "scenes": [
            underfilled_scene,
            second.model_copy(update={"scene_shell": first.scene_shell}),
            *remaining,
        ],
    })
    first_repair = good.model_copy(update={"scenes": [underfilled_scene, second, *remaining]})
    responses = [initial, first_repair, good]
    stages: list[str] = []
    prompts: list[str] = []

    class SequenceAgent:
        def run(self, *, stage, prompt, **_kwargs):
            stages.append(stage)
            prompts.append(prompt)
            return responses.pop(0)

    monkeypatch.setattr(pipeline, "_structured_agent", lambda *_args, **_kwargs: SequenceAgent())
    monkeypatch.setattr(pipeline, "_validate_graphics_visuals", lambda *_args, **_kwargs: None)

    repaired = generate_graphics_plan(store, "quality-repairs")

    assert repaired == good
    assert stages == [
        "graphics_builder", "graphics_builder_quality_repair", "graphics_builder_quality_repair_2",
    ]
    assert "Adjacent graphics scenes repeat" in prompts[1]
    assert "under-fills the portrait stage" in prompts[1]
    assert "under-fills the portrait stage" in prompts[2]


def test_graphics_actions_snap_to_the_selected_word_occurrence_and_next_frame():
    director = DirectorPlan.model_validate({
        "episode_id": "word-cues", "duration_seconds": 3,
        "visual_thesis": "Exact word cues drive motion.",
        "scenes": [{
            "scene_id": "S01", "start": 0, "end": 3, "type": "motion_graphic",
            "renderer": "hyperframes", "narration_excerpt": "hello again hello",
            "purpose": "Show exact timing", "visual_brief": "One object moves.",
        }],
    })
    plan = GraphicsPlan.model_validate({
        "episode_id": "word-cues", "duration_seconds": 3, "creative_thesis": "Exact cues",
        "scenes": [{
            "scene_id": "S01", "start": 0, "end": 3, "scene_shell": "spatial_stage",
            "motion_grammar": "match_move", "layout_variant": "one moving object",
            "visual_thesis": "The object follows the second hello", "headline": "HELLO",
            "support": "", "visual_world": "one stage", "opening_state": "left",
            "payoff_state": "right", "review_checkpoints": [0.4, 2.5],
            "objects": [{
                "object_id": "word", "object_type": "text", "role": "subject",
                "label": "HELLO", "detail": "", "slot": "hero",
                "frame": {"x": 10, "y": 20, "width": 30, "height": 20},
            }],
            "actions": [{
                "at_seconds": 0, "action": "move", "target": "word",
                "anchor_text": "hello", "anchor_occurrence": 1, "direction": "right",
            }],
        }],
    })
    words = WordTimestampBundle(
        episode_id="word-cues", audio_duration_seconds=3, whisper_model="test",
        audio_sha256="a" * 64,
        words=[
            WordTimestamp(index=0, paragraph_id="P01", beat_id="B01", word="hello", start=0.101, end=0.25),
            WordTimestamp(index=1, paragraph_id="P01", beat_id="B01", word="again", start=0.421, end=0.61),
            WordTimestamp(index=2, paragraph_id="P01", beat_id="B01", word="hello", start=0.751, end=0.94),
        ],
    )

    aligned = _align_graphics_actions_to_words(plan, director, words, fps=60)

    assert aligned.scenes[0].actions[0].at_seconds == pytest.approx(46 / 60, abs=1e-6)
    assert aligned.scenes[0].actions[0].at_seconds >= words.words[2].start


def test_graphics_usage_limit_stops_without_deterministic_fallback(tmp_path: Path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    store.create(EpisodeBrief(
        episode_id="graphics-limit", title="Invoice flow",
        pain_point="Invoices are lost between intake channels and project records.",
        industry="Test", role="Owner",
    ))
    generate_narration(store, "graphics-limit", agent_kind="mock")
    project = store.project_dir("graphics-limit")
    director = MockAgent({"episode_id": "graphics-limit"}).run(
        stage="director", prompt="", output_model=DirectorPlan, request_dir=project / "_requests",
    )
    write_json(project / "03_director/director_plan.approved.json", director)
    state_before = store.state("graphics-limit")

    class UsageLimitedAgent:
        def run(self, **_kwargs):
            raise RuntimeError("ERROR: You've hit your usage limit")

    monkeypatch.setattr(pipeline, "_structured_agent", lambda *_args, **_kwargs: UsageLimitedAgent())

    with pytest.raises(RuntimeError, match="usage limit is exhausted") as exc_info:
        generate_graphics_plan(store, "graphics-limit")

    assert "No deterministic fallback or new preview was generated" in str(exc_info.value)
    assert not (project / "08_graphics/graphics_plan.json").exists()
    assert not (project / "09_composition/preview/index.html").exists()
    assert store.state("graphics-limit") == state_before


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


def test_graphics_contract_rejects_freeform_frame_outside_stage():
    with pytest.raises(ValueError, match="extends too far outside"):
        GraphicsPlan.model_validate({
            "episode_id": "bad-frame",
            "duration_seconds": 5,
            "creative_thesis": "Explain the workflow",
            "scenes": [{
                "scene_id": "S01", "start": 0, "end": 5,
                "scene_shell": "metaphor_stage", "motion_grammar": "object_transformation",
                "layout_variant": "asymmetric-world", "visual_thesis": "A becomes B",
                "headline": "A becomes B", "support": "", "visual_world": "one evolving object",
                "opening_state": "A is unresolved", "payoff_state": "A visibly becomes B",
                "continuity_object": "a", "review_checkpoints": [1, 4],
                "objects": [{
                    "object_id": "a", "object_type": "artifact", "role": "source",
                    "label": "A", "detail": "Start", "slot": "left",
                    "frame": {"x": 90, "y": 10, "width": 20, "height": 20},
                    "visual_form": "torn source document",
                }],
                "actions": [{"at_seconds": 0, "action": "reveal", "target": "a"}],
            }],
        })
