# Review: Data Warehouse / ETL Ingestion - System Design

Reviewed file: `data/book/data-warehouse/interview.json`
Review date: 2026-06-09

## Executive Summary

This dataset is now a near-ready book-quality walkthrough for a modern
analytical data platform. The recent operator-contract pass addressed the
previous review's main gaps: run states are explicit, query/cost operations have
an async query-job API and data-model entry, deletion requests are modeled, and
the orchestration step now has patterns, concepts, traps, and a quality-gated
sequence flow.

The interview now teaches a coherent platform: heterogeneous CDC/batch/stream
ingestion, immutable governed raw landing, idempotent ELT, atomic snapshot
publish, schema evolution, partitioned columnar serving, query workload
isolation, controlled backfills, quality gates, lineage, and governance.

The remaining work is polish. The core architecture is sound; the places to
tighten are the top-level interview aids, derived capacity math, and a few
advanced operational edge cases.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.8/5 | Strong architecture with credible reliability, replay, governance, and serving contracts. |
| Production realism | 4.8/5 | Now covers run lifecycle, query jobs, deletion, quality gates, lineage, and cost controls. |
| Pedagogical flow | 4.7/5 | The seven-step progression is clear; wrap-up teaching aids should catch up with the richer content. |
| Dataset/rendering fit | 4.8/5 | JSON, graph references, sequence references, step links, and asset paths validate cleanly. |
| Overall | 4.8/5 | Ready for use after a focused polish pass. |

## What Works Well

- The seven-step spine is strong: naive ETL, raw ELT landing, idempotent
  transforms, schema evolution, serving, backfills, then orchestration/quality
  and lineage.
- Step `ingest` now treats governance as part of the data path rather than a
  compliance footnote. It covers classification, encryption, least-privilege
  access, audit, retention, legal hold, erasure, and backfill-safe deletion.
- Step `transform` teaches the critical correctness boundary: write a temporary
  snapshot, validate, atomically publish, then advance the output watermark.
  Failed or cancelled runs leave the last committed snapshot visible.
- The API and data model now line up with the operator story: richer run states,
  cancel/retry semantics, output snapshot lifecycle, async query jobs, query
  cancellation, and cost attribution.
- Step `serve` does more than "partition by date"; it explains compaction,
  snapshot expiry, statistics, clustering, rollups, workload queues, budgets,
  kill/cancel controls, and governance-aware query admission.
- Step `orchestrate` is now a real production step. It covers dependency
  freshness, blocking vs advisory gates, lineage recording, publish success,
  blocking failure, and owner remediation.
- Top-level patterns have caught up with the design: atomic snapshot publish,
  governed raw lake, workload isolation, quality-gated orchestration, and
  run/snapshot lineage are all represented.
- Generated assets are wired: requirements/capacity visuals, per-step visuals,
  final-design visual, design-vs-requirements visuals, comic, and technology
  icons.

## Highest-Impact Issues

### 1. The interview script and level variants now lag behind the richer design

The core walkthrough is strong, but `interviewScript`, `levelVariants`, and some
`followUps` still describe the earlier, simpler version of the interview. They
mention ELT, idempotency, schema evolution, backfills, and orchestration, but
they do not surface the new differentiators strongly enough:

- atomic publish and committed-snapshot visibility;
- run-state lifecycle and retry/cancel boundaries;
- governed raw retention and deletion propagation;
- async query jobs, workload isolation, budgets, and cost attribution;
- blocking vs advisory quality gates and run/snapshot lineage.

This matters because those fields are book-facing learning aids. A reader using
the interview script should be prompted to say the same senior-level details the
step content now teaches.

Concrete fix:

- Update the "High-level design" script to name governed raw lake and atomic
  publish.
- Update the "Deep dive" script to include run lifecycle, query-job controls,
  deletion propagation, and quality-gated publish.
- Raise Staff expectations to include governance, query cost controls, and
  run/snapshot lineage.
- Add follow-ups for "How do you cancel safely during publishing?", "How does
  deletion avoid resurrection during backfill?", and "How do query queues and
  budgets work?"

### 2. Capacity is concrete but still mostly descriptive, not derived

The capacity section gives useful anchors: about 500 tables, about 50 hot
tables, about 5 TB/day raw ingest, 2-4x stored volume, 90-day hot modeled
retention, 1-7 year raw retention, about 200 queries/min peak, about 20
long-running dashboards, and a 90-day backfill example.

