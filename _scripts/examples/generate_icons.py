"""Generate an icon image for each post in a journal using Google's Gemini
image-generation model.

Usage:
    GEMINI_API_KEY=... python3 _wiring/generate_icons.py --journal documents

The set of posts to process is taken from the journal's ``config.yaml``
(the same source of truth ``build.py`` uses): every path listed under
``sections[].posts`` is checked. The skip decision is based on the icon
file's presence on disk -- not on the front-matter field -- so a post whose
``icon:`` is set but whose underlying file was deleted will get regenerated.

For each post:

  1. If the icon file exists on disk, skip generation. If the post is missing
     the ``icon:`` front-matter field, wire it up.
  2. Otherwise, build a short visual prompt from the post title + excerpt,
     call the Gemini image model, and save the result to
     ``_journals/<journal>/assets/icons/<slug>.png`` (or to the per-post
     folder for the ``<slug>/index.md`` layout).
  3. Add the front-matter field if it isn't already there::

         icon: assets/icons/<slug>.png

Standard-library only -- matches the rest of ``_wiring``.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Reuse the journal's own YAML subset parser so we read config.yaml exactly
# the same way build.py does.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import parse_yaml  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
JOURNALS_DIR = REPO_ROOT / "_journals"

MODEL = "gemini-3.1-flash-image-preview"
# Gemini imageSize values: "512" (lowest), "1K", "2K", "4K". "512" is only
# supported by gemini-3.1-flash-image-preview.
DEFAULT_IMAGE_SIZE = "512"

ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)


# ---------- front matter helpers (kept compatible with build.py) ----------

def split_front_matter(text: str):
    """Return (fm_lines, body) where fm_lines is the list of raw lines
    between the leading ``---`` fences. If no front matter is present,
    fm_lines is None."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    fm = text[3:end].strip("\n")
    body_start = text.find("\n", end + 3)
    body = text[body_start + 1:] if body_start != -1 else ""
    return fm.splitlines(), body


def parse_fm_dict(fm_lines):
    """Parse front matter lines into a dict of stripped string values.
    Mirrors build.parse_front_matter's behavior."""
    meta = {}
    for line in fm_lines or []:
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        v = value.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        meta[key.strip()] = v
    return meta


def write_post_with_added_fm(path: Path, fm_lines, body, additions):
    """Append ``additions`` (list of (key, value) pairs) to fm_lines and
    write the file back. Values are written as double-quoted strings."""
    new_fm = list(fm_lines)
    for key, value in additions:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        new_fm.append(f'{key}: "{escaped}"')
    text = "---\n" + "\n".join(new_fm) + "\n---\n" + body
    path.write_text(text, encoding="utf-8")


# ---------- prompt construction ----------

def build_prompt(title: str, excerpt: str) -> str:
    """Construct an image-generation prompt for a small square icon."""
    parts = [
        "Icon requirements:"
        "- A minimalist icon in a clean, professional line-art style, no text"
        "- No text, or labels."
        "- No borders or frames."
        "- The design features bold, consistent black outlines with rounded stroke ends."
        "- Use thick, uniform line weights and simple geometric shapes."
        "- No shading, no gradients, and no colors—only high-contrast black and white vector-style graphics. ",
        "",
        f"Article title: {title}",
    ]
    if excerpt:
        parts.append(f"Excerpt: {excerpt}")
    return "\n".join(parts)


# ---------- Gemini API call ----------

def call_gemini_image(api_key: str, prompt: str, timeout: int = 240) -> bytes:
    """Call the Gemini image model and return the raw image bytes (JPEG/PNG).
    Raises RuntimeError on failure."""
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
                "aspectRatio": "1:1",
                "imageSize": DEFAULT_IMAGE_SIZE,
            },
        },
    }
    req = urllib.request.Request(
        f"{ENDPOINT}?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} from Gemini: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling Gemini: {e}") from e

    data = json.loads(body.decode("utf-8"))
    candidates = data.get("candidates") or []
    for cand in candidates:
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])

    raise RuntimeError(
        "No image data in Gemini response. Raw response: "
        + json.dumps(data)[:1000]
    )


# ---------- main per-post workflow ----------

