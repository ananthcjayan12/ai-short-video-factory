from __future__ import annotations

from pathlib import Path

from .director import validate_budgets, validate_presenter_policy, validate_word_boundaries
from .io import load_model
from .models import AudioTiming, DirectorPlan, EpisodeBrief, GraphicsPlan, VoiceMetadata, WordTimestampBundle
from .project import ProjectStore
from .timing import audio_sha256


def episode_qa(project_dir: Path) -> dict:
    issues: list[str] = []
    warnings: list[str] = []
    brief = load_model(project_dir / "00_input/episode_brief.json", EpisodeBrief)
    plan = load_model(project_dir / "03_director/director_plan.approved.json", DirectorPlan)
    issues.extend(validate_budgets(plan))
    include_talking_head = ProjectStore(project_dir.parent).settings().include_talking_head
    issues.extend(validate_presenter_policy(plan, include_talking_head=include_talking_head))

    if (project_dir / "02_voice/voice.json").exists():
        voice = load_model(project_dir / "02_voice/voice.json", VoiceMetadata)
        if abs(voice.duration_seconds - plan.duration_seconds) > 1.0:
            warnings.append(f"Voice duration {voice.duration_seconds:.2f}s differs from director plan {plan.duration_seconds:.2f}s")
        timing_path = project_dir / "02_voice/audio_timing.json"
        words_path = project_dir / "02_voice/audio_word_timestamps.json"
        if timing_path.exists() and words_path.exists():
            timing = load_model(timing_path, AudioTiming)
            words = load_model(words_path, WordTimestampBundle)
            digest = audio_sha256(project_dir / voice.audio_path)
            if timing.audio_sha256 != digest or words.audio_sha256 != digest:
                issues.append("Whisper word timing is stale for the current voice master")
            issues.extend(validate_word_boundaries(plan, words))
        elif voice.source == "mock":
            warnings.append("Offline timing track has no Whisper word alignment")
        else:
            issues.append("No validated Whisper word timing for the voice master")
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

    graphics_scenes = {scene.scene_id: scene for scene in plan.scenes if scene.renderer in {"hyperframes", "static"}}
    graphics_path = project_dir / "08_graphics/graphics_plan.json"
    if graphics_scenes and not graphics_path.is_file():
        issues.append("Graphics package has not been generated")
    elif graphics_scenes:
        graphics = load_model(graphics_path, GraphicsPlan)
        planned = {scene.scene_id: scene for scene in graphics.scenes}
        if set(planned) != set(graphics_scenes):
            issues.append("Graphics package does not cover every approved graphics scene")
        for scene_id in sorted(set(planned) & set(graphics_scenes)):
            contract = planned[scene_id]
            source = graphics_scenes[scene_id]
            if abs(contract.start - source.start) > 0.02 or abs(contract.end - source.end) > 0.02:
                issues.append(f"Graphics timing for {scene_id} differs from the approved timeline")
            if not (project_dir / f"08_graphics/scenes/{scene_id}.html").is_file():
                issues.append(f"Missing inspectable graphics preview for {scene_id}")
        if not (project_dir / "08_graphics/master.html").is_file():
            issues.append("Missing graphics master preview")

    if not (project_dir / "09_composition/preview/index.html").is_file():
        issues.append("Full interactive timeline preview has not been built")

    return {
        "episode_id": brief.episode_id,
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
        "scene_count": len(plan.scenes),
        "duration_seconds": plan.duration_seconds,
    }
