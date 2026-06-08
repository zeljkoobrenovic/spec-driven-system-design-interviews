# Review: Distributed Cache - System Design

Reviewed file: `data/book/distributed-cache/interview.json`
Review date: 2026-06-08

## Executive Summary

This is now a strong distributed-cache walkthrough. The recent edits resolved
the previous highest-impact gaps: the default cache-aside path is mostly cleanly
separated from read-through, capacity now includes useful sizing math, the
eviction view no longer references a hidden client-library node, and failover
now has an explicit async-replication/config-epoch story plus a sequence flow.

The remaining work is no longer about basic correctness. It is about production
depth and teaching precision: make operational control loops explicit, extend
the API/data model with the knobs the prose already depends on, clarify
topology-change behavior beyond consistent hashing, and make the final diagram
less likely to read as "all alternatives are default."

| Area | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.45 / 5 | Cache-aside, sharding, eviction, consistency, hot keys, and failover are coherent; API/data model still understate versioning, tenancy, and topology metadata. |
| Production realism | 4.10 / 5 | Capacity and failover are much better; needs a clearer operations/backpressure loop and resharding/warmup behavior. |
| Pedagogical flow | 4.55 / 5 | Excellent seven-step progression with just-in-time concepts and realistic trade-offs; a few labels can still confuse cache-aside vs read-through. |
| Dataset/rendering fit | 4.40 / 5 | JSON parses, references resolve, and structured views fit the renderer; final view is visually busy and option labels are generic. |
| Overall | 4.35 / 5 | Book-ready in core shape, with targeted production-hardening edits still worth doing. |

## What Works Well

- The prior cache-aside/read-through mismatch has been largely fixed. Default
  views now show `App -> DB` miss load and `App -> CacheA` backfill; the
  `CacheA -> DB` link is labeled as read-through and kept out of the default
  final path.
- Capacity is now interview-useful: residual DB load, node count, per-node QPS,
  bandwidth, and latency-budget notes make the architecture feel sized rather
  than merely described.
- The failover step now teaches a real contract: async cache replication, config
  epochs, client refresh, bounded stale replicas, split-brain risk, and
  rate-limited DB fallback.
- The step sequence remains concise and natural. Each step exposes the next
  problem: local cache limits, cache-aside, sharding, eviction, consistency,
  hot keys, and node failure.
- Option sets are practical rather than strawman-heavy: cache-aside vs
  read-through, client hashing vs proxy, LRU vs LFU vs TTL-only,
  invalidate-on-write vs write-through/write-back, and hot-key mitigations.
- The dataset teaches strong senior signals: read-miss/write races, virtual
  nodes, scan pollution, TTL jitter, request coalescing, warm failover, epoch
  drift, and DB-fallback budgets.

## Highest-Impact Issues

### 1. Operations and backpressure are still compressed into prose

The final design now mentions hit-rate SLOs, DB-fallback budget, hot-key alerts,
evictions, memory headroom, replica lag, and config-epoch drift. That is the
right set of signals, but it is mostly a single final-design sentence rather
than a teachable operating model.

Why it matters: distributed caches fail by overload and feedback loops. A miss
storm can take down the DB; a bad config epoch can split traffic; hot-key
replication can waste memory; warm failover can still become cold if backfill is
uncontrolled. Candidates should be able to describe what the system does when
metrics cross thresholds, not only what metrics exist.

Concrete fix:

- Add an "Operations, Backpressure, and Warmup" section or eighth step.
- Include explicit actions: rate-limit DB backfill, shed optional cache-fill
  work, serve stale for eligible keys, jitter TTLs, cap per-key single-flight
  waiters, and throttle rewarming after node add/failover.
- Name alerts by symptom and owner: DB fallback QPS over budget, per-shard QPS
  skew, high evictions/sec, replica lag, stale config epoch across clients, and
  rising p99 cache-hit latency.
- Add one failure drill for "DB fallback budget exhausted during cache cold
  start" with expected degradation behavior.

### 2. API and data model do not yet carry the production knobs the story uses

The public API is intentionally small, which is good for an interview baseline.
But the prose now depends on concepts that are not represented in API or data
model fields: versioned keys, config epochs, replica ownership, value sizing,
tenant/namespace isolation, and high-throughput batched reads.

Useful additions:

- `namespace` or tenant/key prefix so quotas, auth, metrics, and invalidation
  can be scoped.
