# Review: Data Warehouse / ETL Ingestion - System Design

Reviewed file: `data/book/data-warehouse/interview.json`
Review date: 2026-06-04

## Executive Summary

This is a strong, compact data-platform walkthrough. The interview teaches the
right spine: start with a naive transform-first pipeline, introduce ELT and a
raw lake, make loads idempotent, handle schema evolution, serve from
partitioned columnar tables, and close with backfills plus orchestration,
quality, and lineage.

The broad design is credible. The highest-impact improvements are about making
the production contract precise enough for a senior/staff interview: capacity
math, CDC semantics, atomic publish/read isolation, richer run metadata, and
more concrete operational APIs.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Correct architecture and trade-offs, but capacity, publish semantics, and CDC details need more precision. |
| Production realism | 3/5 | Mentions watermarks, retries, quality, lineage, and backfills, but the API/data model do not yet enforce those guarantees. |
| Pedagogical flow | 4/5 | The step sequence builds naturally and each step exposes the next problem. |
| Dataset/rendering fit | 4/5 | JSON is valid and references mostly resolve; two focused step captions mention links that the renderer filters out. |
| Overall | 4/5 | Very usable as a book case after tightening the operational contract. |

## What Works Well

- The ELT motivation is clear. The baseline exposes why transform-first ETL and
  operational-DB analytics fail, then later steps remove those pains one by one.
- The options are real interview trade-offs: ELT vs ETL, partition overwrite vs
  append-dedup vs MERGE, and warehouse vs lakehouse vs cube.
- The final design includes the core components introduced in the walkthrough:
  CDC/connectors, event stream, raw lake, loader, staging, transform engine,
  warehouse, schema catalog, orchestrator, query layer, and quality checks.
- The follow-up questions are strong. Breaking schema changes, backfill
  starvation, kappa, half-written partitions, and data contracts are the right
  pressure points for this domain.
- The book-specific teaching fields are present: patterns, concepts,
  probeLinks, interviewScript, levelVariants, followUps, traps, bottlenecks, and
  failureDrills.

## Highest-Impact Issues

### 1. The baseline diagram contradicts the baseline story

Step `naive` is titled "One Script Transforms Then Loads Into the Operational
DB" and the prose says analysts query the operational database directly. The
view, however, uses the canonical `Warehouse` node whose label is "Warehouse
(Columnar)", and the caption says the transform writes into the columnar
warehouse.

That makes the baseline look like it already has the separate analytical store
that the rest of the walkthrough is supposed to motivate.

Concrete fix: add a local `OperationalDB` node to the `naive` view with local
links such as `Sources -> Transform -> OperationalDB -> Query`, or retitle the
baseline as a naive warehouse load. The first option is better because it keeps
the contrast with the later warehouse step.

### 2. Atomic publish and read isolation are not taught

Step `transform` says partition loads overwrite output, and step `serve` says
queries prune partitions, but the dataset does not explain how an overwrite
becomes visible atomically. The follow-up asks, "How do you guarantee a query
never reads a half-written partition?", which is important enough to teach in
the main design.

Concrete fix: add an explicit publish pattern:

- Write output to a temporary table/location or unpublished snapshot.
- Validate row counts, schema, freshness, and quality checks.
- Publish via atomic partition swap, warehouse transaction, or table-format
  snapshot commit.
- Advance the watermark only after the publish commit.
- Pin queries to committed snapshots or published partitions.

This would connect idempotent loads, quality gates, and query correctness into
one defensible mechanism.

### 3. Capacity is too qualitative for a flagship data-warehouse case

The capacity section says "TBs/day", "minutes to daily", and "raw kept long",
but it does not translate those into design choices. A candidate still needs to
reason about source count, source rate, row width, raw/staging/modeled storage
multiplier, retention, query concurrency, dashboard refreshes, backfill size,
and compute isolation.

Concrete fix: add a small quantitative model, for example:

- 500 source tables, 50 high-volume tables, 5 TB/day raw ingest.
- 2x to 4x storage multiplier across raw, staging, modeled tables, snapshots,
  and compaction overhead.
