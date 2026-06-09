# Review: Data Warehouse / ETL Ingestion - System Design

Reviewed file: `data/book/data-warehouse/interview.json`
Review date: 2026-06-09

## Executive Summary

This dataset is now a strong book-quality walkthrough. It teaches a coherent
modern analytical platform: heterogeneous ingestion, immutable raw landing,
idempotent ELT, schema evolution, partitioned columnar serving, controlled
backfills, quality-gated orchestration, lineage, and governance.

The previous review's biggest concerns have largely been addressed in the
current `interview.json`: governance is now first-class, the run API includes
idempotency/versioning, serving operations are explained, step 7 has a sequence
flow, technology icons and generated visuals are wired, and structural
references validate cleanly.

The remaining work is mostly about tightening the operator control plane and
teaching the newer production concerns as reusable patterns.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.7/5 | The architecture is credible and internally consistent; remaining gaps are lifecycle/state-model details. |
| Production realism | 4.5/5 | Strong on CDC, snapshots, governance, quality, and backfills; query/cost operations need a concrete contract. |
| Pedagogical flow | 4.6/5 | The seven-step progression is natural; newer concepts should be promoted into patterns/concepts/traps. |
| Dataset/rendering fit | 4.8/5 | JSON, graph references, step links, sequence participants, and asset references validate cleanly. |
| Overall | 4.6/5 | Near-ready. A focused control-plane polish pass would move it from strong to excellent. |

## What Works Well

- The interview has a clear spine: naive ETL into an operational DB, raw ELT
  landing, idempotent transforms, schema evolution, serving, backfills, then
  orchestration/quality/lineage.
- Step `ingest` now teaches the CDC contract well: offsets/LSNs, source
  version, primary key, op type, tombstones, event time, ingest time,
  completeness watermarks, late events, and replay.
- Raw-lake governance is now structurally represented through a non-functional
  requirement, architecture node, architecture links, data-model entities,
  governance APIs, technology choices, and final-design prose.
- Step `transform` correctly teaches the key reliability invariant: write a
  temporary/unpublished snapshot, validate, atomically publish, then advance the
  output watermark while readers pin to committed snapshots.
- Step `serve` now connects storage layout to operations: compaction, snapshot
  expiry, table stats, clustering/sorting, materialized rollups, query
  isolation, quotas, budgets, kill/cancel controls, and cost telemetry.
- Step `orchestrate` now has the missing quality-gated publish flow, including
  pass/fail branches and lineage recording after publish.
- The final design integrates all high-level nodes and links, including
  governance.
- Generated assets are now present: requirements/capacity visuals, per-step AI
  visuals, final-design visual, design-vs-requirements visuals, comic, and
  technology icons.

## Highest-Impact Issues

### 1. The run-state contract is close but not explicit enough

The API and data model use related but not identical state language. For
example, `POST /v1/pipelines/{id}/run` returns `state: "loading"`, retry returns
`state: "running"`, and the `pipeline_run / task_run` data model lists only
`running, succeeded, failed, cancelled`. The architecture prose needs more
states than that: queued/admitted, loading, transforming, validating,
publishing, succeeded, failed, cancelled, and possibly blocked.

This matters because the dataset is now teaching an operator-facing platform,
not just a data path. A candidate should be able to explain exactly when the
run is retryable, when a temp snapshot exists, when the output is visible, when
dependents can unblock, and what a cancel request can still cancel.

Concrete fix:

- Expand `pipeline_run / task_run.state` to match the API and sequence flow:
  `queued`, `loading`, `transforming`, `validating`, `publishing`, `succeeded`,
  `failed`, `cancelled`.
- Add `failure_reason`, `blocked_by`, `cancel_requested_at`, and
  `completed_at` fields, or mention them in the run-status API.
- Make `output_snapshot.state` distinguish `pending`, `committed`,
  `superseded`, and `aborted` so failed temp output has a clean lifecycle.
- Add one sentence to step `transform` or `orchestrate` that describes the
  visibility boundary: only `committed` snapshots are queryable; failed or
  cancelled runs abort temp snapshots and leave the last good snapshot visible.

### 2. Query and cost operations are in prose but not in the API/data model

Step `serve` rightly says the platform needs workload isolation, query queues,
quotas, budgets, kill/cancel controls, and cost telemetry. The exposed query
API is still:

`GET /v1/query` with `{ "sql": "SELECT ..." }` returning `{ "rows": [ ... ] }`.

