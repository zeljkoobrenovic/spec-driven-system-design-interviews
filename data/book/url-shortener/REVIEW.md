# Review: URL Shortener - System Design

Reviewed file: `data/book/url-shortener/interview.json`  
Review date: 2026-06-10

## Executive Summary

This review reflects the current dataset after the recent URL-shortener updates.
Several earlier high-impact findings have been addressed: create idempotency and
URL normalization are now in the API, the data model includes idempotency,
abuse, redirect-policy, and click-rollup fields, click-event capacity is sized,
analytics traps cover duplicate/replayed events, the multi-region sequence
participant IDs are unique, and the incorrect node types have been fixed.

The case is now a strong book-quality walkthrough. The remaining work is mostly
about making newly introduced production contracts visible everywhere they
matter: the active-active write model needs matching data fields and diagram
components, the safety gate needs API/operational semantics, and analytics/cache
degradation behavior should be explicit enough for an interview candidate to
defend under follow-up questions.

Overall assessment:

| Dimension | Rating | Notes |
|---|---:|---|
| System design soundness | 4.4 / 5 | The core architecture is credible and now covers idempotency, abuse state, analytics sizing, and a clearer regional write model. |
| Production realism | 4.1 / 5 | Much stronger than before; remaining gaps are safety workflow semantics, queue/backpressure behavior, cache stampede handling, and owner-index consistency. |
| Pedagogical flow | 4.6 / 5 | Excellent step progression with concrete trade-offs; a few advanced contracts need to be staged more visibly. |
| Final design coherence | 4.3 / 5 | The final prose chooses active-active generated-code writes plus global alias ownership, but the final diagram/data model do not fully carry that choice. |
| Dataset/rendering fit | 4.8 / 5 | JSON and structured views validate cleanly; no duplicate sequence participants or unresolved step references were found. |

Recommendation: keep the step sequence and recent fixes. Make a targeted pass
over final-design artifacts, safety semantics, and operational failure modes
rather than restructuring the interview.

## What Works Well

- The capacity section now includes click-event throughput and storage impact:
  about 100k events/sec, about 8.6B/day, raw retention of 7-30 days, and
  rollups for long-term dashboards.
- `POST /api/v1/shorten` now covers auth, URL normalization/validation, an
  `Idempotency-Key`, and useful error codes for unsafe URLs, reserved aliases,
  and quota exhaustion.
- The data model is substantially more production-ready: `idempotency_keys`,
  `redirect_policy`, URL hash, abuse fields, blocked reasons, created IP hash,
  and click rollups are all present.
- The step order remains strong: client/server, durable storage, stateless
  scale-out, cache, ID generation, sharding, edge/analytics, and multi-region.
- The cache, database, and analytics steps now have realistic traps instead of
  only happy-path descriptions.
- The final design now states a concrete default: active-active writes for
  generated codes and single-owner/global reservation for custom aliases.
- The renderer-facing issues called out in the previous review appear resolved:
  sequence participant IDs are unique, `AppA` is typed as `service`, and
  `Clock` is no longer rendered as a database.

## Highest-Impact Issues

### 1. The active-active final design needs matching data-model and diagram support

The final prose says generated codes are active-active, custom aliases are
globally reserved or home-region routed, and early misses during replication lag
fall back to the link's home region. That is the right direction, but the
structured artifacts do not fully model it.

Current gaps:

- `urls` does not store `home_region`, `region_id`, `code_source`, or an
  equivalent owner-region marker.
- There is no `alias_reservations` table or final-design node for the
  strongly-consistent custom-alias namespace.
- The create API response does not include `homeRegion`, even though the
  multi-region create flow returns it.
- The final diagram is still a collapsed global stack, so the reader cannot see
  regional ownership, alias reservation, or early-miss home-region fallback.

Concrete fix: add the missing fields/table, add an `Alias Reservation` or
`Home Region Router` component to the final view, and align the create API
response with the multi-region flow. If the final diagram stays collapsed, add a
short final-design deep-dive note that names these contracts explicitly.

