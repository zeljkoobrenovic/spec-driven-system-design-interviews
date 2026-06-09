# Review: Reusable Design Patterns - Catalog

Reviewed file: `data/book/patterns/interview.json`
Review date: 2026-06-09

## Executive Summary

The catalog has been materially improved since the previous review. It is still
a valid standalone `patternCatalog[]` dataset with no `steps[]`, and it now
contains 49 patterns across 9 categories. The expansion addresses the earlier
largest gap: request/edge patterns, security and identity, search/ML indexes,
media/object-storage patterns, retry/circuit-breaker/backpressure, and
operationally important "failure mode to name" guidance are now present.

The remaining issues are less about breadth and more about consistency and
navigability. Exact names in `patternCatalog[].name` still diverge from many
current `step.patterns[]` tags, `usedBy` remains free text, and several repeated
case-study patterns are still either missing or hidden as variants of broader
entries. As the book grows, this catalog should become a canonical vocabulary,
not just a strong glossary.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.4/5 | Definitions are production-aware and usually name the right failure mode. |
| Production realism | 4.3/5 | Strong operational caveats; a few high-frequency case patterns still deserve first-class entries or aliases. |
| Pedagogical flow | 4.2/5 | Cards are scan-friendly and grouped well; cross-pattern relationships are only in follow-ups. |
| Dataset/rendering fit | 4.5/5 | JSON parses; catalog-only shape and grouped links are valid; `category`/`group` duplication is harmless but noisy. |
| Overall | 4.3/5 | A strong reference catalog that now needs canonicalization and linkable usage metadata. |

## What Works Well

- The catalog now covers the book's major reusable families: distribution,
  caching/read models, messaging, correctness, protection/fairness, specialized
  indexes, edge/integration, security/identity, and media/object storage.
- Each pattern has an actionable production warning. All 49 entries include
  "Failure mode to name" guidance, which makes the catalog much more useful for
  interview preparation than a pure definition list.
- The expansion added previously missing anchor patterns such as CDC/change
  streams, retry with backoff and jitter, circuit breaker, API gateway,
  CDN/edge caching, RBAC/ABAC, ReBAC, OAuth/OIDC, inverted indexes, vector
  indexes, time-series rollups, multipart upload, erasure coding, and adaptive
  bitrate streaming.
- The `toProbeFurther` field now uses the grouped link shape with 11 links
  across foundations, distributed data, queues/streams, security, and
  observability. That matches the renderer's grouped reading-list support.
- The catalog-only dataset remains intentionally simple: no fake `steps[]`, no
  fake final design, and an empty `highLevelArchitecture` object that satisfies
  validation without pretending there is one architecture to draw.

## Highest-Impact Issues

### 1. Exact pattern names still drift from case-study tags

The catalog includes many aliases in prose, but current book datasets still use
many `step.patterns[]` names that do not exactly match the catalog. Examples:

- Catalog: `Horizontal sharding (partitioning)`; tags include `Sharding by key`,
  `Partitioning by key`, `Document partitioning (sharding)`, and `Sharding by
  series`.
- Catalog: `Deduplication`; tags include `Dedup store`, `Dedupe store`,
  `Idempotent dedup`, and `Merchant webhook dedup`.
- Catalog: `Optimistic concurrency control (CAS)`; tags include `Optimistic
  concurrency`, `Optimistic concurrency (CAS)`, `Distributed lock / CAS`, and
  `Idempotency + optimistic concurrency`.
- Catalog: `Leases & fencing tokens`; tags include `Fencing token`, `Lease with
  TTL`, `Session lease (heartbeat TTL)`, and `Leader election + fencing`.
- Catalog: `Saga / state machine`; tags include `Saga with compensation`,
  `Saga / compensation`, `Order state machine`, `Charge state machine`, and
  `Pipeline state machine`.

Why it matters: this page is meant to define the shared vocabulary for the
book. If exact names do not line up, future linkification/search will either
miss valid references or need a growing pile of one-off heuristics.

Concrete fix:

- Add an explicit `aliases` array to catalog entries, or normalize the most
  common `step.patterns[]` tags to canonical catalog names.
- Start with the highest-frequency tags: `Idempotency key`, `Synchronous
  request/response`, `Transactional outbox`, `Work queue`, `Order state
  machine`, `Saga with compensation`, `Optimistic concurrency control`,
  `Load shedding / admission control`, `Durable change log + idempotent
  projectors`, and `Dead-letter queue`.
- If aliases are added, use them in renderer/search/linking instead of keeping
  them only inside the `what` text.

### 2. A few repeated book patterns still deserve first-class catalog coverage

The catalog is much broader now, but repeated tags in current cases still point
to missing or under-modeled vocabulary:

