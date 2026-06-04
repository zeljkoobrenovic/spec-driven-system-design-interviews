# Review: Data Warehouse / ETL Ingestion - System Design

Reviewed file: `data/book/data-warehouse/interview.json`
Review date: 2026-06-04

## Executive Summary

This is a strong, compact data-platform walkthrough. The case teaches the core
ELT story clearly: keep raw data, transform into modeled tables, handle schema
evolution, serve with partitioned columnar storage, and make backfills possible.
The highest-value improvements are not about the broad shape of the design.
They are about making the promised production guarantees explicit enough that a
candidate could defend them under follow-up pressure.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Correct overall architecture, but capacity, atomic publish, and CDC semantics need more precision. |
| Production realism | 3/5 | Mentions retries, watermarks, quality, and lineage, but APIs and data model do not yet support them concretely. |
| Pedagogical flow | 4/5 | The step sequence is coherent and teaches one problem at a time. |
| Dataset/rendering fit | 4/5 | JSON and cross-references are mostly clean; two step diagrams have endpoint omissions and the baseline view contradicts its prose. |
| Overall | 4/5 | Very usable as a book case after tightening the operational contract. |

## What Works Well

- The ELT motivation is clear. The baseline exposes why transform-first ETL and
  operational-DB analytics fail, then each later step removes one specific pain.
- The option sets are real trade-offs: ELT vs ETL, partition overwrite vs append
  dedup vs MERGE, warehouse vs lakehouse vs cube. These are useful interview
  comparison points rather than strawmen.
- The final design integrates the main components: CDC/connectors, event stream,
  raw lake, loader, staging, transform engine, warehouse, schema catalog,
  orchestrator, query layer, and quality checks.
- Follow-ups are strong. Questions about breaking schema changes, backfill
  starvation, kappa, half-written partitions, and data contracts are exactly the
  pressure points for this domain.

## Highest-Impact Issues

### 1. The baseline diagram contradicts the baseline story

Step `naive` is titled "One Script Transforms Then Loads Into the Operational DB"
and the prose says analysts query the operational database directly. The view,
however, uses the canonical `Warehouse` node, whose label is "Warehouse
(Columnar)", and the caption says the transform writes into the columnar
warehouse. That makes the baseline look like it already has the separate
analytical store the walkthrough is supposed to motivate.

Concrete fix: either add a local `OperationalDB` node to the `naive` view with
local links from `Sources -> Transform -> OperationalDB -> Query`, or retitle
the baseline so it is honestly a naive warehouse load. The first option is
better pedagogically because it preserves the contrast with the later warehouse
step.

### 2. Two step views include links whose endpoint nodes are omitted from the view

The main `transform` view lists `Loader`, `Staging`, `Transform`, and
`Warehouse`, but includes the `landing-loader` link, whose `Landing` endpoint is
not listed. The main `serve` view lists `Query` and `Warehouse`, but includes
the `transform-warehouse` link, whose `Transform` endpoint is not listed.

Depending on renderer behavior, this can create implicit Mermaid nodes or make
the diagram show more than the intended focused view. It also makes the diagram
caption less reliable.

Concrete fix: include `Landing` in the `transform` view nodes, include
`Transform` in the `serve` view nodes, or remove those context links from the
focused views.

### 3. Capacity is too qualitative for a flagship data-warehouse interview

The capacity section says "TBs/day", "minutes to daily", and "raw kept long",
but it does not translate those into sizing decisions. A candidate still needs
to reason about source count, event/change rate, row width, raw plus modeled
retention, partition count, query concurrency, dashboard refresh frequency,
backfill size, and compute isolation.

Concrete fix: add a small quantitative model such as:

- 500 source tables, 50 high-volume tables, 5 TB/day raw ingest.
- 2x to 4x storage multiplier for raw, staging, modeled tables, and snapshots.
- 90 days hot queryable data, 1 to 7 years raw retention depending on compliance.
- 200 analyst queries/minute peak, with 20 long-running dashboard queries.
- Backfill example: 90 days at 5 TB/day, throttled below fresh-data priority.

Then tie those numbers to partition size, object count/small-file pressure,
warehouse concurrency, transform cluster sizing, and backfill admission control.

### 4. APIs and data model do not support the operational guarantees in the prose

The walkthrough repeatedly promises idempotency, watermarks, DAG dependencies,
quality gates, schema versions, lineage, and backfills. The data model only has
`raw_extract`, `warehouse_table`, and `run_metadata`, and the API only exposes
run, query, and backfill calls. That is not enough surface area to explain how
the platform actually enforces those guarantees.

Concrete fix: expand the model with at least:

- `source`: source type, owner, cadence, schema contract, credentials reference.
- `pipeline`: DAG definition, dependencies, freshness SLA, priority, enabled
  state.
- `pipeline_run` and `task_run`: idempotency key, attempt, state transitions,
  partition/range, input watermark, output snapshot/version.
- `schema_version`: fields, compatibility mode, migration/mapping rules.
- `quality_check_result`: check type, threshold, status, blocking/non-blocking.
- `lineage_edge`: source dataset, transform version, output dataset/snapshot.
- `backfill_job`: range, priority, concurrency cap, dry-run estimate, owner.

Likewise, add API examples for run status, cancel/retry, registering or updating
a schema, submitting quality results, and querying lineage. The existing
`/v1/backfill` request should include priority, concurrency cap, transform
version, and idempotency key.

### 5. Atomic publish and read isolation are deferred to a follow-up, but not taught

The follow-up "How do you guarantee a query never reads a half-written
partition?" is important enough that the main design should introduce at least
one mechanism. Step `transform` says a partition is overwritten, and step
`serve` says queries prune partitions, but the dataset does not explain how an
overwrite becomes visible atomically to queries.

Concrete fix: add an explicit publish pattern:

- Write output to a temporary/staging location or table.
- Validate row counts, schema, and quality checks.
- Publish via atomic partition swap, table-format snapshot commit, or warehouse
  transaction.
- Move the run watermark only after the publish commit.
- Keep queries pinned to committed snapshots or published partitions.

This would connect idempotent loads, quality gates, and query correctness into a
single defensible production story.

## System Design Soundness

The high-level architecture is sound for a modern analytical platform. It has
separate ingest, storage, transform, serve, and control-plane concerns, and the
final design correctly avoids querying operational systems directly.

The main gap is precision. "Idempotent partition overwrite" is a good default,
but it needs boundaries: late CDC events, slowly changing dimensions, primary
key updates, delete propagation, and partitions that are too large to rewrite
wholesale. The MERGE option mentions some of this, but the default path should
name when partition overwrite is safe and when a table-format transaction,
change table, or keyed merge is required.

Schema evolution is directionally right, but the design should separate raw
schema capture from modeled contract evolution. Additive raw changes, source
renames, type changes, deletes, and downstream semantic changes have different
blast radii. A data contract or schema compatibility policy would make this
step stronger.

Serving is also directionally right. Partitioning plus columnar storage is the
right core mechanism, but the dataset should mention clustering/sorting,
statistics, compaction, small-file cleanup, materialized views, and warehouse
concurrency controls as follow-on techniques.

## Step-by-Step Pedagogical Review

### Step 1: Naive baseline

Strong motivation, but the diagram should use an operational DB node rather than
the final columnar warehouse. The current visual weakens the contrast the prose
is trying to teach.

### Step 2: Ingest into a raw lake

This is the strongest step. It explains ELT, raw retention, source cadence
differences, and governance cost. The recap says `before: "Nothing."`; it
should reference the baseline script from step 1.

### Step 3: Idempotent loads and ELT transformation

Good trade-off set. The missing piece is atomic publish and exactly what the
watermark records. Add the output snapshot/partition version and clarify that
the watermark advances only after successful publish.

### Step 4: Schema evolution

Conceptually strong, but too short for how central this is to data warehouses.
Add compatibility modes, migration mappings, source ownership, and how breaking
changes are rolled out without silently corrupting downstream models.

### Step 5: Partitioning and columnar serving

The options are good. The main view should include `Transform` if it shows the
`transform-warehouse` link. The step could also teach compaction/statistics and
query concurrency, since those are common production bottlenecks.

### Step 6: Reprocessing and backfills

Clear payoff from ELT plus idempotency. Add backfill admission control:
priority, concurrency limits, fresh-data preemption, dry-run estimation, and
blast-radius controls for large historical rewrites.

### Step 7: Orchestration, quality, and lineage

The right closing step, but it compresses three big topics into prose. It would
benefit from either a sequence flow or concrete model/API fields showing how a
DAG task waits on freshness, how quality gates block publication, and how
lineage is recorded.

## Final Design Review

The final design includes all major components introduced by the steps and is
coherent. It would be stronger if it named the publish boundary explicitly:
raw/staging writes, transform writes, quality validation, atomic publish, and
query visibility. Without that, "idempotent" and "correct/auditable" remain
claims rather than mechanisms.

The final design also says ingestion, transform compute, and warehouse scale
independently. That is plausible, but the capacity section should support it
with concrete scaling knobs: connector parallelism, object-storage throughput,
transform cluster size, warehouse size/concurrency, and backfill queue limits.

## Concept Introduction and Learning Flow

