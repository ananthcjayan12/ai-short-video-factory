from __future__ import annotations

import html
import json
from pathlib import Path

from ..io import write_json
from ..models import GraphicsPlan, GraphicsScenePlan


# Editorial primitives are deliberately shared by the inspectable graphics package and
# the final composition. Objects retain their semantic type instead of becoming a grid
# of interchangeable UI cards.
GRAPHICS_STYLES = r'''
.generated-graphic{--paper:#f4f0e5;--paper-2:#e8e1d1;--ink:#151513;--muted-ink:#5d5b54;--coral:#ef5b4c;--yellow:#f4c84a;--teal:#168c86;--blue:#2468c9;display:block;background:var(--paper);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,sans-serif;isolation:isolate}
.generated-graphic::before{content:"";position:absolute;inset:0;z-index:-2;background:linear-gradient(115deg,transparent 0 54%,color-mix(in srgb,var(--yellow) 15%,transparent) 54% 70%,transparent 70%),radial-gradient(circle at 84% 10%,color-mix(in srgb,var(--coral) 18%,transparent),transparent 32%)}
.generated-graphic::after{content:"";position:absolute;inset:-30%;z-index:50;pointer-events:none;opacity:.055;mix-blend-mode:multiply;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 160 160' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.82' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
.graphics-heading{position:absolute;z-index:20;left:6.4%;right:6.4%;top:5.1%;border-top:8px solid var(--ink);padding-top:25px}.graphics-heading::after{content:"";display:block;width:86px;height:8px;background:var(--coral);margin-top:25px}.graphics-kicker{font-size:17px;font-weight:900;letter-spacing:.16em;text-transform:uppercase;color:var(--coral)}.graphics-headline{font-size:76px;line-height:.91;margin:15px 0 0;max-width:930px;font-weight:950;letter-spacing:-.065em;text-transform:uppercase;text-wrap:balance}.graphics-support{font-size:24px;line-height:1.22;color:var(--muted-ink);max-width:860px;margin:17px 0 0;font-weight:700;letter-spacing:.01em}
.graphics-stage{position:absolute;z-index:5;left:5.6%;right:5.6%;top:32%;bottom:10.5%;overflow:hidden}.graphics-stage::before{content:"";position:absolute;inset:2% 1%;border:1px solid color-mix(in srgb,var(--ink) 11%,transparent);pointer-events:none}.graphics-connections{position:absolute;inset:0;width:100%;height:100%;z-index:1;overflow:visible}.graphics-connection{stroke:var(--ink);stroke-width:4;fill:none;stroke-linecap:round;stroke-dasharray:14 12;opacity:.78;vector-effect:non-scaling-stroke}.graphics-connection-arrow{fill:var(--ink)}
.graphics-object{--accent:var(--teal);position:absolute;z-index:3;opacity:0;transform-origin:center;will-change:transform,opacity;max-width:44%;color:var(--ink)}.graphics-object[data-object-type="document"]{--accent:var(--yellow)}.graphics-object[data-object-type="decision"],.graphics-object[data-object-type="status"]{--accent:var(--coral)}.graphics-object[data-object-type="database"]{--accent:var(--blue)}.graphics-object[data-object-type="annotation"]{--accent:var(--coral)}
.graphics-object .object-shape{position:relative;min-width:190px;min-height:118px;display:flex;flex-direction:column;justify-content:center}.graphics-object strong{display:block;font-size:30px;line-height:1.02;font-weight:950;letter-spacing:-.035em;text-transform:uppercase}.graphics-object span{display:block;font-size:17px;line-height:1.24;color:var(--muted-ink);font-weight:650;margin-top:10px;max-width:300px}.graphics-object .object-index{position:absolute;font-size:13px;line-height:1;font-weight:950;color:var(--accent);letter-spacing:.08em;top:-21px;left:0}
.graphics-object[data-object-type="channel"] .object-shape{width:190px;height:190px;min-width:190px;min-height:190px;border:5px solid var(--ink);border-radius:50%;padding:29px;text-align:center;align-items:center;background:var(--paper)}.graphics-object[data-object-type="channel"] .object-shape::after{content:"";position:absolute;width:20px;height:20px;border-radius:50%;background:var(--accent);right:2px;top:19px;border:4px solid var(--paper)}.graphics-object[data-object-type="channel"] span{font-size:14px;margin-top:7px}
.graphics-object[data-object-type="document"] .object-shape{width:250px;min-height:176px;padding:36px 27px 24px;background:#fffdf7;border:3px solid var(--ink);box-shadow:12px 14px 0 color-mix(in srgb,var(--ink) 14%,transparent);transform:rotate(-2deg)}.graphics-object[data-object-type="document"] .object-shape::before{content:"";position:absolute;left:27px;right:27px;top:20px;height:5px;background:var(--accent);box-shadow:0 10px 0 color-mix(in srgb,var(--ink) 14%,transparent)}
.graphics-object[data-object-type="process"] .object-shape{min-width:250px;padding:27px 31px;border:4px solid var(--ink);border-radius:999px;background:var(--accent);box-shadow:9px 10px 0 var(--ink)}.graphics-object[data-object-type="process"] span{color:color-mix(in srgb,var(--ink) 72%,transparent)}
.graphics-object[data-object-type="decision"] .object-shape{width:210px;height:210px;min-height:210px;padding:42px;transform:rotate(45deg);border:5px solid var(--ink);background:var(--yellow);text-align:center}.graphics-object[data-object-type="decision"] .object-copy{transform:rotate(-45deg)}
.graphics-object[data-object-type="database"] .object-shape{width:260px;min-height:166px;padding:44px 28px 27px;border:4px solid var(--ink);border-radius:50% / 18%;background:var(--paper-2);box-shadow:0 12px 0 var(--blue)}.graphics-object[data-object-type="database"] .object-shape::before{content:"";position:absolute;left:-4px;right:-4px;top:25px;height:28px;border:4px solid var(--ink);border-radius:50%}
.graphics-object[data-object-type="status"] .object-shape{min-width:210px;padding:21px 25px;border:6px solid var(--accent);color:var(--accent);transform:rotate(-5deg);text-align:center;background:color-mix(in srgb,var(--paper) 90%,transparent)}.graphics-object[data-object-type="status"] strong{font-size:37px;letter-spacing:.02em}.graphics-object[data-object-type="status"] span{color:var(--accent)}
.graphics-object[data-object-type="annotation"] .object-shape{min-width:210px;padding:15px 8px 18px;border-bottom:9px solid var(--accent)}.graphics-object[data-object-type="annotation"] strong{font-family:Georgia,serif;font-style:italic;font-size:42px;text-transform:none}.graphics-object[data-object-type="annotation"] .object-shape::after{content:"↗";position:absolute;right:-30px;top:-14px;font-size:50px;color:var(--accent);transform:rotate(10deg)}
.graphics-object[data-object-type="metric"] .object-shape{min-width:280px}.graphics-object[data-object-type="metric"] strong{font-size:96px;line-height:.8;color:var(--accent)}.graphics-object[data-object-type="text"] .object-shape{min-width:300px}.graphics-object[data-object-type="text"] strong{font-size:52px;line-height:.9}.graphics-object[data-object-type="person"] .object-shape{width:190px;height:230px;padding:105px 20px 20px;border:4px solid var(--ink);border-radius:95px 95px 24px 24px;background:var(--paper-2);text-align:center}.graphics-object[data-object-type="person"] .object-shape::before{content:"";position:absolute;width:78px;height:78px;border:4px solid var(--ink);border-radius:50%;top:20px;left:52px;background:var(--yellow)}
.graphics-object.is-highlighted .object-shape{filter:drop-shadow(0 0 0 var(--coral));outline:8px solid color-mix(in srgb,var(--coral) 28%,transparent);outline-offset:8px}.graphics-object.is-highlighted[data-object-type="annotation"] .object-shape{outline:0}.graphics-object.is-stamped .object-shape::after{content:"APPROVED";position:absolute;right:-38px;top:-30px;padding:9px 14px;border:5px solid var(--coral);color:var(--coral);font-size:17px;font-weight:950;letter-spacing:.08em;transform:rotate(9deg);background:var(--paper)}
.graphics-continuity{position:absolute;z-index:21;left:6.4%;bottom:4.8%;font-size:13px;font-weight:900;letter-spacing:.16em;text-transform:uppercase;color:var(--muted-ink)}.graphics-continuity::before{content:"";display:inline-block;width:42px;height:4px;margin:0 12px 3px 0;background:var(--coral)}
/* Semantic layouts: irregular composition first; no interchangeable card grid. */
.shell-flow_stage .slot-left{left:2%;top:7%}.shell-flow_stage .slot-center{left:38%;top:7%}.shell-flow_stage .slot-right{right:2%;top:7%}.shell-flow_stage .slot-hero{left:30%;top:39%}.shell-flow_stage .slot-bottom{left:33%;bottom:2%}.shell-flow_stage .slot-top{right:5%;top:38%}
.shell-comparison_stage .graphics-stage::after{content:"VS";position:absolute;z-index:0;left:44%;top:36%;font-size:92px;font-weight:950;color:color-mix(in srgb,var(--coral) 30%,transparent);transform:rotate(-8deg)}.shell-comparison_stage .slot-left{left:3%;top:8%}.shell-comparison_stage .slot-right{right:3%;top:8%}.shell-comparison_stage .slot-center{left:35%;top:36%}.shell-comparison_stage .slot-bottom{left:8%;bottom:3%}.shell-comparison_stage .slot-hero{right:8%;bottom:4%}.shell-comparison_stage .slot-top{left:36%;top:2%}
.shell-system_stage .slot-left{left:2%;top:32%}.shell-system_stage .slot-center{left:36%;top:32%}.shell-system_stage .slot-right{right:2%;top:32%}.shell-system_stage .slot-hero{left:28%;top:3%}.shell-system_stage .slot-top{right:5%;top:2%}.shell-system_stage .slot-bottom{left:34%;bottom:2%}
.shell-document_stage .slot-hero{left:8%;top:13%;transform:scale(1.34)}.shell-document_stage .slot-left{left:3%;bottom:4%}.shell-document_stage .slot-right{right:3%;bottom:4%}.shell-document_stage .slot-center{right:8%;top:28%}.shell-document_stage .slot-top{right:6%;top:3%}.shell-document_stage .slot-bottom{left:35%;bottom:2%}
.shell-queue_stage .graphics-stage::after{content:"";position:absolute;left:12%;right:12%;top:51%;height:8px;background:var(--ink);z-index:0}.shell-queue_stage .slot-left{left:2%;top:34%}.shell-queue_stage .slot-center{left:38%;top:27%}.shell-queue_stage .slot-right{right:2%;top:34%}.shell-queue_stage .slot-top{left:22%;top:1%}.shell-queue_stage .slot-bottom{left:35%;bottom:0}.shell-queue_stage .slot-hero{right:6%;top:1%}
.shell-timeline_stage .graphics-stage::after{content:"";position:absolute;left:12%;top:4%;bottom:4%;width:8px;background:var(--ink)}.shell-timeline_stage .graphics-object{left:19%;top:calc(2% + var(--i) * 17%);max-width:72%}.shell-timeline_stage .graphics-object::before{content:"";position:absolute;left:-11.3%;top:45%;width:28px;height:28px;border-radius:50%;background:var(--coral);border:6px solid var(--paper)}
.shell-editorial_stage .graphics-stage{top:28%;bottom:8%}.shell-editorial_stage .graphics-stage::before{display:none}.shell-editorial_stage .graphics-object{max-width:80%}.shell-editorial_stage .slot-left{left:2%;top:17%}.shell-editorial_stage .slot-center{left:33%;top:37%}.shell-editorial_stage .slot-right{right:1%;top:17%}.shell-editorial_stage .slot-bottom{left:12%;bottom:2%}.shell-editorial_stage .slot-top{left:18%;top:1%}.shell-editorial_stage .slot-hero{left:28%;top:25%}.shell-editorial_stage .graphics-object[data-object-type="text"]{max-width:88%}.shell-editorial_stage .graphics-object[data-object-type="text"] strong{font-size:64px}
'''


