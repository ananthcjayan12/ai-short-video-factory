#!/usr/bin/env python3
"""Recover a custom graphics package from completed per-scene provider responses."""

from __future__ import annotations

import argparse
from pathlib import Path

from shorts_factory.custom_graphics import (
    CustomGraphicsLayoutPlan,
    CustomGraphicsPackage,
    CustomGraphicsSceneBundle,
    CustomGraphicsSource,
    custom_package_summary,
    validate_custom_graphics_source,
    write_custom_graphics_package,
)
from shorts_factory.io import load_model, read_json, write_json
from shorts_factory.models import DirectorPlan, EpisodeBrief, WordTimestampBundle
from shorts_factory.pipeline import _align_custom_layout_to_words, _validate_graphics_against_director
from shorts_factory.rendering.composition import build as build_composition


def _newest(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda item: item.stat().st_mtime_ns, reverse=True)


def recover(project: Path) -> Path:
    brief = load_model(project / "00_input/episode_brief.json", EpisodeBrief)
    director = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    words_path = project / "02_voice/audio_word_timestamps.json"
    words = load_model(words_path, WordTimestampBundle) if words_path.is_file() else None
    request_dir = project / "_requests"
    graphics_scenes = [
        scene for scene in director.scenes if scene.renderer in {"hyperframes", "static"}
    ]

    bundles: list[CustomGraphicsSceneBundle] = []
    recovered: list[dict[str, str]] = []
    for scene in graphics_scenes:
        stem = scene.scene_id.casefold()
        layout = None
        layout_path = None
        layout_errors: list[str] = []
        for candidate_path in _newest(list(request_dir.glob(f"graphics_layout_{stem}*_response.json"))):
            try:
                candidate = CustomGraphicsLayoutPlan.model_validate(read_json(candidate_path))
                if candidate.theme != brief.graphics_theme:
                    raise RuntimeError(
                        f"theme {candidate.theme!r} does not match {brief.graphics_theme!r}"
                    )
                layout = _align_custom_layout_to_words(candidate, scene, words, fps=brief.fps)
                layout_path = candidate_path
                break
            except Exception as exc:  # preserve every paid response and try the prior repair
                layout_errors.append(f"{candidate_path.name}: {exc}")
        if layout is None or layout_path is None:
            raise RuntimeError(
                f"No recoverable layout response for {scene.scene_id}: " + " | ".join(layout_errors)
            )

        source = None
        source_path = None
        source_errors: list[str] = []
        for candidate_path in _newest(list(request_dir.glob(f"graphics_coder_{stem}*_response.json"))):
            try:
                candidate = CustomGraphicsSource.model_validate(read_json(candidate_path))
                validate_custom_graphics_source(layout, candidate)
                source = candidate
                source_path = candidate_path
                break
            except Exception as exc:  # preserve every paid response and try the prior repair
                source_errors.append(f"{candidate_path.name}: {exc}")
        if source is None or source_path is None:
            raise RuntimeError(
                f"No recoverable code response for {scene.scene_id}: " + " | ".join(source_errors)
            )

        bundles.append(CustomGraphicsSceneBundle(
            layout=layout,
            source=source,
            repairs=["Recovered from completed provider response files after interrupted generation."],
        ))
        recovered.append({
            "scene_id": scene.scene_id,
            "layout_response": str(layout_path.relative_to(project)),
            "source_response": str(source_path.relative_to(project)),
        })

    package = CustomGraphicsPackage(
        episode_id=brief.episode_id,
        duration_seconds=director.duration_seconds,
        theme=brief.graphics_theme,
        scenes=bundles,
    )
    summary = custom_package_summary(package, creative_thesis=director.visual_thesis)
    _validate_graphics_against_director(summary, director)
    preview = write_custom_graphics_package(
        project, package, summary, width=brief.width, height=brief.height, fps=brief.fps,
    )
    composition = build_composition(
        project, preview=True, width=brief.width, height=brief.height, fps=brief.fps,
    )
    write_json(project / "08_graphics/recovery_manifest.json", {
        "episode_id": brief.episode_id,
        "scene_count": len(recovered),
        "source": "completed_provider_responses",
        "automated_visual_qa_run": False,
        "scenes": recovered,
        "graphics_preview": str(preview.relative_to(project)),
        "composition_preview": str(composition.relative_to(project)),
    })
    return composition


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    print(recover(args.project.resolve()))


if __name__ == "__main__":
    main()
