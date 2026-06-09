# Review: Metrics & Monitoring - System Design

Reviewed file: `data/book/metrics-monitoring/interview.json`
Review date: 2026-06-09

## Executive Summary

This dataset has been materially strengthened since the previous review. The
core gaps called out earlier are now mostly addressed: the capacity section
derives bandwidth/storage/index/shard estimates, ingestion has a partial
acceptance contract, percentiles are modeled with histograms/sketches, the data
model includes control-plane and alerting state, collection has service
discovery plus push-gateway behavior, and the final design now includes the
control plane and both TSDB shards feeding rollups.

The remaining work is not about making the design plausible; it is about making
the stronger design easier to defend in an interview. The main risks are
precision around "point" sizing and histogram expansion, a slightly muddy
collector/scraper model, alerting state being clearer in prose than in the
diagram, and wrap-up sections that lag behind the richer main content.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | Strong architecture with realistic contracts; tighten capacity definitions and alert/state diagrams. |
| Production realism | 4.4/5 | Good handling of cardinality, tenant limits, partial accepts, rollups, and alert HA; collection and replay semantics need a little more exactness. |
| Pedagogical flow | 4.6/5 | The eight-step progression is coherent and teaches one pressure at a time. |
| Dataset/rendering fit | 4.8/5 | JSON and renderer references check cleanly; icons resolve; no docs rebuild needed for review-only edits. |
| Overall | 4.5/5 | A strong book-grade metrics case with a few remaining precision and polish issues. |

## What Works Well

- The capacity section now connects 10M points/sec to peak write rate,
  compressed volume, hot-store size, index memory, shards, query envelope, and
  alert evaluation load.
- The ingest API is much more credible: tenant identity, `Idempotency-Key`,
  histogram payloads, partial acceptance, dropped reasons, and retry hints are
  all explicit.
- Percentile support is no longer hand-waved. Requirements, API, data model,
  storage deep dives, rollup notes, and traps all call out histogram/sketch
  preservation and the "do not average p95s" trap.
- The data model now carries the production contracts: `metric_descriptor`,
  `scrape_target`, `alert_instance`, `notification_attempt`, and `silence`
  records make the control plane and alerting state visible.
- The step sequence is strong: naive rows -> buffered ingest -> TSDB chunks ->
  rollups -> collection -> cardinality -> query/alerting -> sharding.
- The final design now matches the steps much better. It includes service
  discovery, push gateway, control plane, cardinality guard, router, replicated
  shards, rollup worker, query/cache, dashboards, alert rules, and notification
  provider.
- `technologyChoices` has been added and is useful for this domain: Prometheus,
  managed Prometheus, Kafka/Pulsar/Kinesis, object storage, Grafana/query
  frontends, and Alertmanager-style routing are the right comparison families.
- Renderer-facing checks are clean: nested view nodes/links resolve, final
  design references resolve, sequence participants resolve, step cross-links
  resolve, probe links resolve, canonical node types are valid, and icon paths
  exist.

## Highest-Impact Issues

### 1. Capacity math should define "point" more precisely

The sizing ladder is now useful, but the "Sample-on-wire size" entry mixes
in-chunk compression with ingestion bandwidth. A compressed scalar sample can be
tiny inside a TSDB chunk, but remote-write payloads also carry labels, metadata,
protobuf/framing overhead, WAL cost, and replication. Histogram metrics also
expand one logical observation into many bucket series.

Why it matters: a candidate may overstate how little bandwidth/storage the
system needs if they read "1-2 B compressed" as the end-to-end ingest unit.
Metrics platforms are often constrained by labels, active series, and
histogram bucket fan-out before raw scalar point bytes.

Concrete fix:

- Define whether "10M points/sec" means scalar samples, bucket samples, or
  logical measurements before bucket expansion.
- Split capacity into "wire/WAL bytes before TSDB compression" and
  "compressed chunk bytes after TSDB encoding."
- Add a short histogram example: one latency histogram with N buckets creates N
  bucket series plus count/sum, so percentiles increase active-series and
  ingest work.
- Mention label/index overhead explicitly in the ingest bandwidth estimate, not
  only in the active-series memory estimate.

### 2. The collector/scraper model is still a little ambiguous

