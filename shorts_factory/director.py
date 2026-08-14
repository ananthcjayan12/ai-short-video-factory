from __future__ import annotations

from .models import DirectorPlan, Scene


VISUAL_TYPES = {"screen_recording", "motion_graphic", "diagram", "ui_mockup", "broll"}


def normalize(plan: DirectorPlan) -> DirectorPlan:
    """Fail-closed production policy after the creative Director.

    The Director is allowed to be creative. This normalizer is not: it enforces
    short-form budgets and converts risky/excess visual beats back to a safe
    talking-head placeholder while preserving the narration clock.
    """
    scenes = sorted(plan.scenes, key=lambda s: s.start)
    warnings = list(plan.warnings)
    budgets = plan.budgets

    if budgets.require_talking_head_hook and scenes[0].type != "talking_head":
        scenes[0] = scenes[0].model_copy(update={
            "type": "talking_head", "renderer": "manual_talking_head",
            "purpose": scenes[0].purpose + " [normalized to presenter hook]",
        })
        warnings.append("Opening scene normalized to talking head")

    if budgets.require_talking_head_close and scenes[-1].type not in {"talking_head", "cta"}:
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
        if scene.duration > budgets.max_scene_seconds + 1e-6:
            warnings.append(f"{scene.scene_id} exceeds max_scene_seconds")
        is_visual = scene.type in VISUAL_TYPES
        is_generated = scene.renderer in {"hyperframes", "infinite_talk"}
        if is_visual:
            visual_count += 1
        if is_generated:
            generated_count += 1
        if scene.type in {"talking_head", "cta"}:
            non_head_run = 0.0
        else:
            non_head_run += scene.duration

        over_budget = visual_count > budgets.max_visual_moments or generated_count > budgets.max_generated_assets
        too_long_without_face = non_head_run > budgets.max_consecutive_non_talking_head_seconds + 1e-6
        if over_budget or too_long_without_face:
            reason = "visual budget" if over_budget else "presenter cadence"
            scene = scene.model_copy(update={
                "type": "talking_head", "renderer": "manual_talking_head",
                "purpose": scene.purpose + f" [safe fallback: {reason}]",
                "demo_job_id": None,
            })
            warnings.append(f"{scene.scene_id} converted to talking head due to {reason}")
            non_head_run = 0.0
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
