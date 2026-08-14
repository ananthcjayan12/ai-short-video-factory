from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

from .agents import CommandAgent, ManualAgent, MockAgent, StructuredAgent
from .demo import bootstrap_pain001
from .director import normalize, validate_budgets
from .io import atomic_write_text, load_model, read_json, write_json
from .models import (
    DirectorPlan, EpisodeBrief, EpisodeStage, Narration, VoiceMetadata,
)
from .orchestrator import PROVIDERS, default_config, resolve_task
from .project import ProjectStore
from .prompts import director_prompt, narration_prompt
from .rendering.hyperframes import render as render_hyperframes


def load_config(store: ProjectStore) -> dict[str, Any]:
    config = default_config()
    path = store.root / ".svf-orchestrator.json"
    if not path.exists():
        return config
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
    config = load_config(store)
    resolved = resolve_task(config, task_id)
    if resolved["provider_mode"] == "mock":
        return MockAgent(context)
    if resolved["provider_mode"] == "manual":
        return ManualAgent(consume_response=consume_response)
    if resolved["provider_adapter"] != "command":
        raise RuntimeError(f"Structured provider adapter not implemented in this MVP: {resolved['provider_adapter']}")
    fallback = PROVIDERS.get(resolved.get("fallback_provider"), {})
    fallback_template = ""
    if fallback.get("mode") == "command":
        fallback_template = load_config(store).get("providers", {}).get(fallback["id"], {}).get("command_template") or fallback.get("command_template", "")
    return CommandAgent(
        command_template=resolved["command_template"], model=resolved["model"],
        timeout=max(1, int(resolved.get("timeout_seconds", 900))), retries=int(resolved.get("retry_count", 1)),
        fallback_template=fallback_template, fallback_model=resolved.get("fallback_model", ""),
    )


def generate_narration(store: ProjectStore, episode_id: str, *, agent_kind: str | None = None,
                       consume_response: bool = False) -> Narration:
    brief = store.brief(episode_id)
    context = {"episode_id": episode_id, "brief": brief}
    agent = _structured_agent(store, "narration_writer", context, agent_kind=agent_kind, consume_response=consume_response)
    narration = agent.run(stage="narration", prompt=narration_prompt(brief), output_model=Narration,
                          request_dir=store.project_dir(episode_id) / "_requests")
    out = store.project_dir(episode_id) / "01_narration"
    write_json(out / "narration.json", narration)
    atomic_write_text(out / "narration.txt", narration.text + "\n")
    store.transition(episode_id, EpisodeStage.NARRATION_READY)
    return narration


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
    meta = VoiceMetadata(episode_id=episode_id, audio_path=str(dest.relative_to(project)), duration_seconds=_duration(dest), source=source_kind)
    write_json(project / "02_voice/voice.json", meta)
    store.transition(episode_id, EpisodeStage.VOICE_READY)
    return meta


def mock_voice(store: ProjectStore, episode_id: str, *, seconds: float = 58.0) -> VoiceMetadata:
    project = store.project_dir(episode_id)
    dest = project / "02_voice/voice_master.wav"
    dest.parent.mkdir(parents=True, exist_ok=True)
    rate = 16000
    with wave.open(str(dest), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * int(rate * seconds))
    meta = VoiceMetadata(episode_id=episode_id, audio_path=str(dest.relative_to(project)), duration_seconds=seconds, source="mock")
    write_json(project / "02_voice/voice.json", meta)
    store.transition(episode_id, EpisodeStage.VOICE_READY)
    return meta


def generate_director_plan(store: ProjectStore, episode_id: str, *, agent_kind: str | None = None,
                           consume_response: bool = False) -> DirectorPlan:
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    narration = load_model(project / "01_narration/narration.json", Narration)
    voice = load_model(project / "02_voice/voice.json", VoiceMetadata) if (project / "02_voice/voice.json").exists() else None
    context = {"episode_id": episode_id, "brief": brief, "narration": narration, "voice": voice}
    agent = _structured_agent(store, "director", context, agent_kind=agent_kind, consume_response=consume_response)
    raw = agent.run(stage="director", prompt=director_prompt(brief, narration, voice), output_model=DirectorPlan,
                    request_dir=project / "_requests")
    normalized = normalize(raw)
    write_json(project / "03_director/director_plan.raw.json", raw)
    write_json(project / "03_director/director_plan.json", normalized)
    store.transition(episode_id, EpisodeStage.DIRECTOR_REVIEW)
    return normalized


