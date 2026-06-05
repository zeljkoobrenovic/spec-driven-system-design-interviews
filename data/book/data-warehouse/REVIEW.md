# Review: Data Warehouse / ETL Ingestion - System Design

Reviewed file: `data/book/data-warehouse/interview.json`
Review date: 2026-06-04

## Executive Summary

This review reflects the current dataset after the recent improvement pass. The
previous highest-impact findings have largely been addressed: the baseline now
uses an operational database instead of the warehouse, the capacity model is
quantitative, CDC/watermark semantics are explicit, atomic publish/read
isolation are taught, the API and data model are much richer, and
`technologyChoices` has been added.

The interview is now a strong book-quality data-platform case. The remaining
work is less about the core architecture and more about making the production
contract visible everywhere it matters: operator APIs, raw-data governance,
serving/cost operations, and the final orchestration/quality/lineage workflow.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | The architecture is coherent and now includes CDC, idempotency, atomic publish, schema evolution, backfills, and quality gates. |
| Production realism | 4/5 | Much stronger, but raw-lake governance, API state transitions, workload controls, and cost operations should be more explicit. |
| Pedagogical flow | 4.5/5 | The seven-step progression is natural and each step exposes the next problem. Step 7 is still dense. |
| Dataset/rendering fit | 4.5/5 | JSON is valid and structural references resolve; remaining issues are content polish and optional visual/icon assets. |
| Overall | 4.5/5 | Near-ready. Tightening the control-plane and governance details would move it from strong to excellent. |

## What Works Well

- The ELT spine is now very clear: transform-first ETL into an operational DB is
  the baseline, then the design moves raw landing, idempotent transforms,
  schema evolution, serving, backfills, and orchestration into place.
- The capacity section now gives useful interview numbers: source count, hot
  tables, 5 TB/day raw ingest, 2x to 4x storage multiplier, retention,
  query concurrency, and a concrete 90-day backfill example.
- Step `ingest` now teaches a real CDC contract: offsets/LSNs, primary keys,
  event time, ingest time, source version, operation type, tombstones,
  watermarks, and late/out-of-order handling.
- Step `transform` now explains the most important correctness mechanism:
  write temporary output, validate, atomically publish, then advance the output
  watermark while readers pin to committed snapshots.
- The data model now supports the promised control plane with `source`,
  `pipeline`, `pipeline_run / task_run`, `output_snapshot`, `schema_version`,
  `quality_check_result`, `lineage_edge`, and `backfill_job`.
- The option comparisons are realistic: ELT vs ETL, partition overwrite vs
  append/dedup vs MERGE, warehouse vs lakehouse vs OLAP cube.
- The technology choices section is useful and covers warehouse/lakehouse,
  table formats, transform frameworks, orchestrators, CDC/connectors, and event
  streams.

## Highest-Impact Issues

### 1. The API examples lag behind the new control-plane contract

The prose and data model now teach idempotency keys, output snapshots, quality
gates, atomic publish, cancel/retry, lineage, and controlled backfills. The
first API, `POST /v1/pipelines/{id}/run`, is still too simple:

- Request: `{ "partition": "2026-06-01", "mode": "incremental" }`
- Response: `{ "runId": "r_9", "state": "running" }`
- Sequence: load partition, write staging, transform partition, write modeled
  marts, mark run complete.

That sequence skips the new temporary output, quality validation, snapshot
commit, output watermark advancement, and failure branch. It also does not show
the idempotency key or transform/schema version that later sections rely on.

Concrete fix: update the run API to carry `idempotencyKey`, `partition` or
`range`, `mode`, `transformVersion`, optional `schemaVersion`, and maybe
`priority`. Update the sequence to match step `transform`: write temp snapshot,
run quality checks, commit/publish on pass, discard temp output on fail, then
advance the watermark. The richer `GET /v1/runs/{runId}` response is good; the
trigger API should expose the same contract.

### 2. Raw-lake governance is acknowledged but not designed

