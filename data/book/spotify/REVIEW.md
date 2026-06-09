# Review: Spotify - Audio Streaming - System Design

Reviewed file: `data/book/spotify/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a clear, usable first-pass case for audio streaming. The main teaching
arc is sound: start with naive origin streaming, move to segmented CDN delivery,
split catalog from user library state, store playlists by track reference,
handle offline download/sync, and use play-event streams for recommendations and
royalties.

The dataset is not yet at the depth of the stronger book cases. It states
Spotify-scale requirements, but the capacity model, API contracts, data model,
and final architecture stay too small for that scale. The largest gaps are
entitlement/DRM/licensing state, search/indexing, richer playlist/offline/play
event records, royalty accounting consumers, operational SLOs, and a few
renderer-facing diagram inconsistencies.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 3.5/5 | The main split is right, but several required state surfaces are only implied. |
| Production realism | 3.2/5 | CDN, segmentation, offline sync, and streams are present; licensing, DRM, search, royalty accounting, failure handling, and operations are thin. |
| Pedagogical flow | 3.8/5 | The seven-step arc is coherent, but many steps need stronger problem statements, failure drills, and concrete trade-offs. |
| Dataset/rendering fit | 3.7/5 | JSON parses and most references resolve; two step diagrams reference link endpoints outside their node lists. |
| Overall | 3.5/5 | Good foundation; one substantial content pass would make it book-quality. |

## What Works Well

- The scope is easy to understand: streaming playback, catalog browsing,
  personal libraries/playlists, offline use, recommendations, and royalties.
- The high-level architecture uses the right core boundaries: streaming
  service, object storage, CDN, catalog service/store, library service/store,
  ingestion/transcode, play-event log, and recommendation service.
- Step 2's default option explains segmented audio, signed segment URLs, CDN
  origin misses, adaptive bitrate, and egress cost.
- The catalog/library split and reference-by-id playlist pattern are the right
  lessons for shared media plus per-user mutable state.
- Offline playback is framed as encrypted local cache plus reconnect
  reconciliation rather than just "download files."
- The play-event stream option correctly avoids synchronous analytics writes on
  the playback path and names idempotent consumers for royalty accuracy.

## Highest-Impact Issues

### 1. Capacity is descriptive, not quantitative enough to drive design choices

The capacity section names "100M+ tracks", "tens of millions" of concurrent
streams, "few MB" tracks, sub-second start latency, and "billions/day" of play
events. Those are useful headlines, but they do not convert into bandwidth,
storage, request rate, CDN hit ratio, origin miss traffic, ingestion backlog, or
stream partitions.

Why it matters: the case claims Spotify scale. Readers need enough arithmetic
to justify CDN-first delivery, object-store layout, play-log partitioning,
offline cache limits, catalog/search cache behavior, and hot-release prewarming.

Concrete fix: add capacity bullets such as average/peak segment QPS, edge
bandwidth, origin miss budget at several hit ratios, audio storage multiplier
for bitrate ladders, play-event events/sec, event retention, ingestion/transcode
throughput, and catalog/search read QPS. Tie each number to a step.

### 2. The API and data model do not support the behavior promised by the prose

The API surface is intentionally small, but it omits fields that later become
important: user/device/session identity, market/region, entitlement state,
manifest version, DRM/license response, idempotency/event IDs, offline batch
sync, playlist item positions, optimistic concurrency, and unavailable-track
handling. The data model has only `tracks`, `playlists`, and `play_event`.

Why it matters: offline download, licensing, playlist edits, royalty counts,
recommendations, and search cannot be made reliable from these records alone.
The design reads plausible at the component level but underspecified at the
state level.

Concrete fix: add or expand records for `artists`/`albums`, `playlist_items`
with position/version, saved-library rows, offline download/license state,
playback sessions, deduped play events with event ID and device timestamp,
royalty aggregation or accounting output, and recommendation feature/history
storage. Update APIs with idempotency keys, versions, and sync cursors.

### 3. Entitlements, DRM, takedowns, and region restrictions are only implied

The text mentions signed segment URLs, key rotation, encrypted offline cache,
license revalidation, and tracks becoming unavailable. There is no entitlement
or license service, no rights/policy store, no DRM license flow, no regional
availability state, and no takedown invalidation path in the final design.

Why it matters: for a music streaming system, "can this user play/download this
track in this country on this device right now?" is on the critical path. It
also affects offline expiration, cached manifests, CDN tokens, playlist
hydration, and royalty reporting.

Concrete fix: introduce an Entitlement/License service and rights-policy store.
Show playback checking user subscription, region, track availability, and
device/offline rules before issuing manifest URLs and DRM keys. Add a flow for
license/takedown changes invalidating manifests, offline licenses, and playlist
hydration results.

### 4. Search and recommendations are requirements but not designed deeply

"Search and browse a large music catalog" is a functional requirement, yet the
architecture has no search index, indexing pipeline, query path, cache, ranking,
or typo/prefix strategy. Recommendations are represented by `RecSvc`, but there
is no feature store, model/batch pipeline, online retrieval path, or separation
between recommendations and royalty accounting consumers.

Why it matters: the dataset risks teaching that catalog DB queries and a single
recommendation service are enough for a music product. At this scale, search and
personalized home are their own read paths and data pipelines.

Concrete fix: add a search/index component fed by catalog ingestion, and add a
recommendation pipeline split such as play log -> stream/batch processors ->
feature/history store -> recommendation service. Add a separate royalty
consumer/ledger so recommendations and accounting do not look like the same
system.

### 5. The walkthrough needs more production failure modes and operations

The steps teach the broad architecture, but only the naive step has a trap. The
case would benefit from failure drills around CDN outage/origin overload,
playlist concurrent edits, offline sync conflicts, duplicate/late play events,
fraudulent play farming, hot new releases, catalog takedowns, and ingestion
retries.

Why it matters: the current case is good for explaining the happy path. A
strong senior/staff interview answer should also expose where the design breaks,
what is retried, what is idempotent, what is eventually consistent, and which
metrics page an operator would watch.

Concrete fix: add traps or failure drills to Steps 2, 4, 5, 6, and 7. Add
observability/SLO details for start latency, rebuffer ratio, CDN hit ratio,
origin egress, manifest failures, offline sync conflicts, play-log lag,
duplicate rate, royalty pipeline lag, and ingestion backlog.

## System Design Soundness

The core playback architecture is directionally correct. Segmented audio served
from a CDN with object storage as origin is the right default, and the option
set in Step 2 compares it against peer-assisted and direct-origin delivery in a
useful way.

The catalog/library split is also sound. Shared catalog metadata and per-user
mutable library state have different scale, consistency, and caching needs.
The reference-by-id playlist lesson is appropriate because duplicating track
metadata across millions of playlists creates storage and takedown problems.

The design becomes thin around state and policy. A music system needs rights,
availability, user subscription/device authorization, signed URL expiry, DRM key
issuance, offline license expiry, and takedown propagation. The current model
has hooks in the prose but no components or records to own those decisions.

The play-event architecture is directionally right but should be more precise.
It should distinguish raw events, deduped playback sessions, recommendation
features, royalty/accounting aggregates, fraud/bot filtering, and metrics. A
single `PlayLog -> RecSvc -> LibrarySvc` path hides the harder accounting and
consumer-isolation questions.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Stream the Whole File from the App Server

This is a good baseline. The diagram and trap expose why direct whole-file
streaming fails: slow start, origin bandwidth pressure, and no adaptive bitrate.

Improvement: add a short problem statement or recap that tees up Step 2. The
reader should see that the next design goal is to keep playback traffic off the
application servers and start audio after the first small segment, not after a
whole object fetch.

### Step 2: Segmented Audio Delivery via CDN

This is the strongest step. It teaches manifest URLs, edge segment fetches,
origin misses, bitrate ladders, pre-segmentation, and CDN egress trade-offs.
The peer-to-peer alternative is useful historical context.

Improvements: add entitlement/DRM checks to the playback flow, include manifest
and segment cache keys/TTL at a high level, and add a failure drill for CDN
miss storms or a massive new release that needs prewarming.

### Step 3: Catalog vs Library Split

The concept is correct and well placed. The step separates shared, mostly
cacheable metadata from user-owned mutable state before playlists are modeled.

Improvements: add the search/index read path here or in a nearby sub-step. The
functional requirement says search and browse a large catalog; a catalog DB
alone is not the right mental model for prefix search, relevance ranking,
artist/album browsing, or popularity signals.

### Step 4: Playlists and Library (Reference by ID)

The default option is the right one, and the denormalized alternative explains
the storage and takedown downsides clearly.

Improvements: model playlist items as rows or an ordered CRDT-like list rather
than one `track_ids` array. Add optimistic concurrency, version/cursor based
sync, collaborative playlist conflict behavior, deleted/unavailable track
hydration, and cache strategy for resolving many track IDs.

### Step 5: Offline Download and Sync

The step correctly states encrypted local cache, library edits buffered offline,
and license revalidation on reconnect.

Improvements: make offline a real state machine. Track download intent,
downloaded segment set, license expiry, device limit, subscription/region
revalidation, local edit operations, sync cursor, conflict policy, and delete or
revocation behavior when a track becomes unavailable.

### Step 6: Play Events: Recommendations and Royalties

The default stream option is correct and the synchronous database alternative is
a useful foil. The flow correctly keeps event ingestion asynchronous so playback
is not blocked by analytics.

Improvements: split the consumers. Recommendations, royalty accounting, fraud
filtering, resume position, metrics, and artist dashboards have different
latency and correctness requirements. Add event IDs, playback session IDs,
sequence numbers, client timestamps, server receive timestamps, offline batch
upload, dedup windows, and threshold semantics for "counts as a stream."

### Step 7: Ingestion, Hot Content, and Scale

This works as a synthesis step, but it is too brief for the title. Ingestion,
hot content, and scale are each substantial topics.

Improvements: add a concrete ingestion state machine for masters, transcode
jobs, segment output, catalog publish, retry/dead-letter behavior, and rollback.
For hot content, add CDN prewarm, origin shield, per-track popularity cache, and
backpressure. For scale, add SLOs and operator metrics.

## Final Design Review

The final design integrates the main components introduced in the steps. It
does not accidentally put the application server on the segment hot path, and
it preserves the catalog/library split and play-event stream.

The final design should become more explicit about the systems it currently
implies: entitlement/license checks before playback and offline download,
search indexing for catalog browsing, recommendation and royalty consumers,
feature/history storage, fraud filtering, and operational monitoring. Without
those, the final design is a good audio-delivery diagram but not yet a full
Spotify-like product design.

## Concept Introduction and Learning Flow

The concept sequence is logical: naive delivery, segmented CDN delivery,
catalog/library split, reference-by-id playlists, offline sync, play-event
streams, then scale. Each concept mostly arrives near the step where it matters.

The main teaching gap is that several steps state outcomes without exposing the
pressure that forces the mechanism. Adding `problem`/`decision` style prose,
traps, and failure drills would make the walkthrough more interview-like. The
case should let readers practice why a mechanism is needed, not only recognize
the final mechanism.

## Step-to-Final-Design Coherence

The final architecture includes the components introduced by the steps:
`StreamSvc`, `AudioStore`, `CDN`, `CatalogSvc`, `CatalogDB`, `LibrarySvc`,
`LibraryDB`, `Ingest`, `PlayLog`, and `RecSvc`. The `satisfies` section maps
the major requirements to relevant steps and all listed step IDs resolve.

The coherence gaps are mostly omissions rather than contradictions. Search is a
requirement without a designed component. Royalties are named but do not appear
as a consumer or ledger. Offline license enforcement is mentioned but not owned.
Catalog availability changes are mentioned in follow-ups but not reflected in
the data model or final design.

## Realism Compared With Production Systems

For an interview, this is realistic at the first architectural layer. It knows
that audio is segmented, cached, and authorized by manifest/URL issuance rather
than streamed through app servers. It understands that playlists reference
shared tracks and that play events should flow through a durable log.

Production realism needs another layer of detail:

- Entitlement, subscription, rights, market availability, and DRM license
  issuance.
- CDN prewarming, origin shield, cache invalidation, signed URL TTLs, and
  regional edge behavior.
- Search indexing and ranking separate from the authoritative catalog store.
- Playlist ordering, concurrent edits, sync cursors, and unavailable-track
  hydration.
- Offline license expiry, device limits, subscription checks, conflict
  resolution, and revocation.
- Raw play-event deduplication, fraud filtering, stream-count thresholds,
  royalty ledgering, and delayed/offline event handling.
- Ingestion/transcode retries, deterministic output keys, publish state, and
  rollback.
- Observability and operations for quality of experience and cost.

## Dataset and Renderer-Facing Observations

- JSON parses successfully.
- Step view node IDs resolve to `highLevelArchitecture.nodes`.
- Step and final-design string link references resolve to
  `highLevelArchitecture.links`.
- `satisfies[*].steps[*]` and `patterns[*].steps[*]` resolve to real step IDs.
- No raw `diagram` fields appear under structured step or final-design areas.
- `steps[library].view.links` includes `lb-catalog`, whose source endpoint
  `LB` is not listed in that view's nodes. The default option uses an inline
  `LibrarySvc -> CatalogSvc` link that better matches the caption.
- `steps[scale].view.links` includes `client-playlog`, whose source endpoint
  `Client` is not listed in that view's nodes. This can cause Mermaid to create
  an implicit unlabeled node.
- The peer-assisted delivery option introduces a local `Peers` node without a
  canonical node type. Add `type: "client"` or another suitable type so styling
  is intentional.
- `REVIEW.md` is repo-only; no docs rebuild is needed for this review.

## Recommended Edits, Prioritized

### P1: Add quantitative capacity and workload math

Expand capacity into concrete request, bandwidth, storage, event, and ingestion
numbers. Use those numbers to justify CDN, object storage, play-log partitions,
and ingestion worker scale.

### P1: Model entitlement, DRM, regional availability, and offline license state

Add an entitlement/license component, policy store, playback authorization flow,
DRM/offline license fields, and takedown/region-change behavior.

### P1: Strengthen API and data-model contracts

Add playlist item/version records, saved-library rows, playback sessions,
deduped play events, offline download/license state, and royalty/recommendation
outputs. Add idempotency keys, sync cursors, event IDs, versions, and region or
device context to APIs.

### P2: Add search and recommendation pipeline depth

Introduce a catalog search index and indexing path. Split recommendations into
feature/history processing and online retrieval. Add a separate royalty
accounting consumer or ledger.

### P2: Add failure drills and operations

Add drills for CDN miss storms, offline sync conflicts, duplicate late play
events, fraud, ingestion retry/dead-letter, and licensing takedowns. Add SLOs
and metrics for playback quality, CDN cost, event lag, and ingestion backlog.

### P3: Fix diagram hygiene

For the `library` and `scale` step views, either include the missing endpoint
nodes or replace the link references with inline links whose endpoints are in
the view. Give the `Peers` option node a canonical type.

## What Not To Change

- Keep the seven-step arc.
- Keep the naive baseline as contrast.
- Keep segmented CDN delivery as the default playback answer.
- Keep the catalog/library split and reference-by-id playlist lesson.
- Keep offline as encrypted local cache plus reconnect reconciliation.
- Keep play-event logging asynchronous and off the playback critical path.
- Keep peer-assisted delivery as a non-default historical alternative.

## Bottom Line

This dataset has the right backbone for a Spotify-style audio streaming
interview. To become book-quality, it needs more quantitative capacity, stronger
state models, entitlement/DRM/search/recommendation depth, and a small diagram
cleanup pass.
