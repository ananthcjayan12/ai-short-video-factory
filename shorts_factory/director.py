from __future__ import annotations

from .models import AudioTiming, DirectorBudgets, DirectorPlan, Scene, WordTimestampBundle


VISUAL_TYPES = {"screen_recording", "motion_graphic", "diagram", "ui_mockup", "broll"}
PRESENTER_TYPES = {"talking_head", "cta"}


def production_budgets(*, duration_seconds: float, include_talking_head: bool) -> DirectorBudgets:
    """Hard production budgets owned by code, never by an AI response."""
    long_form_short = duration_seconds > 90
    return DirectorBudgets(
        max_visual_moments=7 if include_talking_head else 24,
        max_generated_assets=5 if include_talking_head else 7,
        max_scene_seconds=13.0 if long_form_short else 8.0,
        max_consecutive_non_talking_head_seconds=(
            (20.0 if long_form_short else 16.0)
            if include_talking_head else duration_seconds + 0.001
        ),
        require_talking_head_hook=include_talking_head,
        require_talking_head_close=include_talking_head,
    )


def snap_to_word_boundaries(
    plan: DirectorPlan,
    timing: AudioTiming,
    words: WordTimestampBundle,
) -> DirectorPlan:
    """Snap creative scene cuts to the immutable Whisper word clock."""
    scenes = sorted(plan.scenes, key=lambda scene: scene.start)
    duration = timing.audio_duration_seconds
    internal_edges = sorted({word.end for word in words.words if 0.01 < word.end < duration - 0.01})
    required = max(0, len(scenes) - 1)
    if len(internal_edges) < required:
        raise RuntimeError("Whisper did not produce enough word boundaries for the requested scene count")

    selected: list[float] = []
    previous_index = -1
    for scene_index, scene in enumerate(scenes[:-1]):
        remaining = required - scene_index - 1
        first_allowed = previous_index + 1
        last_allowed = len(internal_edges) - remaining - 1
        candidate_index = min(
            range(first_allowed, last_allowed + 1),
            key=lambda index: abs(internal_edges[index] - scene.end),
        )
        selected.append(internal_edges[candidate_index])
        previous_index = candidate_index

    boundaries = [0.0, *selected, duration]
    snapped = [
        scene.model_copy(update={"start": boundaries[index], "end": boundaries[index + 1]})
        for index, scene in enumerate(scenes)
    ]
    warnings = list(plan.warnings)
    if any(abs(old.start - new.start) > 0.001 or abs(old.end - new.end) > 0.001 for old, new in zip(scenes, snapped)):
        warnings.append("Scene boundaries snapped to validated Whisper word timestamps")
    return plan.model_copy(update={"duration_seconds": duration, "scenes": snapped, "warnings": warnings})


def validate_word_boundaries(plan: DirectorPlan, words: WordTimestampBundle, *, tolerance: float = 0.002) -> list[str]:
    allowed = [0.0, words.audio_duration_seconds, *[word.end for word in words.words]]
    issues: list[str] = []
    for scene in plan.scenes:
        if not any(abs(scene.start - edge) <= tolerance for edge in allowed):
            issues.append(f"{scene.scene_id} start is not on a Whisper word boundary")
        if not any(abs(scene.end - edge) <= tolerance for edge in allowed):
            issues.append(f"{scene.scene_id} end is not on a Whisper word boundary")
    return issues


