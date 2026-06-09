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
  - **Architecture**: the sequence of design steps (sub-steps with a `parent`
    field render indented under their parent — useful for focused deep-dives
    on one aspect of a step, like an algorithm choice), and the **Target Final
    Design** — which leads with an auto-generated **decision-tree map** (steps
    as nodes, their options as branches, converging on the final design; nodes
    are clickable) shown above the final architecture diagram
  - **Wrap-up**: Design vs. Requirements · Technology Choices · API Flows · By Level · Follow-up Questions · To Probe Further

  Each item is clickable. The selected item drives the right pane.

- **Right pane** — title, prev/next buttons, step counter, and the rendered
  content for the selected entry (intro section, architecture step, or
  wrap-up section). Step and Target Final Design architecture diagrams are
  interactive: a controls panel to the right of the diagram lets you toggle
  individual nodes on/off (hidden nodes drop their edges), flip the layout
  between top–down (default) and left–right, and download the diagram as SVG.
  The toggle/direction state is per-diagram and resets when you move to another
  step/option/view.

Navigation:
- Click any sidebar entry.
- ← / → arrow keys move between entries.
- Prev/Next buttons do the same.
- The URL hash is `#<datasetId>/<entryId>` and is shareable.

## Manifest shape (`index.json`)

A dataset is a JSON file in `data/<group>/<dataset-id>/interview.json`. Each
group's manifest `data/<group>/index.json` lists its datasets, organized into
**categories** the overview renders as sections. (At runtime the built site
fetches `data/index.json` relative to its own page, i.e.
`docs/<group>/data/index.json`.)

```jsonc
{
  "groups": [                          // categories within this site
    {
      "id": "fundamentals",
      "name": "Fundamentals",
      "datasets": [
        {
          "id": "url-shortener",       // also the #hash and icon-dir name
          "name": "URL Shortener",     // shown on the overview card
          "path": "data/url-shortener/interview.json"
        }
      ]
    }
  ]
}
```

The overview shows each dataset's icon from `data/<id>/icon.png` (derived from
`path`), falling back to `icons/system-design.png` if that file is missing.
The explorer header shows the same icon (resolved from `assets.icon`, a
manifest `icon`, or the `<dir>/icon.png` convention) beside the interview title
— but only when it's defined and actually loads; there's no fallback there, so
a missing icon just leaves the title alone.

## Dataset shape

All fields below are optional except `highLevelArchitecture` and either
`steps` or `patternCatalog`. `highLevelArchitecture` always contains `nodes`,
`links`, and `types` arrays; catalog datasets may keep them empty.

