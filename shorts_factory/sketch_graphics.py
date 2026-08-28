from __future__ import annotations

import base64
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .io import load_model, write_json
from .models import (
    DirectorPlan,
    EpisodeBrief,
    EpisodeStage,
    GraphicsAction,
    GraphicsFrame,
    GraphicsObject,
    GraphicsPlan,
    GraphicsScenePlan,
    Narration,
    WordTimestampBundle,
)
from .orchestrator import resolve_task
from .pipeline import _run_graphics_agent, _structured_agent, load_config
from .progress import emit
from .project import ProjectStore
from .rendering.composition import build as build_composition


GRAPHICS_RENDERERS = {"hyperframes", "static"}


class SketchSceneAsset(BaseModel):
    """Prompt-only translation of one already-approved Director graphics scene."""

    model_config = ConfigDict(extra="forbid")

    scene_id: str
    image_prompt: str = Field(min_length=40)
    animation_prompt: str = Field(min_length=80)
    draw_order: list[str] = Field(min_length=2, max_length=12)
    focal_elements: list[str] = Field(min_length=1, max_length=10)
    camera_move: str = Field(min_length=2, max_length=180)
    final_hold: str = Field(
        default="Hold the completed drawing cleanly for the final beat.",
        min_length=10,
    )


class SketchAssetPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    episode_id: str
    visual_thesis: str
    scenes: list[SketchSceneAsset] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_scenes(self):
        ids = [scene.scene_id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("sketch scene IDs must be unique")
        return self


def _scene_words(words: WordTimestampBundle | None, scene: Any) -> list[dict[str, Any]]:
    if words is None:
        return []
    return [
        {
            "word": word.word,
            "start": round(word.start, 3),
            "end": round(word.end, 3),
        }
        for word in words.words
        if word.end > scene.start and word.start < scene.end
    ]


def _asset_prompt(
    *,
    brief: EpisodeBrief,
    narration: Narration,
    director: DirectorPlan,
    graphics_scenes: list[Any],
    words: WordTimestampBundle | None,
) -> str:
    payload = {
        "episode": {
            "episode_id": brief.episode_id,
            "title": brief.title,
            "industry": brief.industry,
            "role": brief.role,
            "graphics_theme": brief.graphics_theme,
            "canvas": {
                "width": brief.width,
                "height": brief.height,
                "fps": brief.fps,
            },
            "full_narration": narration.text,
        },
        "director_visual_thesis": director.visual_thesis,
        "approved_graphics_scenes": [
            {
                "scene_id": scene.scene_id,
                "start": scene.start,
                "end": scene.end,
                "narration_excerpt": scene.narration_excerpt,
                "purpose": scene.purpose,
                "visual_brief": scene.visual_brief,
                "emphasis": scene.emphasis,
                "on_screen_text": scene.on_screen_text,
                "word_timestamps": _scene_words(words, scene),
            }
            for scene in graphics_scenes
        ],
    }
    return (
        "# ROLE\n"
        "You are the image-and-motion translator for an approved vertical sketch-video Director plan.\n"
        "The Director has ALREADY decided which beats are illustrations and which beats are screen recordings. "
        "Do not add scenes, remove scenes, change timing, or reinterpret the story. Your job is to translate each "
        "approved graphics scene into one faithful whiteboard keyframe prompt and one image-to-video drawing prompt.\n\n"
        "# IMAGE LANGUAGE\n"
        "Create premium modern whiteboard/sketch illustrations: clean white background, confident black marker/ink "
        "linework, subtle gray shading, restrained teal/blue accents, and yellow/red only for warning or error. "
        "The image must feel designed by an experienced editorial illustrator, not like clip-art or a generic AI infographic.\n"
        "Use one strong visual idea per scene. Preserve natural body language. Prefer concrete episode-specific objects "
        "already present in the approved Director brief. Do not add stock business symbols just to fill the frame.\n"
        "Do not paste narration into the artwork. Text should be minimal: short labels, amounts, job names, or one tiny question "
        "only when it materially improves comprehension. Never invent metrics, savings, confidence values or customer facts.\n"
        "Design every frame specifically for 1080x1920 portrait viewing, with useful negative space and a clear focal hierarchy.\n\n"
        "# ANIMATION LANGUAGE\n"
        "The animation prompt must make the finished keyframe appear to be DRAWN LIVE from a blank whiteboard. "
        "Specify a logical stroke-by-stroke draw order, occasional marker-hand entry only when useful, arrows after their "
        "source objects, subtle camera push/pan, one or two emphasis pulses, and a clean final hold. "
        "Strictly forbid morphing, object substitution, extra text, 3D rendering, photorealism, facial distortion, "
        "random particles, and camera shake. The animation must preserve the exact reference composition.\n\n"
        "# TIMING\n"
        "Use the supplied Whisper word timestamps only as editorial context. The image itself is a keyframe; the animation "
        "should reveal the most important visual idea near the phrase that explains it. Do not return new timestamps and "
        "do not change Director scene boundaries.\n\n"
        "# OUTPUT\n"
        "Return exactly one SketchSceneAsset for every approved graphics scene, in the same order.\n\n"
        "# INPUT\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )


def _mock_asset_plan(
    episode_id: str,
    director: DirectorPlan,
    graphics_scenes: list[Any],
) -> SketchAssetPlan:
    return SketchAssetPlan(
        episode_id=episode_id,
        visual_thesis=director.visual_thesis,
        scenes=[
            SketchSceneAsset(
                scene_id=scene.scene_id,
                image_prompt=(
                    "Premium 9:16 whiteboard sketch on clean white background. "
                    + scene.visual_brief
                    + " Use black marker linework, subtle teal accents, minimal labels, and one clear focal story."
                ),
                animation_prompt=(
                    "Animate the supplied whiteboard keyframe from a blank white board. Draw the main subject first, "
                    "then supporting objects, then arrows and emphasis marks. Preserve every object and label exactly. "
                    "Use a subtle camera push and finish with a clean one-second hold. No morphing, no extra text, no 3D, "
                    "no photorealism, no distortion, no camera shake."
                ),
                draw_order=[
                    "main subject",
                    "supporting objects",
                    "arrows and relationships",
                    "final emphasis",
                ],
                focal_elements=[scene.purpose],
                camera_move="Very gentle portrait push-in toward the final visual proof.",
            )
            for scene in graphics_scenes
        ],
    )


def _codex_image_model(store: ProjectStore, episode_id: str) -> str:
    override = os.getenv("SVF_CODEX_IMAGE_MODEL", "").strip()
    if override:
        return override
    route = resolve_task(load_config(store, episode_id), "sketch_imagegen")
    if route.get("provider") != "codex":
        raise RuntimeError(
            "Sketch image generation uses Codex imagegen. Route sketch_imagegen to the Codex provider in Factory Desk "
            "or set SVF_CODEX_IMAGE_MODEL explicitly."
        )
    return str(route["model"])


def _run_codex_imagegen(
    store: ProjectStore,
    episode_id: str,
    *,
    scene: SketchSceneAsset,
    output: Path,
    prompt_file: Path,
) -> None:
    """Ask Codex to use its bundled imagegen skill and built-in image_gen tool.

    The system imagegen skill saves built-in results below CODEX_HOME, so the task
    explicitly requires copying the selected final into the episode workspace.
    We intentionally do not auto-fallback to the API-key CLI path.
    """

    output.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(scene.image_prompt + "\n", encoding="utf-8")
    model = _codex_image_model(store, episode_id)
    task_file = prompt_file.with_suffix(".codex.md")
    task_file.write_text(
        (
            "Use the system-provided imagegen skill for this project asset.\n\n"
            "IMPORTANT EXECUTION RULES:\n"
            "- Use the preferred BUILT-IN image_gen tool mode.\n"
            "- Do NOT silently use scripts/image_gen.py or an OPENAI_API_KEY fallback.\n"
            "- Generate exactly one final raster image.\n"
            "- The result is a project asset. After generation, copy the selected final from CODEX_HOME/generated_images "
            "into the exact destination below.\n"
            "- Do not create SVG, HTML, CSS, Canvas, or JavaScript instead of the raster image.\n"
            "- If built-in image_gen is unavailable in this Codex session, fail clearly.\n\n"
            f"DESTINATION:\n{output.resolve()}\n\n"
            f"IMAGE PROMPT:\n{scene.image_prompt}\n"
        ),
        encoding="utf-8",
    )
    command = (
        f"codex exec --skip-git-repo-check --model {shlex.quote(model)} - "
        f"< {shlex.quote(str(task_file.resolve()))}"
    )
    emit(
        35,
        f"{scene.scene_id}: generating whiteboard keyframe with Codex imagegen",
        task="graphics_builder",
    )
    result = subprocess.run(
        command,
        shell=True,
        cwd=output.parent,
        text=True,
        capture_output=True,
        timeout=max(120, int(os.getenv("SVF_IMAGEGEN_TIMEOUT_SECONDS", "900"))),
    )
    log_path = prompt_file.with_suffix(".imagegen.log")
    log_path.write_text(
        (result.stdout or "") + "\n" + (result.stderr or ""),
        encoding="utf-8",
    )
    if result.returncode != 0 or not output.is_file():
        raise RuntimeError(
            f"Codex imagegen failed for {scene.scene_id}. Built-in image_gen may not be exposed in this Codex session. "
            f"Inspect {log_path}. The pipeline intentionally did not switch to the API-key fallback automatically."
        )


def _write_mock_png(path: Path) -> None:
    """Tiny deterministic PNG used only by offline tests/mock mode."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/l4t9WQAAAABJRU5ErkJggg=="
        )
    )


def _run_optional_animation(
    scene_id: str,
    image: Path,
    prompt: Path,
    output: Path,
    duration: float,
) -> bool:
    template = os.getenv("SVF_GROK_ANIMATE_COMMAND", "").strip()
    if not template:
        return output.is_file()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = template.format(
        image=shlex.quote(str(image.resolve())),
        prompt=shlex.quote(str(prompt.resolve())),
        output=shlex.quote(str(output.resolve())),
        duration=f"{duration:.3f}",
        scene_id=scene_id,
    )
    emit(
        62,
        f"{scene_id}: running configured image-to-video animator",
        task="graphics_builder",
    )
    result = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        timeout=max(120, int(os.getenv("SVF_GROK_ANIMATE_TIMEOUT_SECONDS", "1200"))),
    )
    log = output.with_suffix(".animation.log")
    log.write_text(
        (result.stdout or "") + "\n" + (result.stderr or ""),
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Animation command failed for {scene_id}; inspect {log}")
    return output.is_file()


def _compat_scene(scene: Any, asset: SketchSceneAsset) -> GraphicsScenePlan:
    duration = scene.end - scene.start
    object_id = f"{scene.scene_id.lower()}_keyframe"
    return GraphicsScenePlan(
        scene_id=scene.scene_id,
        start=scene.start,
        end=scene.end,
        scene_shell="editorial_stage",
        motion_grammar="image_to_video_whiteboard",
        layout_variant="director_keyframe",
        visual_thesis=scene.visual_brief,
        headline=(scene.on_screen_text[0] if scene.on_screen_text else scene.purpose)[:120],
        support="Whiteboard keyframe + image-to-video drawing animation",
        visual_world="clean modern whiteboard sketch",
        opening_state="blank whiteboard before the illustration is drawn",
        payoff_state="completed Director-approved sketch composition",
        camera_move=(
            "push_in"
            if "push" in asset.camera_move.casefold()
            else "pan_left"
            if "pan left" in asset.camera_move.casefold()
            else "pan_right"
            if "pan right" in asset.camera_move.casefold()
            else "locked"
        ),
        continuity_object=(asset.focal_elements[0] if asset.focal_elements else None),
        objects=[
            GraphicsObject(
                object_id=object_id,
                object_type="artifact",
                role="generated whiteboard keyframe",
                label=(scene.on_screen_text[0] if scene.on_screen_text else scene.purpose)[:72],
                detail=scene.visual_brief[:240],
                slot="hero",
                frame=GraphicsFrame(
                    x=4,
                    y=4,
                    width=92,
                    height=92,
                    depth="foreground",
                ),
                visual_form="generated raster whiteboard illustration",
                show_detail=True,
                initially_visible=True,
            )
        ],
        actions=[
            GraphicsAction(
                at_seconds=0.0,
                action="hold",
                target=object_id,
                value="external image-to-video animation owns internal drawing motion",
                duration_seconds=max(0.2, min(4.0, duration)),
            )
        ],
        review_checkpoints=[
            round(max(0.0, min(duration, duration * 0.5)), 3)
        ],
    )


def generate_sketch_graphics_plan(
    store: ProjectStore,
    episode_id: str,
    *,
    agent_kind: str | None = None,
    consume_response: bool = False,
) -> GraphicsPlan:
    """Replace HTML/CSS/JS motion graphics with generated image + animation assets."""

    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    narration = load_model(project / "01_narration/narration.json", Narration)
    director_path = project / "03_director/director_plan.approved.json"
    director = load_model(director_path, DirectorPlan)
    graphics_scenes = [
        scene for scene in director.scenes if scene.renderer in GRAPHICS_RENDERERS
    ]
    if not graphics_scenes:
        raise RuntimeError(
            "The approved Director plan has no sketch/static graphics scenes"
        )

    words_path = project / "02_voice/audio_word_timestamps.json"
    words = (
        load_model(words_path, WordTimestampBundle)
        if words_path.is_file()
        else None
    )
    root = project / "08_graphics"
    image_root = root / "images"
    prompt_root = root / "prompts"
    animation_root = root / "animations"
    for directory in (image_root, prompt_root, animation_root):
        directory.mkdir(parents=True, exist_ok=True)

    configured_mock = False
    if agent_kind is None:
        configured_mock = (
            resolve_task(load_config(store, episode_id), "sketch_asset_planner")[
                "provider_mode"
            ]
            == "mock"
        )

    emit(
        10,
        f"Translating {len(graphics_scenes)} Director beats into whiteboard image assets",
        task="graphics_builder",
    )
    if agent_kind == "mock" or configured_mock:
        asset_plan = _mock_asset_plan(episode_id, director, graphics_scenes)
    else:
        agent = _structured_agent(
            store,
            "sketch_asset_planner",
            {"episode_id": episode_id},
            agent_kind=agent_kind,
            consume_response=consume_response,
        )
        asset_plan = _run_graphics_agent(
            agent,
            stage="sketch_asset_plan",
            prompt=_asset_prompt(
                brief=brief,
                narration=narration,
                director=director,
                graphics_scenes=graphics_scenes,
                words=words,
            ),
            output_model=SketchAssetPlan,
            request_dir=project / "_requests",
        )

    expected = [scene.scene_id for scene in graphics_scenes]
    actual = [scene.scene_id for scene in asset_plan.scenes]
    if actual != expected:
        raise RuntimeError(
            "Sketch asset order differs from Director order; "
            f"expected={expected}, actual={actual}"
        )
    write_json(root / "sketch_asset_plan.json", asset_plan)

    assets_by_scene: dict[str, str] = {}
    warnings: list[str] = []
    for index, (director_scene, asset) in enumerate(
        zip(graphics_scenes, asset_plan.scenes),
        1,
    ):
        image = image_root / f"{director_scene.scene_id}.png"
        image_prompt = prompt_root / f"{director_scene.scene_id}.image.md"
        animation_prompt = prompt_root / f"{director_scene.scene_id}.animation.md"
        image_prompt.write_text(asset.image_prompt + "\n", encoding="utf-8")
        animation_prompt.write_text(
            asset.animation_prompt + "\n",
            encoding="utf-8",
        )

        if not image.is_file():
            if agent_kind == "mock" or configured_mock:
                _write_mock_png(image)
            else:
                _run_codex_imagegen(
                    store,
                    episode_id,
                    scene=asset,
                    output=image,
                    prompt_file=image_prompt,
                )
        else:
            emit(
                28 + round(index / len(graphics_scenes) * 20),
                f"{director_scene.scene_id}: reusing existing keyframe",
                task="graphics_builder",
            )

        animated = animation_root / f"{director_scene.scene_id}.mp4"
        if _run_optional_animation(
            director_scene.scene_id,
            image,
            animation_prompt,
            animated,
            director_scene.end - director_scene.start,
        ):
            chosen = animated
        else:
            chosen = image
            warnings.append(
                f"{director_scene.scene_id}: animation pending; static keyframe is attached until "
                f"08_graphics/animations/{director_scene.scene_id}.mp4 exists"
            )
        assets_by_scene[director_scene.scene_id] = (
            chosen.relative_to(project).as_posix()
        )

    # Composition already prioritizes generated_asset/source_asset, so attaching
    # real image/video files removes the need for HTML/CSS graphics scenes.
    updated_scenes = [
        scene.model_copy(
            update={"generated_asset": assets_by_scene[scene.scene_id]}
        )
        if scene.scene_id in assets_by_scene
        else scene
        for scene in director.scenes
    ]
    director = director.model_copy(update={"scenes": updated_scenes})
    write_json(director_path, director)

    compat = GraphicsPlan(
        episode_id=episode_id,
        duration_seconds=director.duration_seconds,
        theme=brief.graphics_theme,
        creative_thesis=asset_plan.visual_thesis,
        scenes=[
            _compat_scene(scene, asset)
            for scene, asset in zip(graphics_scenes, asset_plan.scenes)
        ],
        warnings=warnings,
    )
    # Retain the repo's existing graphics_plan.json contract so Factory Desk,
    # artifact browsing and composition do not need a parallel application.
    write_json(root / "graphics_plan.json", compat)
    write_json(
        root / "sketch_manifest.json",
        {
            "episode_id": episode_id,
            "pipeline": "director -> codex imagegen -> image-to-video animation",
            "assets": assets_by_scene,
            "animation_command_configured": bool(
                os.getenv("SVF_GROK_ANIMATE_COMMAND", "").strip()
            ),
            "warnings": warnings,
        },
    )

    emit(
        88,
        "Building mixed-media preview with generated sketch assets",
        task="graphics_builder",
    )
    build_composition(
        project,
        preview=True,
        width=brief.width,
        height=brief.height,
        fps=brief.fps,
    )
    store.transition(episode_id, EpisodeStage.COMPOSITION_READY)
    emit(
        100,
        f"Prepared {len(compat.scenes)} image-first sketch scenes",
        task="graphics_builder",
    )
    return compat