GRAPHICS_RUNTIME = r'''
const graphicsClamp=(value,min=0,max=1)=>Math.max(min,Math.min(max,value));
const graphicsEase=value=>1-Math.pow(1-graphicsClamp(value),3);
function graphicsObjectPoint(scene,id){
  const object=[...scene.querySelectorAll('[data-object-id]')].find(item=>item.dataset.objectId===id);const stage=scene.querySelector('.graphics-stage');
  if(!object||!stage)return null;const a=object.getBoundingClientRect(),b=stage.getBoundingClientRect();
  const sx=stage.clientWidth/Math.max(1,b.width),sy=stage.clientHeight/Math.max(1,b.height);
  return{x:(a.left-b.left+a.width/2)*sx,y:(a.top-b.top+a.height/2)*sy};
}
function layoutGraphicConnections(scene){
  const stage=scene.querySelector('.graphics-stage'),svg=scene.querySelector('.graphics-connections');if(stage&&svg)svg.setAttribute('viewBox',`0 0 ${stage.clientWidth} ${stage.clientHeight}`);
  scene.querySelectorAll('.graphics-connection').forEach(line=>{const source=graphicsObjectPoint(scene,line.dataset.source),target=graphicsObjectPoint(scene,line.dataset.target);if(!source||!target)return;line.setAttribute('x1',source.x);line.setAttribute('y1',source.y);line.setAttribute('x2',target.x);line.setAttribute('y2',target.y);const length=Math.hypot(target.x-source.x,target.y-source.y);line.dataset.length=String(length);line.style.strokeDasharray=String(length);});
}
function renderGeneratedGraphic(scene,localTime,duration){
  let actions=[];try{actions=JSON.parse(scene.dataset.graphicsActions||'[]')}catch(error){}
  const objects=[...scene.querySelectorAll('.graphics-object')];const sceneProgress=graphicsClamp(localTime/Math.max(.01,duration));
  const heading=scene.querySelector('.graphics-heading');if(heading){const hp=graphicsEase(graphicsClamp(localTime/.7));heading.style.opacity=String(hp);heading.style.transform=`translateY(${(1-hp)*-24}px)`;}
  const stage=scene.querySelector('.graphics-stage');if(stage)stage.style.transform=`scale(${1+sceneProgress*.018}) translateY(${-sceneProgress*5}px)`;
  for(const [index,object] of objects.entries()){
    const objectId=object.dataset.objectId;const related=actions.filter(action=>action.target===objectId);
    const reveal=related.find(action=>action.action==='reveal')?.at_seconds??Math.min(duration*.7,.3+index*.38);const p=graphicsEase(graphicsClamp((localTime-reveal)/.48));
    const type=object.dataset.objectType;let transform=`translateY(${(1-p)*34}px) scale(${.84+p*.16})`;
    if(type==='document')transform+=` rotate(${(1-p)*-7}deg)`;if(type==='status'||type==='annotation')transform+=` rotate(${(1-p)*-5}deg)`;
    const transformation=related.find(action=>action.action==='transform'&&localTime>=action.at_seconds);if(transformation){const tp=graphicsEase(graphicsClamp((localTime-transformation.at_seconds)/.55));transform+=` translateX(${tp*10}px) scale(${1+tp*.055})`;}
    object.style.opacity=String(p);object.style.transform=transform;
    object.classList.toggle('is-highlighted',related.some(action=>action.action==='highlight'&&localTime>=action.at_seconds));
    object.classList.toggle('is-stamped',related.some(action=>action.action==='stamp'&&localTime>=action.at_seconds));
    const detail=object.querySelector('.object-detail');if(detail){const original=object.dataset.detail||'';detail.textContent=transformation?.value||original;}
    const counter=related.find(action=>action.action==='count_to'&&localTime>=action.at_seconds);if(counter){const match=String(counter.value||'').match(/[\d,.]+/);const label=object.querySelector('strong');if(match&&label){const target=Number(match[0].replace(/,/g,''));const cp=graphicsEase(graphicsClamp((localTime-counter.at_seconds)/.8));label.textContent=String(Math.round(target*cp));}}
  }
  layoutGraphicConnections(scene);
  scene.querySelectorAll('.graphics-connection').forEach(line=>{const at=Number(line.dataset.at||0),length=Number(line.dataset.length||500),p=graphicsEase(graphicsClamp((localTime-at)/.65));line.style.opacity=String(p*.86);line.style.strokeDashoffset=String(length*(1-p));});
}
'''


