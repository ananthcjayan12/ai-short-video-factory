from __future__ import annotations

import html
import json
import math
import shutil
from pathlib import Path
from typing import Any

from ..io import load_model, write_json
from ..models import DirectorPlan, EpisodeBrief, GraphicsPlan, GraphicsScenePlan, GraphicsTheme, VoiceMetadata
from .graphics import GRAPHICS_RUNTIME, GRAPHICS_STYLES, graphic_markup

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}


def _link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        destination.symlink_to(source.resolve())
    except OSError:
        shutil.copy2(source, destination)


def _visual_markup(
    scene: dict[str, Any], element_id: str, graphics_scene: GraphicsScenePlan | None = None,
    graphics_theme: GraphicsTheme = "editorial",
) -> str:
    if graphics_scene:
        return graphic_markup(
            graphics_scene, element_id, start=float(scene["start"]), duration=float(scene["duration"]),
            theme=graphics_theme,
        )
    scene_type = scene["type"]
    track_start = float(scene["start"])
    track_duration = float(scene.get("track_duration", scene["duration"]))
    title = html.escape(scene.get("purpose") or "")
    brief = html.escape(scene.get("visual_brief") or "")
    if scene_type == "motion_graphic" and scene["scene_id"] == "S02":
        return f'''<section id="{element_id}" class="clip scene graphic" data-start="{track_start:.9f}" data-duration="{track_duration:.9f}" data-track-index="10">
          <div class="eyebrow">ONE RECEIPT · THREE POSSIBLE JOBS</div>
          <div class="receipt-card">$483.67<br><span>Harbor Plumbing</span></div>
          <div class="branch-lines"><i></i><i></i><i></i></div>
          <div class="job-grid"><div>Riverside Villa</div><div>Downtown Office</div><div>Harbor Shop</div></div>
          <div class="big-question">?</div>
        </section>'''
    if scene_type == "diagram" and scene["scene_id"] == "S05":
        return f'''<section id="{element_id}" class="clip scene diagram" data-start="{track_start:.9f}" data-duration="{track_duration:.9f}" data-track-index="10">
          <div class="eyebrow">AI NEEDS BUSINESS CONTEXT</div>
          <div class="context-grid"><div>👷<b>Mike</b><span>crew member</span></div><div>📅<b>Riverside</b><span>today's schedule</span></div><div>🏪<b>Harbor</b><span>supplier history</span></div><div>🔧<b>Plumbing</b><span>items purchased</span></div></div>
          <div class="converge">↓</div><div class="confidence">94%<span>Riverside Villa</span></div>
        </section>'''
    if scene_type == "motion_graphic" and scene["scene_id"] == "S09":
        return f'''<section id="{element_id}" class="clip scene graphic" data-start="{track_start:.9f}" data-duration="{track_duration:.9f}" data-track-index="10">
          <div class="eyebrow">DIY PROTOTYPE</div><div class="stack"><div>WhatsApp / Telegram</div><b>→</b><div>n8n</div><b>→</b><div>Vision AI</div><b>→</b><div>Jobs Sheet</div></div>
          <div class="small-note">Start with sample data. Integrate the real systems only after you trust the decisions.</div>
        </section>'''
    return f'''<section id="{element_id}" class="clip scene graphic" data-start="{track_start:.9f}" data-duration="{track_duration:.9f}" data-track-index="10"><div class="eyebrow">{html.escape(scene_type.replace('_',' ').upper())}</div><div class="generic-title">{title}</div><div class="generic-copy">{brief}</div></section>'''


