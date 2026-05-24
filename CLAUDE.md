# CLAUDE.md

Notes for future Claude sessions working on this directory. See `PLAN.md` for
the product spec and dataset schema — this file covers code conventions,
where logic lives, and common pitfalls.

## What this is

A static, single-page system-design interview explorer. No build step, no
framework, one CDN dep (Mermaid v10).

Five files:

| File                                | Role                                                     |
|-------------------------------------|----------------------------------------------------------|
| `index.html`                        | DOM shell + Mermaid CDN tag                              |
| `styles.css`                        | All styling                                              |
| `app.js`                            | All behavior (one IIFE, no modules)                      |
| `data/index.json`                   | Dataset manifest                                         |
| `data/<id>/interview.json`          | One dataset per subdirectory                             |

## Running locally

```bash
python3 -m http.server 8000
# visit http://localhost:8000/
```

The app fetches JSON, so `file://` does not work — always serve.

## Verification you can do without a browser

The user usually can't see browser-side rendering from your sandbox. Use:

```bash
node --check app.js                                   # JS syntax
python3 -c "import json; json.load(open('data/...'))" # JSON validity
```

For dataset edits, cross-check that `highlight` node IDs actually appear in
their diagrams, and that `satisfies[*].steps[*]` slugs resolve to real step
IDs. Both checks were done inline during initial population — repeat them
when you touch those fields. Mermaid source itself can only be visually
validated; if you change diagrams, say so explicitly to the user.

HTTP-serve check (start server in the background, curl each asset for 200,
stop server) is fast and worth doing after large edits.

## app.js structure

One IIFE. Top to bottom:

1. **Mermaid init** — `securityLevel: 'strict'`. Don't change unless you need
   clickable nodes inside diagrams.
2. **`els`** — cached `document.getElementById` refs. All DOM access goes
   through this object.
3. **`state`** — current dataset, entries list, indices.
4. **`INTRO_SLUGS` / `WRAPUP_ORDER` / `WRAPUP_SLUGS`** — sidebar wiring. New
   intro sections must be registered here.
5. **Utilities** — `fetchJson`, `extractNodeIds`, `computeAutoDiff`,
   `resolveHighlights`, `augmentDiagramWithHighlights`, sentence splitter.
6. **`buildEntries(data)`** — turns a dataset into a flat list of `{ kind,
   id, title, payload }` items in sidebar order (intros, then steps, then
   wrap-up intros). The order here matters: it's exactly the display order.
7. **`renderNav` / `updateNavActive`** — renders the three sidebar groups
   (`Overview`, `Architecture`, `Wrap-up`). Groups are populated by
   filtering `INTRO_SLUGS` membership in `WRAPUP_SLUGS`.
8. **Step rendering** — `effectiveDiagramFor`, `renderDiagram`,
   `renderOptionTabs`, `renderProsCons`, `renderStepExtras`. The diagram
   highlight pipeline is described below.
9. **Intro renderers** — `renderIntroRequirements`, `renderIntroCapacity`,
   `renderIntroApi`, `renderIntroDataModel`, `renderIntroApiFlows`,
   `renderIntroSatisfies`, `renderIntroFollowUps`. Each returns a DOM node;
   `renderIntroEntry()` dispatches by slug.
10. **`renderCurrentEntry()`** — top-level rendering. Shows/hides
    `#diagram-block` vs `#intro-block` based on `entry.kind`.
11. **Navigation** — `selectEntry`, `selectOption`, `updateHash`, `parseHash`.
12. **Dataset loading** — `validateDataset`, `loadDataset`, `init`.
13. **Event wiring** — buttons, dataset dropdown, arrow keys, `hashchange`.

## Highlight pipeline (the subtle part)

There are **two paths** depending on diagram type, because Mermaid's
sequence-diagram parser rejects the `classDef`/`class` syntax used for
flowcharts. Don't try to unify them.

### Flowcharts (step main diagram, intro overview diagrams)

