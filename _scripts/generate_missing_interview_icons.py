#!/usr/bin/env python3
"""Generate only missing interview overview icons.

Usage:
    GEMINI_API_KEY=... python3 _scripts/generate_missing_interview_icons.py

    # Preview the datasets that would get data/<group>/<id>/icon.png
    python3 _scripts/generate_missing_interview_icons.py --dry-run

The script scans data/*/*/interview.json, finds interviews whose sibling
icon.png is missing, generates only that square overview icon, and writes
assets.icon = "icon.png" into the corresponding interview.json.

It intentionally does not generate pattern icons, concept icons, or final-design
images. Existing icon.png files are never regenerated.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import textwrap
import time
from pathlib import Path

import generate_interview_assets as assets

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_ROOT = REPO_ROOT / "data"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def find_interview_files(data_root: Path, groups: list[str]) -> list[Path]:
    if groups:
        files: list[Path] = []
        for group in groups:
            group_dir = data_root / group
            if not group_dir.is_dir():
                raise SystemExit(f"error: data group does not exist: {rel(group_dir)}")
            files.extend(sorted(group_dir.glob("*/interview.json")))
        return sorted(files)
    return sorted(data_root.glob("*/*/interview.json"))


def missing_icon_files(interview_files: list[Path]) -> list[Path]:
    return [
        interview_file
        for interview_file in interview_files
        if not (interview_file.parent / "icon.png").is_file()
    ]


def make_icon_spec(interview_file: Path, model: str, size: str) -> assets.AssetSpec:
    data = assets.load_dataset(interview_file)
    title = str(data.get("title") or interview_file.parent.name)
    description = assets.compact(data.get("description"), 900)
    return assets.AssetSpec(
        kind="icon",
        label=f"{title} overview icon",
        path=interview_file.parent / "icon.png",
        prompt=assets.icon_prompt(title, description, "interview overview icon"),
        aspect_ratio="1:1",
        image_size=size,
        model=model,
    )


def write_icon_link(interview_file: Path) -> bool:
    data = assets.load_dataset(interview_file)
    current = data.get("assets")
    if not isinstance(current, dict):
        current = {}
        data["assets"] = current
    if current.get("icon") == "icon.png":
        return False
    current["icon"] = "icon.png"
    assets.write_dataset(interview_file, data)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "groups",
        nargs="*",
        help="Optional data group names to scan, for example: book examples. Defaults to all data groups.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print missing icon targets and prompt summaries without API calls or writes.",
    )
    parser.add_argument(
        "--model",
        default=assets.DEFAULT_ICON_MODEL,
        help=f"Gemini image model for square icons (default: {assets.DEFAULT_ICON_MODEL}).",
    )
    parser.add_argument(
        "--icon-size",
        default=assets.DEFAULT_ICON_SIZE,
        help=f"Gemini imageSize for square icons (default: {assets.DEFAULT_ICON_SIZE}).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Seconds to sleep between generated icons (default: 2.0).",
    )
    parser.add_argument(
        "--no-update-json",
        action="store_true",
        help='Do not write assets.icon = "icon.png" after generating icons.',
    )
    args = parser.parse_args(argv)

    if not DEFAULT_DATA_ROOT.is_dir():
        print(f"error: no data directory at {rel(DEFAULT_DATA_ROOT)}", file=sys.stderr)
        return 2

    interview_files = find_interview_files(DEFAULT_DATA_ROOT, args.groups)
    targets = missing_icon_files(interview_files)

    print(f"Scanned interviews: {len(interview_files)}")
    print(f"Missing icon.png: {len(targets)}")
    if not targets:
        print("Nothing to generate.")
        return 0

    specs = [make_icon_spec(path, args.model, args.icon_size) for path in targets]
    if args.dry_run:
        for index, spec in enumerate(specs, start=1):
            short_prompt = textwrap.shorten(
                re.sub(r"\s+", " ", spec.prompt),
                width=260,
                placeholder="...",
            )
            print(f"[{index}/{len(specs)}] dry-run: {rel(spec.path)}")
            print(f"    prompt: {short_prompt}")
        if not args.no_update_json:
            print(f"\nPlanned JSON link updates: {len(specs)}")
            for interview_file in targets:
                print(f"    {rel(interview_file)}: assets.icon -> icon.png")
        return 0

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        return 2

    generated = 0
    errors = 0
    json_updates = 0
    for index, spec in enumerate(specs, start=1):
        print(f"[{index}/{len(specs)}] {rel(spec.path)}")
        try:
            status = assets.process_asset(
                spec=spec,
                api_key=api_key,
                force=False,
                dry_run=False,
                repo_root=REPO_ROOT,
            )
            print(f"    {status}")
            if status.startswith("generated"):
                generated += 1
            if not args.no_update_json and spec.path.is_file():
                if write_icon_link(spec.path.parent / "interview.json"):
                    json_updates += 1
                    print("    updated JSON: assets.icon -> icon.png")
            if args.sleep and index < len(specs):
                time.sleep(args.sleep)
        except Exception as exc:  # noqa: BLE001 -- keep going dataset by dataset
            errors += 1
            print(f"    ERROR: {exc}", file=sys.stderr)

    print(f"\nDone. Generated {generated}, JSON updates {json_updates}, errors {errors}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
