# Review: Reusable Design Patterns - Catalog

Reviewed file: `data/book/patterns/interview.json`
Review date: 2026-06-09

## Executive Summary

This dataset is a valid standalone catalog: it has no `steps[]`, but the
non-empty `patternCatalog[]` makes it legal for the current renderer. The 22
patterns are clear, compact, and grouped around the right core distributed
systems vocabulary: partitioning, replication, caching, queues, outbox, sagas,
idempotency, deduplication, ledgers, reconciliation, leases, fairness, and
provider adapters.

The main gap is that the catalog is now behind the breadth of the book. The
book datasets already use many recurring patterns that are not represented or
are represented under different names. Since this page is meant to define the
shared vocabulary, drift between catalog names, step-level `patterns` tags, and
`usedBy` chips is the highest-impact issue.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 3.8/5 | Strong definitions for core patterns, but several production families are missing. |
| Production realism | 3.7/5 | Good trade-off summaries; weak on operational signals, failure handling recipes, and when not to use each pattern. |
| Pedagogical flow | 3.9/5 | Easy to scan, but not yet strong enough as the book's canonical vocabulary. |
| Dataset/rendering fit | 4.4/5 | JSON parses; catalog-only shape is supported; empty architecture object is harmless but not informative. |
| Overall | 3.9/5 | A useful seed catalog that needs normalization and broader coverage to serve as a book reference. |

## What Works Well

- The catalog is concise. Each card has a name, category, definition, use case,
  trade-off, and `usedBy` examples, which matches what the renderer displays.
- Categories are understandable and mostly balanced: scaling, read/write
  optimization, messaging, correctness, protection, specialized indexing, and
  integration.
- The definitions avoid common overselling. For example, the outbox entry says
  events are still at-least-once and consumers dedupe; the DLQ entry says it
  needs monitoring and replay; the lease entry explicitly names fencing tokens.
- The catalog covers the strongest reference cases in the current project:
  Payment System, Notification System, Key-Value Store, Distributed Cache, Rate
  Limiter, Web Crawler, News Feed System, and Real-Time Gaming Leaderboard.
- `toProbeFurther` contains credible foundational links for distributed data,
  queues/streams, overload, monitoring, and authorization.

## Highest-Impact Issues

### 1. Catalog names drift from step-level pattern tags

The catalog is supposed to define shared vocabulary, but many local datasets use
near-equivalent names that will not match this catalog by eye or by future
machine linking. Examples from current book datasets include:

- `Horizontal sharding (partitioning)` vs. `Sharding by key`,
  `Partitioning by key`, and `Document partitioning (sharding)`.
- `Deduplication` vs. `Dedup store`, `Dedupe store`, and
  `Idempotent dedup`.
- `Quorum reads/writes` vs. `Quorum consistency (N/W/R)`.
- `Leases & fencing tokens` vs. `Fencing token`,
  `Leader election + fencing`, and `Lease with TTL`.
- `Sharded / priority queues` vs. `Sharded queues` and `Priority queue`.
- `Geo-indexing` vs. `Geo-indexing (geohash / S2)` and
  `Geospatial indexing`.

Why it matters: the catalog currently renders `usedBy` as plain chips, not
links. If names are not canonical, readers cannot reliably connect a case's
pattern tags back to the catalog, and future linkification will need aliases.

Concrete fix:

- Give each catalog pattern a stable canonical name and normalize common
  `step.patterns[]` values to that name.
- If preserving local wording is important, add an `aliases` field and teach
  the renderer/search layer to use it later.
- Start with the most repeated local tags: `Idempotency key`,
  `Transactional outbox`, `Synchronous request/response`, `Work queue`,
  `Order state machine`, `Saga / state machine`, `Load shedding / admission
  control`, `Optimistic concurrency control`, and `Dead-letter queue`.

### 2. Coverage is narrow compared with the book manifest

The catalog has 22 entries, but the `book` group now spans messaging, social
feeds, financial systems, booking, marketplaces, ML platforms, storage,
observability, search, media, commerce, auth, and delivery pipelines. Many
reusable patterns that appear across those families are absent.

High-value missing families:

- Request and edge patterns: synchronous request/response, API gateway,
  CDN/edge caching, load balancing, persistent connections, SSE/WebSocket.
- Contention and correctness patterns: optimistic concurrency/CAS, distributed
  locks, inventory holds, virtual waiting rooms, consistency tokens.
- Operational resilience: load shedding/admission control, circuit breakers,
  retry with backoff, health-aware failover, graceful degradation.
- Derived data: CDC/change streams, rebuildable projections, backfills,
  rollups/downsampling, tombstones, source-version ordering.
- Security and identity: RBAC/ABAC, ReBAC, OAuth/OIDC, token revocation,
  permission-scoped search.
- Search and ML: inverted indexes, vector indexes, candidate generation,
  two-stage ranking, feature store online/offline parity.
