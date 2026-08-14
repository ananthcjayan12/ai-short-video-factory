from __future__ import annotations

from pathlib import Path

from .director import validate_budgets
from .io import load_model
from .models import DirectorPlan, EpisodeBrief, VoiceMetadata


def episode_qa(project_dir: Path) -> dict:
    issues: list[str] = []
    warnings: list[str] = []
    brief = load_model(project_dir / "00_input/episode_brief.json", EpisodeBrief)
    plan = load_model(project_dir / "03_director/director_plan.approved.json", DirectorPlan)
    issues.extend(validate_budgets(plan))

    if (project_dir / "02_voice/voice.json").exists():
        voice = load_model(project_dir / "02_voice/voice.json", VoiceMetadata)
        if abs(voice.duration_seconds - plan.duration_seconds) > 1.0:
            warnings.append(f"Voice duration {voice.duration_seconds:.2f}s differs from director plan {plan.duration_seconds:.2f}s")
    else:
        warnings.append("No voice metadata imported")

    missing_assets = []
    for scene in plan.scenes:
        if scene.renderer in {"playwright", "manual_talking_head", "infinite_talk"}:
            rel = scene.generated_asset or scene.source_asset
            if not rel or not (project_dir / rel).exists():
                missing_assets.append(scene.scene_id)
    if missing_assets:
        warnings.append("Missing optional/required media for scenes: " + ", ".join(missing_assets))

    if plan.scenes[0].type != "talking_head":
        issues.append("Hook is not presenter-led")
    if plan.scenes[-1].type not in {"talking_head", "cta"}:
        issues.append("Close is not presenter-led")

    return {
        "episode_id": brief.episode_id,
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
        "scene_count": len(plan.scenes),
        "duration_seconds": plan.duration_seconds,
    }
