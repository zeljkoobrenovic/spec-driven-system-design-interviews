#!/usr/bin/env python3
"""Downscale oversized generated AI images in place.

The explorer only ever shows generated AI images in a `.diagram-image` box
capped at `max-height: 560px` (see `_templates/styles.css`), but the originals
are authored at ~1500-3000px tall. Shipping them at full resolution bloats
`docs/` past GitHub Pages' size limit, so run this by hand over a built
`docs/<group>/data/` tree to shrink the copies to 2x the display height
(retina-sharp). It is intentionally NOT part of `build.py` (which is a pure copy
step) — run it separately, only when you're about to deploy, not on every build.
It edits the `docs/` copies in place; the originals under `data/` are untouched,
so a fresh `build.py` restores full-res and you can downsize again.

Scope: each dataset's `assets/generated/{ai-visuals,design-vs-requirements}/`
(recursively, incl. the `steps/` subdir). Comics are intentionally left at full
size — they're long vertical strips read full-size, not in the 560px box.

Backends, in order of preference:
  1. `sips` — macOS-only, no install, ships with the OS.
  2. Pillow — cross-platform fallback (`pip install -r requirements.txt`).
If neither is available the script prints a notice and resizes nothing, so the
build still produces a working (if larger) site.

It searches each given directory recursively (any depth) for
`assets/generated/{ai-visuals,design-vs-requirements}/` folders, so you can
point it at the whole `docs/` root, a single group, or one dataset:

Usage:
  python3 downsize-images.py docs/                # every group under docs/
  python3 downsize-images.py docs/book           # one group
  python3 downsize-images.py docs/book/data/foo  # one dataset
  python3 downsize-images.py --max-height 1120 docs/
  python3 downsize-images.py --backend pillow docs/
  python3 downsize-images.py --help

Run a single pass at a time — running two passes over the same tree
concurrently makes the backends race on the same files.

Importable too: `from downsize_images import downsize_tree` (the module name
uses an underscore — import via importlib if you need the hyphenated file).
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# 2x the 560px CSS display height — retina-sharp at the size it's shown.
DEFAULT_MAX_HEIGHT = 1120

# Only these generated subdirs get downscaled. Comics are deliberately omitted.
RESIZABLE_GENERATED_DIRS = ("ai-visuals", "design-vs-requirements")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


# --- Backend detection -------------------------------------------------------

def _have_sips():
    return shutil.which("sips") is not None


def _have_pillow():
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def _pick_backend():
    """Return 'sips', 'pillow', or None — the resize backend to use."""
    if _have_sips():
        return "sips"
    if _have_pillow():
        return "pillow"
    return None


# --- sips backend ------------------------------------------------------------

def _sips_height(path):
    """Pixel height via `sips`, or None if unreadable."""
    try:
        out = subprocess.run(
            ["sips", "-g", "pixelHeight", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError):
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("pixelHeight:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def _sips_downscale(path, max_height):
    """Downscale via `sips` in place. Returns True if resized, False if already
    small enough. Raises OSError/CalledProcessError on failure."""
    height = _sips_height(path)
    if height is None:
        raise OSError(f"sips could not read height of {path}")
    if height <= max_height:
        return False
    subprocess.run(
        ["sips", "--resampleHeight", str(max_height), str(path)],
        capture_output=True, text=True, check=True,
    )
    return True


# --- Pillow backend ----------------------------------------------------------

def _pillow_downscale(path, max_height):
    """Downscale via Pillow in place, preserving aspect ratio and format.
    Returns True if resized, False if already small enough."""
    from PIL import Image

    with Image.open(path) as im:
        width, height = im.size
        if height <= max_height:
            return False
        new_width = max(1, round(width * max_height / height))
        resized = im.resize((new_width, max_height), Image.LANCZOS)
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


# --- Driver ------------------------------------------------------------------

def _iter_generated_images(root):
    """Yield every resizable generated image under `root`.

    Searches `root` recursively at **any depth** for `assets/generated/<sub>/`
    folders (where <sub> is in RESIZABLE_GENERATED_DIRS) and yields every image
    file inside them. Depth-independent, so you can point it at a single dataset,
    a group's `data/` tree, or the whole `docs/` root — it finds every matching
    folder underneath. Comics (`assets/generated/comic/`) are never matched.
    """
    root = Path(root)
    seen_dirs = set()
    for sub in RESIZABLE_GENERATED_DIRS:
        # rglob the parent pattern so the <sub> dir is found at any depth.
        for gen_dir in root.rglob(f"assets/generated/{sub}"):
            if not gen_dir.is_dir() or gen_dir in seen_dirs:
                continue
            seen_dirs.add(gen_dir)
            for img in gen_dir.rglob("*"):
                if img.is_file() and img.suffix.lower() in IMAGE_SUFFIXES:
                    yield img


def downsize_tree(root, max_height=DEFAULT_MAX_HEIGHT, backend=None):
    """Downscale every oversized generated image under `root` in place.

    `backend` is 'sips', 'pillow', or None (auto-pick). Returns a dict:
    {'backend', 'resized', 'skipped', 'failed'}. If no backend is available,
    'backend' is None and nothing is changed.
    """
    backend = backend or _pick_backend()
    stats = {"backend": backend, "resized": 0, "skipped": 0, "failed": 0}
    if backend is None:
        return stats

    downscale = _sips_downscale if backend == "sips" else _pillow_downscale
    # When the primary backend is sips, individual files can fail for transient
    # reasons (e.g. a sips exit-13 hiccup). If Pillow is importable, retry that
    # one image with it before giving up — so a flaky tool never leaves an
    # oversized image behind.
    can_retry_with_pillow = backend == "sips" and _have_pillow()

    for img in _iter_generated_images(root):
        try:
            resized = downscale(img, max_height)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            if can_retry_with_pillow:
                try:
                    resized = _pillow_downscale(img, max_height)
                except (OSError, ValueError) as exc2:
                    stats["failed"] += 1
                    print(f"    warn: failed to resize {img} "
                          f"(sips: {exc}; pillow: {exc2}) — left as-is",
                          file=sys.stderr)
                    continue
            else:
                stats["failed"] += 1
                print(f"    warn: failed to resize {img} ({exc}) — left as-is",
                      file=sys.stderr)
                continue
        stats["resized" if resized else "skipped"] += 1
    return stats


def main(argv):
    parser = argparse.ArgumentParser(
        description="Downscale oversized generated AI images in place "
                    "(sips, with Pillow as a cross-platform fallback).")
    parser.add_argument("dirs", nargs="+", metavar="DIR",
                        help="one or more directories to search recursively for "
                             "assets/generated/{ai-visuals,design-vs-requirements} "
                             "folders (e.g. docs/, docs/book, a single dataset)")
    parser.add_argument("--max-height", type=int, default=DEFAULT_MAX_HEIGHT,
                        help=f"height cap in px (default {DEFAULT_MAX_HEIGHT})")
    parser.add_argument("--backend", choices=("sips", "pillow"), default=None,
                        help="force a backend instead of auto-picking")
    args = parser.parse_args(argv[1:])

    backend = args.backend or _pick_backend()
    if backend is None:
        print("note: neither `sips` nor Pillow is available — skipping image "
              "downscaling (output will be larger). Install Pillow: "
              "pip install -r requirements.txt", file=sys.stderr)
        return 0

    total = {"resized": 0, "skipped": 0, "failed": 0}
    for d in args.dirs:
        path = Path(d)
        if not path.is_dir():
            print(f"  skip {d} (not a directory)", file=sys.stderr)
            continue
        stats = downsize_tree(path, args.max_height, backend)
        for k in total:
            total[k] += stats[k]
        print(f"  {d}: {stats['resized']} downscaled, "
              f"{stats['skipped']} already small"
              + (f", {stats['failed']} failed" if stats["failed"] else ""))

    print(f"Done via {backend}: {total['resized']} images downscaled, "
          f"{total['skipped']} already small"
          + (f", {total['failed']} failed" if total["failed"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
