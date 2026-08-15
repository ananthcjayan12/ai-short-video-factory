from __future__ import annotations

import hashlib
import json
import math
import os
import re
import select
import shutil
import socket
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

from .agents import CommandAgent, ManualAgent, MockAgent, ProviderAgent, StructuredAgent
from .demo import bootstrap_pain001
from .director import (
    normalize, production_budgets, snap_to_word_boundaries, validate_budgets,
    validate_presenter_policy,
)
from .io import atomic_write_text, load_model, read_json, write_json
from .integrations import NATIVE_STRUCTURED_PROVIDERS, provider_environment
from .models import (
    AudioTiming, DemoAction, DemoJob, DemoJobBundle, DirectorPlan, EpisodeBrief, EpisodeStage, Narration, StoryPlan,
    GraphicsAction, GraphicsFrame, GraphicsObject, GraphicsPlan, GraphicsScenePlan, GraphicsTheme, GraphicsVisualReport, PrototypeRepairAttempt,
    PrototypeRepairIssue, PrototypeRepairReport, PrototypeVisualReport, VoiceMetadata, WordTimestampBundle,
)
from .node_runtime import node_binary
from .orchestrator import PROVIDERS, default_config, resolve_task
from .project import ProjectStore
from .progress import emit
from .prompts import (
    claim_handles, director_prompt, graphics_builder_prompt, narration_prompt, narration_rewrite_prompt,
    prototype_builder_prompt, prototype_repair_prompt, story_structure_prompt,
)
from .rendering.graphics import write_graphics_package
from .rendering.composition import build as build_composition
from .rendering.hyperframes import render as render_hyperframes
from .timing import align_words_to_narration, audio_sha256, transcribe_with_whisper
from .voice_batches import generate_batched_voice
from .story_quality import assess_narration


def load_config(store: ProjectStore, episode_id: str | None = None) -> dict[str, Any]:
    config = default_config()
    paths = [store.root / ".svf-orchestrator.json"]
    if episode_id:
        paths.append(store.project_dir(episode_id) / "_control/model-map.json")
    for path in paths:
        if not path.exists():
            continue
        saved = read_json(path)
        for task_id, values in saved.get("tasks", {}).items():
            if task_id in config["tasks"] and isinstance(values, dict):
                config["tasks"][task_id].update(values)
        for provider_id, values in saved.get("providers", {}).items():
            if provider_id in config["providers"] and isinstance(values, dict):
                config["providers"][provider_id].update(values)
        config["active_profile"] = saved.get("active_profile", config["active_profile"])
    return config


def _structured_agent(store: ProjectStore, task_id: str, context: dict[str, Any], *, agent_kind: str | None = None,
                      consume_response: bool = False) -> StructuredAgent:
    if agent_kind == "mock":
        return MockAgent(context)
    if agent_kind == "manual":
        return ManualAgent(consume_response=consume_response)
    episode_id = context.get("episode_id")
    config = load_config(store, episode_id)
    resolved = resolve_task(config, task_id)
    if resolved["provider_mode"] == "mock":
        return MockAgent(context)
    if resolved["provider_mode"] == "manual":
        return ManualAgent(consume_response=consume_response)
    if resolved["provider"] in NATIVE_STRUCTURED_PROVIDERS:
        fallback_provider = resolved.get("fallback_provider", "")
        if fallback_provider not in NATIVE_STRUCTURED_PROVIDERS:
            fallback_provider = ""
        return ProviderAgent(
            provider=resolved["provider"], model=resolved["model"],
            timeout=max(1, int(resolved.get("timeout_seconds", 900))),
            retries=int(resolved.get("retry_count", 1)),
            reasoning_effort=resolved.get("reasoning_effort"),
            fallback_provider=fallback_provider,
            fallback_model=resolved.get("fallback_model", ""),
        )
    if resolved["provider_adapter"] != "command":
        raise RuntimeError(f"Structured provider adapter not implemented in this MVP: {resolved['provider_adapter']}")
    fallback = PROVIDERS.get(resolved.get("fallback_provider"), {})
    fallback_template = ""
    if fallback.get("mode") == "command":
        fallback_template = config.get("providers", {}).get(fallback["id"], {}).get("command_template") or fallback.get("command_template", "")
    return CommandAgent(
        command_template=resolved["command_template"], model=resolved["model"],
        timeout=max(1, int(resolved.get("timeout_seconds", 900))), retries=int(resolved.get("retry_count", 1)),
        fallback_template=fallback_template, fallback_model=resolved.get("fallback_model", ""),
        provider=resolved["provider"], fallback_provider=resolved.get("fallback_provider", ""),
    )


def generate_story_plan(store: ProjectStore, episode_id: str, *, agent_kind: str | None = None,
                        consume_response: bool = False) -> StoryPlan:
    brief = store.brief(episode_id)
    emit(10, "Building the story structure", task="story_structure")
    context = {"episode_id": episode_id, "brief": brief}
    agent = _structured_agent(store, "story_structure", context, agent_kind=agent_kind,
                              consume_response=consume_response)
    story = agent.run(
        stage="story_structure", prompt=story_structure_prompt(brief), output_model=StoryPlan,
        request_dir=store.project_dir(episode_id) / "_requests",
    )
    known_claims = {claim_id for claim_id, _ in claim_handles(brief)}
    unknown = sorted({claim_id for beat in story.beats for claim_id in beat.claim_ids} - known_claims)
    if unknown:
        raise RuntimeError("Story plan references unknown claim handles: " + ", ".join(unknown))
    if story.story_spine is None:
        raise RuntimeError(
            "Story plan is missing the grounded story_spine. Regenerate it with the current client-story prompt."
        )
    write_json(store.project_dir(episode_id) / "01_narration/story_plan.json", story)
    emit(45, "Story structure validated", task="story_structure")
    return story


def generate_narration(store: ProjectStore, episode_id: str, *, agent_kind: str | None = None,
                       consume_response: bool = False) -> Narration:
    brief = store.brief(episode_id)
    story = generate_story_plan(store, episode_id, agent_kind=agent_kind, consume_response=consume_response)
    emit(50, "Writing narration from the approved structure", task="narration_writer")
    context = {"episode_id": episode_id, "brief": brief, "story": story}
    agent = _structured_agent(store, "narration_writer", context, agent_kind=agent_kind, consume_response=consume_response)
    project = store.project_dir(episode_id)
    narration = agent.run(stage="narration", prompt=narration_prompt(brief, story), output_model=Narration,
                          request_dir=project / "_requests")
    _validate_narration_mapping(brief, story, narration)
    write_json(project / "01_narration/narration_draft.json", narration)
    quality = assess_narration(brief, story, narration)
    write_json(project / "01_narration/narration_quality.json", quality)
    if not quality.passed:
        emit(72, "The first narration reads like an explainer; rewriting it as a client story", task="narration_writer")
        rewrite_agent = _structured_agent(
            store, "narration_qa", context, agent_kind=agent_kind, consume_response=consume_response,
        )
        narration = rewrite_agent.run(
            stage="narration_rewrite",
            prompt=narration_rewrite_prompt(brief, story, narration, quality.blocking_issues),
            output_model=Narration,
            request_dir=project / "_requests",
        )
        _validate_narration_mapping(brief, story, narration)
        quality = assess_narration(brief, story, narration)
        write_json(project / "01_narration/narration_quality.json", quality)
        if not quality.passed:
            raise RuntimeError(
                "Narration remained too weak after the automatic story rewrite: "
                + "; ".join(quality.blocking_issues)
                + ". Both drafts and the quality report were retained for review."
            )
        emit(88, "Narration rewrite passed the client-story quality gate", task="narration_writer")
    out = project / "01_narration"
    write_json(out / "narration.json", narration)
    atomic_write_text(out / "narration.txt", narration.text + "\n")
    store.transition(episode_id, EpisodeStage.NARRATION_READY)
    emit(100, "Narration validated and saved", task="narration_writer")
    return narration


def _validate_narration_mapping(brief: EpisodeBrief, story: StoryPlan, narration: Narration) -> None:
    if narration.paragraphs:
        story_beats = [beat.beat_id for beat in story.beats]
        paragraph_beats = [paragraph.beat_id for paragraph in narration.paragraphs]
        if paragraph_beats != story_beats:
            raise RuntimeError("Narration paragraphs must map one-to-one to story beats in sequence")
        known_claims = {claim_id for claim_id, _ in claim_handles(brief)}
        unknown = sorted({claim_id for paragraph in narration.paragraphs for claim_id in paragraph.claim_ids} - known_claims)
        if unknown:
            raise RuntimeError("Narration references unknown claim handles: " + ", ".join(unknown))


def _duration(path: Path) -> float:
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required to inspect non-WAV audio")
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return float(r.stdout.strip())


def import_voice(store: ProjectStore, episode_id: str, source: Path, *, source_kind: str = "manual") -> VoiceMetadata:
    project = store.project_dir(episode_id)
    dest = project / "02_voice" / f"voice_master{source.suffix.lower()}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    _clear_voice_timing(project)
    meta = VoiceMetadata(episode_id=episode_id, audio_path=str(dest.relative_to(project)), duration_seconds=_duration(dest), source=source_kind)
    write_json(project / "02_voice/voice.json", meta)
    store.transition(episode_id, EpisodeStage.VOICE_READY)
    return meta


def mock_voice(store: ProjectStore, episode_id: str, *, seconds: float = 58.0) -> VoiceMetadata:
    project = store.project_dir(episode_id)
    dest = project / "02_voice/voice_master.wav"
    dest.parent.mkdir(parents=True, exist_ok=True)
    _clear_voice_timing(project)
    rate = 16000
    with wave.open(str(dest), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * int(rate * seconds))
    meta = VoiceMetadata(episode_id=episode_id, audio_path=str(dest.relative_to(project)), duration_seconds=seconds, source="mock")
    write_json(project / "02_voice/voice.json", meta)
    store.transition(episode_id, EpisodeStage.VOICE_READY)
    emit(100, "Timing voice created", task="voice_generator")
    return meta


