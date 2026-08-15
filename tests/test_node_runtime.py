from pathlib import Path

from shorts_factory import node_runtime


def _fake_node(path: Path, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho v{version}\n", encoding="utf-8")
    path.chmod(0o755)


def test_project_nvm_node_wins_over_old_system_node(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".nvmrc").write_text("22.12.0\n", encoding="utf-8")
    nvm_root = tmp_path / "nvm"
    expected = nvm_root / "versions/node/v22.12.0/bin/node"
    _fake_node(expected, "22.12.0")
    old_node = tmp_path / "old/bin/node"
    _fake_node(old_node, "16.14.0")
    monkeypatch.setattr(node_runtime, "PROJECT_ROOT", project)
    monkeypatch.setenv("NVM_DIR", str(nvm_root))
    monkeypatch.setenv("PATH", str(old_node.parent))
    monkeypatch.delenv("SVF_NODE_BIN", raising=False)

    selected = node_runtime.node_binary()
    environment = node_runtime.node_environment()

    assert selected == expected
    assert environment["PATH"].split(":", 1)[0] == str(expected.parent)
