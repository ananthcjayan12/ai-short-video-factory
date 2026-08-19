from __future__ import annotations

import html
import json
import math
from pathlib import Path

from ..io import write_json
from ..models import GraphicsPlan
from .models import CustomGraphicsPackage, CustomGraphicsSceneBundle
from .validation import validate_custom_graphics_source


CUSTOM_GRAPHICS_STYLES = r'''
.custom-generated-graphic{--custom-paper:#f3eee1;--custom-paper-2:#fffaf0;--custom-ink:#171714;--custom-muted:#5c5a54;--custom-accent:#ef5b4c;--custom-secondary:#168c86;--custom-highlight:#f4c84a;position:absolute;inset:0;background:var(--custom-paper);color:var(--custom-ink);isolation:isolate;font-family:Inter,ui-sans-serif,system-ui,sans-serif}
.custom-generated-graphic .custom-graphic-content{position:absolute;inset:0;overflow:hidden}
.custom-generated-graphic[data-custom-theme="editorial"]{background:radial-gradient(circle at 86% 8%,color-mix(in srgb,var(--custom-accent) 15%,transparent),transparent 27%),linear-gradient(118deg,var(--custom-paper) 0 62%,color-mix(in srgb,var(--custom-highlight) 14%,var(--custom-paper)) 62% 78%,var(--custom-paper) 78%)}
.custom-generated-graphic[data-custom-theme="editorial"]::after{content:"";position:absolute;inset:-25%;z-index:90;pointer-events:none;opacity:.045;mix-blend-mode:multiply;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 160 160' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.82' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
.custom-generated-graphic[data-custom-theme="whiteboard"]{--custom-paper:#fffef8;--custom-paper-2:#fffdf4;--custom-ink:#26323a;--custom-muted:#5d6870;--custom-accent:#d94b3d;--custom-secondary:#2c64ad;--custom-highlight:#f4d35e;background-color:var(--custom-paper);background-image:linear-gradient(color-mix(in srgb,var(--custom-secondary) 6%,transparent) 1px,transparent 1px),linear-gradient(90deg,color-mix(in srgb,var(--custom-secondary) 6%,transparent) 1px,transparent 1px);background-size:42px 42px;font-family:"Chalkboard SE","Marker Felt","Segoe Print",Inter,sans-serif}
.custom-generated-graphic svg{overflow:visible}.custom-generated-graphic [data-custom-element]{position:absolute;transform-origin:center;will-change:transform,opacity}.custom-generated-graphic [data-custom-role="background"]{z-index:1}.custom-generated-graphic [data-custom-role="supporting"]{z-index:4}.custom-generated-graphic [data-custom-role="primary"]{z-index:6}.custom-generated-graphic [data-custom-role="annotation"]{z-index:8}
'''


CUSTOM_GRAPHICS_RUNTIME = r'''
const CUSTOM_GRAPHICS_HELPERS={
  clamp:(value,min=0,max=1)=>Math.max(min,Math.min(max,Number(value)||0)),
  ease:(value)=>{const p=Math.max(0,Math.min(1,Number(value)||0));return 1-Math.pow(1-p,3)},
  smooth:(value)=>{const p=Math.max(0,Math.min(1,Number(value)||0));return p*p*(3-2*p)},
  progress:(time,start,duration=.65)=>Math.max(0,Math.min(1,(Number(time)-Number(start))/Math.max(.001,Number(duration)))),
  setVisible:(element,value)=>{if(element)element.style.opacity=String(Math.max(0,Math.min(1,Number(value)||0)))},
  setTransform:(element,{x=0,y=0,scale=1,rotation=0}={})=>{if(element)element.style.transform=`translate(${x}px,${y}px) scale(${scale}) rotate(${rotation}deg)`},
  setDraw:(element,value)=>{if(!element)return;const length=Number(element.dataset.pathLength||element.getTotalLength?.()||600);element.dataset.pathLength=String(length);element.style.strokeDasharray=String(length);element.style.strokeDashoffset=String(length*(1-Math.max(0,Math.min(1,Number(value)||0))))},
  setText:(element,value)=>{if(element)element.textContent=String(value??'')},
};
window.__svfCustomFactories=window.__svfCustomFactories||{};window.__svfCustomRenderers=window.__svfCustomRenderers||{};
function initializeCustomGraphics(){
  document.querySelectorAll('.custom-generated-graphic[data-custom-scene]').forEach(scene=>{
    const sceneId=scene.dataset.customScene,factory=window.__svfCustomFactories[sceneId];if(typeof factory!=='function')return;
    let cues={};try{cues=JSON.parse(scene.dataset.customCues||'{}')}catch(error){}
    const render=factory({root:scene,cues,duration:Number(scene.dataset.customDuration||0),helpers:CUSTOM_GRAPHICS_HELPERS});
    if(typeof render==='function')window.__svfCustomRenderers[sceneId]=render;
  });
}
function renderCustomGraphicScene(scene,localTime,duration){
  const render=window.__svfCustomRenderers[scene.dataset.customScene];if(typeof render==='function')render(Math.max(0,Math.min(duration,Number(localTime)||0)));
}
'''