def approve_director(store: ProjectStore, episode_id: str) -> DirectorPlan:
    project = store.project_dir(episode_id)
    plan = load_model(project / "03_director/director_plan.json", DirectorPlan)
    issues = validate_budgets(plan)
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
    jobs_path = project / "05_asset_jobs/demo_jobs.json"
    if not jobs_path.exists():
        raise RuntimeError("No demo jobs. Build/bootstrap the prototype first.")
    jobs = read_json(jobs_path)["jobs"]
    repo_root = Path(__file__).resolve().parents[1]
    server = subprocess.Popen([sys.executable, str(repo_root / "scripts/serve_demo.py"), str(project / "04_prototype"), str(port)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.8)
        outputs: list[Path] = []
        for job in jobs:
            job_path = project / "05_asset_jobs" / f"{job['job_id']}.json"
            r = subprocess.run(["node", str(repo_root / "scripts/record_demo.mjs"), str(job_path), str(project)],
                               cwd=repo_root, capture_output=True, text=True, timeout=600)
            (project / "06_recordings" / f"{job['job_id']}.log").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
            if r.returncode != 0:
                raise RuntimeError(f"Playwright recording failed for {job['job_id']}: {(r.stderr or r.stdout)[-3000:]}")
            outputs.append(project / job["output_path"])
        _attach_recordings_to_plan(project, jobs)
        store.transition(episode_id, EpisodeStage.ASSETS_READY)
        return outputs
    finally:
        server.terminate()
        try: server.wait(timeout=3)
        except subprocess.TimeoutExpired: server.kill()


def _attach_recordings_to_plan(project: Path, jobs: list[dict[str, Any]]) -> None:
    plan = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    by_id = {j["job_id"]: j for j in jobs}
    scenes = []
    for scene in plan.scenes:
        if scene.demo_job_id and scene.demo_job_id in by_id:
            scene = scene.model_copy(update={"generated_asset": by_id[scene.demo_job_id]["output_path"]})
        scenes.append(scene)
    write_json(project / "03_director/director_plan.approved.json", plan.model_copy(update={"scenes": scenes}))


def import_talking_head(store: ProjectStore, episode_id: str, scene_id: str, source: Path) -> Path:
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
    prompt = f"""You are the prototype builder for a YouTube Short. Build a SMALL working synthetic demo in the current directory.

Episode: {brief.title}
Pain: {brief.pain_point}
Industry: {brief.industry}
Backend facts: {json.dumps(brief.backend_summary)}

Screen scenes to support:
{json.dumps([s.model_dump(mode='json') for s in screens], indent=2)}

Requirements:
- synthetic data only;
- one polished vertical-friendly local web app;
- stable data-testid selectors for every Playwright action;
- deterministic expected states and obvious exception/review state;
- AI may be mocked deterministically for the visual demo unless a configured model is explicitly required;
- do not fake client data or numerical outcomes;
- create README-DEMO.md with start command and exact data-testid selectors;
- keep implementation small and easy for another coding agent to repair.

Build the files directly in this directory. Do not only describe the solution."""
    path = project / "_requests/prototype_builder_prompt.md"
    atomic_write_text(path, prompt)
    return path


def run_prototype_builder(store: ProjectStore, episode_id: str) -> Path:
    project = store.project_dir(episode_id)
    prompt = write_prototype_builder_prompt(store, episode_id)
    config = load_config(store)
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
    r = subprocess.run(cmd, shell=True, cwd=out_dir, capture_output=True, text=True, timeout=int(route.get("timeout_seconds", 1800)))
    (project / "_requests/prototype_builder.log").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"Prototype builder failed: {(r.stderr or r.stdout)[-4000:]}")
    return out_dir


def shlex_quote(value: str) -> str:
    import shlex
    return shlex.quote(value)


def render_preview(store: ProjectStore, episode_id: str) -> dict[str, Any]:
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    output = project / "10_final/preview.mp4"
    report = render_hyperframes(project, preview=True, width=brief.width, height=brief.height, output=output)
    store.transition(episode_id, EpisodeStage.FINAL_REVIEW)
    return report


def render_final(store: ProjectStore, episode_id: str) -> dict[str, Any]:
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    output = project / "10_final/final.mp4"
    return render_hyperframes(project, preview=False, width=brief.width, height=brief.height, output=output)


def generate_voice(store: ProjectStore, episode_id: str) -> VoiceMetadata:
    """Run a configured audio provider. Default route is manual, by design."""
    project = store.project_dir(episode_id)
    narration = load_model(project / "01_narration/narration.json", Narration)
    config = load_config(store)
    route = resolve_task(config, "voice_generator")
    if route["provider_mode"] == "manual":
        raise RuntimeError("voice_generator is manual by default. Use svf import-voice, or route voice_generator to custom_cli with a media_command_template.")
    template = route.get("media_command_template", "").strip()
    if not template:
        raise RuntimeError(f"No media_command_template configured for {route['provider']}")
    prompt_path = project / "_requests/voice_text.txt"
    atomic_write_text(prompt_path, narration.text + "\n")
    output = project / "02_voice/voice_master.wav"
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
    project = store.project_dir(episode_id)
    plan_path = project / "03_director/director_plan.approved.json"
    plan = load_model(plan_path, DirectorPlan)
    scene = next((s for s in plan.scenes if s.scene_id == scene_id), None)
    if not scene or scene.type not in {"talking_head", "cta"}:
        raise ValueError(f"{scene_id} is not a presenter scene")
    config = load_config(store)
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