def _scene_markup(
    scene: dict[str, Any], index: int, graphics_scene: GraphicsScenePlan | None = None,
    graphics_theme: GraphicsTheme = "editorial",
) -> str:
    element_id = f"scene-{index:03d}"
    start = scene["start"]
    duration = scene.get("track_duration", scene["duration"])
    media_file = html.escape(scene.get("media_file") or "")
    if media_file:
        suffix = Path(media_file).suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            cls = "talking" if scene["type"] in {"talking_head", "cta"} else "screen"
            return f'''<video id="{element_id}" class="clip scene media {cls}" src="assets/{media_file}" muted playsinline preload="auto" data-start="{start:.9f}" data-duration="{duration:.9f}" data-track-index="10" data-loop></video>'''
        return f'''<section id="{element_id}" class="clip scene media" data-start="{start:.9f}" data-duration="{duration:.9f}" data-track-index="10"><img src="assets/{media_file}" alt="" /></section>'''
    if scene["type"] in {"talking_head", "cta"}:
        return f'''<section id="{element_id}" class="clip scene presenter-placeholder" data-start="{start:.9f}" data-duration="{duration:.9f}" data-track-index="10"><div class="silhouette">YOU</div><div class="presenter-note">Drop your real talking-head clip here<br><code>svf import-head ...</code></div></section>'''
    return _visual_markup(scene, element_id, graphics_scene, graphics_theme)