That is fine for a minimal query example, but it does not support the operating
story the step now teaches. There is no query job ID, queue/warehouse selection,
bytes-scanned estimate, caller identity, access/masking decision, cost
attribution, or query cancellation endpoint.

Concrete fix:

- Replace or supplement `GET /v1/query` with an async query-job contract:
  `POST /v1/query-jobs`, `GET /v1/query-jobs/{id}`, and
  `POST /v1/query-jobs/{id}/cancel`.
- Include `workloadClass` or `queue`, `principal`, `estimatedBytes`,
  `budgetPolicy`, `state`, `bytesScanned`, `computeSeconds`, and
  `costAttribution`.
- Add a small `query_job` or `workload_policy` data-model entry.
- Tie the governance response to this query contract: the effective access
  decision should explain whether the result is raw denied, modeled allowed,
  or column-masked.

### 3. Governance deletion is credible but under-modeled

The dataset now has strong governance coverage, including classification,
access policy, retention/legal hold, audit events, and deletion-request APIs.
The remaining ambiguity is how deletion requests interact with raw retention,
modeled snapshots, and backfills.

The API says a deletion request can crypto-shred and record an audit event, but
the data model has no `deletion_request` entity. The walkthrough also does not
say whether erasure creates tombstones, rewrites affected modeled partitions,
marks snapshots as expired, or prevents future backfills from resurrecting
erased raw data.

Concrete fix:

- Add a small `deletion_request` entity with `request_id`, `subject_key`,
  `scope`, `state`, `blocked_by_legal_hold`, `created_by`, and `completed_at`.
- Mention the propagation rule: a deletion request either records a tombstone or
  crypto-shreds the subject key, schedules modeled-partition rewrites, and
  makes future backfills apply the same erasure policy.
- Add one governance trap: "Deleting only modeled rows while retained raw can
  re-create them during a backfill."

### 4. New production mechanisms are not fully promoted into pedagogy fields

The current top-level `patterns` list still has the original six patterns:
ELT, CDC/batch ingestion, idempotent partition loads, schema registry,
partitioning/columnar, and backfill. The dataset now teaches additional
book-worthy mechanisms that deserve the same treatment:

- Atomic snapshot publish.
- Governed raw lake.
- Quality-gated orchestration.
- Workload isolation and cost controls.
- Data lineage at run/snapshot granularity.

Step `orchestrate` also has no `concepts` and no `traps`, even though it now
carries several production concepts. That makes the wrap-up and concept review
less useful than the step content itself.

Concrete fix:

- Add top-level patterns for atomic publish, raw-lake governance,
  quality-gated orchestration, and workload isolation.
- Add `step.patterns` for `orchestrate`, likely "Quality-gated orchestration"
  and "Run/snapshot lineage".
- Add 1-2 `concepts` to step `orchestrate`, especially blocking vs advisory
  quality gates and lineage granularity.
- Add a trap for step `orchestrate`: treating lineage as table-level metadata
  only, instead of recording source offsets, transform version, and output
  snapshot per run.

## System Design Soundness

The design is sound for a modern data warehouse / ELT ingestion platform. The
major architectural boundaries are in place:

- `Sources`, `CDC`, and `EventBus` separate capture paths from storage.
- `Landing` is immutable raw storage and the replay source of truth.
- `Loader` and `Staging` isolate typed loading from modeled transformation.
- `Transform` writes modeled outputs into `Warehouse`.
- `Catalog` handles schema/version contracts and lineage metadata.
- `Orchestrator` owns dependencies, retries, state, and backfills.
- `Quality` gates outputs before publish.
- `Governance` covers raw and modeled access, masking, audit, retention,
  deletion, and legal hold.
- `Query` serves analysts over committed modeled snapshots.

The capacity model is useful and concrete: 500 source tables, 50 hot tables,
5 TB/day raw ingest, 2-4x stored volume, 90-day hot modeled retention,
1-7 year raw retention, about 200 queries/min peak, about 20 long dashboard
queries, and a 90-day backfill example.

The best part of the system design is the explicit separation of watermarks and
visibility:

- Source offsets/LSNs belong to ingestion replay.
- Output watermarks belong to published partitions/snapshots.
- Freshness is an SLA/lag measurement, not a checkpoint.

That distinction prevents a common interview failure where "watermark" is used
as a vague correctness word.

The main system-design polish is the operator state model. The components now
exist, but the API/data model should expose their lifecycle more explicitly.

## Step-by-Step Pedagogical Review

### Step 1: Naive Baseline