Step 5 and the final design now include service discovery, target registry,
scrape health, and push gateway behavior, which is the right fix. The remaining
ambiguity is the role of `Agent`: it is called "Collector Agent", receives
targets from discovery, scrapes the app, forwards to ingest, and also appears
as an app-adjacent component. Its generated node description still says it is a
"synchronous application component that owns request-time business logic,"
which is not accurate for a collector.

Why it matters: push-vs-pull collection is a control-plane topic. Candidates
should be clear whether the system runs central scrapers, node agents,
sidecars, or library exporters, because that changes auth, liveness, rate
control, network reachability, and label ownership.

Concrete fix:

- Rename or describe the component as `Scraper` / `Collector` / `OpenTelemetry
  Collector` rather than generic `Agent`, or explicitly state it may be a
  node-local collector managed by the platform.
- Add a one-line distinction between instrumentation library, scrape target,
  collector/scraper, and push gateway.
- Update the high-level node description for `Agent` so generated tooltips do
  not call it request-time business logic.
- Consider showing `Discovery -> Collector -> App` and `Collector -> Ingest`
  as the main pull path, with `App -> PushGW -> Ingest` as the ephemeral-job
  branch.

### 3. Alerting is well described but underrepresented in the architecture view

Step 7 now includes the right alerting concepts: rule ownership, persisted
inactive/pending/firing/resolved state, silences, inhibition, dedup, delivery
retries, escalation, and missing-data behavior. The data model also includes
`alert_instance`, `notification_attempt`, and `silence`.

The diagram still compresses this into `Alert`, `Rules`, and `Notify`. That is
acceptable for a compact view, but the visual underplays the most important
production point: alerting is not just a query client; it owns durable state and
a notification delivery pipeline.

Concrete fix:

- Add either `Alert State Store` and `Notification Queue` nodes, or add a
  final-design caption sentence that explicitly maps those records to durable
  storage/queueing.
- In Step 7, show the persisted state and delivery queue in the flow
  participants if the diagram should teach the operational path.
- Keep the current query and alerting content in one step only if the UI stays
  compact; otherwise split into "Querying" and "Alerting" sub-steps.

### 4. Wrap-up sections lag behind the richer main content

The main walkthrough now mentions histograms, control plane, partial
acceptance, query admission, alert HA, and multi-tenant budgets in detail. Some
wrap-up fields are still shorter and older in tone. For example,
`satisfies.functional[0].how` says "Buffered, batched, fire-and-forget
ingestion" but does not mention partial acceptance, tenant auth, or histogram
input; the interview script and level variants also underplay the new control
contracts.

Why it matters: the wrap-up is what readers use to rehearse the answer. If it
summarizes the earlier, simpler version, readers may miss the higher-level
production lessons that now exist in the steps.

Concrete fix:

- Update `satisfies[*].how` to mention the newer mechanisms where relevant:
  histograms/sketches, partial acceptance, query admission, persisted alert
  state, and control-plane budgets.
- Expand the "Estimate & API" script phase with the point-vs-series distinction
  and histogram payload.
- Add staff-level expectations around acceptance boundaries, alert state, and
  collection control-plane ownership.

### 5. Technology choices are useful but many chips fall back to generic icons

The `technologyChoices` content is good and all icon paths resolve. Many
high-value options still use `assets/tech-icons/tech.png`, including Thanos,
Cortex/Mimir, M3DB, VictoriaMetrics, InfluxDB, Amazon Timestream, GCP Pub/Sub,
Azure Event Hubs, and several managed Grafana/cloud options.

Why it matters: this is polish, not correctness. But the book group uses tech
chips as visual anchors, and generic icons make the technology section look
less finished than the content deserves.

Concrete fix:

- Add mappings in `_media/index.yaml` for the most common observability and
  cloud-service terms, then re-run `_scripts/assign_tech_icons.py` for this
  dataset.
- Prioritize Mimir/Thanos/M3/VictoriaMetrics/InfluxDB and the managed cloud
  services that appear in multiple interviews.

## System Design Soundness

The design is now sound for a senior-level system design interview. It covers
the important data-plane path (samples -> buffer/WAL -> cardinality guard ->
series shards -> chunks/rollups -> queries/alerts) and the important
control-plane concerns (tenant identity, descriptors, budgets, scrape targets,
retention policies, query limits, routes, silences).

The strongest content is the treatment of cardinality and percentile-safe
rollups. Those are exactly the areas where generic "ingest lots of events"
answers usually fail. The dataset also correctly distinguishes dashboard
partial results from alerting fail-closed behavior on shard timeouts.

