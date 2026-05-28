# Review: Listing Platform - System Design

Reviewed file: `data/book/listing-platform/interview.json`  
Review date: 2026-05-28

## Executive Summary

The listing-platform dataset is now close to flagship quality. The recent
changes addressed most of the earlier high-impact gaps: lifecycle semantics are
first-class, delete/GDPR behavior is explicit, SearchDocs and ranking are
modeled, media processing is part of the pipeline, saved listings/searches,
alerts, reports, analytics, and webhooks are backed by APIs/data/flows, and the
final design now includes several non-happy-path flows instead of only the API
happy path.

The walkthrough now teaches a complete listing platform rather than only an
ingestion pipeline. It still has a clear architecture spine: accept work fast,
normalize/enrich/media-process asynchronously, dedup and fraud-score before
publication, project into search through an outbox, keep seeker reads isolated
from writes, and operate the system by tenant, lag, and replayability.

Remaining work is now mostly polish: fix one renderer-facing edge in the FTP
view, consider whether the final design needs a little more visual decomposition
to stay teachable, and optionally add real icons for specialized technologies
that currently use the generic fallback.

Overall assessment:

| Dimension | Rating | Notes |
|---|---:|---|
| System design soundness | 4.7 / 5 | Strong end-to-end design with lifecycle, media, search, trust, product features, promotions, and operations. |
| Production realism | 4.5 / 5 | Much improved: tombstones, version ordering, webhook retries, media safety, GDPR projection cleanup, DLQ/replay, and hot-partition handling are present. |
| Pedagogical flow | 4.7 / 5 | The step sequence remains excellent and now covers richer product realities. Promotion is useful but needs external readings and careful positioning. |
| Final design coherence | 4.6 / 5 | Final design now closes API, FTP, moderation, delete, read, webhook, and promotion loops. It is coherent but visually dense. |
| Dataset/rendering fit | 4.6 / 5 | JSON is valid; step links, probe links, and technology choices fit the schema. Main remaining issue is one filtered view edge. |

Recommendation: keep the current architecture and step order. Do not rewrite the
case. Focus on the remaining renderer edge, optional icon polish, and keeping
the final design easy to scan.

## What Improved

The recent changes fixed the earlier review's largest concerns:

- Lifecycle is now explicit. Requirements, API, data model, search indexing,
  final flows, and follow-ups all mention update/delete/expire, version
  ordering, tombstones, and stale-event protection.
- The API now includes `DELETE /api/v1/listings/{listingId}`, abuse reports,
  saved searches, and webhook registration.
- The data model expanded from ingestion/trust tables into a real product model:
  `listing_state_transitions`, `outbox_events`, `media_assets`,
  `search_documents`, `saved_searches`, `saved_listings`, `listing_reports`,
  `ai_authoring_events`, `rate_limit_state`, `webhook_deliveries`,
  `listing_promotions`, and `promotion_events`.
- Search relevance is no longer hand-waved. Step 7 has a SearchDoc shape,
  ranking signals, cursor pagination, lifecycle-driven invalidation,
  version-conditional indexing, tombstones, and blue/green reindexing.
- Media is now designed, not just named. `MediaWorker`, `MediaScanner`,
  `MediaStore`, and `MediaCDN` give the case a real story for fetch, scan,
  EXIF/PII stripping, thumbnails, moderation, and deletion.
- Seeker product features are backed by real system pieces: saved listings,
  saved searches, alert worker, reports, analytics, and notification flow.
- Webhooks are treated as a distributed system: HMAC signing, retry, delivery
  history, DLQ, and replay.
- Capacity math is much better: average vs peak seeker QPS is fixed, FTP row
  count is explicit, and index/media/moderation/webhook dimensions are included.
- Final design now has 7 flows: API publish, FTP import, moderation, GDPR
  erasure, seeker read path, webhook delivery, and promotion lifecycle.
- `toProbeFurther` now uses the canonical flat `{"links": [...]}` shape and has
  31 external links with step-level `probeLinks`, including promoted-listing
  ad-ranking, disclosure, CTR prediction, and pacing references.
- `technologyChoices` now covers 12 implementation concerns with self-hosted,
  AWS, GCP, and Azure options, plus trade-off and "makes irrelevant" notes.

These are the right changes. The case now has enough depth for a senior-level
or staff-level discussion without losing the core interview arc.

## Highest-Impact Remaining Issues

### 1. Technology choices are now present; icon coverage is the remaining polish