- `multiGet(keys)` or pipelining as an explicit high-throughput read path.
- TTL semantics: relative vs absolute expiry, max TTL, jitter policy, and
  whether reads refresh TTL.
- Optional CAS/version token for callers that need safer invalidate/backfill
  races.
- Value-size limits and optional compression guidance.
- Entry metadata: `size_bytes`, `created_at`, `last_accessed`,
  `frequency_count`, `version`, and flags such as negative-cache marker.
- Ring/topology metadata: `epoch`, primary owner, replica owner, zone, node
  state, and last health transition.

Concrete fix:

- Keep `get/set/delete` as the simple core API, but add one "advanced controls"
  API card and expand the two data-model entries.
- Align the failover text's "TTL/version" and "config epoch" language with
  concrete fields in the data model.

### 3. Resharding and topology-change behavior is still too implicit

The sharding step correctly teaches consistent hashing and virtual nodes. It
also says adding/removing a node moves only that node's share of keys. What is
missing is the production workflow around that remap.

Ambiguities:

- How are new nodes warmed before taking real traffic?
- Are keys actively migrated, lazily reloaded on miss, or both?
- How is DB fallback throttled during planned resharding?
- How are virtual nodes assigned across zones so a zone event does not remove a
  primary and its replica together?
- What happens to long-lived clients that lag behind a ring update?

Concrete fix:

- Add a short topology-change flow: add node, publish new epoch, gradually move
  token ranges, warm key ranges, throttle misses, and alert on client epoch
  drift.
- In the failover or sharding step, state the placement rule: primary and
  replica should not share the same host/rack/AZ fault domain.
- Clarify whether this cache relies on lazy refill only, active key migration,
  or a hybrid.

### 4. The final view still mixes default and optional paths visually

The final design prose is now explicit: the default is client-library
cache-aside, while the proxy/router tier and read-through/write-through are
alternatives. The final view still includes both `clientlib-a` and
`clientlib-router` plus router-to-node links in one diagram. Because generated
flowchart links are rendered as plain lines without arrowheads, the optional
proxy path can look as authoritative as the default direct path.

Why it matters: the final diagram is what many readers will remember. It should
make the default architecture visually dominant and alternatives visibly
secondary.

Concrete fix:

- Either remove `Router` from the default final view and keep it in the
  sharding option, or mark router links with a dotted/optional render style if
  the renderer supports that for generated views.
- If both paths remain, add a final-design option tab: "Client library default"
  vs "Proxy routing variant."
- Keep `a-db` out of the default view; it is correctly reserved for explicit
  read-through/write-back alternatives.

### 5. A few labels still blur cache vocabulary

The main diagrams now distinguish cache-aside and read-through, but one flow is
named "Read-through with hit/miss" while its note and messages describe
cache-aside. In cache-system terminology, read-through usually means the cache
tier loads from the backing store, so this label can reintroduce the confusion
the recent edits otherwise fixed.

Concrete fix:

- Rename the `cache-aside` flow to "Cache-aside hit/miss" or "Cache-aside read
  with backfill."
- Consider giving option titles explicit names instead of relying on generic
  tab labels: "Cache-aside", "Read-through", "Client-side hashing", "Proxy
  routing", "LRU", "LFU", and "TTL-only."

## System Design Soundness

The default architecture is sound: cache-aside in front of an authoritative DB,
consistent-hashing shards with virtual nodes, per-node eviction, delete-on-write
invalidation, request coalescing, hot-key replication, and async warm replicas.
The recent edits made the source-of-truth boundary much clearer. Cache failure
now degrades to DB reads by the application rather than implying cache nodes
must have DB loaders in the default path.

The capacity model is now strong enough for an interview. The new residual miss
load note is especially important: 95% hit rate at 1M reads/sec still sends
about 50k reads/sec to the DB before writes and stampedes. The node-count,
per-node QPS, bandwidth, and p99 latency rows make the sharding and hot-key
steps feel motivated by numbers.

The consistency step is good but can be grounded further. It names the
read-miss/write interleaving race and mentions versioned keys, but neither the
API nor data model carries a version/CAS concept. Adding that field would make
the mitigation concrete without bloating the case.

The failover story is now credible for a cache. Async replication is acceptable
because the DB is authoritative, stale replicas are bounded by TTL/version, and
config epochs prevent split-brain routing. The next level is placement and
resharding: where replicas live, how epochs roll out under planned changes, and
how warmup is throttled.