### 2. Abuse controls exist, but the user-visible safety contract is under-specified

The data model now has `status`, `abuse_status`, `last_scanned_at`,
`blocked_reason`, and `created_ip_hash`, and step 7 includes a takedown flow.
That is a major improvement. The remaining gap is that the product/API behavior
for unsafe links is still not crisp.

Current gaps:

- `GET /{code}` still says unknown/expired/deleted links return 404, but does
  not define behavior for `blocked` or `under_review`.
- The takedown flow uses `POST /admin/block`, but that API is not listed in the
  API section.
- Cache/CDN purge retry is named in the final prose, but there is no durable
  purge job, outbox, or acknowledgement model in the data model.
- Abuse is still not promoted into the requirements list, even though the design
  now contains safety mechanisms.

Concrete fix: add a safety requirement, define redirect responses for blocked
and under-review links (for example warning page, 410, or 451 depending on
policy), add an admin/scanner API or describe it as internal, and model purge
retry state if takedown propagation is part of the design.

### 3. Redirect policy is modeled, but clients cannot set it

The dataset correctly teaches the 302 vs. 301 trade-off, and `urls` now has a
`redirect_policy` field. However, `POST /api/v1/shorten` accepts only
`longUrl`, optional `alias`, and optional `ttlSeconds`. A candidate reading the
API cannot tell how a permanent 301 link is requested, which constraints apply,
or whether 301 is only an operator-side policy.

Concrete fix: add a request field such as `redirectPolicy?: "temporary" |
"permanent"` or `permanent?: boolean`. State that permanent links cannot have a
short TTL, are poor fits for editable vanity links, and make analytics
approximate because browsers may never return to the edge/origin.

### 4. Analytics and cache degradation behavior should be explicit

The analytics capacity and duplicate-event traps are good. The remaining
production question is what the redirect path does when the click queue,
analytics consumer, or rollup store is degraded. The step currently says
analytics can drop during queue outages, but does not choose a behavior.

Concrete fix: add a small operational note or trap that says redirects never
block on analytics; edge/origin either buffer briefly, drop/sampling-mark events
under pressure, or write to a durable local/outbox stream. Also add cache
stampede mitigation to step 4: request coalescing/singleflight, jittered TTLs,
or stale-while-revalidate for extremely hot codes.

### 5. Secondary consistency details need one more pass

Two secondary indexes are now important enough to define more tightly:

- `idempotency_keys` is keyed by `idempotency_key`, but the note says the key is
  per user/request. In practice this should be `(user_id, idempotency_key)` plus
  a request hash so a repeated key with a different body returns an idempotency
  conflict.
- `owner_links` supports dashboards, but the write path does not say whether it
  is updated synchronously with the mapping, updated from a change stream, or
  asynchronously repaired.

Concrete fix: tighten the table definitions and add one sentence in steps 2/6
about the consistency contract for each index.

## System Design Soundness

### Requirements and Capacity

The requirements and capacity are now strong for the classic URL-shortener
scope. The click-event row is especially valuable because it prevents the
analytics pipeline from looking free next to the mapping store.

The main missing requirement is safety/abuse. Since the design now includes
abuse state, scanner/admin flows, and redirect blocking, safety should be a
first-class functional or non-functional requirement instead of only a follow-up
question.

### API

The public API is much more credible after adding auth, idempotency, URL
validation, quota errors, and alias-reservation errors. The remaining API gaps
are concentrated around policies introduced elsewhere:

- Add how clients request 301 vs. 302 behavior.
- Add blocked/under-review redirect semantics.
- Add or explicitly mark the admin/scanner block endpoint as internal.
- Include `homeRegion` or equivalent metadata if early-miss fallback is part of
  the multi-region contract.

### Data Model

The model now supports the promised behavior better than before. `urls`,
`idempotency_keys`, `click_counters`, `owner_links`, `click_events`, and `users`
cover the core read/write/analytics paths.

The next useful additions are not broad new tables; they are targeted
contract fields: home-region ownership, alias reservation state, purge retry
state, scoped idempotency keys, and request hashes for idempotency replay.

