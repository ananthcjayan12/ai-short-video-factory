from __future__ import annotations

import html
import json
import math
from pathlib import Path

from ..io import write_json
from ..models import GraphicsPlan, GraphicsScenePlan, GraphicsTheme


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
.graphics-object .object-shape{position:relative;min-width:190px;min-height:118px;display:flex;flex-direction:column;justify-content:center}.graphics-object strong{display:block;font-size:30px;line-height:1.02;font-weight:950;letter-spacing:-.035em;text-transform:uppercase}.graphics-object span{display:block;font-size:17px;line-height:1.24;color:var(--muted-ink);font-weight:650;margin-top:10px;max-width:300px}
.graphics-object[data-object-type="channel"] .object-shape{width:190px;height:190px;min-width:190px;min-height:190px;border:5px solid var(--ink);border-radius:50%;padding:29px;text-align:center;align-items:center;background:var(--paper)}.graphics-object[data-object-type="channel"] .object-shape::after{content:"";position:absolute;width:20px;height:20px;border-radius:50%;background:var(--accent);right:2px;top:19px;border:4px solid var(--paper)}.graphics-object[data-object-type="channel"] span{font-size:14px;margin-top:7px}
.graphics-object[data-object-type="document"] .object-shape{width:250px;min-height:176px;padding:36px 27px 24px;background:#fffdf7;border:3px solid var(--ink);box-shadow:12px 14px 0 color-mix(in srgb,var(--ink) 14%,transparent);transform:rotate(-2deg)}.graphics-object[data-object-type="document"] .object-shape::before{content:"";position:absolute;left:27px;right:27px;top:20px;height:5px;background:var(--accent);box-shadow:0 10px 0 color-mix(in srgb,var(--ink) 14%,transparent)}
.graphics-object[data-object-type="process"] .object-shape{min-width:250px;padding:27px 31px;border:4px solid var(--ink);border-radius:999px;background:var(--accent);box-shadow:9px 10px 0 var(--ink)}.graphics-object[data-object-type="process"] span{color:color-mix(in srgb,var(--ink) 72%,transparent)}
.graphics-object[data-object-type="decision"] .object-shape{width:210px;height:210px;min-height:210px;padding:42px;transform:rotate(45deg);border:5px solid var(--ink);background:var(--yellow);text-align:center}.graphics-object[data-object-type="decision"] .object-copy{transform:rotate(-45deg)}
.graphics-object[data-object-type="database"] .object-shape{width:260px;min-height:166px;padding:44px 28px 27px;border:4px solid var(--ink);border-radius:50% / 18%;background:var(--paper-2);box-shadow:0 12px 0 var(--blue)}.graphics-object[data-object-type="database"] .object-shape::before{content:"";position:absolute;left:-4px;right:-4px;top:25px;height:28px;border:4px solid var(--ink);border-radius:50%}
.graphics-object[data-object-type="status"] .object-shape{min-width:210px;padding:21px 25px;border:6px solid var(--accent);color:var(--accent);transform:rotate(-5deg);text-align:center;background:color-mix(in srgb,var(--paper) 90%,transparent)}.graphics-object[data-object-type="status"] strong{font-size:37px;letter-spacing:.02em}.graphics-object[data-object-type="status"] span{color:var(--accent)}
.graphics-object[data-object-type="annotation"] .object-shape{min-width:210px;padding:15px 8px 18px;border-bottom:9px solid var(--accent)}.graphics-object[data-object-type="annotation"] strong{font-family:Georgia,serif;font-style:italic;font-size:42px;text-transform:none}.graphics-object[data-object-type="annotation"] .object-shape::after{content:"↗";position:absolute;right:-30px;top:-14px;font-size:50px;color:var(--accent);transform:rotate(10deg)}
.graphics-object[data-object-type="metric"] .object-shape{min-width:280px}.graphics-object[data-object-type="metric"] strong{font-size:96px;line-height:.8;color:var(--accent)}.graphics-object[data-object-type="text"] .object-shape{min-width:300px}.graphics-object[data-object-type="text"] strong{font-size:52px;line-height:.9}.graphics-object[data-object-type="person"] .object-shape{width:190px;height:230px;padding:105px 20px 20px;border:4px solid var(--ink);border-radius:95px 95px 24px 24px;background:var(--paper-2);text-align:center}.graphics-object[data-object-type="person"] .object-shape::before{content:"";position:absolute;width:78px;height:78px;border:4px solid var(--ink);border-radius:50%;top:20px;left:52px;background:var(--yellow)}
.graphics-object.is-highlighted .object-shape{filter:drop-shadow(0 0 0 var(--coral));outline:8px solid color-mix(in srgb,var(--coral) 28%,transparent);outline-offset:8px}.graphics-object.is-highlighted[data-object-type="annotation"] .object-shape{outline:0}.graphics-object.is-stamped .object-shape::after{content:attr(data-stamp-label);position:absolute;right:-38px;top:-30px;padding:9px 14px;border:5px solid var(--coral);color:var(--coral);font-size:17px;font-weight:950;letter-spacing:.08em;transform:rotate(9deg);background:var(--paper)}
.graphics-continuity{position:absolute;z-index:21;left:6.4%;bottom:4.8%;font-size:13px;font-weight:900;letter-spacing:.16em;text-transform:uppercase;color:var(--muted-ink)}.graphics-continuity::before{content:"";display:inline-block;width:42px;height:4px;margin:0 12px 3px 0;background:var(--coral)}
/* Semantic layouts: irregular composition first; no interchangeable card grid. */
.shell-flow_stage .slot-left{left:2%;top:7%}.shell-flow_stage .slot-center{left:38%;top:7%}.shell-flow_stage .slot-right{right:2%;top:7%}.shell-flow_stage .slot-hero{left:30%;top:39%}.shell-flow_stage .slot-bottom{left:33%;bottom:2%}.shell-flow_stage .slot-top{right:5%;top:38%}
.shell-comparison_stage .graphics-stage::after{content:"VS";position:absolute;z-index:0;left:44%;top:36%;font-size:92px;font-weight:950;color:color-mix(in srgb,var(--coral) 30%,transparent);transform:rotate(-8deg)}.shell-comparison_stage .slot-left{left:3%;top:8%}.shell-comparison_stage .slot-right{right:3%;top:8%}.shell-comparison_stage .slot-center{left:35%;top:36%}.shell-comparison_stage .slot-bottom{left:8%;bottom:3%}.shell-comparison_stage .slot-hero{right:8%;bottom:4%}.shell-comparison_stage .slot-top{left:36%;top:2%}
.shell-system_stage .slot-left{left:2%;top:32%}.shell-system_stage .slot-center{left:36%;top:32%}.shell-system_stage .slot-right{right:2%;top:32%}.shell-system_stage .slot-hero{left:28%;top:3%}.shell-system_stage .slot-top{right:5%;top:2%}.shell-system_stage .slot-bottom{left:34%;bottom:2%}
.shell-document_stage .slot-hero{left:8%;top:13%;transform:scale(1.34)}.shell-document_stage .slot-left{left:3%;bottom:4%}.shell-document_stage .slot-right{right:3%;bottom:4%}.shell-document_stage .slot-center{right:8%;top:28%}.shell-document_stage .slot-top{right:6%;top:3%}.shell-document_stage .slot-bottom{left:35%;bottom:2%}
.shell-queue_stage .graphics-stage::after{content:"";position:absolute;left:12%;right:12%;top:51%;height:8px;background:var(--ink);z-index:0}.shell-queue_stage .slot-left{left:2%;top:34%}.shell-queue_stage .slot-center{left:38%;top:27%}.shell-queue_stage .slot-right{right:2%;top:34%}.shell-queue_stage .slot-top{left:22%;top:1%}.shell-queue_stage .slot-bottom{left:35%;bottom:0}.shell-queue_stage .slot-hero{right:6%;top:1%}
.shell-timeline_stage .graphics-stage::after{content:"";position:absolute;left:12%;top:4%;bottom:4%;width:8px;background:var(--ink)}.shell-timeline_stage .graphics-object{left:19%;top:calc(2% + var(--i) * 17%);max-width:72%}.shell-timeline_stage .graphics-object::before{content:"";position:absolute;left:-11.3%;top:45%;width:28px;height:28px;border-radius:50%;background:var(--coral);border:6px solid var(--paper)}
.shell-editorial_stage .graphics-stage{top:28%;bottom:8%}.shell-editorial_stage .graphics-stage::before{display:none}.shell-editorial_stage .graphics-object{max-width:80%}.shell-editorial_stage .slot-left{left:2%;top:17%}.shell-editorial_stage .slot-center{left:33%;top:37%}.shell-editorial_stage .slot-right{right:1%;top:17%}.shell-editorial_stage .slot-bottom{left:12%;bottom:2%}.shell-editorial_stage .slot-top{left:18%;top:1%}.shell-editorial_stage .slot-hero{left:28%;top:25%}.shell-editorial_stage .graphics-object[data-object-type="text"]{max-width:88%}.shell-editorial_stage .graphics-object[data-object-type="text"] strong{font-size:64px}
/* Story-world renderer: free-form staging overrides the legacy slot templates. */
.generated-graphic{--world-a:#f4f0e5;--world-b:#dbe9e6;--world-accent:var(--coral);background:linear-gradient(152deg,var(--world-a),var(--world-b));}
.generated-graphic.shell-collage_stage{--world-b:#ead9c7}.generated-graphic.shell-map_stage{--world-b:#d5e0eb}.generated-graphic.shell-metaphor_stage{--world-b:#eee0a9}.generated-graphic.shell-data_stage{--world-b:#d7dfed}.generated-graphic.shell-spatial_stage{--world-b:#d3e8df}
.generated-graphic.shell-collage_stage::before{background:linear-gradient(12deg,transparent 0 46%,rgba(21,21,19,.07) 46% 47%,transparent 47%),radial-gradient(circle at 86% 12%,rgba(239,91,76,.18),transparent 28%)}
.generated-graphic.shell-map_stage::before{background:radial-gradient(ellipse at 70% 48%,rgba(36,104,201,.16),transparent 38%),linear-gradient(118deg,transparent 0 63%,rgba(21,21,19,.06) 63% 64%,transparent 64%)}
.generated-graphic.shell-metaphor_stage::before{background:radial-gradient(circle at 50% 48%,rgba(244,200,74,.34),transparent 33%)}
.graphics-heading{left:6.2%;right:6.2%;top:4.2%;border-top:0;padding-top:0;pointer-events:none}.graphics-heading::after{width:62px;height:7px;margin-top:18px}.graphics-headline{font-size:70px;max-width:900px;margin:0;line-height:.94}.graphics-support:empty{display:none}.graphics-support{max-width:660px;font-size:21px;margin-top:13px}
.graphics-stage,.shell-editorial_stage .graphics-stage{left:4.8%;right:4.8%;top:17%;bottom:5.8%;overflow:visible}.graphics-stage::before,.shell-editorial_stage .graphics-stage::before{display:none}
.graphics-object.has-frame{left:var(--x)!important;top:var(--y)!important;right:auto!important;bottom:auto!important;width:var(--w);height:var(--h);max-width:none;z-index:var(--depth);transform:rotate(var(--rotation))}.graphics-object.has-frame .object-shape{width:100%;height:100%;min-width:0;min-height:0}.graphics-object.has-frame strong{font-size:clamp(36px,4.5vw,54px)}.graphics-object.has-frame span{font-size:clamp(18px,2vw,24px)}
.graphics-object .object-detail:empty{display:none}
.object-form{position:absolute;inset:0;z-index:-1;pointer-events:none}.graphics-object[data-object-type="artifact"] .object-shape{padding:26px;background:#fffdf7;border:3px solid var(--ink);clip-path:polygon(0 3%,97% 0,100% 93%,72% 96%,70% 100%,38% 97%,4% 100%);box-shadow:12px 15px 0 rgba(21,21,19,.12)}
.graphics-object[data-object-type="evidence"] .object-shape{padding:24px 24px 27px;background:#fffdf7;border-left:8px solid var(--coral);box-shadow:0 12px 25px rgba(21,21,19,.13)}.graphics-object[data-object-type="evidence"] .object-shape::after{content:"";position:absolute;left:24px;right:24px;bottom:16px;height:6px;background:var(--yellow);transform:rotate(-1deg)}
.graphics-object[data-object-type="map_region"] .object-shape{padding:25px;background:var(--blue);color:#fff;clip-path:polygon(8% 8%,72% 0,100% 28%,88% 82%,56% 100%,12% 88%,0 42%);filter:drop-shadow(12px 14px 0 rgba(21,21,19,.14))}.graphics-object[data-object-type="map_region"] span{color:rgba(255,255,255,.78)}
.graphics-object[data-object-type="route"] .object-shape{padding:20px 28px;background:var(--teal);clip-path:polygon(0 18%,82% 18%,82% 0,100% 50%,82% 100%,82% 82%,0 82%)}
.graphics-object[data-object-type="boundary"] .object-shape{padding:24px;border:6px dashed var(--coral);background:transparent}.graphics-object[data-object-type="boundary"] strong{color:var(--coral)}
.graphics-object[data-object-type="axis"] .object-shape{padding:20px 20px 24px;border-left:6px solid var(--ink);border-bottom:6px solid var(--ink);background:linear-gradient(90deg,transparent 24%,rgba(21,21,19,.06) 25%,transparent 26%)}
.graphics-object[data-object-type="number"] .object-shape,.graphics-object[data-object-type="metric"] .object-shape{padding:10px}.graphics-object[data-object-type="number"] strong,.graphics-object[data-object-type="metric"] strong{font-size:clamp(78px,12vw,144px);line-height:.76;color:var(--coral);letter-spacing:-.08em}.graphics-object[data-object-type="number"] span{font-size:22px}
.graphics-object[data-object-type="quote"] .object-shape{padding:26px 12px 28px;border-top:4px solid var(--ink);border-bottom:4px solid var(--ink)}.graphics-object[data-object-type="quote"] strong{font:italic 800 clamp(37px,5vw,64px)/.98 Georgia,serif;text-transform:none;letter-spacing:-.04em}
.graphics-object[data-object-type="figure"] .object-shape{padding:42% 16px 18px;border-radius:48% 48% 14% 14%;background:var(--ink);color:var(--paper);text-align:center}.graphics-object[data-object-type="figure"] .object-shape::before{content:"";position:absolute;left:31%;right:31%;top:9%;aspect-ratio:1;border-radius:50%;background:var(--yellow)}.graphics-object[data-object-type="figure"] span{color:rgba(244,240,229,.7)}
.graphics-object[data-object-type="process"] .object-shape{border-radius:0;box-shadow:none;clip-path:polygon(0 0,88% 0,100% 50%,88% 100%,0 100%,8% 50%)}
.graphics-object[data-object-type="channel"] .object-shape{border-radius:18% 18% 45% 18%;box-shadow:9px 10px 0 rgba(21,21,19,.13)}
.graphics-object[data-object-type="text"] .object-shape{padding:10px}.graphics-object[data-object-type="text"] strong{font-size:clamp(54px,8vw,96px);line-height:.82}
.graphics-object.is-focused .object-shape{filter:drop-shadow(0 22px 28px rgba(21,21,19,.2));outline:9px solid rgba(239,91,76,.3);outline-offset:9px}.graphics-object.is-crossed .object-shape::before{content:"";position:absolute;z-index:8;left:-7%;right:-7%;top:48%;height:10px;background:var(--coral);transform:rotate(-8deg)}
.graphics-object.is-traced .object-shape{outline:6px solid color-mix(in srgb,var(--teal) 68%,transparent);outline-offset:calc(4px + 8px * var(--trace-progress,0));filter:drop-shadow(0 12px 18px rgba(22,140,134,.2))}
.graphics-object[data-depth="background"]{--depth:2}.graphics-object[data-depth="midground"]{--depth:4}.graphics-object[data-depth="foreground"]{--depth:7}
.graphics-object[data-depth="background"] .object-copy{position:absolute;right:10px;top:14px;writing-mode:vertical-rl;opacity:.48}.graphics-object[data-depth="background"] .object-copy strong{font-size:18px!important;letter-spacing:.08em}.graphics-object[data-depth="background"] .object-copy span{display:none}
.graphics-continuity{font-size:12px;opacity:.7}.graphics-continuity::before{width:26px}.graphics-continuity strong{font-weight:950;color:var(--ink)}
/* Whiteboard is a package-wide teaching language, selected by the operator. */
.generated-graphic[data-graphics-theme="whiteboard"]{--paper:#fffef8;--paper-2:#fffdf4;--ink:#26323a;--muted-ink:#5d6870;--coral:#d94b3d;--yellow:#f4d35e;--teal:#168978;--blue:#2c64ad;--world-a:#fffef9;--world-b:#fffef9;background-color:var(--paper);background-image:linear-gradient(rgba(44,100,173,.055) 1px,transparent 1px),linear-gradient(90deg,rgba(44,100,173,.055) 1px,transparent 1px);background-size:42px 42px;font-family:Inter,ui-sans-serif,system-ui,sans-serif}
.generated-graphic[data-graphics-theme="whiteboard"]::before{background:radial-gradient(circle at 11% 13%,rgba(244,211,94,.16),transparent 18%),radial-gradient(circle at 88% 82%,rgba(22,137,120,.09),transparent 22%)}
.generated-graphic[data-graphics-theme="whiteboard"]::after{opacity:.025}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-headline{font-family:"Chalkboard SE","Marker Felt","Segoe Print",Inter,sans-serif;font-size:64px;font-weight:800;letter-spacing:-.045em;text-transform:none;line-height:1.02}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-heading::after{width:170px;height:6px;border-radius:50%;background:var(--blue);transform:rotate(-1.5deg)}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-support{font-size:22px;font-weight:600}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object strong{font-family:"Chalkboard SE","Marker Felt","Segoe Print",Inter,sans-serif;font-weight:800;text-transform:none;letter-spacing:-.025em}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object .object-shape{box-shadow:none;filter:none}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="process"] .object-shape,.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="channel"] .object-shape,.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="artifact"] .object-shape,.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="evidence"] .object-shape{clip-path:none;background:rgba(255,254,248,.92);border:4px solid var(--ink);border-radius:18px}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="decision"] .object-shape{background:rgba(244,211,94,.34)}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="route"] .object-shape{clip-path:none;background:transparent;border-bottom:8px solid var(--teal)}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-stage{overflow:hidden}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-headline{max-height:2.08em;overflow:hidden;overflow-wrap:anywhere}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object.has-frame{overflow:hidden}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object.has-frame .object-shape{display:grid;grid-template-rows:minmax(0,1fr) auto;gap:6px;padding:4px!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;clip-path:none!important;transform:none!important;text-align:center;overflow:hidden}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object.has-frame .object-copy{position:relative!important;inset:auto!important;display:block;max-width:100%;writing-mode:horizontal-tb!important;transform:none!important;overflow:hidden}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object.has-frame strong{display:-webkit-box;font-size:clamp(20px,3.1vw,38px);line-height:1.02;overflow:hidden;overflow-wrap:anywhere;-webkit-box-orient:vertical;-webkit-line-clamp:2}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object.has-frame .object-detail{display:none}
.generated-graphic[data-graphics-theme="whiteboard"] .object-form{position:relative;inset:auto;z-index:0;width:100%;height:100%;min-height:0;color:var(--ink)}
.generated-graphic[data-graphics-theme="whiteboard"] .object-form svg{display:block;width:100%;height:100%;overflow:visible}
.generated-graphic[data-graphics-theme="whiteboard"] .object-form .sketch-line{fill:none;stroke:currentColor;stroke-width:5;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;pathLength:1;stroke-dasharray:1;stroke-dashoffset:calc(1 - var(--draw-progress,0))}
.generated-graphic[data-graphics-theme="whiteboard"] .object-form .sketch-accent{stroke:var(--teal)}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="warning"] .object-form .sketch-accent{stroke:var(--coral)}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="check"] .object-form .sketch-accent{stroke:var(--teal);stroke-width:8}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="decision"] .object-shape::before,.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="figure"] .object-shape::before,.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object.is-crossed .object-shape::before{display:none}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="figure"] .object-shape{background:transparent;color:var(--ink);border:5px solid var(--ink)}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object[data-object-type="figure"] span{color:var(--muted-ink)}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-connection{stroke-width:5;stroke-dasharray:10 8}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object.is-highlighted .object-shape,.generated-graphic[data-graphics-theme="whiteboard"] .graphics-object.is-focused .object-shape{outline:6px solid color-mix(in srgb,var(--yellow) 72%,transparent);outline-offset:7px;filter:none}
.generated-graphic[data-graphics-theme="whiteboard"] .graphics-continuity{font-family:"Chalkboard SE","Marker Felt","Segoe Print",Inter,sans-serif;text-transform:none;letter-spacing:.04em}
'''


GRAPHICS_RUNTIME = r'''
const graphicsClamp=(value,min=0,max=1)=>Math.max(min,Math.min(max,value));
const graphicsEase=value=>1-Math.pow(1-graphicsClamp(value),3);
const graphicsSpring=value=>{const p=graphicsClamp(value);return 1-Math.cos(p*Math.PI*1.5)*Math.exp(-5*p)};
const graphicsProgress=(time,action)=>graphicsSpring(graphicsClamp((time-Number(action.at_seconds||0))/Math.max(.05,Number(action.duration_seconds||.65))));
const graphicsVector=(direction,amount)=>({left:[-amount,0],right:[amount,0],up:[0,-amount],down:[0,amount],in:[0,0],out:[0,0]}[direction]||[0,0]);
const graphicsVisible=object=>Number(getComputedStyle(object).opacity)>.2&&object.getBoundingClientRect().width>2&&object.getBoundingClientRect().height>2;
const graphicsOverlap=(first,second,gap=0)=>({x:Math.min(first.right,second.right)-Math.max(first.left,second.left)+gap,y:Math.min(first.bottom,second.bottom)-Math.max(first.top,second.top)+gap});
const graphicsPairIgnored=(first,second)=>first.object.dataset.depth==='background'||second.object.dataset.depth==='background';
function graphicsApplyChoreography(state){
  state.object.dataset.choreoX=String(state.x);state.object.dataset.choreoY=String(state.y);state.object.dataset.choreoScale='1';
  state.object.style.transform=`translate(${state.x}px,${state.y}px) ${state.base}`;
  state.rect=state.object.getBoundingClientRect();state.collisionRect=(state.object.querySelector('.object-copy')||state.object).getBoundingClientRect();
}
function choreographGraphicScene(scene){
  const stage=scene.querySelector('.graphics-stage');if(!stage)return;
  const stageRect=stage.getBoundingClientRect(),safe={left:stageRect.left+8,right:stageRect.right-8,top:stageRect.top+8,bottom:stageRect.bottom-8};
  const objects=[...scene.querySelectorAll('.graphics-object')];
  for(const object of objects){const base=object.dataset.motionTransform||object.style.transform||'none';object.style.transform=base;object.dataset.choreoX='0';object.dataset.choreoY='0';object.dataset.choreoScale='1';delete object.dataset.choreoHidden;}
  const states=objects.filter(graphicsVisible).map(object=>({
    object,base:object.dataset.motionTransform||'none',rect:object.getBoundingClientRect(),collisionRect:(object.querySelector('.object-copy')||object).getBoundingClientRect(),x:0,y:0,
  }));
  const clampInside=state=>{
    let dx=0,dy=0;if(state.rect.left<safe.left)dx+=safe.left-state.rect.left;if(state.rect.right+dx>safe.right)dx+=safe.right-(state.rect.right+dx);if(state.rect.top<safe.top)dy+=safe.top-state.rect.top;if(state.rect.bottom+dy>safe.bottom)dy+=safe.bottom-(state.rect.bottom+dy);
    if(dx||dy){state.x+=dx;state.y+=dy;graphicsApplyChoreography(state);}
  };
  states.forEach(clampInside);
  let unresolved=0;const visible=states.filter(state=>Number(getComputedStyle(state.object).opacity)>.2);for(let first=0;first<visible.length;first+=1){for(let second=first+1;second<visible.length;second+=1){if(graphicsPairIgnored(visible[first],visible[second]))continue;const overlap=graphicsOverlap(visible[first].collisionRect,visible[second].collisionRect,0);if(overlap.x>4&&overlap.y>4)unresolved+=1;}}
  scene.dataset.graphicsUnresolvedOverlaps=String(unresolved);
}
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
  const stage=scene.querySelector('.graphics-stage');if(stage){const camera=scene.dataset.cameraMove||'locked';let tx=0,ty=-sceneProgress*5,scale=1;if(camera==='push_in')scale=1+sceneProgress*.065;if(camera==='pull_out')scale=1.07-sceneProgress*.07;if(camera==='pan_left')tx=-sceneProgress*28;if(camera==='pan_right')tx=sceneProgress*28;if(camera==='tilt_up')ty=-sceneProgress*34;if(camera==='tilt_down')ty=sceneProgress*24;stage.style.transform=`translate(${tx}px,${ty}px) scale(${scale})`;}
  for(const [index,object] of objects.entries()){
    object.style.clipPath='';const objectId=object.dataset.objectId;const related=actions.filter(action=>action.target===objectId);const explicitContract=scene.dataset.visibilityContract==='explicit';
    const initiallyVisible=object.dataset.initiallyVisible==='true';const revealAction=related.find(action=>action.action==='reveal');const p=explicitContract?(initiallyVisible?1:(revealAction?graphicsProgress(localTime,revealAction):0)):(revealAction?graphicsProgress(localTime,revealAction):1);const entry=graphicsVector(revealAction?.direction,54*(1-p));
    const type=object.dataset.objectType;const baseRotation=Number(object.dataset.rotation||0);let tx=entry[0],ty=entry[1]+(1-p)*24,scale=.82+p*.18,rotation=baseRotation+(1-p)*(type==='document'||type==='artifact'?-7:0),opacity=p;object.style.setProperty('--draw-progress',String(graphicsEase(p)));
    const active=related.filter(action=>localTime>=Number(action.at_seconds||0));const latest=active[active.length-1];
    for(const action of active){const ap=graphicsProgress(localTime,action),vector=graphicsVector(action.direction,70*ap);if(action.action==='move'){tx+=vector[0];ty+=vector[1]}if(action.action==='transform'){scale+=.08*ap;rotation+=action.direction==='clockwise'?8*ap:action.direction==='counterclockwise'?-8*ap:0}if(action.action==='scatter'){tx+=(index%2?1:-1)*58*ap;ty+=(index%3-1)*38*ap}if(action.action==='split'){tx+=(index%2?1:-1)*42*ap}if(action.action==='merge'){tx*=1-ap*.65;ty*=1-ap*.65;scale+=.05*ap}if(action.action==='exit'){opacity*=1-ap;scale*=1-ap*.12}if(action.action==='wipe'){object.style.clipPath=`inset(0 ${100*(1-ap)}% 0 0)`;}if(action.action==='trace'||action.action==='draw'){object.style.setProperty('--trace-progress',String(ap));object.style.setProperty('--draw-progress',String(ap));}}
    object.style.opacity=String(opacity);object.dataset.motionTransform=`translate(${tx}px,${ty}px) scale(${scale}) rotate(${rotation}deg)`;object.style.transform=object.dataset.motionTransform;
    object.classList.toggle('is-highlighted',related.some(action=>action.action==='highlight'&&localTime>=action.at_seconds));object.classList.toggle('is-focused',related.some(action=>action.action==='focus'&&localTime>=action.at_seconds));object.classList.toggle('is-crossed',related.some(action=>action.action==='cross_out'&&localTime>=action.at_seconds));
    object.classList.toggle('is-stamped',related.some(action=>action.action==='stamp'&&localTime>=action.at_seconds));
    object.classList.toggle('is-traced',related.some(action=>(action.action==='trace'||action.action==='draw')&&localTime>=action.at_seconds));const stamp=[...active].reverse().find(action=>action.action==='stamp');const shape=object.querySelector('.object-shape');if(shape&&stamp)shape.dataset.stampLabel=String(stamp.value||'APPROVED');
    const transformation=[...active].reverse().find(action=>['transform','cross_out','wipe','split','merge'].includes(action.action));const detail=object.querySelector('.object-detail');if(detail){const original=object.dataset.detail||'';detail.textContent=transformation?.value||original;}
    const label=object.querySelector('strong');if(label)label.textContent=object.dataset.label||label.textContent;const plannedCounter=related.find(action=>action.action==='count_to');const counter=plannedCounter&&localTime>=plannedCounter.at_seconds?plannedCounter:null;if(explicitContract&&plannedCounter&&label&&!counter)label.textContent='0';if(counter){const match=String(counter.value||'').match(/[\d,.]+/);if(match&&label){const target=Number(match[0].replace(/,/g,'')),cp=graphicsEase(graphicsClamp((localTime-counter.at_seconds)/.8));label.textContent=cp>=.995?String(counter.value||target):String(Math.round(target*cp));}}
  }
  choreographGraphicScene(scene);layoutGraphicConnections(scene);
  scene.querySelectorAll('.graphics-connection').forEach(line=>{const at=Number(line.dataset.at||0),length=Number(line.dataset.length||500),span=Number(line.dataset.duration||.65),p=graphicsEase(graphicsClamp((localTime-at)/span));line.style.opacity=String(p*.86);line.style.strokeDashoffset=String(length*(1-p));});
}
'''


def _svg_icon_markup(object_type: str) -> str:
    """Return a small, fixed SVG vocabulary; scene data never injects markup."""
    icons = {
        "building": '<path class="sketch-line" pathLength="1" d="M20 88V25h80v63M12 88h96M34 40h12m14 0h12m14 0h2M34 55h12m14 0h12m14 0h2M34 70h12m14 18V69h14v19"/>',
        "phone": '<rect class="sketch-line" pathLength="1" x="34" y="10" width="52" height="82" rx="8"/><path class="sketch-line sketch-accent" pathLength="1" d="M48 24h24M49 70l10 8 18-22M56 84h8"/>',
        "person": '<circle class="sketch-line" pathLength="1" cx="60" cy="28" r="17"/><path class="sketch-line" pathLength="1" d="M28 89c2-28 14-42 32-42s30 14 32 42M45 60l15 14 15-14"/>',
        "figure": '<circle class="sketch-line" pathLength="1" cx="60" cy="25" r="15"/><path class="sketch-line" pathLength="1" d="M60 40v28M32 52l28-12 28 12M44 91l16-23 16 23"/>',
        "document": '<path class="sketch-line" pathLength="1" d="M25 9h52l18 18v64H25zM77 9v19h18M40 45h40M40 59h40M40 73h25"/>',
        "artifact": '<path class="sketch-line" pathLength="1" d="M24 12h72v78H24zM38 30h44M38 45h34M38 60h44"/><path class="sketch-line sketch-accent" pathLength="1" d="M38 76h27"/>',
        "database": '<path class="sketch-line" pathLength="1" d="M24 25c0-10 16-17 36-17s36 7 36 17v52c0 10-16 17-36 17S24 87 24 77zM24 25c0 10 16 17 36 17s36-7 36-17M24 50c0 10 16 17 36 17s36-7 36-17"/>',
        "decision": '<path class="sketch-line" pathLength="1" d="M60 8l48 42-48 42L12 50z"/><path class="sketch-line sketch-accent" pathLength="1" d="M43 50l11 11 24-25"/>',
        "check": '<circle class="sketch-line" pathLength="1" cx="60" cy="50" r="41"/><path class="sketch-line sketch-accent" pathLength="1" d="M35 50l16 17 34-37"/>',
        "warning": '<path class="sketch-line" pathLength="1" d="M60 8l50 84H10z"/><path class="sketch-line sketch-accent" pathLength="1" d="M60 34v28M60 77h.1"/>',
        "route": '<path class="sketch-line" pathLength="1" d="M15 78c10-52 31 1 49-38 11-24 25-17 40-6"/><path class="sketch-line sketch-accent" pathLength="1" d="M92 22l14 11-16 8M15 78l8-3M15 78l4 8"/>',
        "map_region": '<path class="sketch-line" pathLength="1" d="M13 28l26-17 25 13 27-11 17 29-13 42-31 7-23-13-25 9-8-33z"/><circle class="sketch-line sketch-accent" pathLength="1" cx="69" cy="49" r="8"/>',
        "number": '<path class="sketch-line" pathLength="1" d="M18 84h84M28 75V51M49 75V34M70 75V43M91 75V18"/>',
        "metric": '<path class="sketch-line" pathLength="1" d="M15 82l23-25 18 10 34-43M77 24h13v13"/>',
        "status": '<rect class="sketch-line" pathLength="1" x="14" y="20" width="92" height="60" rx="12"/><path class="sketch-line sketch-accent" pathLength="1" d="M30 50h14l8-17 13 35 9-18h16"/>',
        "channel": '<circle class="sketch-line" pathLength="1" cx="60" cy="50" r="38"/><path class="sketch-line" pathLength="1" d="M22 50h76M60 12c15 16 20 60 0 76M60 12c-15 16-20 60 0 76"/>',
        "process": '<rect class="sketch-line" pathLength="1" x="13" y="24" width="94" height="52" rx="18"/><path class="sketch-line sketch-accent" pathLength="1" d="M34 50h47M72 40l11 10-11 10"/>',
    }
    drawing = icons.get(
        object_type,
        '<path class="sketch-line" pathLength="1" d="M17 20h86v60H17zM32 38h56M32 53h42M32 68h50"/>',
    )
    return f'<svg viewBox="0 0 120 100" preserveAspectRatio="xMidYMid meet" aria-hidden="true">{drawing}</svg>'


def _object_markup(item: object, index: int, count: int) -> str:
    object_id = html.escape(item.object_id)
    detail = html.escape(item.detail)
    frame = item.frame
    frame_class = " has-frame" if frame else ""
    frame_style = (
        f"--x:{frame.x:.3f}%;--y:{frame.y:.3f}%;--w:{frame.width:.3f}%;--h:{frame.height:.3f}%;"
        f"--rotation:{frame.rotation:.3f}deg;--depth:{ {'background': 2, 'midground': 4, 'foreground': 7}[frame.depth] };"
        if frame else ""
    )
    depth = frame.depth if frame else "midground"
    rotation = frame.rotation if frame else 0
    detail_markup = f'<span class="object-detail">{detail}</span>' if item.show_detail and detail else ""
    return (
        f'<article class="graphics-object slot-{html.escape(item.slot)}{frame_class}" '
        f'data-object-id="{object_id}" data-object-type="{html.escape(item.object_type)}" '
        f'data-depth="{html.escape(depth)}" data-rotation="{rotation:.3f}" '
        f'data-initially-visible="{str(item.initially_visible).lower()}" '
        f'data-visual-form="{html.escape(item.visual_form)}" data-label="{html.escape(item.label)}" data-detail="{detail}" '
        f'style="--i:{index};--count:{count};{frame_style}">'
        f'<div class="object-shape"><div class="object-form">{_svg_icon_markup(item.object_type)}</div><div class="object-copy">'
        f'<strong>{html.escape(item.label)}</strong>{detail_markup}'
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
        "spatial_stage": "spatial reveal",
        "collage_stage": "evidence collage",
        "map_stage": "route trace",
        "metaphor_stage": "object transformation",
        "data_stage": "data drama",
    }[scene.scene_shell]


def graphic_markup(
    scene: GraphicsScenePlan,
    element_id: str,
    *,
    start: float,
    duration: float,
    theme: GraphicsTheme = "editorial",
) -> str:
    count = len(scene.objects)
    visibility_contract = (
        "explicit"
        if all("initially_visible" in item.model_fields_set for item in scene.objects)
        else "legacy"
    )
    objects = "".join(_object_markup(item, index, count) for index, item in enumerate(scene.objects))
    connections = "".join(
        f'<line class="graphics-connection" data-source="{html.escape(action.source or "")}" '
        f'data-target="{html.escape(action.target)}" data-at="{action.at_seconds:.4f}" '
        f'data-duration="{action.duration_seconds:.4f}" data-kind="{html.escape(action.action)}" />'
        for action in scene.actions if action.action in {"connect", "trace", "draw"} and action.source
    )
    connections_markup = (
        '<svg class="graphics-connections" viewBox="0 0 960 1000" preserveAspectRatio="none" '
        'aria-hidden="true"><g>' + connections + '</g></svg>'
    )
    actions = html.escape(json.dumps([item.model_dump(mode="json") for item in scene.actions]), quote=True)
    continuity = html.escape(scene.continuity_object or "")
    continuity_markup = f'<div class="graphics-continuity"><strong>{continuity}</strong></div>' if continuity else ""
    support_markup = f'<p class="graphics-support">{html.escape(scene.support)}</p>' if scene.support else ""
    checkpoints = html.escape(json.dumps(scene.review_checkpoints), quote=True)
    track_duration = max(0.000001, duration - 0.0000001)
    return (
        f'<section id="{element_id}" class="clip scene graphic generated-graphic shell-{html.escape(scene.scene_shell)}" '
        f'data-scene-id="{html.escape(scene.scene_id)}" '
        f'data-graphics-theme="{html.escape(theme)}" '
        f'data-visibility-contract="{visibility_contract}" '
        f'data-start="{start:.9f}" data-duration="{track_duration:.9f}" data-track-index="10" '
        f'data-camera-move="{html.escape(scene.camera_move)}" data-visual-world="{html.escape(scene.visual_world)}" '
        f'data-opening-state="{html.escape(scene.opening_state)}" data-payoff-state="{html.escape(scene.payoff_state)}" '
        f'data-review-checkpoints="{checkpoints}" data-graphics-actions="{actions}">'
        f'<header class="graphics-heading">'
        f'<h1 class="graphics-headline">{html.escape(scene.headline)}</h1>'
        f'{support_markup}</header>'
        f'<div class="graphics-stage">{connections_markup}{objects}</div>{continuity_markup}</section>'
    )


def _frame_bounds(start: float, end: float, fps: int, *, final: bool = False) -> tuple[int, int]:
    start_frame = round(start * fps)
    end_frame = math.ceil(end * fps - 1e-9) if final else round(end * fps)
    return start_frame, max(start_frame + 1, end_frame)


def _standalone_html(
    scenes: list[GraphicsScenePlan], *, width: int, height: int, duration: float, fps: int,
    theme: GraphicsTheme = "editorial",
) -> str:
    frame_windows = [
        _frame_bounds(scene.start, scene.end, fps, final=index == len(scenes) - 1)
        for index, scene in enumerate(scenes)
    ]
    markup = "\n".join(
        graphic_markup(
            scene, f"graphics-{index:03d}", start=start_frame / fps,
            duration=(end_frame - start_frame) / fps, theme=theme,
        )
        for index, (scene, (start_frame, end_frame)) in enumerate(zip(scenes, frame_windows), 1)
    )
    scene_data = json.dumps([
        {
            "id": f"graphics-{index:03d}", "start": start_frame / fps, "end": end_frame / fps,
            "start_frame": start_frame, "end_frame": end_frame, "scene_id": scene.scene_id,
        }
        for index, (scene, (start_frame, end_frame)) in enumerate(zip(scenes, frame_windows), 1)
    ])
    duration_frames = math.ceil(duration * fps - 1e-9)
    render_duration = duration_frames / fps
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:#171715;color:#f4f0e5;font-family:Inter,ui-sans-serif,system-ui,sans-serif;overflow:hidden}}#viewport{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:repeating-linear-gradient(135deg,#171715,#171715 20px,#1c1c19 20px,#1c1c19 40px)}}#stage{{position:absolute;width:{width}px;height:{height}px;overflow:hidden;transform-origin:center center;box-shadow:0 34px 110px rgba(0,0,0,.52)}}.scene{{position:absolute;inset:0;opacity:0}}#controls{{position:fixed;z-index:100;left:50%;bottom:18px;transform:translateX(-50%);display:flex;align-items:center;gap:10px;width:min(760px,calc(100vw - 28px));padding:10px 13px;border:1px solid rgba(255,255,255,.16);border-radius:7px;background:rgba(21,21,19,.92);backdrop-filter:blur(16px)}}#controls button{{border:1px solid rgba(255,255,255,.22);border-radius:5px;background:#f4f0e5;color:#151513;padding:9px 12px;font-weight:900;cursor:pointer}}#controls input{{flex:1;min-width:120px;accent-color:#ef5b4c}}#time{{min-width:102px;color:#d3cfbf;font-size:13px;font-variant-numeric:tabular-nums}}body.render-mode #controls{{display:none}}{GRAPHICS_STYLES}
</style></head><body><div id="viewport"><div id="stage" data-composition-id="graphics-package" data-no-timeline data-start="0" data-duration="{render_duration:.6f}" data-width="{width}" data-height="{height}" data-fps="{fps}">{markup}</div></div><div id="controls"><button id="previous" type="button">Previous</button><button id="toggle" type="button">Pause</button><button id="next" type="button">Next</button><input id="scrubber" type="range" min="0" max="{render_duration:.6f}" step="{1/fps:.6f}" value="0"><span id="time"></span></div><script>{GRAPHICS_RUNTIME}
const GRAPHICS_SCENES={scene_data};const stage=document.getElementById('stage');const scrubber=document.getElementById('scrubber');const timeLabel=document.getElementById('time');let playing=true;let currentTime=0;let previousFrame=performance.now();if(window.__hf||new URLSearchParams(location.search).get('render')==='1')document.body.classList.add('render-mode');
function scaleStage(){{const scale=Math.min(innerWidth/{width},innerHeight/{height})*(document.body.classList.contains('render-mode')?1:.94);stage.style.transform=`scale(${{scale}})`;}}window.addEventListener('resize',scaleStage);scaleStage();
function renderAt(time){{currentTime=Math.max(0,Math.min({render_duration:.6f},time));for(const item of GRAPHICS_SCENES){{const scene=document.getElementById(item.id);const active=currentTime>=item.start&&currentTime<item.end;scene.style.opacity=active?'1':'0';if(active)renderGeneratedGraphic(scene,currentTime-item.start,item.end-item.start);}}scrubber.value=String(currentTime);timeLabel.textContent=`${{currentTime.toFixed(1)}} / {render_duration:.1f}s`;}}
function tick(now){{if(playing){{currentTime+=(now-previousFrame)/1000;if(currentTime>={render_duration:.6f})currentTime=0;renderAt(currentTime);}}previousFrame=now;requestAnimationFrame(tick);}}requestAnimationFrame(tick);
document.getElementById('toggle').addEventListener('click',event=>{{playing=!playing;event.currentTarget.textContent=playing?'Pause':'Play';}});scrubber.addEventListener('input',()=>{{playing=false;document.getElementById('toggle').textContent='Play';renderAt(Number(scrubber.value));}});document.getElementById('previous').addEventListener('click',()=>{{const starts=GRAPHICS_SCENES.map(item=>item.start);const target=[...starts].reverse().find(value=>value<currentTime-.2)??0;renderAt(target+{1/fps:.6f});}});document.getElementById('next').addEventListener('click',()=>{{const target=GRAPHICS_SCENES.find(item=>item.start>currentTime+.2)?.start??0;renderAt(target+{1/fps:.6f});}});window.__svfRenderAt=renderAt;window.addEventListener('hf-seek',event=>{{playing=false;renderAt(Number(event.detail.time||0));}});renderAt(0);window.__hf_ready__=true;</script></body></html>'''


