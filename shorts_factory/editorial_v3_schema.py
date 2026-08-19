from __future__ import annotations

from copy import deepcopy
from typing import Any


_INSTALLED = False


def _strict_object(properties: dict[str, Any]) -> dict[str, Any]:
    """Build an OpenAI/Codex strict-output-compatible object schema."""

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def v3_provider_schema() -> dict[str, Any]:
    """Provider-facing schema for the lightweight editorial V3 creative contract.

    The local Pydantic V3 models intentionally remain tolerant because the creative
    response is normalized before compilation. Codex/OpenAI structured output is
    stricter: every object property must be declared and required, and arbitrary
    dictionaries are not representable with ``additionalProperties: false``.

    Keep only the creative fields the compiler actually consumes. ``css_tokens``
    and choreography ``params`` are local optional metadata and therefore do not
    need to cross the provider boundary.
    """

    position = _strict_object({
        "left": {"type": "number"},
        "top": {"type": "number"},
        "width": {"type": "number"},
        "height": {"type": "number"},
    })
    element = _strict_object({
        "id": {"type": "string"},
        "type": {"type": "string"},
        "description": {"type": "string"},
        "label": {"type": "string"},
        "position": position,
    })
    beat_layout = _strict_object({
        "type": {"type": "string"},
        "background": {"type": "string"},
        "elements": {"type": "array", "items": element},
    })
    choreography = _strict_object({
        "target_id": {"type": "string"},
        "enter_type": {"type": "string"},
        "at_offset": {"type": "number"},
        "duration": {"type": "number"},
    })
    beat = _strict_object({
        "beat_id": {"type": "string"},
        "scene_id": {"type": "string"},
        "renderer": {"type": "string"},
        "time_start": {"type": "number"},
        "time_end": {"type": "number"},
        "narration_text": {"type": "string"},
        "transition_in": {"type": "string"},
        "transition_out": {"type": "string"},
        "overlay_intent": {"type": "string"},
        "layout": {"anyOf": [beat_layout, {"type": "null"}]},
        "gsap_choreography": {"type": "array", "items": choreography},
    })
    return _strict_object({
        "sequence_id": {"type": "string"},
        "canvas_duration": {"type": "number"},
        "visual_thesis": {"type": "string"},
        "continuity_object": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "beats": {"type": "array", "items": beat},
    })


def install_v3_provider_schema() -> None:
    """Use the strict provider schema only for the creative V3 output model."""

    global _INSTALLED
    if _INSTALLED:
        return

    from .editorial_v3 import V3EditorialSequenceLayout

    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        # Return a fresh object because downstream provider adapters may normalize
        # their copy of the schema before invoking a CLI/API.
        return deepcopy(v3_provider_schema())

    V3EditorialSequenceLayout.model_json_schema = classmethod(model_json_schema)
    _INSTALLED = True
