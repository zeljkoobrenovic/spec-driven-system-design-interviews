# Review: URL Shortener - System Design

Reviewed file: `data/book/url-shortener/interview.json`  
Review date: 2026-06-10

## Executive Summary

This is a strong classic-system-design walkthrough. The step order is coherent:
local state, durable storage, stateless scale-out, hot-read caching, ID
generation, sharding, CDN/analytics, and multi-region replication. The case does
well at teaching read-heavy trade-offs, 301 vs. 302 redirect semantics, cache
invalidation, sharding by `short_code`, and active-passive vs. active-active
multi-region choices.

It is close to publish-ready as a book case, but the dataset itself still has a
few important gaps. The biggest design gaps are production abuse controls,
create idempotency and URL normalization, analytics capacity, and a more
explicit final multi-region write model. There are also two concrete
renderer-facing issues in the multi-region sequence diagrams and node metadata.

Overall assessment:

| Dimension | Rating | Notes |
|---|---:|---|
| System design soundness | 4.1 / 5 | The main architecture is credible; abuse, idempotency, analytics sizing, and multi-region write semantics need tightening. |
| Production realism | 3.6 / 5 | Good cache/CDN/sharding coverage, but safety, takedown, queue-loss, replay, and operational workflows are thin. |
| Pedagogical flow | 4.5 / 5 | Clear problem-by-problem buildup with useful option trade-offs and strong 301/302 teaching. |
| Final design coherence | 4.0 / 5 | Final design includes the introduced components, but collapses regional details and does not choose a crisp write model. |
| Dataset/rendering fit | 3.9 / 5 | JSON parses and option views validate; multi-region sequence IDs and a node type need repair. |

Recommendation: keep the overall step sequence. Fix the publication and
generated-doc sync issues first, then add targeted realism around create
safety, analytics, and operations rather than restructuring the case.

## What Works Well

- The capacity section gives the right first-order shape: about 1k creates/sec,
  100k redirects/sec, 100:1 read/write ratio, 7-character base62 codes, and a
  bounded cache working set rather than pretending the cache holds everything.
- The API covers the important user-facing operations: create, redirect,
  metadata fetch, and soft delete.
- The data model includes the core `urls` table, owner listing support,
  append-only click events, and users.
- The step sequence introduces one scaling pressure at a time and connects each
  new component to a visible bottleneck.
- The cache step has useful traps for long-tail cache pollution and stale
  deleted/expired links.
- The CDN/analytics step correctly teaches why 302 is the safer default when
  expiry, deletion, and analytics matter, while 301 is an explicit lower-cost,
  lower-observability mode.
- The sharding step teaches the right shard key: hash `short_code`, not
  `user_id`, because redirects start with the code.
- The multi-region step frames active-passive and active-active as real
  alternatives instead of treating active-active as automatically better.
- `satisfies` is mostly aligned with the steps and gives a readable
  requirement-to-design trace.

## Highest-Impact Issues

### 1. Multi-region sequence diagrams reuse participant IDs for different actors

The step `multi-region` has two flow diagrams with duplicate participant IDs:

- `Create in home region` declares `DB` for both "Region A DB Shard" and
  "Region B DB Shard".
- `Regional failover redirect` declares `B` for both "Region B App" and
  "Region B DB Shard".

Mermaid participants are keyed by ID, so these diagrams can collapse distinct
actors or turn app-to-DB interactions into self-messages. This weakens the most
advanced step in the case.

Concrete fix:

- Use unique IDs such as `DBA` and `DBB`, or `AppB` and `DBB`, in the sequence
  participants and messages.
- Keep aliases only for display labels, not for making two different
  participants share the same canonical ID.
- Rerun a browser/serve check for the multi-region sequence diagrams after the
  change.

### 2. Abuse prevention is treated as a follow-up, but it is core to URL shorteners

The follow-up list asks how to prevent phishing and malware URLs, and how to
rate limit at the edge. That is useful, but for a production URL shortener these
are not optional polish items. Without them, the create path can become an abuse
factory and the redirect path can damage users before operators can intervene.

Concrete fix:

- Add a short abuse/safety slice to either step 2 or step 7: URL validation,
  per-IP/per-user create quotas, domain reputation checks, malware/phishing scan
  state, and blocklist enforcement on redirect.
- Add data fields such as `abuse_status`, `review_status`, `last_scanned_at`,
  `blocked_reason`, and `created_ip_hash` or an equivalent abuse table.
- Add an admin/takedown flow that invalidates cache/CDN entries and changes
  redirect behavior to a warning page or 404/410.
- Keep the deeper anti-abuse system as a follow-up, but make the base design
  acknowledge the safety gate.

