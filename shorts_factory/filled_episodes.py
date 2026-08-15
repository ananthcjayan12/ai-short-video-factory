from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .io import atomic_write_text, write_json
from .models import FilledEpisode, FilledEpisodeCatalog, FilledEpisodeSource
from .project import ProjectStore


SOURCE_DOCUMENT = "100_AI_Automation_Client_Stories_Individually_Rewritten.md"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_PATH = REPO_ROOT / SOURCE_DOCUMENT

ROLE_BY_INDUSTRY = {
    "Contractor / Handyman": "Owner / general contractor",
    "Property Management": "Property manager",
    "Hotels": "Hotel operations manager",
    "Bookkeeping": "Bookkeeper",
    "Restaurant": "Restaurant owner / operator",
    "E-commerce / Retail": "E-commerce operator",
    "Recruiting / Staffing": "Recruiter / staffing operator",
    "Law Firm": "Attorney / legal operations lead",
    "Dental Clinic": "Dental practice manager",
    "Logistics / Freight": "Logistics / freight coordinator",
}

_INDUSTRY_RE = re.compile(r"^# \*\*(.+?)\*\*\s*$")
_EPISODE_RE = re.compile(r"^## \*\*(PAIN-\d{3})\s+—\s+(.+?)\*\*\s*$")
_PAIN_RE = re.compile(r"^\*\*Pain:\s*(.+?)\*\*\s*$")
_STACK_RE = re.compile(r"^\*\*Suggested stack:\*\*\s*(.+?)\s*$")


def _plain_markdown(value: str) -> str:
    value = value.strip().replace("\\+", "+").replace("\\.", ".")
    value = re.sub(r"^\s*[*-]\s+", "", value)
    value = re.sub(r"^\*\*(.+?)\*\*$", r"\1", value)
    value = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
    return value.strip()


def _section(lines: list[str], start: int, heading: str, next_heading: str | None) -> list[str]:
    heading_line = f"### **{heading}**"
    try:
        section_start = next(i for i in range(start, len(lines)) if lines[i].strip() == heading_line) + 1
    except StopIteration as exc:
        raise ValueError(f"Missing section '{heading}' after line {start + 1}") from exc
    section_end = len(lines)
    if next_heading:
        next_line = f"### **{next_heading}**"
        try:
            section_end = next(i for i in range(section_start, len(lines)) if lines[i].strip() == next_line)
        except StopIteration as exc:
            raise ValueError(f"Missing section '{next_heading}' after line {section_start + 1}") from exc
    else:
        for i in range(section_start, len(lines)):
            if _EPISODE_RE.match(lines[i]) or (_INDUSTRY_RE.match(lines[i]) and not lines[i].startswith("##")):
                section_end = i
                break
    return lines[section_start:section_end]


def parse_filled_episode_catalog(path: Path = DEFAULT_SOURCE_PATH) -> FilledEpisodeCatalog:
    """Parse the operator's Markdown library into schema-validated episode contracts."""

    lines = path.read_text(encoding="utf-8").splitlines()
    episodes: list[FilledEpisode] = []
    industry: str | None = None

    for index, line in enumerate(lines):
        industry_match = _INDUSTRY_RE.match(line)
        if industry_match and not line.startswith("##"):
            candidate = industry_match.group(1).strip()
            if candidate in ROLE_BY_INDUSTRY:
                industry = candidate
            continue

        episode_match = _EPISODE_RE.match(line)
        if not episode_match:
            continue
        if industry is None:
            raise ValueError(f"Episode at line {index + 1} has no industry heading")

        source_id, title = episode_match.groups()
        next_episode = next(
            (i for i in range(index + 1, len(lines)) if _EPISODE_RE.match(lines[i])),
            len(lines),
        )
        pain_line = next(
            (i for i in range(index + 1, next_episode) if _PAIN_RE.match(lines[i])),
            None,
        )
        if pain_line is None:
            raise ValueError(f"{source_id} is missing its Pain line")
        pain_point = _PAIN_RE.match(lines[pain_line]).group(1).strip()  # type: ignore[union-attr]

        narration_lines = _section(lines, index, "Narration", "Backend — what we actually built")
        backend_lines = _section(
            lines, index, "Backend — what we actually built", "Viewer DIY — easiest version to build",
        )
        diy_lines = _section(lines, index, "Viewer DIY — easiest version to build", None)

        narration = "\n\n".join(
            paragraph.strip() for paragraph in "\n".join(narration_lines).split("\n\n") if paragraph.strip()
        )
        backend = [_plain_markdown(value) for value in backend_lines if value.strip().startswith("*")]
        stack = None
        diy: list[str] = []
        for value in diy_lines:
            stripped = value.strip()
            if not stripped:
                continue
            stack_match = _STACK_RE.match(stripped)
            if stack_match:
                stack = _plain_markdown(stack_match.group(1))
                continue
            plain = _plain_markdown(stripped)
            if re.match(r"^\d+\.\s+", plain):
                diy.append(plain)

        episodes.append(FilledEpisode(
            source_id=source_id,
            episode_id=f"filled-{source_id.lower()}",
            title=title,
            industry=industry,
            role=ROLE_BY_INDUSTRY[industry],
            pain_point=pain_point,
            backend_summary=backend,
            viewer_diy=diy,
            suggested_stack=stack,
            source=FilledEpisodeSource(
                document=path.name,
                heading=f"{source_id} — {title}",
                line_start=index + 1,
                line_end=next_episode,
                narration=narration,
            ),
        ))

    return FilledEpisodeCatalog(source_document=path.name, episodes=episodes)


@lru_cache(maxsize=1)
def filled_episode_catalog() -> FilledEpisodeCatalog:
    return parse_filled_episode_catalog()


def find_filled_episode(source_id: str) -> FilledEpisode:
    normalized = source_id.strip().upper()
    for episode in filled_episode_catalog().episodes:
        if episode.source_id == normalized:
            return episode
    raise KeyError(normalized)


def materialize_filled_episode(store: ProjectStore, episode: FilledEpisode) -> Path:
    """Create an inspectable production workspace without overwriting existing work."""

    project = store.create(episode.to_brief())
    write_json(project / "00_input/filled_episode_source.json", episode)
    atomic_write_text(
        project / "00_input/source_narration.md",
        f"# {episode.source.heading}\n\n"
        f"Source: {episode.source.document}, lines {episode.source.line_start}-{episode.source.line_end}\n\n"
        f"## Original supplied narration\n\n{episode.source.narration}\n",
    )
    return project
