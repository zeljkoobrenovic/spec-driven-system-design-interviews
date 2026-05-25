#!/usr/bin/env python3
"""Generate visual assets for one system-design interview dataset.

Usage:
    GEMINI_API_KEY=... python3 _scripts/generate_interview_assets.py \
        data/book/ticketmaster/interview.json

    # Optional: use different Gemini image models for small icons and 16:9 images.
    GEMINI_API_KEY=... python3 _scripts/generate_interview_assets.py \
        data/book/ticketmaster/interview.json \
        --icon-model gemini-3.1-flash-image-preview \
        --image-model gemini-3-pro-image-preview

The script reads one ``interview.json`` file and creates assets next to it:

  - ``icon.png`` — square overview icon for the interview
  - ``assets/icons/patterns/<slug>.png`` — icons for ``patterns[]`` and
    ``patternCatalog[]`` entries
  - ``assets/icons/concepts/<slug>.png`` — icons for step ``concepts[]``
  - ``assets/images/final-design.png`` — image for final design, if present

Existing files are skipped unless ``--force`` is passed. ``--dry-run`` prints
the planned targets, prompts, and JSON link updates without calling Gemini or
writing images. By default, a non-dry run also updates ``interview.json`` with
relative links to generated or already-existing assets.

Standard-library only, matching the scripts in ``_scripts/examples``.
"""

from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import re
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# DEFAULT_ICON_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_ICON_MODEL = "gemini-3-pro-image-preview"
DEFAULT_IMAGE_MODEL = "gemini-3-pro-image-preview"
DEFAULT_ICON_SIZE = "1K"
DEFAULT_IMAGE_SIZE = "1K"


@dataclass(frozen=True)
class AssetSpec:
    kind: str
    label: str
    path: Path
    prompt: str
    aspect_ratio: str
    image_size: str
    model: str


def endpoint_for(model: str) -> str:
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )


def slugify(value: str, fallback: str = "asset") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or fallback