def _clear_voice_timing(project: Path) -> None:
    for name in ("audio_word_timestamps.json", "audio_timing.json"):
        (project / "02_voice" / name).unlink(missing_ok=True)


def align_voice(store: ProjectStore, episode_id: str, *, force: bool = False) -> AudioTiming:
    """Create the master word clock using local OpenAI Whisper for every voice provider."""
    project = store.project_dir(episode_id)
    narration = load_model(project / "01_narration/narration.json", Narration)
    voice_path = project / "02_voice/voice.json"
    if not voice_path.exists():
        raise RuntimeError("Master voice is missing. Generate or import voice before alignment.")
    voice = load_model(voice_path, VoiceMetadata)
    audio_path = project / voice.audio_path
    digest = audio_sha256(audio_path)
    timing_path = project / "02_voice/audio_timing.json"
    words_path = project / "02_voice/audio_word_timestamps.json"

    if not force and timing_path.exists() and words_path.exists():
        cached_timing = load_model(timing_path, AudioTiming)
        cached_words = load_model(words_path, WordTimestampBundle)
        if cached_timing.audio_sha256 == digest and cached_words.audio_sha256 == digest:
            voice = voice.model_copy(update={
                "timing_path": "02_voice/audio_timing.json",
                "word_timestamps_path": "02_voice/audio_word_timestamps.json",
            })
            write_json(voice_path, voice)
            store.transition(episode_id, EpisodeStage.TIMING_READY)
            emit(100, "Reused validated Whisper word timestamps", task="voice_aligner")
            return cached_timing

    emit(10, "Loading local Whisper for word-level alignment", task="voice_aligner")
    transcript_words, whisper_model = transcribe_with_whisper(audio_path)
    emit(75, f"Aligning {len(transcript_words)} Whisper words to narration beats", task="voice_aligner")
    bundle, timing = align_words_to_narration(
        narration=narration,
        transcript_words=transcript_words,
        audio_duration=voice.duration_seconds,
        audio_hash=digest,
        whisper_model=whisper_model,
    )
    write_json(words_path, bundle)
    write_json(timing_path, timing)
    voice = voice.model_copy(update={
        "timing_path": "02_voice/audio_timing.json",
        "word_timestamps_path": "02_voice/audio_word_timestamps.json",
    })
    write_json(voice_path, voice)
    store.transition(episode_id, EpisodeStage.TIMING_READY)
    emit(100, f"Validated {len(bundle.words)} Whisper word timestamps", task="voice_aligner")
    return timing


def generate_director_plan(store: ProjectStore, episode_id: str, *, agent_kind: str | None = None,
                           consume_response: bool = False) -> DirectorPlan:
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    story_path = project / "01_narration/story_plan.json"
    if not story_path.exists():
        raise RuntimeError("Story plan is missing. Run narration before directing.")
    story = load_model(story_path, StoryPlan)
    narration = load_model(project / "01_narration/narration.json", Narration)
    voice = load_model(project / "02_voice/voice.json", VoiceMetadata) if (project / "02_voice/voice.json").exists() else None
    timing_path = project / "02_voice/audio_timing.json"
    words_path = project / "02_voice/audio_word_timestamps.json"
    timing = load_model(timing_path, AudioTiming) if timing_path.exists() else None
    words = load_model(words_path, WordTimestampBundle) if words_path.exists() else None
    if agent_kind != "mock":
        if not voice:
            raise RuntimeError("Master voice is missing. Generate or import voice before directing.")
        if not timing or not words:
            raise RuntimeError("Whisper word alignment is missing. Run `svf align-voice EPISODE_ID` before directing.")
        digest = audio_sha256(project / voice.audio_path)
        if timing.audio_sha256 != digest or words.audio_sha256 != digest:
            raise RuntimeError("Whisper timing is stale because the voice changed. Run align-voice again.")
    include_talking_head = store.settings().include_talking_head
    duration = voice.duration_seconds if voice else narration.target_seconds
    budgets = production_budgets(
        duration_seconds=duration,
        include_talking_head=include_talking_head,
    )
    emit(15, "Mapping narration beats to visual scenes", task="director")
    context = {"episode_id": episode_id, "brief": brief, "story": story, "narration": narration, "voice": voice,
               "timing": timing, "words": words}
    agent = _structured_agent(store, "director", context, agent_kind=agent_kind, consume_response=consume_response)
    raw = agent.run(stage="director", prompt=director_prompt(
        brief, story, narration, voice, timing, words,
        budgets=budgets, include_talking_head=include_talking_head,
    ), output_model=DirectorPlan,
                    request_dir=project / "_requests")
    write_json(project / "03_director/director_plan.raw.json", raw)
    warnings = list(raw.warnings)
    if raw.budgets != budgets:
        warnings.append("AI-supplied budget fields ignored; deterministic project budgets applied")
    raw = raw.model_copy(update={"budgets": budgets, "warnings": warnings})
    if timing and words:
        raw = snap_to_word_boundaries(raw, timing, words)
    normalized = normalize(raw, include_talking_head=include_talking_head)
    write_json(project / "03_director/director_plan.json", normalized)
    store.transition(episode_id, EpisodeStage.DIRECTOR_REVIEW)
    emit(100, "Director plan normalized and ready for review", task="director")
    return normalized


def approve_director(store: ProjectStore, episode_id: str) -> DirectorPlan:
    project = store.project_dir(episode_id)
    plan = load_model(project / "03_director/director_plan.json", DirectorPlan)
    issues = validate_budgets(plan)
    issues.extend(validate_presenter_policy(
        plan, include_talking_head=store.settings().include_talking_head,
    ))
    if issues:
        raise RuntimeError("Director plan violates production budgets: " + "; ".join(issues))
    write_json(project / "03_director/director_plan.approved.json", plan)
    store.approve_director(episode_id)
    return plan


def bootstrap_reference_demo(store: ProjectStore, episode_id: str) -> None:
    project = store.project_dir(episode_id)
    bootstrap_pain001(project)