### 3. Create semantics need idempotency, canonicalization, and alias ownership

The design handles short-code collisions, but it does not clearly handle client
retry semantics. A mobile client or load balancer retrying `POST /api/v1/shorten`
can create multiple short links for the same user intent unless the API exposes
an idempotency key or deterministic request token.

The API also accepts `longUrl`, `alias`, and `ttlSeconds` without discussing URL
normalization, reserved aliases, ownership of vanity aliases, or validation of
dangerous schemes.

Concrete fix:

- Add `Idempotency-Key` or `requestId` to the create API and store the resolved
  result for a bounded window.
- Normalize and validate the target URL before generating a code. Be explicit
  about allowed schemes, max length, punycode/Unicode handling, and canonical
  host normalization.
- For custom aliases, document reserved words, per-user ownership, release
  policy after deletion/expiry, and whether aliases are globally unique or
  scoped by domain/tenant.
- Add a trap: "only relying on UNIQUE(short_code) solves collisions, not client
  retries."

### 4. Analytics volume is under-modeled relative to the stated traffic

The capacity section estimates mapping storage, cache hot set, and redirect
bandwidth. It does not size click-event ingestion or retention, even though the
architecture adds a click queue and analytics store. At 100k redirects/sec, the
raw click event stream can dominate storage, queue throughput, and processing
cost if retained at full fidelity.

Concrete fix:

- Add a capacity row for click events/sec and daily event volume.
- State a retention policy: raw events for a short window, rolled-up aggregates
  for long-term dashboards, and sampled or privacy-limited dimensions where
  needed.
- Add a data model entry for aggregate counters, for example per-code
  minute/hour/day rollups, since `GET /api/v1/links/{code}` returns `clickCount`
  and the prose mentions near-real-time counters.
- Discuss duplicate click events and replay in the async pipeline, because edge
  logs and queue consumers are usually at-least-once.

### 5. The final design does not choose a crisp multi-region write model

Step 8 teaches active-passive and active-active, but the final design is named a
"Recommended multi-region redirect design" without saying whether creates are
active-passive, active-active, or home-region routed. The final diagram uses
collapsed global nodes (`DB1`, `DB2`, `DB3`, `Rep`) rather than region-specific
app/cache/shard ownership, so the reader has to infer where writes happen and
how a brand-new link becomes visible in another region.

There is also a specific wording issue in the active-passive option:
`appb-replica-lookup-write` labels Region B app traffic to the replica as
`lookup/write`. In active-passive mode, the standby replica should usually serve
reads only until promotion; writes should route to the primary or fail until a
controlled failover.

Concrete fix:

- Make the final recommended write model explicit: for example, "single write
  primary with regional read replicas and home-region fallback on early misses"
  or "active-active generated-code writes with globally reserved custom aliases."
- If active-passive is the recommended default, change Region B replica links to
  read-only and describe promotion.
- If active-active is the recommended default, add the global alias reservation
  service or home-region alias routing to the final design.
- Consider showing two regional cache/shard groups in the final view rather than
  one collapsed shard set.

## System Design Soundness

### Requirements and Capacity

The functional and non-functional requirements are a good fit for a classic URL
shortener. They include optional custom aliases, expiration, analytics, high
redirect availability, low p99 latency, read-heavy traffic, durable mappings,
and eventual analytics.

The capacity math is directionally sound, but incomplete for the components
introduced later. Mapping storage is estimated; click-event storage, queue
throughput, analytics rollups, CDN log ingestion, and purge volume are not. The
bandwidth estimate is plausible for 302 responses, but should mention that bot
traffic and abuse scans can distort both redirect QPS and analytics volume.

### API

The API is practical and teachable. It includes create, redirect, metadata
fetch, and delete. The redirect endpoint correctly defaults to 302 and names 301
as a permanent, less-trackable mode.

Missing production details:

- Create idempotency for retried POSTs.
- Authentication/ownership semantics on create, not only on metadata/delete.
- URL normalization and validation.
- Custom alias reservation and reserved-name policy.
- Explicit response behavior for blocked, expired, deleted, and under-review
  links. The current text mostly collapses these into 404.

### Data Model

The `urls`, `owner_links`, `click_events`, and `users` tables are a good
starting point. `status`, `expires_at`, and `deleted_at` support expiration and
soft delete.

Missing or thin model pieces:

- `redirect_policy` or equivalent to distinguish 301-permanent links from the
  default 302 mode.
- Normalized URL hash and create idempotency state.
- Abuse/review state and takedown metadata.
- Aggregate click counters and rollups.
- Alias ownership/reuse policy.
- Owner index denormalization for status/expiry so management pages do not
  immediately fan out to many shards.

