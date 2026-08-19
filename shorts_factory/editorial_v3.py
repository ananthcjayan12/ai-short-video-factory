from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import editorial_graphics as legacy
from .custom_graphics import (
    CustomGraphicsAction,
    CustomGraphicsElement,
    CustomGraphicsLayoutPlan,
    CustomGraphicsPackage,
    custom_package_summary,
    write_custom_graphics_package,
)
from .io import load_model, write_json
from .models import (
    DirectorPlan,
    EpisodeBrief,
    EpisodeStage,
    GraphicsFrame,
    GraphicsPlan,
    GraphicsTheme,
    Narration,
    WordTimestampBundle,
)
from .orchestrator import resolve_task
from .pipeline import (
    CustomGraphicsVisualValidationError,
    _run_graphics_agent,
    _structured_agent,
    _validate_custom_graphics_visuals,
    _validate_graphics_against_director,
    load_config,
)
from .progress import emit
from .project import ProjectStore
from .rendering.composition import build as build_composition


GRAPHICS_RENDERERS = {"hyperframes", "static"}

_CUSTOM_KIND = {
    "svg_map": "map",
    "svg_chart": "axis",
    "metric_counter": "metric",
    "text_headline": "headline",
    "evidence_card": "evidence",
    "pitch_diagram": "route",
    "spec_card": "document",
    "timeline_bar": "timeline",
    "stamp": "annotation",
    "annotation": "annotation",
    "image_frame": "artifact",
}
_ACTION_KIND = {
    "slide_left": "move",
    "slide_right": "move",
    "fade_in": "transform",
    "line_draw": "draw",
    "count_up": "count_to",
    "paper_drop": "move",
    "stamp_hit": "stamp",
    "formation_build": "merge",
    "bar_fill": "transform",
    "scale_reveal": "transform",
    "persist": "transform",
}
_DIRECTION = {
    "slide_left": "right",
    "slide_right": "left",
    "paper_drop": "down",
    "scale_reveal": "in",
    "fade_in": "in",
}


class V3LayoutElement(BaseModel):
    """Stock-Select-style creative element: descriptive, not renderer-executable."""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    type: str = "evidence_card"
    description: str = ""
    label: str = ""
    position: dict[str, float] = Field(default_factory=dict)
    css_tokens: dict[str, str] = Field(default_factory=dict)