What is missing is the next layer of math that shows how those numbers drive
the architecture:

- ingest throughput per hot table and per connector;
- approximate raw object/file counts and compaction pressure;
- transform concurrency needed to keep freshness SLAs;
- query queue sizing for dashboards vs ad-hoc workloads;
- backfill concurrency caps relative to fresh-data priority;
- metadata volume for run records, snapshots, quality results, and lineage.

Concrete fix:

- Add one capacity bullet or note that converts 5 TB/day into GB/hour and
  per-hot-table throughput.
- Add a compaction note: target file size and why small-file counts matter.
- Add query queue math: 200 queries/min plus 20 long dashboards implies isolated
  queues/warehouses and bounded concurrency.
- Add a backfill envelope: "90d x 5 TB/day = 450 TB raw scanned; cap at N
  partitions or M TB/hour below fresh-data priority."

### 3. The advanced control-plane APIs are present, but the teaching visuals
could show them more directly

The query-job API and data model are now present, which resolves the earlier
contract gap. The main `serve` flow, however, still shows only `Query ->
Warehouse` partition pruning. That is useful for the storage-layout concept,
but it does not visualize the newer control-plane idea: authorize, estimate,
admit to queue, run, attribute cost, and cancel if needed.

Similarly, the lineage API response is still compact compared with the prose.
The text says lineage is run/snapshot granular, but the API example could return
`runId`, `outputSnapshot`, `sourceOffsets`, and `inputSnapshots` so the contract
matches the claim.

Concrete fix:

- Add a second `serve` flow for "Governed async query job" with `Query`,
  `Governance`, and `Warehouse`.
- Expand `GET /v1/lineage?dataset=...` response to include run/snapshot-level
  fields, not just upstream/downstream and transform version.
- Consider adding `affectedSnapshots` or `rewriteJobId` to deletion-request
  responses so erasure propagation is visible as an operator workflow.

### 4. A few traps and drills could reinforce the hardest invariants

The traps are much better than before, especially for governance, serving, and
orchestration. Two high-value invariants still deserve explicit teaching aids:

- Step `transform` has no trap even though "advance watermark only after atomic
  publish" is one of the hardest correctness rules in the whole design.
- Step `backfill` has good traps for priority and approval, but the failure
  drill still focuses on a mid-partition job failure. The more interesting
  production failure is a bad backfill that successfully publishes incorrect
  history.

Concrete fix:

- Add a transform trap: "Advancing the watermark before publish commits."
- Add a backfill failure drill: "A 90-day backfill publishes wrong metrics."
  Expected behavior should include pausing dependents, rolling back to previous
  snapshots, notifying owners, and rerunning with a corrected transform version.

## System Design Soundness

The design is sound for a senior/staff data warehouse and ELT platform
interview. It separates the system into the right boundaries:

- `Sources`, `CDC`, and `EventBus` capture heterogeneous input.
- `Landing` is immutable raw storage and replay source of truth.
- `Governance` classifies, masks, audits, enforces access, and applies
  retention/deletion/legal-hold policy.
- `Loader` and `Staging` isolate raw loading from modeling.
- `Transform` writes modeled outputs into `Warehouse`.
- `Catalog` owns schema versions and lineage metadata.
- `Quality` validates staging and warehouse outputs.
- `Orchestrator` owns dependency freshness, retries, state, and backfills.
- `Query` serves analysts through governed query contracts over committed
  warehouse snapshots.

The best system-design quality is the precise distinction among source offsets,
output watermarks, freshness, and committed snapshots. That prevents the common
interview mistake of using "watermark" as a vague correctness term.

The run lifecycle is now credible:

- `queued -> loading -> transforming -> validating -> publishing -> succeeded`
  with `failed`, `cancelled`, and `blocked` branches.
- `output_snapshot.state` distinguishes `pending`, `committed`, `superseded`,
  and `aborted`.
- Cancel is only effective before publish commits.
- Readers pin to committed snapshots and never see temporary output.

The query-serving contract is also now credible. `POST /v1/query-jobs`,
`GET /v1/query-jobs/{id}`, and cancel expose queue, principal, estimated bytes,
access/masking decision, bytes scanned, compute seconds, and cost attribution.

## Step-by-Step Pedagogical Review

