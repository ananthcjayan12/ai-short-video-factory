from __future__ import annotations

from shorts_factory.editorial_v3 import (
    V3BeatLayout,
    V3Choreography,
    V3EditorialBeat,
    V3EditorialSequenceLayout,
    V3EditorialSequenceRecord,
    V3LayoutElement,
    _compile_graphics_beat,
    _load_sequence_plan_checkpoint,
    _normalize_sequence_layout,
    build_v3_editorial_sequence_plan,
)
from shorts_factory.io import write_json
from shorts_factory.models import DirectorPlan, Scene


def _scene(
    scene_id: str,
    start: float,
    end: float,
    *,
    scene_type: str,
    renderer: str,
) -> Scene:
    return Scene(
        scene_id=scene_id,
        start=start,
        end=end,
        type=scene_type,
        renderer=renderer,
        narration_excerpt=f"Narration for {scene_id}",
        purpose=f"Purpose {scene_id}",
        visual_brief=f"Visual brief {scene_id}",
    )


def test_v3_plan_preserves_real_mixed_media_adjacency(monkeypatch):
    monkeypatch.setenv("SVF_EDITORIAL_BEATS_PER_SEQUENCE", "2")
    monkeypatch.setenv("SVF_EDITORIAL_MAX_SEQUENCE_SECONDS", "16")
    director = DirectorPlan(
        episode_id="mixed-v3",
        duration_seconds=20,
        visual_thesis="Graphics hand off into real proof and back.",
        scenes=[
            _scene("S01", 0, 4, scene_type="talking_head", renderer="manual_talking_head"),
            _scene("S02", 4, 8, scene_type="motion_graphic", renderer="hyperframes"),
            _scene("S03", 8, 12, scene_type="screen_recording", renderer="playwright"),
            _scene("S04", 12, 16, scene_type="diagram", renderer="hyperframes"),
            _scene("S05", 16, 20, scene_type="talking_head", renderer="manual_talking_head"),
        ],
    )

    plan = build_v3_editorial_sequence_plan(director, theme="editorial")

    assert [sequence.scene_ids for sequence in plan.sequences] == [
        ["S01", "S02"],
        ["S03", "S04", "S05"],
    ]
    assert "Stock-Select V3" in plan.visual_bible["creative_contract"]
    assert "sequence-local" in plan.visual_bible["timing_rule"]


def test_v3_creative_contract_has_no_phrase_anchor_or_checkpoint_fields():
    assert "anchor_text" not in V3Choreography.model_fields
    assert "anchor_occurrence" not in V3Choreography.model_fields
    assert "review_checkpoints" not in V3EditorialBeat.model_fields
    assert "initially_visible" not in V3LayoutElement.model_fields


def test_v3_plan_checkpoint_resumes_only_complete_matching_timeline(tmp_path):
    director = DirectorPlan(
        episode_id="resume-v3",
        duration_seconds=4,
        visual_thesis="Resume accepted creative work.",
        scenes=[_scene("S01", 0, 4, scene_type="motion_graphic", renderer="hyperframes")],
    )
    expected = build_v3_editorial_sequence_plan(director, theme="editorial")
    saved = expected.model_copy(update={
        "sequences": [
            expected.sequences[0].model_copy(update={
                "layout": V3EditorialSequenceLayout(
                    sequence_id="Q01",
                    beats=[V3EditorialBeat(scene_id="S01", renderer="hyperframes")],
                )
            })
        ]
    })
    path = tmp_path / "editorial_sequence_plan.json"
    write_json(path, saved)

    assert _load_sequence_plan_checkpoint(path, expected) == saved

    changed = build_v3_editorial_sequence_plan(
        director.model_copy(update={"scenes": [
            _scene("S01", 0, 3.5, scene_type="motion_graphic", renderer="hyperframes")
        ]}),
        theme="editorial",
    )
    assert _load_sequence_plan_checkpoint(path, changed) is None


