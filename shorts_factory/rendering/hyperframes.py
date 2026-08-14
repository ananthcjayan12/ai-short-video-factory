from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..io import load_model, write_json
from ..models import DirectorPlan, VoiceMetadata
from .composition import build

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def binary() -> list[str]:
    explicit = os.getenv("SVF_HYPERFRAMES_BIN", "").strip()
    if explicit:
        return [explicit]
    global_bin = shutil.which("hyperframes")
    if global_bin:
        return [global_bin]
    local = PROJECT_ROOT / "node_modules/.bin/hyperframes"
    if local.exists():
        return [str(local)]
    npx = shutil.which("npx")
    if npx:
        return [npx, "hyperframes"]
    raise RuntimeError("HyperFrames missing. Run npm install and npm run doctor.")


def validate(project_dir: Path, *, preview: bool, width: int, height: int) -> dict[str, Any]:
    composition = build(project_dir, preview=preview, width=width, height=height)
    result = subprocess.run([*binary(), "lint", ".", "--json"], cwd=composition.parent,
                            capture_output=True, text=True, timeout=600)
    report = {"returncode": result.returncode, "stdout": result.stdout[-12000:], "stderr": result.stderr[-12000:]}
    if result.returncode != 0:
        raise RuntimeError(f"HyperFrames lint failed: {(result.stderr or result.stdout)[-4000:]}")
    return report


def chunk_windows(plan: DirectorPlan, max_seconds: float = 30.0) -> list[tuple[float, float]]:
    scenes = sorted(plan.scenes, key=lambda s: (s.start, s.end))
    if not scenes:
        return [(0.0, plan.duration_seconds)]
    windows: list[tuple[float, float]] = []
    start = 0.0
    previous_end = 0.0
    for scene in scenes:
        end = float(scene.end)
        if previous_end > start and end - start > max_seconds:
            windows.append((start, previous_end))
            start = previous_end
        previous_end = max(previous_end, end)
    previous_end = max(previous_end, float(plan.duration_seconds))
    if previous_end > start:
        windows.append((start, previous_end))
    return windows


def _valid_video(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1024:
        return False
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, timeout=60)
    return r.returncode == 0 and bool(r.stdout.strip())


def _render_one(composition: Path, output: Path) -> None:
    result = subprocess.run([*binary(), "render", "-c", composition.name, "-o", str(output.resolve())],
                            cwd=composition.parent, capture_output=True, text=True, timeout=14400)
    output.with_suffix(".render.log").write_text((result.stdout or "") + "\n" + (result.stderr or ""), encoding="utf-8")
    if result.returncode != 0 or not output.exists():
        raise RuntimeError(f"HyperFrames render failed: {(result.stderr or result.stdout)[-5000:]}")


def _concat(chunks: list[Path], output: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        if len(chunks) == 1:
            shutil.copy2(chunks[0], output)
            return
        raise RuntimeError("FFmpeg required for multi-chunk render")
    manifest = output.parent / f"{output.stem}.chunks.ffconcat"
    manifest.write_text("ffconcat version 1.0\n" + "\n".join(f"file '{p.resolve().as_posix()}'" for p in chunks) + "\n", encoding="utf-8")
    r = subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", str(output)], capture_output=True, text=True, timeout=3600)
    (output.parent / "hyperframes-concat.log").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"concat failed: {(r.stderr or r.stdout)[-4000:]}")


def render(project_dir: Path, *, preview: bool, width: int, height: int, output: Path) -> dict[str, Any]:
    plan = load_model(project_dir / "03_director/director_plan.approved.json", DirectorPlan)
    output.parent.mkdir(parents=True, exist_ok=True)
    lint = validate(project_dir, preview=preview, width=width, height=height)
    (output.parent / "hyperframes-lint.log").write_text((lint.get("stdout") or "") + "\n" + (lint.get("stderr") or ""), encoding="utf-8")
    windows = chunk_windows(plan, float(os.getenv("SVF_HYPERFRAMES_CHUNK_SECONDS", "30")))
    chunk_root = output.parent / f"{output.stem}.chunks"
    chunk_root.mkdir(parents=True, exist_ok=True)
    chunks: list[Path] = []
    report_windows = []
    for i, window in enumerate(windows, 1):
        chunk = chunk_root / f"part-{i:03d}.mp4"
        chunks.append(chunk)
        if _valid_video(chunk):
            report_windows.append({"index": i, "window": window, "status": "resumed", "path": str(chunk)})
            continue
        composition = build(project_dir, preview=preview, width=width, height=height, window=window, composition_name=f"chunks/part-{i:03d}")
        _render_one(composition, chunk)
        report_windows.append({"index": i, "window": window, "status": "rendered", "path": str(chunk)})
    video_only = output.parent / f"{output.stem}.video.mp4"
    _concat(chunks, video_only)

    voice_meta = project_dir / "02_voice/voice.json"
    ffmpeg = shutil.which("ffmpeg")
    if voice_meta.exists() and ffmpeg:
        voice = load_model(voice_meta, VoiceMetadata)
        voice_path = project_dir / voice.audio_path
        r = subprocess.run([ffmpeg, "-y", "-i", str(video_only), "-i", str(voice_path), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(output)], capture_output=True, text=True, timeout=1800)
        (output.parent / "hyperframes-mux.log").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
        if r.returncode != 0:
            raise RuntimeError(f"voice mux failed: {(r.stderr or r.stdout)[-4000:]}")
    else:
        shutil.copy2(video_only, output)

    report = {"renderer": "hyperframes", "output": str(output), "windows": report_windows}
    write_json(output.parent / "hyperframes-render-report.json", report)
    return report
