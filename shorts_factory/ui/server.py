from __future__ import annotations

import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from ..io import load_model, read_json, write_json
from ..integrations import list_tts_voices
from ..filled_episodes import filled_episode_catalog, find_filled_episode, materialize_filled_episode
from ..models import (
    DirectorPlan, EpisodeBrief, EpisodeStage, EpisodeState, FilledEpisode, GraphicsTheme, Narration, NarrationQualityReport,
    ProductionJob, ProgressEvent, ProjectSettings, PromptInvocation, TaskModelSelection, TTSVoiceCatalog, VoiceMetadata,
)
from ..orchestrator import PROVIDERS, TASKS, default_config, provider_health, provider_models, resolve_task
from ..pipeline import (
    align_voice,
    approve_director,
    bootstrap_reference_demo,
    generate_director_plan,
    generate_graphics_plan,
    generate_narration,
    generate_voice,
    load_config,
    mock_voice,
    prepare_timeline_preview,
    record_demos,
    render_final,
    render_preview,
    repair_prototype,
    run_prototype_builder,
    _prototype_activity,
    write_prototype_builder_prompt,
)
from ..project import ProjectStore
from ..qa import episode_qa


REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTS_ROOT = REPO_ROOT / "projects"
STATIC_ROOT = Path(__file__).resolve().parent / "static"

Capability = Literal["structured", "code", "audio", "browser", "talking_head", "render"]


def _failure_summary(lines: list[str], returncode: int) -> str:
    """Prefer the actionable exception over runtime/version footer lines."""

    for line in reversed(lines):
        value = line.strip()
        if value.startswith(("RuntimeError:", "Error:", "ValueError:", "ClientError:")):
            return value[-240:]
    for line in reversed(lines):
        value = line.strip()
        if value and not re.match(r"^(Node\.js|Python) v?\d", value):
            return value[-240:]
    return f"Command exited with status {returncode}"


class EpisodeCreateRequest(BaseModel):
    episode_id: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=3, max_length=160)
    pain_point: str = Field(min_length=8)
    industry: str = Field(default="Small Business", min_length=2, max_length=100)
    role: str = Field(default="Owner", min_length=2, max_length=100)
    target_seconds: float = Field(default=58.0, ge=15, le=480)
    case_nature: Literal["real", "hypothetical", "synthetic_demo"] = "synthetic_demo"
    backend_summary: list[str] = Field(default_factory=list, max_length=12)
    viewer_diy: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("episode_id")
    @classmethod
    def validate_episode_id(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for ch in cleaned):
            raise ValueError("Use lowercase letters, numbers, hyphens or underscores")
        return cleaned


class EpisodeSummary(BaseModel):
    episode_id: str
    title: str
    industry: str
    stage: str
    progress: int = Field(ge=0, le=100)
    approved_director: bool
    approved_final: bool
    updated_at: str
    is_filled_episode: bool = False


class FilledEpisodeSummary(BaseModel):
    source_id: str
    episode_id: str
    title: str
    industry: str
    imported: bool
    stage: str | None = None
    progress: int = Field(default=0, ge=0, le=100)


class FilledEpisodeImportResult(BaseModel):
    created: list[str] = Field(default_factory=list)
    existing: list[str] = Field(default_factory=list)


class Artifact(BaseModel):
    label: str
    path: str
    kind: Literal["audio", "video", "document", "prototype", "graphics", "composition"]
    url: str


class EpisodeDetail(BaseModel):
    brief: EpisodeBrief
    state: EpisodeState
    summary: EpisodeSummary
    narration: Narration | None = None
    narration_quality: NarrationQualityReport | None = None
    voice: VoiceMetadata | None = None
    director: DirectorPlan | None = None
    qa: dict[str, Any] | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)


class ProviderStatus(BaseModel):
    provider_id: str
    label: str
    status: str
    detail: str
    healthy: bool
    capabilities: list[str]


class ActionSpec(BaseModel):
    action: str
    label: str
    capability: Capability
    stage: str
    task: str
    destructive: bool = False


class DashboardResponse(BaseModel):
    episodes: list[EpisodeSummary]
    filled_episodes: list[FilledEpisodeSummary]
    providers: list[ProviderStatus]
    actions: list[ActionSpec]
    tasks: list[dict[str, Any]]
    settings: ProjectSettings


class ProjectSettingsRequest(BaseModel):
    include_talking_head: bool


class EpisodeDurationRequest(BaseModel):
    target_seconds: float = Field(ge=15, le=480)


class EpisodeGraphicsThemeRequest(BaseModel):
    graphics_theme: GraphicsTheme


class ActionRequest(BaseModel):
    seconds: float = Field(default=58.0, ge=5, le=480)


class UploadResult(BaseModel):
    episode_id: str
    capability: Capability
    path: str
    message: str


class ModelMapRequest(BaseModel):
    tasks: dict[str, TaskModelSelection]


class ResetRequest(BaseModel):
    from_stage: Literal["narration", "voice", "direction", "assets", "render"]
    confirm: bool = False


# Each generating action is the source of truth for its stage.  Before it runs,
# artifacts produced by later stages must be removed from the active episode so
# they cannot be mistaken for output based on the new input.
INVALIDATION_STAGES: dict[str, list[str]] = {
    "narration": ["01_narration", "02_voice", "03_director", "04_prototype", "05_asset_jobs", "06_recordings", "07_talking_head", "08_graphics", "09_composition", "10_final"],
    "voice": ["02_voice", "03_director", "04_prototype", "05_asset_jobs", "06_recordings", "07_talking_head", "08_graphics", "09_composition", "10_final"],
    "timing": ["03_director", "04_prototype", "05_asset_jobs", "06_recordings", "07_talking_head", "08_graphics", "09_composition", "10_final"],
    "direction": ["03_director", "04_prototype", "05_asset_jobs", "06_recordings", "07_talking_head", "08_graphics", "09_composition", "10_final"],
    "assets": ["04_prototype", "05_asset_jobs", "06_recordings", "07_talking_head", "08_graphics", "09_composition", "10_final"],
    "prototype": ["04_prototype", "05_asset_jobs", "06_recordings", "09_composition", "10_final"],
    "recordings": ["06_recordings", "09_composition", "10_final"],
    "graphics": ["08_graphics", "09_composition", "10_final"],
    "composition": ["09_composition", "10_final"],
}