def build(project_dir: Path, *, preview: bool, width: int, height: int, fps: int = 60,
          window: tuple[float, float] | None = None, composition_name: str | None = None) -> Path:
    brief = load_model(project_dir / "00_input/episode_brief.json", EpisodeBrief)
    plan = load_model(project_dir / "03_director/director_plan.approved.json", DirectorPlan)
    graphics_path = project_dir / "08_graphics/graphics_plan.json"
    graphics = load_model(graphics_path, GraphicsPlan) if graphics_path.is_file() else None
    graphics_by_scene = {scene.scene_id: scene for scene in graphics.scenes} if graphics else {}
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

    window_start_frame = round(window_start * fps)
    window_end_frame = (
        math.ceil(window_end * fps - 1e-9)
        if abs(window_end - duration) <= 1e-6 else round(window_end * fps)
    )
    window_end_frame = max(window_start_frame + 1, window_end_frame)
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
        absolute_start_frame = round(scene.start * fps)
        absolute_end_frame = (
            math.ceil(scene.end * fps - 1e-9)
            if abs(scene.end - duration) <= 1e-6 else round(scene.end * fps)
        )
        absolute_end_frame = max(absolute_start_frame + 1, absolute_end_frame)
        start_frame = absolute_start_frame - window_start_frame
        end_frame = absolute_end_frame - window_start_frame
        item = scene.model_dump(mode="json")
        item.update({
            "start": start_frame / fps, "end": end_frame / fps,
            "duration": (end_frame - start_frame) / fps, "media_file": media_file,
            "track_duration": max(0.000001, (end_frame - start_frame) / fps - 0.0000001),
            "render_start_frame": start_frame, "render_end_frame": end_frame,
            "absolute_start_frame": absolute_start_frame, "absolute_end_frame": absolute_end_frame,
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
        "fps": fps, "duration": (window_end_frame - window_start_frame) / fps,
        "duration_frames": window_end_frame - window_start_frame,
        "timeline_offset": window_start_frame / fps, "timeline_offset_frame": window_start_frame,
        "source_duration": duration, "entries": entries, "voice_file": voice_file, "preview": preview,
        "graphics_theme": graphics.theme if graphics else brief.graphics_theme,
        "graphics_scenes": {
            scene_id: value.model_dump(mode="json") for scene_id, value in graphics_by_scene.items()
        },
    }
    write_json(composition / "composition-manifest.json", manifest)
    (composition / "index.html").write_text(_html(manifest), encoding="utf-8")
    return composition / "index.html"


def _html(manifest: dict[str, Any]) -> str:
    graphics_by_scene = {
        scene_id: GraphicsScenePlan.model_validate(value)
        for scene_id, value in manifest.get("graphics_scenes", {}).items()
    }
    entries_markup = "\n".join(
        _scene_markup(
            item, i, graphics_by_scene.get(item["scene_id"]),
            manifest.get("graphics_theme", "editorial"),
        )
        for i, item in enumerate(manifest["entries"], 1)
    )
    entries_json = json.dumps([
        {
            "id": f"scene-{i:03d}", "scene_id": e["scene_id"], "start": e["start"], "end": e["end"],
            "type": e["type"], "caption": e.get("narration_excerpt", ""), "purpose": e.get("purpose", ""),
        }
        for i, e in enumerate(manifest["entries"], 1)
    ], ensure_ascii=False)
    audio_markup = (
        f'<audio id="master-audio" preload="auto" src="assets/{html.escape(manifest["voice_file"])}" '
        f'data-start="0" data-duration="{manifest["duration"]:.6f}" data-track-index="1"></audio>'
        if manifest.get("voice_file") else ""
    )
    template = r'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--ink:#f6fbff;--muted:#a8bac9;--teal:#62e6c1;--navy:#07111c;--panel:#102232;--amber:#ffd166;--control:#181816;--control-paper:#f4f0e5;--control-coral:#ef5b4c}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:#171715;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;overflow:hidden}body{display:flex;align-items:center;justify-content:center;background:repeating-linear-gradient(135deg,#171715,#171715 20px,#1d1d1a 20px,#1d1d1a 40px)}
#stage{position:relative;flex:0 0 auto;width:__WIDTH__px;height:__HEIGHT__px;overflow:hidden;background:radial-gradient(circle at 72% 10%,#13364c,var(--navy) 48%);transform-origin:center center;box-shadow:0 35px 120px rgba(0,0,0,.55)}
.scene{position:absolute;inset:0;opacity:0;overflow:hidden}.media video,.media img,video.media,img.media{width:100%;height:100%;object-fit:cover}.screen video,video.screen{object-fit:contain;background:#07111c;padding:80px 26px}.media-shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.05),transparent 50%,rgba(0,0,0,.28))}
.graphic,.diagram{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:100px 64px;text-align:center}.eyebrow{font-size:25px;font-weight:900;letter-spacing:.12em;color:var(--teal);margin-bottom:42px}.receipt-card{padding:28px 45px;border-radius:26px;background:#f4efe2;color:#1b2228;font-size:45px;font-weight:950;box-shadow:0 25px 70px rgba(0,0,0,.35)}.receipt-card span{font-size:21px;font-weight:650}.branch-lines{display:flex;width:72%;justify-content:space-between;margin:25px 0 -2px}.branch-lines i{height:80px;border-left:3px solid rgba(98,230,193,.65)}.job-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;width:100%}.job-grid div{padding:24px 12px;background:var(--panel);border:1px solid rgba(255,255,255,.1);border-radius:20px;font-size:22px;font-weight:800}.big-question{font-size:140px;color:var(--amber);font-weight:950;line-height:1}.context-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;width:100%}.context-grid div{padding:27px 18px;border-radius:24px;background:var(--panel);font-size:42px}.context-grid b{display:block;font-size:28px;margin-top:8px}.context-grid span{display:block;color:var(--muted);font-size:17px}.converge{font-size:68px;color:var(--teal)}.confidence{font-size:100px;font-weight:950;color:var(--teal)}.confidence span{display:block;font-size:28px;color:var(--ink)}.stack{display:flex;flex-direction:column;gap:13px;align-items:center;width:86%}.stack div{width:100%;padding:22px;border-radius:18px;background:var(--panel);font-size:26px;font-weight:850}.stack b{font-size:31px;color:var(--teal)}.small-note{color:var(--muted);font-size:21px;line-height:1.4;margin-top:34px}.generic-title{font-size:55px;font-weight:950;line-height:1.05}.generic-copy{font-size:26px;color:var(--muted);line-height:1.45;margin-top:25px}.presenter-placeholder{display:flex;align-items:center;justify-content:center;flex-direction:column;background:linear-gradient(135deg,#08131f,#173149)}.silhouette{width:430px;height:620px;border-radius:210px 210px 70px 70px;background:linear-gradient(180deg,#31536b,#142331);display:flex;align-items:center;justify-content:center;font-size:65px;font-weight:950;color:rgba(255,255,255,.35)}.presenter-note{margin-top:35px;text-align:center;color:var(--muted);font-size:21px;line-height:1.5}.presenter-note code{color:var(--teal)}#caption{position:absolute;z-index:80;left:6.4%;right:6.4%;bottom:4.8%;padding:14px 18px;background:rgba(15,15,14,.82);font-size:29px;font-weight:850;line-height:1.14;text-align:left;border-left:8px solid #ef5b4c;box-shadow:0 12px 42px rgba(0,0,0,.24)}#brand{position:absolute;z-index:81;top:2.4%;right:4.5%;font-size:14px;letter-spacing:.16em;font-weight:900;color:rgba(255,255,255,.62);text-transform:uppercase}#grain{position:absolute;inset:-20%;z-index:70;pointer-events:none;opacity:.035;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
#timeline-controls{position:fixed;z-index:200;left:50%;bottom:16px;transform:translateX(-50%);width:min(980px,calc(100vw - 28px));padding:12px;background:rgba(24,24,22,.94);border:1px solid rgba(255,255,255,.16);border-radius:8px;color:var(--control-paper);box-shadow:0 20px 70px rgba(0,0,0,.42);backdrop-filter:blur(18px)}.control-row{display:flex;align-items:center;gap:9px}.control-row button{border:1px solid rgba(255,255,255,.2);border-radius:5px;padding:8px 11px;background:var(--control-paper);color:var(--control);font:900 13px/1 Inter,system-ui,sans-serif;cursor:pointer}.control-row input{flex:1;min-width:100px;accent-color:var(--control-coral)}#timeline-time{min-width:104px;text-align:right;font-size:13px;font-variant-numeric:tabular-nums}.scene-rail{display:flex;height:31px;margin-top:10px;overflow:hidden;border-radius:4px;background:#2a2a27}.scene-jump{position:relative;min-width:14px;border:0;border-right:1px solid rgba(255,255,255,.28);background:#3d3d38;color:transparent;cursor:pointer;overflow:hidden}.scene-jump[data-type="screen_recording"]{background:#168c86}.scene-jump[data-type="diagram"]{background:#2468c9}.scene-jump[data-type="motion_graphic"]{background:#ef5b4c}.render-mode #timeline-controls{display:none}.render-mode{background:#000}.render-mode #stage{box-shadow:none}
__GRAPHICS_STYLES__
</style></head><body>
<div id="stage" data-composition-id="ai-short" data-no-timeline data-start="0" data-duration="__DURATION__" data-width="__WIDTH__" data-height="__HEIGHT__" data-fps="__FPS__">
__ENTRIES__<div id="grain"></div><div id="brand">AI WORKFLOW CASE STUDY</div><div id="caption"></div></div>
__AUDIO__
  <div id="timeline-controls"><div class="control-row"><button id="timeline-toggle" type="button">Play</button><button id="timeline-restart" type="button">Restart</button><input id="timeline-seek" type="range" min="0" max="__DURATION__" step="__FRAME_SECONDS__" value="0"><span id="timeline-time">0.0 / __DURATION_SHORT__s</span><button id="timeline-mute" type="button">Mute</button></div><div id="scene-rail" class="scene-rail"></div></div>
<script>
__GRAPHICS_RUNTIME__
const ENTRIES=__ENTRIES_JSON__,DURATION=__DURATION__;const stage=document.getElementById('stage'),caption=document.getElementById('caption'),audio=document.getElementById('master-audio'),seek=document.getElementById('timeline-seek'),timeLabel=document.getElementById('timeline-time'),toggle=document.getElementById('timeline-toggle'),rail=document.getElementById('scene-rail');const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));const ease=v=>1-Math.pow(1-clamp(v),3);let currentTime=0,playing=false;
const renderMode=Boolean(window.__hf)||new URLSearchParams(location.search).get('render')==='1';if(renderMode)document.body.classList.add('render-mode');
function scaleStage(){stage.style.transform=renderMode?'none':`scale(${Math.min(innerWidth/__WIDTH__,innerHeight/__HEIGHT__)*.88})`;}window.addEventListener('resize',scaleStage);scaleStage();
function renderAt(t){currentTime=clamp(Number(t)||0,0,DURATION);let activeCaption='';for(const item of ENTRIES){const el=document.getElementById(item.id);if(!el)continue;const active=currentTime>=item.start&&currentTime<item.end;if(!active){el.style.opacity='0';continue}const d=Math.max(.001,item.end-item.start),p=(currentTime-item.start)/d;const intro=ease(clamp(p/.055)),outro=ease(clamp((1-p)/.055));el.style.opacity=String(outro);el.style.clipPath=`inset(0 ${Math.max(0,(1-intro)*8)}% 0 0)`;activeCaption=item.caption||'';const graphic=el.classList.contains('graphic')||el.classList.contains('diagram');if(graphic&&!el.classList.contains('generated-graphic'))el.style.transform=`scale(${.985+.015*ease(p)})`;if(el.classList.contains('generated-graphic'))renderGeneratedGraphic(el,Math.max(0,currentTime-item.start),d);const vid=el.matches('video')?el:el.querySelector('video');if(vid){const local=Math.max(0,currentTime-item.start);if(Number.isFinite(vid.duration)&&vid.duration>.05){const wanted=Math.min(local,Math.max(0,vid.duration-.04));if(Math.abs((vid.currentTime||0)-wanted)>.08)vid.currentTime=wanted;}vid.pause();}}caption.textContent=activeCaption;seek.value=String(currentTime);timeLabel.textContent=`${currentTime.toFixed(1)} / ${DURATION.toFixed(1)}s`;}
function setPlaying(next){playing=Boolean(next&&audio);toggle.textContent=playing?'Pause':'Play';if(audio){if(playing){audio.currentTime=currentTime;audio.play().catch(()=>{playing=false;toggle.textContent='Play';});}else audio.pause();}}
toggle.addEventListener('click',()=>setPlaying(!playing));document.getElementById('timeline-restart').addEventListener('click',()=>{renderAt(0);if(audio)audio.currentTime=0;setPlaying(true);});seek.addEventListener('input',()=>{setPlaying(false);renderAt(seek.value);if(audio)audio.currentTime=currentTime;});document.getElementById('timeline-mute').addEventListener('click',event=>{if(!audio)return;audio.muted=!audio.muted;event.currentTarget.textContent=audio.muted?'Unmute':'Mute';});
for(const item of ENTRIES){const button=document.createElement('button');button.type='button';button.className='scene-jump';button.style.flexGrow=String(Math.max(.1,item.end-item.start));button.dataset.type=item.type;button.dataset.label=`${item.scene_id} · ${item.purpose}`;button.title=button.dataset.label;button.addEventListener('click',()=>{setPlaying(false);renderAt(Math.min(item.end-.01,item.start+.35));if(audio)audio.currentTime=currentTime;});rail.appendChild(button);}
  const schedulePreviewFrame=renderMode?null:window['requestAnimation'+'Frame']?.bind(window);function playbackFrame(){if(playing&&audio&&!audio.paused)renderAt(audio.currentTime);schedulePreviewFrame?.(playbackFrame);}schedulePreviewFrame?.(playbackFrame);
  audio?.addEventListener('timeupdate',()=>{if(!audio.paused)renderAt(audio.currentTime);});audio?.addEventListener('ended',()=>{playing=false;toggle.textContent='Play';renderAt(DURATION);});
  window.__svfRenderAt=renderAt;window.addEventListener('hf-seek',event=>{setPlaying(false);renderAt(Number(event.detail.time||0));});renderAt(0);window.__hf_ready__=true;
</script></body></html>'''
    for key, value in {
        "__WIDTH__": str(manifest["width"]), "__HEIGHT__": str(manifest["height"]),
        "__DURATION__": f"{manifest['duration']:.6f}", "__FPS__": str(manifest["fps"]),
        "__FRAME_SECONDS__": f"{1 / manifest['fps']:.6f}",
        "__DURATION_SHORT__": f"{manifest['duration']:.1f}", "__AUDIO__": audio_markup,
        "__ENTRIES__": entries_markup, "__ENTRIES_JSON__": entries_json,
        "__GRAPHICS_STYLES__": GRAPHICS_STYLES, "__GRAPHICS_RUNTIME__": GRAPHICS_RUNTIME,
    }.items():
        template = template.replace(key, value)
    return template
