#!/usr/bin/env python3
"""Assign icons to a dataset's `technologyChoices` chips, driven by YAML.

Mapping lives in ``_media/index.yaml`` — a list of ``{ icon, terms }`` entries
(one icon, many terms). Terms match CASE-INSENSITIVELY; a chip name also has any
parenthetical qualifier stripped and is matched against progressively shorter
leading-word prefixes, so "Aurora (PostgreSQL/MySQL)" and "Aurora Global
Database" both match the term "Aurora".

For each technology name under ``technologyChoices[].selfHosted`` and
``technologyChoices[].cloud.{aws,gcp,azure}`` this:
  - resolves the name to an icon via ``_media/index.yaml`` (else falls back to
    ``_media/tech.png`` and records the term in ``_media/missing.yaml``),
  - copies the icon into ``<interview-dir>/assets/tech-icons/``,
  - rewrites the chip from a bare string into ``{ "name": <text>, "icon":
    "assets/tech-icons/<file>" }``.

Idempotent. Standard-library only — includes a tiny reader/writer for the
specific YAML shapes used by index.yaml / missing.yaml.

Usage:
    python3 _scripts/assign_tech_icons.py data/book/simple-web-application/interview.json
    python3 _scripts/assign_tech_icons.py <interview.json> --dry-run
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = REPO_ROOT / "_media"
INDEX_YAML = MEDIA_DIR / "index.yaml"
MISSING_YAML = MEDIA_DIR / "missing.yaml"
FALLBACK_ICON = MEDIA_DIR / "tech.png"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Tiny YAML helpers (only the shapes index.yaml / missing.yaml use).
# ---------------------------------------------------------------------------
def _strip_comment(line: str) -> str:
    # Drop a trailing comment that is not inside quotes (our files don't put
    # '#' inside values, so a simple split on " #" / leading-# is enough).
    if line.lstrip().startswith("#"):
        return ""
    return line


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1]
    return s


def load_index(path: Path):
    """Parse index.yaml: a list of { icon: <str>, terms: [<str>...] }.

    Supports inline `terms: ["a", "b"]` and block list form. Returns a list of
    (icon, [terms]).
    """
    entries = []
    cur = None  # {"icon":..., "terms":[...]}
    in_terms_block = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not _strip_comment(raw).strip():
            continue
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())

        # New entry: "- icon: <path>"
        m = re.match(r"^-\s*icon:\s*(.+)$", stripped)
        if m:
            if cur is not None:
                entries.append(cur)
            cur = {"icon": _unquote(m.group(1)), "terms": []}
            in_terms_block = False
            continue

        if cur is None:
            continue

        # inline terms list: terms: ["a", "b", ...]
        m = re.match(r"^terms:\s*\[(.*)\]\s*$", stripped)
        if m:
            inner = m.group(1).strip()
            cur["terms"] = [_unquote(x) for x in _split_inline_list(inner)]
            in_terms_block = False
            continue

        # block terms list header: terms:
        if re.match(r"^terms:\s*$", stripped):
            in_terms_block = True
            continue

        # block list item: "- value"
        if in_terms_block and stripped.startswith("-"):
            cur["terms"].append(_unquote(stripped[1:].strip()))
            continue

        # inline single icon-less continuation (ignore unknown keys)
    if cur is not None:
        entries.append(cur)
    return entries


def _split_inline_list(inner: str):
    # Split "a", "b", c on commas not inside quotes (our values have no commas
    # inside quotes, but be safe).
    out, buf, q = [], "", None
    for ch in inner:
        if q:
            buf += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
            buf += ch
        elif ch == ",":
            if buf.strip():
                out.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf.strip())
    return out


def load_missing(path: Path) -> list[str]:
    if not path.is_file():
        return []
    out = []
    in_list = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not _strip_comment(raw).strip():
            continue
        stripped = raw.strip()
        if re.match(r"^missing:\s*$", stripped):
            in_list = True
            continue
        if in_list and stripped.startswith("-"):
            out.append(_unquote(stripped[1:].strip()))
    return out


def write_missing(path: Path, terms: list[str]) -> None:
    header = (
        "# Technology terms that use the _media/tech.png fallback.\n"
        "#\n"
        "# A term lands here when it has no match in _media/index.yaml, is rejected\n"
        "# by the provider-family rule (an AWS/GCP/Azure chip whose icon would be\n"
        "# outside aws-icons//gcp-icons//azure-icons/), or its mapped file is missing.\n"
        "# assign_tech_icons.py keeps this list in sync: it adds terms that fall back\n"
        "# to tech.png and prunes any term that now resolves to a real icon. To give a\n"
        "# term an icon, add it to _media/index.yaml (the script prunes it from here).\n"
        "missing:\n"
    )
    body = "".join(f'  - "{t}"\n' for t in sorted(set(terms), key=str.lower))
    path.write_text(header + body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
def norm(text: str) -> str:
    """Lowercase, drop parenthetical qualifiers, collapse whitespace."""
    text = re.sub(r"\(.*?\)", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip().lower()


def build_term_index(entries):
    """term-key (normalized) -> icon relative path. First entry wins on dupes."""
    idx = {}
    for e in entries:
        icon = e.get("icon")
        if not icon:
            continue
        for term in e.get("terms", []):
            key = norm(term)
            if key and key not in idx:
                idx[key] = icon
    return idx


def resolve(name: str, term_index: dict[str, str], require_family: str | None = None):
    """Return icon-rel-path or None.

    Tries, in order: the full normalized name, progressively shorter leading-word
    prefixes, and (for slash-joined compound names like "IPVS/LVS" or
    "Fluentd/Fluent Bit") the segment before the first '/'.

    `require_family`, when set (e.g. "aws-icons"), enforces that a cloud-column
    chip only uses an icon from that provider's directory: a mapped icon outside
    that family is rejected (returns None) so it falls back rather than shipping
    a cross-provider icon.
    """
    candidates = [norm(name)]
    if "/" in name:
        candidates.append(norm(name.split("/", 1)[0]))
    for key in candidates:
        if not key:
            continue
        words = key.split(" ")
        for n in range(len(words), 0, -1):
            prefix = " ".join(words[:n])
            if prefix in term_index:
                icon = term_index[prefix]
                if require_family and not icon.startswith(require_family + "/"):
                    return None
                return icon
    return None


def chip_name(chip) -> str:
    if isinstance(chip, str):
        return chip
    if isinstance(chip, dict):
        return str(chip.get("name") or "")
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("interview_json")
    ap.add_argument("--dry-run", action="store_true", help="Report matches; copy nothing, rewrite nothing.")
    args = ap.parse_args(argv)

    interview = Path(args.interview_json)
    if not interview.is_absolute():
        interview = (Path.cwd() / interview).resolve()
    if not interview.is_file():
        print(f"error: no interview.json at {interview}", file=sys.stderr)
        return 2
    if not INDEX_YAML.is_file():
        print(f"error: mapping file missing: {rel(INDEX_YAML)}", file=sys.stderr)
        return 2
    if not FALLBACK_ICON.is_file():
        print(f"error: fallback icon missing: {rel(FALLBACK_ICON)}", file=sys.stderr)
        return 2

    term_index = build_term_index(load_index(INDEX_YAML))

    data = json.loads(interview.read_text(encoding="utf-8"), object_pairs_hook=collections.OrderedDict)
    tc = data.get("technologyChoices")
    if not isinstance(tc, list) or not tc:
        print("No technologyChoices in dataset; nothing to do.")
        return 0

    dataset_dir = interview.parent
    icons_dir = dataset_dir / "assets" / "tech-icons"

    # Resolve every distinct chip name to an icon (or None -> fallback).
    # Cloud-column chips must use that provider's icon directory; self-hosted
    # chips may use any (general-icons, etc.).
    PROVIDER_FAMILY = {"aws": "aws-icons", "gcp": "gcp-icons", "azure": "azure-icons"}
    name_to_icon: dict[str, str | None] = {}
    def collect(chips, family=None):
        for c in chips or []:
            nm = chip_name(c)
            if nm and nm not in name_to_icon:
                name_to_icon[nm] = resolve(nm, term_index, require_family=family)
    for item in tc:
        if not isinstance(item, dict):
            continue
        collect(item.get("selfHosted"))
        cl = item.get("cloud") or {}
        for prov in ("aws", "gcp", "azure"):
            collect(cl.get(prov), family=PROVIDER_FAMILY[prov])

    # Map each name to a destination filename (dataset-relative), copying the
    # source media file (or the fallback) into assets/tech-icons. Dedup copies
    # by destination basename.
    name_to_relpath: dict[str, str] = {}
    copied: dict[str, str] = {}  # source abs path -> dest filename
    if not args.dry_run:
        icons_dir.mkdir(parents=True, exist_ok=True)
    for nm, icon in name_to_icon.items():
        source = (MEDIA_DIR / icon) if icon else FALLBACK_ICON
        if not source.is_file():
            # Mapping points at a non-existent file: fall back to tech.png.
            print(f"warning: icon for {nm!r} not found: {rel(source)} -> fallback", file=sys.stderr)
            source = FALLBACK_ICON
        key = str(source.resolve())
        if key in copied:
            dest_name = copied[key]
        else:
            dest_name = source.name
            copied[key] = dest_name
            if not args.dry_run:
                shutil.copyfile(source, icons_dir / dest_name)
        name_to_relpath[nm] = f"assets/tech-icons/{dest_name}"

    # "Missing" = every term whose final assigned icon is the tech.png fallback,
    # whether because it had no index match, was rejected by the provider-family
    # rule, or its mapped file did not exist. This is the single source of truth
    # for missing.yaml.
    fallback_rel = f"assets/tech-icons/{FALLBACK_ICON.name}"
    new_missing = [nm for nm, rp in name_to_relpath.items() if rp == fallback_rel]
    matched = len(name_to_icon) - len(new_missing)

    # Rewrite chips -> {name, icon}
    def rewrite(chips):
        out = []
        for c in chips or []:
            nm = chip_name(c)
            if not nm:
                out.append(c)
                continue
            out.append(collections.OrderedDict([("name", nm), ("icon", name_to_relpath[nm])]))
        return out
    for item in tc:
        if not isinstance(item, dict):
            continue
        if "selfHosted" in item:
            item["selfHosted"] = rewrite(item["selfHosted"])
        cl = item.get("cloud")
        if isinstance(cl, dict):
            for prov in ("aws", "gcp", "azure"):
                if prov in cl:
                    cl[prov] = rewrite(cl[prov])

    total = len(name_to_icon)
    print(f"Names: {total}; matched via index.yaml: {matched}; fallback (tech.png): {total - matched}")
    print(f"Distinct icon files: {len(copied)} -> {rel(icons_dir)}")

    if args.dry_run:
        print("dry-run: copied nothing, JSON/missing.yaml left unchanged.")
        if new_missing:
            print("Would add to missing.yaml:")
            for t in sorted(set(new_missing), key=str.lower):
                print(f"   - {t}")
        return 0

    interview.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Rewrote {rel(interview)} with icon paths.")

    # Keep missing.yaml in sync: it lists every term that uses the tech.png
    # fallback. Add this run's fallbacks, and prune any existing entry that now
    # resolves to a real icon under _media/ (re-validated against index.yaml),
    # so the file never claims a term is missing when it isn't.
    existing = load_missing(MISSING_YAML)
    def still_missing(term: str) -> bool:
        icon = resolve(term, term_index)
        return icon is None or not (MEDIA_DIR / icon).is_file()
    kept = [t for t in existing if still_missing(t)]
    pruned = [t for t in existing if t not in kept]
    combined = kept + [t for t in new_missing if t not in kept]
    if set(combined) != set(existing):
        write_missing(MISSING_YAML, combined)
        added = len(set(combined) - set(existing))
        print(f"Updated {rel(MISSING_YAML)} (+{added} added, -{len(pruned)} pruned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