INVALIDATION_STATE: dict[str, EpisodeStage] = {
    "narration": EpisodeStage.INPUT,
    "voice": EpisodeStage.NARRATION_READY,
    "timing": EpisodeStage.VOICE_READY,
    "direction": EpisodeStage.VOICE_READY,
    "assets": EpisodeStage.DIRECTOR_APPROVED,
    "prototype": EpisodeStage.DIRECTOR_APPROVED,
    "recordings": EpisodeStage.ASSETS_READY,
    "graphics": EpisodeStage.ASSETS_READY,
    "composition": EpisodeStage.ASSETS_READY,
}


def _invalidate_from_stage(episode_id: str, from_stage: str) -> list[str]:
    """Archive active downstream artifacts and restore the appropriate state."""
    store = _store()
    project = store.project_dir(episode_id)
    folders = INVALIDATION_STAGES[from_stage]
    # Include microseconds to keep consecutive regenerations independently
    # recoverable in the archive.
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    archive = project / "_control/archive" / stamp
    moved: list[str] = []
    for folder_name in folders:
        source = project / folder_name
        if source.exists() and any(source.iterdir()):
            destination = archive / folder_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append(folder_name)
        source.mkdir(parents=True, exist_ok=True)
    state = store.state(episode_id)
    state.stage = INVALIDATION_STATE[from_stage]
    if from_stage in {"narration", "voice", "timing", "direction"}:
        state.approved_director = False
    state.approved_final = False
    write_json(project / "episode-state.json", state)
    return moved


ACTION_SPECS: dict[str, ActionSpec] = {
    "narrate": ActionSpec(action="narrate", label="Generate narration", capability="structured", stage="story", task="narration_writer"),
    "narrate-mock": ActionSpec(action="narrate-mock", label="Draft narration offline", capability="structured", stage="story", task="narration_writer"),
    "mock-voice": ActionSpec(action="mock-voice", label="Create timing voice", capability="audio", stage="voice", task="voice_generator"),
    "generate-voice": ActionSpec(action="generate-voice", label="Generate voice", capability="audio", stage="voice", task="voice_generator"),
    "align-voice": ActionSpec(action="align-voice", label="Align voice with Whisper", capability="audio", stage="timing", task="voice_aligner"),
    "direct": ActionSpec(action="direct", label="Create director plan", capability="structured", stage="direction", task="director"),
    "direct-mock": ActionSpec(action="direct-mock", label="Draft director plan offline", capability="structured", stage="direction", task="director"),
    "approve-director": ActionSpec(action="approve-director", label="Approve director plan", capability="structured", stage="direction", task="director_qa"),
    "prototype-prompt": ActionSpec(action="prototype-prompt", label="Prepare prototype brief", capability="code", stage="assets", task="prototype_builder"),
    "build-prototype": ActionSpec(action="build-prototype", label="Build prototype", capability="code", stage="assets", task="prototype_builder"),
    "repair-prototype": ActionSpec(action="repair-prototype", label="Repair prototype", capability="code", stage="assets", task="prototype_repair"),
    "record-demos": ActionSpec(action="record-demos", label="Record screen demos", capability="browser", stage="assets", task="screen_recorder"),
    "generate-graphics": ActionSpec(action="generate-graphics", label="Generate graphics", capability="structured", stage="assets", task="graphics_builder"),
    "prepare-preview": ActionSpec(action="prepare-preview", label="Build timeline preview", capability="render", stage="assembly", task="composition_preview"),
    "render-preview": ActionSpec(action="render-preview", label="Render preview", capability="render", stage="assembly", task="composition_renderer"),
    "run-qa": ActionSpec(action="run-qa", label="Run quality check", capability="structured", stage="review", task="final_qc"),
    "render-final": ActionSpec(action="render-final", label="Render final", capability="render", stage="assembly", task="composition_renderer"),
    "approve-final": ActionSpec(action="approve-final", label="Approve final", capability="structured", stage="review", task="final_qc"),
}

# Regeneration clears the active downstream chain before the job is queued.
# The previous artifacts are retained in _control/archive by the helper above.
ACTION_INVALIDATION: dict[str, str] = {
    "narrate": "narration",
    "narrate-mock": "narration",
    "mock-voice": "voice",
    "generate-voice": "voice",
    "align-voice": "timing",
    "direct": "direction",
    "direct-mock": "direction",
    "build-prototype": "prototype",
    "record-demos": "recordings",
    "generate-graphics": "graphics",
    "prepare-preview": "composition",
}

