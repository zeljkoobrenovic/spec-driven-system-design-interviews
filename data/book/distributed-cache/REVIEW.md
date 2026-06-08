# Review: Distributed Cache - System Design

Reviewed file: `data/book/distributed-cache/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a strong, compact distributed-cache walkthrough. It teaches the right
main arc: local cache limitations, cache-aside, keyspace sharding, eviction,
write consistency, hot-key protection, and failure handling. The options,
traps, recaps, and probe links are useful and mostly interview-ready.

The main gaps are not in the topic selection. They are in precision. Several
views and captions blur cache-aside with read-through by showing the cache node
loading from the database even when the default design says the application
loads and backfills. Capacity gives headline numbers but does not translate
them into node count, memory overhead, per-node QPS, network bandwidth, or
residual database load. Failover is directionally correct but needs a more
explicit replication and promotion contract.

| Area | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.05 / 5 | Correct core mechanisms; needs sharper cache-aside/read-through boundary, capacity math, and replication semantics. |
| Production realism | 3.75 / 5 | Hot keys, eviction, consistency, and failover are covered; operations, observability, backpressure, and resharding are still thin. |
| Pedagogical flow | 4.35 / 5 | Excellent step order and useful trade-off options; a few diagrams contradict the prose. |
| Dataset/rendering fit | 4.15 / 5 | JSON parses and step references resolve; one step view references a hidden node through a reused link. |
| Overall | 4.05 / 5 | A good book case that would become much stronger with focused precision and operations hardening. |

## What Works Well

- The step sequence is natural. Each step exposes the next problem: local maps
  are not shared, one cache node cannot scale, sharded nodes need eviction,
  cache/DB divergence needs a consistency strategy, hot keys break uniform
  sharding, and node loss creates a cold-shard DB spike.
- The default design stays scoped. It does not turn the cache into the source
  of truth; the database remains authoritative and the cache is explicitly
  best-effort.
- The option sets are practical. Cache-aside vs read-through, client-side
  hashing vs proxy, LRU vs LFU vs TTL-only, invalidate vs write-through vs
  write-back, and hot-key mitigations are all real interview trade-offs.
- The dataset calls out important senior signals: read-miss/write races,
  synchronized expiries, request coalescing, local L1 cache trade-offs,
  virtual nodes, and cold-shard protection.
- `satisfies`, `interviewScript`, `levelVariants`, and `followUps` are aligned
  with the main story and make the case usable as teaching material.
- The external probes are credible for this topic, especially Facebook
  Memcache, Redis Cluster, Redis client-side caching, Tail at Scale, and SRE
  overload handling.

## Highest-Impact Issues

### 1. Cache-aside and read-through are mixed in diagrams and captions

The default design is cache-aside: the application checks the cache, loads from
the database on a miss, and backfills the cache. Several diagram captions and
links imply a different contract where `CacheA` loads directly from `DB`.

Examples:

- Step `cache-aside` says the app loads from the DB on a miss, but its view
  caption says "on a miss the node loads from the backing database."
- The default cache-aside option includes the high-level link `a-db`, whose
  label is `miss -> load`, even though the prose says the app does the load.
- Step `hotkeys` and `failover` continue to use `a-db`, again implying cache
  node to DB loading.
- The final design includes both `app-db` and `a-db`, so it looks like the
  system has both cache-aside and read-through loaders in the default path.

Why it matters: this is the central contract of the design. In cache-aside,
cache failure degrades to DB reads by the app and cache nodes do not need DB
credentials/loaders. In read-through, the cache tier owns loading and cache
failure has different blast radius. Candidates should not learn those as one
merged mechanism.

Concrete fix:

- Reserve `CacheA -> DB` links for the read-through and write-back options.
- For the default cache-aside path, show `App -> DB` for the miss load and
  `App -> CacheA` for the backfill or invalidation.
- Update captions that say the node loads from DB unless the selected option
  is explicitly read-through.
- In the final design, choose one default. If it remains cache-aside, remove
  `a-db` from the default final view or relabel it as an optional read-through
  path.

### 2. Capacity is a headline, not a sizing model

The capacity section lists useful targets: about 1M reads/s, 95%+ hit rate, TBs
of RAM, KB-sized values, and sub-ms hit latency. It stops before the interview
math that would justify the architecture.

Missing pieces:

- Residual DB load: at 1M reads/s and 95% hit rate, the DB still sees about
  50k read misses/s before writes and stampedes.
- Memory sizing: `TBs` should be translated into approximate node count using
  per-node RAM, usable memory after fragmentation/metadata, replication factor,
  and safety headroom.
- Per-node throughput: the design should estimate QPS per node under uniform
  load and explain how much skew/hot-key headroom is needed.
- Network bandwidth: 1M ops/s with KB-sized values can become multiple GB/s
  across clients, caches, replicas, and DB backfills.
- Latency budget: "sub-ms reads on a hit" should distinguish same-AZ network
  round trip, client serialization, cache CPU, connection pooling, and p99 tail
  behavior.

Concrete fix:

- Add 4-6 capacity rows or notes deriving node count, residual DB miss load,
  per-node QPS, memory overhead, replication cost, and bandwidth.
- Explicitly state that 95% hit rate may be insufficient if the backing DB
  cannot absorb 50k misses/s.
- Add one line for headroom under hot-key skew and cache warmup.

### 3. Replication and failover need a clearer contract

The failover step is directionally right: a dead cache node can cold-spike the
database, so replicas and membership updates help. But the design does not yet
define how replication works or how failover is made safe enough for a cache.

Ambiguities:

- Is replication synchronous or asynchronous?
- Does the client write to primary only, primary plus replica, or a proxy that
  fans out?
- Who promotes the replica: config service, router, client library, or an
  operator?
- What happens if the primary is suspected dead but still serving traffic?
- How stale may a warm replica be, and how is that bounded by TTL/version?
- Does failover reroute to one replica, or does consistent hashing spread the
  failed shard across many peers?

The current `Replica -> App` link also reads oddly: applications normally route
through the client library or router, not by receiving service directly from a
replica.

Concrete fix:

- Add one sequence flow for primary failure: health check fails, config epoch
  advances, clients refresh, reads route to replica or remapped owners, and DB
  backfill is rate-limited.
- Add a short note that cache replication may be async because the DB is
  authoritative, but stale replicas must be bounded by TTL/version and miss
  fallback.
- Change the failover diagram to route through `ClientLib` or `Router` rather
  than `Replica -> App`.

### 4. Operations and observability are underrepresented

The final design says the cache improves performance without becoming a new
single point of failure, but the dataset has no explicit operations step or
wrap-up section for the signals that prove this in production.

Important missing signals:

- Hit rate, miss rate, negative-cache hit rate, and DB fallback QPS.
- Evictions/sec, memory fragmentation, used memory, large-value distribution,
  and item age distribution.
- Per-shard QPS, hot-key detection, single-flight wait time, and rejected or
  shed requests.
- p50/p95/p99 latency for hits, misses, sets, deletes, replication, and config
  refresh.
- Ring/config epoch drift across clients, failed health checks, failover time,
  warmup progress, and replica lag/staleness.

Concrete fix:

- Either add an eighth "Operations, Backpressure, and Observability" step or
  expand `failover` with an operations subsection.
- Include overload behavior: rate-limit DB backfill, serve stale for eligible
  keys, use TTL jitter, and shed cache-fill work before taking down the DB.
- Add `technologyChoices` for self-hosted Redis/Memcached/Dragonfly/KeyDB and
  managed ElastiCache/Memorystore/Azure Cache options.

### 5. API and data model are intentionally small, but missing production knobs

The simple `get`, `set`, and `delete` API is fine as a baseline. For a
production distributed cache, the dataset should name a few optional controls
because later steps depend on them.

Useful additions:

- Namespace or tenant/key prefix so quotas, auth, and invalidation can be
  scoped.
- Conditional set/CAS token or version check for callers that need safer
  write-through/update behavior.
- `multiGet` or pipelining for high-throughput callers.
- TTL semantics: absolute vs relative expiry, max TTL, jitter, and whether TTL
  is refreshed on read.
- Value size limits and optional compression guidance.
- Entry metadata such as `created_at`, `last_accessed`, `frequency`, `version`,
  `size_bytes`, and `flags`.
- Ring metadata with config epoch, replica owner, node zone, and node state.

Concrete fix:

- Keep the public API compact, but add an "advanced knobs" note or one extra
  API row for `multiGet`.
- Extend the data model enough to support eviction accounting, versioned
  invalidation, and membership epochs.

## System Design Soundness

The core architecture is sound for a read-heavy, stale-tolerant cache in front
of an authoritative database. Cache-aside is the right default because it keeps
correctness in the application/database path and makes cache outages a
performance event rather than a correctness event.

Sharding with consistent hashing and virtual nodes is the right scaling answer
for a key-value cache. The dataset correctly warns against modulo hashing and
explains why topology changes should not remap the whole keyspace.

Eviction coverage is good. LRU, LFU, and TTL-only are compared honestly. The
TTL-only option correctly says TTL alone does not protect memory under pressure.
The next improvement is to add concrete memory accounting and scan-resistant
variants such as segmented LRU or TinyLFU as an advanced note, not as a core
step.

The consistency step is strong conceptually. It names invalidate-on-write,
write-through, write-back, and the read-miss/write interleaving race. The main
fix is to align the diagrams so the default invalidate/cache-aside path does
not look like read-through.

Hot-key handling is also sound. Request coalescing, hot-key replication, tiny
local L1 cache, refresh-before-expiry, and TTL jitter are the right mechanisms.
The missing piece is operational: how hot keys are detected, how long keys stay
replicated, and what happens when the hot-key list itself changes rapidly.

## Step-by-Step Pedagogical Review

### Step 1: 1. Naive: An In-Process Local Cache

This is a clean baseline. It makes the limitations of per-instance memory
obvious: duplication, stale invalidations, heap limits, and cold deploys. It is
especially useful because the later L1 hot-key option can refer back to this
step as a deliberately tiny and short-TTL exception.

No major change needed.

### Step 2: 2. Cache-Aside in Front of the Database

This is the most important step and the main place to tighten precision. The
description, option pros/cons, and sequence correctly explain cache-aside: the
application loads from DB and backfills. The view caption and reused `a-db` link
make the cache node look responsible for loading from DB.

Fixing this step will clarify the entire dataset. Split the default
cache-aside view from the read-through option view, and use the read-through
option to teach why centralizing loaders is useful but operationally more
coupled.

### Step 3: 3. Shard the Keyspace with Consistent Hashing

This is a strong sharding step. The client-side hashing and proxy/router
options are realistic, and the trade-offs are stated well: latency and fewer
tiers vs thin clients and centralized routing.

Possible improvement: connect the routing choice to observability and
backpressure. A proxy can enforce quotas and collect central metrics; client
libraries need shared telemetry and consistent config refresh logic.

### Step 4: 4. Eviction: Make Room When Memory Is Full

The teaching content is good, but this step has a renderer-facing issue: the
default view includes visible nodes `App`, `CacheA`, `Eviction`, and `DB`, while
its link list includes `clientlib-a`, whose source node is `ClientLib`. Since
`ClientLib` is not in the step view, the generated diagram can introduce or
reference a hidden node inconsistently.

Fix the view by either adding `ClientLib` to `view.nodes` or replacing
`clientlib-a` with an inline `App -> CacheA` link, matching the option views.

Conceptually, this step would also benefit from one capacity note: memory
pressure comes from value bytes plus metadata, fragmentation, replication, and
reserved headroom, not only number of keys.

### Step 5: 5. Cache/DB Consistency on Writes

This is one of the stronger steps. It chooses invalidate-on-write as the
default, keeps write-through/write-back as trade-offs, and names the read-miss
backfill race.

The main improvement is to add a version/CAS or monotonic timestamp mitigation
as a concrete option for the race. The current prose mentions versioned keys,
but the API and data model do not carry a version field.

### Step 6: 6. Hot Keys and Thundering Herds

This step is strong and interview-relevant. It correctly says consistent
hashing does not spread one hot key and introduces request coalescing, key
replication, and tiny local L1 caching.

Possible improvement: add the operating loop. How does the system detect a hot
key, decide replica count, invalidate every hot-key replica, and avoid memory
waste after the spike ends?

### Step 7: 7. Replication, Failover, and Failure Modes

This is the right closing step, but it is too compressed for the amount of
production responsibility it carries. The failover mechanics, config epoch,
stale replica tolerance, and DB backfill throttle should be more explicit.

Add one sequence flow and consider one more failure drill for config-service
staleness or split-brain routing, because that is the subtle failure mode of
client-side hashing.

## Final Design Review

The final design integrates all main concepts: cache-aside, client library or
proxy routing, consistent hashing, virtual nodes, per-node eviction, write
invalidation, hot-key replication, request coalescing, and warm failover.

The final diagram should be made more opinionated. It currently includes both
direct client hashing (`clientlib-a`) and proxy routing (`clientlib-router`),
and both app-to-DB and cache-to-DB paths. That is acceptable if the goal is to
show alternatives, but the final design should usually show the chosen default
and mention alternatives in text.

Recommended final-design stance:

- Default to cache-aside with app DB fallback and app cache backfill.
- Choose client-side hashing or proxy as the main route. If both remain, label
  the proxy as optional.
- Route failover through `ClientLib`/`Router` based on config epoch, not
  directly from `Replica` to `App`.
- Add a concise operations sentence covering hit-rate SLOs, DB fallback budget,
  TTL jitter, backfill throttling, and hot-key alerts.

## Concept Introduction and Learning Flow

The concept staging is good. The dataset introduces concepts just before they
are needed, and the `whyNow` and `recap` fields help each step hand off to the
next one.

The strongest teaching moments are:

- Local cache limitations motivate a shared cache tier.
- Consistent hashing is introduced as protection against cache-wide churn, not
  just as a sharding buzzword.
- Eviction is tied to hit rate, not treated as an implementation detail.
- The write consistency step names a real race.
- The hot-key step explains why uniform sharding assumptions fail.

The one concept that needs more careful separation is cache-aside vs
read-through. Once that boundary is clean, the rest of the walkthrough will
read much more consistently.

## Step-to-Final-Design Coherence

The steps build toward the final design well:

- `naive` motivates moving out of process.
- `cache-aside` introduces the read path and fallback contract.
- `sharding` explains how the cache grows horizontally.
- `eviction` addresses bounded memory.
- `consistency` handles DB/cache divergence on writes.
- `hotkeys` handles skew and stampedes.
- `failover` closes the node-loss scenario.

The coherence gap is the final design's diagram surface. It accumulates
mechanisms from all steps but does not clearly distinguish chosen defaults from
alternatives. The final prose says cache-aside and optional proxy, while the
view includes read-through-looking `CacheA -> DB` and both direct/proxy routing.

## Realism Compared With Production Systems

The dataset is realistic on the core cache mechanics. It would be more
production-realistic if it added:

- Resharding/rebalancing behavior when nodes are added or removed, including
  warmup and migration throttles.
- Config epoch handling and client refresh behavior.
- Backpressure when the DB fallback path approaches its budget.
- Hot-key detection and expiration of hot-key replication decisions.
- Observability dashboards and alerts for hit rate, evictions, hot shards,
  stale config, failover time, replica lag, and stampedes.
- Security/tenancy basics: namespacing, authn/authz, TLS, quotas, and limits on
  value size.
- A technology-choice section covering common self-hosted and managed cache
  options.

These do not all need full steps. A focused operations step or a practical
`technologyChoices` wrap-up would cover most of the gap without bloating the
case.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Top-level `patterns[*].steps` and `satisfies[*].steps` references resolve to
  real step IDs.
- Step and option views use structured `view` objects rather than raw Mermaid,
  matching current project conventions.
- The targeted endpoint check found one issue: step `eviction` references
  `clientlib-a`, whose endpoint `ClientLib` is not listed in that view's
  `nodes`.
- The inline `L1` node in the local-cache option appears intentional and
  acceptable as a local view node, but it is worth keeping such local nodes
  rare so the final architecture remains coherent.
- No `technologyChoices` field is present. That is optional, but this dataset
  is a good candidate because cache product choices materially affect routing,
  replication, persistence, and operational burden.
- No `aiVisual`, `aiVisuals`, or `explainerComic` assets are wired. That is not
  a correctness issue.

## Recommended Edits, Prioritized

### P1: Align cache-aside diagrams with the default contract

Fix `cache-aside`, `hotkeys`, `failover`, and `finalDesign` so default diagrams
do not imply cache-node DB loading unless the selected option is read-through.

### P1: Fix the eviction view link endpoint mismatch

In step `eviction`, either add `ClientLib` to `view.nodes` or replace
`clientlib-a` with an inline `App -> CacheA` link.

### P1: Add capacity math

Expand capacity with residual DB load, per-node QPS, node count, memory
overhead, replication cost, bandwidth, and latency-budget notes.

### P2: Clarify replication and failover semantics

Add one sequence flow and specify async/sync replication, config epochs,
promotion/rerouting ownership, replica staleness bounds, and backfill
throttling.

### P2: Add operations and observability

Add either a short operations step or expand failover with monitoring,
overload/backpressure, warmup, hit-rate SLOs, and hot-key alerts.

### P2: Extend API/data model with production knobs

Add namespace/tenant scope, optional CAS/version field, value-size limits,
`multiGet`/pipelining, TTL jitter semantics, and ring config epochs.

### P3: Add technology choices

Include self-hosted and managed choices such as Memcached, Redis Cluster,
Dragonfly, KeyDB, ElastiCache, Memorystore, Azure Cache for Redis, and relevant
trade-offs around persistence, clustering, replication, and client libraries.

## What Not To Change

- Preserve cache-aside as the default. It is the right baseline for a cache in
  front of an authoritative DB.
- Keep the seven-step progression. It is concise and teaches one problem at a
  time.
- Keep read-through, write-through, write-back, proxy routing, and local L1 as
  alternatives rather than forcing them into the default final design.
- Preserve the hot-key and stampede material. It is one of the strongest parts
  of the dataset.
- Keep the case focused on a cache, not a durable distributed KV store. Durable
  write semantics belong in the adjacent KV-store dataset.

## Bottom Line

This dataset is already a useful distributed-cache interview. The next edit
should focus on precision rather than breadth: clean up cache-aside vs
read-through diagrams, add real sizing math, make failover mechanics explicit,
and fix the one renderer-facing link mismatch. After that, an operations and
technology-choice pass would make it book-ready.