## Step-by-Step Pedagogical Review

### Step 1: 1. Naive: An In-Process Local Cache

This is a clean baseline. It makes the limitations of per-instance memory
obvious: duplicate caches, stale invalidations, heap limits, and cold deploys.
It also sets up the later local L1 option as a deliberately tiny exception, not
the main cache.

No major change needed.

### Step 2: 2. Cache-Aside in Front of the Database

This step is much stronger after the recent changes. The default view, option,
API sequence, and captions now show the application loading from the DB and
backfilling the cache. The read-through alternative is properly framed as a
different contract where the cache tier owns the loader.

Recommended polish: rename the flow currently called "Read-through with
hit/miss" because its actual behavior is cache-aside. Explicit option titles
would also make the tabbed UI more teachable.

### Step 3: 3. Shard the Keyspace with Consistent Hashing

This is a strong sharding step. It explains why modulo hashing is dangerous and
why virtual nodes reduce cache churn. The client-side hashing vs proxy trade-off
is realistic: lower latency and fewer tiers vs thin clients and centralized
metrics/quotas.

Add a bit more topology-change realism. The step should say how node add/remove
is rolled out: epoch publishing, gradual token movement, lazy refill vs active
warming, and throttled DB fallback during planned resharding.

### Step 4: 4. Eviction: Make Room When Memory Is Full

This step now fits the renderer and the architecture. The previous hidden
`ClientLib` link issue is fixed with an inline `App -> CacheA` read/backfill
link. LRU, LFU, and TTL-only are compared honestly, and the capacity section now
supports the memory-pressure story.

Possible improvement: add one advanced sentence about scan-resistant policies
such as segmented LRU or TinyLFU. Keep it as an advanced note, not a new main
step.

### Step 5: 5. Cache/DB Consistency on Writes

This remains one of the stronger steps. It chooses invalidate-on-write as the
default, keeps write-through/write-back as trade-offs, and names the
read-miss/backfill race.

The main improvement is to make the race mitigation concrete. Add version/CAS
fields in the API/data model, or show a short flow where a stale backfill is
rejected because its version is older than the current DB value.

### Step 6: 6. Hot Keys and Thundering Herds

This step is strong and interview-relevant. It correctly says consistent
hashing cannot spread one key, then introduces request coalescing, key
replication, and tiny local L1 caching.

The next improvement is operational: how hot keys are detected, when a key is
promoted to replicated status, how replica count is chosen, how invalidation
fans out, and how the system demotes keys after a spike.

### Step 7: 7. Replication, Failover, and Failure Modes

This step improved materially. It now explains async replication, bounded
staleness, config-owned promotion, epoch fencing, cache-empty correctness, and
rate-limited backfill. The new sequence flow and split-brain drill are exactly
the right additions.

Further improvement should focus on placement and warmup. State that primary
and replica must sit in different fault domains, and describe how the system
warms or slowly admits traffic after a primary failure or planned node add.

## Final Design Review

The final design now integrates the chosen mechanisms coherently:

- Cache-aside default with application DB fallback and cache backfill.
- Client library using consistent hashing and virtual nodes.
- Optional proxy/router alternative.
- Per-node LRU/LFU/TTL eviction with jitter.
- Delete-on-write invalidation for bounded staleness.
- Request coalescing and hot-key replication.
- Async warm replicas, config epochs, and rate-limited fallback.
- Operational signals for hit rate, DB fallback, shard skew, evictions, replica
  lag, and config drift.

The remaining issue is visual clarity. The final diagram includes both the
direct client-library path and the optional proxy path. That is acceptable if
the caption is read carefully, but it weakens the diagram as a default design.
Prefer either a default-only final diagram plus option views, or two final
options that let the reader compare "client-library routing" and "proxy
routing" explicitly.

## Concept Introduction and Learning Flow

The concept staging is excellent. The dataset introduces concepts at the moment
they become necessary:

- Local cache limitations motivate a shared cache tier.
- Cache-aside establishes the source-of-truth and fallback contract.
- Consistent hashing solves horizontal growth and topology churn.
- Eviction connects finite memory to hit-rate behavior.
- Consistency handles stale cache entries after DB writes.
- Hot-key handling corrects the uniform-load assumption.
- Failover closes the cold-shard and split-brain scenarios.