The remaining soundness work is precision. Define bytes and points in capacity,
make replay/idempotency semantics exact enough for counters and histograms, and
make the durable alerting state visible enough that a reader cannot mistake
alerting for a stateless polling loop.

## Step-by-Step Pedagogical Review

### Step 1: Naive Metrics Table (the baseline)

This baseline now lands well because it has the 0.86 trillion rows/day failure
example. It quickly motivates why row-per-sample OLTP storage is the wrong
shape without spending too long on a strawman.

### Step 2: Ingestion Pipeline

This step has improved substantially. It now explains the acceptance boundary,
partial acceptance, priority shedding, retries, and idempotency. The flow also
shows the `202 {accepted, rejected, droppedReasons}` response, which is a good
teaching detail.

The nuance to add is counter/histogram replay semantics. State whether a retry
dedupes by batch id, by series+timestamp, or by both, and what happens to
out-of-order histogram bucket samples.

### Step 3: Time-Series Storage

This is one of the strongest steps. It names compressed chunks,
delta-of-delta/XOR encoding, WAL/head chunks, compaction, label indexes,
out-of-order windows, and histogram/sketch storage. Keep the three option
families: purpose-built TSDB, wide-column/LSM, and relational extension.

Tighten the capacity connection by linking index memory and histogram bucket
series back to the Step 1/Step 2 estimates.

### Step 4: Downsampling & Retention

The rollup step now handles the earlier correctness gap. It preserves
min/max/sum/count for scalar metrics, sums histogram buckets for percentiles,
mentions sketches, and models late/backfilled data with versioned dirty
buckets.

This is production-realistic and should stay as-is except for maybe noting that
rollup recomputation must invalidate query cache entries.

### Step 5: Collection: Push vs Pull

The new control-plane deep dive is valuable: discovery labels, scrape health,
push gateway expiry, and push auth are exactly the right concepts.

The diagram and naming need a small cleanup. Make it unmistakable whether the
collector is a scraper service, a node agent, or a sidecar, and update the
`Agent` node description accordingly.

### Step 6: Cardinality Control

This remains the conceptual center of the case and it works. The step now goes
beyond "drop labels" into budgets, descriptors, owner reporting, emergency
overrides, and redirecting high-cardinality exploration to logs/traces or
exemplars.

No major content change is needed. A useful small addition would be an example
before/after relabeling rule for `path="/users/123"` -> `path="/users/:id"`.

### Step 7: Querying & Alerting

The content is strong and realistic. Query admission, cache, raw-vs-rollup
selection, rule scheduling, persisted alert state, silences, inhibition, dedup,
notification retries, escalation, and missing-data behavior are all covered.

The issue is density. This step carries two major subsystems. It is still
usable as one step, but the architecture view should make alert state/delivery
more visible, or the prose should explicitly say those are represented by the
data-model records rather than separate nodes.

### Step 8: Scaling by Sharding

This step now has the missing mechanics: shard ring, replica set, membership
registry, low write quorum vs async replication, consistent-hash rebalancing,
virtual nodes, hot-shard mitigation, partial dashboard results, and fail-closed
alerting.

The final design caption correctly explains that two shard nodes are
illustrative for about 16-32 replicated shards. Keep that clarification.

## Final Design Review

The final design is coherent and now reflects the current walkthrough. It shows
collection, push gateway, control plane, buffered ingest, cardinality guard,
metric router, two illustrative TSDB shards, rollups, cold storage,
query/cache/dashboard, alert rules, alerting engine, and notification provider.

The best part is the caption: it states that the diagram's two shards are only
illustrative and that the real ring has about 16-32 shards with RF=3. It also
states that both shards feed the rollup worker, fixing the earlier single-shard
rollup ambiguity.

The main improvement would be adding or naming durable alert state and
notification delivery state. The data model already has those records; the
diagram should either show them or explicitly map them in the caption.

## Concept Introduction and Learning Flow

Concept staging is strong. The reader meets time series and cardinality first,
then ingestion, then storage, then retention, then collection identity, then
cardinality enforcement, then query/alerting, then horizontal scale. That order
lets each step solve a visible problem from the previous one.

The only sequencing question is whether collection should come before storage.
The current placement is defensible: first teach the data-store shape, then
teach how samples arrive. If a reader is focused on tenant identity and labels,
Step 5 could be introduced earlier, but the current eight-step order is still
clear.

## Step-to-Final-Design Coherence