Step `ingest` correctly notes that sensitive fields land in the lake before
masking, so governance must cover raw data. The rest of the dataset does not
carry that concern forward. There is no requirement, architecture node, API, or
data-model entity for raw-data access control, classification, masking,
retention, audit, legal hold, or deletion workflows.

This matters because ELT intentionally keeps unmodified raw data. That is the
source of reprocessability, but it also means the raw lake is the most sensitive
part of the system.

Concrete fix: add a small governance thread without turning the case into a
compliance interview:

- Non-functional requirement: governed raw retention and auditable access.
- Data model: `data_classification`, `access_policy`, `retention_policy`,
  `audit_event`, and maybe `deletion_request` or `legal_hold`.
- Architecture: either a `Catalog` responsibility extension or a small
  governance/access-control node.
- Step text: raw is encrypted, access is least-privilege, sensitive columns are
  tagged, modeled outputs apply masking/tokenization, and raw retention/deletion
  policies are enforced.

### 3. Serving and cost operations need one more layer of mechanism

The capacity model, serving traps, and technology choices now mention small
files, compaction, query concurrency, rollups, and storage/compute trade-offs.
That is good, but the default serving path still mostly teaches partitioning
and columnar scans. It does not show how the platform keeps those tables healthy
over time.

Concrete fix: expand step `serve` or step `orchestrate` with operational knobs:

- Compaction and file-size targets for the lakehouse path.
- Table statistics, clustering/sorting, and partition-pruning health checks.
- Materialized view or rollup refresh ownership.
- Workload isolation for dashboards vs ad-hoc queries.
- Query queues, quotas, budgets, and kill/cancel controls.
- Cost telemetry tied to pipeline runs, backfills, and query workloads.

This would connect the new capacity numbers to operating decisions.

### 4. Orchestration, quality, and lineage are correct but visually compressed

Step `orchestrate` contains the right ideas: DAG dependencies, retries,
watermarks, quality gates, blocking vs advisory checks, owner alerts,
remediation, and lineage. The step has a focused architecture view, but no
sequence flow. Because the step closes the interview, it should show the final
production workflow as concretely as step `transform` shows atomic publish.

Concrete fix: add one sequence flow such as:

`Orchestrator -> Transform -> Quality -> Warehouse -> Catalog/Lineage -> Orchestrator`

Include the failure branch: blocking quality failure alerts the owner, leaves
the last good snapshot visible, records the failed check, and waits for retry or
remediation. Include the success branch: commit output snapshot, record lineage,
advance watermark, unblock dependents.

## System Design Soundness

The high-level architecture is sound for a modern analytical data platform. It
separates ingestion, raw storage, staging, transform compute, modeled serving,
schema control, orchestration, quality checks, and BI/query access. It also
does the right thing pedagogically: it motivates why raw retention matters
before asking candidates to reason about backfills.

The strongest improvement is the explicit publish boundary. The design now
distinguishes source offsets/LSNs from output watermarks and from freshness.
That avoids a common interview bug where "watermark" is used for too many
different meanings. It also correctly ties idempotency to an atomic publish
mechanism rather than just saying "overwrite the partition."

The main system-design gap is governance. A platform that stores raw CDC and
batch extracts for one to seven years needs a policy plane. That policy plane
does not have to dominate the interview, but without it the design overstates
how safe raw retention is.

The second gap is operational cost control. The capacity section gives enough
numbers to size storage, query concurrency, and backfill pressure, but the
architecture does not yet show the controls that keep those costs bounded.

## Step-by-Step Pedagogical Review

### Step 1: Naive baseline

This step is now coherent. The view uses a local `OperationalDB` node and the
caption/story match: a transform-first script writes to the operational DB that
analysts query directly. That cleanly motivates both ELT and a separate
analytical warehouse.

### Step 2: Ingest into a Raw Lake

This is now one of the strongest steps. The CDC contract is concrete enough for
a senior interview: offsets/LSNs, tombstones, late data, watermarks, and the
micro-batch vs streaming boundary all appear.