### Step 1: Naive Baseline

This remains a good start. It shows a plausible small-company script and
exposes exactly why the rest of the design exists: raw data is discarded and
analytics contend with operational traffic.

No major changes needed. The single trap is sufficient.

### Step 2: Ingest into a Raw Lake

This is one of the strongest steps. It teaches ELT, immutable raw retention, CDC
metadata, tombstones, late/out-of-order events, micro-batch vs streaming, and
governance at landing time.

The recent deletion-propagation content is especially important: deleting only
modeled rows is not enough because retained raw can resurrect erased subjects
during a backfill. That is a strong production detail.

### Step 3: Idempotent Loads and ELT Transformation

This step now teaches the core reliability invariant very well. The prose,
sequence, API, data model, and final design agree on temp snapshots, validation,
atomic publish, committed-snapshot reads, output watermark advancement, and
cancel/failure behavior.

Recommended polish: add one trap for advancing the watermark before publish or
allowing queries to read the temporary snapshot.

### Step 4: Schema Evolution

The schema step is clear and well scoped. It distinguishes additive from
breaking changes, requires explicit mapping/approval for renames and retypes,
and warns against pinning transforms to "latest" schema.

Optional improvement: connect schema evolution to governance classification. A
new source column can also be a new PII/secret classification event.

### Step 5: Partitioning and Columnar Serving

This is now much stronger than a basic partitioning explanation. It connects
layout to operations: compaction, snapshot expiry, stats, clustering, rollups,
queues, budgets, cancellation, and cost telemetry.

The API/data model now backs that story. The only teaching gap is visual: the
step flow still illustrates pruning, not governed async query admission.

### Step 6: Reprocessing and Backfills

This step is strong. It ties raw retention, idempotent partitions, atomic
publish, lower-priority queues, dry-run estimates, owner approval, cancellation,
and fresh-data preemption together.

Recommended polish: add a bad-backfill failure drill. A successful publish of
wrong historical data is a more realistic senior-level incident than a simple
mid-job failure.

### Step 7: Orchestration, Quality, and Lineage

This step is now correct and production-oriented. It shows dependency
freshness, quality validation before publish, blocking/advisory distinction,
snapshot commit, lineage recording, watermark advancement, and failure behavior.

The added patterns, concepts, and traps are exactly the right teaching metadata.
No major changes needed.

## Final Design Review

The final design integrates the steps cleanly. It includes every high-level
architecture node and all important links:

- source capture and event stream to raw lake;
- governance over raw, warehouse, and query access;
- raw lake to loader to staging;
- staging to transform to warehouse;
- schema validation through catalog;
- orchestration over load and transform;
- quality checks over staging and warehouse;
- query serving over warehouse.

The final-design prose includes the right operational details: checkpointed
offsets/LSNs, raw record metadata, idempotent staging loads, schema evolution,
temporary snapshots, quality validation, atomic publish, committed-snapshot
reads, table health, workload isolation, backfill admission control, lineage,
and governance.

No new architecture boxes are needed. The next improvements should sharpen
teaching aids and examples, not expand the diagram.

## Concept Introduction and Learning Flow

The learning flow is strong:

1. Start with a simple transform-first baseline.
2. Preserve raw source truth with ELT.
3. Make transformations idempotent and publish atomically.
4. Handle schema evolution deliberately.
5. Serve queries efficiently and operate table health.
6. Use raw plus idempotency for controlled backfills.
7. Coordinate the platform with orchestration, quality, lineage, and
   governance.

The best teaching quality is that each step creates the reason for the next
step. The reader does not get a list of disconnected data-platform tools; they
see why each subsystem exists.

The step-level concepts are now mostly aligned with the prose. The remaining
gap is outside the steps: the interview script and level variants should prompt
the richer senior/staff answer.

## Step-to-Final-Design Coherence

The step-to-final-design coherence is strong. Every major final-design
component is introduced before the wrap-up:

- `Landing`, `CDC`, `EventBus`, and `Governance` come from step `ingest`.
- `Loader`, `Staging`, `Transform`, and `Warehouse` come from step `transform`.
- `Catalog` comes from step `schema`.
- `Query` and workload controls come from step `serve`.
- `Orchestrator` and replay/backfill behavior come from step `backfill`.
- `Quality` and run/snapshot lineage come from step `orchestrate`.

