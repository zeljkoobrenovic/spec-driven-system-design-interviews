# Review: Metrics & Monitoring - System Design

Reviewed file: `data/book/metrics-monitoring/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong teaching skeleton for a metrics platform interview. It starts
from the right baseline, makes cardinality a first-class theme, introduces
chunked TSDB storage, downsampling, push-vs-pull collection, query caching,
alert debouncing, and series sharding in a coherent order.

The main gap is production precision. The current dataset teaches the broad
architecture well, but it does not yet define the operator contracts that make a
metrics system trustworthy at large scale: derived capacity math, ingestion
acknowledgement and overload semantics, tenant/source metadata, query limits,
alert rule state, notification delivery, histogram/percentile support, and shard
replication/rebalancing details.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 3.8/5 | The architecture is plausible, but capacity, percentiles, API contracts, and alert reliability need more rigor. |
| Production realism | 3.5/5 | Good concepts, but missing tenant/source controls, durable acceptance semantics, alert HA, and operational workflows. |
| Pedagogical flow | 4.2/5 | The eight-step progression is clear and teachable; collection/control-plane details should be introduced earlier. |
| Dataset/rendering fit | 4.7/5 | JSON and renderer references check cleanly; issues are mostly content-level, not schema-level. |
| Overall | 4.0/5 | Useful book-grade draft; one focused hardening pass would make it much stronger. |

## What Works Well

- The scope is clear: ingest time-series samples, store them efficiently, query
  dashboards, evaluate alerts, and retain older data at lower resolution.
- The naive row-per-sample baseline exposes the right forces: write volume,
  range queries, and cardinality.
- Cardinality is treated as a central failure mode, not as an afterthought. The
  traps around `user_id`/`request_id` labels are realistic and valuable.
- The storage step teaches the right mental model: per-series compressed chunks
  plus a label-to-series index.
- The rollup step correctly warns against averaging away spikes and keeps
  min/max/sum/count, which is much better than a vague "downsample old data"
  explanation.
- The option sets are generally honest tradeoffs: buffered ingest vs synchronous
  writes, TSDB vs wide-column vs relational extension, precomputed rollups vs
  query-time aggregation, pull/scrape vs push-only.
- The wrap-up fields are useful: `satisfies`, `interviewScript`,
  `levelVariants`, `followUps`, and `patterns` all line up with the main step
  sequence.
- Renderer-facing checks are clean: step/final-design nodes and links resolve,
  sequence participants resolve, `satisfies[*].steps[*]` and pattern step links
  resolve, and node types are canonical.

## Highest-Impact Issues

### 1. Capacity is a set of headlines, not an architecture-sizing ladder

The capacity section gives useful anchors: about 10M points/sec, tens to
hundreds of millions of active series, sub-second recent queries, full-res days,
rollups for months, and alert evaluation every 10-60 seconds. It does not yet
convert those numbers into the design decisions that follow.

Why it matters: metrics systems are data-intensive. A candidate should be able
to show how points/sec become network bandwidth, queue partitions, TSDB shard
count, chunk sizes, label-index memory, retention cost, rollup throughput, query
fan-out, and alert evaluation load.

Concrete fix:

- Add an assumed sample/event size after encoding and compression.
- Derive ingest bandwidth from 10M points/sec and a peak multiplier.
- Estimate raw data/day, compressed hot storage/day, and retained rollup
  storage/month.
- Estimate active-series index memory, because cardinality pressure is mostly
  memory/index pressure.
- Tie those estimates to queue partitions, ingestion workers, TSDB shard count,
  replication factor, and rollup worker throughput.
- Add a query/alert envelope: dashboard query QPS, max returned series, maximum
  lookback, rule count, and rule evaluation concurrency.

### 2. Ingestion acceptance and reliability semantics are ambiguous

Step 2 says ingestion is fire-and-forget, buffered, best-effort, and may lose
recent samples on buffer failure. The API returns only `202 Accepted`. The
requirements also say reliable alerting should not miss real alerts, and the
final design describes a buffered ingestion path without defining whether the
buffer is durable, replicated, memory-only, or replayable.

Why it matters: "metrics are best-effort" is often true, but alert-critical
metrics still need a clear contract. The system needs to say what happens before
acknowledgement, what can be dropped, what is retried, and which classes of data
are protected during overload.

Concrete fix:

- Define the acceptance boundary: for example, acknowledge only after append to
  a bounded replicated buffer/WAL, or explicitly say the API acknowledges after
  in-memory admission and can lose recent samples.
- Return partial acceptance details from ingest: accepted count, rejected count,
  dropped labels/series, retry-after, and error categories.
- Separate durable/replayable remote-write queues from ephemeral agent buffers.
- Add overload policy by priority: keep alert-critical metrics, shed debug or
  high-cardinality metrics, and emit owner-facing warnings.
- Clarify whether duplicates are acceptable and how idempotency is handled for
  retried batches.

### 3. The API and data model are too thin for the behavior being promised

The API has three compact endpoints: ingest, query range, and create rule. The
data model has `series`, `samples`, `rollups`, and `alert_rules`. That is a good
teaching minimum, but it does not support several claims in the requirements and
steps: collection topology, cardinality policy, tenant isolation, query limits,
retention tiers, alert state, notification routing, and operational ownership.

Why it matters: without these fields, important behavior remains prose-only. A
candidate can describe "cardinality guard" or "routed notifications", but the
reader does not see what state the system stores to enforce those contracts.

Concrete fix:

- Add tenant/source metadata: `tenant`, `service`, `collector`, `scrape_target`,
  `metric_descriptor`, and `retention_policy`.
- Expand `series` with owner, created/last-seen timestamps, status, label
  fingerprint, per-tenant/per-metric cardinality policy, and dropped/relabel
  counters.
- Add chunk/index metadata: `chunk`, `block`, `label_index_entry`, compaction
  level, min/max time, and storage tier.
- Add query governance: max lookback, max series, timeout, cache key, result
  freshness, and query cost/bytes scanned.
- Add alerting records: `alert_rule`, `rule_eval_state`, `alert_instance`,
  `silence`, `notification_route`, and `notification_attempt`.

### 4. Percentiles are promised but not supported by the model

The requirements and API mention percentiles, but the data model stores scalar
samples and rollups with only `min,max,sum,count`. That supports gauges,
counters, rates, sums, and means, but it does not support request-latency
percentiles across many observations unless the system stores histogram buckets,
summaries, sketches, or treats each request latency as an individual sample.

Why it matters: percentiles are a common interview trap in monitoring systems.
You cannot average p95s across hosts and get a correct global p95, and rollups
that preserve only sum/count cannot answer percentile queries later.

Concrete fix:

- Add histogram metrics as first-class input: bucket series, explicit bounds,
  count, sum, and bucket counters.
- Or add sketch support, such as t-digest/HDR-style rollups, with mergeability
  caveats.
- Update `rollups.agg` to preserve histogram buckets or sketches where
  percentile queries are required.
- Add a trap: "averaging per-host p95s" and the correct replacement: merge
  histograms/sketches or compute from raw observations while available.

### 5. Alerting reliability is under-modeled

Step 7 covers query caching, debounced rules, grouping, and routed
notifications. That is the right direction, but a reliable alerting platform
needs more: rule scheduling, evaluation state, HA/failover behavior, missed
evaluation handling, dedupe, silences, inhibition, escalation, notification
retries, and evidence of delivery.

Why it matters: alerting is not just another query client. During incidents, the
monitoring system may be overloaded, the TSDB may be partially unavailable, and
notification providers may fail. The design should say how it avoids both missed
critical alerts and alert storms.

Concrete fix:

- Add an alert-evaluator flow: load rules, evaluate recent raw/fine-resolution
  data, persist `pending/firing/resolved` state, and send notification jobs.
- Model HA rule ownership: shard rules across evaluators with leader election
  or deterministic ownership, and avoid duplicate pages after failover.
- Add silence/inhibition/dedup state and notification retry/escalation records.
- Define stale-data behavior: whether an alert fires, suppresses, or emits
  "monitoring data missing" when the input series disappears.

### 6. Collection is introduced, but the collection control plane is missing

The default collection option says pull/scrape with a push gateway for ephemeral
jobs. The final design shows `App -> Agent -> Ingest`, but it does not include
service discovery, scrape target metadata, scrape scheduling, target health,
push gateway state, or collector authentication.

Why it matters: push vs pull is not just an edge preference. It changes how the
system discovers services, detects liveness, controls scrape interval, handles
NAT/private networks, authenticates producers, and prevents a bad target from
overloading ingestion.

Concrete fix:

- Introduce `ServiceDiscovery`/`TargetRegistry` and optionally `PushGateway` in
  Step 5 and the final design.
- Add data-model records for targets, scrape intervals, labels injected by
  discovery, last scrape status, and owner/team.
- Show failed scrape as a liveness signal and distinguish it from "metric value
  is zero."
- Add auth/tenant identity for push ingestion so arbitrary clients cannot mint
  unlimited labels.

### 7. Sharding and final-design replication need sharper mechanics

Step 8 correctly chooses shard-by-series and warns against sharding by time.
The final design, however, has two shard nodes but no explicit replica model,
membership/ring metadata, write quorum, anti-entropy, or rebalancing path. It
also shows rollup from `ShardA` only, which can read as if only one shard feeds
retention.

Why it matters: at 10M points/sec and hundreds of millions of active series, the
hard parts are shard ownership, hot-shard mitigation, rebalancing, partial query
failure, and preserving recent data when a node dies.

Concrete fix:

- Add a concise shard-ring concept: series fingerprint -> shard owner(s), with
  replication factor and membership changes.
- Say whether writes go to a primary plus replicas, quorum, or async replicas.
- Show rollup workers consuming all shards or use a generalized `TSDB Shards`
  node instead of a single `ShardA -> Roll` edge.
- Add query behavior for partial shard failure: timeout, partial response flag,
  retry, or fail closed for alerting.
- Add hot-series/hot-shard mitigation: split hot metrics, virtual shards, or
  adaptive routing.

## System Design Soundness

The core design is sound as a learning path. It uses the right architecture
families: buffered ingestion, TSDB storage, label index, hot/cold retention,
rollup workers, query service, alerting engine, cardinality guard, and series
sharding.

The weak point is that several correctness and reliability contracts are
implicit. The system needs to define what "accepted" means, what data can be
dropped, how alert-critical data is protected, how query limits protect the
cluster, how alert state survives evaluator restarts, and how percentiles remain
valid after rollup.

The data model should also carry more of the design. Four entities are enough
for a simple illustration, but a book-grade system design should expose the
state that lets the platform enforce source ownership, cardinality budgets,
retention, alerting state, and notification delivery.

## Step-by-Step Pedagogical Review

### Step 1: Naive Metrics Table (the baseline)

This is an effective baseline. It explains why row-per-sample relational
storage fails and introduces series/cardinality early. Keep this step.

The improvement is to add one numerical failure example: at 10M points/sec, a
row-per-sample table receives hundreds of billions of rows/day before indexes
and retention. That would connect the capacity section to the baseline more
forcefully.

### Step 2: Ingestion Pipeline

The buffer-plus-batch default is the right first move. The traps correctly warn
against blocking producers and having no overload behavior.

Clarify the queue semantics. "In-memory buffer/queue" and `202 Accepted` are
too loose for a system that also promises reliable alerting. This step should
state whether the buffer is durable and replicated, whether agents retry, how
partial acceptance is reported, and which samples are sacrificed first during
overload.

### Step 3: Time-Series Storage

This is one of the strongest steps. It explains compressed per-series chunks and
the inverted label index clearly. The TSDB, wide-column, and relational-extension
options are realistic.

Add the missing storage mechanics: WAL or commit log, chunk/block metadata,
compaction, index memory sizing, out-of-order sample handling, and histogram or
sketch storage for percentile support.

### Step 4: Downsampling & Retention

The step teaches the right concept and correctly warns that averages hide
spikes. The raw -> 1m -> 1h progression is easy to understand.

The production gap is late and corrected data. Rollups need versioning or
recompute behavior for late-arriving samples, backfills, and retention-policy
changes. If percentiles are in scope, rollups also need histogram/sketch
preservation, not only min/max/sum/count.

### Step 5: Collection: Push vs Pull

The push-vs-pull tradeoff is well presented, and the default hybrid choice is
credible. Pull for long-lived services plus push for ephemeral jobs is a good
interview answer.

This step needs a visible control-plane component. Add service discovery, target
registry, scrape status, and push gateway behavior. Also consider placing this
step earlier or cross-linking it back to ingestion, because collection identity
and labels strongly affect cardinality and tenant limits.

### Step 6: Cardinality Control

This is the conceptual center of the interview and it works well. The traps are
specific and realistic, and the agent-side vs ingestion-side options are useful.

The next improvement is operator workflow. A cardinality guard should not only
drop or relabel samples; it should report the offending metric, owner, tenant,
label name, estimated series growth, and policy action. Add per-tenant and
per-metric budgets, allowlists, emergency overrides, and links to logs/traces or
exemplars for high-cardinality exploration.

### Step 7: Querying & Alerting

The dashboard/query path and alert debounce concept are both necessary. The
flow for recent raw vs long-range rollups is clear.

The issue is scope compression. Querying and alerting are different enough that
the alert path deserves its own state and flow: rule scheduler, evaluator
ownership, persisted pending/firing state, silences, notification queue, retries,
and delivery evidence. The query path should also include guardrails: max
series, max lookback, timeout, query cost, partial results, and cache freshness.

### Step 8: Scaling by Sharding

Series sharding is the right default and the traps identify the important
mistakes. Keeping a series co-located is the correct teaching point.

Add mechanics: shard ring, virtual shards, replication factor, write/read
quorum or primary-replica behavior, rebalancing, hot-shard handling, and partial
query failure. The step says replicas exist, but the view does not show or
describe enough of the replication contract.

## Final Design Review

The final design integrates the main components from the walkthrough: app,
agent, ingest, queue, cardinality guard, router, TSDB shards, rollup worker,
cold store, query/cache/dashboard path, alert rules, alerting engine, and
notification provider.

It would become more production-realistic with a small set of additions:

- `TargetRegistry` or `ServiceDiscovery` for scrape/pull collection.
- `PushGateway` for ephemeral jobs if the default collection choice keeps
  mentioning it.
- `ControlPlane` for tenant/source auth, metric descriptors, cardinality
  budgets, retention policies, query limits, and alert routes.
- Alert state and notification delivery components, or at least records in the
  data model.
- A clearer `TSDB Shards`/replica representation so rollups, queries, and shard
  failure behavior are not tied to one illustrated shard.

## Concept Introduction and Learning Flow

The concept staging is mostly strong: time series and cardinality first, then
buffered ingestion, compressed chunks, rollups, collection models, cardinality
guarding, query/alerting, and finally sharding.

Two concepts should be introduced explicitly:

- Histogram/sketch metrics for percentile queries. This belongs near Step 3 or
  Step 4.
- Alert state machines. This belongs in Step 7 and should cover
  `inactive -> pending -> firing -> resolved`, plus silence/inhibition/dedup.

The dataset should also distinguish telemetry data from observability workflows:
samples, series, chunks, and rollups are the data plane; targets, descriptors,
policies, quotas, rules, silences, and routes are the control plane.

## Step-to-Final-Design Coherence

Most steps map cleanly to final-design components:

- Step 2 adds `Queue`.
- Step 3 motivates `TSDB`/hot store.
- Step 4 adds `Roll` and `Cold`.
- Step 6 adds `Cardinality`.
- Step 7 adds `Query`, `Cache`, `Alert`, `Rules`, and `Notify`.
- Step 8 adds `Router`, `ShardA`, and `ShardB`.

The weaker connections are collection and replication. Step 5's default hybrid
collection design is not fully visible in the final design, and Step 8's
replication claim is not represented beyond two shard nodes. The final design
should show either explicit replica/shard ownership or prose that explains the
diagram is simplified.

## Realism Compared With Production Systems

The dataset captures the broad shape of Prometheus/M3-style metric systems, but
it should add the operational surfaces that make those systems survivable:

- tenant/source authentication and quotas;
- metric descriptors, ownership, and label policies;
- service discovery and scrape health;
- per-tenant cardinality budgets and owner notifications;
- query admission control and expensive-query protection;
- histogram/sketch support for percentiles;
- alert evaluator HA and persisted state;
- silences, inhibition, dedupe, escalation, and notification retries;
- shard membership, rebalancing, replication, and repair;
- self-monitoring of the monitoring system itself.

These additions do not require changing the main eight-step order. They can be
added as compact API/model fields, traps, failure drills, one or two extra
flows, and final-design notes.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- The `dataModel` array shape is valid for this renderer.
- Step and final-design `view.nodes` references resolve to
  `highLevelArchitecture.nodes`.
- Step and final-design string `view.links` references resolve to
  `highLevelArchitecture.links`.
- `satisfies.functional[*].steps`, `satisfies.nonFunctional[*].steps`, and
  `patterns[*].steps` all resolve to existing steps.
- Step `probeLinks` resolve to top-level `toProbeFurther.links`.
- Sequence participants and top-level sequence message endpoints resolve.
- Canonical node types in use are valid: `cache`, `database`, `external`,
  `gateway`, `observability`, `queue`, `service`, and `worker`.
- No generated `docs/` rebuild is needed for this `REVIEW.md`-only change.
- Optional book extras are absent: `technologyChoices`, `aiVisuals`, per-step
  `aiVisual`, and `explainerComic`. That is not a rendering problem, but
  `technologyChoices` would be useful for this domain.

## Recommended Edits, Prioritized

### P1: Add derived capacity math

Turn the current capacity bullets into a sizing ladder for bandwidth, storage,
index memory, queue partitions, shards, replication, rollup work, query fan-out,
and alert evaluation load.

### P1: Define ingestion acceptance and overload contracts

Make `202 Accepted` mean something precise. Add partial acceptance, rejected
series/labels, retry/backpressure behavior, priority shedding, and durable vs
best-effort buffer semantics.

### P1: Expand API and data model to support the promised operations

Add tenant/source/target records, metric descriptors, cardinality policy,
retention policy, chunk/index metadata, query guardrails, alert state, silences,
routes, and notification attempts.

### P1: Fix percentile support

Add histograms or mergeable sketches and preserve them through rollups. Add a
trap for averaging p95s across hosts.

### P2: Make alerting a real subsystem

Add a rule-evaluation flow and records for pending/firing/resolved state,
evaluator ownership, dedupe, inhibition, silences, escalation, and notification
delivery retries.

### P2: Add collection control-plane details

Introduce service discovery/target registry, scrape status, push gateway,
collector auth, and target ownership.

### P2: Sharpen sharding and replication

Define shard ring ownership, replication factor, write/read behavior,
rebalancing, hot-shard handling, and partial query failure behavior.

### P3: Add technology choices

For a book dataset, `technologyChoices` would be valuable: Prometheus/Mimir/M3,
VictoriaMetrics, Kafka/Pulsar buffers, object storage tiers, Cortex-style
querying, Alertmanager-style notification routing, and managed cloud monitoring
options.

### P3: Add a few generated learning assets when convenient

AI visuals/comic are optional, but this case would benefit from one visual for
the write path, one for cardinality explosion, and one for query/alerting.

## What Not To Change

- Keep the naive baseline. It is short and does useful teaching work.
- Keep cardinality as a central theme. It is the most important differentiator
  from generic data-ingestion interviews.
- Keep the hybrid pull/push collection default.
- Keep precomputed rollups as the default for long-range dashboards.
- Keep sharding by series as the scaling default.
- Keep the existing traps; they are concrete and interview-relevant.

## Bottom Line

This is a good metrics-monitoring walkthrough with strong conceptual coverage.
The next pass should make it operationally explicit: derive the numbers, define
ingestion and alerting contracts, model the control-plane state, preserve
percentiles correctly, and make sharding/replication mechanics visible enough
for a senior candidate to defend.