def _object_markup(item: object, index: int, count: int) -> str:
    object_id = html.escape(item.object_id)
    detail = html.escape(item.detail)
    return (
        f'<article class="graphics-object slot-{html.escape(item.slot)}" '
        f'data-object-id="{object_id}" data-object-type="{html.escape(item.object_type)}" '
        f'data-detail="{detail}" style="--i:{index};--count:{count}">'
        f'<div class="object-shape"><i class="object-index">0{index + 1}</i><div class="object-copy">'
        f'<strong>{html.escape(item.label)}</strong><span class="object-detail">{detail}</span>'
        f'</div></div></article>'
    )


def _motion_label(scene: GraphicsScenePlan) -> str:
    value = scene.motion_grammar.strip()
    if len(value) <= 32 and " " not in value:
        return value.replace("_", " ")
    return {
        "flow_stage": "cause and effect",
        "comparison_stage": "object transformation",
        "timeline_stage": "timeline build",
        "document_stage": "document annotation",
        "system_stage": "progressive evidence",
        "queue_stage": "status resolution",
        "editorial_stage": "editorial reveal",
    }[scene.scene_shell]


def graphic_markup(scene: GraphicsScenePlan, element_id: str, *, start: float, duration: float) -> str:
    count = len(scene.objects)
    objects = "".join(_object_markup(item, index, count) for index, item in enumerate(scene.objects))
    connections = "".join(
        f'<line class="graphics-connection" data-source="{html.escape(action.source or "")}" '
        f'data-target="{html.escape(action.target)}" data-at="{action.at_seconds:.4f}" />'
        for action in scene.actions if action.action == "connect" and action.source
    )
    connections_markup = (
        '<svg class="graphics-connections" viewBox="0 0 960 1000" preserveAspectRatio="none" '
        'aria-hidden="true"><g>' + connections + '</g></svg>'
    )
    actions = html.escape(json.dumps([item.model_dump(mode="json") for item in scene.actions]), quote=True)
    continuity = html.escape(scene.continuity_object or "")
    continuity_markup = f'<div class="graphics-continuity">Carries forward · {continuity}</div>' if continuity else ""
    return (
        f'<section id="{element_id}" class="clip scene graphic generated-graphic shell-{html.escape(scene.scene_shell)}" '
        f'data-start="{start:.6f}" data-duration="{duration:.6f}" data-track-index="10" '
        f'data-graphics-actions="{actions}">'
        f'<header class="graphics-heading"><div class="graphics-kicker">{html.escape(_motion_label(scene))}</div>'
        f'<h1 class="graphics-headline">{html.escape(scene.headline)}</h1>'
        f'<p class="graphics-support">{html.escape(scene.support)}</p></header>'
        f'<div class="graphics-stage">{connections_markup}{objects}</div>{continuity_markup}</section>'
    )


