from __future__ import annotations

import json

from shorts_factory.editorial_v3 import V3EditorialSequenceLayout
from shorts_factory.editorial_v3_schema import v3_provider_schema
from shorts_factory.integrations import _strict_schema


def _assert_strict_objects(node):
    if isinstance(node, list):
        for item in node:
            _assert_strict_objects(item)
        return
    if not isinstance(node, dict):
        return
    if node.get("type") == "object" or "properties" in node:
        properties = node.get("properties", {})
        assert node.get("additionalProperties") is False
        assert node.get("required") == list(properties)
    for value in node.values():
        _assert_strict_objects(value)


def test_v3_provider_schema_has_no_freeform_maps():
    schema = v3_provider_schema()
    encoded = json.dumps(schema)

    _assert_strict_objects(schema)
    assert '"params"' not in encoded
    assert '"css_tokens"' not in encoded
    assert '"position"' in encoded
    assert '"left"' in encoded
    assert '"top"' in encoded
    assert '"width"' in encoded
    assert '"height"' in encoded


def test_installed_v3_schema_survives_codex_strict_normalization():
    schema = V3EditorialSequenceLayout.model_json_schema()
    strict = _strict_schema(schema)

    _assert_strict_objects(strict)
    assert strict == schema


def test_provider_payload_validates_against_tolerant_local_model():
    payload = {
        "sequence_id": "Q01",
        "canvas_duration": 8.54,
        "visual_thesis": "One request becomes one visual proof.",
        "continuity_object": "request card",
        "beats": [
            {
                "beat_id": "b01",
                "scene_id": "S02",
                "renderer": "hyperframes",
                "time_start": 0.0,
                "time_end": 8.54,
                "narration_text": "Work out the shipment.",
                "transition_in": "Request card enters from the previous beat.",
                "transition_out": "The card resolves into the next proof.",
                "overlay_intent": "",
                "layout": {
                    "type": "evidence_board",
                    "background": "paper field",
                    "elements": [
                        {
                            "id": "b01_request",
                            "type": "evidence_card",
                            "description": "Shipment request card",
                            "label": "REQUEST",
                            "position": {
                                "left": 10.0,
                                "top": 16.0,
                                "width": 80.0,
                                "height": 60.0,
                            },
                        }
                    ],
                },
                "gsap_choreography": [
                    {
                        "target_id": "b01_request",
                        "enter_type": "scale_reveal",
                        "at_offset": 0.35,
                        "duration": 0.6,
                    }
                ],
            }
        ],
    }

    parsed = V3EditorialSequenceLayout.model_validate(payload)

    assert parsed.beats[0].layout is not None
    assert parsed.beats[0].layout.elements[0].css_tokens == {}
    assert parsed.beats[0].gsap_choreography[0].params == {}
