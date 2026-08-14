from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

from ..io import load_model, write_json
from ..models import DirectorPlan, EpisodeBrief, VoiceMetadata

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}


def _link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        destination.symlink_to(source.resolve())
    except OSError:
        shutil.copy2(source, destination)


def _visual_markup(scene: dict[str, Any], element_id: str) -> str:
    scene_type = scene["type"]
    title = html.escape(scene.get("purpose") or "")
    brief = html.escape(scene.get("visual_brief") or "")
    if scene_type == "motion_graphic" and scene["scene_id"] == "S02":
        return f'''<section id="{element_id}" class="clip scene graphic" data-start="{scene['start']:.6f}" data-duration="{scene['duration']:.6f}" data-track-index="10">
          <div class="eyebrow">ONE RECEIPT · THREE POSSIBLE JOBS</div>
          <div class="receipt-card">$483.67<br><span>Harbor Plumbing</span></div>
          <div class="branch-lines"><i></i><i></i><i></i></div>
          <div class="job-grid"><div>Riverside Villa</div><div>Downtown Office</div><div>Harbor Shop</div></div>
          <div class="big-question">?</div>
        </section>'''
    if scene_type == "diagram" and scene["scene_id"] == "S05":
        return f'''<section id="{element_id}" class="clip scene diagram" data-start="{scene['start']:.6f}" data-duration="{scene['duration']:.6f}" data-track-index="10">
          <div class="eyebrow">AI NEEDS BUSINESS CONTEXT</div>
          <div class="context-grid"><div>👷<b>Mike</b><span>crew member</span></div><div>📅<b>Riverside</b><span>today's schedule</span></div><div>🏪<b>Harbor</b><span>supplier history</span></div><div>🔧<b>Plumbing</b><span>items purchased</span></div></div>
          <div class="converge">↓</div><div class="confidence">94%<span>Riverside Villa</span></div>
        </section>'''
    if scene_type == "motion_graphic" and scene["scene_id"] == "S09":
        return f'''<section id="{element_id}" class="clip scene graphic" data-start="{scene['start']:.6f}" data-duration="{scene['duration']:.6f}" data-track-index="10">
          <div class="eyebrow">DIY PROTOTYPE</div><div class="stack"><div>WhatsApp / Telegram</div><b>→</b><div>n8n</div><b>→</b><div>Vision AI</div><b>→</b><div>Jobs Sheet</div></div>
          <div class="small-note">Start with sample data. Integrate the real systems only after you trust the decisions.</div>
        </section>'''
    return f'''<section id="{element_id}" class="clip scene graphic" data-start="{scene['start']:.6f}" data-duration="{scene['duration']:.6f}" data-track-index="10"><div class="eyebrow">{html.escape(scene_type.replace('_',' ').upper())}</div><div class="generic-title">{title}</div><div class="generic-copy">{brief}</div></section>'''


def _scene_markup(scene: dict[str, Any], index: int) -> str:
    element_id = f"scene-{index:03d}"
    start = scene["start"]
    duration = scene["duration"]
    media_file = html.escape(scene.get("media_file") or "")
    if media_file:
        suffix = Path(media_file).suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            cls = "talking" if scene["type"] in {"talking_head", "cta"} else "screen"
            return f'''<section id="{element_id}" class="clip scene media {cls}" data-start="{start:.6f}" data-duration="{duration:.6f}" data-track-index="10"><video src="assets/{media_file}" muted playsinline preload="auto" data-loop></video><div class="media-shade"></div></section>'''
        return f'''<section id="{element_id}" class="clip scene media" data-start="{start:.6f}" data-duration="{duration:.6f}" data-track-index="10"><img src="assets/{media_file}" alt="" /></section>'''
    if scene["type"] in {"talking_head", "cta"}:
        return f'''<section id="{element_id}" class="clip scene presenter-placeholder" data-start="{start:.6f}" data-duration="{duration:.6f}" data-track-index="10"><div class="silhouette">YOU</div><div class="presenter-note">Drop your real talking-head clip here<br><code>svf import-head ...</code></div></section>'''
    return _visual_markup(scene, element_id)


