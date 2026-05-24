# System Design Step-by-Step Explorer

A lightweight static-HTML app for walking through system design problems
interview-style: requirements first, then capacity, API contract, data model,
the architecture evolution as a sequence of steps, and finally a wrap-up that
ties the design back to the requirements.

Two pages share one stylesheet: an **overview** (`index.html` + `overview.js`)
showing a grid of all interviews grouped into categories, and the
**explorer** (`interview.html` + `interview.js`) for one interview at a time.
Overview cards link to `interview.html#<datasetId>`.

## Goals

- No page-level bundler; the only build step is a copy script (`build.py`)
  that assembles deployable sites into `docs/`. Open a built `index.html` via
  any static server.
- Vanilla HTML / CSS / JS. One external dependency: Mermaid (loaded from CDN).
- Data-driven: every interview is one JSON file; the app reads it and renders.
- Graceful: invalid JSON, missing fields, and Mermaid render errors must not
  break the page. They surface as inline errors.

## Building and running

Sources live in `_templates/` (the shared HTML/CSS/JS shell) and
`data/<group>/` (dataset groups). `build.py` copies them into one deployable
site per group under `docs/<group>/`:

```bash
python3 build.py                       # build every publishable group
python3 -m http.server 8000 -d docs    # serve the built output
# then visit http://localhost:8000/examples/
```

`docs/` is committed and deployed via GitHub Pages (the `/docs` folder). After
editing `_templates/` or `data/`, re-run `build.py` and commit `docs/`.

Opening `index.html` directly via `file://` will fail to fetch the JSON
because of browser CORS rules — use a static server.

## Layout

The page is a two-column layout:

- **Left sidebar** — a navigation list grouped into three sections:
  - **Overview**: Requirements · Capacity Estimation · API Design · Data Model
  - **Architecture**: the sequence of design steps (sub-steps with a
    `parent` field render indented under their parent — useful for focused
    deep-dives on one aspect of a step, like an algorithm choice)
  - **Wrap-up**: API Flows · Design vs. Requirements · Follow-up Questions

  Each item is clickable. The selected item drives the right pane.

- **Right pane** — title, prev/next buttons, step counter, and the rendered
  content for the selected entry (intro section, architecture step, or
  wrap-up section).

Navigation:
- Click any sidebar entry.
- ← / → arrow keys move between entries.
- Prev/Next buttons do the same.
- The URL hash is `#<datasetId>/<entryId>` and is shareable.

## Manifest shape (`index.json`)

A dataset is a JSON file in `data/<group>/<dataset-id>/interview.json`. Each
group's manifest `data/<group>/index.json` lists its datasets, organized into
**categories** the overview renders as sections and the explorer renders as
dropdown `<optgroup>`s. (At runtime the built site fetches `data/index.json`
relative to its own page, i.e. `docs/<group>/data/index.json`.)

```jsonc
{
  "groups": [                          // categories within this site
    {
      "id": "fundamentals",
      "name": "Fundamentals",
      "datasets": [
        {
          "id": "url-shortener",       // also the #hash and icon-dir name
          "name": "URL Shortener",     // shown in card + dropdown
          "path": "data/url-shortener/interview.json"
        }
      ]
    }
  ]
}
```

The overview shows each dataset's icon from `data/<id>/icon.png` (derived from
`path`), falling back to `icons/system-design.png` if that file is missing. A
legacy flat `{ "datasets": [...] }` manifest is still accepted by both
`normalizeManifest` (explorer) and `normalizeGroups` (overview); it renders as
one unnamed category.

## Dataset shape

All fields below are optional except `steps`.