The remaining addition is raw governance. The option cons mention sensitive
fields before masking, but the chosen design should say how raw access,
classification, retention, and audit are controlled.

### Step 3: Idempotent Loads and ELT Transformation

This step now teaches the right correctness invariant: idempotent partition
processing plus temporary output plus validation plus atomic publish. The flow
is useful and directly answers the follow-up about half-written partitions.

The API section should be updated to match this step; otherwise a reader sees a
strong step flow and a weaker public run API.

### Step 4: Schema Evolution

The step has the right depth now. It distinguishes additive from breaking
changes, uses versioning and owner approval, and warns against pinning
transforms to "latest." The sequence flow makes the registry behavior concrete.

One possible polish item: connect schema changes to data contracts and consumer
communication. For example, show how downstream owners are notified or how
breaking changes are staged before modeled tables change.

### Step 5: Partitioning and Columnar Serving

The core serving story is correct and the options are useful. The step now
includes `Transform` in the view, so the earlier renderer mismatch is resolved.

To reach staff-level realism, add a little more on table health and workload
management: compaction, stats, clustering, materialized rollups, query queues,
separate dashboard/ad-hoc compute, and cost controls.

### Step 6: Reprocessing and Backfills

This step is strong. It ties together raw retention, idempotent partition
processing, atomic publish, admission control, dry-run estimates, approval,
cancellation, and fresh-data preemption.

Consider adding a failure drill for a bad backfill that publishes incorrect
history: expected behavior would be rollback to previous snapshots, pause
dependent jobs, notify owners, and re-run with a corrected transform version.

### Step 7: Orchestration, Quality, and Lineage

The content is correct but compressed. This step is carrying DAG scheduling,
dependency gating, retries, quality checks, alerting, remediation, and lineage.
The architecture view is enough to orient the reader, but a sequence flow would
make the final operational contract much easier to defend.

## Final Design Review

The final design now integrates the steps well. It includes CDC/connectors,
event stream, raw lake, loader, staging, transform engine, warehouse, schema
catalog, orchestrator, query layer, and quality checks. It also states the
publish boundary clearly: temporary/unpublished snapshot, quality validation,
atomic commit, output watermark advancement, and committed-snapshot reads.

The final design would be stronger if it named governance and cost controls as
first-class platform responsibilities. Those are the two remaining production
areas that are implied but not structurally represented.

## Concept Introduction and Learning Flow

The concept order is strong:

1. Baseline pain: raw data lost and operational DB overloaded.
2. ELT/raw lake: preserve source truth.
3. Idempotency/atomic publish: make retries safe.
4. Schema evolution: keep source changes from breaking downstream tables.
5. Partitioning/columnar: make analytical serving fast.
6. Backfills: use raw plus idempotency to fix history.
7. Orchestration/quality/lineage: operate the platform.

This is a good interview progression. The only learning-flow issue is that the
last step introduces many operational concepts at once. A flow diagram would
help those ideas feel like one system instead of a list of production concerns.

## Step-to-Final-Design Coherence

The earlier coherence issues are resolved:

- Step `naive` now uses `OperationalDB`, matching the story.
- Step `transform` no longer includes filtered-out context links in its focused
  view.
- Step `serve` now includes `Transform` when it mentions writes into the
  warehouse.
- `satisfies[*].steps[*]`, `technologyChoices[*].steps[*]`, pattern step links,
  and probe links resolve cleanly.

The remaining coherence polish is mostly textual. The `satisfies` entry for
"Idempotent loads" says "Partition-replace + watermarks"; it should include the
new atomic publish/snapshot mechanism because that is now the actual guarantee.

## Realism Compared With Production Systems

The dataset now covers many production realities that were previously thin:
CDC semantics, late data, tombstones, output watermarks, snapshot publish,
schema versions, quality gates, lineage, backfill admission control, and
technology trade-offs.

Remaining realism gaps:

- Raw-data governance: classification, access control, masking/tokenization,
  audit, retention, legal hold, and deletion policy.
- Operator state transitions: the API should show run states from submitted to
  loading, transforming, validating, publishing, succeeded/failed/cancelled.
- Serving operations: compaction, stats, clustering, query queue isolation,
  materialized-view refresh, and budget enforcement.
- Incident workflow: what happens when quality fails, a bad schema version is
  approved, or a backfill publishes bad history.
- Multi-team ownership: source owner, pipeline owner, data product owner, and
  alert owner are mentioned only lightly.

## Dataset and Renderer-Facing Observations

Validated successfully:

- `interview.json` parses as JSON.
- Top-level shape is complete for this case: requirements, capacity, API,
  data model, highLevelArchitecture, steps, finalDesign, satisfies,
  technologyChoices, interviewScript, levelVariants, followUps, and
  toProbeFurther.
- Step, option, and final-design `view.nodes` string IDs reference canonical
  high-level architecture nodes; local option nodes are used where appropriate.
- Step, option, and final-design `view.links` string IDs resolve to
  `highLevelArchitecture.links`.
- Step and API sequence participants resolve to the participants used by their
  messages.
- `satisfies[*].steps[*]`, `technologyChoices[*].steps[*]`, pattern step links,
  and `probeLinks` references resolve.

Issues or polish:

- The first run API sequence is a content mismatch with the newer
  atomic-publish flow, not a renderer problem.
- `technologyChoices` chips are valid bare strings, but icon assignment has not
  been run for this dataset. For book polish, run
  `_scripts/assign_tech_icons.py data/book/data-warehouse/interview.json` and
  rebuild the book docs if those generated assets are desired.
- There are no `aiVisual`, design-vs-requirements illustrations, or
  `explainerComic` assets. These are optional, but this case would benefit from
  generated visuals for atomic publish, backfill, and the final architecture.
- Requirements and capacity diagrams are raw Mermaid arrays. If they are edited
  later, they still need browser-side visual validation.

## Recommended Edits, Prioritized

### P1: Align the APIs with the corrected design

- Update `POST /v1/pipelines/{id}/run` to include idempotency key, transform or
  schema version, partition/range, and priority.
- Update that API sequence to include temp output, quality validation, snapshot
  commit, watermark advancement, and failure handling.
- Tighten the `satisfies` "Idempotent loads" summary to name atomic publish and
  committed snapshots.

### P1: Add raw-data governance

- Add a non-functional requirement for governed raw retention and auditable
  access.
- Add governance/policy entities to the data model.
- Carry masking/classification/access-control language from the ingest option
  cons into the chosen design path.

### P2: Make serving operations explicit

- Add compaction, table statistics, clustering/sorting, query queue isolation,
  materialized rollup refresh, and cost controls to step `serve` or
  `orchestrate`.
- Tie these controls back to the capacity numbers.

### P2: Add an orchestration/quality/lineage sequence

- Show success and failure branches for a quality-gated publish.
- Record lineage and unblock dependents only after publish succeeds.
- Show owner alert/remediation when a blocking quality check fails.

### P3: Add book polish

- Assign technology icons.
- Add generated AI visuals for the final design, atomic publish, and backfill.
- Add a failure drill for a bad backfill or bad schema-version approval.

## What Not To Change

- Keep the compact seven-step flow. It now has enough depth without becoming a
  catalog of every data-platform subsystem.
- Keep ELT plus immutable raw as the central teaching decision.
- Keep the option sets; they are realistic and useful in an interview.
- Keep the explicit distinction among source offsets, output watermarks, and
  freshness.
- Keep the final design as one integrated platform rather than splitting ingest,
  warehousing, and orchestration into separate cases.

## Bottom Line

The recent changes moved this dataset from a solid draft to a strong
book-quality interview. The core architecture is now defensible. The next best
edits are to make the operator-facing API match the atomic-publish contract, add
raw-data governance, and show the final orchestration/quality/lineage workflow
as a concrete sequence.