def build(project_dir: Path, *, preview: bool, width: int, height: int, fps: int = 30,
          window: tuple[float, float] | None = None, composition_name: str | None = None) -> Path:
    brief = load_model(project_dir / "00_input/episode_brief.json", EpisodeBrief)
    plan = load_model(project_dir / "03_director/director_plan.approved.json", DirectorPlan)
    duration = float(plan.duration_seconds)
    window_start, window_end = window or (0.0, duration)
    if not (0 <= window_start < window_end <= duration + 1e-6):
        raise ValueError(f"Invalid composition window {window_start}-{window_end}")

    root = project_dir / ("09_composition/preview" if preview else "09_composition/final")
    composition = root / composition_name if composition_name else root
    if composition.exists():
        shutil.rmtree(composition)
    assets_dir = composition / "assets"
    assets_dir.mkdir(parents=True)

    selected = [s for s in plan.scenes if s.end > window_start and s.start < window_end]
    entries: list[dict[str, Any]] = []
    for idx, scene in enumerate(selected, 1):
        if scene.start < window_start - 1e-6 or scene.end > window_end + 1e-6:
            raise ValueError(f"Render window splits {scene.scene_id}")
        asset_rel = scene.generated_asset or scene.source_asset
        media_file = ""
        if asset_rel:
            source = project_dir / asset_rel
            if source.exists():
                media_file = f"media-{idx:03d}{source.suffix.lower()}"
                _link_or_copy(source, assets_dir / media_file)
        item = scene.model_dump(mode="json")
        item.update({
            "start": float(scene.start - window_start), "end": float(scene.end - window_start),
            "duration": float(scene.end - scene.start), "media_file": media_file,
        })
        entries.append(item)

    voice_file = None
    voice_meta_path = project_dir / "02_voice/voice.json"
    if voice_meta_path.exists():
        voice = load_model(voice_meta_path, VoiceMetadata)
        source = project_dir / voice.audio_path
        if source.exists():
            voice_file = f"voice{source.suffix.lower()}"
            _link_or_copy(source, assets_dir / voice_file)

    manifest = {
        "episode_id": brief.episode_id, "title": brief.title, "width": width, "height": height,
        "fps": fps, "duration": float(window_end - window_start), "timeline_offset": window_start,
        "source_duration": duration, "entries": entries, "voice_file": voice_file, "preview": preview,
    }
    write_json(composition / "composition-manifest.json", manifest)
    (composition / "index.html").write_text(_html(manifest), encoding="utf-8")
    return composition / "index.html"


def _html(manifest: dict[str, Any]) -> str:
    entries_markup = "\n".join(_scene_markup(item, i) for i, item in enumerate(manifest["entries"], 1))
    entries_json = json.dumps([
        {"id": f"scene-{i:03d}", "start": e["start"], "end": e["end"], "type": e["type"], "caption": e.get("narration_excerpt", "")}
        for i, e in enumerate(manifest["entries"], 1)
    ], ensure_ascii=False)
    template = r'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--ink:#f6fbff;--muted:#a8bac9;--teal:#62e6c1;--navy:#07111c;--panel:#102232;--amber:#ffd166}
