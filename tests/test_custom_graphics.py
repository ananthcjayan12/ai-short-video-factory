from pathlib import Path

import pytest

from shorts_factory.custom_graphics import (
    CustomGraphicsLayoutPlan,
    CustomGraphicsPackage,
    CustomGraphicsSceneBundle,
    CustomGraphicsSource,
    CustomGraphicsSourceError,
    custom_package_summary,
    validate_custom_graphics_source,
    write_custom_graphics_package,
)
from shorts_factory.io import write_json
from shorts_factory.models import DirectorPlan, EpisodeBrief
from shorts_factory.pipeline import _validate_custom_graphics_visuals
from shorts_factory.rendering.composition import build as build_composition


def _layout() -> CustomGraphicsLayoutPlan:
    return CustomGraphicsLayoutPlan.model_validate({
        "scene_id": "S02",
        "start": 4,
        "end": 9,
        "theme": "whiteboard",
        "visual_thesis": "A receipt moves from ambiguity to one verified job.",
        "headline": "WHERE DOES IT GO?",
        "support": "",
        "layout_style": "receipt route drawn across one whiteboard",
        "opening_state": "One receipt waits beside an unfinished route.",
        "payoff_state": "The completed route reaches the verified job.",
        "elements": [
            {
                "element_id": "receipt",
                "kind": "receipt",
                "role": "primary",
                "label": "Receipt",
                "detail": "",
                "visual_form": "hand-drawn receipt with torn lower edge",
                "frame": {"x": 5, "y": 8, "width": 34, "height": 30},
                "initially_visible": True,
            },
            {
                "element_id": "route",
                "kind": "route",
                "role": "supporting",
                "label": "Evidence route",
                "detail": "",
                "visual_form": "curving marker route with arrowhead",
                "frame": {"x": 28, "y": 41, "width": 58, "height": 18},
                "initially_visible": False,
            },
            {
                "element_id": "verified_job",
                "kind": "gate",
                "role": "primary",
                "label": "Verified job",
                "detail": "",
                "visual_form": "circled job name with check mark",
                "frame": {"x": 50, "y": 65, "width": 44, "height": 28},
                "initially_visible": False,
            },
        ],
        "actions": [
            {
                "cue_id": "cue_route",
                "action": "reveal",
                "target_id": "route",
                "anchor_text": "bought materials",
                "at_seconds": 1.2,
                "duration_seconds": 0.7,
            },
            {
                "cue_id": "cue_job",
                "action": "reveal",
                "target_id": "verified_job",
                "anchor_text": "which purchase belonged",
                "at_seconds": 3.2,
                "duration_seconds": 0.7,
            },
            {
                "cue_id": "cue_connect",
                "action": "connect",
                "source_id": "receipt",
                "target_id": "verified_job",
                "anchor_text": "which project",
                "at_seconds": 3.8,
                "duration_seconds": 0.6,
            },
        ],
        "review_checkpoints": [0.2, 4.4],
    })


def _source() -> CustomGraphicsSource:
    return CustomGraphicsSource(
        scene_id="S02",
        html=(
            '<div id="receipt" data-custom-element data-custom-role="primary"><strong>Receipt</strong></div>'
            '<svg id="route" data-custom-element data-custom-role="supporting" viewBox="0 0 400 120">'
            '<path class="route-line" d="M10 90 C130 0 260 120 390 25" /></svg>'
            '<div id="verified_job" data-custom-element data-custom-role="primary"><strong>Verified job</strong></div>'
        ),
        css=(
            '.custom-generated-graphic[data-custom-scene="S02"] #receipt{left:5%;top:8%;width:34%;height:30%;position:absolute;background:var(--custom-paper-2);color:var(--custom-ink)}'
            '.custom-generated-graphic[data-custom-scene="S02"] #route{left:28%;top:41%;width:58%;height:18%;position:absolute;opacity:0;stroke:var(--custom-secondary);fill:none}'
            '.custom-generated-graphic[data-custom-scene="S02"] #verified_job{left:50%;top:65%;width:44%;height:28%;position:absolute;opacity:0;border:4px solid var(--custom-accent)}'
        ),
        javascript=(
            'function initCustomGraphicScene({root, cues, duration, helpers}) {'
            'const receipt=root.querySelector("#receipt");'
            'const route=root.querySelector("#route");'
            'const job=root.querySelector("#verified_job");'
            'return (localTime) => {'
            'helpers.setVisible(receipt,1);'
            'helpers.setVisible(route,helpers.ease(helpers.progress(localTime,cues["cue_route"],0.7)));'
            'helpers.setVisible(job,helpers.ease(helpers.progress(localTime,cues["cue_job"],0.7)));'
            'helpers.setTransform(job,{scale:0.9+0.1*helpers.ease(helpers.progress(localTime,cues["cue_connect"],0.6))});'
            '};}'
        ),
    )


