from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import editorial_graphics as legacy
from .custom_graphics import CustomGraphicsAction, CustomGraphicsElement, CustomGraphicsLayoutPlan
from .models import DirectorPlan, EpisodeBrief, GraphicsTheme, Narration, WordTimestampBundle
from .pipeline import _run_graphics_agent, _structured_agent
from .progress import emit
from .project import ProjectStore


class CustomGraphicsLayoutDraft(BaseModel):
    """Schema-complete graphics layout without cross-field semantic validation.

    Provider output must first survive structural JSON/schema validation so the
    editorial repair loop can inspect and repair semantic defects (for example a
    future element that is missing its required reveal). The draft is converted
    into the strict CustomGraphicsLayoutPlan only inside that repair loop.
    """

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
    elements: list[CustomGraphicsElement] = Field(min_length=1, max_length=8)
    actions: list[CustomGraphicsAction] = Field(min_length=1, max_length=18)
    review_checkpoints: list[float] = Field(min_length=2, max_length=3)


class EditorialSequenceLayoutDraft(BaseModel):
    """Repairable provider response for one 2-3 beat editorial sequence."""

    model_config = ConfigDict(extra="forbid")

    sequence_id: str = Field(pattern=r"^Q\d{2}$")
    visual_thesis: str = Field(min_length=3, max_length=240)
    opening_handoff: str = Field(min_length=3, max_length=180)
    closing_handoff: str = Field(min_length=3, max_length=180)
    continuity_object: str | None = Field(default=None, max_length=96)
    beats: list[legacy.EditorialBeatDirection] = Field(min_length=1, max_length=3)
    graphics_layouts: list[CustomGraphicsLayoutDraft] = Field(default_factory=list, max_length=3)


def _strict_sequence_layout(
    candidate: EditorialSequenceLayoutDraft,
    *,
    record: legacy.EditorialSequenceRecord,
    director: DirectorPlan,
    brief: EpisodeBrief,
    words: WordTimestampBundle | None,
) -> legacy.EditorialSequenceLayout:
    """Convert a structurally valid draft into strict scene contracts.

    All semantic failures intentionally occur here, inside the bounded repair
    loop, instead of inside ProviderAgent's first Pydantic parse.
    """

    if candidate.sequence_id != record.sequence_id:
        raise RuntimeError(
            f"Editorial layout returned {candidate.sequence_id}; expected {record.sequence_id}"
        )
    beat_ids = [beat.scene_id for beat in candidate.beats]
    if beat_ids != record.scene_ids:
        raise RuntimeError(
            f"Editorial sequence {record.sequence_id} changed beat coverage/order; "
            f"expected={record.scene_ids}, actual={beat_ids}"
        )

    scene_by_id = {scene.scene_id: scene for scene in director.scenes}
    for beat in candidate.beats:
        expected = scene_by_id[beat.scene_id].renderer
        if beat.renderer != expected:
            raise RuntimeError(
                f"Editorial sequence {record.sequence_id}/{beat.scene_id} changed renderer "
                f"{expected} -> {beat.renderer}"
            )

    expected_graphics = [
        scene_id for scene_id in record.scene_ids
        if scene_by_id[scene_id].renderer in {"hyperframes", "static"}
    ]
    actual_graphics = [item.scene_id for item in candidate.graphics_layouts]
    if actual_graphics != expected_graphics:
        raise RuntimeError(
            f"Editorial sequence {record.sequence_id} graphics coverage differs; "
            f"expected={expected_graphics}, actual={actual_graphics}"
        )

    aligned: list[CustomGraphicsLayoutPlan] = []
    for draft in candidate.graphics_layouts:
        try:
            strict = CustomGraphicsLayoutPlan.model_validate(draft.model_dump(mode="json"))
        except Exception as exc:
            raise RuntimeError(
                f"Editorial sequence {record.sequence_id}/{draft.scene_id} failed the strict "
                f"graphics contract and must be repaired: {exc}"
            ) from exc
        if strict.theme != brief.graphics_theme:
            raise RuntimeError(
                f"Editorial graphics layout theme {strict.theme!r} does not match "
                f"{brief.graphics_theme!r}"
            )
        aligned.append(
            legacy._align_custom_layout_to_words(
                strict, scene_by_id[strict.scene_id], words, fps=brief.fps,
            )
        )

    return legacy.EditorialSequenceLayout(
        sequence_id=candidate.sequence_id,
        visual_thesis=candidate.visual_thesis,
        opening_handoff=candidate.opening_handoff,
        closing_handoff=candidate.closing_handoff,
        continuity_object=candidate.continuity_object,
        beats=candidate.beats,
        graphics_layouts=aligned,
    )