# These actions write validated checkpoints or independently reusable outputs.
# Resume keeps them active and starts at the narrowest safe continuation action.
RESUMABLE_ACTIONS = {
    "generate-voice", "build-prototype", "repair-prototype", "record-demos",
    "generate-graphics", "prepare-preview", "render-preview", "render-final",
}
RESUME_ACTION_MAP = {
    # A failed build that reached validation already contains a prototype; the
    # continuation should validate/repair it, not invoke the builder again.
    "build-prototype": "repair-prototype",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _store() -> ProjectStore:
    return ProjectStore(PROJECTS_ROOT)


def _progress(state: EpisodeState) -> int:
    values = {
        "input": 8,
        "narration_ready": 20,
        "voice_ready": 34,
        "timing_ready": 41,
        "director_review": 48,
        "director_approved": 60,
        "assets_ready": 74,
        "composition_ready": 84,
        "final_review": 92,
        "approved": 100,
    }
    return values.get(state.stage.value, 0)


def _updated_at(project: Path) -> str:
    files = [path for path in project.rglob("*") if path.is_file()]
    stamp = max((path.stat().st_mtime for path in files), default=project.stat().st_mtime)
    return datetime.fromtimestamp(stamp, UTC).isoformat()


def _summary(brief: EpisodeBrief, state: EpisodeState, project: Path) -> EpisodeSummary:
    return EpisodeSummary(
        episode_id=brief.episode_id,
        title=brief.title,
        industry=brief.industry,
        stage=state.stage.value,
        progress=_progress(state),
        approved_director=state.approved_director,
        approved_final=state.approved_final,
        updated_at=_updated_at(project),
        is_filled_episode=brief.is_filled_episode,
    )


def _optional_model(path: Path, model: type[BaseModel]) -> Any:
    return load_model(path, model) if path.exists() else None


def _artifacts(project: Path, episode_id: str) -> list[Artifact]:
    found: list[Artifact] = []
    patterns = [
        ("02_voice/voice_master.*", "Master voice", "audio"),
        ("06_recordings/*.*", "Screen recording", "video"),
        ("07_talking_head/*.*", "Presenter clip", "video"),
        ("10_final/preview.mp4", "Preview", "video"),
        ("10_final/final.mp4", "Final video", "video"),
    ]
    for pattern, label, kind in patterns:
        for path in sorted(project.glob(pattern)):
            if not path.is_file() or path.suffix.lower() == ".log":
                continue
            rel = path.relative_to(project).as_posix()
            found.append(Artifact(label=label, path=rel, kind=kind, url=f"/media/{episode_id}/{rel}"))
    if _prototype_entrypoint(project):
        found.append(Artifact(
            label="Working prototype",
            path="04_prototype/index.html",
            kind="prototype",
            url=f"/prototype/{episode_id}/index.html",
        ))
    graphics = project / "08_graphics/master.html"
    if graphics.is_file():
        found.append(Artifact(
            label="Graphics master preview", path="08_graphics/master.html", kind="graphics",
            url=f"/graphics/{episode_id}/master.html",
        ))
    timeline_preview = project / "09_composition/preview/index.html"
    if timeline_preview.is_file():
        found.append(Artifact(
            label="Interactive timeline preview", path="09_composition/preview/index.html", kind="composition",
            url=f"/composition/{episode_id}/preview/index.html",
        ))
    return found


def _detail(episode_id: str) -> EpisodeDetail:
    store = _store()
    project = store.project_dir(episode_id)
    if not project.exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    try:
        brief = store.brief(episode_id)
        state = store.state(episode_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Episode data is invalid: {exc}") from exc
    narration = _optional_model(project / "01_narration/narration.json", Narration)
    narration_quality = _optional_model(
        project / "01_narration/narration_quality.json", NarrationQualityReport,
    )
    voice = _optional_model(project / "02_voice/voice.json", VoiceMetadata)
    director_path = project / "03_director/director_plan.approved.json"
    if not director_path.exists():
        director_path = project / "03_director/director_plan.json"
    director = _optional_model(director_path, DirectorPlan)
    qa_result = None
    if (project / "03_director/director_plan.approved.json").exists():
        try:
            qa_result = episode_qa(project)
        except Exception as exc:
            qa_result = {"ok": False, "issues": [str(exc)], "warnings": []}
    completed = []
    checks = {
        "brief": project / "00_input/episode_brief.json",
        "narration": project / "01_narration/narration.json",
        "voice": project / "02_voice/voice.json",
        "timing": project / "02_voice/audio_timing.json",
        "direction": project / "03_director/director_plan.json",
        "director_approved": project / "03_director/director_plan.approved.json",
        "prototype": _prototype_entrypoint(project),
        "recordings": project / "06_recordings",
        "graphics": project / "08_graphics/graphics_plan.json",
        "timeline_preview": project / "09_composition/preview/index.html",
        "preview": project / "10_final/preview.mp4",
        "final": project / "10_final/final.mp4",
    }
    for key, path in checks.items():
        if key == "recordings":
            if path.exists() and any(p.is_file() and p.suffix != ".log" for p in path.iterdir()):
                completed.append(key)
        elif path and path.exists():
            completed.append(key)
    return EpisodeDetail(
        brief=brief,
        state=state,
        summary=_summary(brief, state, project),
        narration=narration,
        narration_quality=narration_quality,
        voice=voice,
        director=director,
        qa=qa_result,
        artifacts=_artifacts(project, episode_id),
        completed_steps=completed,
    )


def _serialize(value: Any) -> Any:
    return jsonable_encoder(value)


def _execute_action(episode_id: str, action: str, request: ActionRequest) -> Any:
    store = _store()
    if not store.project_dir(episode_id).exists():
        raise FileNotFoundError(f"Episode not found: {episode_id}")
    if action == "narrate":
        return generate_narration(store, episode_id)
    if action == "narrate-mock":
        return generate_narration(store, episode_id, agent_kind="mock")
    if action == "mock-voice":
        return mock_voice(store, episode_id, seconds=request.seconds)
    if action == "generate-voice":
        return generate_voice(store, episode_id)
    if action == "align-voice":
        return align_voice(store, episode_id)
    if action == "direct":
        return generate_director_plan(store, episode_id)
    if action == "direct-mock":
        return generate_director_plan(store, episode_id, agent_kind="mock")
    if action == "approve-director":
        return approve_director(store, episode_id)
    if action == "prototype-prompt":
        return write_prototype_builder_prompt(store, episode_id)
    if action == "build-prototype":
        return run_prototype_builder(store, episode_id)
    if action == "repair-prototype":
        return repair_prototype(store, episode_id)
    if action == "record-demos":
        return record_demos(store, episode_id)
    if action == "generate-graphics":
        return generate_graphics_plan(store, episode_id)
    if action == "prepare-preview":
        return prepare_timeline_preview(store, episode_id)
    if action == "render-preview":
        return render_preview(store, episode_id)
    if action == "run-qa":
        return episode_qa(store.project_dir(episode_id))
    if action == "render-final":
        return render_final(store, episode_id)
    if action == "approve-final":
        return store.approve_final(episode_id)
    raise ValueError(f"Unknown action: {action}")


class JobQueue:
    """A single production worker with disk-backed jobs, logs and progress events."""

    def __init__(self) -> None:
        # Rendering and browser capture are memory-heavy; serialize production work.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="factory-desk")
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._futures: dict[str, Future[None]] = {}

    def _control(self, episode_id: str) -> Path:
        path = _store().project_dir(episode_id) / "_control"
        (path / "jobs").mkdir(parents=True, exist_ok=True)
        return path

    def _job_path(self, episode_id: str, job_id: str) -> Path:
        return self._control(episode_id) / "jobs" / f"{job_id}.json"

    def _job_log_path(self, episode_id: str, job_id: str) -> Path:
        return self._control(episode_id) / "jobs" / f"{job_id}.log"

    def _save(self, job: ProductionJob) -> None:
        write_json(self._job_path(job.episode_id, job.job_id), job)

    def _event(self, job: ProductionJob, status: str, progress: float, message: str) -> None:
        now = _now()
        event = ProgressEvent(
            event_id=uuid.uuid4().hex[:12], episode_id=job.episode_id, job_id=job.job_id,
            stage=job.stage, task=job.task, capability=job.capability, status=status,
            completed=progress, total=100, unit="percent", percent=progress,
            message=message, timestamp=now,
        )
        path = self._control(job.episode_id) / "progress.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")

    def submit(
        self, episode_id: str, action: str, request: ActionRequest, *,
        invalidate: bool = True, resumed_from: str | None = None,
    ) -> ProductionJob:
        for existing in self.recent():
            if existing.status == "queued" or (existing.status == "running" and self._pid_alive(existing.pid)):
                raise RuntimeError(f"{existing.label} is already using the production worker")
        spec = ACTION_SPECS[action]
        invalidation_stage = ACTION_INVALIDATION.get(action)
        moved = _invalidate_from_stage(episode_id, invalidation_stage) if invalidate and invalidation_stage else []
        now = _now()
        message = (
            f"Resuming from checkpoints saved by job {resumed_from}"
            if resumed_from else
            f"Archived {len(moved)} downstream stage(s); waiting for the production worker"
            if invalidate and invalidation_stage else "Waiting for the production worker"
        )
        job = ProductionJob(
            job_id=uuid.uuid4().hex[:12], episode_id=episode_id, action=action,
            label=spec.label, stage=spec.stage, task=spec.task, capability=spec.capability,
            status="queued", message=message,
            request=request.model_dump(mode="json"), progress=0, resumable=action in RESUMABLE_ACTIONS,
            created_at=now, updated_at=now,
        )
        with self._lock:
            self._save(job)
            self._event(job, "queued", 0, job.message)
        future = self._executor.submit(self._run, job.job_id, episode_id)
        with self._lock:
            self._futures[job.job_id] = future
        future.add_done_callback(lambda _: self._forget_future(job.job_id))
        return job.model_copy(deep=True)

    def _forget_future(self, job_id: str) -> None:
        with self._lock:
            self._futures.pop(job_id, None)

    def _command(self, job: ProductionJob) -> list[str]:
        root = str(PROJECTS_ROOT)
        action_commands = {
            "narrate": ["narrate", job.episode_id],
            "narrate-mock": ["narrate", job.episode_id, "--agent", "mock"],
            "mock-voice": ["mock-voice", job.episode_id, "--seconds", str(job.request.get("seconds", 58))],
            "generate-voice": ["generate-voice", job.episode_id],
            "align-voice": ["align-voice", job.episode_id],
            "direct": ["direct", job.episode_id],
            "direct-mock": ["direct", job.episode_id, "--agent", "mock"],
            "approve-director": ["approve-director", job.episode_id],
            "prototype-prompt": ["prototype-prompt", job.episode_id],
            "build-prototype": ["build-prototype", job.episode_id],
            "repair-prototype": ["repair-prototype", job.episode_id],
            "record-demos": ["record-demos", job.episode_id],
            "generate-graphics": ["generate-graphics", job.episode_id],
            "prepare-preview": ["prepare-preview", job.episode_id],
            "render-preview": ["render-preview", job.episode_id],
            "run-qa": ["qa", job.episode_id],
            "render-final": ["render-final", job.episode_id],
            "approve-final": ["approve-final", job.episode_id],
        }
        return [sys.executable, "-m", "shorts_factory", *action_commands[job.action], "--root", root]

    def _run(self, job_id: str, episode_id: str) -> None:
        job_path = self._job_path(episode_id, job_id)
        job = ProductionJob.model_validate(read_json(job_path))
        if job.status == "stopped":
            with self._lock:
                self._futures.pop(job_id, None)
            return
        log_path = self._control(episode_id) / "production.log"
        command = self._command(job)
        output_tail: list[str] = []
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            process = subprocess.Popen(
                command, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env, start_new_session=True,
            )
            with self._lock:
                self._processes[job_id] = process
            persisted = ProductionJob.model_validate(read_json(job_path))
            if persisted.status == "stopped":
                self._terminate_process_group(process.pid, process)
                with self._lock:
                    self._processes.pop(job_id, None)
                return
            job = persisted.model_copy(update={
                "status": "running",
                "progress": 5,
                "message": f"{job.label} is running",
                "pid": process.pid,
                "updated_at": _now(),
            })
            self._save(job)
            self._event(job, "running", 5, job.message)
            with log_path.open("a", encoding="utf-8") as log, self._job_log_path(episode_id, job_id).open("a", encoding="utf-8") as job_log:
                header = f"\n[{_now()}] {job.job_id} {' '.join(command)}\n"
                log.write(header)
                job_log.write(header)
                log.flush()
                job_log.flush()
                if process.stdout:
                    for raw_line in process.stdout:
                        line = raw_line.rstrip()
                        log.write(raw_line)
                        job_log.write(raw_line)
                        log.flush()
                        job_log.flush()
                        if line:
                            output_tail.append(line)
                            output_tail = output_tail[-40:]
                            persisted = ProductionJob.model_validate(read_json(job_path))
                            if persisted.status == "stopped":
                                job.status = "stopped"
                                continue
                            if not line.startswith("SVF_PROGRESS "):
                                job.message = line[-240:]
                                job.progress = min(90, job.progress + 2)
                                job.updated_at = _now()
                                self._save(job)
                            else:
                                try:
                                    payload = json.loads(line.removeprefix("SVF_PROGRESS "))
                                    job.progress = float(payload.get("percent", job.progress))
                                    job.message = str(payload.get("message", job.message))[-240:]
                                    job.updated_at = _now()
                                    self._save(job)
                                    self._event(job, "running", job.progress, job.message)
                                except (ValueError, TypeError, json.JSONDecodeError):
                                    pass
            returncode = process.wait()
            with self._lock:
                self._processes.pop(job_id, None)
                self._futures.pop(job_id, None)
            latest = ProductionJob.model_validate(read_json(job_path))
            if latest.status == "stopped":
                return
            if returncode != 0:
                message = _failure_summary(output_tail, returncode)
                job.status = "failed"
                job.error = "\n".join(output_tail)[-4000:]
                job.message = message[-240:]
                job.progress = min(job.progress, 99)
            else:
                job.status = "succeeded"
                job.result = "\n".join(output_tail)[-4000:]
                job.message = f"{job.label} completed"
                job.progress = 100
            job.pid = None
            job.updated_at = _now()
            self._save(job)
            self._event(job, job.status, job.progress, job.message)
        except Exception as exc:
            try:
                latest = ProductionJob.model_validate(read_json(job_path))
                if latest.status == "stopped":
                    with self._lock:
                        self._processes.pop(job_id, None)
                        self._futures.pop(job_id, None)
                    return
            except Exception:
                pass
            job.status = "failed"
            job.error = str(exc)
            job.message = str(exc) or exc.__class__.__name__
            job.pid = None
            job.updated_at = _now()
            self._save(job)
            self._event(job, "failed", job.progress, job.message)
            with self._lock:
                self._processes.pop(job_id, None)
                self._futures.pop(job_id, None)

    def _find(self, job_id: str) -> Path | None:
        for path in PROJECTS_ROOT.glob(f"*/_control/jobs/{job_id}.json"):
            return path
        return None

    @staticmethod
    def _pid_alive(pid: int | None) -> bool:
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def get(self, job_id: str) -> ProductionJob | None:
        path = self._find(job_id)
        if not path:
            return None
        job = ProductionJob.model_validate(read_json(path))
        if job.resumable != (job.action in RESUMABLE_ACTIONS):
            job.resumable = job.action in RESUMABLE_ACTIONS
            self._save(job)
        if job.status == "running" and job.pid and job_id not in self._processes and not self._pid_alive(job.pid):
            if self._artifact_complete(job):
                job.status = "succeeded"
                job.progress = 100
                job.message = f"{job.label} completed before the desk restarted"
            else:
                job.status = "interrupted"
                job.message = "Worker stopped before the job could report completion; completed artifacts were preserved"
            job.pid = None
            job.updated_at = _now()
            self._save(job)
            self._event(job, job.status, job.progress, job.message)
        return job

    def resume(self, job_id: str) -> ProductionJob | None:
        original = self.get(job_id)
        if not original:
            return None
        if original.status not in {"failed", "stopped", "interrupted"}:
            raise RuntimeError("Only a failed, stopped or interrupted job can be resumed")
        if original.action not in RESUMABLE_ACTIONS:
            raise RuntimeError(f"{original.label} has no safe checkpoint to resume")
        action = RESUME_ACTION_MAP.get(original.action, original.action)
        request = ActionRequest.model_validate(original.request)
        return self.submit(
            original.episode_id, action, request,
            invalidate=False, resumed_from=original.job_id,
        )

    def _artifact_complete(self, job: ProductionJob) -> bool:
        project = _store().project_dir(job.episode_id)
        expected = {
            "narrate": project / "01_narration/narration.json",
            "narrate-mock": project / "01_narration/narration.json",
            "mock-voice": project / "02_voice/voice.json",
            "generate-voice": project / "02_voice/voice.json",
            "align-voice": project / "02_voice/audio_timing.json",
            "direct": project / "03_director/director_plan.json",
            "direct-mock": project / "03_director/director_plan.json",
            "approve-director": project / "03_director/director_plan.approved.json",
            "prototype-prompt": project / "_requests/prototype_builder_prompt.md",
            "generate-graphics": project / "08_graphics/graphics_plan.json",
            "prepare-preview": project / "09_composition/preview/index.html",
            "render-preview": project / "10_final/preview.mp4",
            "render-final": project / "10_final/final.mp4",
        }.get(job.action)
        if job.action == "build-prototype":
            expected = _prototype_entrypoint(project)
        if job.action == "repair-prototype":
            expected = project / "_requests/prototype_repair_report.json"
            if expected.is_file():
                try:
                    return read_json(expected).get("status") in {"not_needed", "repaired"}
                except Exception:
                    return False
        if job.action == "approve-final":
            try:
                return _store().state(job.episode_id).approved_final
            except Exception:
                return False
        if job.action == "record-demos":
            folder = project / "06_recordings"
            return folder.exists() and any(path.is_file() and path.suffix != ".log" for path in folder.iterdir())
        if not expected or not expected.exists():
            return False
        try:
            created = datetime.fromisoformat(job.created_at).timestamp()
            return expected.stat().st_mtime >= created - 1
        except (ValueError, OSError):
            return True

    def stop(self, job_id: str) -> ProductionJob | None:
        job = self.get(job_id)
        if not job:
            return None
        if job.status not in {"queued", "running"}:
            return job
        future = self._futures.get(job_id)
        if job.status == "queued" and future:
            future.cancel()
        # Persist cancellation before signaling. The worker reads this marker
        # after its process exits and must not misclassify SIGTERM as failure.
        job.status = "stopped"
        job.message = "Termination requested by the operator"
        job.updated_at = _now()
        self._save(job)
        process = self._processes.get(job_id)
        if process and process.poll() is None:
            self._terminate_process_group(process.pid, process)
        elif self._pid_alive(job.pid):
            self._terminate_process_group(job.pid)
        job.message = "Terminated by the operator; completed artifacts were preserved"
        job.pid = None
        job.updated_at = _now()
        self._save(job)
        self._event(job, "stopped", job.progress, job.message)
        with self._lock:
            self._processes.pop(job_id, None)
            self._futures.pop(job_id, None)
        return job

    @staticmethod
    def _terminate_process_group(pid: int | None, process: subprocess.Popen[str] | None = None) -> None:
        """Terminate a complete production process tree, escalating after a short grace period."""
        if not pid or pid <= 1:
            return
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError:
            if process and process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                return
            time.sleep(0.05)
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            if process and process.poll() is None:
                process.kill()

    def recent(self) -> list[ProductionJob]:
        jobs = []
        for path in PROJECTS_ROOT.glob("*/_control/jobs/*.json"):
            try:
                job = ProductionJob.model_validate(read_json(path))
                job.resumable = job.action in RESUMABLE_ACTIONS
                jobs.append(job)
            except Exception:
                continue
        return sorted(jobs, key=lambda item: item.created_at, reverse=True)[:20]


queue = JobQueue()
app = FastAPI(
    title="Factory Desk",
    description="Local production interface for the AI Short Video Factory",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard() -> DashboardResponse:
    store = _store()
    episodes: list[EpisodeSummary] = []
    for project in store.root.iterdir():
        if not project.is_dir() or project.name.startswith("."):
            continue
        try:
            brief = store.brief(project.name)
            state = store.state(project.name)
            episodes.append(_summary(brief, state, project))
        except Exception:
            continue
    episodes.sort(key=lambda item: item.updated_at, reverse=True)
    episode_summaries = {episode.episode_id: episode for episode in episodes}
    filled_episodes = []
    for episode in filled_episode_catalog().episodes:
        production = episode_summaries.get(episode.episode_id)
        filled_episodes.append(FilledEpisodeSummary(
            source_id=episode.source_id,
            episode_id=episode.episode_id,
            title=episode.title,
            industry=episode.industry,
            imported=production is not None,
            stage=production.stage if production else None,
            progress=production.progress if production else 0,
        ))
    providers = []
    for provider_id, provider in PROVIDERS.items():
        health = provider_health(provider_id)
        providers.append(ProviderStatus(
            provider_id=provider_id,
            label=provider["label"],
            capabilities=provider["capabilities"],
            **health,
        ))
    return DashboardResponse(
        episodes=episodes,
        filled_episodes=filled_episodes,
        providers=providers,
        actions=list(ACTION_SPECS.values()),
        tasks=TASKS,
        settings=store.settings(),
    )


@app.get("/api/filled-episodes/{source_id}", response_model=FilledEpisode)
def filled_episode_detail(source_id: str) -> FilledEpisode:
    try:
        return find_filled_episode(source_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Filled episode not found") from exc


@app.post("/api/filled-episodes/{source_id}/create", response_model=EpisodeDetail, status_code=201)
def create_filled_episode(source_id: str) -> EpisodeDetail:
    try:
        episode = find_filled_episode(source_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Filled episode not found") from exc
    store = _store()
    if store.project_dir(episode.episode_id).exists():
        return _detail(episode.episode_id)
    materialize_filled_episode(store, episode)
    return _detail(episode.episode_id)


@app.post("/api/filled-episodes/import", response_model=FilledEpisodeImportResult)
def import_all_filled_episodes() -> FilledEpisodeImportResult:
    store = _store()
    created: list[str] = []
    existing: list[str] = []
    for episode in filled_episode_catalog().episodes:
        if store.project_dir(episode.episode_id).exists():
            existing.append(episode.episode_id)
            continue
        materialize_filled_episode(store, episode)
        created.append(episode.episode_id)
    return FilledEpisodeImportResult(created=created, existing=existing)


@app.put("/api/project/settings", response_model=ProjectSettings)
def save_project_settings(request: ProjectSettingsRequest) -> ProjectSettings:
    return _store().save_settings(ProjectSettings(**request.model_dump()))


@app.post("/api/episodes", response_model=EpisodeDetail, status_code=201)
def create_episode(request: EpisodeCreateRequest) -> EpisodeDetail:
    brief = EpisodeBrief(**request.model_dump())
    try:
        _store().create(brief)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _detail(brief.episode_id)


@app.put("/api/episodes/{episode_id}/duration", response_model=EpisodeDetail)
def update_episode_duration(episode_id: str, request: EpisodeDurationRequest) -> EpisodeDetail:
    store = _store()
    project = store.project_dir(episode_id)
    if not project.exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    state = store.state(episode_id)
    if state.stage != EpisodeStage.INPUT or (project / "01_narration/narration.json").exists():
        raise HTTPException(
            status_code=409,
            detail="Duration can only change before narration. Archive from Narration first to rebuild the timeline safely.",
        )
    brief = store.brief(episode_id).model_copy(update={"target_seconds": request.target_seconds})
    write_json(project / "00_input/episode_brief.json", brief)
    return _detail(episode_id)


@app.put("/api/episodes/{episode_id}/graphics-theme", response_model=EpisodeDetail)
def update_episode_graphics_theme(
    episode_id: str, request: EpisodeGraphicsThemeRequest,
) -> EpisodeDetail:
    store = _store()
    project = store.project_dir(episode_id)
    if not project.exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    brief = store.brief(episode_id).model_copy(update={"graphics_theme": request.graphics_theme})
    write_json(project / "00_input/episode_brief.json", brief)
    return _detail(episode_id)


@app.post("/api/episodes/reference-demo", response_model=EpisodeDetail, status_code=201)
def create_reference_demo() -> EpisodeDetail:
    episode_id = "pain-001"
    store = _store()
    if store.project_dir(episode_id).exists():
        return _detail(episode_id)
    brief = EpisodeBrief(
        episode_id=episode_id,
        title="Context-aware receipt-to-job matcher",
        pain_point="Materials from multiple suppliers end up charged to the wrong job.",
        industry="Contractor / Handyman",
        role="Owner / GC",
        backend_summary=[
            "Vision AI reads vendor, date, items and total from the receipt.",
            "A reasoning step checks crew member, work schedule, supplier, items and recent job history.",
            "Deterministic rules accept strong matches and route ambiguous purchases to one review question.",
        ],
        viewer_diy=[
            "Keep an Active Jobs sheet.", "Send receipts through a shared message inbox.",
            "Use n8n and vision AI to extract fields.", "Route low-confidence results to review.",
        ],
    )
    store.create(brief)
    generate_narration(store, episode_id, agent_kind="mock")
    mock_voice(store, episode_id, seconds=58)
    generate_director_plan(store, episode_id, agent_kind="mock")
    approve_director(store, episode_id)
    bootstrap_reference_demo(store, episode_id)
    return _detail(episode_id)


@app.get("/api/episodes/{episode_id}", response_model=EpisodeDetail)
def episode_detail(episode_id: str) -> EpisodeDetail:
    return _detail(episode_id)


@app.get("/api/episodes/{episode_id}/models")
def episode_models(episode_id: str) -> dict[str, Any]:
    store = _store()
    if not store.project_dir(episode_id).exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    config = load_config(store, episode_id)
    routes = {}
    for task in TASKS:
        task_id = task["id"]
        resolved = resolve_task(config, task_id)
        routes[task_id] = {
            "provider": resolved["provider"], "model": resolved["model"],
            "reasoning_effort": resolved.get("reasoning_effort"),
            "voice_id": resolved.get("voice_id") if resolved["capability"] == "audio" else None,
            "fallback_provider": resolved.get("fallback_provider"),
            "fallback_model": resolved.get("fallback_model"),
            "capability": resolved["capability"], "group": task["group"],
        }
    providers = {
        provider_id: {
            "label": provider["label"], "models": provider["models"],
            "models_by_capability": provider.get("models_by_capability", {}),
            "reasoning_efforts": provider.get("reasoning_efforts", []),
            "capabilities": provider["capabilities"], "mode": provider["mode"],
            "supports_voice_catalog": provider_id in {"gemini", "elevenlabs"},
            "default_voice_id": provider.get("voice_id", ""),
        }
        for provider_id, provider in PROVIDERS.items()
    }
    return {"tasks": routes, "providers": providers}


@app.get("/api/tts/voices/{provider_id}", response_model=TTSVoiceCatalog)
def tts_voices(provider_id: str) -> TTSVoiceCatalog:
    provider = PROVIDERS.get(provider_id)
    if not provider or "audio" not in provider["capabilities"]:
        raise HTTPException(status_code=404, detail=f"Unknown TTS provider: {provider_id}")
    try:
        voices = list_tts_voices(provider_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TTSVoiceCatalog(provider=provider_id, voices=voices)


@app.put("/api/episodes/{episode_id}/models")
def save_episode_models(episode_id: str, request: ModelMapRequest) -> dict[str, Any]:
    store = _store()
    project = store.project_dir(episode_id)
    if not project.exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    known_tasks = {task["id"] for task in TASKS}
    overrides: dict[str, dict[str, Any]] = {}
    for task_id, selection in request.tasks.items():
        if task_id not in known_tasks:
            raise HTTPException(status_code=422, detail=f"Unknown task: {task_id}")
        provider_id = selection.provider
        model = selection.model
        provider = PROVIDERS.get(provider_id)
        if not provider:
            raise HTTPException(status_code=422, detail=f"Unknown provider: {provider_id}")
        task = next(item for item in TASKS if item["id"] == task_id)
        if model not in provider_models(provider_id, task["capability"]):
            raise HTTPException(status_code=422, detail=f"Model {model} is not registered for {provider_id} {task['capability']}")
        efforts = provider.get("reasoning_efforts", [])
        reasoning = selection.reasoning_effort
        if efforts and reasoning is not None and reasoning not in efforts:
            raise HTTPException(status_code=422, detail=f"Unsupported reasoning effort for {provider_id}: {reasoning}")
        voice_id = selection.voice_id
        if voice_id and task["capability"] != "audio":
            raise HTTPException(status_code=422, detail=f"Task {task_id} does not accept a voice")
        if provider_id == "gemini" and voice_id:
            known_voice_ids = {voice.voice_id for voice in list_tts_voices("gemini")}
            if voice_id not in known_voice_ids:
                raise HTTPException(status_code=422, detail=f"Unknown Gemini TTS voice: {voice_id}")
        overrides[task_id] = {
            "provider": provider_id, "model": model,
            **({"reasoning_effort": reasoning or efforts[0]} if efforts else {}),
            **({"voice_id": voice_id} if voice_id else {}),
        }
    candidate = default_config()
    global_path = store.root / ".svf-orchestrator.json"
    if global_path.exists():
        candidate = load_config(store)
    for task_id, values in overrides.items():
        candidate["tasks"][task_id].update(values)
        try:
            resolve_task(candidate, task_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    write_json(project / "_control/model-map.json", {"version": 1, "tasks": overrides})
    return episode_models(episode_id)


@app.get("/api/episodes/{episode_id}/prompts")
def episode_prompts(episode_id: str) -> dict[str, Any]:
    project = _store().project_dir(episode_id)
    if not project.exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    request_dir = project / "_requests"
    records = []
    usage = {"invocations": 0, "attempts": 0, "estimated_input_tokens": 0, "output_tokens": 0}
    for invocation_path in sorted(request_dir.glob("*_invocation.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            invocation = PromptInvocation.model_validate(read_json(invocation_path))
        except Exception:
            continue
        def content(path_value: str, limit: int = 40000) -> str | None:
            path = Path(path_value)
            if not path.is_absolute():
                path = project / path
            try:
                resolved = path.resolve()
                if project.resolve() not in resolved.parents or not resolved.is_file():
                    return None
                return resolved.read_text(encoding="utf-8", errors="replace")[-limit:]
            except OSError:
                return None
        records.append({
            "invocation": invocation.model_dump(mode="json"),
            "prompt": content(invocation.prompt_path),
            "schema": content(invocation.schema_path),
            "response": content(invocation.response_path),
        })
        usage["invocations"] += 1
        usage["attempts"] += invocation.attempts
        usage["estimated_input_tokens"] += invocation.estimated_input_tokens or 0
        usage["output_tokens"] += invocation.output_tokens or 0
    return {"records": records, "usage": usage}


@app.get("/api/episodes/{episode_id}/logs")
def episode_logs(episode_id: str, limit: int = 200) -> dict[str, Any]:
    project = _store().project_dir(episode_id)
    if not project.exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    limit = max(10, min(limit, 1000))
    path = project / "_control/production.log"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:] if path.exists() else []
    return {"lines": lines}


@app.get("/api/jobs/{job_id}/logs")
def job_logs(job_id: str, limit: int = 200) -> dict[str, Any]:
    job = queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    limit = max(10, min(limit, 1000))
    path = queue._job_log_path(job.episode_id, job.job_id)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:] if path.exists() else []
    if job.action == "build-prototype" and job.status == "running":
        _, file_count, newest = _prototype_activity(_store().project_dir(job.episode_id) / "04_prototype")
        if newest:
            lines.append(f"Live filesystem activity: {newest} ({file_count} source files observed)")
    if not lines and job.message:
        lines = [job.message]
    return {"job_id": job_id, "lines": lines}


@app.get("/api/episodes/{episode_id}/progress")
def episode_progress(episode_id: str, limit: int = 100) -> dict[str, Any]:
    project = _store().project_dir(episode_id)
    if not project.exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    limit = max(10, min(limit, 1000))
    path = project / "_control/progress.jsonl"
    events = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {"events": events}


@app.post("/api/episodes/{episode_id}/reset")
def reset_episode(episode_id: str, request: ResetRequest) -> dict[str, Any]:
    if not request.confirm:
        raise HTTPException(status_code=409, detail="Reset requires explicit operator confirmation")
    project = _store().project_dir(episode_id)
    if not project.exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    reset_stage = {"render": "composition"}.get(request.from_stage, request.from_stage)
    moved = _invalidate_from_stage(episode_id, reset_stage)
    return {"message": f"Archived {len(moved)} populated stages", "moved": moved}


@app.post("/api/episodes/{episode_id}/actions/{action}", response_model=ProductionJob, status_code=202)
def start_action(episode_id: str, action: str, request: ActionRequest | None = None) -> ProductionJob:
    if action not in ACTION_SPECS:
        raise HTTPException(status_code=404, detail="Unknown production action")
    if not _store().project_dir(episode_id).exists():
        raise HTTPException(status_code=404, detail="Episode not found")
    try:
        return queue.submit(episode_id, action, request or ActionRequest())
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _save_upload(upload: UploadFile, suffixes: set[str]) -> Path:
    suffix = Path(upload.filename or "upload").suffix.lower()
    if suffix not in suffixes:
        raise HTTPException(status_code=415, detail=f"Unsupported file type. Use: {', '.join(sorted(suffixes))}")
    handle = tempfile.NamedTemporaryFile(prefix="factory-desk-", suffix=suffix, delete=False)
    path = Path(handle.name)
    try:
        with handle:
            shutil.copyfileobj(upload.file, handle)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


@app.post("/api/episodes/{episode_id}/voice", response_model=UploadResult)
def upload_voice(episode_id: str, file: UploadFile = File(...)) -> UploadResult:
    from ..pipeline import import_voice

    temp = _save_upload(file, {".wav", ".mp3", ".m4a", ".aac", ".flac"})
    try:
        result = import_voice(_store(), episode_id, temp)
    finally:
        temp.unlink(missing_ok=True)
    return UploadResult(
        episode_id=episode_id,
        capability="audio",
        path=result.audio_path,
        message="Master voice imported and set as the timeline",
    )


@app.post("/api/episodes/{episode_id}/talking-head/{scene_id}", response_model=UploadResult)
def upload_talking_head(episode_id: str, scene_id: str, file: UploadFile = File(...)) -> UploadResult:
    from ..pipeline import import_talking_head

    temp = _save_upload(file, {".mp4", ".mov", ".webm", ".m4v"})
    try:
        try:
            result = import_talking_head(_store(), episode_id, scene_id, temp)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        temp.unlink(missing_ok=True)
    return UploadResult(
        episode_id=episode_id,
        capability="talking_head",
        path=str(result),
        message=f"Presenter clip attached to {scene_id}",
    )


@app.get("/api/jobs", response_model=list[ProductionJob])
def recent_jobs() -> list[ProductionJob]:
    return queue.recent()


@app.get("/api/jobs/{job_id}", response_model=ProductionJob)
def job_detail(job_id: str) -> ProductionJob:
    job = queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/stop", response_model=ProductionJob)
def stop_job(job_id: str) -> ProductionJob:
    job = queue.stop(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/terminate", response_model=ProductionJob)
def terminate_job(job_id: str) -> ProductionJob:
    return stop_job(job_id)


@app.post("/api/jobs/{job_id}/resume", response_model=ProductionJob, status_code=202)
def resume_job(job_id: str) -> ProductionJob:
    try:
        job = queue.resume(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _safe_project_file(episode_id: str, relative_path: str, root_folder: str | None = None) -> Path:
    project = _store().project_dir(episode_id).resolve()
    base = (project / root_folder).resolve() if root_folder else project
    candidate = (base / relative_path).resolve()
    if candidate != base and base not in candidate.parents:
        raise HTTPException(status_code=403, detail="Path is outside the episode")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return candidate


@app.get("/media/{episode_id}/{relative_path:path}", include_in_schema=False)
def media(episode_id: str, relative_path: str) -> FileResponse:
    return FileResponse(_safe_project_file(episode_id, relative_path))


@app.get("/prototype/{episode_id}/{relative_path:path}", include_in_schema=False)
def prototype(episode_id: str, relative_path: str) -> FileResponse:
    project = _store().project_dir(episode_id)
    root = _prototype_root(project).resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=403, detail="Path is outside the prototype")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Prototype file not found")
    return FileResponse(candidate)


@app.get("/graphics/{episode_id}/{relative_path:path}", include_in_schema=False)
def graphics(episode_id: str, relative_path: str) -> FileResponse:
    return FileResponse(_safe_project_file(episode_id, relative_path, "08_graphics"))


@app.get("/composition/{episode_id}/{relative_path:path}", include_in_schema=False)
def composition(episode_id: str, relative_path: str) -> FileResponse:
    # Resolve from the project root so copied/symlinked preview media remains readable,
    # while _safe_project_file still prevents leaving the episode directory.
    return FileResponse(_safe_project_file(episode_id, f"09_composition/{relative_path}"))


def _prototype_root(project: Path) -> Path:
    dist = project / "04_prototype/dist"
    return dist if (dist / "index.html").is_file() else project / "04_prototype"


def _prototype_entrypoint(project: Path) -> Path | None:
    entrypoint = _prototype_root(project) / "index.html"
    return entrypoint if entrypoint.is_file() else None