The design-vs-requirements section is aligned and has generated illustrations
for each requirement. The "Idempotent loads" answer is especially good because
it names temporary snapshots, validation, atomic publish, output watermark
advancement, and committed reads.

## Realism Compared With Production Systems

This is realistic enough for a senior/staff interview. It covers the details
that usually separate a credible answer from a generic one:

- CDC replay metadata and tombstones.
- Late and out-of-order events.
- Immutable raw storage.
- Raw-lake governance and erasure propagation.
- Idempotent partitioned processing.
- Atomic publish and snapshot isolation.
- Schema versioning and breaking-change review.
- Table health operations.
- Async query jobs, workload isolation, and cost visibility.
- Backfill admission control and cancellation.
- Quality gates and remediation.
- Lineage at run/snapshot granularity.

The remaining realism gaps are edge-case elaborations: derived capacity
budgets, bad-backfill recovery, query-job visual flow, and more explicit
lineage/deletion response examples.

## Dataset and Renderer-Facing Observations

Validated successfully:

- `interview.json` parses as JSON.
- Top-level shape is complete for this case: requirements, capacity, API, data
  model, high-level architecture, steps, final design, satisfies, technology
  choices, interview script, level variants, follow-ups, probe links, AI
  visuals, and comic.
- The dataset has 11 requirements, 8 capacity bullets, 14 API entries, 16 data
  model entries, 7 steps, 11 patterns, 11 technology-choice groups, and 25
  probe links.
- Step `view.nodes` string references resolve to canonical high-level nodes;
  local option nodes are authored as objects where needed.
- Step `view.links` string references resolve to `highLevelArchitecture.links`.
- Option view node/link references resolve.
- Final-design view node/link references resolve.
- `satisfies[*].steps[*]`, `technologyChoices[*].steps[*]`, and
  `patterns[*].steps[*]` resolve to real step IDs.
- Step, final-design, and API sequence messages reference declared
  participants.
- 78 unique referenced asset paths were checked and all exist.

Renderer-facing polish:

- Several technology chips still use the generic `assets/tech-icons/tech.png`
  fallback, including MinIO, Debezium, Iceberg, Delta Lake, Hudi, dbt Core,
  Trino/Presto, Superset, Dagster, Great Expectations, DataHub, Ranger, and
  Microsoft Purview. This is acceptable but visible book polish remains.
- Requirements and capacity diagrams are intentionally simple raw Mermaid. If
  edited later, they still need browser-side visual validation.
- No rebuild is needed for this review-only change. If `interview.json` changes
  later, rebuild `docs/book/`.

## Recommended Edits, Prioritized

### P1: Refresh interview script, level variants, and follow-ups

Promote the new senior/staff material into the top-level teaching aids:
governed raw lake, atomic publish, run lifecycle, async query jobs, query cost
controls, deletion propagation, quality-gated publish, and run/snapshot
lineage.

### P2: Add derived capacity math

Convert the existing capacity anchors into operational sizing: GB/hour ingest,
per-hot-table connector throughput, target file size/compaction pressure,
query-queue concurrency, backfill TB/hour caps, and metadata volume.

### P2: Add a governed query-job flow and richer lineage response

Keep the pruning flow, but add a second `serve` flow for authorize -> estimate
-> admit -> run -> attribute/cancel. Expand the lineage API response with
run/snapshot/offset fields.

### P3: Add two failure-oriented teaching aids

Add a transform trap for advancing the watermark before commit, and a backfill
drill for rolling back a bad historical publish.

### P3: Improve remaining technology icon mappings

Map the visible `tech.png` fallbacks where good vendor/project icons are
available.

## What Not To Change

- Keep the seven-step structure; it is compact and coherent.
- Keep ELT plus immutable raw as the central design decision.
- Keep the distinction among source offsets, output watermarks, freshness, and
  committed snapshots.
- Keep governance in the main architecture and not as an appendix.
- Keep query controls as an operator-facing contract, not just prose.
- Keep the option sets; they teach real trade-offs without derailing the
  walkthrough.

## Bottom Line

The data-warehouse interview is now in excellent shape. The recent changes
closed the major production-contract gaps. The next pass should focus on
teaching polish: update the wrap-up aids, add derived capacity math, visualize
the query-job control plane, and add a couple of failure drills around the
hardest invariants.