def record_demos(store: ProjectStore, episode_id: str, *, port: int = 4173) -> list[Path]:
    project = store.project_dir(episode_id)
    bundle = ensure_demo_jobs(store, episode_id, port=port)
    jobs = bundle.jobs
    if not jobs:
        raise RuntimeError("The approved director plan has no screen-recording scenes to capture.")
    repo_root = Path(__file__).resolve().parents[1]
    prototype_root = project / "04_prototype/dist"
    if not (prototype_root / "index.html").is_file():
        prototype_root = project / "04_prototype"
    server = subprocess.Popen([sys.executable, str(repo_root / "scripts/serve_demo.py"), str(prototype_root), str(port)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_for_local_server(server, port)
        outputs: list[Path] = []
        total = max(1, len(jobs))
        for index, job in enumerate(jobs, 1):
            emit(10 + ((index - 1) / total) * 80, f"Recording {job.job_id}", task="screen_recorder")
            job_path = project / "05_asset_jobs" / f"{job.job_id}.json"
            r = subprocess.run([str(node_binary()), str(repo_root / "scripts/record_demo.mjs"), str(job_path), str(project)],
                               cwd=repo_root, capture_output=True, text=True, timeout=600)
            (project / "06_recordings" / f"{job.job_id}.log").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
            if r.returncode != 0:
                raise RuntimeError(f"Playwright recording failed for {job.job_id}: {(r.stderr or r.stdout)[-3000:]}")
            outputs.append(project / job.output_path)
        _attach_recordings_to_plan(project, [job.model_dump(mode="json") for job in jobs])
        store.transition(episode_id, EpisodeStage.ASSETS_READY)
        emit(100, f"Recorded {len(outputs)} screen demos", task="screen_recorder")
        return outputs
    finally:
        server.terminate()
        try: server.wait(timeout=3)
        except subprocess.TimeoutExpired: server.kill()


def _wait_for_local_server(server: subprocess.Popen[Any], port: int, *, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        returncode = server.poll()
        if returncode is not None:
            raise RuntimeError(f"Prototype server exited before recording started (status {returncode})")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"Prototype server did not become ready on port {port}: {last_error}")


def _attach_recordings_to_plan(project: Path, jobs: list[dict[str, Any]]) -> None:
    plan = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    by_id = {j["job_id"]: j for j in jobs}
    scenes = []
    for scene in plan.scenes:
        if scene.demo_job_id and scene.demo_job_id in by_id:
            scene = scene.model_copy(update={"generated_asset": by_id[scene.demo_job_id]["output_path"]})
        scenes.append(scene)
    write_json(project / "03_director/director_plan.approved.json", plan.model_copy(update={"scenes": scenes}))


def ensure_demo_jobs(store: ProjectStore, episode_id: str, *, port: int = 4173) -> DemoJobBundle:
    """Load builder-authored capture contracts or create an offline static fallback.

    Once the Whisper master clock exists, builder-authored timeline cues are required
    and verified against the spoken word anchors. Static fallback contracts remain
    available only for offline/mock projects with no word timing artifact.
    """
    project = store.project_dir(episode_id)
    _stage_builder_demo_jobs(project, project / "04_prototype")
    plan = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    scenes = [scene for scene in plan.scenes if scene.type == "screen_recording" and scene.renderer == "playwright"]
    scenes_by_id = {scene.scene_id: scene for scene in scenes}
    words_path = project / "02_voice/audio_word_timestamps.json"
    words = load_model(words_path, WordTimestampBundle) if words_path.is_file() else None
    expected_scene_ids = {scene.scene_id for scene in scenes}
    jobs_path = project / "05_asset_jobs/demo_jobs.json"
    if jobs_path.is_file():
        bundle = load_model(jobs_path, DemoJobBundle)
        if bundle.episode_id != episode_id:
            raise RuntimeError("Demo job bundle belongs to a different episode")
        actual_scene_ids = [job.scene_id for job in bundle.jobs]
        if len(actual_scene_ids) != len(set(actual_scene_ids)):
            raise RuntimeError("Demo job bundle contains duplicate scene capture contracts")
        if set(actual_scene_ids) != expected_scene_ids:
            raise RuntimeError(
                "Demo job coverage differs from the approved screen scenes; "
                f"expected={sorted(expected_scene_ids)}, actual={sorted(set(actual_scene_ids))}"
            )
        for job in bundle.jobs:
            _validate_demo_job(job, project, scene=scenes_by_id[job.scene_id], words=words)
        return bundle

    if not (project / "04_prototype/index.html").is_file() and not (project / "04_prototype/dist/index.html").is_file():
        raise RuntimeError("No prototype entrypoint. Build the prototype before recording demos.")
    jobs: list[DemoJob] = []
    for scene in scenes:
        job_id = scene.demo_job_id or f"demo-{scene.scene_id.lower()}"
        job = DemoJob(
            job_id=job_id,
            scene_id=scene.scene_id,
            url=f"http://127.0.0.1:{port}/index.html#{scene.scene_id}",
            output_path=f"06_recordings/{scene.scene_id.lower()}-{job_id}.webm",
            actions=[
                DemoAction(action="goto", value=f"http://127.0.0.1:{port}/index.html#{scene.scene_id}"),
                DemoAction(action="wait", milliseconds=1500),
            ],
        )
        _validate_demo_job(job, project, scene=scene, words=words)
        jobs.append(job)
    bundle = DemoJobBundle(episode_id=episode_id, jobs=jobs)
    write_json(jobs_path, bundle)
    for job in jobs:
        write_json(project / "05_asset_jobs" / f"{job.job_id}.json", job)
    if jobs:
        emit(5, f"Prepared {len(jobs)} validated demo capture contracts", task="screen_recorder")
    return bundle


def _stage_builder_demo_jobs(project: Path, out_dir: Path) -> DemoJobBundle | None:
    """Promote sandbox-local builder contracts into the canonical episode folder."""

    candidates = [
        out_dir / "asset_jobs/demo_jobs.json",
        out_dir / "05_asset_jobs/demo_jobs.json",
        out_dir / "dist/asset_jobs/demo_jobs.json",
    ]
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        return None
    bundle = load_model(source, DemoJobBundle)
    if bundle.episode_id != project.name:
        raise RuntimeError(
            f"Prototype capture contracts belong to {bundle.episode_id}, not episode {project.name}"
        )
    target = project / "05_asset_jobs"
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "demo_jobs.json", bundle)
    for job in bundle.jobs:
        write_json(target / f"{job.job_id}.json", job)
    emit(4, f"Staged {len(bundle.jobs)} builder-authored demo contracts", task="prototype_builder")
    return bundle


def _cue_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _cue_anchor_start(
    anchor_text: str,
    scene: Any,
    words: WordTimestampBundle,
    *,
    occurrence: int = 0,
) -> float | None:
    anchor = _cue_tokens(anchor_text)
    if not anchor:
        return None
    scene_words = [word for word in words.words if word.end > scene.start and word.start < scene.end]
    tokens: list[str] = []
    starts: list[float] = []
    for word in scene_words:
        for token in _cue_tokens(word.word):
            tokens.append(token)
            starts.append(word.start)
    matches = [
        max(0.0, starts[index] - scene.start)
        for index in range(0, len(tokens) - len(anchor) + 1)
        if tokens[index:index + len(anchor)] == anchor
    ]
    return matches[occurrence] if occurrence < len(matches) else None


def _validate_demo_job(
    job: DemoJob,
    project: Path,
    *,
    scene: Any | None = None,
    words: WordTimestampBundle | None = None,
) -> None:
    brief = load_model(project / "00_input/episode_brief.json", EpisodeBrief)
    if job.viewport_width != brief.width or job.viewport_height != brief.height:
        raise RuntimeError(
            f"Demo job {job.job_id} viewport must match the {brief.width}x{brief.height} portrait episode canvas"
        )
    if job.viewport_width >= job.viewport_height:
        raise RuntimeError(f"Demo job {job.job_id} must use a portrait viewport")
    if not job.url.endswith(f"#{job.scene_id}"):
        raise RuntimeError(f"Demo job {job.job_id} URL must open its own #{job.scene_id} camera-ready state")
    output = (project / job.output_path).resolve()
    recordings = (project / "06_recordings").resolve()
    if recordings not in output.parents or output.suffix.lower() not in {".webm", ".mp4"}:
        raise RuntimeError(f"Demo job {job.job_id} must write a .webm or .mp4 inside 06_recordings")
    if not job.actions:
        raise RuntimeError(f"Demo job {job.job_id} must contain at least one capture action")
    if scene is None or words is None:
        return
    expected_duration = scene.end - scene.start
    if job.duration_seconds is None or abs(job.duration_seconds - expected_duration) > 0.12:
        raise RuntimeError(
            f"Demo job {job.job_id} duration_seconds must match scene {scene.scene_id} "
            f"duration {expected_duration:.3f}s"
        )
    if not job.timeline_cues:
        raise RuntimeError(
            f"Demo job {job.job_id} has no Whisper-timed choreography. Rebuild the prototype so its "
            "visual reveals follow the supplied word timestamps."
        )
    prototype_root = project / "04_prototype/dist"
    if not (prototype_root / "index.html").is_file():
        prototype_root = project / "04_prototype"
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for suffix in ("*.html", "*.js", "*.css")
        for path in prototype_root.rglob(suffix)
        if not any(part in {"node_modules", ".next"} for part in path.parts)
    )
    if "__svfSetTime" not in source:
        raise RuntimeError(
            f"Prototype for {job.scene_id} must implement window.__svfSetTime(localSeconds, timelineCues)"
        )
    previous = -1.0
    for cue in job.timeline_cues:
        expected = _cue_anchor_start(cue.anchor_text, scene, words)
        if expected is None:
            raise RuntimeError(
                f"Prototype cue {cue.cue_id} anchor {cue.anchor_text!r} is not an exact consecutive phrase "
                f"in the Whisper words for {scene.scene_id}"
            )
        if abs(cue.at_seconds - expected) > 0.18:
            raise RuntimeError(
                f"Prototype cue {cue.cue_id} is at {cue.at_seconds:.3f}s but its Whisper anchor "
                f"{cue.anchor_text!r} starts at {expected:.3f}s in {scene.scene_id}"
            )
        if cue.at_seconds < previous:
            raise RuntimeError(f"Prototype cues for {job.job_id} must be chronological")
        previous = cue.at_seconds
        selector_pattern = rf'data-testid\s*=\s*["\']{re.escape(cue.target_testid)}["\']'
        if not re.search(selector_pattern, source):
            raise RuntimeError(
                f"Prototype cue {cue.cue_id} targets missing data-testid={cue.target_testid!r}"
            )


def import_talking_head(store: ProjectStore, episode_id: str, scene_id: str, source: Path) -> Path:
    if not store.settings().include_talking_head:
        raise RuntimeError("Talking head is disabled for this project")
    project = store.project_dir(episode_id)
    plan_path = project / "03_director/director_plan.approved.json"
    plan = load_model(plan_path, DirectorPlan)
    target_scene = next((s for s in plan.scenes if s.scene_id == scene_id), None)
    if not target_scene or target_scene.type not in {"talking_head", "cta"}:
        raise ValueError(f"{scene_id} is not a talking-head scene")
    dest = project / "07_talking_head" / f"{scene_id}{source.suffix.lower()}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    scenes = [s.model_copy(update={"generated_asset": str(dest.relative_to(project))}) if s.scene_id == scene_id else s for s in plan.scenes]
    write_json(plan_path, plan.model_copy(update={"scenes": scenes}))
    return dest


def write_prototype_builder_prompt(store: ProjectStore, episode_id: str) -> Path:
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    plan = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    screens = [s for s in plan.scenes if s.type == "screen_recording"]
    words_path = project / "02_voice/audio_word_timestamps.json"
    words = load_model(words_path, WordTimestampBundle) if words_path.is_file() else None
    prompt = prototype_builder_prompt(brief, [s.model_dump(mode="json") for s in screens], words)
    path = project / "_requests/prototype_builder_prompt.md"
    atomic_write_text(path, prompt)
    return path