*{box-sizing:border-box}html,body{margin:0;background:#02060b;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;overflow:hidden}
#stage{position:relative;width:__WIDTH__px;height:__HEIGHT__px;overflow:hidden;background:radial-gradient(circle at 72% 10%,#13364c,var(--navy) 48%);transform-origin:top left}
.scene{position:absolute;inset:0;opacity:0;overflow:hidden}.media video,.media img{width:100%;height:100%;object-fit:cover}.screen video{object-fit:contain;background:#07111c;padding:80px 26px}.media-shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.05),transparent 50%,rgba(0,0,0,.28))}
.graphic,.diagram{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:100px 64px;text-align:center}.eyebrow{font-size:25px;font-weight:900;letter-spacing:.12em;color:var(--teal);margin-bottom:42px}.receipt-card{padding:28px 45px;border-radius:26px;background:#f4efe2;color:#1b2228;font-size:45px;font-weight:950;box-shadow:0 25px 70px rgba(0,0,0,.35)}.receipt-card span{font-size:21px;font-weight:650}.branch-lines{display:flex;width:72%;justify-content:space-between;margin:25px 0 -2px}.branch-lines i{height:80px;border-left:3px solid rgba(98,230,193,.65)}.job-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;width:100%}.job-grid div{padding:24px 12px;background:var(--panel);border:1px solid rgba(255,255,255,.1);border-radius:20px;font-size:22px;font-weight:800}.big-question{font-size:140px;color:var(--amber);font-weight:950;line-height:1}.context-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;width:100%}.context-grid div{padding:27px 18px;border-radius:24px;background:var(--panel);font-size:42px}.context-grid b{display:block;font-size:28px;margin-top:8px}.context-grid span{display:block;color:var(--muted);font-size:17px}.converge{font-size:68px;color:var(--teal)}.confidence{font-size:100px;font-weight:950;color:var(--teal)}.confidence span{display:block;font-size:28px;color:var(--ink)}.stack{display:flex;flex-direction:column;gap:13px;align-items:center;width:86%}.stack div{width:100%;padding:22px;border-radius:18px;background:var(--panel);font-size:26px;font-weight:850}.stack b{font-size:31px;color:var(--teal)}.small-note{color:var(--muted);font-size:21px;line-height:1.4;margin-top:34px}.generic-title{font-size:55px;font-weight:950;line-height:1.05}.generic-copy{font-size:26px;color:var(--muted);line-height:1.45;margin-top:25px}.presenter-placeholder{display:flex;align-items:center;justify-content:center;flex-direction:column;background:linear-gradient(135deg,#08131f,#173149)}.silhouette{width:430px;height:620px;border-radius:210px 210px 70px 70px;background:linear-gradient(180deg,#31536b,#142331);display:flex;align-items:center;justify-content:center;font-size:65px;font-weight:950;color:rgba(255,255,255,.35)}.presenter-note{margin-top:35px;text-align:center;color:var(--muted);font-size:21px;line-height:1.5}.presenter-note code{color:var(--teal)}#caption{position:absolute;z-index:80;left:7%;right:7%;bottom:7.5%;padding:18px 24px;border-radius:20px;background:rgba(2,7,12,.72);font-size:34px;font-weight:850;line-height:1.16;text-align:center;box-shadow:0 12px 50px rgba(0,0,0,.3)}#brand{position:absolute;z-index:81;top:3.3%;left:5%;font-size:17px;letter-spacing:.12em;font-weight:900;color:rgba(255,255,255,.58);text-transform:uppercase}#grain{position:absolute;inset:-20%;z-index:70;pointer-events:none;opacity:.035;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
</style></head><body>
<div id="stage" data-composition-id="ai-short" data-no-timeline data-start="0" data-duration="__DURATION__" data-width="__WIDTH__" data-height="__HEIGHT__" data-fps="__FPS__">
__ENTRIES__<div id="grain"></div><div id="brand">AI WORKFLOW CASE STUDY</div><div id="caption"></div></div>
<script>
const ENTRIES=__ENTRIES_JSON__;const caption=document.getElementById('caption');const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));const ease=v=>1-Math.pow(1-clamp(v),3);
function renderAt(t){let activeCaption='';for(const item of ENTRIES){const el=document.getElementById(item.id);if(!el)continue;const active=t>=item.start&&t<item.end;if(!active){el.style.opacity='0';continue}const d=Math.max(.001,item.end-item.start),p=(t-item.start)/d;const intro=ease(clamp(p/.10)),outro=ease(clamp((1-p)/.10));el.style.opacity=String(Math.min(intro,outro));activeCaption=item.caption||'';const graphic=el.classList.contains('graphic')||el.classList.contains('diagram');if(graphic){el.style.transform=`scale(${0.985+0.015*ease(p)})`}const vid=el.querySelector('video');if(vid){const local=Math.max(0,t-item.start);if(Number.isFinite(vid.duration)&&vid.duration>0.05){const wanted=Math.min(local,Math.max(0,vid.duration-.04));if(Math.abs((vid.currentTime||0)-wanted)>.12)vid.currentTime=wanted;}vid.pause();}}
caption.textContent=activeCaption;}window.addEventListener('hf-seek',e=>renderAt(Number(e.detail.time||0)));renderAt(0);window.__hf_ready__=true;
</script></body></html>'''
    for key, value in {
        "__WIDTH__": str(manifest["width"]), "__HEIGHT__": str(manifest["height"]),
        "__DURATION__": f"{manifest['duration']:.6f}", "__FPS__": str(manifest["fps"]),
        "__ENTRIES__": entries_markup, "__ENTRIES_JSON__": entries_json,
    }.items():
        template = template.replace(key, value)
    return template