def compact(value: Any, max_chars: int = 1200) -> str:
    """Convert free-form JSON-ish values into short prompt text."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
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


def item_name(item: Any, fallback: str = "Item") -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("name", "term", "title", "label", "id"):
            if item.get(key):
                return str(item[key])
    return fallback


def load_dataset(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: expected top-level object in {path}")
    return data


def write_dataset(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def node_lookup(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    arch = data.get("highLevelArchitecture") or {}
    for node in arch.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        label = str(node.get("label") or node_id).strip()
        if node_id and node_id not in out:
            out[node_id] = label
    return out


def view_summary(view: Any, labels: dict[str, str]) -> str:
    if not isinstance(view, dict):
        return ""
    node_labels = []
    for ref in view.get("nodes") or []:
        if isinstance(ref, str):
            node_labels.append(labels.get(ref, ref))
        elif isinstance(ref, dict):
            node_id = str(ref.get("id") or "").strip()
            node_labels.append(str(ref.get("label") or labels.get(node_id) or node_id))
    parts = []
    if node_labels:
        parts.append("Nodes: " + ", ".join(node_labels[:14]))
    links = view.get("links") or []
    if links:
        parts.append("Links: " + ", ".join(str(link if isinstance(link, str) else link.get("id", "")) for link in links[:12]))
    return "; ".join(parts)


def icon_prompt(title: str, context: str, kind: str) -> str:
    return "\n".join(
        [
            "Create a small square icon for a system-design interview asset.",
            "Style: minimalist professional line art, bold consistent black outlines, rounded stroke ends, white background.",
            "Use simple geometric architecture symbols. No text, no labels, no logo marks, no border, no frame, no photorealism, no 3D.",
            f"Asset kind: {kind}",
            f"Subject: {title}",
            f"Context: {context}",
        ]
    )


def image_prompt(title: str, context: str, kind: str) -> str:
    return "\n".join(
        [
            "Create a 16:9 visual explainer image for a system design interview walkthrough.",
            "Style: polished flat vector business/technical illustration, crisp outlines, white background, restrained blue/teal/green/orange accents.",
            "Show architecture, workflows, data movement, bottlenecks, or tradeoffs as visual elements.",
            "Avoid dense text. Small readable labels are acceptable only when they clarify components. No article title, no screenshots, no photorealism, no 3D, no fantasy elements.",
            "Leave generous margins so no element touches the image edge.",
            f"Asset kind: {kind}",
            f"Subject: {title}",
            f"Context: {context}",
        ]
    )


def add_unique(specs: list[AssetSpec], seen_paths: set[Path], spec: AssetSpec) -> None:
    key = spec.path
    if key in seen_paths:
        return
    seen_paths.add(key)
    specs.append(spec)


def collect_assets(
    interview_file: Path,
    data: dict[str, Any],
    icon_size: str,
    image_size: str,
    icon_model: str,
    image_model: str,
) -> list[AssetSpec]:
    interview_dir = interview_file.parent
    labels = node_lookup(data)
    title = str(data.get("title") or interview_dir.name)
    description = compact(data.get("description"), 900)
    specs: list[AssetSpec] = []
    seen_paths: set[Path] = set()

    def icon_spec(label: str, rel: str, prompt: str) -> AssetSpec:
        return AssetSpec("icon", label, interview_dir / rel, prompt, "1:1", icon_size, icon_model)

    def image_spec(label: str, rel: str, prompt: str) -> AssetSpec:
        return AssetSpec("image", label, interview_dir / rel, prompt, "16:9", image_size, image_model)

    add_unique(
        specs,
        seen_paths,
        icon_spec(
            "interview icon",
            "icon.png",
            icon_prompt(title, description, "interview overview icon"),
        ),
    )

    for collection_name in ("patterns", "patternCatalog"):
        for item in data.get(collection_name) or []:
            name = item_name(item, collection_name)
            slug = slugify(name, collection_name)
            context = compact(item, 900)
            add_unique(
                specs,
                seen_paths,
                icon_spec(
                    f"{collection_name}: {name}",
                    f"assets/icons/patterns/{slug}.png",
                    icon_prompt(name, context, "design pattern icon"),
                ),
            )

    for step in data.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for concept in step.get("concepts") or []:
            name = item_name(concept, "Concept")
            slug = slugify(name, "concept")
            context = compact(concept, 900)
            add_unique(
                specs,
                seen_paths,
                icon_spec(
                    f"concept: {name}",
                    f"assets/icons/concepts/{slug}.png",
                    icon_prompt(name, context, "concept-introduced icon"),
                ),
            )

    final_design = data.get("finalDesign")
    if isinstance(final_design, dict):
        final_context = "; ".join(
            part
            for part in [
                compact(final_design.get("description"), 900),
                view_summary(final_design.get("view"), labels),
                compact({"options": final_design.get("options")}, 800),
            ]
            if part
        )
        add_unique(
            specs,
            seen_paths,
            image_spec(
                "final design",
                "assets/images/final-design.png",
                image_prompt(str(final_design.get("title") or f"{title} final design"), final_context, "final architecture design"),
            ),
        )

    return specs


def update_asset_links(
    interview_file: Path,
    data: dict[str, Any],
    available_paths: set[Path],
) -> list[str]:
    """Attach asset links to the JSON objects the renderer reads."""
    interview_dir = interview_file.parent
    changes: list[str] = []

    def has(rel: str) -> bool:
        return interview_dir / rel in available_paths

    def set_field(obj: dict[str, Any], key: str, rel: str, label: str) -> None:
        if not has(rel):
            return
        if obj.get(key) == rel:
            return
        obj[key] = rel
        changes.append(f"{label}: {key} -> {rel}")

    def remove_field(obj: dict[str, Any], key: str, label: str) -> None:
        if key not in obj:
            return
        del obj[key]
        changes.append(f"{label}: removed {key}")

    def set_dataset_asset(key: str, rel: str, label: str) -> None:
        if not has(rel):
            return
        assets = data.get("assets")
        if not isinstance(assets, dict):
            assets = {}
            data["assets"] = assets
        set_field(assets, key, rel, label)

    set_dataset_asset("icon", "icon.png", "dataset")
    if isinstance(data.get("assets"), dict):
        for key in ("requirements", "capacityEstimation", "apiDesign"):
            remove_field(data["assets"], key, "dataset assets")

    for collection_name in ("patterns", "patternCatalog"):
        for index, item in enumerate(data.get(collection_name) or []):
            if not isinstance(item, dict):
                continue
            name = item_name(item, collection_name)
            slug = slugify(name, collection_name)
            set_field(
                item,
                "icon",
                f"assets/icons/patterns/{slug}.png",
                f"{collection_name}[{index}] {name}",
            )

    for step_index, step in enumerate(data.get("steps") or []):
        if not isinstance(step, dict):
            continue
        remove_field(step, "image", f"steps[{step_index}] {step.get('title') or step.get('id') or 'step'}")
        for concept_index, concept in enumerate(step.get("concepts") or []):
            if not isinstance(concept, dict):
                continue
            name = item_name(concept, "Concept")
            slug = slugify(name, "concept")
            set_field(
                concept,
                "icon",
                f"assets/icons/concepts/{slug}.png",
                f"steps[{step_index}].concepts[{concept_index}] {name}",
            )

    final_design = data.get("finalDesign")
    if isinstance(final_design, dict):
        set_field(
            final_design,
            "image",
            "assets/images/final-design.png",
            "finalDesign",
        )

    return changes


def call_gemini_image(
    api_key: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    image_size: str,
    timeout: int = 240,
) -> bytes:
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
        f"{endpoint_for(model)}?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
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
    candidates = response.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])

    raise RuntimeError(
        "No image data in Gemini response. Raw response: "
        + json.dumps(response)[:1000]
    )


def process_asset(
    spec: AssetSpec,
    api_key: str | None,
    force: bool,
    dry_run: bool,
    repo_root: Path,
) -> str:
    rel = spec.path.relative_to(repo_root) if spec.path.is_relative_to(repo_root) else spec.path
    if spec.path.exists() and not force:
        return f"skip existing: {rel}"
    if dry_run:
        short_prompt = textwrap.shorten(re.sub(r"\s+", " ", spec.prompt), width=260, placeholder="...")
        return f"dry-run: {rel}\n    prompt: {short_prompt}"
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    image_bytes = call_gemini_image(
        api_key=api_key,
        model=spec.model,
        prompt=spec.prompt,
        aspect_ratio=spec.aspect_ratio,
        image_size=spec.image_size,
    )
    spec.path.parent.mkdir(parents=True, exist_ok=True)
    spec.path.write_bytes(image_bytes)
    return f"generated: {rel}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "interview_json",
        help="Path to a data/<group>/<id>/interview.json file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned assets, prompt summaries, and JSON link updates without API calls or writes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate assets even if the target file already exists.",
    )
    parser.add_argument(
        "--no-update-json",
        action="store_true",
        help="Do not add generated asset links to interview.json after generation.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Deprecated alias: use this model for both icons and 16:9 images unless --icon-model or --image-model is also set.",
    )
    parser.add_argument(
        "--icon-model",
        default=None,
        help=f"Gemini image model for square icons (default: {DEFAULT_ICON_MODEL}).",
    )
    parser.add_argument(
        "--image-model",
        default=None,
        help=f"Gemini image model for 16:9 images (default: {DEFAULT_IMAGE_MODEL}).",
    )
    parser.add_argument(
        "--icon-size",
        default=DEFAULT_ICON_SIZE,
        help=f"Gemini imageSize for square icons (default: {DEFAULT_ICON_SIZE}).",
    )
    parser.add_argument(
        "--image-size",
        default=DEFAULT_IMAGE_SIZE,
        help=f"Gemini imageSize for 16:9 images (default: {DEFAULT_IMAGE_SIZE}).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Seconds to sleep between generated assets (default: 2.0).",
    )
    args = parser.parse_args(argv)

    interview_file = Path(args.interview_json)
    if not interview_file.is_absolute():
        interview_file = (Path.cwd() / interview_file).resolve()
    if not interview_file.is_file():
        print(f"error: no interview.json at {interview_file}", file=sys.stderr)
        return 2
    if interview_file.name != "interview.json":
        print(f"error: expected a file named interview.json, got {interview_file}", file=sys.stderr)
        return 2

    icon_model = args.icon_model or args.model or DEFAULT_ICON_MODEL
    image_model = args.image_model or args.model or DEFAULT_IMAGE_MODEL

    data = load_dataset(interview_file)
    specs = collect_assets(
        interview_file=interview_file,
        data=data,
        icon_size=args.icon_size,
        image_size=args.image_size,
        icon_model=icon_model,
        image_model=image_model,
    )
    api_key = os.environ.get("GEMINI_API_KEY")
    needs_api = any(args.force or not spec.path.exists() for spec in specs)
    if needs_api and not api_key and not args.dry_run:
        print("error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        return 2

    print(f"Processing {interview_file.relative_to(REPO_ROOT) if interview_file.is_relative_to(REPO_ROOT) else interview_file}")
    print(f"Planned assets: {len(specs)}")
    print(f"Icon model: {icon_model}")
    print(f"Image model: {image_model}")

    generated = 0
    skipped = 0
    errors = 0
    for index, spec in enumerate(specs, start=1):
        try:
            print(f"[{index}/{len(specs)}] {spec.kind}: {spec.label}")
            status = process_asset(
                spec=spec,
                api_key=api_key,
                force=args.force,
                dry_run=args.dry_run,
                repo_root=REPO_ROOT,
            )
            print(f"    {status}")
            if status.startswith("generated"):
                generated += 1
                if args.sleep and index < len(specs):
                    time.sleep(args.sleep)
            elif status.startswith("skip"):
                skipped += 1
        except Exception as exc:  # noqa: BLE001 -- keep going asset by asset
            errors += 1
            print(f"    ERROR: {exc}", file=sys.stderr)

    if not args.no_update_json:
        if args.dry_run:
            preview = copy.deepcopy(data)
            planned_paths = {spec.path for spec in specs}
            changes = update_asset_links(interview_file, preview, planned_paths)
            print(f"\nPlanned JSON link updates: {len(changes)}")
            for change in changes:
                print(f"    {change}")
        else:
            available_paths = {spec.path for spec in specs if spec.path.exists()}
            changes = update_asset_links(interview_file, data, available_paths)
            if changes:
                write_dataset(interview_file, data)
            print(f"\nJSON link updates: {len(changes)}")
            for change in changes:
                print(f"    {change}")

    print(f"\nDone. Generated {generated}, skipped {skipped}, errors {errors}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