def _icon_paths(journal_dir: Path, post_src: Path):
    """Return (icon_path_on_disk, icon_value_for_front_matter).

    Two post layouts are supported, mirroring ``generate_logos.py``:

    1. ``posts/<slug>/index.md`` (decisions-log / documents style) -- icon at
       ``posts/<slug>/assets/icons/<slug>.png``; front matter
       ``icon: assets/icons/<slug>.png``. The build merges the post-level
       ``assets/`` into the journal-level output, so the path resolves at
       ``docs/<journal>/assets/icons/<slug>.png``.

    2. ``posts/<year>/<slug>.md`` (underhood style) -- no per-post directory;
       icon goes to the journal's shared ``assets/icons/<slug>.png`` and
       front matter is ``icon: assets/icons/<slug>.png``.
    """
    if post_src.name in ("index.md", "index.markdown"):
        post_dir = post_src.parent
        slug = post_dir.name
        return (
            post_dir / "assets" / "icons" / f"{slug}.png",
            f"assets/icons/{slug}.png",
        )
    slug = post_src.stem
    return (
        journal_dir / "assets" / "icons" / f"{slug}.png",
        f"assets/icons/{slug}.png",
    )


def process_post(journal_dir: Path, post_src: Path, api_key: str, dry_run: bool) -> str:
    """Returns a short status string for the post."""
    label = post_src.relative_to(journal_dir / "posts").as_posix()

    text = post_src.read_text(encoding="utf-8")
    fm_lines, body = split_front_matter(text)
    if fm_lines is None:
        return f"skip (no front matter): {label}"

    meta = parse_fm_dict(fm_lines)
    icon_path, icon_value = _icon_paths(journal_dir, post_src)

    if icon_path.exists():
        # File on disk is the source of truth. If the front-matter field is
        # already set, leave the post alone; otherwise wire it up.
        if meta.get("icon"):
            return f"skip (icon file present): {label}"
        if not dry_run:
            write_post_with_added_fm(
                post_src,
                fm_lines,
                body,
                [("icon", icon_value)],
            )
        return f"linked existing icon: {label}"

    title = meta.get("title", post_src.stem)
    excerpt = meta.get("excerpt", "")
    prompt = build_prompt(title, excerpt)

    if dry_run:
        return f"dry-run (would generate): {label}"

    print(f"  generating icon for: {label} ...", flush=True)
    image_bytes = call_gemini_image(api_key, prompt)
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    icon_path.write_bytes(image_bytes)

    if not meta.get("icon"):
        write_post_with_added_fm(
            post_src,
            fm_lines,
            body,
            [("icon", icon_value)],
        )
    return f"generated: {label}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--journal",
        required=True,
        help="Journal directory name under _journals/, e.g. documents",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be done without calling the API or writing files.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Seconds to sleep between API calls (default: 2.0).",
    )
    args = parser.parse_args(argv)

    journal_dir = JOURNALS_DIR / args.journal
    posts_dir = journal_dir / "posts"
    config_file = journal_dir / "config.yaml"
    if not config_file.is_file():
        print(f"error: no config.yaml at {config_file}", file=sys.stderr)
        return 2
    if not posts_dir.is_dir():
        print(f"error: no posts directory at {posts_dir}", file=sys.stderr)
        return 2

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not args.dry_run:
        print(
            "error: GEMINI_API_KEY environment variable is not set.",
            file=sys.stderr,
        )
        return 2

    config = parse_yaml(config_file.read_text(encoding="utf-8")) or {}
    sections = config.get("sections") or []

    # Collect post source files from config.yaml, preserving config order
    # and de-duplicating if a post is listed in multiple sections.
    seen = set()
    targets = []  # list of Path (post source file)
    for section in sections:
        for rel in section.get("posts") or []:
            post_src = posts_dir / rel
            key = post_src.resolve()
            if key in seen:
                continue
            seen.add(key)
            targets.append(post_src)

    print(
        f"Processing {len(targets)} posts from {config_file.relative_to(REPO_ROOT)} ..."
    )

    generated = 0
    missing = 0
    for i, post_src in enumerate(targets):
        label = post_src.relative_to(posts_dir).as_posix()
        if not post_src.exists():
            print(f"[{i + 1}/{len(targets)}] missing post: {label}")
            missing += 1
            continue
        try:
            status = process_post(journal_dir, post_src, api_key, args.dry_run)
        except Exception as e:  # noqa: BLE001 -- keep going on per-post errors
            status = f"ERROR ({label}): {e}"
        print(f"[{i + 1}/{len(targets)}] {status}")
        if status.startswith("generated"):
            generated += 1
            if args.sleep and i + 1 < len(targets):
                time.sleep(args.sleep)

    print(f"\nDone. Generated {generated} new icon(s).", end="")
    if missing:
        print(f" {missing} post(s) listed in config.yaml were missing on disk.")
    else:
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