- Event logs and projectors: `Durable change log + idempotent projectors`,
  `Append-only log`, `Consumer groups + offsets`, `Versioned events with
  source_version ordering`.
- Data pipeline and warehouse patterns: `ELT`, `Governed raw lake`,
  `Schema registry + evolution`, `Batch reprocessing`, `Point-in-time
  correctness`.
- ML/platform patterns: `Feature store (online/offline parity)`,
  `Train/serve consistency`, `Model routing / cascading`, `Inference batching`,
  `Feature monitoring (drift/skew)`.
- Real-time collaboration and sync: `CRDT`, `Operational Transformation (OT)`,
  `Snapshot + op log`, `Delta sync`, `Per-device sync cursor`.
- Release/build patterns: `Progressive delivery`, `GitOps`, `Merge queue`,
  `Affected-only builds`, `Immutable, signed artifacts`.

Why it matters: these are not just domain details. They are reusable interview
moves across the newer book families: analytics, feature store, collaboration,
CI/CD, media pipelines, and operational platforms.

Concrete fix:

- Add a second catalog pass for patterns used by several cases or central to an
  entire family, even if their exact frequency is low today.
- Prefer compact entries over exhaustive coverage; the current card format can
  absorb 10-15 more high-value patterns without becoming unwieldy.
- For narrower tags, add aliases under broader entries rather than creating
  near-duplicate cards.

### 3. `usedBy` is still not machine-checkable

`usedBy` is helpful, but it is currently a list of display strings. It cannot
link to a dataset or step, and it cannot be validated against `data/book/index.json`
or `step.patterns[]`.

Why it matters: the catalog should answer "where do I see this pattern in a
real case?" Plain strings are easy to stale as case titles change, and they do
not prove that a case actually uses the pattern.

Concrete fix:

- Consider allowing `usedBy` entries as objects:
  `{ group, datasetId, label, steps }`, while preserving string support for
  older data.
- Generate or validate `usedBy` from `step.patterns[]` once aliases exist.
- At minimum, add a lint script that checks display names against the manifest
  and flags catalog patterns with no matching case tags or aliases.

### 4. Cross-pattern relationships are only implicit

The follow-up questions correctly call out compositions such as outbox -> work
queue -> idempotency/dedup -> DLQ and sharding -> replication -> quorum. The
cards themselves, however, do not expose "pairs well with", "confused with", or
"usually follows" relationships.

Why it matters: candidates need to know not only the pattern definition, but
the move sequence. For example, "use a queue" should naturally lead to
visibility timeout, idempotent consumer, retry policy, DLQ, backlog metrics, and
backpressure.

Concrete fix:

- Add optional lightweight fields such as `pairsWith`, `commonlyConfusedWith`,
  or `nextPatterns`, rendered as chips.
- If schema change is too much, add one sentence to the most compositional
  entries: queues, outbox, CDC, read model, cache, lease/fencing, saga,
  authorization, and vector search.

## System Design Soundness

The included pattern definitions are sound and noticeably more operational than
before. They identify the durable source of truth, expected consistency model,
or critical control point in most places:

- Distributed data entries distinguish partitioning, replication, quorum, and
  consensus, and call out hot shards, stale failover, conflict ordering, and CP
  minority behavior.
- Messaging entries correctly present at-least-once delivery, visibility
  timeouts, idempotent consumers, DLQs, retry storms, and bounded backpressure.
- Correctness entries handle the major interview traps: idempotency key scope,
  dedup windows, append-only ledger entries, reconciliation authority, fencing
  tokens, CAS contention, and reservation expiry.
- Security entries now cover RBAC/ABAC, ReBAC, OAuth/OIDC token lifecycle, and
  permission-scoped search with stale-permission failure modes.
- Media/storage entries include commit-metadata-last, reference-counted GC,
  metadata/blob drift, erasure-code repair cost, and QoE telemetry.

The main soundness gap is taxonomy granularity. Some case-study tags are
standalone interview concepts but currently need to be inferred from broader
catalog cards. Examples include consumer groups/offsets, event-version
ordering, feature stores, CRDT/OT, and progressive delivery.

## Step-by-Step Pedagogical Review

This dataset intentionally has no walkthrough steps. That is valid because a
non-empty `patternCatalog[]` is enough for a catalog dataset.

The pedagogical unit is the pattern card. The card now teaches:

- what the pattern is
- when to use it
- what trade-off it carries
- one failure mode an interviewer expects the candidate to name
- which systems use it

That is a strong shape for recall. The next teaching improvement is to make the
cards teach composition. A candidate should be able to move from "this system
needs async processing" to "queue, idempotent consumer, retry with jitter, DLQ,
backpressure, and queue-lag alerting" without relying on the follow-up section
alone.

## Final Design Review

There is no `finalDesign`, which is appropriate. This is a catalog, not a
single system design walkthrough.

