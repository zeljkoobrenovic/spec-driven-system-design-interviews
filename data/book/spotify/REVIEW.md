# Review: Spotify — Audio Streaming — System Design

Reviewed file: `data/book/spotify/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent dataset pass materially improves the Spotify case. The earlier
largest gaps — quantitative capacity, entitlement/DRM, regional availability,
search indexing, richer data contracts, royalty accounting, feature storage,
hot-content operations, and diagram hygiene — are now addressed in the source
interview.

This is now a strong book-style walkthrough. It has a coherent seven-step arc,
good production vocabulary, concrete capacity numbers, and a final architecture
that integrates audio delivery, catalog/search, library/playlists, offline
licenses, play-event streams, recommendations, and royalties. The remaining
work is mostly second-layer depth: make recommendations/home feed less
placeholder-like, tighten rights/accounting details, promote some operational
details into first-class architecture, and fix a few dataset coherence nits.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.3/5 | Core media, catalog, library, offline, event, entitlement, and royalty paths are credible. |
| Production realism | 4.1/5 | Much stronger than before; fraud/privacy/observability and recommendation serving still need more shape. |
| Pedagogical flow | 4.2/5 | The step sequence works and now has decision prompts, recaps, traps, and drills; Step 7 is dense and could teach more gradually. |
| Dataset/rendering fit | 4.4/5 | JSON parses, structured views resolve, and prior link endpoint issues are fixed; a few mapping/pattern details remain. |
| Overall | 4.2/5 | Book-quality foundation with targeted polish still worthwhile. |

## What Works Well

- The capacity section now does real work: catalog PB estimate, concurrent
  stream bandwidth, segment QPS, CDN hit-ratio/origin-miss budget, play-event
  rate, search read QPS, and ingestion throughput all tie back to design steps.
- The playback path now models the critical licensed-media decision: per-play
  entitlement checks across subscription, market, availability, device, signed
  segment URLs, short TTLs, and DRM licenses.
- Search is no longer hand-waved as catalog DB reads. The case adds a dedicated
  search index, indexing path, market filtering, and prefix/typo-tolerant
  ranked search.
- The data model has become much more credible: rights policy, subscriptions
  and devices, playlist items with fractional rank/versioning, offline download
  state, raw play events, royalty ledger, and feature store.
- Play-event processing is correctly split between recommendations and a
  separate idempotent, fraud-filtered royalty ledger.
- The step extras are much richer than the old review: decision prompts,
  why-now sections, recaps, traps, failure drills, and scale bottlenecks make
  the walkthrough easier to teach.
- Prior diagram issues appear fixed. Step views and string links resolve, and
  the previous missing endpoint cases for `library` and `scale` no longer show
  up in the current structured views.

## Highest-Impact Issues

### 1. Recommendation serving is still thinner than the rest of the design

The case now has `FeatureStore` and `RecSvc`, which is a major improvement, but
the personalized-home requirement still reads mostly as "play events feed
features, then recs write to library." It does not yet explain candidate
generation, ranking, online retrieval, home-feed serving, freshness, or why
generated playlists differ from a real-time recommendation shelf.

Why it matters: recommendations are one of the named product requirements, and
the rest of the dataset has become concrete enough that this path now stands
out as the least developed major subsystem.

Concrete fix: add a small recommendation-serving shape: play log -> stream/batch
features -> feature store + candidate store/model outputs -> recommendation
service -> home/feed or generated playlist API. Name the latency expectations
for home page personalization versus weekly playlist generation, and explain
fallbacks for cold-start users.

### 2. Rights and royalty modeling is strong at the API level but still compact

`rights_policy`, `isrc`, and `royalty_ledger` are the right primitives. The
remaining gap is that labels, territories, rights holders, splits, effective
windows, disputes, corrections, and audit/replay workflows are still compressed
into one policy row and one ledger row.

Why it matters: the interview does not need a full music-industry accounting
system, but it should be honest that "accurate royalties" involves more than
deduping play events. The current design could make readers underweight rights
holder splits and replayable accounting periods.

Concrete fix: add one or two sentences or fields for rights-holder splits,
territorial contracts, ledger period close/replay, and adjustment events. Keep
it bounded; the goal is to show the boundary, not design a finance platform.

### 3. Observability is present as prose but not represented in the architecture

Step 7 has useful operating metrics: start latency p99, rebuffer ratio, CDN hit
ratio, origin miss QPS, manifest/entitlement failures, play-log lag, duplicate
rate, royalty lag, offline sync conflicts, ingestion backlog, and transcode
dead-letter rate. However, there is no observability node or flow in the
high-level architecture/final design.

Why it matters: for a media system, quality-of-experience metrics are not
incidental. They are how operators detect CDN regressions, bad bitrate ladders,
entitlement outages, fraud spikes, and ingestion backlogs.

Concrete fix: add an `Observability` node of canonical type `observability` to
the final design or scale view, fed by client playback telemetry, CDN/origin
metrics, service metrics, and pipeline lag. The text is already good; the
diagram should make it visible.

### 4. Fraud, privacy, and retention need one more production pass

The dataset now says royalties are fraud-filtered and play events retain raw
data for about 30 days before aggregation. That is directionally correct, but
the fraud/privacy boundary remains thin. Listening history is sensitive, and
fraud filtering affects payments.

Why it matters: a senior/staff answer should mention abuse controls and data
governance when behavior data drives money and personalization.

Concrete fix: add a fraud/risk consumer or a short fraud-filtering paragraph:
bot/farm signals, device/account velocity, suspicious repeats, appeal/replay
path, and separation from recommendation features. Add a retention/privacy note
for raw play events, user deletion/export, and aggregation/anonymization.

### 5. A few dataset coherence details lag behind the content upgrades

The source requirements list six functional requirements, but
`satisfies.functional` maps five; licensed playback is represented under
non-functional instead of matching the functional requirement. The
`Async ingestion pipeline` pattern points to `playback`, even though Step 7 is
the main ingestion/hot-content step. Step 7 has no `concepts` despite
introducing ingestion state machines, origin shields, prewarming, SLOs, and
derived-state rebuildability.

Why it matters: these are small, but they affect the rendered wrap-up and the
reader's ability to trace requirements and patterns back to the right step.

Concrete fix: add a functional `satisfies` row for licensed playback/download
or move that requirement category consistently; add `scale` to the async
ingestion pattern; add one or two Step 7 concepts such as "Ingestion state
machine" and "Hot-content prewarming/origin shield."

## System Design Soundness

The core architecture is sound. CDN-served segmented audio is the right default
for instant start and massive fanout. The design correctly keeps application
servers off the byte-serving hot path, uses object storage as durable origin,
and explains the origin-miss budget at a 98-99% edge hit ratio.

The catalog/library split is also well handled. Shared catalog state, search
indexing, and per-user mutable library/playlists are separated, and the
playlist-item model avoids the earlier track-id-array weakness. The design now
accounts for unavailable tracks at hydration time instead of assuming every
reference remains playable forever.

Entitlement and offline playback are credible. Playback and download APIs carry
device/market/session context, rights are versioned, offline licenses expire
and revalidate, and takedowns invalidate manifests and offline licenses. That
is the right shape for licensed media.

The play-event system now separates raw ingestion from recommendation features
and royalty accounting. The design names idempotency keys, session/sequence
ordering, client/server timestamps, dedupe windows, stream thresholds, fraud
filtering, and an auditable ledger. The remaining improvement is to make the
fraud/accounting boundary a little more explicit.

Search is finally designed as its own path. The dedicated index, market filter,
and ingestion-fed updates close the old "catalog DB does search" gap.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Stream the Whole File from the App Server

This remains a good baseline. The decision prompt now asks what happens to
latency and origin load at tens of millions of streams, which sets up Step 2
well. The trap is clear and specific.

Improvement: no major change needed. If anything, keep this step short so it
does not compete with the real design.

### Step 2: Segmented Audio Delivery via CDN

This is now the strongest step. It combines segmented streaming, bitrate
ladders, CDN cache behavior, origin miss budgeting, entitlement checks, signed
URL TTLs, DRM licenses, takedown-driven manifest invalidation, and CDN failure
drills. The options compare the real default against peer-assisted delivery
and origin streaming without strawmen.

Improvement: if adding an observability node later, this step should mention
client playback telemetry and CDN/origin metrics as first-class signals.

### Step 3: Catalog vs Library Split

The search-index addition fixes the prior biggest gap in this step. The lesson
now covers authoritative catalog metadata, separate ranked search, market
filtering, and the different scaling axes for catalog and user library.

Improvement: add a short note on stale search results after takedown: the
catalog/rights store is authoritative, and the search index is rebuildable and
filtered at query/hydration time.

### Step 4: Playlists and Library (Reference by ID)

This step is much stronger after the move from a single `track_ids` array to
playlist item rows with fractional rank and optimistic concurrency. The
unavailable-track trap is a useful production detail.

Improvement: collaborative playlists are in follow-ups; consider one small
failure drill here for concurrent offline edits or collaborative reorder
conflicts, since the data model now has enough detail to support it.

### Step 5: Offline Download and Sync

This step now has the right primitives: device-bound offline licenses, encrypted
local cache, license expiry/revalidation, sync cursors, buffered edit
operations, and conflict handling. The failure drills are practical.

Improvement: state whether offline play events are uploaded through the same
`/v1/plays:batch` path and how very late events are accepted, deduped, or
excluded from a closed royalty period.

### Step 6: Play Events: Recommendations and Royalties

The asynchronous event log remains the right answer, and the current version
adds the important split between feature generation and royalty accounting. The
traps are good: do not count directly from an at-least-once raw log, and do not
couple recs and royalties.

Improvement: add a bit more recommendation-serving depth and a short fraud
consumer shape. This would bring the step up to the same quality as playback
and offline.

### Step 7: Ingestion, Hot Content, and Scale

This step is now much more substantial. It covers ingestion state, deterministic
output keys, retry/dead-letter, publish-last semantics, rollback, CDN prewarm,
origin shield, popularity cache, log backpressure, derived state, and operating
SLOs.

Improvement: split or teach the concepts more explicitly. Step 7 carries many
advanced ideas but has no `concepts`, and the async ingestion pattern is not
linked to this step. Add concepts for the ingestion state machine and
hot-content/origin-shield strategy.

## Final Design Review

The final design now integrates the important systems introduced by the steps:
`StreamSvc`, `EntSvc`, `RightsDB`, `CDN`, `AudioStore`, `CatalogSvc`,
`CatalogDB`, `SearchIdx`, `LibrarySvc`, `LibraryDB`, `Ingest`, `PlayLog`,
`FeatureStore`, `RecSvc`, `Royalty`, and `RoyaltyDB`.

The description is strong. It states which stores are authoritative and which
stores are rebuildable derived state, explains offline license and sync behavior,
and separates recommendation features from royalty ledgering.

The main final-design omission is observability. Step 7 names the right SLOs,
but the final diagram does not show how playback telemetry, CDN/origin metrics,
service failures, and pipeline lag are collected. Add that if the goal is a
staff-level final architecture.

## Concept Introduction and Learning Flow

The concept sequence is logical and much improved:

- Step 1 establishes the failed baseline.
- Step 2 introduces segmented CDN delivery and entitlement.
- Step 3 separates catalog, library, and search.
- Step 4 models playlist references and concurrent ordering.
- Step 5 adds offline cache/license/sync.
- Step 6 turns playback behavior into durable streams for recs and royalties.
- Step 7 closes with ingestion, hot-content scaling, and operations.

The new `decisionPrompt`, `whyNow`, and `recap` fields make the case feel more
like an interview walkthrough than a static architecture note. The remaining
pedagogical gap is Step 7 density: it introduces several staff-level concepts
at once without concept cards.

## Step-to-Final-Design Coherence

The final architecture now reflects the step additions. Entitlement/rights,
search index, feature store, royalty accounting, and ingestion are all present
in `highLevelArchitecture` and the final design. This closes most of the old
coherence problems.

The remaining mismatches are small:

- Licensed playback/download is listed as a functional requirement but mapped
  under non-functional satisfaction.
- `Async ingestion pipeline` points to Step 2 even though Step 7 is the
  ingestion/scale synthesis step.
- Step 7's scale concepts are mostly embedded in prose rather than represented
  as concept cards/pattern tags.

## Realism Compared With Production Systems

This is now realistic at the level expected for a strong system design
interview. It does not pretend that app servers stream audio, that catalog DBs
serve ranked search, that offline is just "download a file," or that raw play
logs can directly pay royalties.

Production caveats worth adding:

- Rights contracts and royalty splits are simplified.
- Recommendation serving and cold-start behavior are simplified.
- Fraud filtering is named but not architected.
- Privacy, deletion/export, and play-history retention are only lightly
  covered.
- Observability is described but not shown as an architectural path.

These are acceptable omissions for a bounded case, but they are the right next
places to deepen the interview.

## Dataset and Renderer-Facing Observations

- JSON parses successfully.
- Step view node IDs resolve to `highLevelArchitecture.nodes`.
- Step and final-design string link references resolve to
  `highLevelArchitecture.links`.
- The previous `library` view issue with `lb-catalog` is fixed by a local
  inline `LibrarySvc -> CatalogSvc` link.
- The previous `scale` view issue with `client-playlog` is fixed; `Client` is
  now included in that view's nodes.
- The peer-assisted option's local `Peers` node now has `type: "client"`.
- `satisfies[*].steps[*]` and `patterns[*].steps[*]` resolve to real step IDs.
- No raw `diagram` fields appear under structured step or final-design areas.
- `REVIEW.md` is repo-only; no docs rebuild is needed for this review update.

## Recommended Edits, Prioritized

### P1: Add recommendation-serving depth

Show how features become personalized home/generated playlists: candidate
generation, model or batch output, online ranking/retrieval, cold-start
fallbacks, and freshness expectations.

### P1: Add observability to the architecture

Represent playback QoE, CDN/origin, entitlement, play-log, royalty, fraud, and
ingestion metrics with an observability node/path in the final or scale view.

### P2: Tighten rights, royalty, fraud, and privacy boundaries

Add concise details for rights-holder splits, territorial contracts, accounting
period replay/adjustments, fraud signals, and retention/deletion handling for
listening history.

### P2: Fix requirement and pattern traceability

Align the licensed-playback functional requirement with `satisfies.functional`,
and link `Async ingestion pipeline` to `scale` as well as or instead of
`playback`.

### P3: Add Step 7 concept cards

Add concepts for "Ingestion state machine" and "Hot-content prewarming/origin
shield" so the dense scale step is easier to scan and teach.

### P3: Add a collaborative/offline playlist conflict drill

The playlist data model supports concurrent edits; a short failure drill would
make that lesson more interview-ready.

## What Not To Change

- Keep the seven-step arc.
- Keep the naive baseline as contrast.
- Keep segmented CDN delivery as the default playback answer.
- Keep entitlement/DRM on the playback and offline authorization paths.
- Keep the catalog/search/library separation.
- Keep playlist item rows with reference-by-id hydration.
- Keep play-event ingestion asynchronous and off the playback critical path.
- Keep recommendation and royalty consumers separated.
- Keep Step 7 as the capstone, but make its concepts more explicit.

## Bottom Line

The Spotify dataset has moved from a good first-pass case to a credible
book-quality system design interview. The remaining work is targeted: deepen
recommendations, show observability, sharpen rights/accounting/fraud/privacy,
and clean up a few requirement/pattern mappings.
