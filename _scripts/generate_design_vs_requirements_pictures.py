#!/usr/bin/env python3
"""Generate per-requirement "Design vs. Requirements" illustrations with Gemini.

This is the sibling of ``generate_diagram_picture.py``, specialized for the
Wrap-up **"Design vs. Requirements"** section (the dataset's ``satisfies``
object). For each requirement — every item under ``satisfies.functional`` and
``satisfies.nonFunctional`` — it generates one illustration that visualizes how
the design *meets that requirement* (the requirement on one side, the
mechanism / components that satisfy it on the other), then writes the relative
image path back into that item's ``aiVisual`` field.

Usage:
    # Generate one illustration per requirement in the satisfies section.
    GEMINI_API_KEY=... python3 _scripts/generate_design_vs_requirements_pictures.py \
        data/book/payment-system/interview.json

    # Preview the targets and prompt summaries without API calls.
    python3 _scripts/generate_design_vs_requirements_pictures.py \
        data/book/payment-system/interview.json --dry-run

    # Only one column.
    GEMINI_API_KEY=... python3 _scripts/generate_design_vs_requirements_pictures.py \
        data/book/payment-system/interview.json --include functional

Images are written under ``assets/generated/design-vs-requirements/`` inside the
dataset directory by default. Each file is saved with the extension matching the
image bytes Gemini actually returns (e.g. ``.jpg`` for ``image/jpeg``). After a
successful generation (not in ``--dry-run``, and skipped files keep their
existing path), the dataset-relative image path is written back into the
matching ``satisfies.<column>[<i>].aiVisual`` field. The JSON file is rewritten
once at the end, preserving key order. It does not rebuild ``docs/``.

Standard-library only, matching the other Gemini scripts in ``_scripts``.
"""

from __future__ import annotations

import argparse
import base64
import collections
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

DEFAULT_MODEL = "gemini-3-pro-image-preview"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_IMAGE_SIZE = "4K"
DEFAULT_BATCH_OUTPUT_DIR = Path("assets/generated/design-vs-requirements")

# satisfies columns -> human label used in prompts.
COLUMNS = {
    "functional": "functional requirement",
    "nonFunctional": "non-functional requirement / guarantee",
}


@dataclass(frozen=True)
class DiagramSpec:
    kind: str
    label: str
    path: Path
    prompt: str
    # Sequence of keys / indices locating the field that should receive the
    # generated image's relative path inside the dataset JSON, for example:
    #   ("satisfies", "functional", 0, "aiVisual")
    json_pointer: tuple[Any, ...] | None = None


def endpoint_for(model: str) -> str:
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def dataset_relative_path(image_path: Path, dataset_dir: Path) -> str:
    """Path to store in ``aiVisual`` fields, relative to the dataset directory."""
    try:
        relative = image_path.resolve().relative_to(dataset_dir.resolve())
    except ValueError:
        print(
            f"warning: {rel(image_path)} is not under the dataset directory "
            f"{rel(dataset_dir)}; storing the path as given (renderer expects a "
            "dataset-relative path).",
            file=sys.stderr,
        )
        return image_path.as_posix()
    return relative.as_posix()


def set_json_pointer(root: dict[str, Any], pointer: tuple[Any, ...], value: str) -> None:
    """Set ``value`` at ``pointer`` inside ``root``, creating dict steps as needed."""
    node: Any = root
    for part in pointer[:-1]:
        if isinstance(part, int):
            node = node[part]
        elif part in node:
            node = node[part]
        else:
            child = collections.OrderedDict()
            node[part] = child
            node = child
    node[pointer[-1]] = value


def compact(value: Any, max_chars: int = 1600) -> str:
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
    if not text:
        return ""
    return textwrap.shorten(text, width=max_chars, placeholder="...")


def slugify(value: str, fallback: str = "requirement") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or fallback


def load_dataset(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: expected top-level object in {path}")
    return data


def step_lookup(data: dict[str, Any]) -> dict[str, str]:
    """Map step id -> step title, for naming the steps a requirement cites."""
    titles: dict[str, str] = {}
    for step in data.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("id") or "").strip()
        title = str(step.get("title") or step_id).strip()
        if step_id and step_id not in titles:
            titles[step_id] = title
    return titles


def step_titles(item: dict[str, Any], steps: dict[str, str]) -> list[str]:
    names = []
    for ref in item.get("steps") or []:
        ref_id = str(ref or "").strip()
        if ref_id:
            names.append(steps.get(ref_id, ref_id))
    return names


