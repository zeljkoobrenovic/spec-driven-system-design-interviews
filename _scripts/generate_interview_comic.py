#!/usr/bin/env python3
"""Generate a comic-strip visual from one interview.json dataset with Gemini.

Usage:
    GEMINI_API_KEY=... python3 _scripts/generate_interview_comic.py \
        data/book/notification-system/interview.json

    python3 _scripts/generate_interview_comic.py \
        data/book/notification-system/interview.json \
        --dry-run --show-prompt

The script reads the interview's requirements, capacity signals, steps, final
design, and technology choices, then asks the Gemini image API for a polished
comic-style visual. Like ``generate_diagram_picture.py``, the saved file uses
the extension matching the MIME type Gemini returns (for example ``.jpg`` for
``image/jpeg``), not a hard-coded suffix.

By default the output is:

    <interview-dir>/assets/generated/comic/interview-comic.png

After a successful generation the script writes an ``explainerComic`` field into
``interview.json`` holding the dataset-relative path to the image (e.g.
``assets/generated/comic/interview-comic.jpg``). The explorer shows it as the
first "Explainer Comic" entry in the Wrap-up section. Pass ``--no-write-json``
to skip that write.

``--dry-run`` prints the planned output and prompt without calling Gemini or
writing files (and never touches ``interview.json``). The script does not
rebuild ``docs/`` — re-run ``build.py`` afterward.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "gemini-3-pro-image-preview"
DEFAULT_ASPECT_RATIO = "2:3"
DEFAULT_IMAGE_SIZE = "2K"
DEFAULT_OUTPUT = Path("assets/generated/comic/interview-comic.png")
DEFAULT_COLUMNS = 2
DEFAULT_PANEL_WIDTH = 560
DEFAULT_PANEL_HEIGHT = 350
PAGE_MARGIN = 42
GUTTER = 28
HEADER_HEIGHT = 150
FOOTER_HEIGHT = 62
FONT_STACK = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

ACCENTS = [
    "#4F8A8B",
    "#F2A65A",
    "#7A6FF0",
    "#D95D6A",
    "#63A46C",
    "#2F80ED",
    "#B7791F",
    "#2C7A7B",
    "#6B7280",
]


@dataclass(frozen=True)
class Panel:
    title: str
    eyebrow: str
    body: str
    bullets: list[str]
    kind: str
    accent: str


@dataclass(frozen=True)
class ComicSpec:
    path: Path
    prompt: str
    panel_count: int


def endpoint_for(model: str) -> str:
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def extension_for_mime(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime_type.lower(), ".png")


def existing_for_stem(path: Path) -> Path | None:
    parent = path.parent
    if not parent.is_dir():
        return None
    for candidate in sorted(parent.glob(path.stem + ".*")):
        if candidate.stem == path.stem and candidate.is_file():
            return candidate
    return None


def xml(value: Any) -> str:
    return html.escape(str(value), quote=True)


def load_dataset(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: expected top-level object in {path}")
    return data


def write_explainer_comic_field(interview_file: Path, image_path: Path) -> str:
    """Set interview.json's ``explainerComic`` to the dataset-relative image path.

    The path is relative to the interview.json directory (like other asset
    fields). Returns a short status string. Re-reads the file so we don't clobber
    edits made since the dataset was first loaded.
    """
    try:
        rel_path = image_path.resolve().relative_to(interview_file.parent.resolve())
    except ValueError:
        # Image lives outside the dataset dir — store an absolute-ish repo path.
        rel_path = Path(rel(image_path))
    rel_str = rel_path.as_posix()

    data = json.loads(interview_file.read_text(encoding="utf-8"))
    if data.get("explainerComic") == rel_str:
        return f"explainerComic already set to {rel_str}"
    data["explainerComic"] = rel_str
    interview_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return f"wrote explainerComic = {rel_str} into {rel(interview_file)}"


def compact(value: Any, max_chars: int = 260) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        text = "; ".join(compact(item, max_chars=max_chars) for item in value)
    elif isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if item in (None, "", [], {}):
                continue
            parts.append(f"{key}: {compact(item, max_chars=max_chars)}")
        text = "; ".join(parts)
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return textwrap.shorten(text, width=max_chars, placeholder="...")


def item_name(item: Any, fallback: str = "item") -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("term", "name", "title", "label", "id"):
            value = item.get(key)
            if value:
                return str(value)
    return fallback


def strip_step_number(title: str) -> str:
    return re.sub(r"^\s*\d+[a-z]?\.\s*", "", title).strip()


def pick_kind(text: str) -> str:
    hay = text.lower()
    checks = [
        ("final", ("final", "target design")),
        ("scale", ("scale", "shard", "partition", "lane", "fair")),
        ("rate", ("rate", "limit", "throttle", "digest")),
        ("channel", ("channel", "provider", "receipt", "callback", "router")),
        ("prefs", ("preference", "quiet", "consent", "suppression")),
        ("fanout", ("fanout", "broadcast", "recipient")),
        ("dedup", ("idempot", "dedup", "duplicate")),
        ("queue", ("queue", "worker", "retry", "dlq")),
    ]
    for kind, needles in checks:
        if any(needle in hay for needle in needles):
            return kind
    return "baseline"


def pick_step_kind(step: dict[str, Any], title: str, body: str, bullets: list[str]) -> str:
    step_id = str(step.get("id") or "").lower()
    title_l = title.lower()
    direct = [
        ("baseline", ("single-send", "synchronous")),
        ("queue", ("queue-workers", "queue", "worker")),
        ("dedup", ("idempotency", "dedup")),
        ("fanout", ("fanout", "broadcast")),
        ("prefs", ("preferences", "quiet")),
        ("channel", ("channels", "multi-channel", "provider")),
        ("rate", ("rate-limiting", "rate limiting", "throttling")),
        ("scale", ("scale", "scaling", "partition", "shard")),
    ]
    for kind, needles in direct:
        if any(needle in step_id or needle in title_l for needle in needles):
            return kind
    return pick_kind(" ".join([step_id, title, body, " ".join(bullets)]))


def node_labels(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    arch = data.get("highLevelArchitecture") or {}
    for node in arch.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        if node_id:
            out[node_id] = str(node.get("label") or node_id).strip()
    return out


def view_node_summary(view: Any, labels: dict[str, str], limit: int = 7) -> str:
    if not isinstance(view, dict):
        return ""
    names = []
    for ref in view.get("nodes") or []:
        if isinstance(ref, str):
            names.append(labels.get(ref, ref))
        elif isinstance(ref, dict):
            node_id = str(ref.get("id") or "").strip()
            names.append(str(ref.get("label") or labels.get(node_id) or node_id))
    if not names:
        return ""
    return ", ".join(names[:limit])


def capacity_bullets(data: dict[str, Any]) -> list[str]:
    bullets = []
    for item in data.get("capacity") or []:
        if not isinstance(item, dict):
            continue
        label = compact(item.get("label"), 40)
        value = compact(item.get("value"), 48)
        if label and value:
            bullets.append(f"{label}: {value}")
        if len(bullets) >= 3:
            break
    return bullets


def technology_bullet(data: dict[str, Any]) -> str:
    choices = [
        str(item.get("concern"))
        for item in data.get("technologyChoices") or []
        if isinstance(item, dict) and item.get("concern")
    ]
    if not choices:
        return ""
    return "Choices: " + ", ".join(choices[:3])


def build_panels(data: dict[str, Any], max_steps: int | None) -> list[Panel]:
    title = str(data.get("title") or "System Design Interview")
    description = compact(data.get("description"), 310)
    panels: list[Panel] = [
        Panel(
            title="The mission",
            eyebrow="Scope",
            body=description,
            bullets=capacity_bullets(data),
            kind="baseline",
            accent=ACCENTS[0],
        )
    ]

    steps = [step for step in data.get("steps") or [] if isinstance(step, dict)]
    if max_steps is not None:
        steps = steps[:max_steps]
    for index, step in enumerate(steps, start=1):
        raw_title = str(step.get("title") or step.get("id") or f"Step {index}")
        title_text = strip_step_number(raw_title) or raw_title
        body = compact(step.get("description"), 250)
        bullets: list[str] = []
        decision = compact(step.get("decisionPrompt"), 96)
        if decision:
            bullets.append(f"Decision: {decision}")
        concepts = [item_name(item, "concept") for item in step.get("concepts") or []]
        if concepts:
            bullets.append("Concepts: " + ", ".join(concepts[:3]))
        traps = [compact(item.get("trap"), 80) for item in step.get("traps") or [] if isinstance(item, dict)]
        if traps:
            bullets.append("Trap: " + traps[0])
        panels.append(
            Panel(
                title=title_text,
                eyebrow=f"Step {index}",
                body=body,
                bullets=bullets[:3],
                kind=pick_step_kind(step, raw_title, body, bullets),
                accent=ACCENTS[index % len(ACCENTS)],
            )
        )

    final_design = data.get("finalDesign")
    if isinstance(final_design, dict):
        labels = node_labels(data)
        nodes = view_node_summary(final_design.get("view"), labels)
        bullets = []
        if nodes:
            bullets.append("Key pieces: " + nodes)
        tech = technology_bullet(data)
        if tech:
            bullets.append(tech)
        panels.append(
            Panel(
                title="Target final design",
                eyebrow="Wrap-up",
                body=compact(final_design.get("description"), 320),
                bullets=bullets[:3],
                kind="final",
                accent=ACCENTS[(len(panels) + 1) % len(ACCENTS)],
            )
        )

    if len(panels) == 1:
        panels[0] = Panel(
            title=title,
            eyebrow="Interview",
            body=description,
            bullets=capacity_bullets(data),
            kind="baseline",
            accent=ACCENTS[0],
        )
    return panels


def wrap_lines(text: str, width_chars: int, max_lines: int) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    lines = textwrap.wrap(
        text,
        width=max(10, width_chars),
        break_long_words=False,
        break_on_hyphens=False,
    )
    if len(lines) > max_lines:
        clipped = lines[:max_lines]
        clipped[-1] = textwrap.shorten(clipped[-1], width=max(12, width_chars), placeholder="...")
        return clipped
    return lines


def text_block(
    text: str,
    x: float,
    y: float,
    width: float,
    font_size: int,
    max_lines: int,
    *,
    weight: int = 500,
    fill: str = "#111827",
    line_height: float = 1.24,
) -> tuple[str, float]:
    chars = max(14, int(width / (font_size * 0.54)))
    lines = wrap_lines(text, chars, max_lines)
    if not lines:
        return "", y
    parts = [
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{font_size}" '
        f'font-weight="{weight}" fill="{fill}">'
    ]
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else font_size * line_height
        parts.append(f'<tspan x="{x:.1f}" dy="{dy:.1f}">{xml(line)}</tspan>')
    parts.append("</text>")
    return "".join(parts), y + (len(lines) - 1) * font_size * line_height + font_size


def bullet_block(
    bullets: list[str],
    x: float,
    y: float,
    width: float,
    font_size: int,
    max_lines_total: int,
) -> tuple[str, float]:
    parts: list[str] = []
    current_y = y
    used_lines = 0
    for bullet in bullets:
        if used_lines >= max_lines_total:
            break
        remaining = max_lines_total - used_lines
        chars = max(12, int((width - 18) / (font_size * 0.54)))
        lines = wrap_lines(bullet, chars, remaining)
        if not lines:
            continue
        parts.append(f'<circle cx="{x + 5:.1f}" cy="{current_y - 4:.1f}" r="3.2" fill="#111827"/>')
        parts.append(
            f'<text x="{x + 18:.1f}" y="{current_y:.1f}" font-size="{font_size}" '
            f'font-weight="520" fill="#1F2937">'
        )
        for index, line in enumerate(lines):
            dy = 0 if index == 0 else font_size * 1.2
            parts.append(f'<tspan x="{x + 18:.1f}" dy="{dy:.1f}">{xml(line)}</tspan>')
        parts.append("</text>")
        current_y += len(lines) * font_size * 1.2 + 8
        used_lines += len(lines)
    return "".join(parts), current_y


def draw_cloud(x: float, y: float, w: float, h: float, fill: str, stroke: str = "#111827") -> str:
    return (
        f'<path d="M {x + w * .18:.1f} {y + h * .70:.1f} '
        f'C {x + w * .02:.1f} {y + h * .70:.1f}, {x + w * .02:.1f} {y + h * .42:.1f}, {x + w * .24:.1f} {y + h * .43:.1f} '
        f'C {x + w * .28:.1f} {y + h * .12:.1f}, {x + w * .62:.1f} {y + h * .14:.1f}, {x + w * .65:.1f} {y + h * .38:.1f} '
        f'C {x + w * .92:.1f} {y + h * .36:.1f}, {x + w * .94:.1f} {y + h * .70:.1f}, {x + w * .76:.1f} {y + h * .70:.1f} Z" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="4" stroke-linejoin="round"/>'
    )


def draw_icon(kind: str, x: float, y: float, size: float, accent: str) -> str:
    s = size
    dark = "#111827"
    light = "#F8FAFC"
    muted = "#DDE7EE"
    parts = [f'<g class="comic-icon" transform="translate({x:.1f} {y:.1f})">']
    parts.append(f'<circle cx="{s/2:.1f}" cy="{s/2:.1f}" r="{s*.45:.1f}" fill="{accent}" opacity=".13"/>')

    if kind == "queue":
        for i in range(3):
            yy = s * (0.24 + i * 0.18)
            parts.append(f'<rect x="{s*.18:.1f}" y="{yy:.1f}" width="{s*.40:.1f}" height="{s*.12:.1f}" rx="8" fill="{light}" stroke="{dark}" stroke-width="4"/>')
        parts.append(f'<circle cx="{s*.74:.1f}" cy="{s*.36:.1f}" r="{s*.09:.1f}" fill="{accent}" stroke="{dark}" stroke-width="4"/>')
        parts.append(f'<path d="M {s*.74:.1f} {s*.46:.1f} L {s*.74:.1f} {s*.74:.1f} M {s*.62:.1f} {s*.58:.1f} L {s*.86:.1f} {s*.58:.1f}" stroke="{dark}" stroke-width="4" stroke-linecap="round"/>')
    elif kind == "dedup":
        parts.append(f'<rect x="{s*.18:.1f}" y="{s*.28:.1f}" width="{s*.34:.1f}" height="{s*.22:.1f}" rx="8" fill="{light}" stroke="{dark}" stroke-width="4"/>')
        parts.append(f'<rect x="{s*.28:.1f}" y="{s*.40:.1f}" width="{s*.34:.1f}" height="{s*.22:.1f}" rx="8" fill="{muted}" stroke="{dark}" stroke-width="4"/>')
        parts.append(f'<circle cx="{s*.70:.1f}" cy="{s*.38:.1f}" r="{s*.10:.1f}" fill="{accent}" stroke="{dark}" stroke-width="4"/>')
        parts.append(f'<path d="M {s*.77:.1f} {s*.45:.1f} L {s*.90:.1f} {s*.58:.1f} M {s*.84:.1f} {s*.52:.1f} L {s*.78:.1f} {s*.58:.1f}" stroke="{dark}" stroke-width="4" stroke-linecap="round"/>')
    elif kind == "fanout":
        points = [(0.22, 0.24), (0.78, 0.24), (0.18, 0.72), (0.82, 0.72)]
        parts.append(f'<circle cx="{s*.50:.1f}" cy="{s*.48:.1f}" r="{s*.11:.1f}" fill="{accent}" stroke="{dark}" stroke-width="4"/>')
        for px, py in points:
            parts.append(f'<path d="M {s*.50:.1f} {s*.48:.1f} L {s*px:.1f} {s*py:.1f}" stroke="{dark}" stroke-width="3" stroke-linecap="round"/>')
            parts.append(f'<circle cx="{s*px:.1f}" cy="{s*py:.1f}" r="{s*.075:.1f}" fill="{light}" stroke="{dark}" stroke-width="4"/>')
    elif kind == "prefs":
        parts.append(f'<rect x="{s*.19:.1f}" y="{s*.20:.1f}" width="{s*.58:.1f}" height="{s*.50:.1f}" rx="18" fill="{light}" stroke="{dark}" stroke-width="4"/>')
        for i, knob in enumerate([0.64, 0.38, 0.56]):
            yy = s * (0.32 + i * 0.13)
            parts.append(f'<path d="M {s*.29:.1f} {yy:.1f} L {s*.68:.1f} {yy:.1f}" stroke="{dark}" stroke-width="4" stroke-linecap="round"/>')
            parts.append(f'<circle cx="{s*knob:.1f}" cy="{yy:.1f}" r="{s*.045:.1f}" fill="{accent}" stroke="{dark}" stroke-width="3"/>')
    elif kind == "channel":
        parts.append(f'<rect x="{s*.34:.1f}" y="{s*.34:.1f}" width="{s*.26:.1f}" height="{s*.22:.1f}" rx="8" fill="{accent}" stroke="{dark}" stroke-width="4"/>')
        for px, py, label in [(0.18, 0.22, ""), (0.78, 0.22, ""), (0.20, 0.76, ""), (0.78, 0.76, "")]:
            parts.append(f'<path d="M {s*.47:.1f} {s*.45:.1f} L {s*px:.1f} {s*py:.1f}" stroke="{dark}" stroke-width="3" stroke-linecap="round"/>')
            parts.append(f'<rect x="{s*px - s*.07:.1f}" y="{s*py - s*.055:.1f}" width="{s*.14:.1f}" height="{s*.11:.1f}" rx="6" fill="{light}" stroke="{dark}" stroke-width="3"/>')
    elif kind == "rate":
        parts.append(f'<path d="M {s*.22:.1f} {s*.65:.1f} A {s*.28:.1f} {s*.28:.1f} 0 0 1 {s*.78:.1f} {s*.65:.1f}" fill="none" stroke="{dark}" stroke-width="5" stroke-linecap="round"/>')
        parts.append(f'<path d="M {s*.50:.1f} {s*.65:.1f} L {s*.66:.1f} {s*.42:.1f}" stroke="{accent}" stroke-width="7" stroke-linecap="round"/>')
        for px in [0.29, 0.50, 0.71]:
            parts.append(f'<circle cx="{s*px:.1f}" cy="{s*.65:.1f}" r="{s*.025:.1f}" fill="{dark}"/>')
        parts.append(f'<rect x="{s*.24:.1f}" y="{s*.72:.1f}" width="{s*.52:.1f}" height="{s*.10:.1f}" rx="8" fill="{light}" stroke="{dark}" stroke-width="4"/>')
    elif kind == "scale":
        for i, yy in enumerate([0.26, 0.45, 0.64]):
            parts.append(f'<rect x="{s*.17:.1f}" y="{s*yy:.1f}" width="{s*.66:.1f}" height="{s*.11:.1f}" rx="9" fill="{light if i != 1 else accent}" stroke="{dark}" stroke-width="4"/>')
            parts.append(f'<path d="M {s*.34:.1f} {s*yy:.1f} L {s*.34:.1f} {s*(yy+.11):.1f} M {s*.56:.1f} {s*yy:.1f} L {s*.56:.1f} {s*(yy+.11):.1f}" stroke="{dark}" stroke-width="3"/>')
    elif kind == "final":
        positions = [(0.22, 0.30), (0.50, 0.22), (0.78, 0.30), (0.34, 0.66), (0.66, 0.66)]
        for a, b in [(0, 1), (1, 2), (1, 3), (1, 4), (3, 4)]:
            ax, ay = positions[a]
            bx, by = positions[b]
            parts.append(f'<path d="M {s*ax:.1f} {s*ay:.1f} L {s*bx:.1f} {s*by:.1f}" stroke="{dark}" stroke-width="3" stroke-linecap="round"/>')
        for i, (px, py) in enumerate(positions):
            fill = accent if i == 1 else light
            parts.append(f'<rect x="{s*px - s*.065:.1f}" y="{s*py - s*.055:.1f}" width="{s*.13:.1f}" height="{s*.11:.1f}" rx="6" fill="{fill}" stroke="{dark}" stroke-width="3"/>')
    else:
        parts.append(draw_cloud(0, s * 0.20, s * 0.72, s * 0.42, light))
        parts.append(f'<path d="M {s*.45:.1f} {s*.47:.1f} L {s*.35:.1f} {s*.72:.1f} L {s*.52:.1f} {s*.61:.1f} L {s*.45:.1f} {s*.82:.1f}" fill="{accent}" stroke="{dark}" stroke-width="4" stroke-linejoin="round"/>')

    parts.append("</g>")
    return "".join(parts)


def draw_panel(panel: Panel, index: int, x: float, y: float, w: float, h: float) -> str:
    parts: list[str] = []
    shadow = f'M {x + 8:.1f} {y + 10:.1f} h {w - 2:.1f} a 16 16 0 0 1 16 16 v {h - 2:.1f} a 16 16 0 0 1 -16 16 h {-w + 2:.1f} z'
    parts.append(f'<path d="{shadow}" fill="#0F172A" opacity=".12"/>')
    parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="18" fill="#FFFFFF" stroke="#111827" stroke-width="4"/>')
    parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="58" rx="18" fill="{panel.accent}" opacity=".92"/>')
    parts.append(f'<path d="M {x:.1f} {y + 42:.1f} h {w:.1f} v 18 h {-w:.1f} z" fill="{panel.accent}" opacity=".92"/>')
    parts.append(f'<circle cx="{x + 38:.1f}" cy="{y + 30:.1f}" r="19" fill="#FFFFFF" stroke="#111827" stroke-width="3"/>')
    parts.append(f'<text x="{x + 38:.1f}" y="{y + 37:.1f}" text-anchor="middle" font-size="19" font-weight="850" fill="#111827">{index}</text>')
    parts.append(f'<text x="{x + 70:.1f}" y="{y + 36:.1f}" font-size="17" font-weight="850" fill="#FFFFFF" letter-spacing=".3">{xml(panel.eyebrow.upper())}</text>')
    parts.append(f'<path d="M {x + w - 68:.1f} {y + 16:.1f} l 14 12 l -14 12" fill="none" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" opacity=".86"/>')

    icon_size = min(128, w * 0.26)
    parts.append(draw_icon(panel.kind, x + w - icon_size - 26, y + 78, icon_size, panel.accent))

    title_svg, cursor_y = text_block(
        panel.title,
        x + 26,
        y + 92,
        w - icon_size - 72,
        24,
        2,
        weight=850,
        fill="#111827",
    )
    parts.append(title_svg)

    body_svg, cursor_y = text_block(
        panel.body,
        x + 26,
        cursor_y + 18,
        w - 52,
        16,
        5,
        weight=520,
        fill="#374151",
        line_height=1.28,
    )
    parts.append(body_svg)

    bubble_y = max(y + h - 112, cursor_y + 18)
    bubble_h = y + h - bubble_y - 22
    if panel.bullets and bubble_h > 50:
        parts.append(
            f'<path d="M {x + 26:.1f} {bubble_y:.1f} h {w - 52:.1f} a 14 14 0 0 1 14 14 '
            f'v {bubble_h - 20:.1f} a 14 14 0 0 1 -14 14 h {-w + 96:.1f} '
            f'l -22 20 l 6 -20 h -28 a 14 14 0 0 1 -14 -14 v {-bubble_h + 20:.1f} '
            f'a 14 14 0 0 1 14 -14 z" fill="#F8FAFC" stroke="#111827" stroke-width="3"/>'
        )
        bullet_svg, _ = bullet_block(panel.bullets, x + 46, bubble_y + 28, w - 92, 13, 4)
        parts.append(bullet_svg)
    return "".join(parts)


def render_svg(
    data: dict[str, Any],
    panels: list[Panel],
    *,
    columns: int,
    panel_width: int,
    panel_height: int,
    source_label: str,
) -> str:
    columns = max(1, columns)
    rows = (len(panels) + columns - 1) // columns
    width = PAGE_MARGIN * 2 + columns * panel_width + (columns - 1) * GUTTER
    height = HEADER_HEIGHT + rows * panel_height + (rows - 1) * GUTTER + FOOTER_HEIGHT
    title = str(data.get("title") or "System Design Interview")
    subtitle = compact(data.get("description"), 170)

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{xml(title)} comic visual">',
        "<defs>",
        '<pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="3" cy="3" r="1.8" fill="#111827" opacity=".12"/></pattern>',
        '<linearGradient id="paper" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFDF7"/><stop offset="1" stop-color="#EEF7F6"/></linearGradient>',
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="url(#paper)"/>',
        f'<rect width="{width}" height="{height}" fill="url(#dots)" opacity=".55"/>',
        f'<text x="{PAGE_MARGIN}" y="58" font-family="{FONT_STACK}" font-size="38" font-weight="900" fill="#111827">{xml(title)}</text>',
        f'<text x="{PAGE_MARGIN}" y="88" font-family="{FONT_STACK}" font-size="17" font-weight="620" fill="#374151">{xml(subtitle)}</text>',
        f'<text x="{PAGE_MARGIN}" y="120" font-family="{FONT_STACK}" font-size="15" font-weight="800" fill="#111827">Comic walkthrough: from naive call to production-grade design</text>',
        f'<g font-family="{FONT_STACK}">',
    ]

    for idx, panel in enumerate(panels, start=1):
        row = (idx - 1) // columns
        col = (idx - 1) % columns
        x = PAGE_MARGIN + col * (panel_width + GUTTER)
        y = HEADER_HEIGHT + row * (panel_height + GUTTER)
        parts.append(draw_panel(panel, idx, x, y, panel_width, panel_height))

    footer_y = height - 28
    parts.append(
        f'<text x="{PAGE_MARGIN}" y="{footer_y}" font-size="13" font-weight="620" fill="#4B5563">'
        f'Generated from {xml(source_label)} - panels summarize authored interview data.</text>'
    )
    parts.append("</g></svg>")
    return "\n".join(parts) + "\n"


def storyboard_text(panels: list[Panel]) -> str:
    lines: list[str] = []
    for index, panel in enumerate(panels, start=1):
        parts = [
            f"Panel {index}: {panel.eyebrow} - {panel.title}",
            f"Visual motif: {panel.kind}",
            f"Caption idea: {compact(panel.body, 260)}",
        ]
        if panel.bullets:
            parts.append("Callouts: " + " | ".join(compact(item, 120) for item in panel.bullets[:3]))
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def build_comic_prompt(data: dict[str, Any], panels: list[Panel], user_prompt: str = "") -> str:
    title = str(data.get("title") or "System Design Interview")
    requirements = data.get("requirements") if isinstance(data.get("requirements"), dict) else {}
    functional = [compact(item, 110) for item in requirements.get("functional") or []][:4]
    nonfunctional = [compact(item, 130) for item in requirements.get("nonFunctional") or []][:4]
    tech = [
        str(item.get("concern"))
        for item in data.get("technologyChoices") or []
        if isinstance(item, dict) and item.get("concern")
    ][:6]
    final_design = data.get("finalDesign") if isinstance(data.get("finalDesign"), dict) else {}

    parts = [
        "Create a polished comic-strip visual for a system-design interview walkthrough.",
        f"The image should be a single 16:9 comic page with {len(panels)} clean panels, not a literal UI screenshot and not a Mermaid diagram.",
        "Style: modern editorial technical comic, crisp ink outlines, subtle halftone texture, white/off-white paper background, restrained teal/blue/orange/green accents, professional and readable.",
        "Audience: senior software engineers preparing for system design interviews.",
        "Show the interview as a journey from naive design to production-grade architecture.",
        "Use short labels only, with correct spelling. Keep labels horizontal, legible, and inside their shapes. If a label would be too small or uncertain, omit it.",
        "Do not include tiny paragraphs, code blocks, terminal windows, UI chrome, watermarks, logos, photorealism, 3D render styling, neon cyberpunk styling, or fantasy elements.",
        "Make the panels feel connected with arrows, recurring characters or icons, and visual escalation of complexity.",
        "Minimize long blocks of text, keep comic primary visual.",
        f"Interview title: {compact(title, 180)}",
        f"Interview description: {compact(data.get('description'), 480)}",
    ]
    if functional:
        parts.append("Functional requirements to imply:")
        parts.extend(f"- {item}" for item in functional)
    if nonfunctional:
        parts.append("Non-functional requirements to imply:")
        parts.extend(f"- {item}" for item in nonfunctional)
    if tech:
        parts.append("Modern technology choice themes to hint at without drawing vendor logos:")
        parts.extend(f"- {item}" for item in tech)
    if final_design:
        parts.append("Final design summary:")
        parts.append(compact(final_design.get("description"), 520))
    parts.append("Storyboard:")
    parts.append(storyboard_text(panels))
    parts.append(
        "Final quality bar: presentation-ready, visually engaging, technically credible, clear at social-media preview size, and useful as a shareable visual summary of the interview."
    )
    if user_prompt:
        parts.append("Additional user instruction:")
        parts.append(compact(user_prompt, 1400))
    return "\n".join(parts)


def extract_image(response: dict[str, Any]) -> tuple[bytes, str]:
    candidates = response.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                return base64.b64decode(inline["data"]), mime_type
    raise RuntimeError(
        "No image data in Gemini response. Raw response: "
        + json.dumps(response)[:1000]
    )


def call_gemini_image(
    *,
    api_key: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    image_size: str,
    timeout: int,
) -> tuple[bytes, str]:
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": image_size,
            },
        },
    }
    req = urllib.request.Request(
        endpoint_for(model),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from Gemini: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling Gemini: {exc}") from exc

    response = json.loads(body.decode("utf-8"))
    return extract_image(response)


def process_spec(
    *,
    spec: ComicSpec,
    api_key: str | None,
    model: str,
    aspect_ratio: str,
    image_size: str,
    timeout: int,
    force: bool,
    dry_run: bool,
    show_prompt: bool,
) -> tuple[str, Path]:
    existing = existing_for_stem(spec.path)
    if existing is not None and not force:
        return f"skip existing: {rel(existing)}", existing
    if dry_run:
        if show_prompt:
            return f"dry-run: {rel(spec.path)}\n\n{spec.prompt}", spec.path
        short_prompt = textwrap.shorten(
            re.sub(r"\s+", " ", spec.prompt),
            width=420,
            placeholder="...",
        )
        return f"dry-run: {rel(spec.path)}\n    prompt: {short_prompt}", spec.path
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    image_bytes, mime_type = call_gemini_image(
        api_key=api_key,
        model=model,
        prompt=spec.prompt,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
        timeout=timeout,
    )
    out_path = spec.path.with_suffix(extension_for_mime(mime_type))
    if existing is not None and existing != out_path:
        try:
            existing.unlink()
        except OSError:
            pass
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(image_bytes)
    return f"generated: {rel(out_path)} ({mime_type}, {len(image_bytes)} bytes)", out_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "interview_json",
        help="Path to a data/<group>/<id>/interview.json file.",
    )
    parser.add_argument(
        "--output",
        default="",
        help=(
            "Planned output image path. The actual extension is replaced with "
            "the MIME type returned by Gemini. Defaults to "
            "<interview-dir>/assets/generated/comic/interview-comic.png."
        ),
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=0,
        help="Limit the number of interview steps shown. Default 0 means all steps.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing generated image output.",
    )
    parser.add_argument(
        "--no-write-json",
        action="store_true",
        help=(
            "Do not write the explainerComic path back into interview.json "
            "after generating the image."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print panel summaries and output path without writing files.",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="With --dry-run, print the full Gemini prompt instead of a summary.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini image model (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--aspect-ratio",
        default=DEFAULT_ASPECT_RATIO,
        help=f"Gemini image aspect ratio (default: {DEFAULT_ASPECT_RATIO}).",
    )
    parser.add_argument(
        "--image-size",
        default=DEFAULT_IMAGE_SIZE,
        help=f"Gemini imageSize (default: {DEFAULT_IMAGE_SIZE}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=240,
        help="Gemini request timeout in seconds (default: 240).",
    )
    parser.add_argument(
        "--prompt",
        default="",
        help="Free-form extra prompt text appended to the generated comic prompt.",
    )
    parser.add_argument(
        "--prompt-file",
        default="",
        help="Read extra prompt text from a UTF-8 file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    interview_file = Path(args.interview_json)
    if not interview_file.is_absolute():
        interview_file = (Path.cwd() / interview_file).resolve()
    if not interview_file.is_file():
        print(f"error: no interview.json at {interview_file}", file=sys.stderr)
        return 2
    if interview_file.name != "interview.json":
        print(f"error: expected a file named interview.json, got {interview_file}", file=sys.stderr)
        return 2

    data = load_dataset(interview_file)
    max_steps = args.max_steps if args.max_steps and args.max_steps > 0 else None
    panels = build_panels(data, max_steps=max_steps)
    user_prompt = args.prompt
    if args.prompt_file:
        prompt_file = Path(args.prompt_file)
        if not prompt_file.is_absolute():
            prompt_file = (Path.cwd() / prompt_file).resolve()
        user_prompt = (user_prompt + "\n\n" + prompt_file.read_text(encoding="utf-8")).strip()

    output = Path(args.output) if args.output else interview_file.parent / DEFAULT_OUTPUT
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()

    spec = ComicSpec(
        path=output,
        prompt=build_comic_prompt(data, panels, user_prompt=user_prompt),
        panel_count=len(panels),
    )

    existing = existing_for_stem(output)
    if existing is not None and not args.force and not args.dry_run:
        # Image already exists: don't spend an API call. Still ensure the
        # interview.json field points at it (so re-running wires up the comic).
        print(f"skip existing image: {rel(existing)} (use --force to regenerate)")
        if args.no_write_json:
            print("skipped interview.json update (--no-write-json)")
        else:
            try:
                print(write_explainer_comic_field(interview_file, existing))
            except Exception as exc:  # noqa: BLE001
                print(f"warning: could not update interview.json: {exc}", file=sys.stderr)
        return 0

    print(f"Interview: {data.get('title') or interview_file.parent.name}")
    print(f"Output: {rel(output)}")
    print(f"Model: {args.model}")
    print(f"Aspect ratio: {args.aspect_ratio}")
    print(f"Image size: {args.image_size}")
    print(f"Panels: {len(panels)}")

    if args.dry_run:
        for index, panel in enumerate(panels, start=1):
            print(f"  {index:02d}. [{panel.eyebrow}] {panel.title} ({panel.kind})")
        status, _actual_path = process_spec(
            spec=spec,
            api_key=None,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            image_size=args.image_size,
            timeout=args.timeout,
            force=args.force,
            dry_run=True,
            show_prompt=args.show_prompt,
        )
        print(f"\n{status}")
        return 0

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        return 2

    try:
        status, actual_path = process_spec(
            spec=spec,
            api_key=api_key,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            image_size=args.image_size,
            timeout=args.timeout,
            force=args.force,
            dry_run=False,
            show_prompt=False,
        )
    except Exception as exc:  # noqa: BLE001 - surface Gemini/network details
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(status)

    if args.no_write_json:
        print("skipped interview.json update (--no-write-json)")
    else:
        try:
            print(write_explainer_comic_field(interview_file, actual_path))
        except Exception as exc:  # noqa: BLE001 - image is saved; surface JSON issue
            print(f"warning: could not update interview.json: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