def write_graphics_package(
    project_dir: Path, plan: GraphicsPlan, *, width: int, height: int, fps: int = 60,
) -> Path:
    root = project_dir / "08_graphics"
    # A deterministic/offline regeneration supersedes any previously accepted
    # custom package. Leaving the custom index behind would make composition
    # prefer stale generated source over this newly written legacy plan.
    (root / "custom_graphics.json").unlink(missing_ok=True)
    scene_root = root / "scenes"
    scene_root.mkdir(parents=True, exist_ok=True)
    write_json(root / "graphics_plan.json", plan)
    manifest_scenes = []
    for scene in plan.scenes:
        path = scene_root / f"{scene.scene_id}.html"
        local = scene.model_copy(update={"start": 0.0, "end": scene.end - scene.start})
        start_frame, end_frame = _frame_bounds(scene.start, scene.end, fps)
        path.write_text(
            _standalone_html(
                [local], width=width, height=height, duration=local.end, fps=fps,
                theme=plan.theme,
            ),
            encoding="utf-8",
        )
        manifest_scenes.append({
            "scene_id": scene.scene_id,
            "path": path.relative_to(project_dir).as_posix(),
            "start": scene.start,
            "duration": scene.end - scene.start,
            "render_start_frame": start_frame,
            "render_end_frame": end_frame,
            "scene_shell": scene.scene_shell,
            "motion_grammar": scene.motion_grammar,
            "layout_variant": scene.layout_variant,
        })
    master = root / "master.html"
    master.write_text(
        _standalone_html(
            plan.scenes, width=width, height=height, duration=plan.duration_seconds,
            fps=fps, theme=plan.theme,
        ),
        encoding="utf-8",
    )
    write_json(root / "graphics_manifest.json", {
        "episode_id": plan.episode_id,
        "duration_seconds": plan.duration_seconds,
        "theme": plan.theme,
        "fps": fps,
        "total_frames": math.ceil(plan.duration_seconds * fps - 1e-9),
        "scene_count": len(plan.scenes),
        "master": master.relative_to(project_dir).as_posix(),
        "scenes": manifest_scenes,
    })
    return master