- 90 days hot queryable data; 1 to 7 years raw retention depending on policy.
- 200 analyst queries/minute peak, with 20 long-running dashboard queries.
- Backfill example: 90 days at 5 TB/day, throttled below fresh-data priority.

Then tie those numbers to partition size, object count/small-file pressure,
warehouse concurrency, transform cluster sizing, and backfill admission control.

### 4. The API and data model do not support the promised guarantees

The prose repeatedly promises idempotency, watermarks, DAG dependencies, schema
versions, quality gates, lineage, and controlled backfills. The data model has
only `raw_extract`, `warehouse_table`, and `run_metadata`; the API has run,
query, and backfill calls.

That is enough for a high-level overview, but not enough for the platform to
enforce the guarantees the interview asks candidates to defend.

Concrete fix: expand the model with:

- `source`: source type, owner, cadence, schema contract, credentials reference.
- `pipeline`: DAG definition, dependencies, freshness SLA, priority, enabled
  state.
- `pipeline_run` and `task_run`: idempotency key, attempt, state transitions,
  partition/range, input watermark, output snapshot/version.
- `schema_version`: fields, compatibility mode, migration/mapping rules.
- `quality_check_result`: check type, threshold, status, blocking/advisory mode.
- `lineage_edge`: source dataset, transform version, output dataset/snapshot.
- `backfill_job`: range, priority, concurrency cap, estimate, owner.

Add API examples for run status, cancel/retry, schema registration, quality
results, lineage lookup, and backfill controls. `/v1/backfill` should include
priority, concurrency cap, transform version, dry-run estimate, and an
idempotency key.

### 5. CDC and late-data semantics are under-specified

The design correctly includes CDC/connectors, streams, raw landing, and
watermarks. It does not yet explain offset tracking, deduplication, deletes,
tombstones, out-of-order events, late events, or the boundary between
micro-batch and streaming transforms.

Concrete fix: in step `ingest` or `transform`, add a short CDC contract:

- Persist source offsets/LSNs and connector checkpoints.
- Store event time, ingest time, source version, operation type, and primary key
  in raw records.
- Represent deletes/tombstones explicitly.
- Use watermarks for completeness, not just "what was processed".
- Define late-event handling: reopen affected partitions, MERGE keyed rows, or
  send corrections to a backfill path.

This also makes the kappa follow-up easier to answer.

## System Design Soundness

The high-level architecture is sound for a modern analytical platform. It
separates ingest, durable raw storage, staging, transform, serving, and
control-plane concerns. It avoids querying operational systems directly and
keeps raw data so historical outputs are reprocessable.

The default "idempotent partition overwrite" path is reasonable, but it needs
boundaries. It works best when tables are naturally partitioned, inputs are
partition-aligned, and the rewritten partition size is acceptable. It is weaker
for very late CDC events, slowly changing dimensions, primary-key updates,
deletes, or partitions that are too large to rewrite wholesale. The MERGE option
mentions some of this, but the chosen/default path should state when partition
overwrite is safe and when keyed MERGE, table-format transactions, or change
tables are required.

Schema evolution is directionally right. The next improvement is to separate
raw schema capture from modeled data-contract evolution. Additive source
changes, source renames, type changes, deletions, and downstream semantic
changes have different blast radii.

Serving is also directionally right. Partitioning plus columnar storage is the
right core mechanism, and the lakehouse/cube options are useful. Production
depth would come from adding clustering/sorting, table statistics, compaction,
small-file cleanup, materialized views, warehouse concurrency controls, and
cost controls.

## Step-by-Step Pedagogical Review

### Step 1: Naive baseline

The motivation is strong, but the view should not use the final columnar
warehouse node while the prose says operational DB. This is the largest
pedagogical mismatch because it weakens the contrast the rest of the interview
depends on.

### Step 2: Ingest into a Raw Lake

This is one of the strongest steps. It explains ELT, immutable raw retention,
source cadence differences, and the governance cost of landing sensitive raw
data. The recap currently says `before: "Nothing."`; it would be more coherent
as "transform-first script into operational DB" so the step visibly advances
from the baseline.