def build_prompt(
    *,
    system_title: str,
    column_label: str,
    requirement: str,
    how: str,
    related_steps: list[str],
    user_prompt: str,
) -> str:
    """Create an image prompt for a single requirement-satisfaction illustration."""
    parts: list[str] = [
        "Create a high-quality, visually appealing illustration for a system-design "
        "interview walkthrough that shows HOW a specific requirement is satisfied by the design.",
        "The output should feel like a professional technical explainer illustration, not a "
        "Mermaid diagram, not a screenshot, and not a dense whiteboard sketch.",
        "Use a refined flat-vector visual language: crisp outlines, restrained "
        "blue/teal/green/orange accents, white background.",
        "Composition: a clear two-sided 'requirement → how it is met' relationship. Put the "
        "requirement (the goal/guarantee) on one side and the design mechanism / components that "
        "satisfy it on the other, connected by a single dominant arrow or link that reads as "
        "'this design satisfies this requirement'.",
        "Convey satisfaction visually — e.g. a checkmark, a fulfilled-goal motif, or a "
        "matched/connected pairing — without turning the image into a checklist.",
        "Prioritize readability, visual hierarchy, and composition quality over exhaustive completeness.",
        "Use short labels only. Keep labels horizontal, legible, correctly spelled, and inside their "
        "shapes. If a label would be too small or uncertain, omit it rather than inventing text.",
        "Do not show a title of the diagram as text in the image. Do not include watermarks, code "
        "blocks, terminal windows, UI chrome, photorealism, 3D render styling, fantasy elements, "
        "neon cyberpunk styling, or cluttered decoration.",
        "Use icons only where they clearly and specifically relate to the component or concept; do "
        "not use icons as a crutch for missing labels or as generic decoration.",
    ]

    parts.append(f"System under design: {compact(system_title, 200)}")
    parts.append(f"This illustration is about one {column_label}.")
    parts.append("Context:")
    parts.append(f"- Requirement to satisfy: {compact(requirement, 400)}")
    if how:
        parts.append(f"- How the design meets it: {compact(how, 700)}")
    if related_steps:
        parts.append(
            "- Design steps / mechanisms that contribute: "
            + "; ".join(compact(name, 120) for name in related_steps[:8])
        )

    parts.append("Important visual constraints:")
    parts.append("- Focus on this one requirement and the mechanism that satisfies it, not the whole architecture.")
    parts.append("- The relationship between requirement and satisfying mechanism must be the clearest thing in the image.")
    parts.append("- Show just the few components named in 'how'/steps; do not draw the full system topology.")

    if user_prompt:
        parts.append("Additional user prompt:")
        parts.append(compact(user_prompt, 1600))

    parts.append(
        "Final quality bar: the image should be presentation-ready, clean at 16:9, visually polished, "
        "and immediately communicate that the design satisfies this requirement."
    )
    return "\n".join(parts)


def satisfies_specs(
    data: dict[str, Any],
    output_dir: Path,
    include: set[str],
    user_prompt: str,
) -> list[DiagramSpec]:
    satisfies = data.get("satisfies")
    if not isinstance(satisfies, dict):
        return []
    system_title = str(data.get("title") or "System design")
    steps = step_lookup(data)
    specs: list[DiagramSpec] = []

    for column, column_label in COLUMNS.items():
        if column not in include:
            continue
        items = satisfies.get(column)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            requirement = str(item.get("requirement") or "").strip()
            if not requirement:
                continue
            how = str(item.get("how") or "").strip()
            related = step_titles(item, steps)
            prompt = build_prompt(
                system_title=system_title,
                column_label=column_label,
                requirement=requirement,
                how=how,
                related_steps=related,
                user_prompt=user_prompt,
            )
            slug = slugify(requirement, f"req-{index + 1:02d}")
            short_col = "func" if column == "functional" else "nonfunc"
            specs.append(
                DiagramSpec(
                    kind=f"satisfies-{column}",
                    label=f"{column_label}: {requirement}",
                    path=output_dir / f"{short_col}-{index + 1:02d}-{slug}.png",
                    prompt=prompt,
                    json_pointer=("satisfies", column, index, "aiVisual"),
                )
            )
    return specs


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