### Architecture

The architecture is credible: stateless app servers, HA load balancing, Redis or
Memcached cache-aside, dedicated ID generation, shard routing, CDN edge
redirects, async analytics, replication, and observability. The final design now
has a defensible multi-region choice. It should make that choice visible in the
diagram and in table/API contracts so the learner can answer follow-up questions
without relying on prose alone.

## Step-by-Step Pedagogical Review

### Step 1: Client and Server

Good opening step. It keeps the first architecture intentionally small while
anchoring create and redirect behavior. The in-memory and local-store options
are weak by design, and their limitations are clear.

Suggested improvement: no structural change needed.

### Step 2: Add a Database

This step is now much stronger. The SQL/KV comparison is useful, and the traps
for idempotency and URL normalization are exactly the right corrections.

Suggested improvement: tie the `idempotency_keys` table to `(user_id,
idempotency_key, request_hash)` so the trap has a complete implementation
answer.

### Step 3: Scale Out with a Load Balancer

The statelessness and health-check story is good. Adding create-side quota and
safety-gate concepts improves production realism.

Suggested improvement: show where create-side quotas are enforced in the request
path, even if it is just a sentence naming edge/LB/app admission control.

### Step 4: Add a Cache for Hot URLs

Still one of the strongest teaching steps. It explains cache-aside, TTLs,
negative caching, and stale deleted/expired links without overcomplicating the
first cache pass.

Suggested improvement: add cache-stampede mitigation for very hot codes:
singleflight/request coalescing, jittered TTLs, or stale-while-revalidate.

### Step 5: Dedicated ID Generation Service

The range-allocation vs. Snowflake contrast is clear and useful. The current
range-allocation cons mention predictable codes, which is the right caveat.

Suggested improvement: make the mitigation explicit: scramble encoded IDs,
reserve random-looking code space, or use non-sequential generated codes when
enumeration risk matters.

### Step 6: Shard the Mapping Store

Good shard-key explanation. The step correctly chooses `short_code`, not
`user_id`, because redirects start with the code.

Suggested improvement: define owner-index consistency. If dashboards can lag,
say so; if the owner index is written in the same transaction or via an outbox,
say that instead.

### Step 7: CDN, Analytics, and Async Pipeline

This step now teaches the right 302/301 distinction, includes a takedown flow,
and has good traps for at-least-once analytics and raw-event retention.

Suggested improvement: define analytics backpressure behavior. Redirects should
not fail because click logging is degraded, but the design should say whether it
buffers, samples, drops with counters, or writes an outbox.

### Step 8: Multi-Region Redirects and Replication

This step improved substantially. Active-passive now reads as read-only standby
until promotion, active-active names region-scoped ID prefixes, and the sequence
diagrams no longer reuse participant IDs.

Suggested improvement: connect the active-active choice to concrete data and
control-plane artifacts: home region, alias reservation, early-miss fallback,
and promotion/failover behavior.

## Final Design Review

The final design now integrates the main components introduced in the steps:
GeoDNS/CDN, load balancer, stateless app tier, ID generator, cache, shard
router, mapping shards, owner index, queue, analytics store, replication, and
metrics.

The biggest improvement is that the final prose chooses a write model instead
of leaving active-passive vs. active-active ambiguous. The remaining weakness is
representation: the final view does not show the regional ownership contracts
that the prose relies on. Add a global alias reservation component, home-region
metadata/fallback, or region-specific cache/app/shard groups if the final
diagram is meant to be the candidate's last drawing.

## Concept Introduction and Learning Flow

Concept staging is strong. The walkthrough introduces API contracts and HTTP
redirects first, then durable mapping, uniqueness, horizontal scale, cache-aside,
TTL, collision avoidance, base62 encoding, sharding, async analytics, edge
caching, replication lag, and active-active trade-offs.

The safety concepts were added in a reasonable place, but they should now be
connected to requirements and API behavior. That will make abuse prevention feel
like part of the base design instead of an attached note.