The step-to-final mapping is now strong:

- Step 2 contributes `Queue` and the partial-acceptance ingest path.
- Step 3 contributes `TSDB`/hot store concepts that become `ShardA`/`ShardB`.
- Step 4 contributes `Roll` and `Cold`.
- Step 5 contributes `Discovery`, `Agent`, and `PushGW`.
- Step 6 contributes `Cardinality` and the `Control -> Cardinality` policy
  link.
- Step 7 contributes `Query`, `Cache`, `Dash`, `Alert`, `Rules`, `Notify`, and
  control-plane query/route links.
- Step 8 contributes `Router`, replicated shard semantics, fan-out, and partial
  failure behavior.

The remaining mismatch is alerting state: Step 7 and the data model teach it,
but the final visual compresses it.

## Realism Compared With Production Systems

The dataset now captures the shape of production Prometheus/Mimir/Thanos/M3 or
managed-monitoring systems: remote-write buffering, compressed TSDB chunks,
label indexes, cardinality limits, service discovery, push gateway handling,
histograms, tiered retention, query frontends, alert routing, and sharded
storage.

Remaining realism caveats:

- Be explicit that histogram support multiplies series and must be budgeted.
- Make the collector/scraper deployment model concrete.
- Clarify replay/dedup behavior for retried batches and out-of-order samples.
- Show alert state/delivery durability more directly.
- Keep self-monitoring of the monitoring system as a follow-up or trap: ingest
  lag, dropped samples, queue depth, rule-eval lag, shard health, and query
  saturation.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level content is rich: requirements, capacity, API, data model, eight
  steps, final design, satisfies, technology choices, interview script, level
  variants, follow-ups, and probe links are present.
- Nested `view.nodes` references resolve to `highLevelArchitecture.nodes`.
- Nested string `view.links` references resolve to
  `highLevelArchitecture.links`.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.
- Sequence participants and message endpoints resolve.
- `satisfies[*].steps`, `patterns[*].steps`, and
  `technologyChoices[*].steps` resolve to existing step IDs.
- Step `probeLinks` resolve to top-level `toProbeFurther.links`.
- Canonical node types in use are valid: `cache`, `database`, `external`,
  `gateway`, `observability`, `queue`, `service`, and `worker`.
- Icon paths referenced from `assets` and `technologyChoices` exist.
- Optional AI visuals and `explainerComic` are absent. That is acceptable, but
  this case would benefit from generated visuals later.
- No generated `docs/` rebuild is needed for this `REVIEW.md`-only change.

## Recommended Edits, Prioritized

### P1: Tighten capacity terminology

Separate scalar sample, histogram bucket sample, logical measurement, wire/WAL
bytes, compressed chunk bytes, label/index overhead, and replication overhead.

### P1: Clarify collector/scraper semantics

Rename or define `Agent`, update its node description, and make the pull path
visually distinct from the push-gateway branch.

### P1: Make alert durability visible

Add alert state and notification delivery queue/store to the diagram or caption
so the visual matches the strong Step 7 prose and data model.

### P2: Refresh wrap-up fields

Bring `satisfies`, `interviewScript`, and `levelVariants` up to the same level
as the updated main walkthrough: histograms, partial acceptance, tenant budgets,
query admission, and persisted alert state.

### P2: Add replay/idempotency nuance

State how retried batches, duplicate samples, out-of-order samples, and
histogram buckets are identified and reconciled.

### P3: Improve technology icons

Add icon mappings for the observability and managed cloud technologies that
currently fall back to `tech.png`.

### P3: Add generated learning visuals

Optional but valuable: one visual each for cardinality explosion, histogram
rollups, and alert state/delivery.

## What Not To Change

- Keep the naive baseline and the 0.86 trillion rows/day failure anchor.
- Keep cardinality as the central recurring theme.
- Keep histogram/sketch support in requirements, API, storage, and rollups.
- Keep the hybrid pull/scrape plus push-gateway collection choice.
- Keep precomputed rollups as the default long-range query strategy.
- Keep series sharding with replicas as the scaling default.
- Keep `technologyChoices`; it adds useful book-level implementation context.

## Bottom Line

The recent changes moved this from a good conceptual draft to a strong
production-minded metrics interview. The next pass should be narrow: tighten the
capacity unit definitions, clarify collector deployment semantics, make alert
durability visible, and refresh the wrap-up summaries so they reflect the now
much richer design.