This is a good starting point. It avoids strawman complexity by showing a
plausible small-company script, then exposes exactly the two reasons the rest
of the design exists: raw data is discarded and analytical scans contend with
operational traffic.

The local `OperationalDB` node is appropriate and the trap is useful.

### Step 2: Ingest into a Raw Lake

This is one of the strongest steps. It teaches ELT, immutable raw retention,
CDC metadata, tombstones, late/out-of-order data, micro-batch vs streaming, and
governance at landing time.

The governance content is now appropriately early. That is important because
ELT makes raw retention central to correctness and central to risk.

Potential improvement: add a top-level pattern for "Governed raw lake" so this
important mechanism appears in the Patterns entry, not only inside the step.

### Step 3: Idempotent Loads and ELT Transformation

This step teaches the core correctness mechanism well. It no longer relies on
"overwrite the partition" as a hand-wave; it explains temp output, validation,
atomic publish, committed-snapshot reads, and output watermark advancement.

The sequence flow is strong. The run API mostly matches it now, but the data
model should align with the fuller run-state lifecycle.

### Step 4: Schema Evolution

The schema step is well scoped. It distinguishes additive from breaking
changes, teaches owner approval and mapping rules, and warns against pinning
transforms to "latest" schema. The data-contract sentence about notifying
downstream owners is a good production detail.

One optional addition: connect schema changes to governance classification. A
new column can be both a schema event and a classification event if it contains
PII or secrets.

### Step 5: Partitioning and Columnar Serving

This step is much stronger than a basic "partition by date" explanation. It now
covers compaction, snapshot expiry, stats, clustering, materialized rollups,
workload isolation, queues, quotas, budgets, kill/cancel controls, and cost
telemetry.

The main gap is contract visibility. Since the step teaches those controls, the
API/data model should show at least a small query-job or workload-policy shape.

### Step 6: Reprocessing and Backfills

This step is strong. It ties together raw retention, idempotent partitioned
processing, atomic publish, admission control, dry-run estimates, owner
approval, cancellation, and fresh-data preemption.

One useful addition would be a failure drill for a bad backfill that publishes
incorrect history. The expected answer should include rolling back to previous
snapshots, pausing dependents, notifying owners, and rerunning with a corrected
transform version.

### Step 7: Orchestration, Quality, and Lineage

The content and sequence are now correct. The step shows dependency checks,
temporary snapshot production, blocking/advisory quality checks, snapshot
commit, lineage recording, watermark advancement, and failure behavior.

The remaining weakness is pedagogical metadata. This step should introduce at
least one explicit concept and one trap because it carries several senior-level
production mechanisms. The step content is good; the wrap-up learning aids just
do not expose it enough.

## Final Design Review

The final design is coherent and integrates all steps. It includes every
high-level architecture node and all major links:

- source capture and event stream to raw lake;
- raw lake to loader to staging;
- staging to transform to warehouse;
- schema validation through catalog;
- orchestration over load/transform;
- query serving over warehouse;
- quality checks over staging and warehouse;
- governance over raw lake, warehouse, and query access.

The final-design prose also includes the right operational details:
checkpointed offsets/LSNs, raw record metadata, idempotent staging loads,
schema evolution, temporary snapshots, quality validation, atomic publish,
committed-snapshot reads, table health, workload isolation, backfill admission
control, lineage, and governance.

The final design would be excellent if the operator state machine and query
control plane were a little more explicit in the API/data model.

## Concept Introduction and Learning Flow

The learning flow is strong:

1. Start with a simple transform-first baseline.
2. Preserve raw source truth with ELT.
3. Make transformations idempotent and publish atomically.
4. Handle schema evolution deliberately.
5. Serve queries efficiently and operate table health.
6. Use raw plus idempotency for backfills.
7. Coordinate the whole platform with orchestration, quality, lineage, and
   governance.

The best teaching quality is that each step exposes the reason for the next
step. The reader does not get a shopping list of data-platform tools; they see
why each subsystem exists.

The concept metadata should now catch up with the prose. The step text has
grown into a stronger teaching artifact than the `patterns` and `concepts`
sections reflect.

## Step-to-Final-Design Coherence

The step-to-final-design coherence is good. Every major final-design component
is introduced before the wrap-up:

- `Landing` and `CDC` come from step `ingest`.
- `Loader`, `Staging`, `Transform`, and `Warehouse` come from step `transform`.
- `Catalog` comes from step `schema`.
- `Query` and serving operations come from step `serve`.
- `Orchestrator` and replay/backfill behavior come from step `backfill`.
- `Quality` and lineage come from step `orchestrate`.
- `Governance` is introduced in step `ingest` and carried through the final
  architecture.