def process_spec(
    *,
    spec: DiagramSpec,
    api_key: str | None,
    model: str,
    aspect_ratio: str,
    image_size: str,
    timeout: int,
    force: bool,
    dry_run: bool,
    show_prompts: bool,
) -> tuple[str, Path]:
    existing = existing_for_stem(spec.path)
    if existing is not None and not force:
        return f"skip existing: {rel(existing)}", existing
    if dry_run:
        if show_prompts:
            return f"dry-run: {rel(spec.path)}\n\n{spec.prompt}", spec.path
        short_prompt = textwrap.shorten(
            re.sub(r"\s+", " ", spec.prompt),
            width=360,
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


def write_json_updates(
    interview_file: Path,
    updates: list[tuple[tuple[Any, ...], str]],
) -> None:
    data = json.loads(
        interview_file.read_text(encoding="utf-8"),
        object_pairs_hook=collections.OrderedDict,
    )
    for pointer, value in updates:
        set_json_pointer(data, pointer, value)
    interview_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_batch(args: argparse.Namespace, interview_file: Path, user_prompt: str) -> int:
    data = load_dataset(interview_file)
    base_output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else interview_file.parent / DEFAULT_BATCH_OUTPUT_DIR
    )
    if not base_output_dir.is_absolute():
        base_output_dir = (Path.cwd() / base_output_dir).resolve()

    include = set(args.include or list(COLUMNS))
    specs = satisfies_specs(data, base_output_dir, include, user_prompt)
    if not specs:
        print(
            "No requirements found in the dataset's satisfies section "
            "(satisfies.functional / satisfies.nonFunctional)."
        )
        return 0

    api_key = os.environ.get("GEMINI_API_KEY")
    needs_api = any(args.force or existing_for_stem(spec.path) is None for spec in specs)
    if needs_api and not api_key and not args.dry_run:
        print("error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        return 2

    dataset_dir = interview_file.parent

    print(f"Interview: {rel(interview_file)}")
    print(f"Targets: {len(specs)}")
    print(f"Model: {args.model}")
    print(f"Aspect ratio: {args.aspect_ratio}")
    print(f"Image size: {args.image_size}")

    generated = 0
    skipped = 0
    errors = 0
    json_updates: list[tuple[tuple[Any, ...], str]] = []
    for index, spec in enumerate(specs, start=1):
        print(f"[{index}/{len(specs)}] {spec.kind}: {spec.label}")
        try:
            status, actual_path = process_spec(
                spec=spec,
                api_key=api_key,
                model=args.model,
                aspect_ratio=args.aspect_ratio,
                image_size=args.image_size,
                timeout=args.timeout,
                force=args.force,
                dry_run=args.dry_run,
                show_prompts=args.show_prompts,
            )
            print(f"    {status}")
            json_path = dataset_relative_path(actual_path, dataset_dir)
            if status.startswith("generated"):
                generated += 1
                if spec.json_pointer is not None:
                    json_updates.append((spec.json_pointer, json_path))
                if args.sleep and index < len(specs):
                    time.sleep(args.sleep)
            elif status.startswith("skip"):
                skipped += 1
                if spec.json_pointer is not None:
                    json_updates.append((spec.json_pointer, json_path))
            elif status.startswith("dry-run") and spec.json_pointer is not None:
                pointer_text = "/".join(str(part) for part in spec.json_pointer)
                print(f"    would write aiVisual: {pointer_text} = {json_path}")
        except Exception as exc:  # noqa: BLE001 -- keep going target by target
            errors += 1
            print(f"    ERROR: {exc}", file=sys.stderr)

    print(f"\nDone. Generated {generated}, skipped {skipped}, errors {errors}.")

    if args.dry_run:
        print(
            f"dry-run: would write {len([s for s in specs if s.json_pointer is not None])} "
            "aiVisual path(s) into the dataset; JSON left unchanged."
        )
    elif json_updates:
        try:
            write_json_updates(interview_file, json_updates)
            print(f"Wrote {len(json_updates)} aiVisual path(s) into {rel(interview_file)}.")
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"ERROR writing aiVisual paths into {rel(interview_file)}: {exc}", file=sys.stderr)

    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "interview_json",
        help="Path to a data/<group>/<id>/interview.json file with a satisfies section.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help=(
            "Batch output directory. Defaults to "
            "<interview-dir>/assets/generated/design-vs-requirements. The aiVisual paths "
            "written into interview.json are relative to the dataset directory."
        ),
    )
    parser.add_argument(
        "--include",
        action="append",
        choices=sorted(COLUMNS),
        help="Which satisfies columns to generate. Can be repeated. Defaults to both.",
    )
    parser.add_argument(
        "--prompt",
        default="",
        help="Free-form extra prompt text appended to every requirement prompt.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini image model (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--aspect-ratio",
        default=DEFAULT_ASPECT_RATIO,
        help=f"Gemini aspectRatio value (default: {DEFAULT_ASPECT_RATIO}).",
    )
    parser.add_argument(
        "--image-size",
        default=DEFAULT_IMAGE_SIZE,
        help=f"Gemini imageSize value, for example 1K, 2K, or 4K (default: {DEFAULT_IMAGE_SIZE}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="HTTP timeout in seconds (default: 300).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output files that already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the targets and prompts without calling the API or writing files.",
    )
    parser.add_argument(
        "--show-prompts",
        action="store_true",
        help="In dry-run mode, print full prompts instead of one-line summaries.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Seconds to sleep between generated images (default: 2.0).",
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

    return run_batch(args, interview_file, args.prompt)


if __name__ == "__main__":
    raise SystemExit(main())
