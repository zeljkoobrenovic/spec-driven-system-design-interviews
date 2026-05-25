#!/usr/bin/env python3
"""Build the static site(s) from sources into docs/.

Source of truth:
  _templates/        shared shell: overview (index.html + overview.js), explorer
                     (interview.html + interview.js), styles.css, icons/
  data/<group>/      one dataset group per directory; each group that is meant
                     to be published has an index.json manifest plus one
                     subdirectory per dataset (<id>/interview.json, etc.)

Output (regenerated, never hand-edited):
  docs/<group>/                  the shared template files, copied verbatim
  docs/<group>/data/             the group's datasets + index.json

Each published group becomes an independent, deployable single-page site:
docs/<group>/index.html fetches docs/<group>/data/index.json at runtime, so
the data must sit next to the page as a sibling `data/` directory.

A group is published only if data/<group>/index.json exists. Groups without
one (e.g. planning/notes folders) are skipped with a notice.

Usage:
  python3 build.py            # build every publishable group
  python3 build.py examples   # build only the named group(s)
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "_templates"
DATA = ROOT / "data"
DOCS = ROOT / "docs"

# Files the templates must contain for a build to make sense.
# The overview page (index.html + overview.js) links to the per-interview
# explorer (interview.html + interview.js); styles.css is shared by both.
REQUIRED_TEMPLATE_FILES = (
    "index.html",
    "interview.html",
    "styles.css",
    "interview.js",
    "overview.js",
)


# File extensions that are authoring/review notes or build helpers — kept in
# the repo next to datasets but never copied into the deployed docs/ output.
NON_DATA_SUFFIXES = (".md", ".markdown", ".py", ".mjs")


def _ignore_non_data(dirpath, names):
    """copytree ignore callback: skip Markdown notes and build helpers."""
    return [n for n in names if n.lower().endswith(NON_DATA_SUFFIXES)]


def _ignore_template_docs(dirpath, names):
    """copytree ignore callback for _templates/: skip developer docs (README,
    other Markdown) so they don't ship into the deployed docs/<group>/ sites."""
    return [n for n in names if n.lower().endswith((".md", ".markdown"))]


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def discover_groups():
    """Return sorted list of group dirs under data/ that have an index.json."""
    if not DATA.is_dir():
        fail(f"missing data directory: {DATA}")
    groups = []
    for child in sorted(DATA.iterdir()):
        if not child.is_dir():
            continue
        if (child / "index.json").is_file():
            groups.append(child.name)
        else:
            print(f"  skip {child.name}/ (no index.json — not publishable yet)")
    return groups


def build_group(group):
    src_data = DATA / group
    out = DOCS / group
    out_data = out / "data"

    # Start clean so renamed/removed datasets don't linger in the output.
    if out.exists():
        shutil.rmtree(out)

    # 1. Shared template shell — the whole _templates/ tree (both pages, their
    #    JS, styles.css, plus icons/ and any other assets). Developer docs
    #    (README.md) are skipped — they belong in the repo, not the site.
    shutil.copytree(TEMPLATES, out, ignore=_ignore_template_docs)
    out_data.mkdir(parents=True)

    # 2. The group's data (manifest + every dataset subdir). Authoring/review
    #    notes (Markdown) and build helpers (.py/.mjs) live alongside the data
    #    for reference but must NOT ship to the deployed site, so they're
    #    skipped during the copy. Everything else (interview.json, icon.png, …)
    #    is copied.
    shutil.copy2(src_data / "index.json", out_data / "index.json")
    for entry in sorted(src_data.iterdir()):
        if entry.is_dir():
            shutil.copytree(entry, out_data / entry.name, ignore=_ignore_non_data)

    dataset_count = sum(1 for e in out_data.iterdir() if e.is_dir())
    print(f"  built docs/{group}/  ({dataset_count} datasets)")


def main(argv):
    if not TEMPLATES.is_dir():
        fail(f"missing templates directory: {TEMPLATES}")
    for name in REQUIRED_TEMPLATE_FILES:
        if not (TEMPLATES / name).is_file():
            fail(f"missing required template file: {TEMPLATES / name}")

    requested = argv[1:]
    available = discover_groups()
    if not available:
        fail("no publishable groups found under data/ (need an index.json)")

    if requested:
        unknown = [g for g in requested if g not in available]
        if unknown:
            fail(
                f"unknown/unpublishable group(s): {', '.join(unknown)}. "
                f"available: {', '.join(available)}"
            )
        groups = requested
    else:
        groups = available

    print(f"Building {len(groups)} group(s): {', '.join(groups)}")
    for group in groups:
        build_group(group)
    print("Done.")


if __name__ == "__main__":
    main(sys.argv)