The design-vs-requirements section is also aligned. In particular, the
"Idempotent loads" answer now names temp snapshots, validation, atomic publish,
output watermark advancement, and committed reads.

The remaining coherence issues are small and actionable:

- API run states should match the data model.
- Query serving controls should be represented somewhere beyond prose.
- Deletion requests should have a data-model counterpart and a backfill
  interaction rule.
- Newer concepts should be reflected in `patterns`, `step.patterns`, and
  `concepts`.

## Realism Compared With Production Systems

This is now realistic enough for a senior/staff data-platform interview. The
dataset covers the details that usually separate a credible answer from a
generic one:

- CDC replay metadata and tombstones.
- Late and out-of-order events.
- Immutable raw storage.
- Idempotent partitioned processing.
- Atomic publish and snapshot isolation.
- Schema versioning and breaking-change review.
- Table health operations.
- Workload isolation and cost visibility.
- Backfill admission control.
- Quality gates and remediation.
- Lineage at source/transform/output-snapshot level.
- Raw and modeled governance.

The biggest realism gaps are not missing components. They are missing
contracts:

- The run-state lifecycle should be formal enough for operators and retries.
- Query jobs should have enough metadata to support queues, budgets, cancel,
  audit, and cost attribution.
- Governance deletion should explain how raw retention and future backfills do
  not resurrect erased data.

## Dataset and Renderer-Facing Observations

Validated successfully:

- `interview.json` parses as JSON.
- Top-level shape is complete for this case: requirements, capacity, API,
  data model, high-level architecture, steps, final design, satisfies,
  technology choices, interview script, level variants, follow-ups, probe
  links, AI visuals, and comic.
- Step `view.nodes` string references resolve to canonical high-level nodes;
  local option nodes are authored as objects where needed.
- Step `view.links` string references resolve to `highLevelArchitecture.links`.
- Option view node/link references resolve.
- Final-design view node/link references resolve.
- `satisfies[*].steps[*]`, `technologyChoices[*].steps[*]`, and
  `patterns[*].steps[*]` resolve to real step IDs.
- Step and API sequence messages reference declared participants.
- Authored asset references resolve; 135 referenced icons/images were checked
  and none were missing.

Renderer-facing polish:

- Some technology chips still use `assets/tech-icons/tech.png` fallback icons
  because the icon mapping does not have specific matches for those products.
  This is acceptable but visible book polish remains.
- Requirements and capacity diagrams are intentionally simple raw Mermaid. If
  they are edited later, browser-side visual validation is still needed.
- No rebuild is needed for the review-only change. If `interview.json` changes
  later, rebuild `docs/book/`.

## Recommended Edits, Prioritized

### P1: Align run states across API, data model, and prose

Define a richer run lifecycle, add missing state fields, and make retry/cancel
semantics explicit around the temporary snapshot and publish boundary.

### P1: Add a query-job/control-plane contract

Promote serving operations from prose into API/data-model shape: async query
jobs, workload queues, cancel, bytes scanned, cost attribution, budget policy,
and governance access/masking decisions.

### P2: Add deletion-request lifecycle modeling

Add `deletion_request` and clarify how erasure affects raw data, modeled
snapshots, future backfills, audit, and legal hold.

### P2: Promote new mechanisms into patterns/concepts/traps

Add patterns and concepts for atomic snapshot publish, governed raw lake,
quality-gated orchestration, workload isolation, and run/snapshot lineage.

### P3: Tighten polish

Add specific icon mappings for the remaining `tech.png` fallbacks, add a bad
backfill failure drill, and consider a slightly richer capacity diagram that
shows query/backfill/governance pressure in addition to raw ingest volume.

## What Not To Change

- Keep the seven-step structure; it is compact and coherent.
- Keep ELT plus immutable raw as the central design decision.
- Keep the explicit distinction among source offsets, output watermarks, and
  freshness.
- Keep governance in the main architecture instead of relegating it to a
  compliance footnote.
- Keep the option sets; they teach real trade-offs without derailing the
  walkthrough.
- Keep final design as one integrated platform rather than splitting ingestion,
  warehousing, orchestration, and governance into separate interviews.

## Bottom Line

The data-warehouse interview is in strong shape. It is production-realistic,
teachable, and structurally valid. The next improvement pass should not add
more architecture boxes; it should make the existing operator contracts sharper:
run states, query/cost controls, deletion lifecycle, and reusable teaching
patterns for the production mechanisms already present.