Do not add a fake architecture diagram. If the UI eventually supports catalog
concept maps, a derived relationship view would be useful: outbox -> queue ->
dedup -> DLQ; sharding -> replication -> quorum; cache -> request coalescing ->
origin protection; RBAC/ABAC -> ReBAC -> permission-scoped search. That should
be a catalog relationship view, not a synthetic high-level architecture.

## Concept Introduction and Learning Flow

The current category order works well:

1. Scaling and data distribution
2. Read/write optimization
3. Messaging and asynchrony
4. Reliability and correctness
5. Protection and fairness
6. Specialized indexing
7. Integration and edge
8. Security and identity
9. Media and object storage

This order moves from broad distributed-systems foundations into domain-specific
families. The one weakness is that "Specialized indexing" now contains search,
recommendation, vector, and time-series concepts that could eventually split
into "Search and retrieval" and "Observability and analytics" if the catalog
continues to grow.

## Step-to-Final-Design Coherence

Not applicable as a walkthrough. The equivalent coherence check is whether case
studies can point back to the catalog. Today that works by human reading, but
not by exact data. The catalog names are close to the case tags, and many cards
include synonyms in prose, but there is no structured aliasing or validation.

## Realism Compared With Production Systems

The catalog now reads like production vocabulary rather than textbook
vocabulary. It covers many gotchas that strong candidates should volunteer:
stale replicas, thundering herds, projector bugs, relay crashes, poison
messages, duplicate redelivery, stale fencing tokens, stale auth decisions,
cold-cache origin stampedes, orphaned blobs, and high-cardinality time series.

Remaining realism improvements should focus on operational ownership:

- Add a monitoring hook to patterns that imply an SLO or page: queue lag, DLQ
  depth, projector freshness, cache hit ratio, stale authorization decisions,
  reconciliation breaks, and CDN origin miss rate.
- Add a "state stored" hint to patterns whose correctness depends on a durable
  table: idempotency keys, dedup windows, holds, leases/fencing tokens,
  outbox rows, saga states, and reconciliation records.
- Add a "do not use when" hint to patterns that candidates over-apply:
  consensus, distributed locks, write fanout, vector indexes, and erasure
  coding.

## Dataset and Renderer-Facing Observations

- `data/book/patterns/interview.json` parses as valid JSON.
- Top-level keys are `assets`, `description`, `followUps`,
  `highLevelArchitecture`, `patternCatalog`, `title`, and `toProbeFurther`.
- The catalog has 49 entries across 9 categories.
- The dataset has no `steps[]`, `requirements`, `capacity`, `api`,
  `dataModel`, `satisfies`, `interviewScript`, `levelVariants`, or
  `finalDesign`. This is valid because `patternCatalog[]` is non-empty.
- `highLevelArchitecture` is `{ "nodes": [], "links": [], "types": [] }`;
  that is accepted and should stay empty unless a real catalog concept-map
  feature is added.
- Each pattern currently has both `category` and `group`, and they match for all
  49 entries. The renderer groups by `category || group`, so carrying both is
  redundant but harmless.
- `toProbeFurther` uses the grouped object form with a `links` array. The
  renderer and validator support this shape.
- `followUps` is an array of strings, which matches the current renderer.
- There is no docs rebuild required for this review file alone.

## Recommended Edits, Prioritized

### P1: Add structured aliases or normalize exact pattern tags

Make `patternCatalog[].name` the canonical vocabulary and connect current
case-study synonyms through `aliases` or normalized `step.patterns[]` values.

### P1: Make `usedBy` linkable or generated

Move toward structured `usedBy` references with dataset IDs and step IDs, or
derive them from case-study pattern tags once aliases exist.

### P2: Add missing high-value families from current case tags

Prioritize durable event logs/projectors, consumer groups/offsets, feature
stores, CRDT/OT, progressive delivery, schema evolution, and warehouse/batch
reprocessing patterns.

### P2: Add relationship hints between patterns

Expose pairs/compositions/confusions directly on cards, at least for the
messaging, storage, caching, authorization, and search families.

### P3: Remove redundant `group` fields if no other tooling uses them

Because `category` and `group` are identical on every pattern, one of them can
be removed after checking any scripts that may still read `group`.

## What Not To Change

- Keep this as a catalog-only dataset; do not add artificial steps.
- Keep entries compact. The strongest improvement is structured relationships,
  not long essays inside each card.
- Keep the "Failure mode to name" wording or equivalent guidance; it is now one
  of the catalog's best teaching features.
- Keep the grouped `toProbeFurther` references. They now align with the broader
  catalog coverage.

## Bottom Line

This is now a strong reusable-pattern reference for the book. The next level is
data coherence: canonical names, aliases, linkable `usedBy` references, and a
small number of missing case-study patterns that are important enough to become
first-class vocabulary.