def _cue_payload(bundle: CustomGraphicsSceneBundle) -> dict[str, float]:
    return {action.cue_id: action.at_seconds for action in bundle.layout.actions}


def custom_scene_markup(
    bundle: CustomGraphicsSceneBundle,
    element_id: str,
    *,
    start: float,
    duration: float,
) -> str:
    validate_custom_graphics_source(bundle.layout, bundle.source)
    layout = bundle.layout
    cues = html.escape(json.dumps(_cue_payload(bundle), separators=(",", ":")), quote=True)
    track_duration = max(0.000001, duration - 0.0000001)
    return (
        f'<section id="{html.escape(element_id)}" class="clip scene graphic custom-generated-graphic" '
        f'data-scene-id="{html.escape(layout.scene_id)}" data-custom-scene="{html.escape(layout.scene_id)}" '
        f'data-custom-theme="{html.escape(layout.theme)}" data-custom-duration="{duration:.9f}" '
        f'data-custom-cues="{cues}" data-start="{start:.9f}" data-duration="{track_duration:.9f}" '
        f'data-track-index="10"><style>{bundle.source.css}</style>'
        f'<div class="custom-graphic-content">{bundle.source.html}</div></section>'
    )


def custom_factory_registration(bundle: CustomGraphicsSceneBundle) -> str:
    validate_custom_graphics_source(bundle.layout, bundle.source)
    scene_id = json.dumps(bundle.layout.scene_id)
    return (
        f'window.__svfCustomFactories[{scene_id}]=(()=>{{\n'
        f'{bundle.source.javascript}\n'
        'return initCustomGraphicScene;\n})();'
    )


def _frame_bounds(start: float, end: float, fps: int, *, final: bool = False) -> tuple[int, int]:
    start_frame = round(start * fps)
    end_frame = math.ceil(end * fps - 1e-9) if final else round(end * fps)
    return start_frame, max(start_frame + 1, end_frame)


