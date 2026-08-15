from __future__ import annotations

import json

from .models import (
    AudioTiming, DirectorBudgets, EpisodeBrief, Narration, StoryPlan,
    VoiceMetadata, WordTimestampBundle,
)
from .prompt_registry import build_prompt


def claim_handles(brief: EpisodeBrief) -> list[tuple[str, str]]:
    claims = [("pain-01", brief.pain_point)]
    claims.extend((f"backend-{index:02d}", value) for index, value in enumerate(brief.backend_summary, 1))
    claims.extend((f"diy-{index:02d}", value) for index, value in enumerate(brief.viewer_diy, 1))
    return claims


def story_structure_prompt(brief: EpisodeBrief) -> str:
    claims = claim_handles(brief)
    bundle = build_prompt(
        "story_structure",
        episode_id=brief.episode_id,
        title=brief.title,
        industry=brief.industry,
        role=brief.role,
        target_seconds=brief.target_seconds,
        case_nature=brief.case_nature,
        pain_point=brief.pain_point,
        claim_lines="\n".join(f"- {claim_id}: {text}" for claim_id, text in claims),
        diy_lines="\n".join(f"- {value}" for value in brief.viewer_diy) or "- No DIY steps supplied",
    )
    return f"{bundle.system}\n\n# CASE INPUT\n{bundle.user}"


def narration_prompt(brief: EpisodeBrief, story: StoryPlan) -> str:
    claims = claim_handles(brief)
    min_words, max_words = narration_word_budget(brief)
    bundle = build_prompt(
        "narration_writer",
        episode_id=brief.episode_id,
        target_seconds=brief.target_seconds,
        min_words=min_words,
        max_words=max_words,
        case_nature=story.case_nature,
        brief_json=json.dumps(brief.model_dump(mode="json"), indent=2),
        story_plan_json=json.dumps(story.model_dump(mode="json"), indent=2),
        claim_lines="\n".join(f"- {claim_id}: {text}" for claim_id, text in claims),
    )
    return f"{bundle.system}\n\n# APPROVED STRUCTURE AND FACTS\n{bundle.user}"


def narration_word_budget(brief: EpisodeBrief) -> tuple[int, int]:
    target_words = max(70, round(brief.target_seconds * 2.25))
    return max(60, target_words - 10), target_words + 8


def narration_rewrite_prompt(
    brief: EpisodeBrief,
    story: StoryPlan,
    draft: Narration,
    quality_issues: list[str],
) -> str:
    claims = claim_handles(brief)
    min_words, max_words = narration_word_budget(brief)
    bundle = build_prompt(
        "narration_rewrite",
        brief_json=json.dumps(brief.model_dump(mode="json"), indent=2),
        story_plan_json=json.dumps(story.model_dump(mode="json"), indent=2),
        claim_lines="\n".join(f"- {claim_id}: {text}" for claim_id, text in claims),
        min_words=min_words,
        max_words=max_words,
        draft_json=json.dumps(draft.model_dump(mode="json"), indent=2),
        quality_issues="\n".join(f"- {issue}" for issue in quality_issues),
    )
    return f"{bundle.system}\n\n# EDIT INPUT\n{bundle.user}"


def director_prompt(
    brief: EpisodeBrief,
    story: StoryPlan,
    narration: Narration,
    voice: VoiceMetadata | None,
    timing: AudioTiming | None = None,
    words: WordTimestampBundle | None = None,
    budgets: DirectorBudgets | None = None,
    include_talking_head: bool = True,
) -> str:
    duration = voice.duration_seconds if voice else narration.target_seconds
    bundle = build_prompt(
        "director",
        brief_json=json.dumps(brief.model_dump(mode="json"), indent=2),
        story_plan_json=json.dumps(story.model_dump(mode="json"), indent=2),
        narration_json=json.dumps(narration.model_dump(mode="json"), indent=2),
        duration_seconds=f"{duration:.3f}",
        audio_timing_json=json.dumps(timing.model_dump(mode="json"), indent=2) if timing else "Not available (offline mock only)",
        word_timestamps_json=json.dumps(words.model_dump(mode="json"), indent=2) if words else "Not available (offline mock only)",
        production_budgets_json=json.dumps((budgets or DirectorBudgets()).model_dump(mode="json"), indent=2),
        talking_head_policy="ENABLED" if include_talking_head else "DISABLED",
        available_renderers=(
            "manual_talking_head, infinite_talk, playwright, hyperframes, static"
            if include_talking_head else "playwright, hyperframes, static"
        ),
    )
    return f"{bundle.system}\n\n# PRODUCTION INPUT\n{bundle.user}"


def _screen_scene_timing(
    screen_scenes: list[dict], words: WordTimestampBundle | None,
) -> list[dict]:
    if words is None:
        return []
    result: list[dict] = []
    for scene in screen_scenes:
        start = float(scene.get("start", 0) or 0)
        end = float(scene.get("end", start) or start)
        scene_words = []
        for word in words.words:
            if word.end <= start or word.start >= end:
                continue
            scene_words.append({
                "word": word.word,
                "absolute_start": round(word.start, 3),
                "absolute_end": round(word.end, 3),
                "local_start": round(max(0.0, word.start - start), 3),
                "local_end": round(min(end - start, word.end - start), 3),
            })
        result.append({
            "scene_id": scene.get("scene_id"),
            "scene_start": round(start, 3),
            "scene_end": round(end, 3),
            "duration_seconds": round(end - start, 3),
            "words": scene_words,
        })
    return result


def prototype_builder_prompt(
    brief: EpisodeBrief,
    screen_scenes: list[dict],
    words: WordTimestampBundle | None = None,
) -> str:
    bundle = build_prompt(
        "prototype_builder",
        brief_json=json.dumps(brief.model_dump(mode="json"), indent=2),
        screen_scenes_json=json.dumps(screen_scenes, indent=2),
        screen_scene_timing_json=json.dumps(_screen_scene_timing(screen_scenes, words), indent=2),
    )
    return f"{bundle.system}\n\n# BUILD INPUT\n{bundle.user}"


def graphics_builder_prompt(
    brief: EpisodeBrief,
    narration: Narration,
    graphics_scenes: list[dict],
    screen_scenes: list[dict],
) -> str:
    bundle = build_prompt(
        "graphics_builder",
        brief_json=json.dumps(brief.model_dump(mode="json"), indent=2),
        narration_json=json.dumps(narration.model_dump(mode="json"), indent=2),
        graphics_scenes_json=json.dumps(graphics_scenes, indent=2),
        screen_scenes_json=json.dumps(screen_scenes, indent=2),
    )
    return f"{bundle.system}\n\n# GRAPHICS INPUT\n{bundle.user}"
