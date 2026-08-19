from __future__ import annotations

from shorts_factory.editorial_graphics import build_editorial_sequence_plan
from shorts_factory.models import DirectorPlan, Scene
from shorts_factory.orchestrator import TASKS, default_config, resolve_task


def _scene(
    number: int,
    start: float,
    end: float,
    *,
    scene_type: str,
    renderer: str,
) -> Scene:
    return Scene(
        scene_id=f"S{number:02d}",
        start=start,
        end=end,
        type=scene_type,
        renderer=renderer,
        narration_excerpt=f"Narration for scene {number}",
        purpose=f"Purpose {number}",
        visual_brief=f"Visual brief {number}",
    )


def _mixed_director() -> DirectorPlan:
    return DirectorPlan(
        episode_id="mixed-media",
        duration_seconds=20,
        visual_thesis="A receipt moves from human story to proof and back to explanation.",
        scenes=[
            _scene(1, 0, 4, scene_type="talking_head", renderer="manual_talking_head"),
            _scene(2, 4, 8, scene_type="motion_graphic", renderer="hyperframes"),
            _scene(3, 8, 12, scene_type="screen_recording", renderer="playwright"),
            _scene(4, 12, 16, scene_type="talking_head", renderer="manual_talking_head"),
            _scene(5, 16, 20, scene_type="diagram", renderer="hyperframes"),
        ],
    )


def test_editorial_sequences_group_the_real_timeline(monkeypatch):
    monkeypatch.setenv("SVF_EDITORIAL_BEATS_PER_SEQUENCE", "2")
    monkeypatch.setenv("SVF_EDITORIAL_MAX_SEQUENCE_SECONDS", "16")

    plan = build_editorial_sequence_plan(_mixed_director(), theme="editorial")

    assert [sequence.scene_ids for sequence in plan.sequences] == [
        ["S01", "S02"],
        ["S03", "S04", "S05"],
    ]
    assert plan.sequences[0].next_scene_id == "S03"
    assert plan.sequences[1].previous_scene_id == "S02"
    assert "Playwright" in plan.visual_bible["screen_recording_rule"]
    assert "presenter" in plan.visual_bible["talking_head_rule"].lower()


def test_graphics_are_not_made_falsely_adjacent(monkeypatch):
    monkeypatch.setenv("SVF_EDITORIAL_BEATS_PER_SEQUENCE", "2")
    monkeypatch.setenv("SVF_EDITORIAL_MAX_SEQUENCE_SECONDS", "16")

    plan = build_editorial_sequence_plan(_mixed_director(), theme="editorial")
    flattened = [scene_id for sequence in plan.sequences for scene_id in sequence.scene_ids]

    assert flattened == ["S01", "S02", "S03", "S04", "S05"]
    # The old graphics-only continuity list effectively jumped S02 -> S05.
    # The editorial plan preserves the actual S03 screen proof and S04 presenter
    # beats between those two graphics scenes.
    first_graphics_index = flattened.index("S02")
    second_graphics_index = flattened.index("S05")
    assert flattened[first_graphics_index + 1:second_graphics_index] == ["S03", "S04"]


def test_sequence_duration_cap_prevents_oversized_batches(monkeypatch):
    monkeypatch.setenv("SVF_EDITORIAL_BEATS_PER_SEQUENCE", "3")
    monkeypatch.setenv("SVF_EDITORIAL_MAX_SEQUENCE_SECONDS", "16")
    director = DirectorPlan(
        episode_id="long-beats",
        duration_seconds=40,
        visual_thesis="Long proof beats stay bounded.",
        scenes=[
            _scene(1, 0, 10, scene_type="talking_head", renderer="manual_talking_head"),
            _scene(2, 10, 20, scene_type="motion_graphic", renderer="hyperframes"),
            _scene(3, 20, 30, scene_type="screen_recording", renderer="playwright"),
            _scene(4, 30, 40, scene_type="diagram", renderer="hyperframes"),
        ],
    )

    plan = build_editorial_sequence_plan(director, theme="editorial")

    assert [sequence.scene_ids for sequence in plan.sequences] == [
        ["S01"], ["S02"], ["S03"], ["S04"],
    ]


def test_split_graphics_routes_are_registered():
    task_ids = {task["id"] for task in TASKS}
    assert {"graphics_layout", "graphics_coder", "graphics_code_repair"} <= task_ids

    config = default_config()
    for task_id in ("graphics_layout", "graphics_coder", "graphics_code_repair"):
        assert task_id in config["tasks"]
        resolved = resolve_task(config, task_id)
        assert resolved["provider"] == "codex"
        assert resolved["model"] == "gpt-5.6-sol"
        assert resolved["capability"] == "structured"