The `whyNow`, `recap`, `traps`, and concepts fields do real teaching work. The
only remaining concept-flow weakness is terminology polish around
"read-through" vs "cache-aside" labels.

## Step-to-Final-Design Coherence

The steps build cleanly toward the final design:

- `naive` motivates moving out of process.
- `cache-aside` introduces the read path and DB fallback.
- `sharding` explains horizontal scale and routing.
- `eviction` keeps memory bounded.
- `consistency` handles writes and stale entries.
- `hotkeys` handles skew and stampedes.
- `failover` handles node loss and cold-start protection.

The final design now reflects these steps better than the previous review
version described. Its one coherence issue is not conceptual but visual: it
accumulates both default and optional routing paths in the same diagram.

## Realism Compared With Production Systems

The dataset is realistic on the core cache mechanics. It now covers several
production concerns that weaker cache interviews miss: DB miss budget,
bandwidth, p99 latency, hot-key replication, request coalescing, stale replica
tolerance, config epochs, and split-brain routing.

Remaining realism gaps:

- Backpressure and degradation policy when DB fallback exceeds budget.
- Hot-key detection, replica-count control, and demotion.
- Planned resharding, node warmup, and active/lazy key migration.
- Replica placement across fault domains.
- Security and tenancy basics: namespace isolation, authn/authz, TLS, quotas,
  and value-size limits.
- Technology choices and managed-service trade-offs.

These do not all need full steps. One operations section plus expanded API/data
model cards would cover most of the gap.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Top-level `patterns[*].steps` and `satisfies[*].steps` references resolve to
  real step IDs.
- Step, option, and final-design views use structured `view` objects rather
  than raw Mermaid, matching project conventions.
- High-level link IDs referenced by step, option, and final views resolve.
- Link endpoints used by step, option, and final views are present in those
  views' `nodes`.
- Step highlights resolve to visible nodes.
- The old eviction endpoint mismatch is fixed.
- `a-db` remains in `highLevelArchitecture.links`, but default views no longer
  use it for cache-aside. It is now correctly scoped to read-through/write-back
  variants.
- No `technologyChoices` field is present. That is optional, but this dataset
  is a strong candidate because cache product choices materially affect
  persistence, clustering, replication, client libraries, and operations.
- No `aiVisual`, `aiVisuals`, or `explainerComic` assets are wired. That is not
  a correctness issue.

## Recommended Edits, Prioritized

### P1: Add an operations/backpressure section

Cover DB fallback budget, cache cold-start behavior, rate-limited backfill,
serve-stale eligibility, per-key single-flight limits, hot-shard alerts,
replica lag, epoch drift, and failover/warmup dashboards.

### P1: Extend API and data model fields

Add namespace/tenant scope, `multiGet` or pipelining, TTL/jitter semantics,
optional CAS/version, value-size limits, entry metadata, and ring/config epoch
fields.

### P2: Clarify topology changes and resharding

Describe node add/remove rollout, epoch propagation, lazy refill vs active
warming, token movement throttling, client epoch drift, and replica placement
across fault domains.

### P2: Make the final diagram default-first

Either remove the optional router path from the default final view, use a
visibly optional/dotted style for router links, or add final-design option tabs
for client-library routing vs proxy routing.

### P2: Rename the cache-aside flow and option tabs

Rename "Read-through with hit/miss" to a cache-aside term and add explicit
option titles for the tabbed choices.

### P3: Add technology choices

Include self-hosted and managed choices such as Memcached, Redis Cluster,
Dragonfly, KeyDB, ElastiCache, Memorystore, and Azure Cache for Redis, with
trade-offs around persistence, clustering, replication, failover, and client
library behavior.

## What Not To Change

- Preserve cache-aside as the default. It is the right baseline for a cache in
  front of an authoritative DB.
- Keep the seven-step progression. It is concise and teaches one problem at a
  time.
- Keep read-through, write-through, write-back, proxy routing, and local L1 as
  alternatives rather than forcing them into the default.
- Preserve the new capacity math. It materially improves the interview.
- Preserve the new failover contract around async replication, config epochs,
  and cache-empty correctness.
- Keep the case focused on a cache, not a durable distributed KV store.

## Bottom Line

The recent changes moved this from a good draft to a strong book case. The next
pass should not broaden the architecture much; it should make the production
controls explicit: operations, backpressure, topology changes, concrete
version/epoch metadata, and a default-first final diagram.