The new `technologyChoices` section is broad and useful. It covers API/auth,
event bus, listing DB/outbox, object storage, media processing, search, vector
dedup, fraud rules/features, CDN/cache, webhooks, promotion analytics/billing,
and observability.

The icon assignment pass matched most chips, but a small set of specialized
technologies uses the generic `tech.png` fallback: examples include Faiss,
Milvus, Qdrant, Weaviate, ClickHouse, Stripe, Adyen, OpenTelemetry, ClamAV,
FFmpeg, and ImageMagick.

Concrete fix:

- Keep the current choices; they are conceptually useful.
- If visual polish matters, add curated icons or mappings for the common
  fallback terms in `_media/index.yaml`.
- Re-run `_scripts/assign_tech_icons.py` after adding mappings so
  `_media/missing.yaml` is pruned automatically.

This is polish, not a blocker.

### 2. The final architecture is coherent but visually dense

The final design has grown into a realistic platform: ingestion, processing,
media, dedup, fraud, search, reads, alerts, webhooks, analytics, billing, and
promotions. That is appropriate for the case, but it is now a very large final
diagram.

Why it matters:

- The final design may become hard to scan in the explorer.
- Dense diagrams can dilute the teaching value of the step-by-step build-up.
- The final diagram now mixes core platform, read surface, trust-and-safety,
  media, alerts, analytics, billing, and promotions in one view.

Concrete fix:

- Keep the final all-up diagram, but consider adding final-design options or
  subviews by concern: ingestion pipeline, publication/indexing, seeker read
  path, trust/media, and monetization.
- If subviews are not supported in the current renderer, keep the final flows
  as the decomposition mechanism and make sure captions explicitly orient the
  reader.
- Consider whether `MediaCDN` needs to appear in the final view if media
  isolation is important enough to model as a separate high-level node.

This is not an architecture flaw; it is a comprehension and rendering risk.

### 3. One FTP view link will be filtered by the renderer

The structural checks show no missing high-level nodes or missing high-level
link IDs. One view still includes a link whose endpoints are not both present in
that view:

```text
where: ftp-ingestion
link: ratelimit-store
from: RateLimit
to: RateLimitStore
```

If `ftp-ingestion.view.nodes` omits `RateLimit` or `RateLimitStore`, the
renderer's node filtering will drop this edge. That is small, but it produces a
diagram that does not fully match the authored intent.

Concrete fix:

- Either add both `RateLimit` and `RateLimitStore` to the FTP step view, or
  remove `ratelimit-store` from that view if the rate-limit store is not part of
  the FTP diagram.

### 4. Promotion is strong, but it increases the interview's scope

The promotion step is realistic and well-designed, but it changes the case from
"listing ingestion and search" into "listing marketplace with monetization."
That is fine if intentional; it should be handled carefully.

Risks:

- It may crowd the core interview if the intended session is 45-60 minutes.
- It introduces billing, ad disclosure, budget pacing, revenue trade-offs, and
  ad fraud, each of which can become its own interview.
- It currently has no `satisfies.nonFunctional` trace for ad-related concerns
  such as disclosure, billing correctness, or no paid amplification of fraud.

Concrete fix:

- Keep promotion as a later step, but make the interview script explicit that it
  is an advanced extension if time allows.
- Add one non-functional requirement or satisfies entry around promoted-listing
  trust: disclosure, relevance floor, fraud blocking, and async billing.
- Add a follow-up asking how the design changes under auction-time bidding vs
  capped boost.

## System Design Soundness

### Requirements and capacity

The requirements are now strong and specific. They cover:

- SFTP and REST ingestion.
- Manual and AI-assisted authoring.
- Validation, normalization, enrichment, media processing.
- Dedup, fraud, lifecycle, and tombstones.
- Search relevance and freshness.
- Public seeker features.
- Owner/admin workflows.
- Webhooks, idempotency, tenant isolation, audit, GDPR, and callback delivery.

The capacity section is materially improved. It now separates:

- FTP imports: 5k/day, roughly 2k average rows/file, with a heavy tail up to
  10M rows.
- Ingestion writes: 3-4k row events/sec sustained and roughly 30k/sec peak after
  large FTP drops.
- Seeker reads: 580 searches/sec average, 5.8k/sec peak; 58 detail/sec average,
  580/sec peak.
- Search index, enrichment fan-out, media object volume, moderation queue, and
  webhook callback volume.

Remaining capacity caveats:

