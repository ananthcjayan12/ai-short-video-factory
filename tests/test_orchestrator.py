import pytest
from shorts_factory.orchestrator import default_config, resolve_task


def test_capability_route_is_explicit():
    cfg = default_config()
    route = resolve_task(cfg, "director")
    assert route["capability"] == "structured"
    assert route["provider"] == "claude_code"


def test_invalid_capability_route_fails():
    cfg = default_config()
    cfg["tasks"]["screen_recorder"]["provider"] = "codex"
    with pytest.raises(ValueError):
        resolve_task(cfg, "screen_recorder")