```jsonc
{
  "title": "URL Shortener — System Design",
  "description": "Short blurb shown under the title.",
  "assets": {
    "icon": "icon.png"                                      // optional; dataset overview icon
  },
  "aiVisuals": {                                            // optional; AI-generated images for the intro sections
    "requirements": "assets/generated/ai-visuals/requirements.png", // toggled via Diagram|AI Visual in Requirements
    "capacity":     "assets/generated/ai-visuals/capacity.png"      // toggled via Diagram|AI Visual in Capacity Estimation
  },

  // Explicit high-level architecture metadata used for generated views,
  // node captions, sequence participant annotations, and styling.
  "highLevelArchitecture": {
    // Each node is keyed at render time by exact (id + label); if an id appears
    // with multiple labels, the exact label disambiguates sequence participants
    // like C/P/I/R that are reused inside one dataset.
    "nodes": [
      {
        "id": "Cache",                         // Mermaid node/participant id
        "label": "Redis Cache",                // exact rendered label in the diagram
        "type": "cache",                       // canonical type from _templates/node-types.json
        "category": "state",                   // boundary | traffic | compute | async | state | ops
        "traits": ["stateful", "derived"],      // optional badges/semantics
        "description": "Fast derived state layer used to reduce DB load."
      }
    ],

    // Canonical architecture links used by structured step views. `from` and `to`
    // reference node ids from highLevelArchitecture.nodes. `render` is optional
    // and should stay an escape hatch for Mermaid-specific arrows/classes.
    // NOTE: generated architecture diagrams (steps, options, final design,
    // full context) draw connections as plain lines with NO arrowheads —
    // `graphLinkLine` strips the arrowhead from whatever token `render.arrow`
    // resolves to, keeping only the line style (solid `---` / dotted `-.-`).
    // The decision-tree map keeps its directed arrows.
    "links": [
      {
        "id": "client-cache",
        "from": "Client",
        "to": "Cache",
        "label": "read hot URL",
        "kind": "sync",
        "description": "Client request reaches the hot redirect cache.",
        "render": { "arrow": "-->" }
      }
    ],

    // Optional subgraph grouping for generated architecture diagrams. Named
    // types rather than groups to avoid collision with manifest categories.
    "types": [
      { "id": "read-path", "label": "Read Path", "nodes": ["Client", "Cache", "DB"] }
    ]
  },

  // ---- Overview ----
  // Raw Mermaid overview fields are arrays of source lines. The renderer joins
  // with "\n". Requirements/capacity render without node-type HTML annotation;
  // keep them simple, metric-oriented sketches.
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
      "sequence": {                                  // optional; appears in Wrap-up > API Flows only
        "participants": [
          { "id": "Client" },
          { "id": "App", "label": "App Server" },
          { "id": "DB", "label": "URL Store" }
        ],
        "messages": [
          { "from": "Client", "to": "App", "label": "POST /api/v1/shorten" },
          { "from": "App", "to": "DB", "label": "persist mapping" },
          { "from": "App", "to": "Client", "arrow": "-->>", "label": "201 shortUrl" }
        ]
      }
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
  // ("Patterns"), grouped by `group`; `steps` cross-links each pattern to
  // where it appears.
  "patterns": [
    { "name": "Cache-aside", "group": "Caching and read path", "what": "...", "whenToUse": "...", "steps": ["cache"],
      "icon": "assets/icons/patterns/cache-aside.png" }
  ],

  // Standalone pattern reference. Renders as a "Pattern Catalog" entry, grouped
  // by `category`. A dataset with patternCatalog[] and NO steps[] is valid — it
  // is a catalog dataset, not a walkthrough (see data/book/patterns).
  //   - `aliases[]`: case-study tag synonyms that map to this canonical name
  //     (rendered as "Also called" chips); makes the catalog name the canonical
  //     vocabulary so case `step.patterns[]` tags can be linked back to it.
  //   - `pairsWith[]` / `commonlyConfusedWith[]`: other catalog pattern names,
  //     rendered as relationship chips ("Pairs with" / "Confused with").
  //   - `usedBy[]`: each entry is either a free-text case name (string) OR an
  //     object `{ datasetId, label }`; a datasetId makes the chip a link to that
  //     case study (hash `#<datasetId>`). datasetIds must exist in the group's
  //     index.json.
  "patternCatalog": [
    { "name": "Idempotency key", "category": "Reliability & correctness",
      "what": "...", "whenToUse": "...", "tradeoffs": "...",
      "aliases": ["Idempotent confirm"],
      "pairsWith": ["Deduplication"], "commonlyConfusedWith": ["Deduplication"],
      "usedBy": [{ "datasetId": "payment-system", "label": "Payment System" }],
      "icon": "assets/icons/patterns/idempotency-key.png" }
  ],

  // ---- Architecture steps ---- (optional when patternCatalog is present)
  "steps": [
    {
      "id":          "cache",
      "title":       "4. Add a Cache for Hot URLs",
      "description": "...",                       // string OR array; strings are auto-bulleted
      "parent":      "load-balancer",             // optional; mark as sub-step of another step (indented in sidebar)

      // Architecture steps use structured graph views. The renderer generates
      // Mermaid from the node/link catalog and type settings.
      "view": {
        "nodes": [
          { "id": "Client", "label": "Client / Browser" },
          { "id": "Cache", "label": "Redis Cache" },
          { "id": "DB", "label": "Mapping Store" }
        ],
        "links": ["client-cache", "cache-db"],
        "groups": ["read-path"],                 // optional highLevelArchitecture.types ids
        "highlight": ["Cache"],
        "caption": "The app checks the cache, then reads the mapping store on a miss." // optional; one-line "what this diagram shows", rendered under the diagram (above pros/cons)
      },

      "aiVisual": "assets/generated/ai-visuals/steps/04-cache.png", // optional; AI image for this step, toggled via the Diagram|AI Visual tab (used when the step has no options)

      // Options may define their own view/pros/cons (tabs above the diagram).
      "options": [
        {
          "name":      "Redis (default)",
          "pros":      ["..."],
          "cons":      ["..."],
          "view":      { "nodes": ["App", "Redis", "DB"], "links": ["app-redis", "redis-db"], "highlight": ["Redis"] },
          "aiVisual":  "assets/generated/ai-visuals/steps/04-cache-opt1.png" // optional; per-option AI image; the AI Visual follows the selected option tab
        },
        { "name": "Memcached", "pros": ["..."], "cons": ["..."], "view": { "nodes": ["App", "Memcached", "DB"], "links": ["app-memcached", "memcached-db"] } }
      ],

      // Per-step education and extras (each optional)
      "decisionPrompt": "What decision should the candidate make at this step?",
      "concepts": [
        {
          "term": "Cache-aside",
          "group": "Caching and read path",
          "definition": "The application checks cache first, reads the database on a miss, then backfills the cache.",
          "whyItMatters": "The candidate sees the concept before using it in the design.",
          "example": "GET /short-code reads Redis, then the URL table on cache miss.",
          "icon": "assets/icons/concepts/cache-aside.png"
        }
      ],
      "whyNow": ["Why this step belongs here in the build order."],
      "patterns": ["Cache-aside", "TTL expiry"],   // optional; reusable-pattern tags (chips), names from dataset-level patterns[]
      "probeLinks": ["youtube-dnn"],                // optional; IDs from toProbeFurther.links[], rendered at step end
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
          "sequence": {
            "participants": [
              { "id": "Client" },
              { "id": "Cache", "label": "Redis Cache" },
              { "id": "DB", "label": "Mapping Store" }
            ],
            "messages": [
              { "from": "Client", "to": "Cache", "label": "GET short code" },
              {
                "type": "alt",
                "label": "cache miss",
                "messages": [
                  { "from": "Cache", "to": "DB", "label": "load mapping" },
                  { "from": "DB", "to": "Cache", "arrow": "-->>", "label": "long URL" }
                ],
                "else": {
                  "label": "cache hit",
                  "messages": [
                    { "from": "Cache", "to": "Client", "arrow": "-->>", "label": "redirect target" }
                  ]
                }
              }
            ]
          },
          "highlight": ["Cache"]   // optional; explicit participant/node IDs to mark as new
        }
      ],
      "deepDives":     [{ "title": "Caching policy", "points": ["...", "..."],
                          "view": { "nodes": ["App", "Cache", "DB"], "links": ["app-cache", "cache-db"] } }],
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
  "finalDesign": {                              // optional; if omitted, no "Target Final Design" architecture entry is shown. The entry is always labelled "Target Final Design" in the UI; this object's `title` is not displayed.
    "title":       "Final Design",
    "description": "End-to-end architecture summary.",
    "aiVisual":    "assets/generated/ai-visuals/final-design.png", // optional; AI-generated image, toggled via the Diagram|AI Visual tab
    "view":        { "nodes": ["Client", "App", "Cache", "DB"], "links": ["client-app", "app-cache", "cache-db"] },
    "options": [                               // optional; same shape/renderer as step.options
      {
        "name":      "Recommended design",
        "pros":      ["..."],
        "cons":      ["..."],
        "view":      { "nodes": ["Client", "App", "Cache", "DB"], "links": ["client-app", "app-cache", "cache-db"] }
      }
    ]
  },

  "satisfies": {
    "functional": [
      // optional aiVisual: per-requirement "how the design meets it" illustration,
      // generated by generate_design_vs_requirements_pictures.py, shown in the card
      { "requirement": "...", "how": "...", "steps": ["cache", "id-generator"], "aiVisual": "assets/generated/design-vs-requirements/func-01-....png" }
    ],
    "nonFunctional": [ /* same shape, incl. optional aiVisual */ ]
  },

  // Wrap-up "Technology Choices" entry (between Design vs. Requirements and API
  // Flows). One object per architecture concern: self-hosted vs cloud-native/SaaS.
  "technologyChoices": [
    {
      "concern": "Relational database",
      "steps": ["database", "replication", "sharding"], // optional; clickable cross-links
      // each chip is a string OR { name, icon }; assign_tech_icons.py rewrites
      // strings into { name, icon } with a copied assets/tech-icons/<file> path
      "selfHosted": [{ "name": "PostgreSQL", "icon": "assets/tech-icons/postgresql.png" }, "MySQL", "Vitess"],
      "cloud": { "aws": ["RDS", "Aurora"], "gcp": ["Cloud SQL", "Spanner"], "azure": ["SQL Database", "Cosmos DB"] },
      "tradeoff": "self-host when ...; managed when ...",
      "makesIrrelevant": "A managed autoscaling/distributed SQL engine can absorb growth so you never hand-shard."
    }
  ],

  // What to say across the interview's phases. Overview entry ("Interview Script").
  "interviewScript": [
    { "phase": "Scope & requirements", "time": "first 5 min", "say": ["...", "..."] }
  ],

  // Junior / senior / staff expectations side by side. Wrap-up entry ("By Level").
  "levelVariants": [
    { "level": "Senior", "expectations": ["...", "..."] }
  ],

  "followUps": ["Dataset-wide follow-up questions..."],

  // Canonical external reading list. Wrap-up entry ("To Probe Further").
  // Steps reference these by id via step.probeLinks[].
  "toProbeFurther": {
    "links": [
      {
        "id": "youtube-dnn",
        "group": "Production systems",
        "groupDescription": "Primary sources and realistic references for readers who want to go deeper.",
        "title": "Deep Neural Networks for YouTube Recommendations",
        "url": "https://research.google/pubs/deep-neural-networks-for-youtube-recommendations/",
        "source": "Google Research",
        "type": "Paper",
        "year": "2016",
        "why": "Shows the classic candidate-generation plus ranking split at large scale."
      }
    ]
  }
}
```

The fields above (`patterns`, `patternCatalog`, `step.concepts`, `step.patterns`, `step.traps`,
`step.probeLinks`, `interviewScript`, `levelVariants`, `toProbeFurther`) are the **book differentiators** — all
optional, so example datasets render unchanged. `patterns` and
deduped `step.concepts` are grouped by their optional `group` on the Overview
pages; step pages still render the local concept and pattern cards flat.
`step.traps` are exercised in the canonical `url-shortener` example;
`data/book/payment-system` uses all of them.
Generated visual assets are optional too: absent `assets`/`icon`, `aiVisual`,
or `aiVisuals` fields simply render nothing. When an `aiVisual` (per step,
option, or finalDesign) or an `aiVisuals.{requirements,capacity}` path is
present, the section shows a **Diagram | AI Visual** tab to flip between the
Mermaid diagram and the generated image. Each `satisfies.{functional,
nonFunctional}[]` item may also carry an `aiVisual` (a per-requirement "how the
design meets it" illustration), rendered inline inside that requirement's card
in the Wrap-up "Design vs. Requirements" section — written by
`generate_design_vs_requirements_pictures.py`.

`highLevelArchitecture` is required for every dataset and always contains
`nodes`, `links`, and `types` arrays; catalog datasets may keep all three empty.
The renderer uses explicit `highLevelArchitecture.nodes` metadata for type
styling and does not infer node types from labels. Architecture steps should
use `view`, not hand-authored Mermaid flowcharts; `step.diagram`,
`step.options[].diagram`, `step.deepDives[].diagram`, `finalDesign.diagram`,
and `finalDesign.options[].diagram` are rejected. Temporal flows use structured
`sequence` objects, not raw Mermaid `diagram` fields, so participants reuse the
same node ids, labels, type styling, and highlights as architecture diagrams.
Canonical `type` values are documented in
`_templates/node-types.json`: `actor`, `client`, `edge`, `gateway`, `service`,
`orchestrator`, `worker`, `queue`, `stream`, `cache`, `database`,
`object-storage`, `index`, `model`, `observability`, and `external`.
Use `actor` for human or organization roles and `client` for browsers, mobile
apps, SDKs, portals, dashboards, devices, and other caller software outside the
backend boundary.
Statefulness is represented as a trait (`stateful` / `stateless`), not as a
separate primary type.
Node rendering is also configured there: `rendering.types[type]` defines the
default Mermaid shape, fill, stroke, text color, and class name for that type.
Renderer code should not infer shape or color from type names; it only reads
the config, with `view.nodes[].render.shape` reserved as a local escape hatch.

### Highlighting "new" elements

Raw Mermaid source fields (`requirementsDiagram`, `capacityDiagram`, and
optional `dataModelDiagram`) are stored as string arrays with one array element
per Mermaid source line. `interview.js` joins those arrays with `\n` before
rendering. Architecture and flow diagrams are structured data now: use `view`
for graph diagrams and `sequence` for temporal flows.

Flowchart **layout direction is forced at render time** via
`forceFlowchartDirection()`: `requirementsDiagram` and `capacityDiagram` render
`LR`; generated architecture step/final/deep-dive views render `TB`. Data model
ER diagrams keep their authored direction.

Requirements/capacity overview diagrams render with `annotateNodeTypes: false`
so their metric labels are not wrapped in inline HTML. Generated architecture
views still get type captions and configured shapes/colors from
`_templates/node-types.json`.

The main step diagram (a flowchart) marks nodes that are new or changed
relative to the previous step:

- If `step.view.highlight` (or `step.options[i].view.highlight`) is present,
  those IDs are highlighted.
- Otherwise the app auto-diffs node IDs against the previous step's generated
  default-option view and highlights the additions.
- Applied by appending Mermaid `classDef newNode ...; class A,B,C newNode;`
  to the source. CSS in `styles.css` targets the rendered SVG.

Each view may carry an optional `caption` string: a one-line description of
**what that diagram shows** (its components and how they connect), rendered
under the diagram and just above the pros/cons. The renderer shows the caption
of the active view — the selected option's view, or the step view when there
are no options — and hides it in the "Full context" diagram mode. It is
diagram-specific and intentionally distinct from the step/option prose.

Per-step flow diagrams (`sequence` objects) get the same treatment for
**participants**, but via a different mechanism (the sequence-diagram parser
rejects `classDef`/`class`):

- If `flow.highlight` is present, those participant IDs are highlighted.
- If a flow uses `sequence`, participants should reference canonical
  `highLevelArchitecture.nodes` ids. Optional `alias` keeps compact Mermaid
  participant names while styling and highlighting still resolve to the
  canonical node id.
- Otherwise the union of:
  - Participants new to this step (not present in any earlier step's flows), and
  - Participants whose ID matches a node in `step.view.highlight`
    (inheritance — so "we introduced X" stays consistent between the
    architecture diagram and the flow).
- Applied by patching the rendered SVG after Mermaid renders (adding the
  `newNode` class to the matching participant `<rect>` and `<text>`).

### Where flow diagrams live

- **Per-step flows** (`step.flows`) appear under each architecture step as a
  **tab strip** — one tab per flow, one flow visible at a time. Tab state
  resets to the first flow on step/dataset change.
- **Per-endpoint flows** (`api[i].sequence`) appear in the **Wrap-up → API
  Flows** section, not in the Overview → API Design section. Flows belong
  after the architecture is established. Endpoints without a flow still render
  in the API Flows section but show an inline placeholder.

## File map

Sources (edit these):

- `_templates/index.html`     — Overview page: shell for the interview grid.
- `_templates/overview.js`    — Overview behavior: fetch manifest, render cards.
- `_templates/interview.html` — Explorer page: sidebar, content panes, mounts.
- `_templates/interview.js`   — Explorer behavior: dataset loading, sidebar
                                grouping, all rendering, Mermaid orchestration,
                                hash routing, keyboard nav, error capture.
- `_templates/node-types.json` — Canonical node types plus Mermaid shape/color
                                 rendering settings.
- `_templates/styles.css`     — All styling for both pages, including the
                                `.newNode` highlight rules applied to
                                Mermaid-rendered SVG nodes.
- `_templates/icons/system-design.png` — Fallback interview icon.
- `data/<group>/index.json`              — One site's manifest (`groups[]`).
- `data/<group>/<id>/interview.json`     — One dataset per directory.
- `data/<group>/<id>/icon.png`           — Optional per-interview icon.
- `data/<group>/<id>/assets/icons/...`   — Optional generated pattern/concept icons linked from JSON.
- `data/<group>/<id>/assets/generated/ai-visuals/...` — Optional AI-generated visuals (`aiVisual`/`aiVisuals`), one per step/option/section, written by `generate_diagram_picture.py`.
- `data/<group>/<id>/assets/generated/design-vs-requirements/...` — Optional per-requirement illustrations (`satisfies[].aiVisual`), written by `generate_design_vs_requirements_pictures.py`.
- `_scripts/generate_interview_assets.py` — Generates interview assets and writes JSON links.
- `build.py`               — Copy step: `_templates/` + `data/<group>/` →
                             `docs/<group>/`.

Build output (generated, committed for GitHub Pages — do not hand-edit):

- `docs/<group>/{index.html,overview.js,interview.html,interview.js,styles.css}`
  plus `node-types.json` and `icons/` — copies of the templates.
- `docs/<group>/data/...`                        — copy of the group's data.

Existing dataset: `data/examples/url-shortener/interview.json` — a fully
populated URL shortener walkthrough used as the worked example.

## Implementation notes

- Mermaid `securityLevel: 'strict'`. Diagrams are static; bumping to `loose`
  would only matter if we wanted clickable nodes inside diagrams.
- Each Mermaid render gets a unique element id (`mermaid-…-<seq>`); render
  errors are caught per-diagram and shown inline so one bad source doesn't
  break the page.
- The dataset validator requires `highLevelArchitecture.nodes`,
  `highLevelArchitecture.links`, and `highLevelArchitecture.types` arrays, plus
  either non-empty `steps[]` or non-empty `patternCatalog[]`. Each step and
  final design must have a `view` or options with views. Step/final/deep-dive
  graph diagrams must use structured `view` objects; flow diagrams must use
  structured `sequence` objects.
- Generated asset paths are relative to the dataset directory. Pattern and
  concept icons live on the object they describe (`icon`). Full diagram-
  replacement images use `aiVisual` on a step/option/finalDesign and
  `aiVisuals.{requirements,capacity}` at the top level; the explorer shows a
  Diagram|AI Visual toggle when present. A `satisfies.{functional,
  nonFunctional}[]` item may carry its own `aiVisual` (per-requirement
  illustration), rendered inline in the "Design vs. Requirements" card.
- Sentence-splitting of `description` strings tolerates common abbreviations
  (`e.g.`, `i.e.`, `etc.`, etc.) so they don't break into separate bullets.

## Extending

Adding a new dataset:
1. Create `data/<group>/<id>/interview.json` following the schema above.
2. Add it to a category in that group's `data/<group>/index.json`
   (`groups[i].datasets[]`: `id`, `name`, `path`).
3. Optionally add `data/<group>/<id>/icon.png` for the overview card.
4. Run `python3 build.py`, reload. It appears in the overview (and is reachable
   in the explorer via its `#<id>` hash).

Adding a new category (a section within one site):
1. Add a `{ id, name, datasets: [...] }` entry to `groups[]` in that site's
   `index.json`. The overview adds a section for it.

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
