from __future__ import annotations


def test_factory_desk_and_cli_share_v3_graphics_planner():
    import shorts_factory.pipeline as pipeline
    import shorts_factory.ui  # applies the Factory Desk compatibility route
    from shorts_factory import cli
    from shorts_factory.editorial_v3 import generate_graphics_plan

    assert pipeline.generate_graphics_plan is generate_graphics_plan
    assert cli.generate_graphics_plan is generate_graphics_plan