Add CDC operational details: offsets, source versions, delete records, late
events, and connector replay semantics.

### Step 3: Idempotent Loads and ELT Transformation

The option set is good. The flow introduces watermarks and idempotent partition
overwrite, which are important. The missing piece is publish safety: define the
temporary write, validation, atomic publish, and watermark-advance order.

Also clarify what the watermark means. It could be source offset, partition
completion, output snapshot version, or freshness timestamp; those are not
interchangeable.

### Step 4: Schema Evolution

The concept is central and well placed. It should go one layer deeper:
compatibility modes, owner approval, schema mapping for renames/retypes,
versioned transforms, and how downstream consumers migrate without silent
corruption.

This step would benefit from either a flow or data-model additions showing how
the loader checks raw schema and how the transform pins a schema version.

### Step 5: Partitioning and Columnar Serving

The warehouse, lakehouse, and cube options are good and interview-realistic. The
main view caption says the transformation engine writes marts into the
warehouse, but the renderer filters out `transform-warehouse` because
`Transform` is not listed in the focused `view.nodes`. Either add `Transform`
to the main `serve` view or remove that link/caption detail.

Add compaction/statistics and query concurrency controls as production polish.

### Step 6: Reprocessing and Backfills

Clear payoff from ELT plus idempotency. The step should add backfill admission
control: priority, concurrency limits, fresh-data preemption, dry-run
estimation, approval, cancellation, and blast-radius limits for large historical
rewrites.

### Step 7: Orchestration, Quality, and Lineage

This is the right closing step, but it compresses three large topics into prose.
The existing `bottlenecks` and `failureDrills` fields help. A sequence flow for
quality-gated publish would make the step much stronger:

`Orchestrator -> Transform -> temporary output -> Quality -> publish snapshot -> lineage/run metadata`.

Also introduce blocking vs advisory checks, alert ownership, remediation, and
lineage granularity.

## Final Design Review

The final design includes all major components introduced by the steps and is
coherent. It would be stronger if it named the publish boundary explicitly:
raw/staging writes, transform writes, quality validation, atomic publish, query
visibility, and lineage/run metadata commit.

The final design says ingestion, transform compute, and the warehouse scale
independently. That is plausible, but the capacity section should support it
with scaling knobs: connector parallelism, object-storage throughput, transform
cluster size, warehouse size/concurrency, query queue isolation, and backfill
queue limits.

## Concept Introduction and Learning Flow

The concepts are introduced in a good order: ELT, idempotency, schema evolution,
serving layout, backfill, then operations. The strongest learning thread is
"keep raw data so you can fix history"; it appears in requirements, step 2,
step 3, step 6, and the final design.

The biggest teaching opportunity is to make the control-plane concepts visible
earlier. Run metadata appears in step 3, schema versioning in step 4, and
orchestration in step 7, but the data model does not show how they connect.
Adding recurring entities like `pipeline_run`, `task_run`, `schema_version`,
`output_snapshot`, and `quality_check_result` would make the walkthrough feel
like one accumulating system instead of adjacent topic cards.

## Step-to-Final-Design Coherence

The final design aligns well with the steps. Each requirement maps to a named
mechanism in `satisfies`, and the referenced step IDs resolve cleanly.

The main coherence issues are visual or operational:

- Step `naive` uses `Warehouse` even though the prose says operational DB.
- Step `transform` includes the `landing-loader` link in the main view, but
  `Landing` is not in `view.nodes`; `graphViewToMermaid` filters that link out.
- Step `serve` includes the `transform-warehouse` link in the main view, but
  `Transform` is not in `view.nodes`; `graphViewToMermaid` filters that link
  out.
- The final design promises quality-gated trust and lineage, but the API/data
  model do not yet carry enough state to show how those guarantees are enforced.

## Realism Compared With Production Systems

Several production topics are present but underdeveloped:

- CDC needs offset tracking, dedupe, delete/tombstone handling, late and
  out-of-order event handling, replay behavior, and a clear micro-batch vs
  streaming stance.