def _plan_sequence_layouts_repairable(
    store: ProjectStore,
    episode_id: str,
    *,
    brief: EpisodeBrief,
    narration: Narration,
    director: DirectorPlan,
    words: WordTimestampBundle | None,
    plan: legacy.EditorialSequencePlan,
    agent_kind: str | None,
    consume_response: bool,
    request_dir,
) -> legacy.EditorialSequencePlan:
    """Plan sequences with semantic validation inside the bounded repair loop."""

    layout_agent = _structured_agent(
        store,
        "graphics_layout",
        {"episode_id": episode_id},
        agent_kind=agent_kind,
        consume_response=consume_response,
    )
    resolved_records: list[legacy.EditorialSequenceRecord] = []
    previous_handoff: str | None = None
    total = len(plan.sequences)

    for index, record in enumerate(plan.sequences, 1):
        emit(
            12 + round((index - 1) / max(1, total) * 28),
            f"{record.sequence_id}: directing {len(record.scene_ids)} adjacent timeline beats together",
            task="graphics_layout",
        )
        base_prompt = legacy._sequence_prompt(
            brief=brief,
            narration=narration,
            director=director,
            plan=plan,
            record=record,
            words=words,
            previous_handoff=previous_handoff,
        )
        base_prompt += (
            "\n\n# STRICT REVEAL INVARIANT\n"
            "Before returning JSON, audit every graphics_layout independently:\n"
            "- Each element with initially_visible=false MUST have exactly one action with action=\"reveal\" and target_id equal to that element_id.\n"
            "- Each element with initially_visible=true MUST have zero reveal actions.\n"
            "- Do not use transform, move, highlight, focus, connect, trace, or another action as a substitute for the required first reveal.\n"
            "These are hard schema invariants, not style suggestions.\n"
        )

        candidate: EditorialSequenceLayoutDraft | None = None
        last_error: Exception | None = None
        strict_candidate: legacy.EditorialSequenceLayout | None = None
        for attempt in range(3):
            prompt = base_prompt
            if last_error is not None:
                prompt += (
                    f"\n\n# BOUNDED SEQUENCE REPAIR {attempt}/2\n"
                    "Return the COMPLETE corrected EditorialSequenceLayout. Preserve approved scene IDs, "
                    "order, renderers, timings, theme, facts, and exact narration anchors. Fix every "
                    "measured contract defect below; do not merely explain it.\n"
                    f"Measured defects:\n{last_error}"
                )
                if candidate is not None:
                    prompt += (
                        "\n\nPrevious structurally-valid response to repair:\n"
                        + candidate.model_dump_json(indent=2)
                    )
            try:
                candidate = _run_graphics_agent(
                    layout_agent,
                    stage=(
                        f"graphics_layout_{record.sequence_id.lower()}"
                        if attempt == 0
                        else f"graphics_layout_{record.sequence_id.lower()}_repair_{attempt}"
                    ),
                    prompt=prompt,
                    output_model=EditorialSequenceLayoutDraft,
                    request_dir=request_dir,
                )
                strict_candidate = _strict_sequence_layout(
                    candidate,
                    record=record,
                    director=director,
                    brief=brief,
                    words=words,
                )
                break
            except (RuntimeError, ValueError) as exc:
                if "usage limit is exhausted" in str(exc).casefold():
                    raise
                last_error = exc
        else:
            raise RuntimeError(
                f"Editorial sequence repair failed for {record.sequence_id}: {last_error}"
            )

        assert strict_candidate is not None
        previous_handoff = strict_candidate.closing_handoff
        resolved_records.append(record.model_copy(update={"layout": strict_candidate}))

    return plan.model_copy(update={"sequences": resolved_records})


def install_repairable_sequence_layout_validation() -> None:
    """Install the repairable schema boundary into the editorial planner.

    Kept as a small compatibility hook so the existing editorial_graphics module
    and its public generate_graphics_plan entrypoint remain stable for this PR.
    """

    legacy._plan_sequence_layouts = _plan_sequence_layouts_repairable
