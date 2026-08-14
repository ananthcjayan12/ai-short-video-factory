from __future__ import annotations

import copy
import os
import shutil
from pathlib import Path
from typing import Any


PROVIDERS: dict[str, dict[str, Any]] = {
    "codex": {
        "id": "codex", "label": "Codex CLI", "mode": "command", "adapter": "command",
        "executable": "codex", "capabilities": ["structured", "code"],
        "command_template": "codex exec --skip-git-repo-check --model {model} --output-last-message {output} - < {prompt}",
        "models": ["gpt-5.6-sol", "gpt-5.6-terra"],
    },
    "claude_code": {
        "id": "claude_code", "label": "Claude Code", "mode": "command", "adapter": "command",
        "executable": "claude", "capabilities": ["structured", "code"],
        "command_template": "claude --model {model} -p \"$(cat {prompt})\" > {output}",
        "models": ["claude-fable-5", "claude-sonnet-5"],
    },
    "custom_cli": {
        "id": "custom_cli", "label": "Custom CLI", "mode": "command", "adapter": "command",
        "executable": None, "capabilities": ["structured", "code", "audio", "talking_head"],
        "command_template": "", "media_command_template": "", "models": ["your-model"],
    },
    "manual_voice": {
        "id": "manual_voice", "label": "Manual / external voice", "mode": "manual", "adapter": "manual",
        "executable": None, "capabilities": ["audio"], "command_template": "", "media_command_template": "", "models": ["external"]
    },
    "manual_talking_head": {
        "id": "manual_talking_head", "label": "Real camera talking head", "mode": "manual", "adapter": "manual",
        "executable": None, "capabilities": ["talking_head"], "command_template": "", "media_command_template": "", "models": ["real camera"]
    },
    "infinite_talk": {
        "id": "infinite_talk", "label": "InfiniteTalk adapter", "mode": "command", "adapter": "command",
        "executable": None, "capabilities": ["talking_head"], "command_template": "", "media_command_template": "", "models": ["configured externally"]
    },
    "playwright": {
        "id": "playwright", "label": "Playwright recorder", "mode": "local", "adapter": "playwright",
        "executable": "node", "capabilities": ["browser"], "command_template": "", "models": ["Chromium"]
    },
    "hyperframes": {
        "id": "hyperframes", "label": "HyperFrames", "mode": "local", "adapter": "hyperframes",
        "executable": "hyperframes", "capabilities": ["render"], "command_template": "", "models": ["0.7.62"]
    },
    "ffmpeg": {
        "id": "ffmpeg", "label": "FFmpeg", "mode": "local", "adapter": "ffmpeg",
        "executable": "ffmpeg", "capabilities": ["render"], "command_template": "", "models": ["local"]
    },
    "mock": {
        "id": "mock", "label": "Offline Mock", "mode": "mock", "adapter": "mock",
        "executable": None, "capabilities": ["structured", "code", "audio", "browser", "talking_head", "render"],
        "command_template": "", "models": ["deterministic"]
    },
}

TASKS = [
    {"id": "narration_writer", "capability": "structured", "group": "Story"},
    {"id": "narration_qa", "capability": "structured", "group": "Story"},
    {"id": "voice_generator", "capability": "audio", "group": "Audio"},
    {"id": "director", "capability": "structured", "group": "Direction"},
    {"id": "director_qa", "capability": "structured", "group": "Direction"},
    {"id": "prototype_builder", "capability": "code", "group": "Assets"},
    {"id": "screen_recorder", "capability": "browser", "group": "Assets"},
    {"id": "talking_head_generator", "capability": "talking_head", "group": "Assets"},
    {"id": "graphics_builder", "capability": "structured", "group": "Assets"},
    {"id": "composition_renderer", "capability": "render", "group": "Assembly"},
    {"id": "final_qc", "capability": "structured", "group": "Assembly"},
]


def route(provider: str, model: str, *, retries: int = 1, timeout: int = 900,
          fallback_provider: str = "mock", fallback_model: str = "deterministic") -> dict[str, Any]:
    return {
        "provider": provider, "model": model, "retry_count": retries, "timeout_seconds": timeout,
        "fallback_provider": fallback_provider, "fallback_model": fallback_model, "enabled": True,
    }