def normalize(plan: DirectorPlan, *, include_talking_head: bool = True) -> DirectorPlan:
    """Fail-closed production policy after the creative Director.

    The Director is allowed to be creative. This normalizer is not: it enforces
    short-form budgets and converts risky/excess visual beats back to a safe
    talking-head placeholder while preserving the narration clock.
    """
    scenes = sorted(plan.scenes, key=lambda s: s.start)
    warnings = list(plan.warnings)
    budgets = plan.budgets

    if include_talking_head and budgets.require_talking_head_hook and scenes[0].type != "talking_head":
        scenes[0] = scenes[0].model_copy(update={
            "type": "talking_head", "renderer": "manual_talking_head",
            "purpose": scenes[0].purpose + " [normalized to presenter hook]",
        })
        warnings.append("Opening scene normalized to talking head")

    if include_talking_head and budgets.require_talking_head_close and scenes[-1].type not in PRESENTER_TYPES:
        scenes[-1] = scenes[-1].model_copy(update={
            "type": "cta", "renderer": "manual_talking_head",
            "purpose": scenes[-1].purpose + " [normalized to presenter close]",
        })
        warnings.append("Closing scene normalized to presenter CTA")

    visual_count = 0
    generated_count = 0
    non_head_run = 0.0
    normalized: list[Scene] = []
    for scene in scenes:
        if not include_talking_head and scene.type in PRESENTER_TYPES:
            scene = scene.model_copy(update={
                "type": "motion_graphic",
                "renderer": "static",
                "purpose": scene.purpose + " [normalized: talking head disabled for this project]",
                "demo_job_id": None,
            })
            warnings.append(f"{scene.scene_id} converted to deterministic graphic because talking head is disabled")
        if scene.duration > budgets.max_scene_seconds + 1e-6:
            warnings.append(f"{scene.scene_id} exceeds max_scene_seconds")
        is_visual = scene.type in VISUAL_TYPES
        is_generated = scene.renderer in {"hyperframes", "infinite_talk"}
        projected_visual_count = visual_count + int(is_visual)
        projected_generated_count = generated_count + int(is_generated)
        if scene.type in PRESENTER_TYPES:
            non_head_run = 0.0
        elif include_talking_head:
            non_head_run += scene.duration

        over_budget = (
            projected_visual_count > budgets.max_visual_moments
            or projected_generated_count > budgets.max_generated_assets
        )
        too_long_without_face = (
            include_talking_head
            and non_head_run > budgets.max_consecutive_non_talking_head_seconds + 1e-6
        )
        if over_budget or too_long_without_face:
            reason = "visual budget" if over_budget else "presenter cadence"
            if include_talking_head:
                scene = scene.model_copy(update={
                    "type": "talking_head", "renderer": "manual_talking_head",
                    "purpose": scene.purpose + f" [safe fallback: {reason}]",
                    "demo_job_id": None,
                })
                warnings.append(f"{scene.scene_id} converted to talking head due to {reason}")
            else:
                scene = scene.model_copy(update={
                    "type": "motion_graphic", "renderer": "static",
                    "purpose": scene.purpose + f" [deterministic fallback: {reason}]",
                    "demo_job_id": None,
                })
                warnings.append(f"{scene.scene_id} converted to static graphic due to {reason}")
            non_head_run = 0.0
        else:
            visual_count = projected_visual_count
            generated_count = projected_generated_count
        normalized.append(scene)

    return plan.model_copy(update={"scenes": normalized, "warnings": warnings})


def validate_budgets(plan: DirectorPlan) -> list[str]:
    issues: list[str] = []
    b = plan.budgets
    visual = sum(s.type in VISUAL_TYPES for s in plan.scenes)
    generated = sum(s.renderer in {"hyperframes", "infinite_talk"} for s in plan.scenes)
    if visual > b.max_visual_moments:
        issues.append(f"visual moments {visual} > {b.max_visual_moments}")
    if generated > b.max_generated_assets:
        issues.append(f"generated assets {generated} > {b.max_generated_assets}")
    if any(s.duration > b.max_scene_seconds + 1e-6 for s in plan.scenes):
        issues.append("one or more scenes exceed max scene duration")
    run = 0.0
    for s in plan.scenes:
        if s.type in {"talking_head", "cta"}:
            run = 0.0
        else:
            run += s.duration
            if run > b.max_consecutive_non_talking_head_seconds + 1e-6:
                issues.append("too long without a presenter beat")
                break
    return issues


def validate_presenter_policy(plan: DirectorPlan, *, include_talking_head: bool) -> list[str]:
    presenter_scenes = [scene.scene_id for scene in plan.scenes if scene.type in PRESENTER_TYPES]
    if not include_talking_head and presenter_scenes:
        return ["Talking head is disabled for this project, but presenter scenes remain: " + ", ".join(presenter_scenes)]
    if include_talking_head:
        issues: list[str] = []
        if plan.budgets.require_talking_head_hook and plan.scenes[0].type != "talking_head":
            issues.append("Hook is not presenter-led")
        if plan.budgets.require_talking_head_close and plan.scenes[-1].type not in PRESENTER_TYPES:
            issues.append("Close is not presenter-led")
        return issues
    return []
