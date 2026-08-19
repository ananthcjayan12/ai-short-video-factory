import pytest
from pydantic import ValidationError

from shorts_factory.custom_graphics import CustomGraphicsLayoutPlan
from shorts_factory.editorial_layout_validation import (
    CustomGraphicsLayoutDraft,
    _normalize_scene_local_timing,
)


def _layout_payload():
    return {
        "engine_version": "custom_html_v1",
        "scene_id": "S01",
        "start": 0.0,
        "end": 6.1,
        "theme": "editorial",
        "visual_thesis": "An inbox becomes a visible workload counter.",
        "headline": "EVERY MORNING",
        "support": "30-40 QUOTE REQUESTS",
        "layout_style": "asymmetric whiteboard workload field",
        "opening_state": "One inbox sits alone on the board.",
        "payoff_state": "The inbox is surrounded by a visible request volume.",
        "elements": [
            {
                "element_id": "inbox",
                "kind": "email",
                "role": "primary",
                "label": "INBOX",
                "detail": "",
                "visual_form": "large hand-drawn inbox tray",
                "frame": {"x": 5, "y": 8, "width": 55, "height": 58, "rotation": 0, "depth": "foreground"},
                "initially_visible": True,
            },
            {
                "element_id": "volume_counter",
                "kind": "metric",
                "role": "supporting",
                "label": "30-40",
                "detail": "quote requests",
                "visual_form": "large handwritten workload counter",
                "frame": {"x": 48, "y": 46, "width": 44, "height": 38, "rotation": 0, "depth": "foreground"},
                "initially_visible": False,
            },
        ],
        "actions": [
            {
                "cue_id": "cue_inbox_transform",
                "action": "transform",
                "target_id": "inbox",
                "anchor_text": "Every morning",
                "anchor_occurrence": 0,
                "at_seconds": 0.2,
                "duration_seconds": 0.6,
                "direction": "in",
                "value": "fills with requests",
            }
        ],
        "review_checkpoints": [0.5, 5.0],
    }


def test_semantically_invalid_layout_survives_draft_schema_for_repair():
    draft = CustomGraphicsLayoutDraft.model_validate(_layout_payload())
    assert draft.elements[1].element_id == "volume_counter"

    with pytest.raises(ValidationError, match="future element volume_counter requires exactly one reveal"):
        CustomGraphicsLayoutPlan.model_validate(draft.model_dump(mode="json"))


def test_repaired_draft_converts_to_strict_layout():
    payload = _layout_payload()
    payload["actions"].append({
        "cue_id": "cue_volume_reveal",
        "action": "reveal",
        "target_id": "volume_counter",
        "anchor_text": "thirty to forty",
        "anchor_occurrence": 0,
        "at_seconds": 2.0,
        "duration_seconds": 0.6,
        "direction": "in",
        "value": None,
    })
    draft = CustomGraphicsLayoutDraft.model_validate(payload)
    strict = CustomGraphicsLayoutPlan.model_validate(draft.model_dump(mode="json"))
    assert strict.scene_id == "S01"
    assert [action.action for action in strict.actions].count("reveal") == 1


def test_absolute_scene_clock_is_normalized_to_local_seconds_before_strict_validation():
    payload = _layout_payload()
    payload.update({"scene_id": "S02", "start": 6.1, "end": 14.64})
    payload["actions"] = [
        {
            "cue_id": "cue_inbox_transform",
            "action": "transform",
            "target_id": "inbox",
            "anchor_text": "Each email",
            "anchor_occurrence": 0,
            "at_seconds": 6.3,
            "duration_seconds": 0.6,
            "direction": "in",
            "value": "starts the workflow",
        },
        {
            "cue_id": "cue_volume_reveal",
            "action": "reveal",
            "target_id": "volume_counter",
            "anchor_text": "choose the right Outlook template",
            "anchor_occurrence": 0,
            "at_seconds": 12.6,
            "duration_seconds": 0.6,
            "direction": "in",
            "value": None,
        },
    ]
    payload["review_checkpoints"] = [6.1, 12.6, 14.64]

    draft = CustomGraphicsLayoutDraft.model_validate(payload)
    normalized = _normalize_scene_local_timing(draft)

    assert normalized.review_checkpoints == pytest.approx([0.0, 6.5, 8.54])
    assert [action.at_seconds for action in normalized.actions] == pytest.approx([0.2, 6.5])
    strict = CustomGraphicsLayoutPlan.model_validate(normalized.model_dump(mode="json"))
    assert strict.scene_id == "S02"