- Raw lake governance needs access control, encryption, masking/tokenization,
  audit logs, retention policies, legal hold, and deletion workflows. Step
  `ingest` notes sensitive fields, but the design does not carry governance
  forward.
- Quality checks need blocking vs advisory modes, owners, alerting, retry or
  remediation workflow, and publish semantics.
- Backfills need resource isolation and approval controls so historical work
  does not starve freshness SLAs.
- Cost needs more explicit treatment: storage multiplier, warehouse compute,
  transform compute, compaction, query concurrency, and duplicate raw/modeled
  data.
- Multi-tenancy/ownership is absent. Even a single-company warehouse usually
  needs dataset owners, source owners, pipeline owners, and access boundaries.

## Dataset and Renderer-Facing Observations

Validated successfully:

- `interview.json` parses as JSON.
- Top-level shape is complete for this case: requirements, capacity, API, data
  model, highLevelArchitecture, steps, finalDesign, satisfies, interviewScript,
  levelVariants, followUps, and toProbeFurther.
- Step and option `view.nodes` string IDs reference canonical nodes, with local
  option nodes used for `TableFmt` and `Cube`.
- Step and option `view.links` string IDs resolve to
  `highLevelArchitecture.links`.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- `probeLinks` references resolve to `toProbeFurther.links`.
- API and step sequence participants resolve to the participants used by their
  messages.

Issues or polish:

- Step `naive` has a prose/diagram mismatch around operational DB vs columnar
  warehouse.
- Main views for `transform` and `serve` include context links whose missing
  endpoints cause the renderer to omit those links.
- There is no `technologyChoices` section. For a book data-warehouse case, a
  focused comparison of Snowflake, BigQuery, Redshift, Databricks, Iceberg,
  Trino/Presto, Airflow, dbt, Kafka, Flink, and managed CDC/connectors would be
  valuable.
- There are no `aiVisual`, design-vs-requirements illustrations, or
  `explainerComic` assets. These are optional, but this case would benefit from
  generated visuals for the final architecture, backfill flow, and atomic
  publish/quality-gate mechanism.

## Recommended Edits, Prioritized

### P1: Fix correctness and rendering mismatches

- Replace the `naive` view's `Warehouse` usage with an `OperationalDB` local
  node, or retitle the baseline.
- Add `Landing` to the `transform` main view or remove `landing-loader` from
  that focused view.
- Add `Transform` to the `serve` main view or remove `transform-warehouse` from
  that focused view.
- Add atomic publish/read-isolation mechanics to step `transform`, step `serve`,
  and `finalDesign`.

### P2: Strengthen the production contract

- Expand capacity from qualitative labels into concrete ingest, storage, query,
  retention, and backfill sizing.
- Expand the data model with source, pipeline, pipeline_run, task_run,
  schema_version, output_snapshot, quality_check_result, lineage_edge, and
  backfill_job.
- Add APIs for run status/cancel/retry, schema registration, quality results,
  lineage queries, and controlled backfill submission.
- Add CDC semantics: offsets, dedupe, deletes, late events, replay, and
  watermark meaning.

### P3: Improve book polish

- Add `technologyChoices` for warehouse/lakehouse, table format, orchestrator,
  transform framework, CDC/streaming, and query layer choices.
- Add a flow for schema evolution and another for quality-gated publish.
- Add traps to schema, serving, backfill, and orchestration steps.
- Add generated AI visuals when the image pipeline is available, especially for
  final design and design-vs-requirements cards.

## What Not To Change

- Keep the ELT-first shape. It is the central teaching decision and is well
  motivated.
- Keep the compact seven-step flow. The issue is missing operational precision,
  not too few components.
- Keep the option comparisons. They make the case useful in an interview.
- Keep the follow-up questions. They point directly at senior/staff-level depth.
- Keep the final design as an integrated platform rather than splitting it into
  unrelated ingestion, warehouse, and orchestration cases.

## Bottom Line

This is a strong data-warehouse interview draft. Fix the opening visual
contradiction, make partition publish/read isolation explicit, and expand the
capacity/API/data-model contract enough to defend the promised guarantees. Once
those are tightened, the dataset will read as both a good interview answer and
a realistic production platform design.
