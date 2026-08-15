from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIN_NODE_MAJOR = 22


def _node_major(binary: Path) -> int | None:
    try:
        result = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=10,
        )
        value = result.stdout.strip().lstrip("v").split(".", 1)[0]
        return int(value) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def node_binary(*, minimum_major: int = MIN_NODE_MAJOR) -> Path:
    candidates: list[Path] = []
    explicit = os.getenv("SVF_NODE_BIN", "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())

    version_file = PROJECT_ROOT / ".nvmrc"
    version = version_file.read_text(encoding="utf-8").strip().lstrip("v") if version_file.is_file() else ""
    nvm_root = Path(os.getenv("NVM_DIR", str(Path.home() / ".nvm"))).expanduser()
    if version:
        candidates.append(nvm_root / "versions/node" / f"v{version}" / "bin/node")

    discovered = shutil.which("node")
    if discovered:
        candidates.append(Path(discovered))
    candidates.extend(sorted((nvm_root / "versions/node").glob("v*/bin/node"), reverse=True))

    checked: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve() if candidate.exists() else candidate
        if resolved in checked:
            continue
        checked.add(resolved)
        major = _node_major(candidate) if candidate.is_file() else None
        if major is not None and major >= minimum_major:
            return candidate
    raise RuntimeError(
        f"Node.js >= {minimum_major} is required. Install the .nvmrc version or set SVF_NODE_BIN."
    )


def node_environment(*, minimum_major: int = MIN_NODE_MAJOR) -> dict[str, str]:
    binary = node_binary(minimum_major=minimum_major)
    environment = os.environ.copy()
    current_path = environment.get("PATH", "")
    environment["PATH"] = str(binary.parent) + (os.pathsep + current_path if current_path else "")
    environment["SVF_NODE_BIN"] = str(binary)
    return environment
