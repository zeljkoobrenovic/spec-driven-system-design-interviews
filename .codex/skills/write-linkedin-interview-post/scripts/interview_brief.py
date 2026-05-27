#!/usr/bin/env python3
"""Print a compact briefing for drafting Spec-Driven System Design posts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_PUBLIC_BASE = "https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews"
DEFAULT_GITHUB_URL = "https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews"


def one_line(value: object) -> str:
    return " ".join(str(value or "").split())


def chip_name(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("name") or "")
    return ""


def limited(items: list[str], count: int = 5) -> str:
    values = [item for item in items if item]
    if len(values) <= count:
        return ", ".join(values)
    return ", ".join(values[:count]) + ", ..."


def find_repo(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "data").is_dir() and (candidate / "build.py").exists():
            return candidate
    return current


def parse_interview_url(url: str) -> tuple[str | None, str | None, str | None]:
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    group = None
    if len(path_parts) >= 2 and path_parts[-1] == "interview.html":
        group = path_parts[-2]

    dataset_id = None
    entry = None
    if parsed.fragment:
        fragment_parts = [part for part in parsed.fragment.split("/") if part]
        if fragment_parts:
            dataset_id = fragment_parts[0]
        if len(fragment_parts) > 1:
            entry = fragment_parts[1]

    return group, dataset_id, entry


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def manifest_info(repo: Path, group: str, dataset_id: str) -> tuple[str | None, str | None]:
    manifest_path = repo / "data" / group / "index.json"
    if not manifest_path.exists():
        return None, None

    manifest = load_json(manifest_path)
    for category in manifest.get("groups", []):
        for dataset in category.get("datasets", []):
            if dataset.get("id") == dataset_id:
                return category.get("name"), dataset.get("name")
    return None, None


def source_path(repo: Path, group: str, dataset_id: str) -> Path:
    direct = repo / "data" / group / dataset_id / "interview.json"
    if direct.exists():
        return direct
    raise FileNotFoundError(f"Could not find interview source: {direct}")


def print_list(title: str, values: list[str], max_items: int) -> None:
    if not values:
        return
    print(f"\n## {title}")
    for value in values[:max_items]:
        print(f"- {one_line(value)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--group", help="Dataset group, for example book or examples.")
    parser.add_argument("--id", dest="dataset_id", help="Dataset id, for example simple-web-application.")
    parser.add_argument("--entry", help="Optional entry slug for the published URL.")
    parser.add_argument("--url", help="Published interview URL to parse.")
    parser.add_argument("--public-base", default=DEFAULT_PUBLIC_BASE)
    parser.add_argument("--github-url", default=DEFAULT_GITHUB_URL)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--max-tech-concerns", type=int, default=10)
    args = parser.parse_args()

    group = args.group
    dataset_id = args.dataset_id
    entry = args.entry
    if args.url:
        parsed_group, parsed_dataset_id, parsed_entry = parse_interview_url(args.url)
        group = group or parsed_group
        dataset_id = dataset_id or parsed_dataset_id
        entry = entry or parsed_entry

    if not group or not dataset_id:
        parser.error("Provide --group and --id, or pass a published interview --url.")

    repo = find_repo(Path(args.repo))
    interview_path = source_path(repo, group, dataset_id)
    data = load_json(interview_path)
    category_name, manifest_name = manifest_info(repo, group, dataset_id)

    base = args.public_base.rstrip("/")
    public_url = f"{base}/{group}/interview.html#{dataset_id}"
    if entry:
        public_url = f"{public_url}/{entry}"
    index_url = f"{base}/{group}/index.html"

    title = data.get("title") or manifest_name or dataset_id
    print("# LinkedIn Post Briefing")
    print(f"\n- Interview: {title}")
    print(f"- Dataset: {dataset_id}")
    print(f"- Group: {group}")
    if category_name:
        print(f"- Category: {category_name}")
    print(f"- Source: {interview_path.relative_to(repo)}")
    print(f"- Published interview: {public_url}")
    print(f"- More examples/catalog: {index_url}")
    print(f"- Source code: {args.github_url}")

    requirements = data.get("requirements") or {}
    print_list("Functional Requirements", requirements.get("functional") or [], 4)
    print_list("Non-Functional Requirements", requirements.get("nonFunctional") or [], 4)

    capacity = data.get("capacity") or []
    if capacity:
        print("\n## Scale Signals")
        for item in capacity[:6]:
            label = item.get("label")
            value = item.get("value")
            note = item.get("note")
            print(f"- {one_line(label)}: {one_line(value)}" + (f" - {one_line(note)}" if note else ""))

    steps = data.get("steps") or []
    if steps:
        print("\n## Interview Journey")
        for step in steps[: args.max_steps]:
            print(f"- {one_line(step.get('title'))}: {one_line(step.get('description'))}")

    final_design = data.get("finalDesign") or {}
    if final_design:
        print("\n## Final Design")
        if final_design.get("title"):
            print(f"- Title: {one_line(final_design.get('title'))}")
        if final_design.get("description"):
            print(f"- Description: {one_line(final_design.get('description'))}")

    tech_choices = data.get("technologyChoices") or []
    if tech_choices:
        print("\n## Technology Angles")
        for choice in tech_choices[: args.max_tech_concerns]:
            self_hosted = [chip_name(item) for item in choice.get("selfHosted") or []]
            cloud = choice.get("cloud") or {}
            cloud_items = []
            for provider in ("aws", "gcp", "azure"):
                cloud_items.extend(chip_name(item) for item in cloud.get(provider) or [])
            print(f"- {one_line(choice.get('concern'))}")
            if self_hosted:
                print(f"  Self-hosted examples: {limited(self_hosted)}")
            if cloud_items:
                print(f"  Managed/cloud examples: {limited(cloud_items, 8)}")
            if choice.get("tradeoff"):
                print(f"  Trade-off: {one_line(choice.get('tradeoff'))}")
            if choice.get("makesIrrelevant"):
                print(f"  Modern shortcut: {one_line(choice.get('makesIrrelevant'))}")

    print("\n## Suggested Post Angles")
    print("- Basics are not beginner material; they are the load-bearing mental model for larger designs.")
    print("- Show the design as a progression: isolate bottlenecks, remove single points of failure, then automate operations.")
    print("- Connect each classic move to today's implementation choices, but keep the interview focused on trade-offs.")
    print("- Use the interactive walkthrough as the call to action, then point readers to the catalog and source code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