```jsonc
{
  "title": "URL Shortener — System Design",
  "description": "Short blurb shown under the title.",

  // ---- Overview ----
  // Mermaid fields are arrays of source lines. The renderer joins with "\n".
  "requirementsDiagram": ["graph LR", "  ..."],   // optional; above Requirements (direction forced to LR)
  "capacityDiagram":     ["graph LR", "  ..."],   // optional; above Capacity (direction forced to LR)
  "dataModelDiagram":    ["erDiagram", "  ..."],  // optional explicit ER; otherwise auto-derived

  "requirements": {
    "functional":    ["...", "..."],
    "nonFunctional": ["...", "..."]
  },

  "capacity": [
    { "label": "Redirects per second", "value": "~100,000", "note": "100:1 read/write" }
  ],

  "api": [
    {
      "method":      "POST",
      "path":        "/api/v1/shorten",
      "description": "...",
      "request":     "{ \"longUrl\": \"...\" }",
      "response":    "{ \"shortUrl\": \"...\" }",
      "diagram":     ["sequenceDiagram", "  ..."]   // optional; appears in Wrap-up > API Flows only
    }
  ],

  "dataModel": [
    {
      "name": "urls",
      "note": "Primary mapping table.",
      "fields": [
        { "name": "short_code", "type": "varchar(10) PK" },
        { "name": "long_url",   "type": "text" }
      ]
    }
  ],

  // Reusable design patterns this case teaches. Renders as an Overview entry
  // ("Patterns"); `steps` cross-links each pattern to where it appears.
  "patterns": [
    { "name": "Cache-aside", "what": "...", "whenToUse": "...", "steps": ["cache"] }
  ],

  // Standalone pattern reference. Renders as a "Pattern Catalog" entry, grouped
  // by `category`. A dataset with patternCatalog[] and NO steps[] is valid — it
  // is a catalog dataset, not a walkthrough (see data/book/patterns). `usedBy`
  // are free-text case names (they may live in other datasets).
  "patternCatalog": [
    { "name": "Idempotency key", "category": "Reliability & correctness",
      "what": "...", "whenToUse": "...", "tradeoffs": "...", "usedBy": ["Payment System"] }
  ],

  // ---- Architecture steps ---- (optional when patternCatalog is present)
  "steps": [
    {
  "steps": [
    {
      "id":          "cache",
      "title":       "4. Add a Cache for Hot URLs",
      "description": "...",                       // string OR array; strings are auto-bulleted
      "parent":      "load-balancer",             // optional; mark as sub-step of another step (indented in sidebar)

      // EITHER a step-level diagram + highlight ...
      "diagram":   ["graph TB", "  ..."],
      "highlight": ["Cache"],                     // explicit nodeIds to highlight as "new"

      // ... OR options with their own diagram/highlight/pros/cons (tabs above the diagram)
      "options": [
        {
          "name":      "Redis (default)",
          "pros":      ["..."],
          "cons":      ["..."],
          "diagram":   ["graph TB", "  ..."],
          "highlight": ["Cache"]
        },
        { "name": "Memcached", "pros": ["..."], "cons": ["..."], "diagram": ["..."], "highlight": ["..."] }
      ],

      // Per-step education and extras (each optional)
      "decisionPrompt": "What decision should the candidate make at this step?",
      "concepts": [
        {
          "term": "Cache-aside",
          "definition": "The application checks cache first, reads the database on a miss, then backfills the cache.",
          "whyItMatters": "The candidate sees the concept before using it in the design.",
          "example": "GET /short-code reads Redis, then the URL table on cache miss."
        }
      ],
      "whyNow": ["Why this step belongs here in the build order."],
      "patterns": ["Cache-aside", "TTL expiry"],   // optional; reusable-pattern tags (chips), names from dataset-level patterns[]
      "traps": [                                    // optional; common mistakes at this step
        { "trap": "The mistake", "why": "Why it's wrong", "instead": "The better move" }
      ],
      "recap": {
        "before": "What the system could do before this step.",
        "after": "What the system can do now.",
        "newRisk": "The tradeoff or risk introduced by this step."
      },
      "failureDrills": [
        {
          "scenario": "A concrete failure to reason through.",
          "expectedBehavior": "What a good design should do.",
          "mitigation": "How the design absorbs or recovers."
        }
      ],
      "flows": [
        {
          "name":      "Redirect — cache-aside read",
          "note":      "...",
          "diagram":   ["sequenceDiagram", "  ..."],
          "highlight": ["K"]   // optional; explicit participant IDs to mark as new
        }
      ],
      "deepDives":     [{ "title": "Caching policy", "points": ["...", "..."],
                          "diagram": ["graph TB", "  ..."] }],  // optional escape hatch:
                        // a structural diagram for the rare deep dive the main/option/flow
                        // diagrams don't cover. Prefer a sub-step or flow when the depth is
                        // a sub-decision or a sequence; reserve dd.diagram for pure structure.
      "bottlenecks":   [{ "issue": "...", "mitigation": "..." }],
      "talkingPoints": ["...", "..."],
      "interviewerSignals": {
        "strong": ["Evidence the candidate understands the tradeoff."],
        "weak": ["Warning signs or shallow reasoning to watch for."]
      },
      "followUps":     ["..."]
    }
  ],

  // ---- Wrap-up ----
  "finalDesign": {                              // optional; if omitted, no Final Design wrap-up entry is shown
    "title":       "Final Design",
    "description": "End-to-end architecture summary.",
    "diagram":     ["graph TB", "  ..."],
    "highlight":   [],                         // usually empty: final design is a review, not a diff
    "options": [                               // optional; same shape/renderer as step.options
      {
        "name":      "Recommended design",
        "pros":      ["..."],
        "cons":      ["..."],
        "diagram":   ["graph TB", "  ..."],
        "highlight": []
      }
    ]
  },

  "satisfies": {
    "functional": [
      { "requirement": "...", "how": "...", "steps": ["cache", "id-generator"] }
    ],
    "nonFunctional": [ /* same shape */ ]
  },

  // What to say across the interview's phases. Wrap-up entry ("Interview Script").
  "interviewScript": [
    { "phase": "Scope & requirements", "time": "first 5 min", "say": ["...", "..."] }
  ],

  // Junior / senior / staff expectations side by side. Wrap-up entry ("By Level").
  "levelVariants": [
    { "level": "Senior", "expectations": ["...", "..."] }
  ],

  "followUps": ["Dataset-wide follow-up questions..."]
}
```

