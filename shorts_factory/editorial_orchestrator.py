from __future__ import annotations

import copy


def register_editorial_tasks() -> None:
    """Register independently routable legacy editorial graphics stages.

    The base orchestrator exposes a single graphics_builder task. This branch
    keeps the structured layout task IDs for compatibility. The active
    whiteboard renderer itself is deterministic and requires no image or video
    provider.

    Existing project model maps continue to validate.
    """

    from . import orchestrator

    definitions = [
        {"id": "graphics_layout", "capability": "structured", "group": "Assets"},
        {"id": "graphics_coder", "capability": "structured", "group": "Assets"},
        {"id": "graphics_code_repair", "capability": "structured", "group": "Assets"},
    ]
    known = {task["id"] for task in orchestrator.TASKS}
    insertion = next(
        (index for index, task in enumerate(orchestrator.TASKS) if task["id"] == "graphics_builder"),
        len(orchestrator.TASKS),
    )
    for definition in definitions:
        if definition["id"] in known:
            continue
        orchestrator.TASKS.insert(insertion, definition)
        insertion += 1
        known.add(definition["id"])

    codex_structured = {
        **orchestrator.route(
            "codex", "gpt-5.6-sol", retries=0,
            fallback_provider="", fallback_model="",
        ),
        "reasoning_effort": "medium",
    }
    routes = {
        "graphics_layout": copy.deepcopy(codex_structured),
        "graphics_coder": copy.deepcopy(codex_structured),
        "graphics_code_repair": copy.deepcopy(codex_structured),
    }
    for task_id, values in routes.items():
        orchestrator.DEFAULT_ROUTES.setdefault(task_id, copy.deepcopy(values))
        orchestrator.PROFILES.setdefault("quality", {}).setdefault(task_id, copy.deepcopy(values))
        orchestrator.PROFILES.setdefault("codex_first", {}).setdefault(task_id, copy.deepcopy(values))
        orchestrator.PROFILES.setdefault("offline", {}).setdefault(
            task_id,
            orchestrator.route(
                "mock", "deterministic", retries=0, timeout=60,
                fallback_provider="mock", fallback_model="deterministic",
            ),
        )