## Step-to-Final-Design Coherence

Most steps map cleanly into `finalDesign`:

- `add-database` and `sharded-mapping-store` become `Router`, `DB1`, `DB2`,
  and `DB3`.
- `cache` becomes `Cache` and the CDN/cache policy.
- `id-generator` becomes `IDGen`.
- `cdn-and-analytics` becomes `CDN`, `Queue`, and `Analytics`.
- `multi-region` becomes `Geo` and `Rep`.
- `load-balancer` becomes `LB` and the stateless `App` tier.

The coherence issue is that some new step-level contracts do not have final
design counterparts: alias reservation, home-region fallback, purge retry, and
analytics rollup/dedup workers.

## Realism Compared With Production Systems

The dataset now acknowledges the two hard production realities that many URL
shortener designs skip: misuse and analytics volume. That is a meaningful
quality jump.

The next realism improvements are operational rather than architectural:
define purge retries and auditability for takedowns, state what happens when
analytics is down, include cache-stampede protection, and add privacy limits for
click analytics fields such as IP hash, referrer, and user agent. The existing
retention note is a good start; a short privacy note would make it stronger.

## Dataset and Renderer-Facing Observations

Validated:

- `interview.json` parses as JSON.
- `_scripts/validate_options.py data/book/url-shortener/interview.json` returns
  `OK`.
- Step and final-design option view nodes resolve to `highLevelArchitecture`.
- Step and final-design option view links resolve to `highLevelArchitecture`.
- `satisfies[*].steps[*]` values resolve to real step IDs.
- Step and API sequence diagrams have no duplicate participant IDs.
- The previous node-type issues for `AppA` and `Clock` are fixed.

Observations:

- `technologyChoices` is absent. That is optional, but this book case is now
  mature enough to benefit from choices for mapping store, cache, CDN/edge
  compute, ID generation, queue/stream, analytics store, observability, abuse
  scanning, and global alias reservation.
- No `docs/` rebuild is needed for this review-only file. If the dataset itself
  changes later, rebuild `docs/book/`.

## Recommended Edits, Prioritized

### P1: Carry the active-active write model into the artifacts

- Add home-region/region-source fields to `urls`.
- Add a global alias reservation table or component.
- Include `homeRegion` or equivalent in the create response if early-miss
  fallback depends on it.
- Add alias reservation and home-region fallback to the final design view or a
  final-design deep dive.

### P1: Make safety behavior explicit

- Add a safety/abuse requirement.
- Define redirect behavior for `blocked` and `under_review`.
- Add or mark the admin/scanner block endpoint as internal.
- Model or describe durable CDN/cache purge retries for takedowns.

### P2: Expose redirect policy in the API

- Add a create-request field for temporary vs. permanent redirects.
- Document constraints for 301 links: no short TTL, hard deletion semantics, and
  approximate analytics.

### P2: Tighten operational degradation paths

- Define analytics queue/backpressure behavior.
- Add cache-stampede mitigation to the cache step.
- Scope idempotency keys by user and request hash.
- State owner-index consistency and repair behavior.

### P3: Add implementation choices

- Add `technologyChoices` for the major implementation concerns.
- Include managed-vs-self-hosted trade-offs for Redis/Memcached, SQL/KV,
  Kafka/Pub/Sub/Kinesis, CDN/edge compute, analytics store, observability, and
  abuse scanning.

## What Not To Change

- Keep the current step order. It remains a clean teaching progression.
- Keep 302 as the default redirect mode and 301 as an explicit permanent-link
  option.
- Keep sharding by `short_code`; the owner index should stay separate.
- Keep analytics off the hot redirect path.
- Keep the active-passive vs. active-active comparison in step 8, even if the
  final recommendation favors active-active generated-code writes.

## Bottom Line

The URL shortener case is now substantially stronger than the earlier review
version. It is publishable as a classic scaling walkthrough, with the remaining
work concentrated in a few high-value production contracts: active-active
metadata, safety behavior, redirect-policy exposure, and degraded-mode
operations.