- Media and object storage: multipart upload, content-addressed chunking,
  metadata/blob split, erasure coding, segmented media, adaptive bitrate.

Why it matters: a reference catalog that omits these families will feel anchored
to the first payment/notification/storage examples rather than to the whole
book.

Concrete fix:

- Add a second expansion pass driven by repeated `step.patterns[]` across
  `data/book/*/interview.json`.
- Prioritize patterns used by three or more datasets, then add domain-specific
  anchor patterns for large book families such as auth, media, search, ML,
  observability, commerce, and booking.
- Keep the current concise card format, but broaden the vocabulary.

### 3. Each pattern needs one more layer of practical guidance

The current card fields are good for vocabulary lookup, but not enough for a
candidate to apply the pattern in an interview. Most entries stop at "what",
"when", and one trade-off. They rarely say what state must be stored, what API
contract changes, what metrics to watch, or what failure mode to name.

Examples:

- `Idempotency key` should mention response replay, dedup key scope, TTL/window,
  and in-flight duplicate handling.
- `Transactional outbox` should mention relay ordering, polling vs. CDC,
  cleanup, and consumer idempotency.
- `Backpressure` should distinguish bounded queueing, admission control, load
  shedding, priority isolation, and downstream rate limits.
- `Reconciliation` should name authoritative source, matching keys, correction
  records, audit trail, and operator workflow.
- `Leases & fencing tokens` should say the resource must reject stale tokens;
  a lease alone is not enough.

Why it matters: the catalog's value is not just definitions; it should help
readers remember the "production gotcha" that makes each pattern interview
worthy.

Concrete fix:

- Add a short "implementation checklist" concept for each pattern, either as a
  new rendered field or as a sentence inside `what`/`tradeoffs`.
- Add "failure mode to name" to at least the correctness, queueing, and
  integration patterns.
- Keep entries compact; one extra sentence per pattern is enough.

### 4. `usedBy` is useful but should become linkable and more complete

The `usedBy` chips are currently plain strings. They mix examples-group cases
such as `Key-Value Store`, `URL Shortener`, and `Hotel Reservation System` with
book-group cases such as `Payment System`, `Notification System`, and
`Distributed Cache`. That is understandable, but it is not machine-checkable
and it does not reflect many newer book cases.

Why it matters: this catalog should be the map from vocabulary to examples. A
plain string chip is easy to stale, cannot link to the case, and cannot point to
the exact step where the pattern is used.

Concrete fix:

- Consider changing `usedBy` from strings to objects such as
  `{ group, datasetId, label, steps }`, while keeping backward compatibility
  with strings in the renderer.
- Add examples from newer book datasets: Wallet / Ledger for double-entry and
  reconciliation, Message Queue for queue/DLQ/backpressure, Object Storage for
  replication and erasure-style storage patterns, Authorization for authZ
  patterns after they are added, and Metrics & Monitoring for rollups and
  admission control after those entries exist.
- If schema expansion is too much for now, at least normalize display names to
  the manifest names and add the most relevant book cases.

### 5. Further-reading links are broader than the catalog itself

The current `toProbeFurther` links include Zanzibar and Prometheus, but the
catalog has no authorization pattern and no observability pattern beyond a
general monitoring reference. The references are credible, but they expose
coverage gaps.

Why it matters: readers may expect every major reading group to correspond to
a pattern category. Today, the links point toward topics the catalog does not
teach.

Concrete fix:

- Either add catalog entries for authorization and observability patterns, or
  move those links into a more general "foundational references" framing.
- Add one or two pattern-specific references after expanding the catalog, for
  example Kafka consumer groups/offsets for queueing, OpenTelemetry/Prometheus
  docs for metrics, and OAuth/OIDC or Zanzibar references for auth.

## System Design Soundness

For the patterns it includes, the catalog is generally sound. It names the
important trade-offs: shard key choice, replica lag, cache invalidation,
projection lag, write amplification, at-least-once delivery, compensation
complexity, DLQ operations, dedup windows, append-only ledgers, drift repair,
clock/pause hazards, and provider-specific leaks.

The weakness is not incorrectness; it is incompleteness. A catalog for a broad
system design book should also cover request routing, consistency coordination,
release/migration safety, auth, observability, search, ML serving, media
delivery, and object storage patterns. Those families already exist elsewhere
in the project, so their absence makes this catalog feel like an early core
distributed-systems subset.

## Step-by-Step Pedagogical Review

This dataset intentionally has no walkthrough steps. That is valid for a
`patternCatalog`-only reference dataset.

The pedagogical unit is therefore the card. The card shape is good for recall,
but not yet for application. A reader can learn what a pattern means, but they
do not consistently learn the interview move: which requirement triggers it,
which component it adds, what state it stores, which failure mode it prevents,
and what trade-off they must acknowledge.

## Final Design Review

