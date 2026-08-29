from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import (
    GraphicsAction,
    GraphicsFrame,
    GraphicsObject,
    GraphicsPlan,
    GraphicsScenePlan,
    GraphicsTheme,
)


CustomElementKind = Literal[
    "artifact", "document", "email", "receipt", "spreadsheet", "database",
    "queue", "gate", "route", "connector", "map", "figure", "machine",
    "metric", "axis", "timeline", "annotation", "headline", "symbol", "evidence",
]
CustomActionKind = Literal[
    "reveal", "highlight", "connect", "count_to", "stamp", "transform", "hold",
    "move", "trace", "draw", "wipe", "cross_out", "split", "merge", "scatter",
    "focus", "exit",
]


class CustomGraphicsElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    kind: CustomElementKind
    role: Literal["primary", "supporting", "annotation", "background"]
    label: str = Field(min_length=1, max_length=72)
    detail: str = Field(default="", max_length=140)
    visual_form: str = Field(min_length=3, max_length=160)
    frame: GraphicsFrame
    initially_visible: bool = False


class CustomGraphicsAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cue_id: str = Field(pattern=r"^cue_[a-z0-9_-]+$")
    action: CustomActionKind
    target_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    source_id: str | None = None
    anchor_text: str | None = Field(default=None, max_length=80)
    anchor_occurrence: int = Field(default=0, ge=0)
    at_seconds: float = Field(default=0, ge=0)
    duration_seconds: float = Field(default=0.65, gt=0, le=4)
    direction: Literal[
        "left", "right", "up", "down", "in", "out", "clockwise", "counterclockwise"
    ] | None = None
    value: str | None = Field(default=None, max_length=120)


class CustomGraphicsLayoutPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine_version: Literal["custom_html_v1"] = "custom_html_v1"
    scene_id: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    theme: GraphicsTheme
    visual_thesis: str = Field(min_length=3, max_length=240)
    headline: str = Field(min_length=1, max_length=64)
    support: str = Field(default="", max_length=100)
    layout_style: str = Field(min_length=3, max_length=120)
    opening_state: str = Field(min_length=3, max_length=180)
    payoff_state: str = Field(min_length=3, max_length=180)
    elements: list[CustomGraphicsElement] = Field(min_length=2, max_length=5)
    actions: list[CustomGraphicsAction] = Field(min_length=2, max_length=12)
    review_checkpoints: list[float] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def validate_scene_contract(self):
        if self.end <= self.start:
            raise ValueError("custom graphics scene end must be after start")
        duration = self.end - self.start
        ids = [element.element_id for element in self.elements]
        if len(ids) != len(set(ids)):
            raise ValueError("custom graphics element IDs must be unique")
        known = set(ids)
        cue_ids = [action.cue_id for action in self.actions]
        if len(cue_ids) != len(set(cue_ids)):
            raise ValueError("custom graphics cue IDs must be unique")
        for action in self.actions:
            if action.target_id not in known:
                raise ValueError(f"custom graphics action targets unknown element {action.target_id}")
            if action.source_id and action.source_id not in known:
                raise ValueError(f"custom graphics action sources unknown element {action.source_id}")
            if action.action == "connect" and not action.source_id:
                raise ValueError("custom graphics connect action requires source_id")
            if action.at_seconds > duration + 0.05:
                raise ValueError(f"custom graphics action {action.cue_id} exceeds scene duration")
            if action.action != "hold" and not (action.anchor_text or "").strip():
                raise ValueError(f"custom graphics action {action.cue_id} requires anchor_text")
        opening = [element for element in self.elements if element.initially_visible]
        if not 1 <= len(opening) <= 3:
            raise ValueError("custom graphics scene needs one to three opening elements")
        for element in self.elements:
            reveals = [
                action for action in self.actions
                if action.target_id == element.element_id and action.action == "reveal"
            ]
            if element.initially_visible and reveals:
                raise ValueError(f"opening element {element.element_id} must not reveal again")
            if not element.initially_visible and len(reveals) != 1:
                raise ValueError(f"future element {element.element_id} requires exactly one reveal")
        for checkpoint in self.review_checkpoints:
            if checkpoint < 0 or checkpoint > duration + 0.05:
                raise ValueError("custom graphics checkpoint exceeds scene duration")
        foreground = [element.frame for element in self.elements if element.role != "background"]
        if foreground:
            span_width = max(frame.x + frame.width for frame in foreground) - min(frame.x for frame in foreground)
            span_height = max(frame.y + frame.height for frame in foreground) - min(frame.y for frame in foreground)
            if span_width < 65 or span_height < 55:
                raise ValueError(
                    f"custom graphics scene under-fills portrait stage ({span_width:.1f}% wide x {span_height:.1f}% high)"
                )
        meaningful = [
            action for action in self.actions
            if action.action not in {"reveal", "hold", "highlight", "focus"}
        ]
        if not meaningful:
            raise ValueError("custom graphics scene must visibly prove a relationship or state change")
        if self.opening_state.casefold() == self.payoff_state.casefold():
            raise ValueError("custom graphics opening and payoff states must differ")
        return self


class CustomGraphicsSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(min_length=1)
    html: str = Field(min_length=20, max_length=48_000)
    css: str = Field(min_length=20, max_length=48_000)
    javascript: str = Field(min_length=40, max_length=64_000)


class CustomGraphicsSceneBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layout: CustomGraphicsLayoutPlan
    source: CustomGraphicsSource
    repairs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_identity(self):
        if self.layout.scene_id != self.source.scene_id:
            raise ValueError("custom graphics layout and source scene IDs differ")
        return self


class CustomGraphicsPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine_version: Literal["custom_html_v1"] = "custom_html_v1"
    episode_id: str
    duration_seconds: float = Field(gt=0)
    theme: GraphicsTheme
    scenes: list[CustomGraphicsSceneBundle] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_package(self):
        ids = [scene.layout.scene_id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("custom graphics package scene IDs must be unique")
        mismatched = [scene.layout.scene_id for scene in self.scenes if scene.layout.theme != self.theme]
        if mismatched:
            raise ValueError("custom graphics scenes must use the package theme")
        return self


_OBJECT_TYPES = {
    "artifact": "artifact", "document": "document", "email": "artifact",
    "receipt": "document", "spreadsheet": "evidence", "database": "database",
    "queue": "process", "gate": "decision", "route": "route", "connector": "route",
    "map": "map_region", "figure": "figure", "machine": "process", "metric": "metric",
    "axis": "axis", "timeline": "axis", "annotation": "annotation", "headline": "text",
    "symbol": "annotation", "evidence": "evidence",
}


def custom_package_summary(package: CustomGraphicsPackage, *, creative_thesis: str) -> GraphicsPlan:
    """Create the legacy-compatible plan index without constraining custom scene rendering."""
    scenes: list[GraphicsScenePlan] = []
    for bundle in package.scenes:
        layout = bundle.layout
        objects = [
            GraphicsObject(
                object_id=element.element_id,
                object_type=_OBJECT_TYPES[element.kind],
                role=element.role,
                label=element.label,
                detail=element.detail,
                slot="hero",
                frame=element.frame,
                visual_form=element.visual_form,
                show_detail=bool(element.detail),
                initially_visible=element.initially_visible,
            )
            for element in layout.elements
        ]
        actions = [
            GraphicsAction(
                at_seconds=action.at_seconds,
                action=action.action,
                target=action.target_id,
                source=action.source_id,
                value=action.value,
                duration_seconds=action.duration_seconds,
                anchor_text=action.anchor_text,
                anchor_occurrence=action.anchor_occurrence,
                direction=action.direction,
            )
            for action in layout.actions
        ]
        scenes.append(GraphicsScenePlan(
            scene_id=layout.scene_id,
            start=layout.start,
            end=layout.end,
            scene_shell="spatial_stage",
            motion_grammar="custom_scene_code",
            layout_variant=layout.layout_style,
            visual_thesis=layout.visual_thesis,
            headline=layout.headline,
            support=layout.support,
            visual_world=layout.layout_style,
            opening_state=layout.opening_state,
            payoff_state=layout.payoff_state,
            camera_move="locked",
            continuity_object=None,
            objects=objects,
            actions=actions,
            review_checkpoints=layout.review_checkpoints,
        ))
    return GraphicsPlan(
        episode_id=package.episode_id,
        duration_seconds=package.duration_seconds,
        theme=package.theme,
        creative_thesis=creative_thesis,
        scenes=scenes,
        warnings=["custom_html_v1 scene sources are authoritative; semantic objects are compatibility metadata"],
    )
