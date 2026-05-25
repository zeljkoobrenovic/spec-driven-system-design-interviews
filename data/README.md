# `data/` — interview datasets

Every interview is one JSON file. Datasets are organized into **groups** and,
within a group, into **categories**.

## Structure

```
data/
  <group>/                 # one group -> one deployable site (docs/<group>/)
    index.json             # the group's manifest: categories + dataset list
    <id>/
      interview.json       # the dataset (one interview)
      icon.png             # optional per-interview overview icon
      assets/              # optional generated icons/images linked from JSON
```

Current groups:

- **`examples/`** — worked example datasets (the canonical reference is
  `url-shortener`).
- **`book/`** — the book group: a pattern catalog, the interview-method
  walkthrough, and ~50 flagship cases organized into categories. Also holds
  planning notes (`BOOK-STRUCTURE.md`) and a verifier (`_verify.mjs`).
- **`real-world-systems/`** — interviews derived from public production
  architecture case studies and engineering write-ups.

A group becomes publishable once it has an `index.json`. Loose files at a group
root that aren't dataset directories (e.g. `BOOK-STRUCTURE.md`) and, inside a
dataset dir, authoring/build helpers (`*.md`, `*.py`, `*.mjs`) are **not**
shipped to `docs/` — only `index.json` and dataset subdirectories (with
`interview.json` and assets like `icon.png`).

## Manifest (`<group>/index.json`)

```jsonc
{
  "groups": [                         // these are the CATEGORIES (see note below)
    {
      "id": "fundamentals",
      "name": "Fundamentals",
      "datasets": [
        { "id": "url-shortener", "name": "URL Shortener",
          "path": "data/url-shortener/interview.json" }  // path is relative to the group
      ]
    }
  ]
}
```

> The JSON key is `groups` for historical reasons, but each entry is a
> **category** (a section the overview renders). A *group* is the directory
> under `data/`. The `path` omits the group prefix (it's resolved relative to
> the built site).

## Adding an interview

1. Create `data/<group>/<id>/interview.json` (schema: [`../PLAN.md`](../PLAN.md)).
   - Required: `highLevelArchitecture` (nodes/links/types) and either `steps[]`
     or `patternCatalog[]`.
   - Step 1 should be a naive baseline; later steps add one mechanism each; add
     `flows` to the key interaction steps.
   - Step `view.nodes`/`view.links` are **id references** into
     `highLevelArchitecture`; `view.highlight` ⊆ `view.nodes`.
2. Register it in a category's `datasets[]` in `data/<group>/index.json`.
3. Optionally add `data/<group>/<id>/icon.png` for the overview card.
4. `python3 build.py` and commit the regenerated `docs/`.

AI agents can scaffold a full, verifier-passing dataset with the
`/new-interview` skill (`.claude/skills/new-interview/`).

## Verifying

```bash
node data/book/_verify.mjs                                   # book: schema + diagram/satisfies refs
python3 -c "import json; json.load(open('data/<group>/<id>/interview.json'))"  # JSON validity
```

`_verify.mjs` checks that view node/link/highlight refs resolve to the dataset's
`highLevelArchitecture`, that no step uses a legacy `diagram` field, that flows
use structured `sequence` objects, that `satisfies`/`patterns` step references
resolve, and that sub-step `parent`s exist.

See also: [`../PLAN.md`](../PLAN.md) (full schema), [`../README.md`](../README.md)
(project overview), [`../CLAUDE.md`](../CLAUDE.md) (agent conventions).
