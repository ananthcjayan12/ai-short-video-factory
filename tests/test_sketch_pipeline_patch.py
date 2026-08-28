from __future__ import annotations


def test_public_graphics_entrypoints_use_sketch_pipeline():
    import shorts_factory  # noqa: F401 - package init installs the branch routing
    from shorts_factory import editorial_v3, pipeline
    from shorts_factory.sketch_graphics import generate_sketch_graphics_plan

    assert pipeline.generate_graphics_plan is generate_sketch_graphics_plan
    assert editorial_v3.generate_graphics_plan is generate_sketch_graphics_plan


def test_sketch_tasks_are_registered_for_factory_desk():
    import shorts_factory  # noqa: F401
    from shorts_factory.orchestrator import TASKS

    tasks = {task["id"]: task for task in TASKS}
    assert tasks["sketch_asset_planner"]["capability"] == "structured"
    assert tasks["sketch_imagegen"]["capability"] == "code"