def test_custom_source_is_scoped_and_compiles_to_inspectable_package(tmp_path: Path):
    layout = _layout()
    source = _source()
    validate_custom_graphics_source(layout, source)
    package = CustomGraphicsPackage(
        episode_id="custom-graphics",
        duration_seconds=9,
        theme="whiteboard",
        scenes=[CustomGraphicsSceneBundle(layout=layout, source=source)],
    )
    summary = custom_package_summary(package, creative_thesis="Custom code explains the route")

    master = write_custom_graphics_package(
        tmp_path, package, summary, width=1080, height=1920, fps=60,
    )

    assert master.is_file()
    assert (tmp_path / "08_graphics/custom_graphics.json").is_file()
    assert (tmp_path / "08_graphics/scenes/S02.html").is_file()
    assert (tmp_path / "08_graphics/scene_sources/S02/layout.json").is_file()
    assert (tmp_path / "08_graphics/scene_sources/S02/scene.html").is_file()
    assert (tmp_path / "08_graphics/scene_sources/S02/scene.css").is_file()
    assert (tmp_path / "08_graphics/scene_sources/S02/scene.js").is_file()
    rendered = master.read_text(encoding="utf-8")
    assert "initCustomGraphicScene" in rendered
    assert 'data-custom-theme="whiteboard"' in rendered
    assert "renderCustomGraphicScene" in rendered
    assert summary.scenes[0].motion_grammar == "custom_scene_code"
    assert _validate_custom_graphics_visuals(
        tmp_path, fps=60, width=1080, height=1920,
    ).ok is True


@pytest.mark.parametrize("field,value,match", [
    ("html", '<img id="receipt" src="https://example.com/a.png">', "not allowed"),
    ("css", 'body{color: #fff}', "literal colors"),
    ("javascript", 'function initCustomGraphicScene({root, cues, duration, helpers}) { document.body.remove(); return (localTime) => {}; }', "document"),
])
def test_custom_source_rejects_scene_escape(field: str, value: str, match: str):
    source = _source().model_copy(update={field: value})
    with pytest.raises(CustomGraphicsSourceError, match=match):
        validate_custom_graphics_source(_layout(), source)


def test_custom_source_allows_prototype_in_scene_content_but_not_property_access():
    source = _source().model_copy(update={
        "javascript": _source().javascript.replace(
            'const receipt=root.querySelector("#receipt");',
            'const prototypeHeading=root.querySelector("#receipt");const receipt=root.querySelector("#receipt");',
        ),
    })
    validate_custom_graphics_source(_layout(), source)

    unsafe = _source().model_copy(update={
        "javascript": _source().javascript.replace(
            'const receipt=root.querySelector("#receipt");',
            'const receipt=root.constructor;',
        ),
    })
    with pytest.raises(CustomGraphicsSourceError, match="constructor property access"):
        validate_custom_graphics_source(_layout(), unsafe)


def test_custom_layout_rejects_future_element_without_reveal():
    payload = _layout().model_dump(mode="json")
    payload["actions"] = [
        action for action in payload["actions"]
        if action["target_id"] != "route"
    ]
    with pytest.raises(ValueError, match="requires exactly one reveal"):
        CustomGraphicsLayoutPlan.model_validate(payload)


def test_composition_prefers_custom_scene_source(tmp_path: Path):
    project = tmp_path / "project"
    brief = EpisodeBrief(
        episode_id="custom-graphics", title="Receipt route",
        pain_point="Receipts must be matched to the correct project.",
        industry="Test", role="Owner", graphics_theme="whiteboard",
        target_seconds=9,
    )
    director = DirectorPlan.model_validate({
        "episode_id": "custom-graphics",
        "duration_seconds": 9,
        "visual_thesis": "Resolve one ambiguous receipt.",
        "scenes": [
            {
                "scene_id": "S01", "start": 0, "end": 4,
                "type": "talking_head", "renderer": "manual_talking_head",
                "narration_excerpt": "Start with the receipt.",
                "purpose": "Introduce the problem", "visual_brief": "Presenter",
            },
            {
                "scene_id": "S02", "start": 4, "end": 9,
                "type": "motion_graphic", "renderer": "hyperframes",
                "narration_excerpt": "Route it to the verified job.",
                "purpose": "Resolve the route", "visual_brief": "Receipt follows evidence route.",
            },
        ],
    })
    write_json(project / "00_input/episode_brief.json", brief)
    write_json(project / "03_director/director_plan.approved.json", director)
    package = CustomGraphicsPackage(
        episode_id="custom-graphics", duration_seconds=9, theme="whiteboard",
        scenes=[CustomGraphicsSceneBundle(layout=_layout(), source=_source())],
    )
    summary = custom_package_summary(package, creative_thesis=director.visual_thesis)
    write_custom_graphics_package(project, package, summary, width=1080, height=1920, fps=60)

    composition = build_composition(project, preview=True, width=1080, height=1920, fps=60)

    rendered = composition.read_text(encoding="utf-8")
    assert 'data-custom-scene="S02"' in rendered
    assert "window.__svfCustomFactories" in rendered
    assert "renderCustomGraphicScene" in rendered