1. `effectiveDiagramFor(step)` resolves which Mermaid source + highlight
   list to use, accounting for `options` if present (selected option's
   diagram + highlight override the step's).
2. For auto-diff, the *previous* step's "default option" diagram is used
   (not its raw `diagram` field) so options don't break the diff.
3. `resolveHighlights()` returns explicit `highlight` if present, else the
   diff of node IDs.
4. `augmentDiagramWithHighlights()` appends `classDef newNode ...` and
   `class A,B,C newNode` to the Mermaid source before render.
5. CSS in `styles.css` (`.node.newNode > rect|polygon|…`) targets the
   rendered SVG. Mermaid's class assignment ends up on the `.node` group.

### Sequence diagrams (per-step `flows[]`)

1. `extractSequenceParticipants()` parses participant IDs from `participant
   X (as Label)?` declarations and from message-arrow endpoints. Identifier
   class deliberately excludes `-` so arrow tokens (`-->>`, `-x`, `-)`)
   aren't swallowed into the operand.
2. `resolveFlowHighlights(flow, currentStep, allStepsBefore)`:
   - Explicit `flow.highlight` wins (filtered to participants that actually
     appear in this flow).
   - Otherwise union of: participants new to this step (not present in any
     earlier step's flows) + IDs from `currentStep.highlight` that match a
     participant in this flow (inheritance from the main diagram).
3. **Do NOT** mutate the Mermaid source — the sequence parser rejects
   `classDef`. Instead pass the highlight list to `makeMermaidEl()` via
   `opts = { highlightParticipants, sourceForLabels }`.
4. After Mermaid resolves, `applySequenceHighlights()` walks the rendered
   SVG, finds `<text>` elements whose textContent matches a participant
   label (resolved via `parseSequenceParticipantLabels`), and adds the
   `newNode` class to that `<text>` plus the matching participant `<rect>`.
5. CSS selectors that target this path: `rect.newNode`, `text.newNode`,
   plus the `.actor.newNode` family. Keep these alongside the flowchart
   selectors.

### Debugging

If a step diagram highlight breaks visually:
1. Does the node ID match the highlight ID character-for-character?
2. Is the `classDef` line being appended (log `src` in `renderDiagram`)?
3. Did Mermaid emit the class on the SVG `<g class="node …">`?

If a flow diagram highlight breaks:
1. Did `extractSequenceParticipants` find the participant? (Check via the
   inline simulator pattern in the conversation history — node script that
   runs the regex against the diagram source.)
2. Does the visible label match what `parseSequenceParticipantLabels`
   resolved? Mermaid renders the `as <label>` value, not the bare ID.
3. Did `applySequenceHighlights` find a matching `<text>` element in the
   SVG? Mermaid version drift can change SVG structure — broaden the
   selector if needed.

## Mermaid render helper

`makeMermaidEl(diagramSrc, className)` returns a container div and kicks
off `mermaid.render()` asynchronously with a unique id. On render failure
it shows an inline error block under that one diagram instead of crashing
the page. Use it for any *new* Mermaid diagram outside the main step
diagram. The step diagram uses `renderDiagram()` because it needs the
highlight pipeline above.

Mermaid render IDs must be unique per page render. We use a monotonically
incrementing `mermaidIdSeq` plus `Date.now()`. Don't reuse IDs.

## Sidebar grouping conventions

There are exactly three groups: **Overview**, **Architecture**, **Wrap-up**.

- Architecture is always `entries.filter(e => e.kind === 'step')`.
- Wrap-up is `entries with id in WRAPUP_SLUGS`, ordered by `WRAPUP_ORDER`.
- Overview is everything else among intros.

To move a section between Overview and Wrap-up, add/remove its slug from
`WRAPUP_SLUGS` and adjust `WRAPUP_ORDER`. The builder still pushes intros
to the same `entries` array; the grouping is purely a render-time filter.

### Sub-steps (`step.parent`)

A step can declare `parent: "<other-step-id>"`. In the sidebar it renders
with the `nav-item-child` class — indented and prefixed with `↳`. It is
still a normal entry: arrow keys, hash routing, highlight pipeline, and
the flow-diff "previous step" lookup all treat it like any other step.
This is for genuinely smaller scope work — e.g. "3a. Choose the Algorithm"
under "3. Centralized Counter Store" in the rate-limiter dataset. The
parent must reference an existing step id; unknown parents are ignored.

## CSS conventions

- Custom properties at `:root` for the palette (`--accent`, `--highlight`,
  `--border`, …). Use those instead of literal colors.
- Card pattern: `background: var(--panel); border: 1px solid var(--border);
  border-radius: 6px; padding: 10px 14px;`. Used by deep-dive cards,
  proscons columns, API cards, schema cards, satisfies cards, flow cards.
- The `.overview-diagram` class is the base for all intro Mermaid diagrams;
  modifier classes (`.api-diagram`, `.flow-diagram`) override via the
  `.overview-diagram.<modifier>` compound selector — bare modifier selectors
  lose specificity to the base.
- `.bullets`, `.mono`, `.muted` are used widely as small utilities.

## Common pitfalls

- **Editing `interview.json`**: it's a single big JSON object. Use small
  targeted `Edit` ops rather than `Write`-ing the whole file; that's easier
  to review and less likely to drop fields. After every edit, validate with
  `python3 -c "import json; json.load(open('...'))"`.
- **Mermaid node IDs**: must be `[A-Za-z_][A-Za-z0-9_-]*`. The highlight
  regex filter drops anything that doesn't match. If you use a node id with
  a space, slash, or dot, it won't highlight.
- **erDiagram type tokens**: must be a bare identifier (no spaces, no
  punctuation). `autoErDiagramFromDataModel()` sanitizes this — if you write
  an explicit `dataModelDiagram`, do the sanitization yourself.
- **Sentence splitter and abbreviations**: descriptions split into bullets
  on `. ` followed by capital/digit. Common abbreviations (`e.g.`, `i.e.`,
  `etc.`, etc.) are handled — add new ones to `ABBREVS` in
  `splitIntoSentences()` if you see bad splits.
- **Don't reintroduce flow diagrams to `renderIntroApi`**. Per-endpoint
  flows live in `renderIntroApiFlows` (the Wrap-up entry). The Overview
  API section is the contract only.
- **Adding a new dataset**: register it in `data/index.json`, otherwise it
  won't appear in the dropdown.

## When the user asks for a small UI tweak

The instinct is to start a long task list. Don't. For a one-file or
two-file tweak (e.g. "make the bullets denser", "swap two columns"),
just make the edit and confirm. Task tracking is worth it when there are
≥3 distinct steps that span both JSON content and code.

## When the user changes the schema

If a new optional field is added to the schema:
1. Update `PLAN.md` with the new field in the schema block.
2. If it needs validation, add a check in `validateDataset()`.
3. Write the renderer; wire it in.
4. Add styling in `styles.css`.
5. Add sample content to `data/url-shortener/interview.json` so the feature
   is visible immediately (this is the canonical "worked example" dataset).
