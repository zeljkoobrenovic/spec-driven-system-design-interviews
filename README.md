# System Design Interview Explorer

A static, framework-free web app for walking through system-design interview
problems step by step: requirements → capacity → API → data model → an
architecture that evolves one decision at a time → a wrap-up that ties the
design back to the requirements.

There is no bundler and one runtime dependency (Mermaid, from a CDN). The only
"build" is a copy step (`build.py`) that assembles deployable static sites from
the sources into `docs/`.

See generated documentation at **[zeljkoobrenovic.github.io/spec-driven-system-design-interviews/](https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/)**

## Two pages

- **Overview (`index.html`)** — a visual grid of all interviews, grouped into
  categories. Each card links to the explorer.
- **Explorer (`interview.html#<id>`)** — the per-interview step-by-step
  walkthrough (the main app).

They share `styles.css`.

## Repository layout

| Path             | What it is |
|------------------|------------|
| `_templates/`    | **Edit here.** The shared HTML/CSS/JS shell + `node-types.json` + `icons/`. See [`_templates/README.md`](_templates/README.md). |
| `data/`          | **Edit here.** Dataset groups; one `interview.json` per interview. See [`data/README.md`](data/README.md). |
| `docs/`          | **Generated** by `build.py` (committed, deployed via GitHub Pages). Do not hand-edit. See [`docs/README.md`](docs/README.md). |
| `build.py`       | The copy step: `_templates/` + each `data/<group>/` → `docs/<group>/`. |
| `PLAN.md`        | Product spec + the full dataset JSON schema. |
| `CLAUDE.md` / `AGENTS.md` | Conventions and pitfalls for AI agents (kept byte-identical). |

> **"Group" vs "category":** a *group* is a top-level dir under `data/` (e.g.
> `examples`, `book`) that builds into one independent site `docs/<group>/`. A
> *category* is a section within one site (the `groups[]` array in that site's
> `index.json`). The JSON key is `groups` for historical reasons; in prose we
> call those **categories**.

## Build and run

```bash
python3 build.py                       # rebuild every publishable group into docs/
python3 build.py examples              # rebuild only the named group(s)
python3 -m http.server 8000 -d docs    # serve the built output
# then open http://localhost:8000/examples/   (overview)
#   explorer: http://localhost:8000/examples/interview.html#url-shortener
```

The app fetches JSON, so opening a file via `file://` will not work — always
serve over HTTP. You serve the **built** output under `docs/<group>/`, never
`_templates/`. After editing anything in `_templates/` or `data/`, re-run
`build.py` and commit the regenerated `docs/`.

## Adding an interview

Create `data/<group>/<id>/interview.json`, register it in that group's
`data/<group>/index.json`, run `python3 build.py`, and commit `docs/`. The
schema is in [`PLAN.md`](PLAN.md); [`data/README.md`](data/README.md) has the
step-by-step. AI agents can scaffold one with the `/new-interview` skill in
`.claude/skills/`.

## Verifying without a browser

```bash
node --check _templates/interview.js     # explorer JS syntax
node --check _templates/overview.js      # overview JS syntax
node data/book/_verify.mjs               # book datasets: schema + diagram refs
python3 build.py                         # the copy step itself
```

Mermaid renders only in a browser, so diagram visuals must be eyeballed by
serving `docs/` — the checks above catch everything else.

## Keeping docs in sync

`README.md`, `CLAUDE.md`, and `AGENTS.md` describe overlapping facts (build
steps, layout, conventions). When you change a shared fact, update all three.
`CLAUDE.md` and `AGENTS.md` are kept **byte-identical**; `README.md` is the
human-facing front door and may differ in level of detail. See the "Keeping the
docs in sync" note in `CLAUDE.md`.