def test_normalizer_converts_obvious_master_clock_choreography_to_sequence_local():
    scene = _scene("S02", 6.10, 14.64, scene_type="motion_graphic", renderer="hyperframes")
    director = DirectorPlan(
        episode_id="timing-v3",
        duration_seconds=14.64,
        visual_thesis="Use one numeric clock at the creative boundary.",
        scenes=[scene],
    )
    record = V3EditorialSequenceRecord(
        sequence_id="Q01",
        scene_ids=["S02"],
        start=6.10,
        end=14.64,
    )
    candidate = V3EditorialSequenceLayout(
        sequence_id="Q01",
        canvas_duration=8.54,
        beats=[
            V3EditorialBeat(
                scene_id="S02",
                renderer="hyperframes",
                layout=V3BeatLayout(elements=[
                    V3LayoutElement(
                        id="b01_counter",
                        type="metric_counter",
                        description="A workload counter",
                        label="30-40",
                        position={"left": 10, "top": 15, "width": 75, "height": 60},
                    )
                ]),
                gsap_choreography=[
                    V3Choreography(
                        target_id="b01_counter",
                        enter_type="count_up",
                        at_offset=12.60,
                        duration=0.8,
                    )
                ],
            )
        ],
    )

    normalized = _normalize_sequence_layout(candidate, record=record, director=director)

    assert normalized.beats[0].time_start == 0.0
    assert normalized.beats[0].time_end == 8.54
    assert normalized.beats[0].gsap_choreography[0].at_offset == 6.5


def test_base_media_is_authoritative_even_if_model_attempts_to_draw_it():
    scene = _scene("S03", 0, 4, scene_type="screen_recording", renderer="playwright")
    director = DirectorPlan(
        episode_id="proof-v3",
        duration_seconds=4,
        visual_thesis="Real application footage remains the proof.",
        scenes=[scene],
    )
    record = V3EditorialSequenceRecord(
        sequence_id="Q01",
        scene_ids=["S03"],
        start=0,
        end=4,
    )
    candidate = V3EditorialSequenceLayout(
        beats=[
            V3EditorialBeat(
                scene_id="S03",
                renderer="playwright",
                overlay_intent="Small callout only",
                layout=V3BeatLayout(elements=[
                    V3LayoutElement(id="b01_fake_ui", label="FAKE UI")
                ]),
                gsap_choreography=[V3Choreography(target_id="b01_fake_ui")],
            )
        ]
    )

    normalized = _normalize_sequence_layout(candidate, record=record, director=director)

    assert normalized.beats[0].renderer == "playwright"
    assert normalized.beats[0].layout is None
    assert normalized.beats[0].gsap_choreography == []
    assert normalized.beats[0].overlay_intent == "Small callout only"


def test_v3_compiler_builds_renderer_bookkeeping_deterministically():
    scene = _scene("S02", 6.10, 14.64, scene_type="motion_graphic", renderer="hyperframes")
    beat = V3EditorialBeat(
        beat_id="b01",
        scene_id="S02",
        renderer="hyperframes",
        time_start=0.0,
        time_end=8.54,
        narration_text="Narration for S02",
        layout=V3BeatLayout(
            type="evidence_board",
            elements=[
                V3LayoutElement(
                    id="b01_inbox",
                    type="evidence_card",
                    description="An inbox establishes the workload.",
                    label="INBOX",
                    position={"left": 7, "top": 10, "width": 52, "height": 36},
                ),
                V3LayoutElement(
                    id="b01_counter",
                    type="metric_counter",
                    description="The request count becomes the payoff.",
                    label="30-40",
                    position={"left": 45, "top": 48, "width": 48, "height": 38},
                ),
            ],
        ),
        gsap_choreography=[
            V3Choreography(
                target_id="b01_counter",
                enter_type="count_up",
                at_offset=6.5,
                duration=0.8,
            )
        ],
    )

    compiled = _compile_graphics_beat(beat, scene=scene, theme="editorial")

    assert compiled.start == 6.10
    assert compiled.end == 14.64
    future = next(element for element in compiled.elements if element.element_id == "b01_counter")
    assert future.initially_visible is False
    reveals = [
        action for action in compiled.actions
        if action.target_id == "b01_counter" and action.action == "reveal"
    ]
    assert len(reveals) == 1
    assert all(action.anchor_text == "numeric_timing" for action in compiled.actions if action.action != "hold")
    assert max(compiled.review_checkpoints) <= 8.54