def _standalone_html(scenes: list[GraphicsScenePlan], *, width: int, height: int, duration: float) -> str:
    markup = "\n".join(
        graphic_markup(scene, f"graphics-{index:03d}", start=scene.start, duration=scene.end - scene.start)
        for index, scene in enumerate(scenes, 1)
    )
    scene_data = json.dumps([
        {"id": f"graphics-{index:03d}", "start": scene.start, "end": scene.end, "scene_id": scene.scene_id}
        for index, scene in enumerate(scenes, 1)
    ])
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:#171715;color:#f4f0e5;font-family:Inter,ui-sans-serif,system-ui,sans-serif;overflow:hidden}}#viewport{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:repeating-linear-gradient(135deg,#171715,#171715 20px,#1c1c19 20px,#1c1c19 40px)}}#stage{{position:absolute;width:{width}px;height:{height}px;overflow:hidden;transform-origin:center center;box-shadow:0 34px 110px rgba(0,0,0,.52)}}.scene{{position:absolute;inset:0;opacity:0}}#controls{{position:fixed;z-index:100;left:50%;bottom:18px;transform:translateX(-50%);display:flex;align-items:center;gap:10px;width:min(760px,calc(100vw - 28px));padding:10px 13px;border:1px solid rgba(255,255,255,.16);border-radius:7px;background:rgba(21,21,19,.92);backdrop-filter:blur(16px)}}#controls button{{border:1px solid rgba(255,255,255,.22);border-radius:5px;background:#f4f0e5;color:#151513;padding:9px 12px;font-weight:900;cursor:pointer}}#controls input{{flex:1;min-width:120px;accent-color:#ef5b4c}}#time{{min-width:102px;color:#d3cfbf;font-size:13px;font-variant-numeric:tabular-nums}}body.render-mode #controls{{display:none}}{GRAPHICS_STYLES}
</style></head><body><div id="viewport"><div id="stage" data-composition-id="graphics-package" data-no-timeline data-start="0" data-duration="{duration:.6f}" data-width="{width}" data-height="{height}" data-fps="30">{markup}</div></div><div id="controls"><button id="previous" type="button">Previous</button><button id="toggle" type="button">Pause</button><button id="next" type="button">Next</button><input id="scrubber" type="range" min="0" max="{duration:.6f}" step="0.01" value="0"><span id="time"></span></div><script>{GRAPHICS_RUNTIME}
const GRAPHICS_SCENES={scene_data};const stage=document.getElementById('stage');const scrubber=document.getElementById('scrubber');const timeLabel=document.getElementById('time');let playing=true;let currentTime=0;let previousFrame=performance.now();if(window.__hf||new URLSearchParams(location.search).get('render')==='1')document.body.classList.add('render-mode');
function scaleStage(){{const scale=Math.min(innerWidth/{width},innerHeight/{height})*(document.body.classList.contains('render-mode')?1:.94);stage.style.transform=`scale(${{scale}})`;}}window.addEventListener('resize',scaleStage);scaleStage();
function renderAt(time){{currentTime=Math.max(0,Math.min({duration:.6f},time));for(const item of GRAPHICS_SCENES){{const scene=document.getElementById(item.id);const active=currentTime>=item.start&&currentTime<item.end;scene.style.opacity=active?'1':'0';if(active)renderGeneratedGraphic(scene,currentTime-item.start,item.end-item.start);}}scrubber.value=String(currentTime);timeLabel.textContent=`${{currentTime.toFixed(1)}} / {duration:.1f}s`;}}
function tick(now){{if(playing){{currentTime+=(now-previousFrame)/1000;if(currentTime>={duration:.6f})currentTime=0;renderAt(currentTime);}}previousFrame=now;requestAnimationFrame(tick);}}requestAnimationFrame(tick);
document.getElementById('toggle').addEventListener('click',event=>{{playing=!playing;event.currentTarget.textContent=playing?'Pause':'Play';}});scrubber.addEventListener('input',()=>{{playing=false;document.getElementById('toggle').textContent='Play';renderAt(Number(scrubber.value));}});document.getElementById('previous').addEventListener('click',()=>{{const starts=GRAPHICS_SCENES.map(item=>item.start);const target=[...starts].reverse().find(value=>value<currentTime-.2)??0;renderAt(target+.01);}});document.getElementById('next').addEventListener('click',()=>{{const target=GRAPHICS_SCENES.find(item=>item.start>currentTime+.2)?.start??0;renderAt(target+.01);}});window.addEventListener('hf-seek',event=>{{playing=false;renderAt(Number(event.detail.time||0));}});renderAt(0);window.__hf_ready__=true;</script></body></html>'''


def write_graphics_package(project_dir: Path, plan: GraphicsPlan, *, width: int, height: int) -> Path:
    root = project_dir / "08_graphics"
    scene_root = root / "scenes"
    scene_root.mkdir(parents=True, exist_ok=True)
    write_json(root / "graphics_plan.json", plan)
    manifest_scenes = []
    for scene in plan.scenes:
        path = scene_root / f"{scene.scene_id}.html"
        local = scene.model_copy(update={"start": 0.0, "end": scene.end - scene.start})
        path.write_text(_standalone_html([local], width=width, height=height, duration=local.end), encoding="utf-8")
        manifest_scenes.append({
            "scene_id": scene.scene_id,
            "path": path.relative_to(project_dir).as_posix(),
            "start": scene.start,
            "duration": scene.end - scene.start,
            "scene_shell": scene.scene_shell,
            "motion_grammar": scene.motion_grammar,
            "layout_variant": scene.layout_variant,
        })
    master = root / "master.html"
    master.write_text(_standalone_html(plan.scenes, width=width, height=height, duration=plan.duration_seconds), encoding="utf-8")
    write_json(root / "graphics_manifest.json", {
        "episode_id": plan.episode_id,
        "duration_seconds": plan.duration_seconds,
        "scene_count": len(plan.scenes),
        "master": master.relative_to(project_dir).as_posix(),
        "scenes": manifest_scenes,
    })
    return master