The concepts are introduced in a good order: ELT, idempotency, schema evolution,
serving layout, backfill, then operations. The biggest teaching opportunity is
to make the control-plane concepts visible earlier. Run metadata appears in
step 3, schema versioning in step 4, and orchestration in step 7, but the data
model does not show how they connect.

Add a small recurring thread: every step writes or checks `pipeline_run`,
`schema_version`, `output_snapshot`, and `quality_check_result`. That would make
the walkthrough feel more like one accumulating system instead of separate
topic cards.

## Step-to-Final-Design Coherence

The final design is well aligned with the steps. Each requirement maps to a
named mechanism in `satisfies`, and those step IDs resolve cleanly.

The main coherence issues are visual:

- Step `naive` uses the final warehouse node even though the prose says
  operational DB.
- Step `transform` references the raw lake via a link but does not list `Landing`
  as a visible node.
- Step `serve` references `Transform` via a link but does not list `Transform`
  as a visible node.

Fixing those will make the decision-tree and step diagrams better match the
narrative.

## Realism Compared With Production Systems

Several production topics are present but underdeveloped:

- CDC needs offset tracking, deduplication, delete/tombstone handling, late and
  out-of-order event handling, and a clear stance on micro-batch vs streaming.
- Raw lake governance needs access control, encryption, masking/tokenization,
  retention, audit logs, and deletion/legal-hold behavior. Step `ingest` notes
  sensitive fields, but the design does not carry that forward.
- Quality checks should have blocking vs advisory modes, ownership, alerting,
  retry/remediation workflows, and promotion semantics.
- Backfills need resource isolation and approval controls so historical work
  does not starve freshness SLAs.
- Cost trade-offs need more explicit treatment: storage multiplier, warehouse
  compute, transform compute, compaction, and query concurrency.

## Dataset and Renderer-Facing Observations

Validated successfully:

- `interview.json` parses as JSON.
- Step view node IDs reference existing high-level nodes or local option nodes.
- Step view link IDs resolve to `highLevelArchitecture.links`.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Step `probeLinks` references resolve to `toProbeFurther.links`.
- API and flow sequence participants map to canonical architecture nodes.

Issues to address:

- Step `naive` has a prose/diagram mismatch around operational DB vs columnar
  warehouse.
- Main step views for `transform` and `serve` have links whose endpoints are not
  included in the same view node list.
- There is no `technologyChoices` section. For a book data-warehouse case, a
  focused comparison of Snowflake, BigQuery, Redshift, Databricks, Iceberg,
  Trino/Presto, Airflow, dbt, Kafka, and Flink would be valuable.
- There are no AI visuals or design-vs-requirements illustrations. These are
  optional, but this dataset would benefit from at least generated visuals for
  the final architecture and the backfill flow.

## Recommended Edits, Prioritized

### P1: Fix correctness and rendering mismatches

- Replace the `naive` view's `Warehouse` usage with an operational DB node and
  local links, or retitle the baseline.
- Add missing endpoint nodes to the `transform` and `serve` main views, or
  remove the context links from those views.
- Add atomic publish/read-isolation mechanics to step `transform`, step `serve`,
  and `finalDesign`.

### P2: Strengthen the production contract

- Expand capacity from qualitative labels into explicit ingest, storage, query,
  retention, and backfill sizing.
- Expand the data model with pipeline, run/task run, schema version, quality
  result, lineage edge, output snapshot, and backfill job entities.
- Add APIs for run status/cancel/retry, backfill controls, schema registration,
  quality results, and lineage queries.
- Add CDC semantics: offset tracking, dedupe, deletes, late events, and
  watermarking.

### P3: Improve book polish

- Add a `technologyChoices` section for warehouse, lakehouse/table format,
  orchestrator, transform framework, stream/CDC, and query layer choices.
- Add a sequence flow for schema evolution and another for quality-gated publish.
- Add traps to the later steps, especially schema evolution, serving, backfill,
  and orchestration.
- Add generated AI visuals for the final architecture and design-vs-requirements
  cards when the image pipeline is available.

## What Not To Change

- Keep the ELT-first shape. It is the central teaching decision and is well
  motivated.
- Keep the option comparisons. They make the case useful in an interview.
- Keep the final design compact. The issue is missing operational precision, not
  the absence of more components.
- Keep the follow-up questions. They point directly at senior/staff-level depth.

## Bottom Line

This is a strong draft of a data-warehouse interview. Fix the opening visual
contradiction, make partition publish and run metadata explicit, and add enough
capacity/API/data-model detail to defend the promised guarantees. After that,
the dataset will read as both a good interview answer and a realistic production
platform design.
