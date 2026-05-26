#!/usr/bin/env python3
"""Generate high-quality diagram pictures with Gemini image APIs.

Usage:
    # Generate requirements, capacity, every step, and final design.
    GEMINI_API_KEY=... python3 _scripts/generate_diagram_picture.py \
        data/book/ticketmaster/interview.json

    # Preview the generated targets and prompt summaries without API calls.
    python3 _scripts/generate_diagram_picture.py \
        data/book/ticketmaster/interview.json \
        --dry-run

    # Manual one-off mode is still supported.
    GEMINI_API_KEY=... python3 _scripts/generate_diagram_picture.py \
        --title "Ticketmaster final architecture" \
        --component "Client / Browser" \
        --component "Anti-Abuse / Bot Filter" \
        --component "Waiting Room Queue" \
        --component "Admission Gate" \
        --component "Booking API" \
        --flow "Client is screened, queued, admitted, routed by event, then reserved with seat locks and inventory CAS." \
        --output data/book/ticketmaster/assets/generated/ticketmaster-gemini-diagram.png

    # Preview the exact prompt without calling Gemini or writing files.
    python3 _scripts/generate_diagram_picture.py \
        --title "Checkout state machine" \
        --context "Held seats expire unless checkout verifies and renews the hold." \
        --output /tmp/checkout-diagram.png \
        --dry-run

When passed an ``interview.json`` file, this script reads the dataset and writes
standalone image files under ``assets/generated/diagram-pictures/`` by default.
It does not update ``interview.json``, rebuild ``docs/``, or wire generated
images into the renderer.

Standard-library only, matching the Gemini scripts in ``_scripts/examples``.
"""

from __future__ import annotations

import argparse
import base64
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
DEFAULT_IMAGE_SIZE = "2K"
DEFAULT_BATCH_OUTPUT_DIR = Path("assets/generated/diagram-pictures")

STYLE_NOTES = {
    "architecture-map": [
        "Composition: polished architecture map with a few broad grouped regions.",
        "Arrange components in calm left-to-right or top-to-bottom lanes.",
        "Use rounded component blocks, thin directional arrows, subtle shadows, and generous whitespace.",
    ],
    "flow": [
        "Composition: elegant staged flow diagram with numbered phases.",
        "Show progression clearly from trigger to final outcome, with one dominant path and restrained side notes.",
        "Use simple stage cards, readable arrows, and a strong visual rhythm.",
    ],
    "consistency": [
        "Composition: technical consistency diagram with lifecycle/state-transition emphasis.",
        "Show authoritative state, temporary/derived state, recovery loops, and invariant checks as distinct visual groups.",
        "Make the correctness boundary visually obvious without making the image dense.",
    ],
    "explainer": [
        "Composition: editorial technical explainer poster.",
        "Balance architecture components with a small number of callouts that explain bottlenecks, tradeoffs, or guarantees.",
        "Use a clean visual hierarchy: main path first, supporting systems second, annotations last.",
    ],
}


@dataclass(frozen=True)
class DiagramSpec:
    kind: str
    label: str
    path: Path
    prompt: str
    mode: str


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


def slugify(value: str, fallback: str = "diagram") -> str:
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


def read_prompt_file(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"error: no prompt file at {path}")
    return path.read_text(encoding="utf-8").strip()


