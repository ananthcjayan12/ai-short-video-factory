from __future__ import annotations

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
from .integrations import NATIVE_STRUCTURED_PROVIDERS, generate_tts
from .models import (
    AudioTiming, DemoAction, DemoJob, DemoJobBundle, DirectorPlan, EpisodeBrief, EpisodeStage, Narration, StoryPlan,
    GraphicsAction, GraphicsObject, GraphicsPlan, GraphicsScenePlan, VoiceMetadata, WordTimestampBundle,
)
from .node_runtime import node_binary
from .orchestrator import PROVIDERS, default_config, resolve_task
from .project import ProjectStore
from .progress import emit
from .prompts import (
    claim_handles, director_prompt, graphics_builder_prompt, narration_prompt, narration_rewrite_prompt,
    prototype_builder_prompt, story_structure_prompt,
)
from .rendering.graphics import write_graphics_package
from .rendering.composition import build as build_composition
from .rendering.hyperframes import render as render_hyperframes
from .timing import align_words_to_narration, audio_sha256, transcribe_with_whisper
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


def _cue_anchor_start(anchor_text: str, scene: Any, words: WordTimestampBundle) -> float | None:
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
    for index in range(0, len(tokens) - len(anchor) + 1):
        if tokens[index:index + len(anchor)] == anchor:
            return max(0.0, starts[index] - scene.start)
    return None


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
        text=True, bufsize=1,
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
    plan = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    screen_scenes = [scene for scene in plan.scenes if scene.type == "screen_recording" and scene.renderer == "playwright"]
    entrypoint = _validate_static_prototype(out_dir, screen_scenes=screen_scenes)
    _stage_builder_demo_jobs(project, out_dir)
    ensure_demo_jobs(store, episode_id)
    emit(90, "Checking every prototype proof scene at reel and phone sizes", task="prototype_builder")
    _validate_prototype_visuals(project, entrypoint, [scene.scene_id for scene in screen_scenes])
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


def _validate_prototype_visuals(project: Path, entrypoint: Path, scene_ids: list[str]) -> None:
    """Run deterministic browser checks at the reel canvas and a real phone width."""
    if not scene_ids:
        return
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
    if not result or result.returncode != 0:
        raise RuntimeError(
            "Prototype is not camera-ready at the 1080x1920 reel canvas and 390x844 phone viewport. "
            f"Fix the visual QA findings and rebuild: {log[-5000:]}"
        )


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
    emit(10, f"Planning {len(graphics_scenes)} graphics scenes", task="graphics_builder")
    if agent_kind == "mock":
        plan = _default_graphics_plan(episode_id, director, graphics_scenes)
    else:
        agent = _structured_agent(
            store, "graphics_builder", {"episode_id": episode_id},
            agent_kind=agent_kind, consume_response=consume_response,
        )
        plan = agent.run(
            stage="graphics_builder",
            prompt=graphics_builder_prompt(
                brief, narration,
                [scene.model_dump(mode="json") for scene in graphics_scenes],
                [scene.model_dump(mode="json") for scene in screen_scenes],
            ),
            output_model=GraphicsPlan,
            request_dir=project / "_requests",
        )
    _validate_graphics_against_director(plan, director)
    emit(55, "Graphics contracts validated; compiling scene previews", task="graphics_builder")
    write_graphics_package(project, plan, width=brief.width, height=brief.height)
    emit(82, "Building the interactive voice-timed timeline preview", task="graphics_builder")
    build_composition(project, preview=True, width=brief.width, height=brief.height, fps=brief.fps)
    store.transition(episode_id, EpisodeStage.COMPOSITION_READY)
    emit(100, f"Generated {len(plan.scenes)} graphics scenes and the timeline preview", task="graphics_builder")
    return plan


def _default_graphics_plan(
    episode_id: str,
    director: DirectorPlan,
    scenes: list[Any],
) -> GraphicsPlan:
    shell_by_type = {
        "motion_graphic": "flow_stage", "diagram": "system_stage", "ui_mockup": "queue_stage",
        "broll": "editorial_stage", "cta": "editorial_stage",
    }
    def object_type(label: str) -> str:
        value = label.lower()
        if any(word in value for word in ("email", "text", "paper", "invoice", "file")):
            return "document"
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

    contracts: list[GraphicsScenePlan] = []
    continuity: str | None = None
    for scene in scenes:
        labels = [value.strip() for value in scene.on_screen_text if value.strip()][:5]
        if not labels:
            labels = [scene.purpose[:72]]
        headline = labels[0]
        object_labels = labels[1:] if len(labels) > 1 else [scene.purpose]
        objects = [
            GraphicsObject(
                object_id=f"{scene.scene_id.lower()}-object-{index}",
                object_type=object_type(label),
                role="visual evidence" if index == len(object_labels) else "workflow step",
                label=label,
                detail=concise(
                    scene.emphasis[index - 1] if index <= len(scene.emphasis) else scene.purpose,
                ),
                slot=["left", "center", "right", "bottom", "top"][(index - 1) % 5],
            )
            for index, label in enumerate(object_labels, 1)
        ]
        duration = scene.end - scene.start
        actions = [
            GraphicsAction(
                at_seconds=min(duration * 0.72, 0.35 + (index - 1) * max(0.35, duration * 0.11)),
                action="reveal", target=item.object_id,
            )
            for index, item in enumerate(objects, 1)
        ]
        if len(objects) > 1:
            actions.append(GraphicsAction(
                at_seconds=min(duration * 0.76, max(action.at_seconds for action in actions) + 0.35),
                action="connect", target=objects[-1].object_id, source=objects[0].object_id,
            ))
        actions.append(GraphicsAction(
            at_seconds=min(duration * 0.86, max(0.0, duration - 0.7)),
            action="highlight", target=objects[-1].object_id,
        ))
        contracts.append(GraphicsScenePlan(
            scene_id=scene.scene_id, start=scene.start, end=scene.end,
            scene_shell=shell_by_type.get(scene.type, "editorial_stage"),
            motion_grammar="cause_and_effect" if len(objects) > 1 else "editorial_reveal",
            layout_variant=f"{len(objects)}-object-{scene.type.replace('_', '-')}",
            visual_thesis=scene.visual_brief,
            headline=headline, support=scene.purpose,
            continuity_object=continuity,
            objects=objects, actions=actions,
        ))
        continuity = objects[-1].label
    return GraphicsPlan(
        episode_id=episode_id, duration_seconds=director.duration_seconds,
        creative_thesis=director.visual_thesis, scenes=contracts,
        warnings=["Deterministic graphics plan used; regenerate with a configured structured model for richer choreography"],
    )


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
        result = generate_tts(
            provider=route["provider"], model=route["model"], text=narration.text, output=output,
            timeout=max(10, int(route.get("timeout_seconds", 900))), voice_id=route.get("voice_id"),
        )
        alignment = Path(result.alignment_path) if result.alignment_path else None
        meta = VoiceMetadata(
            episode_id=episode_id, audio_path=str(output.relative_to(project)),
            duration_seconds=_duration(output), source="generated",
            transcript_path=str(alignment.relative_to(project)) if alignment else None,
        )
        write_json(project / "02_voice/voice.json", meta)
        store.transition(episode_id, EpisodeStage.VOICE_READY)
        emit(100, f"Voice generated with {result.provider}", task="voice_generator")
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