The four fields above (`patterns`, `step.patterns`, `step.traps`,
`interviewScript`, `levelVariants`) are the **book differentiators** — all
optional, so the 17 example datasets render unchanged. `patterns` and
`step.traps` are exercised in the canonical `url-shortener` example;
`data/book/payment-system` uses all of them.

### Highlighting "new" elements

Mermaid source fields (`requirementsDiagram`, `capacityDiagram`,
`dataModelDiagram`, and every `diagram`) are stored as string arrays with one
array element per Mermaid source line. `interview.js` joins those arrays with `\n`
before rendering. The renderer still accepts legacy string values, but new
datasets should use arrays.

Flowchart **layout direction is forced at render time** via
`forceFlowchartDirection()`, so the authored header direction is ignored for
these four slots: `requirementsDiagram` and `capacityDiagram` render `LR`;
architecture `steps[].diagram` and `finalDesign.diagram` render `TB`. (Other
diagrams — API flows, deep dives, data model — keep their authored direction.)

The main step diagram (a flowchart) marks nodes that are new or changed
relative to the previous step:

- If `step.highlight` (or `step.options[i].highlight`) is present, those IDs
  are highlighted.
- Otherwise the app auto-diffs node IDs against the previous step's
  default-option diagram and highlights the additions.
- Applied by appending Mermaid `classDef newNode ...; class A,B,C newNode;`
  to the source. CSS in `styles.css` targets the rendered SVG.

Per-step flow diagrams (sequence diagrams) get the same treatment for
**participants**, but via a different mechanism (the sequence-diagram parser
rejects `classDef`/`class`):