def _standalone_html(
    bundles: list[CustomGraphicsSceneBundle],
    *,
    width: int,
    height: int,
    duration: float,
    fps: int,
) -> str:
    frame_windows = [
        _frame_bounds(bundle.layout.start, bundle.layout.end, fps, final=index == len(bundles) - 1)
        for index, bundle in enumerate(bundles)
    ]
    markup = "\n".join(
        custom_scene_markup(
            bundle,
            f"graphics-{index:03d}",
            start=start_frame / fps,
            duration=(end_frame - start_frame) / fps,
        )
        for index, (bundle, (start_frame, end_frame)) in enumerate(zip(bundles, frame_windows), 1)
    )
    registrations = "\n".join(custom_factory_registration(bundle) for bundle in bundles)
    scene_data = json.dumps([
        {
            "id": f"graphics-{index:03d}",
            "scene_id": bundle.layout.scene_id,
            "start": start_frame / fps,
            "end": end_frame / fps,
        }
        for index, (bundle, (start_frame, end_frame)) in enumerate(zip(bundles, frame_windows), 1)
    ], separators=(",", ":"))
    duration_frames = math.ceil(duration * fps - 1e-9)
    render_duration = duration_frames / fps
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:#171715;overflow:hidden}}#viewport{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:#171715}}#stage{{position:absolute;width:{width}px;height:{height}px;overflow:hidden;transform-origin:center center}}.scene{{position:absolute;inset:0;opacity:0}}#controls{{position:fixed;z-index:200;left:50%;bottom:18px;transform:translateX(-50%);display:flex;gap:10px;width:min(760px,calc(100vw - 28px));padding:10px;background:#181816;color:#f4f0e5}}#controls input{{flex:1}}body.render-mode #controls{{display:none}}{CUSTOM_GRAPHICS_STYLES}
</style></head><body><div id="viewport"><div id="stage" data-composition-id="custom-graphics" data-width="{width}" data-height="{height}" data-fps="{fps}" data-duration="{render_duration:.6f}">{markup}</div></div><div id="controls"><button id="toggle">Pause</button><input id="scrubber" type="range" min="0" max="{render_duration:.6f}" step="{1/fps:.6f}" value="0"><span id="time"></span></div><script>{CUSTOM_GRAPHICS_RUNTIME}
{registrations}
const CUSTOM_SCENES={scene_data};const stage=document.getElementById('stage'),scrubber=document.getElementById('scrubber'),timeLabel=document.getElementById('time');let playing=true,currentTime=0,previousFrame=performance.now();if(window.__hf||new URLSearchParams(location.search).get('render')==='1')document.body.classList.add('render-mode');
function scaleStage(){{const scale=Math.min(innerWidth/{width},innerHeight/{height})*(document.body.classList.contains('render-mode')?1:.94);stage.style.transform=`scale(${{scale}})`}}addEventListener('resize',scaleStage);scaleStage();initializeCustomGraphics();
function renderAt(time){{currentTime=Math.max(0,Math.min({render_duration:.6f},Number(time)||0));for(const item of CUSTOM_SCENES){{const scene=document.getElementById(item.id),active=currentTime>=item.start&&currentTime<item.end;scene.style.opacity=active?'1':'0';if(active)renderCustomGraphicScene(scene,currentTime-item.start,item.end-item.start)}}scrubber.value=String(currentTime);timeLabel.textContent=`${{currentTime.toFixed(1)}} / {render_duration:.1f}s`}}
function tick(now){{if(playing){{currentTime+=(now-previousFrame)/1000;if(currentTime>={render_duration:.6f})currentTime=0;renderAt(currentTime)}}previousFrame=now;requestAnimationFrame(tick)}}requestAnimationFrame(tick);document.getElementById('toggle').addEventListener('click',event=>{{playing=!playing;event.currentTarget.textContent=playing?'Pause':'Play'}});scrubber.addEventListener('input',()=>{{playing=false;renderAt(scrubber.value)}});window.__svfRenderAt=renderAt;addEventListener('hf-seek',event=>{{playing=false;renderAt(Number(event.detail.time||0))}});renderAt(0);window.__hf_ready__=true;</script></body></html>'''


def write_custom_graphics_package(
    project_dir: Path,
    package: CustomGraphicsPackage,
    summary: GraphicsPlan,
    *,
    width: int,
    height: int,
    fps: int,
) -> Path:
    root = project_dir / "08_graphics"
    scene_root = root / "scenes"
    source_root = root / "scene_sources"
    scene_root.mkdir(parents=True, exist_ok=True)
    source_root.mkdir(parents=True, exist_ok=True)
    write_json(root / "custom_graphics.json", package)
    write_json(root / "graphics_plan.json", summary)
    manifest_scenes = []
    for bundle in package.scenes:
        layout = bundle.layout
        validate_custom_graphics_source(layout, bundle.source)
        local_layout = layout.model_copy(update={"start": 0.0, "end": layout.end - layout.start})
        local_bundle = bundle.model_copy(update={"layout": local_layout})
        path = scene_root / f"{layout.scene_id}.html"
        path.write_text(
            _standalone_html(
                [local_bundle], width=width, height=height,
                duration=local_layout.end, fps=fps,
            ),
            encoding="utf-8",
        )
        bundle_root = source_root / layout.scene_id
        bundle_root.mkdir(parents=True, exist_ok=True)
        write_json(bundle_root / "layout.json", layout)
        write_json(bundle_root / "source.json", bundle.source)
        (bundle_root / "scene.html").write_text(bundle.source.html.rstrip() + "\n", encoding="utf-8")
        (bundle_root / "scene.css").write_text(bundle.source.css.rstrip() + "\n", encoding="utf-8")
        (bundle_root / "scene.js").write_text(bundle.source.javascript.rstrip() + "\n", encoding="utf-8")
        start_frame, end_frame = _frame_bounds(layout.start, layout.end, fps)
        manifest_scenes.append({
            "scene_id": layout.scene_id,
            "path": path.relative_to(project_dir).as_posix(),
            "source_path": (bundle_root / "source.json").relative_to(project_dir).as_posix(),
            "html_source": (bundle_root / "scene.html").relative_to(project_dir).as_posix(),
            "css_source": (bundle_root / "scene.css").relative_to(project_dir).as_posix(),
            "javascript_source": (bundle_root / "scene.js").relative_to(project_dir).as_posix(),
            "start": layout.start,
            "duration": layout.end - layout.start,
            "render_start_frame": start_frame,
            "render_end_frame": end_frame,
            "layout_variant": layout.layout_style,
            "engine_version": package.engine_version,
        })
    master = root / "master.html"
    master.write_text(
        _standalone_html(
            package.scenes, width=width, height=height,
            duration=package.duration_seconds, fps=fps,
        ),
        encoding="utf-8",
    )
    write_json(root / "graphics_manifest.json", {
        "episode_id": package.episode_id,
        "duration_seconds": package.duration_seconds,
        "theme": package.theme,
        "engine_version": package.engine_version,
        "fps": fps,
        "total_frames": math.ceil(package.duration_seconds * fps - 1e-9),
        "scene_count": len(package.scenes),
        "master": master.relative_to(project_dir).as_posix(),
        "scenes": manifest_scenes,
    })
    return master