### Architecture

The architecture is credible: stateless app servers, HA load balancing, Redis or
Memcached cache-aside, dedicated ID generation, shard routing, CDN edge
redirects, async analytics, replication, and metrics. The major architectural
gap is not missing infrastructure; it is that a few operational contracts are
only implied: cache purge reliability, queue replay, duplicate analytics events,
regional failover, and abuse enforcement.

## Step-by-Step Pedagogical Review

### Step 1: Client and Server

Good first step. It anchors the product behavior and introduces redirect
semantics before distributed systems. The prototype options are intentionally
weak, which is fine pedagogically.

Suggested improvement: add one sentence that the in-memory version is for
understanding only, not an acceptable first production answer, because successful
creates can disappear.

### Step 2: Add a Database

Strong durability transition. SQL vs. managed KV is a useful option pair, and
the SQL unique constraint explains generated-code and vanity-alias collisions
well.

Suggested improvement: add create idempotency and URL normalization here. This
is the natural place to teach that database uniqueness handles code collisions
but not duplicate client requests or unsafe URLs.

### Step 3: Scale Out with a Load Balancer

Good statelessness and health-check coverage. The DNS round-robin alternative is
useful because its cons teach why a real LB matters.

Suggested improvement: add a small operational note for rate limits or request
admission. URL shorteners need create-side quotas early, before cache/CDN
optimizations.

### Step 4: Add a Cache for Hot URLs

This is one of the strongest steps. It correctly ties read-heavy traffic to a
hot-set cache, includes negative caching, warns about stale deleted/expired
links, and avoids arbitrary "cache 10 percent of all keys" thinking.

Suggested improvement: add cache-stampede mitigation directly to the main path,
not only as a failure-mode note: singleflight/request coalescing, jittered TTLs,
or stale-while-revalidate for very hot keys.

### Step 5: Dedicated ID Generation Service

Good range-allocation vs. Snowflake contrast. The discussion of wasted IDs,
clock rollback, machine ID assignment, and generated-code predictability is
useful.

Suggested improvement: connect generated ID strategy to code enumeration and
abuse. If monotonic IDs are base62-encoded directly, attackers can crawl nearby
codes; scrambling or randomization should be part of the trade-off.

### Step 6: Shard the Mapping Store

Strong shard-key explanation. The step correctly avoids `user_id` as the mapping
shard key and introduces owner indexes and virtual buckets.

Suggested improvement: make the owner/admin read path more concrete. The data
model has `owner_links`, but the step should say whether this index is
synchronously written with the mapping, asynchronously repaired, or allowed to
lag.

### Step 7: CDN, Analytics, and Async Pipeline

Strong conceptual step. It has the right 302/301 distinction and places click
analytics off the redirect critical path.

Suggested improvement: add at-least-once queue semantics. Edge logs and app
servers can emit duplicates; stream processors need event IDs, dedup windows, or
idempotent aggregate updates. Also add backpressure behavior: what happens when
the analytics queue is down or lagging.

### Step 8: Multi-Region Redirects and Replication

The option framing is good, but the diagrams and final recommendation need more
precision. Active-passive should not show standby replica writes, and
active-active needs a concrete alias uniqueness mechanism.

Suggested improvement: use unique participant IDs in the sequence diagrams and
make the chosen default write model explicit before the final design.

## Final Design Review

The final design integrates the main components introduced in the steps:
GeoDNS/CDN, load balancer, stateless app tier, ID generator, cache, shard router,
mapping shards, owner index, queue, analytics store, replication, and metrics.
That is the right component set for the scope.

The weak point is regional specificity. The final design reads like a global
single diagram with a replication node, not a fully explained multi-region
operating model. A candidate using this final design should be able to answer:

- Which region owns a create?
- What happens if a redirect reaches a region before replication catches up?
- Are custom aliases globally reserved synchronously, home-region routed, or
  eventually reconciled?
- During failover, which writes pause and which reads continue?
- How are CDN purges retried and observed?

Add those answers in final design prose or as one final deep-dive note.

## Concept Introduction and Learning Flow

The concept staging is strong. It introduces API contracts and HTTP redirects
first, then durable mapping, unique constraints, horizontal scaling, cache-aside,
TTL, collision avoidance, base62 encoding, sharding, async analytics, edge
caching, replication lag, and active-active.

The main concept gap is security/abuse. A learner can finish the walkthrough
with a strong scaling story but an incomplete product safety story. Add a small
set of concepts such as "URL safety scanning", "takedown propagation", and
"create-side quota" so this does not live only in follow-ups.

## Step-to-Final-Design Coherence

Most steps map cleanly into `finalDesign`:

