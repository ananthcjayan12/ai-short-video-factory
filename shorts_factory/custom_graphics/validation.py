from __future__ import annotations

import re
from html.parser import HTMLParser

from .models import CustomGraphicsLayoutPlan, CustomGraphicsSource


class CustomGraphicsSourceError(RuntimeError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("Custom graphics source validation failed:\n- " + "\n- ".join(issues))


_ALLOWED_TAGS = {
    "div", "span", "strong", "em", "p", "h1", "h2", "h3", "small",
    "svg", "g", "path", "line", "polyline", "polygon", "circle", "ellipse", "rect", "text",
}
_FORBIDDEN_ATTRIBUTES = {"src", "href", "xlink:href", "style", "formaction"}
_FORBIDDEN_JS = {
    "window", "document", "globalThis", "fetch", "XMLHttpRequest", "WebSocket",
    "localStorage", "sessionStorage", "indexedDB", "setTimeout", "setInterval",
    "requestAnimationFrame", "eval", "Function", "import(", "require(", "addEventListener",
    "innerHTML", "outerHTML", "Math.random", "Date(", "new Date",
    "ownerDocument", "defaultView", "getRootNode", ".closest(", ".parentElement",
    ".parentNode", "__proto__", "navigator", "location",
}
_FORBIDDEN_JS_PROPERTY_ACCESS = {
    "prototype-chain access": r"(?:\.\s*prototype\b|\[\s*['\"]prototype['\"]\s*\])",
    "constructor property access": r"(?:\.\s*constructor\b|\[\s*['\"]constructor['\"]\s*\])",
}


class _SceneHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.issues: list[str] = []
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _ALLOWED_TAGS:
            self.issues.append(f"HTML tag <{tag}> is not allowed")
        for name, value in attrs:
            lowered = name.casefold()
            if lowered == "id" and value:
                self.ids.append(value)
            if lowered.startswith("on") or lowered in _FORBIDDEN_ATTRIBUTES:
                self.issues.append(f"HTML attribute {name} is not allowed")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def _validate_html(layout: CustomGraphicsLayoutPlan, source: CustomGraphicsSource) -> list[str]:
    parser = _SceneHTMLParser()
    try:
        parser.feed(source.html)
        parser.close()
    except Exception as exc:
        parser.issues.append(f"HTML could not be parsed: {exc}")
    duplicates = sorted({value for value in parser.ids if parser.ids.count(value) > 1})
    if duplicates:
        parser.issues.append("duplicate HTML IDs: " + ", ".join(duplicates))
    present = set(parser.ids)
    missing = [element.element_id for element in layout.elements if element.element_id not in present]
    if missing:
        parser.issues.append("planned element IDs missing from HTML: " + ", ".join(missing))
    return parser.issues


def _validate_css(layout: CustomGraphicsLayoutPlan, source: CustomGraphicsSource) -> list[str]:
    issues: list[str] = []
    css = re.sub(r"/\*.*?\*/", "", source.css, flags=re.DOTALL)
    scope = f'.custom-generated-graphic[data-custom-scene="{layout.scene_id}"]'
    lowered = css.casefold()
    if "@" in css:
        issues.append("CSS at-rules are not allowed")
    if "url(" in lowered:
        issues.append("CSS URLs are not allowed")
    if re.search(r"#[0-9a-f]{3,8}\b|\b(?:rgb|hsl)a?\(", css, flags=re.IGNORECASE):
        issues.append("CSS must use package theme variables instead of literal colors")
    if re.search(r"\bposition\s*:\s*fixed\b", css, flags=re.IGNORECASE):
        issues.append("fixed positioning can escape the scene root")
    if "</style" in lowered or "<script" in lowered:
        issues.append("CSS contains a tag boundary")
    for match in re.finditer(r"([^{}]+)\{[^{}]*\}", css, flags=re.DOTALL):
        selector_text = match.group(1).strip()
        if not selector_text:
            continue
        for selector in selector_text.split(","):
            if not selector.strip().startswith(scope):
                issues.append(f"unscoped CSS selector: {selector.strip()[:120]}")
    return issues


def _validate_javascript(layout: CustomGraphicsLayoutPlan, source: CustomGraphicsSource) -> list[str]:
    issues: list[str] = []
    javascript = source.javascript
    if not javascript.lstrip().startswith("function initCustomGraphicScene"):
        issues.append("JavaScript must contain only the scene initializer at top level")
    signature = re.compile(
        r"function\s+initCustomGraphicScene\s*\(\s*\{\s*root\s*,\s*cues\s*,\s*duration\s*,\s*helpers\s*\}\s*\)\s*\{"
    )
    if not signature.search(javascript):
        issues.append("JavaScript must define initCustomGraphicScene({root, cues, duration, helpers})")
    if not re.search(r"return\s+(?:function\s*)?\(?\s*localTime\s*\)?\s*=>|return\s+function\s*\(\s*localTime\s*\)", javascript):
        issues.append("JavaScript initializer must return a localTime render function")
    for token in sorted(_FORBIDDEN_JS):
        if token in javascript:
            issues.append(f"JavaScript token {token!r} is not allowed")
    for description, pattern in _FORBIDDEN_JS_PROPERTY_ACCESS.items():
        if re.search(pattern, javascript):
            issues.append(f"JavaScript {description} is not allowed")
    if "</script" in javascript.casefold() or "<script" in javascript.casefold():
        issues.append("JavaScript contains a script tag boundary")
    for action in layout.actions:
        if action.action == "hold":
            continue
        if action.cue_id not in javascript:
            issues.append(f"JavaScript does not reference cue {action.cue_id}")
        if action.target_id not in javascript:
            issues.append(f"JavaScript does not reference action target {action.target_id}")
    return issues


def validate_custom_graphics_source(
    layout: CustomGraphicsLayoutPlan,
    source: CustomGraphicsSource,
) -> None:
    issues: list[str] = []
    if source.scene_id != layout.scene_id:
        issues.append("source scene_id does not match layout scene_id")
    issues.extend(_validate_html(layout, source))
    issues.extend(_validate_css(layout, source))
    issues.extend(_validate_javascript(layout, source))
    if issues:
        raise CustomGraphicsSourceError(list(dict.fromkeys(issues)))