def node_lookup(data: dict[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    arch = data.get("highLevelArchitecture") or {}
    for node in arch.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        label = str(node.get("label") or node_id).strip()
        if node_id and node_id not in labels:
            labels[node_id] = label
    return labels


def link_lookup(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    links: dict[str, dict[str, Any]] = {}
    arch = data.get("highLevelArchitecture") or {}
    for link in arch.get("links") or []:
        if not isinstance(link, dict):
            continue
        link_id = str(link.get("id") or "").strip()
        if link_id:
            links[link_id] = link
    return links


def label_for_node(ref: Any, labels: dict[str, str]) -> str:
    if isinstance(ref, str):
        return labels.get(ref, ref)
    if isinstance(ref, dict):
        node_id = str(ref.get("id") or "").strip()
        return str(ref.get("label") or labels.get(node_id) or node_id).strip()
    return ""


def view_components(view: Any, labels: dict[str, str], limit: int = 12) -> list[str]:
    if not isinstance(view, dict):
        return []
    components = []
    for ref in view.get("nodes") or []:
        label = label_for_node(ref, labels)
        if label:
            components.append(label)
    return components[:limit]


def describe_link(link: Any, labels: dict[str, str], links: dict[str, dict[str, Any]]) -> str:
    if isinstance(link, str):
        link = links.get(link, {"id": link})
    if not isinstance(link, dict):
        return ""
    source = labels.get(str(link.get("from") or ""), str(link.get("from") or ""))
    target = labels.get(str(link.get("to") or ""), str(link.get("to") or ""))
    label = str(link.get("label") or "").strip()
    description = str(link.get("description") or "").strip()
    if source and target and label:
        return f"{source} -> {target}: {label}"
    if source and target:
        return f"{source} -> {target}"
    if description:
        return description
    return str(link.get("id") or "").strip()


def view_flows(
    view: Any,
    labels: dict[str, str],
    links: dict[str, dict[str, Any]],
    limit: int = 12,
) -> list[str]:
    if not isinstance(view, dict):
        return []
    flows = []
    for link in view.get("links") or []:
        description = describe_link(link, labels, links)
        if description:
            flows.append(description)
    return flows[:limit]


def view_caption(view: Any) -> str:
    if isinstance(view, dict):
        return str(view.get("caption") or "").strip()
    return ""


def list_items(title: str, items: Any, limit: int = 8) -> str:
    if not isinstance(items, list) or not items:
        return ""
    values = [compact(item, 260) for item in items if compact(item, 260)]
    if not values:
        return ""
    return f"{title}: " + "; ".join(values[:limit])


def item_name(item: Any, fallback: str = "item") -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("name", "term", "title", "label", "issue", "trap", "id"):
            if item.get(key):
                return str(item[key])
    return fallback


def infer_step_mode(step: dict[str, Any]) -> str:
    text = " ".join(
        str(step.get(key) or "")
        for key in ("id", "title", "description", "decisionPrompt")
    ).lower()
    if any(word in text for word in ("checkout", "state machine", "expiry", "consistency", "overbooking", "counter")):
        return "consistency"
    if any(word in text for word in ("waiting", "admission", "flow", "route", "scale", "anti-abuse")):
        return "flow"
    return "architecture-map"


def requirements_spec(
    data: dict[str, Any],
    output_dir: Path,
) -> DiagramSpec | None:
    requirements = data.get("requirements")
    if not isinstance(requirements, dict):
        return None
    title = str(data.get("title") or "System design")
    context = [
        compact(data.get("description"), 900),
        list_items("Functional requirements", requirements.get("functional"), 10),
        list_items("Non-functional requirements", requirements.get("nonFunctional"), 10),
    ]
    constraints = [
        "Make functional requirements and non-functional guarantees visually distinct.",
        "Emphasize user goals, correctness guarantees, fairness/abuse resistance, latency, and graceful overload handling.",
        "Use only a handful of short labels; avoid copying the full requirement list into the image.",
    ]
    prompt = build_prompt(
        title=f"{title} requirements",
        context=[item for item in context if item],
        components=[],
        flows=[],
        constraints=constraints,
        mode="explainer",
        user_prompt="Create an attractive requirements overview visual, not an architecture topology.",
    )
    return DiagramSpec(
        kind="requirements",
        label="Requirements",
        path=output_dir / "requirements.png",
        prompt=prompt,
        mode="explainer",
    )


def capacity_spec(
    data: dict[str, Any],
    output_dir: Path,
) -> DiagramSpec | None:
    capacity = data.get("capacity")
    if not isinstance(capacity, list) or not capacity:
        return None
    title = str(data.get("title") or "System design")
    metrics = []
    for item in capacity:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip()
        note = str(item.get("note") or "").strip()
        if label and value:
            metrics.append(f"{label}: {value}. {note}".strip())
    prompt = build_prompt(
        title=f"{title} capacity planning",
        context=[
            compact(data.get("description"), 700),
            "Key scale assumptions: " + "; ".join(metrics[:12]),
        ],
        components=[],
        flows=[
            "Show demand entering the system, narrowing through admission/backpressure, and protecting scarce/correctness-critical capacity.",
            "Represent reads, writes, external bottlenecks, and correctness targets as visually separate capacity concerns.",
        ],
        constraints=[
            "Use metric tiles, flow width, or visual scale cues instead of a dense table.",
            "Preserve the most important numbers, but do not overcrowd the image with every note.",
            "Make bottlenecks and protection points obvious.",
        ],
        mode="explainer",
        user_prompt="Create a capacity-planning visual with polished infographic quality.",
    )
    return DiagramSpec(
        kind="capacity",
        label="Capacity planning",
        path=output_dir / "capacity-planning.png",
        prompt=prompt,
        mode="explainer",
    )


def step_spec(
    data: dict[str, Any],
    step: dict[str, Any],
    index: int,
    output_dir: Path,
    labels: dict[str, str],
    links: dict[str, dict[str, Any]],
) -> DiagramSpec:
    title = str(step.get("title") or step.get("id") or f"Step {index}")
    view = step.get("view")
    context = [
        compact(data.get("description"), 500),
        compact(step.get("description"), 900),
        compact(view_caption(view), 700),
        compact({"decisionPrompt": step.get("decisionPrompt")}, 500),
        list_items("Patterns", step.get("patterns"), 6),
        list_items("Why now", step.get("whyNow"), 4),
        list_items("Bottlenecks", step.get("bottlenecks"), 5),
        list_items("Common traps", step.get("traps"), 4),
    ]
    mode = infer_step_mode(step)
    prompt = build_prompt(
        title=title,
        context=[item for item in context if item],
        components=view_components(view, labels, 14),
        flows=view_flows(view, labels, links, 14),
        constraints=[
            "Focus on this single design step, not the entire final architecture.",
            "Show what changed or became important in this step.",
            "Use visual emphasis for highlighted or newly introduced components when that is clear from context.",
        ],
        mode=mode,
        user_prompt="Create a polished alternative to the step Mermaid diagram.",
    )
    step_id = slugify(str(step.get("id") or title), f"step-{index:02d}")
    return DiagramSpec(
        kind="step",
        label=title,
        path=output_dir / "steps" / f"{index:02d}-{step_id}.png",
        prompt=prompt,
        mode=mode,
    )


def final_design_spec(
    data: dict[str, Any],
    output_dir: Path,
    labels: dict[str, str],
    links: dict[str, dict[str, Any]],
) -> DiagramSpec | None:
    final_design = data.get("finalDesign")
    if not isinstance(final_design, dict):
        return None
    title = str(final_design.get("title") or f"{data.get('title') or 'System design'} final design")
    view = final_design.get("view")
    prompt = build_prompt(
        title=title,
        context=[
            compact(data.get("description"), 500),
            compact(final_design.get("description"), 1100),
            compact(view_caption(view), 700),
        ],
        components=view_components(view, labels, 22),
        flows=view_flows(view, labels, links, 22),
        constraints=[
            "This is the end-to-end design, so show the major regions and lifecycle clearly.",
            "Group related systems into readable zones rather than placing every node equally.",
            "Make browse/read path, write/reservation path, asynchronous/recovery path, and external dependencies visually distinct when present.",
        ],
        mode="architecture-map",
        user_prompt="Create the flagship final architecture visual with high production quality.",
    )
    return DiagramSpec(
        kind="final-design",
        label=title,
        path=output_dir / "final-design.png",
        prompt=prompt,
        mode="architecture-map",
    )


def collect_interview_specs(
    interview_file: Path,
    output_dir_arg: str,
    include: set[str],
) -> list[DiagramSpec]:
    data = load_dataset(interview_file)
    base_output_dir = Path(output_dir_arg) if output_dir_arg else interview_file.parent / DEFAULT_BATCH_OUTPUT_DIR
    if not base_output_dir.is_absolute():
        base_output_dir = (Path.cwd() / base_output_dir).resolve()

    labels = node_lookup(data)
    links = link_lookup(data)
    specs: list[DiagramSpec] = []

    if "requirements" in include:
        spec = requirements_spec(data, base_output_dir)
        if spec:
            specs.append(spec)
    if "capacity" in include:
        spec = capacity_spec(data, base_output_dir)
        if spec:
            specs.append(spec)
    if "steps" in include:
        for index, step in enumerate(data.get("steps") or [], start=1):
            if isinstance(step, dict):
                specs.append(step_spec(data, step, index, base_output_dir, labels, links))
    if "final" in include:
        spec = final_design_spec(data, base_output_dir, labels, links)
        if spec:
            specs.append(spec)

    return specs


def build_prompt(
    *,
    title: str,
    context: list[str],
    components: list[str],
    flows: list[str],
    constraints: list[str],
    mode: str,
    user_prompt: str,
) -> str:
    """Create a production-oriented image prompt for a diagram picture."""
    parts: list[str] = [
        "Create a high-quality visually appealing diagram picture for a system-design interview walkthrough.",
        "The output should feel like a professional technical explainer illustration, not a Mermaid diagram, not a screenshot, and not a dense whiteboard sketch.",
        "Use a refined flat-vector visual language: crisp outlines, restrained blue/teal/green/orange accents, white background, subtle depth.",
        "Prioritize readability, visual hierarchy, and composition quality over exhaustive completeness.",
        "Use short labels only. Keep labels horizontal, legible, correctly spelled, and inside their shapes. If a label would be too small or uncertain, omit it rather than inventing text.",
        "Do not include the article title as visible text. Do not include watermarks, code blocks, terminal windows, UI chrome, photorealism, 3D render styling, fantasy elements, neon cyberpunk styling, or cluttered decoration.",
    ]
    parts.extend(STYLE_NOTES[mode])

    if title:
        parts.append(f"Subject: {compact(title, 240)}")
    if context:
        parts.append("Context:")
        parts.extend(f"- {compact(item, 700)}" for item in context if item.strip())
    if components:
        parts.append("Component labels to use when they fit:")
        parts.extend(f"- {compact(item, 120)}" for item in components if item.strip())
    if flows:
        parts.append("Relationships or flows to show:")
        parts.extend(f"- {compact(item, 420)}" for item in flows if item.strip())
    if constraints:
        parts.append("Important visual constraints:")
        parts.extend(f"- {compact(item, 420)}" for item in constraints if item.strip())
    if user_prompt:
        parts.append("Additional user prompt:")
        parts.append(compact(user_prompt, 1600))

    parts.append(
        "Final quality bar: the image should be presentation-ready, clean at 16:9, visually polished, and useful as an alternative to a Mermaid architecture diagram."
    )
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


def warn_if_extension_mismatch(output: Path, mime_type: str) -> None:
    suffix = output.suffix.lower()
    expected = {
        "image/png": {".png"},
        "image/jpeg": {".jpg", ".jpeg"},
        "image/jpg": {".jpg", ".jpeg"},
        "image/webp": {".webp"},
    }.get(mime_type.lower())
    if expected and suffix and suffix not in expected:
        print(
            f"warning: Gemini returned {mime_type}, but output extension is {suffix}. "
            "The file bytes were saved as returned.",
            file=sys.stderr,
        )


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
) -> str:
    if spec.path.exists() and not force:
        return f"skip existing: {rel(spec.path)}"
    if dry_run:
        if show_prompts:
            return f"dry-run: {rel(spec.path)}\n\n{spec.prompt}"
        short_prompt = textwrap.shorten(
            re.sub(r"\s+", " ", spec.prompt),
            width=360,
            placeholder="...",
        )
        return f"dry-run: {rel(spec.path)}\n    prompt: {short_prompt}"
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
    spec.path.parent.mkdir(parents=True, exist_ok=True)
    spec.path.write_bytes(image_bytes)
    warn_if_extension_mismatch(spec.path, mime_type)
    return f"generated: {rel(spec.path)} ({mime_type}, {len(image_bytes)} bytes)"


def run_batch(args: argparse.Namespace, interview_file: Path, user_prompt: str) -> int:
    include = set(args.include or ["requirements", "capacity", "steps", "final"])
    specs = collect_interview_specs(interview_file, args.output_dir, include)
    if user_prompt:
        specs = [
            DiagramSpec(
                kind=spec.kind,
                label=spec.label,
                path=spec.path,
                prompt=spec.prompt + "\n\nAdditional global instruction:\n" + compact(user_prompt, 1600),
                mode=spec.mode,
            )
            for spec in specs
        ]
    if not specs:
        print("No diagram targets found.")
        return 0

    api_key = os.environ.get("GEMINI_API_KEY")
    needs_api = any(args.force or not spec.path.exists() for spec in specs)
    if needs_api and not api_key and not args.dry_run:
        print("error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        return 2

    print(f"Interview: {rel(interview_file)}")
    print(f"Targets: {len(specs)}")
    print(f"Model: {args.model}")
    print(f"Aspect ratio: {args.aspect_ratio}")
    print(f"Image size: {args.image_size}")

    generated = 0
    skipped = 0
    errors = 0
    for index, spec in enumerate(specs, start=1):
        print(f"[{index}/{len(specs)}] {spec.kind}: {spec.label}")
        try:
            status = process_spec(
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
            if status.startswith("generated"):
                generated += 1
                if args.sleep and index < len(specs):
                    time.sleep(args.sleep)
            elif status.startswith("skip"):
                skipped += 1
        except Exception as exc:  # noqa: BLE001 -- keep going target by target
            errors += 1
            print(f"    ERROR: {exc}", file=sys.stderr)

    print(f"\nDone. Generated {generated}, skipped {skipped}, errors {errors}.")
    return 1 if errors else 0


def run_manual(args: argparse.Namespace, user_prompt: str) -> int:
    has_prompt_input = any(
        [
            args.title.strip(),
            args.context,
            args.component,
            args.flow,
            args.constraint,
            user_prompt.strip(),
        ]
    )
    if not has_prompt_input:
        print(
            "error: provide an interview.json path, or at least one of --title, --context, --component, --flow, --constraint, --prompt, or --prompt-file.",
            file=sys.stderr,
        )
        return 2
    if not args.output:
        print("error: --output is required in manual one-off mode.", file=sys.stderr)
        return 2

    output = Path(args.output)
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()

    prompt = build_prompt(
        title=args.title,
        context=args.context,
        components=args.component,
        flows=args.flow,
        constraints=args.constraint,
        mode=args.mode,
        user_prompt=user_prompt,
    )

    spec = DiagramSpec(
        kind="manual",
        label=args.title or "Manual diagram",
        path=output,
        prompt=prompt,
        mode=args.mode,
    )

    print(f"Output: {rel(output)}")
    print(f"Model: {args.model}")
    print(f"Aspect ratio: {args.aspect_ratio}")
    print(f"Image size: {args.image_size}")

    if args.dry_run:
        print("\nPrompt:\n")
        print(prompt)
        return 0

    if output.exists() and not args.force:
        print(f"error: output already exists: {rel(output)} (use --force to overwrite)", file=sys.stderr)
        return 2

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        return 2

    status = process_spec(
        spec=spec,
        api_key=api_key,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        image_size=args.image_size,
        timeout=args.timeout,
        force=args.force,
        dry_run=False,
        show_prompts=False,
    )
    print(status)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "interview_json",
        nargs="?",
        help="Optional path to a data/<group>/<id>/interview.json file. When present, batch mode generates requirements, capacity, steps, and final-design images.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Where to save the generated image in manual one-off mode.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Batch output directory. Defaults to <interview-dir>/assets/generated/diagram-pictures.",
    )
    parser.add_argument(
        "--include",
        action="append",
        choices=["requirements", "capacity", "steps", "final"],
        help="Batch sections to generate. Can be repeated. Defaults to all sections.",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Short subject for the diagram. This is prompt context, not visible title text.",
    )
    parser.add_argument(
        "--context",
        action="append",
        default=[],
        help="Additional context paragraph. Can be repeated.",
    )
    parser.add_argument(
        "--component",
        action="append",
        default=[],
        help="Component label to include if it fits. Can be repeated.",
    )
    parser.add_argument(
        "--flow",
        action="append",
        default=[],
        help="Relationship, data movement, lifecycle, or decision flow to show. Can be repeated.",
    )
    parser.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Important visual or architectural constraint to respect. Can be repeated.",
    )
    parser.add_argument(
        "--prompt",
        default="",
        help="Free-form extra prompt text appended after the structured fields.",
    )
    parser.add_argument(
        "--prompt-file",
        default="",
        help="Read free-form extra prompt text from a UTF-8 file.",
    )
    parser.add_argument(
        "--mode",
        choices=sorted(STYLE_NOTES),
        default="architecture-map",
        help="Diagram composition mode (default: architecture-map).",
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
        help="Overwrite the output file if it already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Gemini model/config and full prompt without calling the API or writing files.",
    )
    parser.add_argument(
        "--show-prompts",
        action="store_true",
        help="In batch dry-run mode, print full prompts instead of one-line summaries.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Seconds to sleep between generated batch images (default: 2.0).",
    )
    args = parser.parse_args(argv)

    user_prompt = args.prompt
    if args.prompt_file:
        file_prompt = read_prompt_file(Path(args.prompt_file))
        user_prompt = "\n".join(part for part in [user_prompt, file_prompt] if part)

    if args.interview_json:
        interview_file = Path(args.interview_json)
        if not interview_file.is_absolute():
            interview_file = (Path.cwd() / interview_file).resolve()
        if not interview_file.is_file():
            print(f"error: no interview.json at {interview_file}", file=sys.stderr)
            return 2
        if interview_file.name != "interview.json":
            print(f"error: expected a file named interview.json, got {interview_file}", file=sys.stderr)
            return 2
        return run_batch(args, interview_file, user_prompt)

    return run_manual(args, user_prompt)


if __name__ == "__main__":
    raise SystemExit(main())