- `add-database` and `sharded-mapping-store` become `Router`, `DB1`, `DB2`,
  and `DB3`.
- `cache` becomes `Cache` and CDN cache policy.
- `id-generator` becomes `IDGen`.
- `cdn-and-analytics` becomes `CDN`, `Queue`, and `Analytics`.
- `multi-region` becomes `Geo` and `Rep`.
- `load-balancer` becomes `LB` and the stateless `App` tier.

The coherence issue is that the final design does not preserve enough detail
from step 8. It should carry forward the chosen active-passive or active-active
decision rather than only the generic concept of replication.

## Realism Compared With Production Systems

Production URL shorteners are shaped as much by misuse as by load. The current
dataset is strong on load but light on misuse. Real systems need controls for
malware/phishing URLs, spam campaigns, account quotas, link takedowns, redirect
warning pages, domain allow/deny lists, and appeal/audit workflows.

The analytics path also needs production semantics. A queue-based click pipeline
should state whether events are at-least-once, how duplicate events are handled,
what retention is kept in raw form, and what aggregates support owner-facing
dashboards.

Operations are present but compressed into a `Metrics / Alerts` node. For this
case, the most useful SLOs and alerts are redirect p99 latency, CDN hit ratio,
cache hit ratio, cache stampede rate, 404/blocked redirect rate, ID allocation
failures, shard hotness, replication lag, queue lag, purge failures, and abuse
scan backlog.

## Dataset and Renderer-Facing Observations

Validated:

- `interview.json` parses as JSON.
- `_scripts/validate_options.py data/book/url-shortener/interview.json` returns
  `OK`.
- Step option view nodes and link references resolve to
  `highLevelArchitecture`.
- `satisfies[*].steps[*]` values resolve to real step IDs.

Issues:

- `data/book/index.json` includes `url-shortener`; keep the generated
  `docs/book/data/index.json` copy in sync whenever the manifest changes.
- The multi-region flows use duplicate participant IDs for different sequence
  actors, as described above.
- `highLevelArchitecture.nodes[]` has `AppA` labeled "Region A Apps" with type
  `database`; it should be `service`.
- `Clock` is labeled "Clock Sync" with type `database`. If it represents clock
  synchronization infrastructure, `external`, `service`, or a more explicit
  "time sync service" label would be clearer than rendering it as a database.
- The active-passive link `appb-replica-lookup-write` should not say
  `lookup/write` unless Region B has been promoted or the design is not really
  active-passive.
- `technologyChoices` is absent. That is optional, but for a book case this
  would be a good addition covering mapping store, cache, CDN/edge compute, ID
  generation, queue/stream, analytics store, observability, and abuse scanning.

## Recommended Edits, Prioritized

### P1: Make the case reachable and render correctly

- Fix duplicate sequence participant IDs in the multi-region flows.
- Change `AppA.type` from `database` to `service`.
- Rename or retype `Clock` so Snowflake clock coordination does not render like
  an authoritative data store.
- Keep the source and generated book manifests in sync after edits.

### P1: Add create-path correctness and safety

- Add idempotency to `POST /api/v1/shorten`.
- Add URL normalization and validation.
- Add custom-alias ownership/reservation rules.
- Add basic anti-abuse controls: quotas, safety scan state, blocklists, and
  takedown/cache-purge flow.

### P2: Tighten analytics realism

- Add click-event capacity math.
- Add raw-event retention and aggregate-counter storage.
- State duplicate/replay handling for queue consumers.
- Define backpressure behavior when analytics ingestion is degraded.

### P2: Make multi-region writes explicit

- Pick the recommended write model in `finalDesign`.
- If active-passive, make standby writes read-only until promotion.
- If active-active, add global alias reservation or home-region alias routing.
- Describe early-miss routing during replication lag.

### P3: Add operations and implementation choices

- Add a metrics/runbook deep dive.
- Add `technologyChoices` for the major implementation concerns.
- Add a few traps beyond cache, especially for idempotency, abuse, analytics
  duplicates, and active-active custom aliases.

## What Not To Change

- Keep the current step order. It is a good teaching progression.
- Keep the SQL vs. managed KV option pair in step 2 and step 6; it teaches the
  right trade-off at two maturity levels.
- Keep 302 as the default redirect mode and 301 as an explicit permanent-link
  option.
- Keep sharding by `short_code`; the owner index should stay separate.
- Keep analytics off the hot redirect path.

## Bottom Line

This is a strong foundation for a book-quality URL shortener case. The core
scaling arc works. The remaining work is to repair the multi-region rendering
issues and add the production contracts that make real URL shorteners hard:
abuse controls, idempotent creates, analytics replay/retention, and an explicit
regional write model.