DEFAULT_ROUTES = {
    "narration_writer": route("claude_code", "claude-fable-5", fallback_provider="codex", fallback_model="gpt-5.6-sol"),
    "narration_qa": route("codex", "gpt-5.6-sol", fallback_provider="claude_code", fallback_model="claude-sonnet-5"),
    "voice_generator": route("manual_voice", "external", retries=0, timeout=0, fallback_provider="mock"),
    "director": route("claude_code", "claude-sonnet-5", fallback_provider="codex", fallback_model="gpt-5.6-sol"),
    "director_qa": route("codex", "gpt-5.6-sol", fallback_provider="claude_code", fallback_model="claude-sonnet-5"),
    "prototype_builder": route("codex", "gpt-5.6-sol", timeout=1800, fallback_provider="claude_code", fallback_model="claude-sonnet-5"),
    "screen_recorder": route("playwright", "Chromium", retries=1, timeout=600, fallback_provider="mock"),
    "talking_head_generator": route("manual_talking_head", "real camera", retries=0, timeout=0, fallback_provider="mock"),
    "graphics_builder": route("codex", "gpt-5.6-terra", fallback_provider="mock"),
    "composition_renderer": route("hyperframes", "0.7.62", timeout=14400, fallback_provider="ffmpeg", fallback_model="local"),
    "final_qc": route("codex", "gpt-5.6-sol", fallback_provider="claude_code", fallback_model="claude-sonnet-5"),
}

PROFILES = {
    "quality": copy.deepcopy(DEFAULT_ROUTES),
    "codex_first": {k: (route("codex", "gpt-5.6-sol") if v.get("provider") in {"codex", "claude_code"} else copy.deepcopy(v)) for k, v in DEFAULT_ROUTES.items()},
    "offline": {task["id"]: route("mock", "deterministic", retries=0, timeout=60, fallback_provider="mock") for task in TASKS},
}


def default_config() -> dict[str, Any]:
    return {
        "version": 1,
        "active_profile": "quality",
        "tasks": copy.deepcopy(DEFAULT_ROUTES),
        "providers": {pid: {"enabled": True, "command_template": p.get("command_template", ""), "media_command_template": p.get("media_command_template", "")} for pid, p in PROVIDERS.items()},
    }


def resolve_task(config: dict[str, Any], task_id: str) -> dict[str, Any]:
    defs = {t["id"]: t for t in TASKS}
    if task_id not in defs:
        raise ValueError(f"Unknown task: {task_id}")
    route_cfg = copy.deepcopy(config["tasks"][task_id])
    provider = PROVIDERS[route_cfg["provider"]]
    capability = defs[task_id]["capability"]
    if capability not in provider["capabilities"]:
        raise ValueError(f"Provider {provider['id']} cannot execute {capability} task {task_id}")
    fallback = PROVIDERS.get(route_cfg.get("fallback_provider"), {})
    if fallback and capability not in fallback.get("capabilities", []):
        raise ValueError(f"Fallback {fallback.get('id')} cannot execute {capability} task {task_id}")
    override = config.get("providers", {}).get(provider["id"], {})
    route_cfg.update({
        "task_id": task_id,
        "capability": capability,
        "provider_mode": provider["mode"],
        "provider_adapter": provider["adapter"],
        "command_template": override.get("command_template") or provider.get("command_template", ""),
        "media_command_template": override.get("media_command_template") or provider.get("media_command_template", ""),
    })
    return route_cfg


def provider_health(provider_id: str) -> dict[str, Any]:
    p = PROVIDERS[provider_id]
    if p["mode"] in {"manual", "mock"}:
        return {"healthy": True, "status": "ready", "detail": p["mode"]}
    if provider_id == "hyperframes":
        root = Path(__file__).resolve().parents[1]
        ok = bool(shutil.which("hyperframes") or (root / "node_modules/.bin/hyperframes").exists())
        return {"healthy": ok, "status": "ready" if ok else "missing", "detail": "available" if ok else "run npm install"}
    if provider_id == "playwright":
        root = Path(__file__).resolve().parents[1]
        package = root / "node_modules/playwright"
        ok = bool(package.exists())
        return {"healthy": ok, "status": "ready" if ok else "missing", "detail": "package installed" if ok else "run npm install && npx playwright install chromium"}
    if provider_id in {"custom_cli", "infinite_talk"}:
        return {"healthy": False, "status": "unconfigured", "detail": "set a command template in projects/.svf-orchestrator.json"}
    executable = p.get("executable")
    ok = bool(executable and shutil.which(executable))
    return {"healthy": ok, "status": "ready" if ok else "missing", "detail": executable or "configure command"}
