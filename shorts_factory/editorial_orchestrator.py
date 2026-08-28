from __future__ import annotations

import copy


def register_editorial_tasks() -> None:
    """Register split graphics stages without removing the legacy graphics_builder route.

    The base orchestrator predates the editorial sequence planner and exposes a
    single graphics_builder task. Registering the new stages at package import
    keeps old project model maps valid while allowing Factory Desk to choose
    independent models for creative layout, scene coding, and measured repairs.
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

    routes = {
        "graphics_layout": {
            **orchestrator.route(
                "codex", "gpt-5.6-sol", retries=0,
                fallback_provider="", fallback_model="",
            ),
            "reasoning_effort": "medium",
        },
        "graphics_coder": {
            **orchestrator.route(
                "codex", "gpt-5.6-sol", retries=0,
                fallback_provider="", fallback_model="",
            ),
            "reasoning_effort": "medium",
        },
        "graphics_code_repair": {
            **orchestrator.route(
                "codex", "gpt-5.6-sol", retries=0,
                fallback_provider="", fallback_model="",
            ),
            "reasoning_effort": "medium",
        },
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
