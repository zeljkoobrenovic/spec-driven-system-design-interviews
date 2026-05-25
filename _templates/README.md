# `_templates/` — the shared site shell

**This is where you edit the app's HTML/CSS/JS.** Both pages of every group are
built from this one tree. `build.py` copies the whole `_templates/` directory
into each `docs/<group>/`, so the source of truth lives here — never edit the
generated `docs/<group>/` copies (the next build overwrites them).

## Files

| File | Role |
|------|------|
| `index.html`      | Overview page DOM shell (the interview grid). |
| `overview.js`     | Overview behavior (one IIFE): fetch the manifest, render cards. |
| `interview.html`  | Explorer DOM shell + the Mermaid CDN `<script>` tag. |
| `interview.js`    | Explorer behavior (one IIFE, no modules): dataset loading, sidebar grouping, all rendering, Mermaid orchestration, hash routing, keyboard nav, error capture. |
| `styles.css`      | All styling for both pages, including the rendered-SVG highlight rules. |
| `node-types.json` | Canonical node types + the rendering config (shape/fill/stroke per type). |
| `icons/`          | Shared icons: the fallback interview icon (`system-design.png`) and the section icons (concept, pattern, trap, before/after/risk, deep-dive, etc.). |

## How it ships

`build.py` copies this entire tree to `docs/<group>/`, then copies the group's
`data/` alongside it. Paths like `icons/...` and `data/...` are resolved
relative to the built `index.html` / `interview.html`, which is why the
templates have no sibling `data/` of their own — serve a built group under
`docs/<group>/`, not `_templates/`.

## Editing notes

- `interview.js` is one IIFE; a top-to-bottom map of its sections (Mermaid
  init, `els`, `state`, entry building, rendering, navigation, loading) is in
  [`../CLAUDE.md`](../CLAUDE.md).
- `overview.js` and `interview.js` each normalize the grouped manifest
  independently — keep the two normalizers in sync by hand.
- Mermaid node/edge **labels are entity-escaped by the renderer** — author
  labels as plain text; don't hand-escape special characters.
- After any change here: `node --check _templates/interview.js`,
  `node --check _templates/overview.js`, then `python3 build.py` and commit the
  regenerated `docs/`.

See also: [`../README.md`](../README.md) (project overview),
[`../CLAUDE.md`](../CLAUDE.md) (full conventions + pitfalls),
[`../PLAN.md`](../PLAN.md) (dataset schema the renderer consumes).
