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

from PIL import Image

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "_templates"
DATA = ROOT / "data"
DOCS = ROOT / "docs"

# Generated AI images are authored at ~1500-3000px tall but only ever shown in
# a .diagram-image box capped at max-height: 560px (see _templates/styles.css).
# Shipping the full-resolution originals bloats docs/ past GitHub Pages' size
# limit, so the build downscales the *copies* in docs/ to 2x the display height
# (retina-sharp) while leaving the originals in data/ untouched. Comics are
# excluded — they're long vertical strips read at full size, not in the 560px
# box. Resizing uses Pillow (cross-platform) — see requirements.txt.
GENERATED_IMAGE_MAX_HEIGHT = 1120  # 2x the 560px CSS display height
RESIZABLE_GENERATED_DIRS = ("ai-visuals", "design-vs-requirements")
GENERATED_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")

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


def _downscale_image(path, max_height):
    """Downscale `path` in place to `max_height` if it's taller, preserving
    aspect ratio and format. Returns True if it resized, False if it was already
    small enough. Raises on a read/write error so the caller can warn.
    """
    with Image.open(path) as im:
        width, height = im.size
        if height <= max_height:
            return False
        new_width = max(1, round(width * max_height / height))
        resized = im.resize((new_width, max_height), Image.LANCZOS)
        # Preserve the original format and don't drop ICC/EXIF; save params
        # mirror typical generator output (high-quality JPEG, optimized PNG).
        fmt = im.format
        save_kwargs = {}
        if fmt == "JPEG":
            save_kwargs.update(quality=90, optimize=True)
            if resized.mode in ("RGBA", "P"):
                resized = resized.convert("RGB")
        elif fmt == "PNG":
            save_kwargs.update(optimize=True)
        resized.save(path, format=fmt, **save_kwargs)
    return True


def _downscale_generated_images(out_data):
    """Downscale oversized generated AI images in the docs/ copy in place.

    Walks each dataset's assets/generated/{ai-visuals,design-vs-requirements}/
    (recursively, incl. the steps/ subdir) and shrinks any image taller than
    GENERATED_IMAGE_MAX_HEIGHT to that height, preserving aspect ratio and
    format. Images already at/below the cap are left alone. Comics are not
    touched. Only the docs/ copies change — the originals under data/ are
    untouched. Returns (resized_count, skipped_count).
    """
    resized = 0
    skipped = 0
    for sub in RESIZABLE_GENERATED_DIRS:
        for gen_dir in out_data.glob(f"*/assets/generated/{sub}"):
            for img in gen_dir.rglob("*"):
                if not img.is_file():
                    continue
                if img.suffix.lower() not in GENERATED_IMAGE_SUFFIXES:
                    continue
                try:
                    if _downscale_image(img, GENERATED_IMAGE_MAX_HEIGHT):
                        resized += 1
                    else:
                        skipped += 1
                except (OSError, ValueError) as exc:
                    print(f"    warn: failed to resize {img} ({exc}) — left as-is")
    return resized, skipped


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

    # 3. Downscale oversized generated AI images in the docs/ copy only — the
    #    originals under data/ stay full-resolution. Keeps docs/ within GitHub
    #    Pages' size budget without losing source images.
    resized, skipped = _downscale_generated_images(out_data)

    dataset_count = sum(1 for e in out_data.iterdir() if e.is_dir())
    print(
        f"  built docs/{group}/  ({dataset_count} datasets; "
        f"{resized} images downscaled, {skipped} already small)"
    )


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
