# Interview dataset schema (reference)

A dataset is one JSON object at `data/<group>/<id>/interview.json`. Below is
every field the renderer + `data/book/_verify.mjs` understand. Optional unless
marked required.

## Top level

```jsonc
{
  "title": "URL Shortener — System Design",          // required
  "description": "One-paragraph blurb under the title.", // required

  "highLevelArchitecture": { ... },                   // required (see below)

  "requirementsDiagram": ["graph LR", "  ..."],       // optional raw Mermaid (rendered LR)
  "capacityDiagram":     ["graph LR", "  ..."],       // optional raw Mermaid (rendered LR)
  "dataModelDiagram":    ["erDiagram", "  ..."],      // optional; else auto-derived from dataModel

  "requirements": { "functional": ["..."], "nonFunctional": ["..."] },
  "capacity":     [ { "label": "...", "value": "...", "note": "..." } ],
  "api":          [ { "method", "path", "description", "request", "response", "sequence"? } ],
  "dataModel":    [ { "name", "note", "fields": [ { "name", "type" } ] } ],

  "patterns":        [ { "name", "what", "whenToUse"?, "steps"?: ["stepId"] } ],
  "steps":           [ { ...step... } ],              // required (OR patternCatalog[])
  "finalDesign":     { "title", "description", "view", "options"?, "flows"? },
  "satisfies":       { "functional": [ {requirement,how,steps:["id"]} ], "nonFunctional": [ ... ] },
  "interviewScript": [ { "phase", "time"?, "say": "..."|["..."] } ],
  "levelVariants":   [ { "level", "expectations": ["..."] } ],
  "followUps":       ["..."]
}
```

## highLevelArchitecture (required)

```jsonc
"highLevelArchitecture": {
  "nodes": [
    {
      "id": "Cache",                 // Mermaid-safe id: [A-Za-z_][A-Za-z0-9_-]*
      "label": "Redis Cache",        // human label (plain text; renderer escapes)
      "type": "cache",               // one of the canonical types (below)
      "category": "state",           // boundary|traffic|compute|async|state|ops
      "traits": ["stateful","derived"], // [] is fine
      "description": "Hot derived-state layer in front of the DB."
    }
  ],
  "links": [
    { "id": "client-cache", "from": "Client", "to": "Cache", "label": "read hot key" }
  ],
  "types": [                          // optional subgraph groups; [] is fine
    { "id": "read-path", "label": "Read Path", "nodes": ["Client","Cache","DB"] }
  ]
}
```

Canonical node `type` values (from `_templates/node-types.json`):
`actor, client, edge, gateway, service, orchestrator, worker, queue, stream,
cache, database, object-storage, index, model, observability, external`.
- `actor` = humans/orgs; `client` = browsers/apps/SDKs/devices.
- Statefulness is a **trait** (`stateful`/`stateless`), not a type.

## Step

```jsonc
{
  "id": "cache",
  "title": "4. Add a Cache for Hot Keys",
  "description": "string OR [array of sentences]",
  "parent": "load-balancer",          // optional: makes this a sub-step (indented ↳)
  "view": {                           // structured graph view (NOT raw Mermaid)
    "nodes": ["Client","Cache","DB"], // ID refs into highLevelArchitecture.nodes
    "links": ["client-cache","cache-db"], // ID refs into highLevelArchitecture.links
    "highlight": ["Cache"],           // subset of view.nodes — the step's focus
    "groups": ["read-path"]           // optional highLevelArchitecture.types ids
  },
  "options": [                        // optional A/B tabs; each has its own view/pros/cons
    { "name", "pros":["..."], "cons":["..."], "view": { ... } }
  ],
  "decisionPrompt": "What should the candidate decide here?",
  "concepts": [ { "term", "definition", "whyItMatters", "example" } ],
  "whyNow": ["Why this step belongs here in the build order."],
  "patterns": ["Cache-aside"],        // pattern-name chips (match dataset patterns[])
  "traps": [ { "trap", "why", "instead" } ],
  "recap": { "before": "...", "after": "...", "newRisk": "..." },
  "failureDrills": [ { "scenario", "expectedBehavior", "mitigation" } ],
  "flows": [ { ...flow... } ],        // see flow grammar below
  "deepDives": [ { "title", "points":["..."], "view"?: { ... } } ],
  "bottlenecks": [ { "issue", "mitigation" } ],
  "talkingPoints": ["..."],
  "interviewerSignals": { "strong":["..."], "weak":["..."] },
  "followUps": ["..."]
}
```

### Step-flow shape (naive → core → refinements → scale)

- **Step 1 is the naive baseline.** Title like `1. Naive: <simplest design>
  (the baseline)`. Its `view` uses a small subset of the HLA (client → one
  service → one store). Description: explain the simple design, then enumerate
  the problems it has (which the next steps remove). Include a `traps` entry
  ("shipping the naive design as good enough") and a `recap`.
- Each later step introduces ONE mechanism, highlights the node(s) it adds via
  `view.highlight`, and ends with a `recap.newRisk` that motivates the next.
- Last step is typically scaling/operability.

## Flow grammar (sequence diagrams)

```jsonc
{
  "name": "Redirect — cache-aside read",
  "note": "Transient failures retry with backoff; permanent ones dead-letter.",
  "sequence": {
    "participants": [
      { "id": "Client" },
      { "id": "Cache", "label": "Redis Cache" }   // label optional; id should be an HLA node id
    ],
    "messages": [
      { "from": "Client", "to": "Cache", "arrow": "->>", "label": "GET key" },
      {
        "type": "alt", "label": "cache miss",
        "messages": [
          { "from": "Cache", "to": "DB",     "arrow": "->>",  "label": "load" },
          { "from": "DB",    "to": "Cache",  "arrow": "-->>", "label": "value" }
        ],
        "else": {
          "label": "cache hit",
          "messages": [ { "from": "Cache", "to": "Client", "arrow": "-->>", "label": "value" } ]
        }
      }
    ]
  },
  "highlight": ["Cache"]   // optional; must be participants IN this flow
}
```

- Arrows: `"->>"` synchronous call, `"-->>"` response/return.
- `participants[].id` should reference `highLevelArchitecture.nodes` ids so the
  diagram's highlight stays consistent with the step's `view.highlight`.
- Add flows to the 2–3 most interaction-heavy steps. Skip purely structural
  (topology-only) steps.

## What `data/book/_verify.mjs` enforces

- `highLevelArchitecture.nodes/links/types` are arrays.
- Each `view.nodes` ref resolves to a real node id; each `view.links` ref
  resolves to a real link id; `view.highlight` ⊆ `view.nodes`;
  `view.groups` resolve to `types` ids.
- No step uses a legacy `diagram` field (must use `view`); flows use
  `sequence` (no raw flow Mermaid).
- `flow.highlight` (or `sequence.highlight`) ids appear as participants.
- `satisfies.*[].steps` and `patterns[].steps` reference existing step ids.
- Sub-step `parent` references an existing step id.

## Catalog datasets (no steps)

A dataset with a non-empty `patternCatalog[]` and NO `steps[]` is valid (a
reference catalog, like `data/book/patterns`). Each catalog entry:
`{ name, category?, what, whenToUse?, tradeoffs?, usedBy? }`.