There is no `finalDesign`, which is appropriate for a catalog. The empty
`highLevelArchitecture` object exists because the dataset validator requires
`nodes`, `links`, and `types`; this is harmless and should not be expanded into
a fake architecture diagram.

If the renderer eventually supports a catalog concept map, this dataset would
benefit from a small derived diagram that groups patterns by relationship:
outbox -> queue -> dedup -> DLQ, sharding -> replication -> quorum, cache ->
read model -> indexing, lease -> fencing -> single writer. Do not hand-author a
fake system architecture for that purpose.

## Concept Introduction and Learning Flow

The category order works reasonably well: data distribution first, then
read/write optimization, async messaging, correctness, fairness, specialized
indexing, and integration. That said, several patterns compose tightly and
would teach better with explicit relationships:

- Outbox, work queue, idempotency, deduplication, retry, and DLQ form one
  reliability pipeline.
- Sharding, consistent hashing, replication, quorum, hinted handoff, and
  anti-entropy form one distributed storage cluster vocabulary.
- Cache-aside, read models, indexing, invalidation, rebuilds, and freshness
  form one derived-read-path vocabulary.
- Leases, fencing, leader election, CAS, and distributed locks form one
  coordination vocabulary.

Adding lightweight "pairs well with" or "commonly confused with" guidance would
make the catalog more useful without turning it into a full tutorial.

## Step-to-Final-Design Coherence

Not applicable as a walkthrough. For a catalog, the equivalent coherence check
is "do case-study pattern tags map back to catalog entries?" Today the answer
is only partially. Several exact names match, but many local case tags use
synonyms, narrower variants, or domain-specific names that do not resolve to a
catalog entry.

## Realism Compared With Production Systems

The included trade-offs are realistic but compressed. Production versions of
these patterns usually require naming the operational contract:

- What is the durable source of truth?
- What is the idempotency or ordering key?
- What retries are safe, and for how long?
- What queue depth, lag, DLQ count, or error budget pages an operator?
- What data can be rebuilt, and from which log or authoritative source?
- What happens during deploys, schema changes, regional failover, or provider
  outages?

The catalog does not need long answers, but each pattern should include one
production hook that prevents it from reading like a glossary-only definition.

## Dataset and Renderer-Facing Observations

- `data/book/patterns/interview.json` parses as valid JSON.
- The dataset has top-level keys `assets`, `description`, `followUps`,
  `highLevelArchitecture`, `patternCatalog`, `title`, and `toProbeFurther`.
- The catalog has 22 entries across seven categories.
- The dataset has no `steps[]`, `requirements`, `capacity`, `api`,
  `dataModel`, `satisfies`, `interviewScript`, `levelVariants`, or
  `finalDesign`. This is valid because `patternCatalog[]` is non-empty.
- `highLevelArchitecture` is an empty `{ nodes: [], links: [], types: [] }`
  object. The validator accepts it and no step/final-design view references are
  present.
- `patternCatalog` cards use only fields the renderer currently displays:
  `name`, `category`, `what`, `whenToUse`, `tradeoffs`, and `usedBy`.
- There is no docs rebuild required for this review file alone.

## Recommended Edits, Prioritized

### P1: Normalize the vocabulary

Canonicalize catalog names against current `step.patterns[]` tags, or add an
alias mechanism. Start with sharding, dedup, quorum, leases/fencing, sharded
queues, geo-indexing, state machines, and load shedding.

### P1: Expand coverage based on repeated local usage

Add entries for the most repeated or strategically important missing patterns:
synchronous request/response, load shedding/admission control, retry with
backoff, circuit breaker, optimistic concurrency/CAS, distributed locks,
CDC/change streams, rebuildable projections, CDN/edge caching, RBAC/ABAC,
ReBAC, OAuth/OIDC, inverted index, vector index, rollups/downsampling, and
adaptive media delivery.

### P2: Add practical application guidance

For each existing pattern, add one implementation hook and one named failure
mode. Keep entries short, but make them interview-actionable.

### P2: Make `usedBy` linkable

Move from plain strings to optional structured references with dataset ids and
step ids, while keeping the current string format valid for old entries.

### P3: Align further reading with catalog categories

After adding auth and observability patterns, keep Zanzibar and Prometheus as
category-relevant links. Otherwise, label the current links as general
foundational references.

## What Not To Change

- Keep the catalog concise. It should remain a quick vocabulary reference, not
  a second copy of every case study.
- Keep the category grouping; expand it rather than replacing it.
- Do not add a fake `steps[]` walkthrough just to make the dataset look like a
  normal interview.
- Do not create a synthetic architecture diagram unless the renderer gains a
  true concept-map view for catalog datasets.

## Bottom Line

This is a clean and useful starting catalog. To become the book's real pattern
reference, it needs canonical naming, broader coverage from the existing book
cases, and one practical production hook per pattern.