- `~10M docs, ~10-30 GB` for the active search index may be low if documents
  include long descriptions, rich domain fields, embeddings, replicas, and
  multiple analyzed fields. Either mark it as compressed primary data only or
  widen the estimate.
- Promotion adds read-path analytics and billing event volume. The capacity
  section should mention promoted impressions/clicks if monetization remains a
  full step.
- Saved-search alert matching can be expensive if millions of saved searches
  exist. The current model is enough for an interview, but a capacity line for
  active saved searches would help.

### API

The API now supports the promised behavior well:

- Create/update/delete/bulk are asynchronous and status-driven.
- Delete emits tombstones and erases PII/media.
- Search uses cursor-style pagination.
- Reports, saved searches, and webhooks are first-class.
- Webhook signing and retry semantics are named.

Recommended polish:

- Show `source_version` or `external_updated_at` in the sample PATCH request,
  not only in the description.
- Add an endpoint or admin action for buying/pausing promoted listings if
  promotion remains a full step.
- Consider a GET for saved listings/searches if the API section is intended to
  be user-facing, not only write-facing.

### Data model

The data model now supports the promised behavior far better than before. The
most important additions are:

- `listing_state_transitions` for state-machine audit.
- `outbox_events` for DB-to-event consistency.
- `media_assets` for media lifecycle.
- `search_documents` for projection/ranking.
- `saved_searches`, `saved_listings`, and `listing_reports`.
- `ai_authoring_events`.
- `rate_limit_state`.
- `webhook_deliveries`.
- `listing_promotions` and `promotion_events`.

Recommended polish:

- Add explicit uniqueness/ordering constraints in prose where they matter:
  `(owner_id, external_listing_id)`, `(listing_id, version)`, outbox ordering,
  and webhook idempotency keys.
- Clarify whether `promotion_events` is a high-volume append stream/table or an
  analytics topic. At 50M searches/day, this should not be a small relational
  table in the request path.
- Clarify retention for `audit_log`, `promotion_events`, raw files, and media
  originals after GDPR erasure.

### Architecture

The architecture is now production-shaped:

- Ingress paths converge on the same versioned event model.
- Pipeline stages are independently scalable and replayable.
- Media has separate processing and serving concerns.
- Dedup and fraud happen before search publication.
- SearchDocs are derived from source-of-truth state.
- Reads are cache-heavy and isolated from writes.
- Alerts, analytics, webhook delivery, and promotion lifecycle are modeled.
- Rate-limit state and hot-partition handling are explicit.

Remaining architecture caveats:

- The diagram is large enough that the final view may need subviews to remain
  readable.
- Promotion and billing add a separate correctness domain. Keep them async and
  isolated from seeker search latency, as the current design does.
- Event schema evolution is named, but a reader may still benefit from a compact
  example of compatible vs incompatible event change.

## Step-by-Step Pedagogical Review

### Step 1: Naive synchronous create-and-index

Still a strong baseline. The new decision prompt correctly adds stale updates,
so the baseline exposes consistency risk as well as latency and availability.
The added probe links are relevant.

Improvement: none required. Keep it short so it does not compete with the real
design.

### Step 2: API ingestion

This step is now much stronger. "Accept fast, publish versioned events" sets up
the entire lifecycle story. Idempotency, owner scoping, per-owner rate limits,
correlation IDs, versioning, schema evolution, and webhooks are introduced at
the right time.

Improvement: show the version/source timestamp in the concrete API sample.

### Step 3: FTP ingestion

Good production shape: raw file store, duplicate file hash, streaming parser,
full vs incremental semantics, row events, per-row failures, checkpointing, and
archive handling.

Improvement: fix the `ratelimit-store` view edge or include its endpoint nodes.
Also consider making tenant-level import concurrency visible in the view if it
is important to the step.

### Step 4: Async pipeline

The title now explicitly includes media, which matches the updated
requirements. Enrichment provenance, AI authoring guardrails, schema evolution,
media scanning, caching, and failure classification are all useful.

Improvement: this is now one of the densest steps. It works, but keep the
diagram/caption focused so media and AI do not hide the core normalize/enrich
pipeline lesson.

### Step 5: Duplicate detection

Still one of the best steps. Exact-first/fuzzy-second, blocking, ANN, reversible
groups, update invalidation, and human review are all strong and realistic.

Improvement: no structural change needed. The probe links are now useful and
well-targeted.

### Step 6: Fraud prevention

The fraud step remains strong and now has options. Conservative hold vs
permissive publish teaches a real product/trust trade-off. The moderation SLA
and backlog metric are valuable additions.

