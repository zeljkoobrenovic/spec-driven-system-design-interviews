---
name: new-interview
description: Scaffold a new system-design interview dataset from a brief problem description. Use when the user asks to "add an interview", "create a new interview/dataset/case", or "design <X> as an interview" for this explorer. Produces data/<group>/<id>/interview.json, registers it in index.json, builds, and verifies.
argument-hint: <brief problem description> [group=book|examples]
---

# Author a new interview dataset

Turn a brief problem description into a complete, verifier-passing interview
dataset for this explorer. Follow the conventions of the existing book
datasets exactly — they were built and reviewed to a consistent shape.

## Input

`$ARGUMENTS` is a brief description of the system to design (e.g. "a URL
shortener", "a distributed rate limiter", "TikTok short-video feed"). An
optional `group=book` or `group=examples` selects the dataset group; default
to **book**. If the description is too vague to scope, ask one clarifying
question (what the system primarily does + the hardest non-functional
requirement), then proceed.

## Steps

1. **Pick an id, group, and category.**
   - `id`: short kebab-case (e.g. `url-shortener`, `rate-limiter`). Must not
     collide with an existing `data/<group>/<id>/` dir.
   - `group`: `book` (default) or `examples`.
   - For `book`, choose the best-fit category from `data/book/index.json`
     `groups[]` (e.g. Messaging & Real-Time, Infrastructure & Distributed
     Systems, …). If none fits, add a new `{id,name,datasets:[]}` category.

2. **Design the architecture (realistically).** Sketch the real-world design
   for this system — match how real systems (Kafka, S3, Dynamo, Stripe,
   Google Docs, etc.) actually solve it. Decide:
   - The `highLevelArchitecture` node catalog: every node with an `id`,
     `label`, `type` (from the canonical vocabulary), `category`, `traits`,
     and a one-line `description`.
   - The link catalog: each `{id, from, to, label}`.
   - 5–7 steps that progress **naive → core mechanism → refinements → scale**.
     **Step 1 MUST be a genuine naive baseline** ("the simplest thing that
     works, and why it fails") that motivates step 2.
   - Which 2–3 steps deserve a **sequence `flow`** (request/write paths, async
     handoffs, sagas, fanout, quorum/consensus, hit/miss branches).
   - Optionally a sub-step (`parent`) where one step genuinely forks or
     bundles two decisions.

3. **Generate the dataset.** Easiest path: copy and fill in the builder
   template, run it, then delete it:
   - Copy `${CLAUDE_SKILL_DIR}/scripts/build_dataset.py` to
     `data/<group>/<id>/_build.py`.
   - Fill in `NODES`, `LINKS`, the steps, `finalDesign`, `satisfies`,
     `interviewScript`, `levelVariants`, `followUps` (see the template's
     inline guidance and `reference.md` for the full schema).
   - Run it: `python3 data/<group>/<id>/_build.py` (writes `interview.json`).
   - **Delete the `_build.py`** afterward (builder helpers are temporary and
     never shipped; `_`-prefixed files aren't treated as datasets).
   You may instead hand-write `interview.json` directly — either way it must
   match the schema in [reference.md](reference.md).

4. **Register it.** Add `{ "id": "<id>", "name": "<Display Name>", "path":
   "data/<id>/interview.json" }` to the chosen category's `datasets[]` in
   `data/<group>/index.json`. (The `path` is relative to the group, so it
   omits the group prefix.)

5. **Build and verify (MANDATORY gate).**
   ```
   node data/book/_verify.mjs          # MUST print "OK — N book datasets pass all checks" (book group)
   python3 -c "import json; json.load(open('data/<group>/<id>/interview.json'))"   # valid JSON
   python3 build.py                     # regenerate docs/
   ```
   Fix anything `_verify.mjs` reports (usually a view node/link id that
   doesn't resolve to `highLevelArchitecture`, or a `highlight` not in
   `view.nodes`). For the `examples` group, validate JSON + `python3 build.py`
   (the verifier is book-specific).

6. **Report** the id/group/category, the step list (showing the naive step-1
   and which steps got flows/sub-steps), and confirm the verifier passed.
   Mention that Mermaid rendering can't be checked from the sandbox — the
   user should serve `docs/` and eyeball the diagrams.

## Hard requirements (the dataset will be rejected otherwise)

- `highLevelArchitecture` with `nodes[]`, `links[]`, `types[]` (types may be
  empty). Every node needs `id, type, category, traits[]`.
- Every step `view.nodes`/`view.links` are **id references** into
  `highLevelArchitecture` (not inline objects); `view.highlight` ⊆ `view.nodes`.
- Steps use `view`, never a raw `diagram` field. Flows use structured
  `sequence` objects, never raw Mermaid.
- `flow.highlight` ids must be participants in that flow.
- Node `type` must be one of: actor, client, edge, gateway, service,
  orchestrator, worker, queue, stream, cache, database, object-storage,
  index, model, observability, external.
- Do NOT escape Mermaid special chars in labels — the renderer entity-escapes
  them. Write labels as plain text (e.g. "Event Log (Kafka)").

## Conventions to honor

- Commit hygiene: stage only the new dataset files (`data/<group>/<id>/`,
  `docs/<group>/data/<id>/`, both `index.json`) — never `_templates/*` or
  unrelated in-progress files. End commit messages with the project's
  Co-Authored-By trailer.
- See [reference.md](reference.md) for the complete field-by-field schema,
  a worked node/link/step example, and the flow grammar.