def run_prototype_builder(store: ProjectStore, episode_id: str) -> Path:
    project = store.project_dir(episode_id)
    prompt = write_prototype_builder_prompt(store, episode_id)
    config = load_config(store, episode_id)
    route = resolve_task(config, "prototype_builder")
    provider = route["provider"]
    model = route["model"]
    stdin_handle = None
    if provider == "codex":
        cmd = f"codex exec --skip-git-repo-check --model {shlex_quote(model)} - < {shlex_quote(str(prompt))}"
    elif provider == "claude_code":
        cmd = f"claude --model {shlex_quote(model)} -p \"$(cat {shlex_quote(str(prompt))})\""
    else:
        raise RuntimeError(f"Prototype code adapter for {provider} is not configured")
    out_dir = project / "04_prototype"
    out_dir.mkdir(parents=True, exist_ok=True)
    timeout = int(route.get("timeout_seconds", 1800))
    emit(10, f"Starting {provider} prototype builder", task="prototype_builder")
    process = subprocess.Popen(
        cmd, shell=True, cwd=out_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=provider_environment(),
    )
    output: list[str] = []
    started = time.monotonic()
    last_heartbeat = 0.0
    last_activity: tuple[float, int, str | None] | None = None
    try:
        while process.poll() is None:
            if process.stdout:
                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if ready:
                    line = process.stdout.readline()
                    if line:
                        output.append(line)
            activity = _prototype_activity(out_dir)
            now = time.monotonic()
            if now - started > timeout:
                raise subprocess.TimeoutExpired(cmd, timeout)
            if activity != last_activity:
                latest_mtime, file_count, newest = activity
                if newest:
                    elapsed = int(now - started)
                    progress = min(85, 15 + min(65, file_count // 2))
                    emit(progress, f"Prototype activity: updated {newest} ({file_count} source files, {elapsed}s elapsed)", task="prototype_builder")
                last_activity = activity
                last_heartbeat = now
            elif now - last_heartbeat >= 15:
                emit(15, f"{provider} is still working; waiting for the next prototype file update ({int(now - started)}s elapsed)", task="prototype_builder")
                last_heartbeat = now
        if process.stdout:
            output.extend(process.stdout.readlines())
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        raise
    returncode = process.wait()
    log_text = "".join(output)
    atomic_write_text(project / "_requests/prototype_builder.log", log_text)
    if returncode != 0:
        raise RuntimeError(f"Prototype builder failed: {log_text[-4000:]}")
    emit(88, "Validating the prototype and repairing measured failures when needed", task="prototype_builder")
    repair_prototype(store, episode_id)
    emit(100, "Prototype builder completed", task="prototype_builder")
    return out_dir


def _prototype_activity(out_dir: Path) -> tuple[float, int, str | None]:
    """Return meaningful source-file activity without dependency churn."""
    ignored = {".git", ".next", ".venv", "node_modules", "__pycache__", "dist", "build"}
    newest_mtime = 0.0
    newest_path: str | None = None
    file_count = 0
    for parent, folders, files in os.walk(out_dir):
        folders[:] = [folder for folder in folders if folder not in ignored]
        for name in files:
            path = Path(parent) / name
            try:
                stamp = path.stat().st_mtime
            except OSError:
                continue
            file_count += 1
            if stamp > newest_mtime:
                newest_mtime = stamp
                newest_path = path.relative_to(out_dir).as_posix()
    return newest_mtime, file_count, newest_path


class PrototypeVisualValidationError(RuntimeError):
    def __init__(self, report: PrototypeVisualReport):
        super().__init__("Prototype browser visual QA failed")
        self.report = report


def _prototype_source_inventory(out_dir: Path) -> list[dict[str, Any]]:
    ignored = {".git", ".next", ".venv", "node_modules", "__pycache__", "dist", "build", "output"}
    inventory: list[dict[str, Any]] = []
    for parent, folders, files in os.walk(out_dir):
        folders[:] = sorted(folder for folder in folders if folder not in ignored)
        for name in sorted(files):
            path = Path(parent) / name
            if path.suffix.lower() not in {".html", ".css", ".js", ".mjs", ".cjs", ".json", ".md", ".csv"}:
                continue
            data = path.read_bytes()
            inventory.append({
                "path": path.relative_to(out_dir).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            })
    return inventory


def _prototype_inventory_hash(inventory: list[dict[str, Any]]) -> str:
    payload = json.dumps(inventory, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _archive_prototype_sources(out_dir: Path, destination: Path, inventory: list[dict[str, Any]]) -> None:
    for item in inventory:
        source = out_dir / item["path"]
        target = destination / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _prototype_validation_issues(
    store: ProjectStore, episode_id: str,
) -> tuple[Path | None, list[PrototypeRepairIssue]]:
    project = store.project_dir(episode_id)
    out_dir = project / "04_prototype"
    plan = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    screen_scenes = [
        scene for scene in plan.scenes
        if scene.type == "screen_recording" and scene.renderer == "playwright"
    ]
    try:
        entrypoint = _validate_static_prototype(out_dir, screen_scenes=screen_scenes)
    except Exception as exc:
        return None, [PrototypeRepairIssue(stage="static_contract", message=str(exc))]
    try:
        _stage_builder_demo_jobs(project, out_dir)
        ensure_demo_jobs(store, episode_id)
    except Exception as exc:
        return entrypoint, [PrototypeRepairIssue(stage="demo_contract", message=str(exc))]
    emit(90, "Checking every prototype proof scene at reel and phone sizes", task="prototype_repair")
    try:
        _validate_prototype_visuals(project, entrypoint, [scene.scene_id for scene in screen_scenes])
    except PrototypeVisualValidationError as exc:
        failed = [finding for finding in exc.report.findings if finding.issues]
        return entrypoint, [PrototypeRepairIssue(
            stage="visual_qa",
            message=f"{len(failed)} browser checks failed across the approved proof scenes",
            findings=failed,
        )]
    except Exception as exc:
        return entrypoint, [PrototypeRepairIssue(stage="visual_qa", message=str(exc))]
    return entrypoint, []


def _run_prototype_repair_agent(
    *, route: dict[str, Any], prompt: Path, out_dir: Path, timeout: int,
) -> tuple[int, str]:
    provider = route["provider"]
    model = route["model"]
    if provider == "codex":
        command = ["codex", "exec", "--skip-git-repo-check", "--model", model]
        reasoning = route.get("reasoning_effort")
        if reasoning:
            command.extend(["-c", f'model_reasoning_effort="{reasoning}"'])
        command.append("-")
        stdin_handle = prompt.open("r", encoding="utf-8")
        stdin: Any = stdin_handle
    elif provider == "claude_code":
        command = ["claude", "--model", model, "-p", prompt.read_text(encoding="utf-8")]
        stdin = subprocess.DEVNULL
    else:
        raise RuntimeError(f"Prototype repair adapter for {provider} is not configured")
    process = subprocess.Popen(
        command, cwd=out_dir, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=provider_environment(),
    )
    output: list[str] = []
    started = time.monotonic()
    last_heartbeat = started
    try:
        while process.poll() is None:
            if process.stdout:
                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if ready:
                    line = process.stdout.readline()
                    if line:
                        output.append(line)
            now = time.monotonic()
            if now - started > timeout:
                raise subprocess.TimeoutExpired(command, timeout)
            if now - last_heartbeat >= 15:
                _, file_count, newest = _prototype_activity(out_dir)
                detail = f"; latest file {newest}" if newest else ""
                emit(92, f"{provider} repair is working ({file_count} source files{detail})", task="prototype_repair")
                last_heartbeat = now
        if process.stdout:
            output.extend(process.stdout.readlines())
        return process.wait(), "".join(output)
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        raise
    finally:
        if stdin_handle is not None:
            stdin_handle.close()


def repair_prototype(
    store: ProjectStore, episode_id: str, *, max_attempts: int | None = None,
) -> PrototypeRepairReport:
    """Validate an existing prototype and run bounded, evidence-only AI repairs."""
    project = store.project_dir(episode_id)
    out_dir = project / "04_prototype"
    if not out_dir.exists():
        raise RuntimeError("No prototype exists to validate or repair")
    configured = int(os.getenv("SVF_PROTOTYPE_REPAIR_ATTEMPTS", "2")) if max_attempts is None else max_attempts
    limit = max(0, min(3, configured))
    report_path = project / "_requests/prototype_repair_report.json"
    _, issues = _prototype_validation_issues(store, episode_id)
    if not issues:
        if report_path.is_file():
            previous = load_model(report_path, PrototypeRepairReport)
            if previous.status == "repaired":
                return previous
        report = PrototypeRepairReport(
            episode_id=episode_id, status="not_needed", max_attempts=limit,
        )
        write_json(report_path, report)
        return report
    if limit == 0:
        report = PrototypeRepairReport(
            episode_id=episode_id, status="failed", max_attempts=0, final_issues=issues,
        )
        write_json(report_path, report)
        raise RuntimeError("Prototype validation failed and automatic repair is disabled")

    route = resolve_task(load_config(store, episode_id), "prototype_repair")
    attempts: list[PrototypeRepairAttempt] = []
    repair_root = project / "_requests/prototype_repairs"
    run_id = time.strftime("run-%Y%m%dT%H%M%SZ", time.gmtime()) + f"-{os.getpid()}"
    repair_run_root = repair_root / run_id
    for attempt_number in range(1, limit + 1):
        attempt_root = repair_run_root / f"attempt-{attempt_number:02d}"
        inventory_before = _prototype_source_inventory(out_dir)
        before_hash = _prototype_inventory_hash(inventory_before)
        _archive_prototype_sources(out_dir, attempt_root / "before", inventory_before)
        prompt = prototype_repair_prompt(
            episode_id=episode_id, attempt=attempt_number, max_attempts=limit,
            issues=[issue.model_dump(mode="json", by_alias=True) for issue in issues],
            source_inventory=inventory_before,
        )
        prompt_path = attempt_root / "prompt.md"
        log_path = attempt_root / "provider.log"
        atomic_write_text(prompt_path, prompt)
        emit(91, f"Starting prototype repair {attempt_number}/{limit} with {route['provider']}", task="prototype_repair")
        provider_issue: PrototypeRepairIssue | None = None
        try:
            returncode, log = _run_prototype_repair_agent(
                route=route, prompt=prompt_path, out_dir=out_dir,
                timeout=max(60, int(route.get("timeout_seconds", 1200))),
            )
            atomic_write_text(log_path, log)
            if returncode != 0:
                provider_issue = PrototypeRepairIssue(
                    stage="repair_provider", message=f"{route['provider']} exited with status {returncode}: {log[-2000:]}",
                )
        except Exception as exc:
            atomic_write_text(log_path, str(exc) + "\n")
            provider_issue = PrototypeRepairIssue(stage="repair_provider", message=str(exc))

        if provider_issue:
            issues_after = [*issues, provider_issue]
        else:
            _, issues_after = _prototype_validation_issues(store, episode_id)
        inventory_after = _prototype_source_inventory(out_dir)
        after_hash = _prototype_inventory_hash(inventory_after)
        attempt = PrototypeRepairAttempt(
            attempt=attempt_number, provider=route["provider"], model=route["model"],
            status="repaired" if not issues_after else "failed",
            prompt_path=prompt_path.relative_to(project).as_posix(),
            log_path=log_path.relative_to(project).as_posix(),
            source_hash_before=before_hash, source_hash_after=after_hash,
            issues_before=issues, issues_after=issues_after,
        )
        attempts.append(attempt)
        write_json(attempt_root / "attempt.json", attempt)
        if not issues_after:
            report = PrototypeRepairReport(
                episode_id=episode_id, status="repaired", max_attempts=limit, attempts=attempts,
            )
            write_json(report_path, report)
            emit(99, f"Prototype repair passed every deterministic check on attempt {attempt_number}", task="prototype_repair")
            return report
        issues = issues_after

    report = PrototypeRepairReport(
        episode_id=episode_id, status="failed", max_attempts=limit,
        attempts=attempts, final_issues=issues,
    )
    write_json(report_path, report)
    raise RuntimeError(
        f"Prototype repair exhausted {limit} attempt(s); inspect {report_path.relative_to(project)}"
    )


def _validate_static_prototype(out_dir: Path, *, screen_scenes: list[Any] | None = None) -> Path:
    entrypoint = out_dir / "dist/index.html"
    if not entrypoint.is_file():
        entrypoint = out_dir / "index.html"
    if not entrypoint.is_file():
        raise RuntimeError("Prototype builder finished without a static index.html or dist/index.html entrypoint")
    html = entrypoint.read_text(encoding="utf-8", errors="replace")
    if not re.search(r'<meta\s+[^>]*name=["\']viewport["\'][^>]*>', html, re.IGNORECASE):
        raise RuntimeError("Prototype must include a mobile viewport meta tag")
    if re.search(r"(?:src|href)\s*=\s*['\"]/(?!/)", html):
        raise RuntimeError(
            "Prototype uses root-absolute assets. Use relative asset paths so it works under /prototype/<episode-id>/"
        )
    for script in entrypoint.parent.glob("*.js"):
        source = script.read_text(encoding="utf-8", errors="replace")
        if re.search(r"fetch\(\s*['\"]/(?!/)", source):
            raise RuntimeError(
                "Prototype fetches root-absolute data. Use relative paths so it works under /prototype/<episode-id>/"
            )
    source_parts: list[str] = []
    for suffix in ("*.html", "*.css", "*.js", "*.json"):
        for path in entrypoint.parent.rglob(suffix):
            if any(folder in {"node_modules", ".next"} for folder in path.parts):
                continue
            source_parts.append(path.read_text(encoding="utf-8", errors="replace"))
    source = "\n".join(source_parts)
    if "data-testid" not in source:
        raise RuntimeError("Prototype must expose durable data-testid selectors for recording and visual QA")
    if screen_scenes and "__svfSetTime" not in source:
        raise RuntimeError(
            "Prototype must implement window.__svfSetTime(localSeconds, timelineCues) for narration-timed animation"
        )
    for scene in screen_scenes or []:
        if scene.scene_id.casefold() not in source.casefold():
            raise RuntimeError(f"Prototype source has no dedicated state for approved scene {scene.scene_id}")
    return entrypoint


def _validate_prototype_visuals(project: Path, entrypoint: Path, scene_ids: list[str]) -> PrototypeVisualReport:
    """Run deterministic browser checks at the reel canvas and a real phone width."""
    if not scene_ids:
        return PrototypeVisualReport(ok=True, findings=[])
    repo_root = Path(__file__).resolve().parents[1]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = int(reservation.getsockname()[1])
    server = subprocess.Popen(
        [sys.executable, str(repo_root / "scripts/serve_demo.py"), str(entrypoint.parent), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    result: subprocess.CompletedProcess[str] | None = None
    try:
        time.sleep(0.8)
        result = subprocess.run(
            [
                str(node_binary()), str(repo_root / "scripts/validate_prototype.mjs"),
                f"http://127.0.0.1:{port}/index.html",
                str(project / "05_asset_jobs/demo_jobs.json"), *scene_ids,
            ],
            cwd=repo_root, capture_output=True, text=True, timeout=180,
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()
    log = ((result.stdout or "") + "\n" + (result.stderr or "")) if result else "Prototype visual QA did not start"
    atomic_write_text(project / "_requests/prototype_visual_qa.log", log)
    if not result:
        raise RuntimeError("Prototype visual QA did not start")
    try:
        report = PrototypeVisualReport.model_validate(json.loads(result.stdout))
    except Exception as exc:
        raise RuntimeError(f"Prototype visual QA returned an invalid report: {log[-3000:]}") from exc
    write_json(project / "_requests/prototype_visual_qa.json", report)
    if result.returncode != 0 or not report.ok:
        raise PrototypeVisualValidationError(report)
    return report


def _validate_graphics_visuals(
    project: Path,
    plan: GraphicsPlan,
    *,
    fps: int,
    width: int,
    height: int,
) -> GraphicsVisualReport:
    """Inspect stable cue frames and action liveness in a deterministic browser."""
    repo_root = Path(__file__).resolve().parents[1]
    graphics_root = project / "08_graphics"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = int(reservation.getsockname()[1])
    server = subprocess.Popen(
        [sys.executable, str(repo_root / "scripts/serve_demo.py"), str(graphics_root), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    result: subprocess.CompletedProcess[str] | None = None
    try:
        time.sleep(0.6)
        result = subprocess.run(
            [
                str(node_binary()), str(repo_root / "scripts/validate_graphics.mjs"),
                f"http://127.0.0.1:{port}/master.html",
                str(graphics_root / "graphics_plan.json"), str(fps), str(width), str(height),
            ],
            cwd=repo_root, capture_output=True, text=True, timeout=240,
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()
    log = ((result.stdout or "") + "\n" + (result.stderr or "")) if result else "Graphics visual QA did not start"
    atomic_write_text(project / "_requests/graphics_visual_qa.log", log)
    if not result:
        raise RuntimeError("Graphics visual QA did not start")
    try:
        report = GraphicsVisualReport.model_validate(json.loads(result.stdout))
    except Exception as exc:
        raise RuntimeError(f"Graphics visual QA returned an invalid report: {log[-3000:]}") from exc
    write_json(project / "_requests/graphics_visual_qa.json", report)
    if result.returncode != 0 or not report.ok:
        failures = [finding for finding in report.findings if finding.issues]
        summary = "; ".join(
            f"{finding.scene_id} {finding.moment}: {', '.join(finding.issues)}"
            for finding in failures[:8]
        )
        raise RuntimeError(f"Graphics frame QA failed: {summary}")
    return report


def generate_graphics_plan(
    store: ProjectStore,
    episode_id: str,
    *,
    agent_kind: str | None = None,
    consume_response: bool = False,
) -> GraphicsPlan:
    """Plan and compile inspectable graphics before the final composition render."""
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    narration = load_model(project / "01_narration/narration.json", Narration)
    director = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    graphics_scenes = [scene for scene in director.scenes if scene.renderer in {"hyperframes", "static"}]
    if not graphics_scenes:
        raise RuntimeError("The approved director plan has no HyperFrames/static graphics scenes")
    screen_scenes = [scene for scene in director.scenes if scene.renderer == "playwright"]
    words_path = project / "02_voice/audio_word_timestamps.json"
    words = load_model(words_path, WordTimestampBundle) if words_path.is_file() else None
    emit(
        10,
        f"Planning {len(graphics_scenes)} {brief.graphics_theme} graphics scenes",
        task="graphics_builder",
    )
    deterministic_plan_requested = agent_kind == "mock"
    if agent_kind == "mock":
        plan = _default_graphics_plan(
            episode_id, director, graphics_scenes, graphics_theme=brief.graphics_theme,
        )
    else:
        agent = _structured_agent(
            store, "graphics_builder", {"episode_id": episode_id},
            agent_kind=agent_kind, consume_response=consume_response,
        )
        base_prompt = graphics_builder_prompt(
            brief, narration,
            [scene.model_dump(mode="json") for scene in graphics_scenes],
            [scene.model_dump(mode="json") for scene in screen_scenes],
            words,
        )
        plan = _run_graphics_agent(
            agent,
            stage="graphics_builder",
            prompt=base_prompt,
            output_model=GraphicsPlan,
            request_dir=project / "_requests",
        )
        quality_repair_attempt = 0
        maximum_quality_repairs = 2
        while True:
            try:
                plan = _prepare_graphics_candidate(
                    plan, brief=brief, director=director, words=words,
                )
                break
            except RuntimeError as exc:
                if quality_repair_attempt >= maximum_quality_repairs:
                    raise RuntimeError(
                        f"Graphics quality repair failed after {maximum_quality_repairs} attempts. "
                        f"Last measured defects: {exc}"
                    ) from exc
                quality_repair_attempt += 1
                emit(
                    34 + quality_repair_attempt * 8,
                    f"Graphics contract failed quality checks; requesting bounded repair "
                    f"{quality_repair_attempt}/{maximum_quality_repairs}",
                    task="graphics_builder",
                )
                stage = (
                    "graphics_builder_quality_repair"
                    if quality_repair_attempt == 1
                    else f"graphics_builder_quality_repair_{quality_repair_attempt}"
                )
                repair_prompt = (
                    base_prompt.rstrip()
                    + f"\n\n# BOUNDED QUALITY REPAIR {quality_repair_attempt}/{maximum_quality_repairs}\n"
                    + "The previous contract passed its JSON schema but failed deterministic quality gates. "
                    + "Every measured defect below must be fixed together. Return a complete corrected "
                    + "GraphicsPlan and preserve episode and scene timings exactly. Do not change already-valid "
                    + "facts, narration anchors, or the operator-selected theme.\n"
                    + f"Measured defects:\n{exc}\n\nPrevious contract:\n"
                    + plan.model_dump_json(indent=2)
                )
                plan = _run_graphics_agent(
                    agent,
                    stage=stage,
                    prompt=repair_prompt,
                    output_model=GraphicsPlan,
                    request_dir=project / "_requests",
                )
    if deterministic_plan_requested:
        plan = _prepare_graphics_candidate(
            plan, brief=brief, director=director, words=words, require_anchors=False,
        )
    emit(55, "Graphics contracts validated; compiling scene previews", task="graphics_builder")
    write_graphics_package(project, plan, width=brief.width, height=brief.height, fps=brief.fps)
    emit(70, "Checking cue frames, safe bounds, motion, and object overlap", task="graphics_builder")
    try:
        _validate_graphics_visuals(project, plan, fps=brief.fps, width=brief.width, height=brief.height)
    except RuntimeError as exc:
        if deterministic_plan_requested:
            raise
        emit(76, "Measured graphics frames failed; requesting one visual repair", task="graphics_builder")
        visual_repair_prompt = (
            base_prompt.rstrip()
            + "\n\n# BOUNDED VISUAL REPAIR\n"
            + "The previous contract passed semantic validation but failed deterministic browser frame QA. "
            + "Return a complete corrected GraphicsPlan. Preserve episode and scene timings exactly, "
            + "fix only the measured visibility, sizing, bounds, or overlap defects, and keep every factual "
            + "claim grounded in the approved inputs.\n"
            + f"Measured issue: {exc}\n\nPrevious contract:\n"
            + plan.model_dump_json(indent=2)
        )
        plan = _run_graphics_agent(
            agent,
            stage="graphics_builder_visual_repair",
            prompt=visual_repair_prompt,
            output_model=GraphicsPlan,
            request_dir=project / "_requests",
        )
        plan = _prepare_graphics_candidate(
            plan, brief=brief, director=director, words=words,
        )
        write_graphics_package(project, plan, width=brief.width, height=brief.height, fps=brief.fps)
        _validate_graphics_visuals(project, plan, fps=brief.fps, width=brief.width, height=brief.height)
    emit(82, "Building the interactive voice-timed timeline preview", task="graphics_builder")
    build_composition(project, preview=True, width=brief.width, height=brief.height, fps=brief.fps)
    store.transition(episode_id, EpisodeStage.COMPOSITION_READY)
    emit(100, f"Generated {len(plan.scenes)} graphics scenes and the timeline preview", task="graphics_builder")
    return plan


def _run_graphics_agent(
    agent: StructuredAgent,
    *,
    stage: str,
    prompt: str,
    output_model: type[GraphicsPlan],
    request_dir: Path,
) -> GraphicsPlan:
    """Run graphics AI without silently replacing a provider failure with mock output."""
    try:
        return agent.run(
            stage=stage,
            prompt=prompt,
            output_model=output_model,
            request_dir=request_dir,
        )
    except RuntimeError as exc:
        message = str(exc)
        normalized = message.casefold()
        limit_markers = (
            "usage limit",
            "insufficient_quota",
            "quota exceeded",
            "quota has been exceeded",
            "billing hard limit",
            "credit balance",
            "resource_exhausted",
        )
        if any(marker in normalized for marker in limit_markers):
            raise RuntimeError(
                "Graphics generation stopped: the selected AI provider's usage limit is exhausted. "
                "No deterministic fallback or new preview was generated. Change the provider/model "
                "or replenish its quota, then retry."
            ) from exc
        raise


def _prepare_graphics_candidate(
    plan: GraphicsPlan,
    *,
    brief: EpisodeBrief,
    director: DirectorPlan,
    words: WordTimestampBundle | None,
    require_anchors: bool | None = None,
) -> GraphicsPlan:
    """Align and run every deterministic contract gate before browser compilation."""
    _validate_graphics_theme(plan, brief.graphics_theme)
    candidate = _align_graphics_actions_to_words(plan, director, words, fps=brief.fps)
    _validate_graphics_against_director(candidate, director)
    _validate_graphics_storytelling_quality(
        candidate,
        require_anchors=words is not None if require_anchors is None else require_anchors,
    )
    return candidate


def _default_graphics_plan(
    episode_id: str,
    director: DirectorPlan,
    scenes: list[Any],
    *,
    graphics_theme: GraphicsTheme = "editorial",
) -> GraphicsPlan:
    shells_by_type = {
        "motion_graphic": ["metaphor_stage", "spatial_stage", "flow_stage"],
        "diagram": ["system_stage", "map_stage", "data_stage"],
        "ui_mockup": ["document_stage", "collage_stage", "queue_stage"],
        "broll": ["collage_stage", "editorial_stage", "spatial_stage"],
        "cta": ["editorial_stage", "metaphor_stage", "spatial_stage"],
    }
    def object_type(label: str) -> str:
        value = label.lower()
        if re.search(r"\d", value):
            return "number"
        if any(word in value for word in ("route", "path", "handoff", "flow")):
            return "route"
        if any(word in value for word in ("origin", "destination", "location", "region", "map")):
            return "map_region"
        if any(word in value for word in ("worker", "owner", "coordinator", "customer", "person")):
            return "figure"
        if any(word in value for word in ("email", "text", "paper", "invoice", "file", "receipt")):
            return "artifact"
        if any(word in value for word in ("review", "approval", "ai", "resolve")):
            return "decision"
        if any(word in value for word in ("record", "queue", "status")):
            return "database"
        return "process"

    def concise(value: str, limit: int = 105) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit].rsplit(" ", 1)[0] + "…"

    def display_phrase(value: str, words: int = 7) -> str:
        cleaned = re.sub(
            r"\b(simple|generic|animation|screen|panel|card|shows?|pulses?|appears?|visual|"
            r"center|phrase|vertical|kinetic|graphic|composition|animate[sd]?|highlight[sed]*|opaque|transparent)\b",
            " ", value, flags=re.IGNORECASE,
        )
        tokens = cleaned.replace("…", "").split()
        return " ".join(tokens[:words]).strip(" .,:;-—") or "THE WORKFLOW CHANGES"

    def visual_labels(scene: Any) -> list[str]:
        supplied = [value.strip() for value in scene.on_screen_text if value.strip()]
        candidates = [display_phrase(value, 4) for value in supplied[1:6]]
        candidates.extend(display_phrase(value, 4) for value in scene.emphasis[:5])
        if len(candidates) < 2:
            raw = re.sub(
                r"\b(branches? toward|converges? into|turns? into|becomes?)\b",
                ",", scene.visual_brief, flags=re.IGNORECASE,
            )
            candidates.extend(
                display_phrase(value, 4) for value in re.split(r"[,+;]|→", raw) if value.strip()
            )
        labels: list[str] = []
        seen: set[str] = set()
        for value in candidates:
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                labels.append(value)
            if len(labels) == 5:
                break
        return labels or [display_phrase(scene.purpose, 4)]

    contracts: list[GraphicsScenePlan] = []
    continuity: str | None = None
    frame_layouts = [
        [(4, 7, 38, 28), (51, 18, 43, 24), (13, 54, 35, 28), (58, 58, 34, 24), (35, 38, 31, 22)],
        [(8, 16, 46, 26), (57, 6, 35, 33), (48, 48, 44, 27), (4, 61, 36, 23), (27, 37, 34, 22)],
        [(6, 5, 34, 31), (49, 9, 44, 22), (11, 47, 45, 30), (62, 55, 30, 25), (35, 31, 30, 23)],
    ]
    for scene_index, scene in enumerate(scenes):
        supplied = [value.strip() for value in scene.on_screen_text if value.strip()][:5]
        headline = display_phrase(supplied[0] if supplied else scene.narration_excerpt, 7)
        object_labels = [value for value in visual_labels(scene) if value.casefold() != headline.casefold()]
        if not object_labels:
            object_labels = [display_phrase(scene.purpose, 4)]
        positions = frame_layouts[scene_index % len(frame_layouts)]
        objects = [
            GraphicsObject(
                object_id=f"{scene.scene_id.lower()}-object-{index}",
                object_type=object_type(label),
                role="visual evidence" if index == len(object_labels) else "workflow step",
                label=label,
                detail=display_phrase(scene.emphasis[index - 1], 6) if index <= len(scene.emphasis) else "",
                slot=["left", "center", "right", "bottom", "top"][(index - 1) % 5],
                frame=GraphicsFrame(
                    x=positions[index - 1][0], y=positions[index - 1][1],
                    width=positions[index - 1][2], height=positions[index - 1][3],
                    rotation=(-4, 3, -2, 5, 0)[(index - 1) % 5],
                    depth=("foreground" if index in {1, len(object_labels)} else "midground"),
                ),
                visual_form=f"topic-specific {object_type(label).replace('_', ' ')} depiction",
                initially_visible=index == 1,
            )
            for index, label in enumerate(object_labels, 1)
        ]
        duration = scene.end - scene.start
        actions = [
            GraphicsAction(
                at_seconds=min(duration * 0.5, 0.18 + (index - 1) * max(0.3, duration * 0.08)),
                action="reveal", target=item.object_id, duration_seconds=0.5,
                direction=("right" if index % 2 else "left"),
            )
            for index, item in enumerate(objects, 1)
            if not item.initially_visible
        ]
        if len(objects) > 1:
            actions.append(GraphicsAction(
                at_seconds=min(duration * 0.76, max(action.at_seconds for action in actions) + 0.35),
                action="trace", target=objects[-1].object_id, source=objects[0].object_id,
                duration_seconds=min(1.2, max(0.4, duration * 0.12)),
            ))
        actions.append(GraphicsAction(
            at_seconds=min(duration * 0.58, max(0.4, duration * 0.44)),
            action="transform", target=objects[-1].object_id,
            value=concise(scene.visual_brief, 70), duration_seconds=min(1.1, max(0.45, duration * 0.12)),
            direction="in",
        ))
        actions.append(GraphicsAction(
            at_seconds=max(0.0, duration - 0.8),
            action="focus", target=objects[-1].object_id, duration_seconds=0.55,
        ))
        shell_options = shells_by_type.get(scene.type, ["editorial_stage", "spatial_stage", "metaphor_stage"])
        shell = shell_options[scene_index % len(shell_options)]
        contracts.append(GraphicsScenePlan(
            scene_id=scene.scene_id, start=scene.start, end=scene.end,
            scene_shell=shell,
            motion_grammar=("object_transformation" if len(objects) == 1 else "cause_and_effect"),
            layout_variant=f"asymmetric-{scene.type.replace('_', '-')}-world",
            visual_thesis=scene.visual_brief,
            headline=concise(headline, 54), support="",
            visual_world=concise(scene.visual_brief, 120),
            opening_state=f"Unresolved {concise(scene.purpose, 82)}",
            payoff_state=f"The final object visibly resolves {concise(scene.purpose, 78)}",
            camera_move=("push_in" if scene_index % 3 == 0 else "pan_right" if scene_index % 3 == 1 else "pull_out"),
            continuity_object=continuity,
            objects=objects, actions=sorted(actions, key=lambda item: item.at_seconds),
            review_checkpoints=sorted(set([
                round(min(duration - 0.1, max(0.05, duration * 0.12)), 3),
                round(min(duration - 0.1, max(0.05, duration * 0.58)), 3),
                round(max(0.05, duration - 0.72), 3),
            ])),
        ))
        continuity = objects[-1].label
    return GraphicsPlan(
        episode_id=episode_id, duration_seconds=director.duration_seconds,
        theme=graphics_theme, creative_thesis=director.visual_thesis, scenes=contracts,
        warnings=["Deterministic graphics plan used; regenerate with a configured structured model for richer choreography"],
    )


def _validate_graphics_theme(plan: GraphicsPlan, expected_theme: GraphicsTheme) -> None:
    if "theme" not in plan.model_fields_set:
        raise RuntimeError("Graphics plan omits the operator-selected top-level theme")
    if plan.theme != expected_theme:
        raise RuntimeError(
            f"Graphics plan theme {plan.theme!r} does not match the operator-selected "
            f"theme {expected_theme!r}"
        )


def _align_graphics_actions_to_words(
    plan: GraphicsPlan,
    director: DirectorPlan,
    words: WordTimestampBundle | None,
    *,
    fps: int = 30,
) -> GraphicsPlan:
    if words is None:
        return plan
    source_by_id = {scene.scene_id: scene for scene in director.scenes}
    aligned_scenes: list[GraphicsScenePlan] = []
    for scene in plan.scenes:
        source = source_by_id[scene.scene_id]
        actions: list[GraphicsAction] = []
        for action in scene.actions:
            if not action.anchor_text:
                actions.append(action)
                continue
            aligned = _cue_anchor_start(
                action.anchor_text, source, words, occurrence=action.anchor_occurrence,
            )
            if aligned is None:
                raise RuntimeError(
                    f"Graphics action {scene.scene_id}/{action.action} uses narration anchor "
                    f"{action.anchor_text!r} occurrence {action.anchor_occurrence}, which was not found inside the scene"
                )
            # A rendered event must never precede the spoken anchor. Quantize to
            # the first whole output frame at or after Whisper's exact word start.
            frame = math.ceil(max(0.0, aligned) * fps - 1e-9)
            frame_aligned = min(scene.end - scene.start, frame / fps)
            actions.append(action.model_copy(update={"at_seconds": round(frame_aligned, 6)}))
        aligned_scenes.append(scene.model_copy(update={"actions": sorted(actions, key=lambda item: item.at_seconds)}))
    return plan.model_copy(update={"scenes": aligned_scenes})


def _validate_graphics_storytelling_quality(plan: GraphicsPlan, *, require_anchors: bool) -> None:
    """Reject slide-deck-like plans and report all repairable defects together."""
    issues: list[str] = []
    forbidden_layout_words = {"grid", "dashboard", "cards", "columns", "quadrant", "tiles"}
    shells = [scene.scene_shell for scene in plan.scenes]
    if len(plan.scenes) >= 4 and len(set(shells)) < 3:
        issues.append("Graphics plan needs at least three distinct visual worlds/shells")
    for previous, current in zip(plan.scenes, plan.scenes[1:]):
        if previous.scene_shell == current.scene_shell:
            issues.append(
                f"Adjacent graphics scenes repeat {current.scene_shell}: "
                f"{previous.scene_id}, {current.scene_id}"
            )
    for scene in plan.scenes:
        duration = scene.end - scene.start
        if not scene.visual_world.strip() or not scene.opening_state.strip() or not scene.payoff_state.strip():
            issues.append(f"Graphics scene {scene.scene_id} lacks an evolving visual-world contract")
        if scene.opening_state.casefold() == scene.payoff_state.casefold():
            issues.append(f"Graphics scene {scene.scene_id} opening and payoff states are identical")
        layout_words = set(_cue_tokens(scene.layout_variant))
        if layout_words & forbidden_layout_words:
            issues.append(f"Graphics scene {scene.scene_id} uses generic layout {scene.layout_variant!r}")
        undeclared_visibility = [
            item.object_id for item in scene.objects
            if "initially_visible" not in item.model_fields_set
        ]
        if undeclared_visibility:
            issues.append(
                f"Graphics scene {scene.scene_id} omits initially_visible for: "
                f"{', '.join(undeclared_visibility)}"
            )
        opening_objects = [item for item in scene.objects if item.initially_visible]
        if not 1 <= len(opening_objects) <= 3:
            issues.append(
                f"Graphics scene {scene.scene_id} must declare one to three opening-frame objects"
            )
        duplicate_headline = [
            item.object_id for item in scene.objects
            if item.label.strip().casefold() == scene.headline.strip().casefold()
        ]
        if duplicate_headline:
            issues.append(
                f"Graphics scene {scene.scene_id} repeats its headline as objects: "
                f"{', '.join(duplicate_headline)}"
            )
        for item in scene.objects:
            reveals = [
                action for action in scene.actions
                if action.target == item.object_id and action.action == "reveal"
            ]
            participation = sorted(
                [
                    action for action in scene.actions
                    if action.action != "hold"
                    and (action.target == item.object_id or action.source == item.object_id)
                ],
                key=lambda action: action.at_seconds,
            )
            if item.initially_visible and reveals:
                issues.append(
                    f"Graphics scene {scene.scene_id}/{item.object_id} is initially visible and must not reveal again"
                )
            if not item.initially_visible:
                if len(reveals) != 1:
                    issues.append(
                        f"Graphics scene {scene.scene_id}/{item.object_id} needs exactly one reveal"
                    )
                elif reveals:
                    earliest_participation = participation[0].at_seconds if participation else math.inf
                    if reveals[0].at_seconds > earliest_participation + 1e-6:
                        issues.append(
                            f"Graphics scene {scene.scene_id}/{item.object_id} is used before its reveal"
                        )
        unframed = [item.object_id for item in scene.objects if item.frame is None]
        if unframed:
            issues.append(
                f"Graphics scene {scene.scene_id} needs explicit frames for: {', '.join(unframed)}"
            )
        readable_frames = [
            item.frame for item in scene.objects
            if item.frame is not None and item.frame.depth != "background"
        ]
        undersized = [
            item.object_id for item in scene.objects
            if item.frame is not None
            and item.frame.depth != "background"
            and item.object_type not in {"route", "boundary", "axis"}
            and (item.frame.width < 18 or item.frame.height < 10)
        ]
        if undersized:
            issues.append(
                f"Graphics scene {scene.scene_id} has undersized readable objects: {', '.join(undersized)}"
            )
        if readable_frames:
            span_width = max(frame.x + frame.width for frame in readable_frames) - min(frame.x for frame in readable_frames)
            span_height = max(frame.y + frame.height for frame in readable_frames) - min(frame.y for frame in readable_frames)
            if span_width < 65 or span_height < 55:
                issues.append(
                    f"Graphics scene {scene.scene_id} under-fills the portrait stage "
                    f"({span_width:.1f}% wide × {span_height:.1f}% high)"
                )
        meaningful = [
            action for action in scene.actions
            if action.action not in {"reveal", "hold", "highlight", "stamp", "focus"}
        ]
        if not meaningful:
            issues.append(f"Graphics scene {scene.scene_id} only reveals labels; it does not prove a change")
        checkpoints = sorted(scene.review_checkpoints)
        if len(checkpoints) < 2:
            issues.append(f"Graphics scene {scene.scene_id} needs proof and payoff review checkpoints")
        action_times = sorted({0.0, *[item.at_seconds for item in scene.actions], max(0.0, duration - 0.7)})
        if any(right - left > 4.25 for left, right in zip(action_times, action_times[1:])):
            issues.append(f"Graphics scene {scene.scene_id} stays visually unchanged for more than 4.25 seconds")
        if max(item.at_seconds for item in scene.actions) < duration * 0.62:
            issues.append(f"Graphics scene {scene.scene_id} has no observable final-third payoff")
        if require_anchors:
            unanchored = [
                item.action for item in scene.actions
                if item.action != "hold" and not (item.anchor_text or "").strip()
            ]
            if unanchored:
                issues.append(
                    f"Graphics scene {scene.scene_id} has non-word-timed actions: {', '.join(unanchored)}"
                )
    if issues:
        maximum_reported = 40
        reported = issues[:maximum_reported]
        overflow = len(issues) - len(reported)
        suffix = f"\n- … and {overflow} more defects" if overflow else ""
        raise RuntimeError("Graphics quality gate failed:\n- " + "\n- ".join(reported) + suffix)


def _validate_graphics_against_director(plan: GraphicsPlan, director: DirectorPlan) -> None:
    expected = {scene.scene_id: scene for scene in director.scenes if scene.renderer in {"hyperframes", "static"}}
    actual = {scene.scene_id: scene for scene in plan.scenes}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing or extra:
        raise RuntimeError(f"Graphics plan scene mismatch; missing={missing}, extra={extra}")
    if plan.episode_id != director.episode_id:
        raise RuntimeError("Graphics plan belongs to a different episode")
    if abs(plan.duration_seconds - director.duration_seconds) > 0.05:
        raise RuntimeError("Graphics plan duration differs from the approved director timeline")
    for scene_id, contract in actual.items():
        source = expected[scene_id]
        if abs(contract.start - source.start) > 0.02 or abs(contract.end - source.end) > 0.02:
            raise RuntimeError(f"Graphics timings for {scene_id} changed the approved director timeline")


def _require_graphics_package(project: Path) -> None:
    director = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    if not any(scene.renderer in {"hyperframes", "static"} for scene in director.scenes):
        return
    path = project / "08_graphics/graphics_plan.json"
    if not path.is_file():
        raise RuntimeError("Graphics have not been generated. Run the Generate graphics step before rendering.")
    plan = load_model(path, GraphicsPlan)
    _validate_graphics_against_director(plan, director)


def shlex_quote(value: str) -> str:
    import shlex
    return shlex.quote(value)


def prepare_timeline_preview(store: ProjectStore, episode_id: str) -> dict[str, Any]:
    """Build the complete browser-playable timeline without rendering video frames."""
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    _require_presenter_policy(store, episode_id)
    _require_graphics_package(project)
    emit(10, "Collecting voice, screen recordings, presenter media and graphics", task="composition_preview")
    path = build_composition(project, preview=True, width=brief.width, height=brief.height, fps=brief.fps)
    emit(100, "Interactive timeline preview is ready; no video frames were rendered", task="composition_preview")
    return {
        "episode_id": episode_id,
        "path": path.relative_to(project).as_posix(),
        "duration_seconds": load_model(
            project / "03_director/director_plan.approved.json", DirectorPlan,
        ).duration_seconds,
        "rendered_video": False,
    }


def render_preview(store: ProjectStore, episode_id: str) -> dict[str, Any]:
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    _require_presenter_policy(store, episode_id)
    _require_graphics_package(project)
    output = project / "10_final/preview.mp4"
    report = render_hyperframes(project, preview=True, width=brief.width, height=brief.height, output=output)
    store.transition(episode_id, EpisodeStage.FINAL_REVIEW)
    return report


def render_final(store: ProjectStore, episode_id: str) -> dict[str, Any]:
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    _require_presenter_policy(store, episode_id)
    _require_graphics_package(project)
    output = project / "10_final/final.mp4"
    return render_hyperframes(project, preview=False, width=brief.width, height=brief.height, output=output)


def generate_voice(store: ProjectStore, episode_id: str) -> VoiceMetadata:
    """Run a configured audio provider. Default route is manual, by design."""
    project = store.project_dir(episode_id)
    narration = load_model(project / "01_narration/narration.json", Narration)
    config = load_config(store, episode_id)
    route = resolve_task(config, "voice_generator")
    if route["provider_mode"] == "manual":
        raise RuntimeError("voice_generator is manual by default. Use svf import-voice, or route voice_generator to custom_cli with a media_command_template.")
    output = project / "02_voice/voice_master.wav"
    _clear_voice_timing(project)
    if route["provider"] in {"elevenlabs", "gemini"}:
        voice_id = route.get("voice_id") or (
            os.getenv("ELEVENLABS_VOICE_ID", "") if route["provider"] == "elevenlabs"
            else os.getenv("GEMINI_TTS_VOICE", "Kore")
        )
        if not voice_id:
            raise RuntimeError(f"Select a {route['provider']} voice in Model orchestration before generating audio")
        emit(4, f"Preparing paragraph-sized TTS batches with {voice_id}", task="voice_generator")

        def chunk_progress(completed: int, total: int, status: str) -> None:
            percent = 5 + (completed / total) * 85
            emit(percent, f"Voice chunk {completed}/{total} {status}", task="voice_generator")

        manifest = generate_batched_voice(
            project=project, episode_id=episode_id, narration=narration,
            provider=route["provider"], model=route["model"], voice_id=voice_id,
            output=output, timeout=max(10, int(route.get("timeout_seconds", 900))),
            progress=chunk_progress,
        )
        manifest_path = project / "02_voice/audio_chunks/manifest.json"
        meta = VoiceMetadata(
            episode_id=episode_id, audio_path=str(output.relative_to(project)),
            duration_seconds=_duration(output), source="generated",
            provider=route["provider"], model=route["model"], voice_id=voice_id,
            chunk_manifest_path=str(manifest_path.relative_to(project)), chunk_count=len(manifest.chunks),
        )
        write_json(project / "02_voice/voice.json", meta)
        store.transition(episode_id, EpisodeStage.VOICE_READY)
        emit(100, f"Assembled {len(manifest.chunks)} quality-checked voice chunks with {route['provider']}", task="voice_generator")
        return meta
    template = route.get("media_command_template", "").strip()
    if not template:
        raise RuntimeError(f"No media_command_template configured for {route['provider']}")
    prompt_path = project / "_requests/voice_text.txt"
    atomic_write_text(prompt_path, narration.text + "\n")
    cmd = template.format(
        prompt=shlex_quote(str(prompt_path)), output=shlex_quote(str(output)),
        model=shlex_quote(route.get("model", "")), reference=shlex_quote(""),
    )
    r = subprocess.run(cmd, shell=True, cwd=project, capture_output=True, text=True, timeout=max(1, int(route.get("timeout_seconds", 900))))
    (project / "_requests/voice_generator.log").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0 or not output.exists():
        raise RuntimeError(f"Voice generator failed: {(r.stderr or r.stdout)[-4000:]}")
    meta = VoiceMetadata(episode_id=episode_id, audio_path=str(output.relative_to(project)), duration_seconds=_duration(output), source="generated")
    write_json(project / "02_voice/voice.json", meta)
    store.transition(episode_id, EpisodeStage.VOICE_READY)
    return meta


def generate_talking_head(store: ProjectStore, episode_id: str, scene_id: str, *, reference: Path | None = None) -> Path:
    """Run a configured talking-head media adapter such as InfiniteTalk for one scene."""
    if not store.settings().include_talking_head:
        raise RuntimeError("Talking head is disabled for this project")
    project = store.project_dir(episode_id)
    plan_path = project / "03_director/director_plan.approved.json"
    plan = load_model(plan_path, DirectorPlan)
    scene = next((s for s in plan.scenes if s.scene_id == scene_id), None)
    if not scene or scene.type not in {"talking_head", "cta"}:
        raise ValueError(f"{scene_id} is not a presenter scene")
    config = load_config(store, episode_id)
    route = resolve_task(config, "talking_head_generator")
    if route["provider_mode"] == "manual":
        raise RuntimeError("talking_head_generator is manual by default. Use svf import-head, or route it to infinite_talk/custom_cli.")
    template = route.get("media_command_template", "").strip()
    if not template:
        raise RuntimeError(f"No media_command_template configured for {route['provider']}")
    prompt_path = project / f"_requests/{scene_id}-talking-head.txt"
    prompt_text = (
        f"Create a natural vertical presenter clip for scene {scene_id}.\n"
        f"Spoken line/context: {scene.narration_excerpt}\n"
        "Preserve speaker identity, natural blink/head motion and realistic lip sync. No camera movement unless requested."
    )
    atomic_write_text(prompt_path, prompt_text)
    output = project / "07_talking_head" / f"{scene_id}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = template.format(
        prompt=shlex_quote(str(prompt_path)), output=shlex_quote(str(output)),
        model=shlex_quote(route.get("model", "")), reference=shlex_quote(str(reference or "")),
    )
    r = subprocess.run(cmd, shell=True, cwd=project, capture_output=True, text=True, timeout=max(1, int(route.get("timeout_seconds", 1800))))
    (project / "_requests" / f"{scene_id}-talking-head.log").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0 or not output.exists():
        raise RuntimeError(f"Talking-head generator failed: {(r.stderr or r.stdout)[-4000:]}")
    scenes = [s.model_copy(update={"generated_asset": str(output.relative_to(project))}) if s.scene_id == scene_id else s for s in plan.scenes]
    write_json(plan_path, plan.model_copy(update={"scenes": scenes}))
    return output


def _require_presenter_policy(store: ProjectStore, episode_id: str) -> None:
    project = store.project_dir(episode_id)
    plan_path = project / "03_director/director_plan.approved.json"
    if not plan_path.exists():
        return
    plan = load_model(plan_path, DirectorPlan)
    issues = validate_presenter_policy(
        plan, include_talking_head=store.settings().include_talking_head,
    )
    if issues:
        raise RuntimeError("; ".join(issues) + ". Regenerate and approve the Director plan.")