Improvement: promotion introduces a new fraud interaction. The step already
connects later through promotion, but a short forward reference would help:
fraud state will also block paid boost.

### Step 7: Search indexing

This step is now a major strength. SearchDoc shape, tombstones, version
conditional upserts, ranking signals, cursor pagination, cache invalidation, and
blue/green reindexing are all exactly the right concepts.

Improvement: check the search index size estimate and consider adding a small
note about index aliases / zero-downtime schema migration in the data model or
deep dive.

### Step 8: Promoted listings

This is a strong advanced addition. It avoids the obvious bad design ("paid
always wins") and instead treats promotion as one capped ranking term with a
relevance floor, slot-share cap, disclosure, async billing, pacing, and fraud
override.

Improvements:

- The promoted-listing `probeLinks` and external references are now in place.
- Make the interview script explicit that this is an advanced extension if time
  is short.
- Consider adding a non-functional requirement for paid-result trust.

### Step 9: Seeker read path

The seeker-read step is now much better grounded. It includes saved listings,
saved searches, alerts, report-listing, analytics, personalization boundaries,
stale-but-served semantics, CDN/query cache/BFF layering, and notification flow.

Improvement: mention how promoted labels interact with CDN caching: labeled,
non-personalized results can cache, but personalization and per-user ad
targeting cannot.

### Step 10: Scale, multi-tenancy, and reliability

This remains a strong operational close. It now includes hot-partition
mitigation, event schema evolution, RPO/RTO, rate-limit store state, webhook
DLQs, and SLO-mapped observability.

Improvement: add a brief note on promotion/billing metrics here if promotion is
part of the mainline: overspend, billing backlog, promotion exhaustion lag, and
organic CTR regression.

## Final Design Review

The final design is now coherent and much more complete than the earlier
version. It includes:

- API publish to seeker-visible flow.
- FTP import to row events, status, and callback.
- Moderation approve/reject flow.
- Delete/GDPR erasure through projections.
- Seeker read path through CDN/query cache/search/DB.
- Webhook signing/retry/DLQ/replay.
- Promotion activation, boost projection, billing, and exhaustion.

This closes the loops that previously existed only in prose. The final design
now demonstrates the system's real behavior under async workflows, not just a
happy path.

Remaining concern: the all-up final diagram is necessarily busy. The final flows
do a good job decomposing it, but if the rendered SVG becomes hard to scan,
consider adding concern-specific final views or using captions to guide the
reader.

## Concept Introduction and Learning Flow

Concept staging is excellent:

- Coupling and stale updates in the naive design.
- Idempotency, versioned events, webhooks, and schema evolution at API ingress.
- Streaming, partial failure, full/incremental imports, and compressed-file
  handling at FTP ingress.
- Consumer groups, enrichment provenance, AI guardrails, media processing, and
  event compatibility in the async pipeline.
- Exact/fuzzy dedup, blocking, ANN, and reversible grouping.
- Rules/ML fraud, feature store, moderation SLA, and fallback policy.
- Outbox, SearchDoc, tombstones, blue/green reindex, cursor pagination, and
  ranking.
- Promotion as a bounded ranking signal with legal/trust constraints.
- CDN/BFF/query cache, saved-search alerts, reports, and stale-but-served reads.
- Tenant partitioning, hot-partition mitigation, DLQ/replay, RPO/RTO, and SLO
  observability.

The only learning-flow risk is scope expansion. The dataset now covers enough
material for a long interview or a chapter, but probably too much for a short
whiteboard session unless the interviewer skips some extension material.

## Step-to-Final-Design Coherence

| Step | Carries into final design | Coherence notes |
|---|---|---|
| Naive | Baseline only | Good contrast; now exposes stale update risk too. |
| API ingestion | `OwnerAPI`, `IAM`, `RateLimit`, `RateLimitStore`, `Validator`, `EventBus`, `Webhooks` | Strong foundation for versioned lifecycle. |
| FTP ingestion | `FTP`, `FileStore`, `FileWatcher`, `Parser`, `ImportDB`, `DLQ` | Strong; one small view-edge issue remains. |
| Async pipeline | `Normalizer`, `Enricher`, `ModelSvc`, `GeoSvc`, `AISvc`, `MediaWorker`, `MediaScanner`, `MediaStore`, `ListingDB`, `Outbox` | Strong, but dense. |
| Dedup | `DedupSvc`, `IDMap`, `HashIdx`, `ModQueue` | Excellent link from duplicate groups to SearchDocs. |
| Fraud | `FraudSvc`, `RulesEngine`, `FeatureStore`, `ModQueue`, `Admin` | Strong; promotion now correctly depends on fraud state. |
| Search indexing | `Outbox`, `Indexer`, `SearchIdx`, `QueryCache` invalidation | Very strong; core consistency boundary is clear. |
| Promotion | `PromotionSvc`, `PromotionDB`, `BillingSvc`, `Analytics`, `SearchIdx` | Strong advanced extension; needs probe links and implementation choices. |
| Seeker read | `Seeker`, `Web`, `CDN`, `PublicAPI`, `BFF`, `QueryCache`, `AlertWorker`, `Notif`, `Analytics` | Strong product-feature closure. |
| Scale | `Obs`, `DLQ`, hot partitioning, rate limiting, schema evolution, RPO/RTO | Good operational closure. |

The final design now follows from the steps. The earlier mismatch between
requirements and architecture is largely gone.

## Realism Compared With Production Systems

The current design has several production-realistic qualities:

- It has both request idempotency and logical-listing idempotency.
- It treats update ordering as a first-class problem.
- It uses raw-file storage for replay.
- It handles row-level import failure.
- It keeps media safety separate from generic enrichment.
- It makes duplicate grouping reversible.
- It uses human review where automation is risky.
- It keeps SearchIdx as a projection.
- It handles deletes with tombstones and projection cleanup.
- It avoids billing in the search request path.
- It has webhook retries and replay.
- It has per-tenant throttling and hot-owner mitigation.

Remaining production caveats:

- Promotion/ad-tech details can get much deeper: auctions, disclosure,
  targeting, billing reconciliation, click fraud, and campaign pacing. The
  current capped-boost design is a reasonable interview scope, but should be
  presented as such.
- Search index storage and media/CDN cost estimates may need widening if the
  dataset wants production-grade capacity math.
- GDPR retention policy is directionally correct, but retention durations and
  audit anonymization boundaries are still intentionally high-level.
- Saved-search alert matching can become a full retrieval problem at large
  scale; the current AlertWorker model is a good start but not the final word.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Top-level `toProbeFurther.links[]` uses the canonical flat shape.
- There are 31 external links.
- All current `step.probeLinks[]` values resolve to link IDs.
- The promotion step now has targeted `probeLinks`.
- There are no duplicate link IDs or duplicate URLs.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- High-level view node and link IDs resolve.
- One view edge will be filtered because `ftp-ingestion` includes
  `ratelimit-store` without both endpoint nodes in that view.
- `technologyChoices` is present with 12 concerns and assigned chip icons.
- No docs rebuild is required for this `REVIEW.md` update alone.

## Recommended Edits, Prioritized

### P1: Fix small correctness/schema gaps

- Fix the `ftp-ingestion` view's `ratelimit-store` edge by adding endpoint nodes
  or removing the link.
- Add a promotion-related non-functional satisfies item if promoted listings are
  a main requirement.

### P2: Polish book-depth metadata

- Add curated icon mappings for common `tech.png` fallback terms such as Faiss,
  Qdrant, ClickHouse, Stripe, and OpenTelemetry.
- Re-run the tech-icon assignment script after adding any mappings.
- Review whether any `technologyChoices` concern should be split if the rendered
  section feels too dense.

### P3: Improve teaching ergonomics

- Make the interview script identify promotion as an advanced/time-permitting
  extension.
- Consider concern-specific final subviews if the final design diagram is too
  dense in the browser.
- Add a capacity line for active saved searches and promotion impression/click
  volume.
- Widen or qualify the SearchIdx size estimate.

## What Not To Change

- Do not change the core step order. The build-up is still one of the dataset's
  strengths.
- Do not remove lifecycle, media, SearchDoc, or product-feature coverage. These
  were important fixes.
- Do not make promotion a master-switch ranking override. The capped-boost
  design is the right teaching point.
- Do not put billing synchronously on the read path.
- Do not collapse dedup and fraud; they teach different failure modes.
- Do not remove the final non-happy-path flows. They make the system credible.

## Bottom Line

The current listing-platform dataset is much stronger than the version the
previous review described. It now has realistic lifecycle semantics, media
safety, SearchDocs, product-feature backing, webhook delivery, promotion
workflow, rich final flows, and credible external reading links.

The remaining work is targeted: fix one small view edge, optionally improve
technology icon coverage, and manage the visual/teaching density. The dataset
now stands comfortably as a flagship book case.