- If `flow.highlight` is present, those participant IDs are highlighted.
- Otherwise the union of:
  - Participants new to this step (not present in any earlier step's flows), and
  - Participants whose ID matches a node in `step.highlight` (inheritance —
    so "we introduced X" stays consistent between the architecture diagram
    and the flow).
- Applied by patching the rendered SVG after Mermaid renders (adding the
  `newNode` class to the matching participant `<rect>` and `<text>`).

### Where flow diagrams live

- **Per-step flows** (`step.flows`) appear under each architecture step as a
  **tab strip** — one tab per flow, one flow visible at a time. Tab state
  resets to the first flow on step/dataset change.
- **Per-endpoint flows** (`api[i].diagram`) appear in the **Wrap-up → API
  Flows** section, not in the Overview → API Design section. Flows belong
  after the architecture is established. Endpoints without a `diagram` still
  render in the API Flows section but show an inline placeholder.

## File map

Sources (edit these):

- `_templates/index.html`     — Overview page: shell for the interview grid.
- `_templates/overview.js`    — Overview behavior: fetch manifest, render cards.
- `_templates/interview.html` — Explorer page: sidebar, content panes, mounts.
- `_templates/interview.js`   — Explorer behavior: dataset loading, sidebar
                                grouping, all rendering, Mermaid orchestration,
                                hash routing, keyboard nav, error capture.
- `_templates/styles.css`     — All styling for both pages, including the
                                `.newNode` highlight rules applied to
                                Mermaid-rendered SVG nodes.
- `_templates/icons/system-design.png` — Fallback interview icon.
- `data/<group>/index.json`              — One site's manifest (`groups[]`).
- `data/<group>/<id>/interview.json`     — One dataset per directory.
- `data/<group>/<id>/icon.png`           — Optional per-interview icon.
- `build.py`               — Copy step: `_templates/` + `data/<group>/` →
                             `docs/<group>/`.

Build output (generated, committed for GitHub Pages — do not hand-edit):

- `docs/<group>/{index.html,overview.js,interview.html,interview.js,styles.css}`
  plus `icons/` — copies of the templates.
- `docs/<group>/data/...`                        — copy of the group's data.

Existing dataset: `data/examples/url-shortener/interview.json` — a fully
populated URL shortener walkthrough used as the worked example.

## Implementation notes

- Mermaid `securityLevel: 'strict'`. Diagrams are static; bumping to `loose`
  would only matter if we wanted clickable nodes inside diagrams.
- Each Mermaid render gets a unique element id (`mermaid-…-<seq>`); render
  errors are caught per-diagram and shown inline so one bad source doesn't
  break the page.
- The dataset validator only requires a non-empty `steps[]` and that each
  step has either a step-level `diagram` or non-empty `options[].diagram`.
  Every other field is optional and renders only if present.
- Sentence-splitting of `description` strings tolerates common abbreviations
  (`e.g.`, `i.e.`, `etc.`, etc.) so they don't break into separate bullets.

## Extending

Adding a new dataset:
1. Create `data/<group>/<id>/interview.json` following the schema above.
2. Add it to a category in that group's `data/<group>/index.json`
   (`groups[i].datasets[]`: `id`, `name`, `path`).
3. Optionally add `data/<group>/<id>/icon.png` for the overview card.
4. Run `python3 build.py`, reload. It appears in the overview and dropdown.

Adding a new category (a section within one site):
1. Add a `{ id, name, datasets: [...] }` entry to `groups[]` in that site's
   `index.json`. The overview adds a section and the dropdown an `<optgroup>`.

Adding a new group (a new deployable site):
1. Create `data/<group>/` with an `index.json` manifest and dataset subdirs.
2. Run `python3 build.py`; it produces `docs/<group>/` automatically.

Adding a new section type:
1. Add a slug to `INTRO_SLUGS` in `_templates/interview.js`.
2. Add a builder branch in `buildEntries()`.
3. Add the section to the `Overview` or `Wrap-up` group via `WRAPUP_SLUGS`.
4. Write a `renderIntro<Name>()` function returning a DOM node, and wire it
   into the switch in `renderIntroEntry()`.
5. Add CSS in `_templates/styles.css` if the section needs custom layout.
6. Run `python3 build.py` and commit the regenerated `docs/`.