class V3BeatLayout(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "evidence_board"
    background: str = ""
    elements: list[V3LayoutElement] = Field(default_factory=list)


class V3Choreography(BaseModel):
    model_config = ConfigDict(extra="allow")

    target_id: str = ""
    enter_type: str = "fade_in"
    at_offset: float = 0.0
    duration: float = 0.65
    params: dict[str, Any] = Field(default_factory=dict)


class V3EditorialBeat(BaseModel):
    """One approved Director scene inside a multi-beat creative canvas."""

    model_config = ConfigDict(extra="allow")

    beat_id: str = ""
    scene_id: str = ""
    renderer: str = ""
    time_start: float = 0.0
    time_end: float = 0.0
    narration_text: str = ""
    transition_in: str = ""
    transition_out: str = ""
    overlay_intent: str = ""
    layout: V3BeatLayout | None = None
    gsap_choreography: list[V3Choreography] = Field(default_factory=list)


class V3EditorialSequenceLayout(BaseModel):
    """Light creative-director contract modeled after stock-select V3."""

    model_config = ConfigDict(extra="allow")

    sequence_id: str = ""
    canvas_duration: float = 0.0
    visual_thesis: str = ""
    continuity_object: str | None = None
    beats: list[V3EditorialBeat] = Field(default_factory=list)


class V3EditorialSequenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_id: str
    scene_ids: list[str]
    start: float
    end: float
    previous_scene_id: str | None = None
    next_scene_id: str | None = None
    layout: V3EditorialSequenceLayout | None = None


class V3EditorialSequencePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "3.0"
    episode_id: str
    theme: GraphicsTheme
    visual_bible: dict[str, Any]
    sequences: list[V3EditorialSequenceRecord]


def build_v3_editorial_sequence_plan(
    director: DirectorPlan,
    *,
    theme: GraphicsTheme,
) -> V3EditorialSequencePlan:
    """Reuse mixed-media grouping, but attach the proven V3 creative boundary."""

    grouped = legacy.build_editorial_sequence_plan(director, theme=theme)
    return V3EditorialSequencePlan(
        episode_id=grouped.episode_id,
        theme=grouped.theme,
        visual_bible={
            **grouped.visual_bible,
            "creative_contract": (
                "Stock-Select V3 style: the creative model describes layout elements and numeric "
                "choreography only. Renderer bookkeeping is compiled deterministically afterward."
            ),
            "timing_rule": (
                "Every beat and choreography time exposed to the creative model is sequence-local. "
                "No narration phrase is used as an executable timing key."
            ),
        },
        sequences=[
            V3EditorialSequenceRecord(
                sequence_id=item.sequence_id,
                scene_ids=item.scene_ids,
                start=item.start,
                end=item.end,
                previous_scene_id=item.previous_scene_id,
                next_scene_id=item.next_scene_id,
            )
            for item in grouped.sequences
        ],
    )


def _sequence_local_words(
    words: WordTimestampBundle | None,
    *,
    start: float,
    end: float,
) -> list[dict[str, Any]]:
    if words is None:
        return []
    result: list[dict[str, Any]] = []
    for word in words.words:
        if word.end <= start or word.start >= end:
            continue
        result.append({
            "word": word.word,
            "start": round(max(0.0, word.start - start), 3),
            "end": round(min(end - start, word.end - start), 3),
        })
    return result


def _creative_prompt(
    *,
    brief: EpisodeBrief,
    narration: Narration,
    director: DirectorPlan,
    plan: V3EditorialSequencePlan,
    record: V3EditorialSequenceRecord,
    words: WordTimestampBundle | None,
    previous_handoff: str | None,
) -> str:
    scene_by_id = {scene.scene_id: scene for scene in director.scenes}
    scenes = [scene_by_id[scene_id] for scene_id in record.scene_ids]
    expected_beats = []
    for index, scene in enumerate(scenes, 1):
        expected_beats.append({
            "beat_id": f"b{index:02d}",
            "scene_id": scene.scene_id,
            "renderer": scene.renderer,
            "time_start": round(scene.start - record.start, 3),
            "time_end": round(scene.end - record.start, 3),
            "duration": round(scene.end - scene.start, 3),
            "narration_text": scene.narration_excerpt,
            "purpose": scene.purpose,
            "visual_brief": scene.visual_brief,
            "on_screen_text": scene.on_screen_text,
            "emphasis": scene.emphasis,
        })
    payload = {
        "episode": {
            "episode_id": brief.episode_id,
            "title": brief.title,
            "theme": brief.graphics_theme,
            "full_narration": narration.text,
        },
        "sequence": {
            "sequence_id": record.sequence_id,
            "canvas_duration": round(record.end - record.start, 3),
            "beats": expected_beats,
            "word_timestamps": _sequence_local_words(words, start=record.start, end=record.end),
            "previous_sequence_handoff": previous_handoff,
        },
        "visual_bible": plan.visual_bible,
    }
    return (
        "# ROLE\n"
        "You are the visual creative director for one continuous short-form editorial sequence.\n"
        "Follow the same lightweight planning boundary used by Stock-Select V3: describe WHAT should "
        "appear and WHEN; do not encode renderer bookkeeping or executable code.\n\n"
        "# OUTPUT\n"
        "Return one compact JSON object with: sequence_id, canvas_duration, visual_thesis, "
        "continuity_object, beats.\n"
        "Each beat must contain: beat_id, scene_id, renderer, time_start, time_end, narration_text, "
        "transition_in, transition_out, overlay_intent, layout, gsap_choreography.\n\n"
        "# GRAPHICS BEATS\n"
        "For hyperframes/static beats, layout is an object with type, background, and at most 2 elements. "
        "Each element has id, type, description, label, position, css_tokens. Position uses portrait-stage "
        "percentages: top/left/width/height in 0..100. Prefix every element ID with the beat ID, e.g. b01_inbox.\n"
        "gsap_choreography has at most 3 entries using target_id, enter_type, at_offset, duration, params. "
        "Preferred enter_type values: slide_left, slide_right, fade_in, line_draw, count_up, paper_drop, "
        "stamp_hit, formation_build, bar_fill, scale_reveal, persist.\n\n"
        "# BASE MEDIA BEATS\n"
        "For playwright/manual_talking_head/infinite_talk, the existing recording remains authoritative. "
        "Set layout=null and gsap_choreography=[]; use overlay_intent and transitions only. Never redraw the UI "
        "or replace the presenter.\n\n"
        "# TIMING\n"
        "All times in this prompt are SEQUENCE-LOCAL numeric seconds. Use the supplied numeric word timestamps "
        "only as creative timing context. Do not return anchor_text, narration phrase keys, anchor occurrences, "
        "review checkpoints, initially_visible flags, reveal-count bookkeeping, or absolute master-video times. "
        "Every choreography at_offset must fall inside that beat's supplied time_start..time_end.\n\n"
        "# CONTINUITY\n"
        "Treat the supplied beats as one evolving visual thought. A useful object can persist or transform into "
        "the next graphics beat; screen/presenter cuts should feel motivated. Use enter_type=persist for an "
        "element that visually carries forward. Do not invent continuity across media that are not adjacent.\n\n"
        "# IMPORTANT\n"
        "Do not write HTML/CSS/JavaScript. Do not add scenes. Keep all scene IDs and order exactly as supplied. "
        "The factory will normalize ordinary model drift deterministically after this response.\n\n"
        "# INPUT\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )


def _slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "_", (value or "").strip().lower()).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"{fallback}_{cleaned}".strip("_")
    return cleaned[:64]


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalized_position(position: dict[str, float], *, index: int) -> dict[str, float]:
    presets = [
        {"left": 8.0, "top": 12.0, "width": 58.0, "height": 34.0},
        {"left": 38.0, "top": 49.0, "width": 54.0, "height": 36.0},
        {"left": 10.0, "top": 58.0, "width": 50.0, "height": 28.0},
    ]
    fallback = presets[min(index, len(presets) - 1)]
    left = _float(position.get("left", position.get("x")), fallback["left"])
    top = _float(position.get("top", position.get("y")), fallback["top"])
    width = _float(position.get("width"), fallback["width"])
    height = _float(position.get("height"), fallback["height"])
    left = max(0.0, min(92.0, left))
    top = max(0.0, min(92.0, top))
    width = max(12.0, min(96.0 - left, width))
    height = max(10.0, min(96.0 - top, height))
    return {"left": left, "top": top, "width": width, "height": height}


def _fallback_layout(beat_id: str, scene: Any) -> V3BeatLayout:
    label = (scene.on_screen_text[0] if scene.on_screen_text else scene.purpose)[:72]
    return V3BeatLayout(
        type="evidence_board",
        background=scene.visual_brief,
        elements=[
            V3LayoutElement(
                id=f"{beat_id}_primary",
                type="evidence_card",
                description=scene.visual_brief,
                label=label,
                position={"left": 10, "top": 16, "width": 80, "height": 62},
            )
        ],
    )


def _normalize_sequence_layout(
    candidate: V3EditorialSequenceLayout,
    *,
    record: V3EditorialSequenceRecord,
    director: DirectorPlan,
) -> V3EditorialSequenceLayout:
    """Normalize creative drift instead of hard-failing the generation call."""

    scene_by_id = {scene.scene_id: scene for scene in director.scenes}
    supplied_by_scene = {beat.scene_id: beat for beat in candidate.beats if beat.scene_id}
    normalized_beats: list[V3EditorialBeat] = []

    for index, scene_id in enumerate(record.scene_ids, 1):
        scene = scene_by_id[scene_id]
        expected_beat_id = f"b{index:02d}"
        source = supplied_by_scene.get(scene_id)
        if source is None and index - 1 < len(candidate.beats):
            source = candidate.beats[index - 1]
        source = source or V3EditorialBeat()
        local_start = round(scene.start - record.start, 3)
        local_end = round(scene.end - record.start, 3)

        transition_in = (source.transition_in or "continue the prior motion cleanly")[:180]
        transition_out = (source.transition_out or "hand off the dominant shape into the next beat")[:180]
        overlay_intent = (source.overlay_intent or "")[:180]

        if scene.renderer in GRAPHICS_RENDERERS:
            raw_layout = source.layout or _fallback_layout(expected_beat_id, scene)
            elements: list[V3LayoutElement] = []
            id_map: dict[str, str] = {}
            for element_index, element in enumerate(raw_layout.elements[:4]):
                original = element.id
                suffix_source = original
                if suffix_source.startswith(expected_beat_id + "_"):
                    suffix_source = suffix_source[len(expected_beat_id) + 1:]
                suffix = _slug(suffix_source, f"element{element_index + 1}")
                normalized_id = f"{expected_beat_id}_{suffix}"
                id_map[original] = normalized_id
                elements.append(element.model_copy(update={
                    "id": normalized_id,
                    "description": (element.description or scene.visual_brief)[:180],
                    "label": (element.label or scene.purpose)[:72],
                    "position": _normalized_position(element.position, index=element_index),
                }))
            if not elements:
                elements = _fallback_layout(expected_beat_id, scene).elements

            choreography: list[V3Choreography] = []
            valid_ids = {element.id for element in elements}
            first_id = elements[0].id
            canvas_duration = record.end - record.start
            for action in source.gsap_choreography[:6]:
                target = id_map.get(action.target_id, action.target_id)
                if target not in valid_ids:
                    target = first_id
                at = _float(action.at_offset, local_start)
                if record.start > 0.05 and record.start - 0.05 <= at <= record.end + 0.05 and at > canvas_duration + 0.05:
                    at -= record.start
                at = round(max(local_start, min(local_end, at)), 3)
                duration = round(max(0.15, min(4.0, _float(action.duration, 0.65))), 3)
                choreography.append(action.model_copy(update={
                    "target_id": target,
                    "at_offset": at,
                    "duration": duration,
                }))
            if not choreography:
                choreography = [
                    V3Choreography(
                        target_id=first_id,
                        enter_type="scale_reveal",
                        at_offset=round(min(local_end, local_start + 0.25), 3),
                        duration=0.6,
                    )
                ]
            layout = raw_layout.model_copy(update={"elements": elements})
        else:
            layout = None
            choreography = []

        normalized_beats.append(V3EditorialBeat(
            beat_id=expected_beat_id,
            scene_id=scene_id,
            renderer=scene.renderer,
            time_start=local_start,
            time_end=local_end,
            narration_text=scene.narration_excerpt,
            transition_in=transition_in,
            transition_out=transition_out,
            overlay_intent=overlay_intent,
            layout=layout,
            gsap_choreography=choreography,
        ))

    return V3EditorialSequenceLayout(
        sequence_id=record.sequence_id,
        canvas_duration=round(record.end - record.start, 3),
        visual_thesis=(candidate.visual_thesis or "One evolving editorial thought across adjacent beats")[:240],
        continuity_object=(candidate.continuity_object or None),
        beats=normalized_beats,
    )


def _plan_sequences(
    store: ProjectStore,
    episode_id: str,
    *,
    brief: EpisodeBrief,
    narration: Narration,
    director: DirectorPlan,
    words: WordTimestampBundle | None,
    plan: V3EditorialSequencePlan,
    agent_kind: str | None,
    consume_response: bool,
    request_dir: Path,
) -> V3EditorialSequencePlan:
    agent = _structured_agent(
        store,
        "graphics_layout",
        {"episode_id": episode_id},
        agent_kind=agent_kind,
        consume_response=consume_response,
    )
    resolved: list[V3EditorialSequenceRecord] = []
    previous_handoff: str | None = None
    total = len(plan.sequences)

    for index, record in enumerate(plan.sequences, 1):
        emit(
            12 + round((index - 1) / max(1, total) * 28),
            f"{record.sequence_id}: V3 creative direction for {len(record.scene_ids)} adjacent beat(s)",
            task="graphics_layout",
        )
        candidate = _run_graphics_agent(
            agent,
            stage=f"graphics_layout_{record.sequence_id.lower()}",
            prompt=_creative_prompt(
                brief=brief,
                narration=narration,
                director=director,
                plan=plan,
                record=record,
                words=words,
                previous_handoff=previous_handoff,
            ),
            output_model=V3EditorialSequenceLayout,
            request_dir=request_dir,
        )
        normalized = _normalize_sequence_layout(candidate, record=record, director=director)
        previous_handoff = normalized.beats[-1].transition_out if normalized.beats else previous_handoff
        resolved.append(record.model_copy(update={"layout": normalized}))
    return plan.model_copy(update={"sequences": resolved})


def _frame_from_element(element: V3LayoutElement) -> GraphicsFrame:
    pos = _normalized_position(element.position, index=0)
    return GraphicsFrame(
        x=round(pos["left"], 3),
        y=round(pos["top"], 3),
        width=round(pos["width"], 3),
        height=round(pos["height"], 3),
        rotation=0,
        depth="foreground",
    )


def _ensure_stage_coverage(elements: list[CustomGraphicsElement]) -> list[CustomGraphicsElement]:
    if not elements:
        return elements
    frames = [item.frame for item in elements if item.role != "background"]
    span_w = max(frame.x + frame.width for frame in frames) - min(frame.x for frame in frames)
    span_h = max(frame.y + frame.height for frame in frames) - min(frame.y for frame in frames)
    if span_w >= 65 and span_h >= 55:
        return elements
    first = elements[0]
    frame = first.frame
    width = max(frame.width, 70.0)
    height = max(frame.height, 58.0)
    x = max(2.0, min(98.0 - width, frame.x - max(0.0, width - frame.width) / 2))
    y = max(2.0, min(98.0 - height, frame.y - max(0.0, height - frame.height) / 2))
    return [
        first.model_copy(update={
            "frame": frame.model_copy(update={"x": x, "y": y, "width": width, "height": height})
        }),
        *elements[1:],
    ]


def _local_action_time(action: V3Choreography, beat: V3EditorialBeat, duration: float) -> float:
    local = _float(action.at_offset, beat.time_start) - beat.time_start
    return round(max(0.0, min(duration, local)), 6)


def _compile_graphics_beat(
    beat: V3EditorialBeat,
    *,
    scene: Any,
    theme: GraphicsTheme,
) -> CustomGraphicsLayoutPlan:
    """Compile V3 creative intent into the existing deterministic renderer contract."""

    layout = beat.layout or _fallback_layout(beat.beat_id, scene)
    duration = scene.end - scene.start
    raw_elements = layout.elements[:7] or _fallback_layout(beat.beat_id, scene).elements

    custom_elements: list[CustomGraphicsElement] = []
    for index, element in enumerate(raw_elements):
        custom_elements.append(CustomGraphicsElement(
            element_id=_slug(element.id, f"{beat.beat_id}_element{index + 1}"),
            kind=_CUSTOM_KIND.get(element.type, "evidence"),
            role="primary" if index == 0 else "supporting",
            label=(element.label or scene.purpose)[:72],
            detail=(element.description or "")[:140],
            visual_form=(element.description or f"{element.type} editorial form")[:160],
            frame=_frame_from_element(element),
            initially_visible=index == 0,
        ))
    custom_elements = _ensure_stage_coverage(custom_elements)
    known = {item.element_id for item in custom_elements}
    first_id = custom_elements[0].element_id

    first_times: dict[str, float] = {}
    for action in beat.gsap_choreography:
        target = action.target_id if action.target_id in known else first_id
        first_times[target] = min(first_times.get(target, duration), _local_action_time(action, beat, duration))

    reveal_times: dict[str, float] = {}
    actions: list[CustomGraphicsAction] = []
    for element in custom_elements[1:]:
        reveal_at = max(0.05, min(duration * 0.72, first_times.get(element.element_id, duration * 0.35) - 0.02))
        reveal_times[element.element_id] = reveal_at
        actions.append(CustomGraphicsAction(
            cue_id=f"cue_{_slug(scene.scene_id, 'scene')}_reveal_{_slug(element.element_id, 'element')}",
            action="reveal",
            target_id=element.element_id,
            anchor_text="numeric_timing",
            at_seconds=round(reveal_at, 6),
            duration_seconds=min(0.6, max(0.2, duration * 0.08)),
            direction="in",
        ))

    for index, item in enumerate(beat.gsap_choreography[:12], 1):
        target = item.target_id if item.target_id in known else first_id
        action_kind = _ACTION_KIND.get(item.enter_type, "transform")
        if action_kind == "merge" and len(custom_elements) < 2:
            action_kind = "transform"
        at_seconds = _local_action_time(item, beat, duration)
        if target in reveal_times:
            at_seconds = max(at_seconds, reveal_times[target] + 0.02)
        actions.append(CustomGraphicsAction(
            cue_id=f"cue_{_slug(scene.scene_id, 'scene')}_{index:02d}_{_slug(item.enter_type, 'motion')}",
            action=action_kind,
            target_id=target,
            source_id=first_id if action_kind in {"connect", "merge"} and target != first_id else None,
            anchor_text="numeric_timing",
            at_seconds=round(min(duration, at_seconds), 6),
            duration_seconds=max(0.15, min(4.0, item.duration)),
            direction=_DIRECTION.get(item.enter_type),
            value=str(item.params)[:120] if item.params else item.enter_type[:120],
        ))

    if not any(item.action not in {"reveal", "hold", "highlight", "focus"} for item in actions):
        actions.append(CustomGraphicsAction(
            cue_id=f"cue_{_slug(scene.scene_id, 'scene')}_payoff",
            action="transform",
            target_id=first_id,
            anchor_text="numeric_timing",
            at_seconds=round(min(max(0.15, duration * 0.65), max(0.15, duration - 0.85)), 6),
            duration_seconds=min(0.8, max(0.25, duration * 0.1)),
            direction="in",
            value="final editorial payoff",
        ))

    latest = max(item.at_seconds for item in actions if item.action != "hold")
    target_latest = min(max(0.15, duration * 0.66), max(0.15, duration - 0.8))
    if latest < target_latest - 0.05:
        actions.append(CustomGraphicsAction(
            cue_id=f"cue_{_slug(scene.scene_id, 'scene')}_final_focus",
            action="transform",
            target_id=first_id,
            anchor_text="numeric_timing",
            at_seconds=round(target_latest, 6),
            duration_seconds=min(0.7, max(0.2, duration * 0.08)),
            direction="in",
            value="hold the final state for readability",
        ))

    actions = sorted(actions, key=lambda item: item.at_seconds)[:18]
    checkpoints = sorted(set([
        round(min(max(0.05, duration * 0.12), max(0.05, duration - 0.05)), 3),
        round(min(max(0.05, duration * 0.55), max(0.05, duration - 0.05)), 3),
        round(max(0.05, duration - 0.72), 3),
    ]))
    if len(checkpoints) < 2:
        checkpoints = [0.0, round(max(0.05, duration - 0.05), 3)]

    headline = custom_elements[0].label[:64]
    support = custom_elements[1].label[:100] if len(custom_elements) > 1 else ""
    return CustomGraphicsLayoutPlan(
        scene_id=scene.scene_id,
        start=scene.start,
        end=scene.end,
        theme=theme,
        visual_thesis=(scene.visual_brief or beat.narration_text)[:240],
        headline=headline,
        support=support,
        layout_style=(layout.type or "evidence_board")[:120],
        opening_state=f"{headline} establishes the first visual state"[:180],
        payoff_state=f"{headline} resolves into the next editorial handoff"[:180],
        elements=custom_elements,
        actions=actions,
        review_checkpoints=checkpoints[:3],
    )


def _compile_graphics_layouts(
    plan: V3EditorialSequencePlan,
    *,
    director: DirectorPlan,
    theme: GraphicsTheme,
) -> list[CustomGraphicsLayoutPlan]:
    scene_by_id = {scene.scene_id: scene for scene in director.scenes}
    result: list[CustomGraphicsLayoutPlan] = []
    for record in plan.sequences:
        if not record.layout:
            continue
        for beat in record.layout.beats:
            scene = scene_by_id[beat.scene_id]
            if scene.renderer not in GRAPHICS_RENDERERS:
                continue
            result.append(_compile_graphics_beat(beat, scene=scene, theme=theme))
    return result


def generate_graphics_plan(
    store: ProjectStore,
    episode_id: str,
    *,
    agent_kind: str | None = None,
    consume_response: bool = False,
) -> GraphicsPlan:
    """V3-style creative planning over the real mixed-media Director timeline."""

    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    narration = load_model(project / "01_narration/narration.json", Narration)
    director = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    graphics_scenes = [scene for scene in director.scenes if scene.renderer in GRAPHICS_RENDERERS]
    if not graphics_scenes:
        raise RuntimeError("The approved director plan has no HyperFrames/static graphics scenes")

    configured_mock = False
    if agent_kind is None:
        configured_mock = resolve_task(load_config(store, episode_id), "graphics_layout")["provider_mode"] == "mock"
    if agent_kind == "mock" or configured_mock:
        from .pipeline import generate_graphics_plan as legacy_generate_graphics_plan
        return legacy_generate_graphics_plan(
            store,
            episode_id,
            agent_kind="mock",
            consume_response=consume_response,
        )

    words_path = project / "02_voice/audio_word_timestamps.json"
    words = load_model(words_path, WordTimestampBundle) if words_path.is_file() else None
    request_dir = project / "_requests"

    plan = build_v3_editorial_sequence_plan(director, theme=brief.graphics_theme)
    write_json(project / "03_director/editorial_sequence_plan.json", plan)
    emit(
        8,
        f"Grouped {len(director.scenes)} Director beats into {len(plan.sequences)} V3 editorial sequence call(s)",
        task="graphics_layout",
    )
    plan = _plan_sequences(
        store,
        episode_id,
        brief=brief,
        narration=narration,
        director=director,
        words=words,
        plan=plan,
        agent_kind=agent_kind,
        consume_response=consume_response,
        request_dir=request_dir,
    )
    write_json(project / "03_director/editorial_sequence_plan.json", plan)

    layouts = _compile_graphics_layouts(plan, director=director, theme=brief.graphics_theme)
    expected_ids = [scene.scene_id for scene in graphics_scenes]
    actual_ids = [layout.scene_id for layout in layouts]
    if actual_ids != expected_ids:
        raise RuntimeError(
            f"V3 compiled graphics order differs from Director graphics order; expected={expected_ids}, actual={actual_ids}"
        )

    bundles = legacy._code_layouts(
        store,
        episode_id,
        layouts=layouts,
        theme=brief.graphics_theme,
        agent_kind=agent_kind,
        consume_response=consume_response,
        request_dir=request_dir,
    )
    package = CustomGraphicsPackage(
        episode_id=episode_id,
        duration_seconds=director.duration_seconds,
        theme=brief.graphics_theme,
        scenes=bundles,
    )
    summary = custom_package_summary(package, creative_thesis=director.visual_thesis)
    _validate_graphics_against_director(summary, director)

    emit(65, "Compiling V3-directed custom graphics previews", task="graphics_builder")
    write_custom_graphics_package(
        project,
        package,
        summary,
        width=brief.width,
        height=brief.height,
        fps=brief.fps,
    )
    emit(72, "Checking rendered cue frames, clipping, overlap, and action liveness", task="graphics_builder")
    try:
        _validate_custom_graphics_visuals(
            project,
            fps=brief.fps,
            width=brief.width,
            height=brief.height,
        )
    except CustomGraphicsVisualValidationError as exc:
        package = legacy._repair_visual_failures(
            store,
            episode_id,
            package=package,
            report=exc.report,
            brief=brief,
            request_dir=request_dir,
            agent_kind=agent_kind,
            consume_response=consume_response,
        )
        summary = custom_package_summary(package, creative_thesis=director.visual_thesis)
        _validate_graphics_against_director(summary, director)
        write_custom_graphics_package(
            project,
            package,
            summary,
            width=brief.width,
            height=brief.height,
            fps=brief.fps,
        )
        _validate_custom_graphics_visuals(
            project,
            fps=brief.fps,
            width=brief.width,
            height=brief.height,
        )

    emit(88, "Building mixed-media timeline from V3 creative direction", task="graphics_builder")
    build_composition(project, preview=True, width=brief.width, height=brief.height, fps=brief.fps)
    store.transition(episode_id, EpisodeStage.COMPOSITION_READY)
    emit(
        100,
        f"Generated {len(summary.scenes)} graphics scenes from {len(plan.sequences)} V3 editorial sequence call(s)",
        task="graphics_builder",
    )
    return summary
