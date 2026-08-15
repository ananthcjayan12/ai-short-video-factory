from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


PROMPT_ROOT = Path(__file__).resolve().parent / "prompt_templates"


class PromptTaskSpec(BaseModel):
    task: str
    capability: str
    system_file: str
    user_file: str
    default_provider: str
    default_model: str
    external_confirmation: bool = False
    max_tokens: int = Field(default=16000, ge=1)


class PromptBundle(BaseModel):
    task: str
    system: str
    user: str
    system_file: str
    user_file: str


def task_specs() -> dict[str, PromptTaskSpec]:
    payload = json.loads((PROMPT_ROOT / "prompt_model_mapping.json").read_text(encoding="utf-8"))
    return {
        task_id: PromptTaskSpec(task=task_id, **values)
        for task_id, values in payload.get("tasks", {}).items()
    }


def _render(path: Path, values: dict[str, Any]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    missing = sorted(set(re.findall(r"\{([a-z][a-z0-9_]*)\}", text)))
    if missing:
        raise ValueError(f"Missing prompt variables for {path.name}: {', '.join(missing)}")
    return text


def build_prompt(task: str, **values: Any) -> PromptBundle:
    specs = task_specs()
    if task not in specs:
        raise KeyError(f"No prompt registered for task {task}")
    spec = specs[task]
    return PromptBundle(
        task=task,
        system=_render(PROMPT_ROOT / spec.system_file, values),
        user=_render(PROMPT_ROOT / spec.user_file, values),
        system_file=spec.system_file,
        user_file=spec.user_file,
    )
