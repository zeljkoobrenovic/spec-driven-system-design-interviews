# Review: Listing Platform - System Design

Reviewed file: `data/book/listing-platform/interview.json`  
Review date: 2026-05-28

## Executive Summary

This is a strong flagship-style interview dataset. The core framing is credible:
a high-throughput, multi-tenant listing ingestion platform feeding a
low-latency seeker read surface. The walkthrough does a good job of starting
from a synchronous baseline, then replacing each risky coupling with a
production pattern: accept-fast APIs, row-level FTP parsing, partitioned event
pipeline, enrichment with provenance, exact plus fuzzy deduplication, fraud
review, outbox-driven search indexing, CDN/BFF reads, and tenant-aware
operations.

The current version is usable and teaches the right interview instincts. The
remaining gaps are not about the main spine of the architecture; they are about
making the product semantics and production details as strong as the pipeline.
The biggest missing pieces are first-class update/delete lifecycle semantics,
SearchDoc/ranking detail, media ingestion, explicit support for seeker saved
listings/alerts/reporting, and book-level implementation trade-offs.

Overall assessment:

| Dimension | Rating | Notes |
|---|---:|---|
| System design soundness | 4.2 / 5 | Strong async ingestion, dedup, fraud, indexing, read isolation, and operations. Needs stronger lifecycle, media, search relevance, and product-feature backing. |
| Production realism | 4.0 / 5 | Good failure and replay posture. Missing delete/tombstone flow, media safety pipeline, rate-limit state, event schema evolution, and GDPR retention detail. |
| Pedagogical flow | 4.5 / 5 | The step order is excellent and each step mostly solves the previous exposed risk. A few concepts are introduced in prose but not backed by state or flows. |
| Final design coherence | 4.2 / 5 | Final view integrates the main components well. Final flow is only the API happy path and should show FTP, moderation, callbacks/status, and CDN read behavior. |
| Dataset/rendering fit | 3.9 / 5 | JSON is valid and main view references resolve. Some option views will render with missing edges; book wrap-up metadata is thinner than comparable flagship cases. |

Recommendation: keep the architecture spine and step order. Focus edits on
making lifecycle semantics, search/media/product requirements, and final flows
more explicit.

## What Works Well

- The core system tension is clear: bursty owner writes and expensive processing
  must not endanger always-on seeker search.
- The requirements and capacity sections are concrete enough to drive design:
  10M active listings, 500M historical, 50k owners, 5k FTP imports/day, 100M API
  writes/month, 50M searches/day, and a 5-minute freshness target.
- The walkthrough starts with a deliberately fragile synchronous baseline, then
  adds decoupling one problem at a time.
- API ingestion correctly uses `202 Accepted`, correlation IDs, idempotency, and
  owner-scoped authentication/rate limiting.
- FTP ingestion is production-shaped: per-owner SFTP, raw object storage,
  `import_jobs`, row-level parsing, partial failures, DLQ, and checkpointed
  recovery.
- Enrichment has good nuance: separate owner-provided fields from enriched
  values, preserve model/source provenance, classify failures, and cache
  expensive calls.
- Dedup is one of the strongest steps. It separates deterministic
  `(owner_id, external_listing_id)` lookup from fuzzy blocking plus ANN and uses
  reversible `duplicate_group_id` rather than destructive merging.
- Fraud is realistic enough for an interview: cheap rules first, ML scoring,
  feature store, human moderation, explanation, fallback policy, and feedback
  loop.
- Search indexing teaches the right pattern: database as source of truth,
  transactional outbox, idempotent indexer, and blue/green reindex.
- The read path makes the central SLO explicit: ingestion can be stale or down,
  but seeker reads should continue serving last-known good data.
- Step 9 adds the operational layer that many interview answers miss: per-tenant
  partitioning, fair scheduling, per-stage lag, DLQ ownership, replay, disaster
  recovery, and observability.

## Highest-Impact Issues

### 1. Update, delete, and lifecycle semantics are under-specified

The requirements and API promise create, update, partial-update, delete, and
bulk ingestion, but the walkthrough mostly teaches create/upsert. The data model
has a rich `state` enum, but the state machine is not made operational.

Why this matters:

- Listing platforms are dominated by churn: price changes, owner edits, paused
  listings, expirations, removed duplicates, rejected fraud, and hard deletes.
- Search correctness depends on tombstones and version ordering as much as on
  inserts.
- GDPR deletion conflicts with audit/replay/history unless the retention story
  is explicit.
- FTP full-snapshot imports need semantics for "missing from today's file":
  expire, pause, delete, or leave unchanged.

Concrete fixes:

- Add a `DELETE /api/v1/listings/{listingId}` or equivalent unpublish endpoint
  to the API section.
- Define lifecycle events such as `listing.upserted`, `listing.unpublished`,
  `listing.deleted`, `listing.expired`, `listing.rejected`, and
  `listing.restored`.
- Add a short state machine note: which states are searchable, which are
  owner-visible, which emit outbox rows, and which can be reversed.
- Add per-listing version or source sequence ordering to prevent older FTP/API
  events from overwriting newer edits.
- Explain how deletes propagate to `SearchIdx`, `MediaStore`, caches, and
  duplicate/fraud indexes.
- Clarify GDPR behavior: tombstone metadata can remain for audit/idempotency,
  while PII/contact data and media are erased or anonymized.

This is the largest realism gap because it affects almost every stage after API
ingestion.

### 2. Search relevance and the SearchDoc shape are too thin

The requirement promises keyword, filter, geo, and ranking by relevance,
freshness, and quality. The design correctly introduces a search index and
read-path caching, but it does not describe what gets indexed or how results are
ranked.

Why this matters:

- A listing platform's user experience is mostly search quality.
- The final architecture includes `SearchIdx`, `QueryCache`, and `BFF`, but not
  a SearchDoc contract or ranking pipeline.
- Dedup, fraud, quality score, owner reputation, recency, location, category,
  and personalization are all potential ranking/filtering signals, but the
  design does not connect them.

Concrete fixes:

- Add a `search_documents` data-model entry or a SearchDoc deep dive with:
  `listing_id`, category-specific fields, geo point, normalized title/body,
  facets, price/salary bands, quality score, fraud status, duplicate group,
  owner reputation, publish timestamp, and media thumbnail refs.
- Add an explicit ranking note: lexical relevance plus filters plus geo distance
  plus freshness/quality/owner reputation, with business rules for hidden
  duplicates and fraud-held records.
- Explain pagination stability: cursor/search-after beats page-number offsets
  under changing indexes.
- Add cache invalidation rules for updates/deletes and why short TTLs are enough
  for search while detail pages can cache longer.

This could be a deep dive in step 7 or step 8 rather than a full new step.

### 3. Media ingestion is represented but not designed

The API accepts `media` URLs and the architecture has `MediaStore`, but there is
no real media pipeline.

Why this matters:

- In real listing platforms, photos and attachments are core product content.
- Media is a security boundary: remote fetches, malware scanning, EXIF/PII
  stripping, image moderation, copyright abuse, and broken links matter.
- Media affects search and detail latency through thumbnails, CDN invalidation,
  and detail page composition.

Concrete fixes:

- Add a short media sub-flow: fetch/copy owner-provided URLs, virus scan,
  normalize/transcode, generate thumbnails, store immutable media objects, and
  write refs to the listing row/SearchDoc.
- Define whether media processing blocks publication or allows partial publish
  with missing images.
- Add moderation/fraud signals from image reuse or unsafe content.
- Add media deletion semantics for listing delete and GDPR erasure.

This does not need to dominate the interview, but it should not remain a single
box.

### 4. Several named product requirements are not backed by APIs or data

The functional requirements include saved listings, alerts, report-listing,
owner analytics, import status, error reports, and webhook callbacks. Some are
mentioned in prose or represented as nodes, but they are not consistently backed
by API/data/flow support.

Specific gaps:

- `saved listings` and `alerts` appear in requirements, but there is no data
  model for saved searches/listings, no alert evaluation path, and no API.
- `report-listing` appears in requirements, but there is no abuse-report API,
  table, moderation queue path, or state transition.
- Owner analytics are listed in requirements and `Analytics` exists in the read
  view, but the final design omits `Analytics` and there is no event flow or
  storage model for it.
- `Webhooks` and `Notif` are in the final diagram, but completion callbacks are
  not shown in the main flows and `Notif` is not explained.

Concrete fixes:

- Either explicitly scope these product features out, or add lightweight support
  for each requirement.
- For saved/alerts: add `saved_searches`, `saved_listings`, and an alert worker
  that consumes newly indexed listings or periodic search deltas.
- For report-listing: add `POST /api/v1/listings/{id}/reports`, a
  `listing_reports` table, and a moderation route.
- For owner analytics: show analytics as a derived projection from read/search
  events, not as a request-path dependency.
- For webhooks: show import/job completion and listing-status callback delivery
  with retry, signing, and dead-letter behavior.

The current design is strongest as an ingestion/search platform. These product
features should be either first-class or clearly out of scope.

### 5. Manual and AI-assisted authoring needs stronger state and guardrails

AI-assisted authoring is a requirement and appears in the admin UI and
enrichment deep dive. The current treatment is good as a concept, but thin as a
production design.

Why this matters:

- Interactive AI suggestions have different latency, cost, safety, and audit
  constraints than async enrichment.
- Accepted suggestions become owner-visible, seeker-visible content.
- Policy checks and translations can create legal and trust-and-safety risk.

Concrete fixes:

- Add a small `ai_suggestions` or `authoring_events` model with prompt version,
  model version, input hash, suggestion type, confidence, accepted/rejected flag,
  and actor.
- Clarify that AI suggestions are not automatically published unless accepted by
  an owner/admin or cleared by policy.
- Add cost/fallback behavior: cached suggestions by content hash, vendor
  timeouts, degradation to manual authoring.
- Make privacy explicit: redact contact data before LLM calls or use an
  approved model boundary.

This could stay as a deep dive in step 4, but it needs one state shape.

### 6. Book-level implementation trade-offs are missing

Unlike the strongest book datasets, this one has no `technologyChoices` section
and no `toProbeFurther` links.

Why this matters:

- This case introduces many implementation concerns where readers expect
  concrete choices: event bus, SFTP/object storage, relational source of truth,
  search cluster, ANN index, feature store, rules engine, geocoder, CDN/cache,
  webhook delivery, observability, and media pipeline.
- The book group benefits from showing self-hosted vs cloud-native options and
  what managed services make unnecessary.

Concrete fixes:

- Add `technologyChoices` entries for at least:
  Event bus/stream, listing DB, object store/SFTP landing zone, search index,
  vector/ANN dedup, feature store, rules engine, CDN/cache, webhook delivery,
  observability, and media processing.
- Add `toProbeFurther` links or whatever the current dataset convention uses
  for further reading.
- Consider running the existing tech icon assignment workflow after adding the
  choices.

This is not required for JSON validity, but it is important for book-quality
depth.

### 7. Some option diagrams will render with missing edges

The main structured views reference valid high-level nodes and links, but some
option views include links whose endpoints are not present in that option's
`view.nodes`. The renderer filters edges touching hidden nodes, so these option
diagrams will look sparse or disconnected.

Concrete examples:

- Step 3, "Load entire file into memory": the option includes `ftp-filestore`
  but omits `FileStore` from `view.nodes`.
- Step 4, "Choreography": the option removes `Enricher` but still uses
  `bus-enricher`, `enricher-modelsvc`, `enricher-geosvc`, and
  `enricher-listingdb`, all of which touch `Enricher`.
- Step 8, "CDN + BFF + query cache": the option omits `Web` and `PublicAPI` but
  includes `seeker-web`, `web-cdn`, `cdn-publicapi`, and `publicapi-bff`.
- Step 8, "Public API hits the search index directly": the option uses links
  touching `Web`, `CDN`, and `BFF` while the option only includes `Seeker`,
  `PublicAPI`, and `SearchIdx`.

Concrete fixes:

- Add the missing endpoint nodes to those option views, or replace the links
  with links whose endpoints are in the option node list.
- For the choreography option, consider adding explicit worker nodes rather than
  reusing `Enricher` links while omitting `Enricher`.

This is a renderer-facing issue, not a conceptual architecture issue.

## System Design Soundness

### Requirements and scope

The scope is ambitious but coherent. It combines two owner write surfaces
(SFTP/API), a manual/admin surface, trust-and-safety, enrichment, deduplication,
search indexing, and seeker reads. That is a realistic listing-platform
interview.

The strongest requirement is read/write isolation: seeker search and detail
should remain available even when ingestion degrades. The steps consistently
preserve that requirement.

The weakest requirement handling is feature traceability. The dataset promises
saved listings, alerts, report-listing, owner analytics, delete, and GDPR. Those
are important enough that the design should either support them or explicitly
mark them as follow-up scope.

### Capacity analysis

The capacity section is directionally good:

- 50M searches/day is about 580 searches/sec average; with 10x peak, design for
  roughly 5.8k searches/sec before cache offload.
- 5M details/day is about 58 details/sec average; with 10x peak, design for
  roughly 580 details/sec.
- 100M API writes/month is only about 40 writes/sec average, so FTP imports and
  row explosion dominate ingestion.
- Pipeline work is correctly multiplied by stage count, not just by ingress
  writes.

Two fixes would make the math stronger:

- The `capacityDiagram` says `~600 searches/s + 60 detail/s peak`, but those are
  average numbers for 50M and 5M per day. Rename them to average or change them
  to roughly 10x peak.
- State an assumed average rows/import for the 5k FTP imports/day. Without that,
  the `~3-4k/s sustained, 10x peak` ingestion estimate is plausible but not
  auditable.

Additional useful capacity lines:

- Search index size and shard estimate: active documents, replicas, refresh
  interval, index write QPS.
- Enrichment fan-out: geocode/model/translation calls per listing and cache hit
  assumptions.
- Media volume: average images/listing, thumbnail count, storage, CDN egress.
- Moderation volume: expected fraud/dedup review rate and queue SLA.
- Webhook callback volume and retry backlog.

### API

The API section has the right high-level shape. `POST /listings` and bulk
returns `202 Accepted`, not a misleading synchronous "created and searchable"
response. Status endpoints expose the async nature of the pipeline.

Recommended improvements:

- Add delete/unpublish explicitly.
- Include a source version, external update timestamp, or monotonic sequence
  field so the pipeline can order conflicting owner events.
- Clarify whether `PATCH` re-runs the whole pipeline or only affected stages
  such as search indexing, fraud, dedup, or media.
- Add webhook registration/signature fields or point to owner integration
  config in `listing_owners`.
- Improve search pagination from `page=1` to cursor/search-after semantics for
  large result sets.
- Add report-listing and saved-listing/saved-search endpoints if those
  requirements remain in scope.

### Data model

The data model is solid for ingestion and trust-and-safety:

- `listings` has versioning, state, enrichment scores, duplicate group, hash,
  embedding, and encrypted contact data.
- `import_jobs` and `import_records` support partial failure and error reports.
- `enrichment_results` preserves model output history.
- `fraud_decisions`, `duplicate_candidates`, and `audit_log` support explainable
  review and post-incident analysis.
- `external_id_map` is the right deterministic dedup table.

Recommended additions:

- Outbox table shape. The architecture relies on `Outbox`, but the data model
  does not show outbox rows, sequence numbers, processed state, or trim policy.
- SearchDoc/search projection shape.
- Media asset table or media processing state.
- Listing state transition/event table, especially if one-row-per-version in
  `listings` is kept.
- Rate-limit/quota state for per-owner token buckets and import concurrency.
- Saved listings/searches, alerts, report-listing, owner analytics, and webhook
  delivery attempts if those product requirements remain in scope.
- GDPR erasure/anonymization markers and retention policy for historical rows.

### Architecture

The final architecture has a credible component map. The best choices are:

- Separate ingress surfaces converge on one event bus.
- Normalization, enrichment, dedup, fraud, and indexing are independent stages.
- Listing DB remains the source of truth.
- Search is a projection, not a truth store.
- Seeker reads have no synchronous dependency on write processing.
- DLQ, observability, replay, and tenant isolation appear as first-class
  operational concerns.

The main architecture gaps are:

- `RateLimit` is modeled as a stateless service, but per-owner rate limiting and
  fair scheduling need state.
- `MediaStore` appears without media workers, scanner, thumbnailer, or deletion
  lifecycle.
- `Analytics`, `Webhooks`, and `Notif` appear but are not integrated into the
  final flow.
- Event schema/versioning is not discussed. A multi-stage pipeline needs
  backwards-compatible event evolution and replay-safe consumers.
- Cross-region failover is mentioned, but RPO/RTO and active-active vs
  active-passive behavior are not defined. For an interview this can stay
  high-level, but the current text could be more explicit.

### Reliability, consistency, and operations

The dataset is above average here. It already includes raw file replay,
checkpointed parsing, DLQ, idempotency, outbox, blue/green reindex, per-stage
lag, and per-tenant isolation.

Recommended improvements:

- Add poison-message policy per stage: skip, hold, retry, DLQ, or quarantine
  tenant.
- Add event versioning and replay compatibility.
- Add index lag and status callback semantics to the final flow.
- Define how duplicate/fraud decisions are replayed after a bad model/rule.
- Define cache invalidation for publish/update/delete.
- Add an explicit webhook retry/DLQ loop for owner callbacks.

### Security, privacy, and compliance

Good starting points exist: authentication, RBAC, audit log, encrypted contact
data, GDPR mention, fraud review, and per-owner isolation.

Recommended additions:

- SFTP credential/key rotation and per-owner directory isolation.
- Webhook signing and replay protection.
- PII redaction before AI/model/geocoder calls where possible.
- Media malware scanning and EXIF stripping.
- Tamper-evident audit log or append-only audit storage.
- GDPR erasure flow that handles listings, media, search index, cache, feature
  store, and historical audit rows.

## Step-by-Step Pedagogical Review

### Step 1: Naive synchronous create-and-index

This is a good baseline. It is intentionally wrong in the right ways: API
latency, external dependencies, search coupling, FTP burst failure, and
availability collapse. The recap sets up the need for async acceptance.

Improvement: mention that the naive flow also cannot handle updates/deletes
consistently, not just slow creates.

### Step 2: API ingestion

This step makes the key interview move: accept fast, authenticate, rate-limit,
validate shape, claim idempotency, publish to a bus, return `202`.

Strong concepts:

- Idempotency key vs logical listing identity.
- Per-owner rate limits.
- Correlation ID for async status.

Improvements:

- Introduce event version/sequence here, because updates/deletes later depend on
  ordering.
- Clarify where idempotency-key state is stored.
- Show webhook registration/delivery as a later concern if `ownerapi-webhooks`
  remains in the diagram.

### Step 3: FTP ingestion

This is a strong production step. It teaches raw file landing, file watcher,
row-level parsing, `import_jobs`, per-row DLQ/error reports, and checkpointed
recovery.

Improvements:

- Define full vs incremental file semantics.
- Add behavior for compressed files, malformed archives, and duplicate file
  detection.
- Fix the option diagram edge that references `FileStore` while the option omits
  `FileStore`.
- Add a note on tenant-level import concurrency so a 10M-row file does not own
  all parser capacity.

### Step 4: Async pipeline

This is a useful consolidation step. It introduces normalization, enrichment,
provenance, failure classification, model versioning, and AI-assisted authoring.

Strong concepts:

- Pipeline stage as consumer group.
- Provenance on enriched fields.
- Transient/permanent/non-blocking failure classes.

Improvements:

- This step is dense: normalize, enrich, persist, provenance, AI authoring, and
  partial failure all land together. It works, but the AI authoring part needs a
  small state model so it does not feel bolted on.
- Add event schema/versioning or consumer compatibility as a concept.
- Fix the choreography option diagram: it removes `Enricher` but uses links that
  all touch `Enricher`.

### Step 5: Duplicate detection

This is one of the best steps in the dataset. It gives a realistic two-layer
strategy and avoids destructive merges. The trap about auto-merging across
owners is especially important.

Improvements:

- Explain candidate invalidation/reprocessing when a listing is updated.
- Define how duplicate grouping affects SearchDoc publication and canonical
  selection.
- Add a note about domain-specific blocking keys: jobs, real estate, and
  vehicles will not block on identical fields.

### Step 6: Fraud prevention

The fraud step is realistic and teachable. Rules plus ML plus human review is
the right shape, and the degradation policy is much better than "publish all" or
"block all".

Improvements:

- Add a moderation SLA/backlog metric.
- Clarify how moderator decisions transition listing state and trigger outbox
  rows.
- Include image/media signals once media is modeled.
- Consider an option comparison: conservative hold policy vs permissive publish
  and retroactive takedown.

### Step 7: Search indexing

This step teaches the right consistency boundary. The transactional outbox is
the correct answer to "DB updated but index missed it", and blue/green reindex
is exactly the right production pattern.

Improvements:

- Add outbox row shape to the data model.
- Add SearchDoc shape and delete/tombstone behavior.
- Explain ordering: idempotent upsert by `listing_id` is not enough if stale
  updates can arrive out of order.
- Connect dedup/fraud/listing states to whether a document is indexed, hidden,
  deleted, or replaced.

### Step 8: Seeker read path

This step correctly focuses on read/write isolation, CDN caching, BFF
composition, query cache, and stale behavior. The trap about personalized CDN
caching is useful.

Improvements:

- Fix option diagrams with omitted `Web`, `CDN`, `PublicAPI`, and `BFF`
  endpoints.
- Add saved listings/saved searches/alerts/report-listing support or explicitly
  move them to follow-ups.
- Distinguish search result cacheability from detail page cacheability in
  invalidation rules.
- Add mobile vs web response differences only if the BFF concept is meant to be
  tested.

### Step 9: Scale, multi-tenancy, and reliability

This is a strong wrap-up architecture step. It teaches that "add workers" is
not enough: tenant partitioning, fair scheduling, DLQ ownership, replay, and
SLO-driven observability are the real production answer.

Improvements:

- Add rate-limit/fair-scheduler state shape.
- Add hot-partition mitigation, not just partitioning by owner.
- Add RPO/RTO expectations for DB failover and index rebuild.
- Mention event schema evolution and backwards-compatible consumers during
  replay.

## Final Design Review

The final design description integrates the main steps well:

- API and FTP ingress converge on a partitioned event bus.
- Pipeline stages are independently scalable.
- Enrichment, dedup, and fraud are before publication.
- Listing DB is authoritative.
- Outbox plus indexer projects to search.
- CDN/BFF read path is decoupled from ingestion.

The final view is broad and mostly coherent. It includes the expected actors,
clients, gateways, pipeline workers, storage, search, cache, callbacks, and
observability.

The final flow is too narrow. It only shows partner API POST to seeker-visible
happy path. For a dataset this rich, the final design should include additional
flows or branches:

- FTP import: file drop, raw storage, parsing, row events, import status,
  partial failure report, and owner callback.
- Fraud/moderation: hold, moderator approve/reject, state transition, outbox,
  and owner notification.
- Delete/update: owner update/delete, version ordering, tombstone outbox, index
  delete, cache invalidation.
- Seeker read: CDN hit/miss, query cache hit/miss, BFF search/detail
  composition, and stale fallback.
- Webhook callback: status completion delivery, signing, retry, and DLQ.

The final design is directionally right. It just needs to demonstrate the
non-happy paths that the earlier steps worked hard to introduce.

## Concept Introduction and Learning Flow

Concept staging is a major strength. The learner meets concepts close to the
step that needs them:

- Synchronous coupling in the naive step.
- Idempotency and correlation IDs at API acceptance.
- Row-level partial failure at FTP ingestion.
- Consumer groups and provenance at enrichment.
- Blocking and ANN at dedup.
- Rules, ML, feature store, and explanation at fraud.
- Outbox and blue/green index swap at search indexing.
- CDN, query cache, BFF, and stale-while-revalidate at reads.
- Tenant partitioning, fair scheduling, DLQ, and replay at scale.

Missing or underdeveloped concepts:

- Listing lifecycle state machine.
- Event versioning and replay compatibility.
- SearchDoc design and ranking signals.
- Tombstones and delete propagation.
- Media processing and media safety.
- Rate-limit/quota state.
- GDPR erasure vs audit retention.
- Webhook delivery semantics.
- Saved-search alert evaluation.

Most of these can be added as concepts, deep dives, or data model entries rather
than new top-level steps.

## Step-to-Final-Design Coherence

| Step | Carries into final design | Coherence notes |
|---|---|---|
| Naive | Baseline links remain as contrast only | Good teaching baseline; should also expose update/delete failure. |
| API ingestion | `OwnerAPI`, `IAM`, `RateLimit`, `Validator`, `EventBus`, `Webhooks` | Strong. Needs idempotency/rate-limit state and update ordering. |
| FTP ingestion | `FTP`, `FileStore`, `FileWatcher`, `Parser`, `ImportDB`, `DLQ` | Strong. Full/incremental import semantics should be explicit. |
| Async pipeline | `Normalizer`, `Enricher`, `ModelSvc`, `GeoSvc`, `AISvc`, `ListingDB`, `Outbox` | Strong. AI authoring needs state and guardrails. |
| Dedup | `DedupSvc`, `IDMap`, `HashIdx`, `ModQueue` | Excellent. Connect grouping to SearchDoc publication. |
| Fraud | `FraudSvc`, `RulesEngine`, `FeatureStore`, `ModQueue`, `Admin` | Strong. Add state transition/outbox behavior after review. |
| Search indexing | `Outbox`, `Indexer`, `SearchIdx` | Strong. Add SearchDoc/tombstone/version handling. |
| Seeker read | `Seeker`, `Web`, `CDN`, `PublicAPI`, `BFF`, `QueryCache` | Strong read isolation. Needs saved/alerts/reporting support or scoping. |
| Scale | `Obs`, `DLQ`, partitioning/rate limiting/fair scheduling ideas | Good operational closure. Add state and event evolution. |

The final design is coherent with the step sequence. The main problem is not
missing boxes; it is missing behavioral contracts between boxes.

## Realism Compared With Production Systems

The dataset already has several production-grade instincts:

- It avoids synchronous indexing and synchronous expensive enrichment.
- It treats the search index as rebuildable.
- It makes the raw file store a replay source.
- It uses reversible duplicate grouping.
- It keeps fraud explainable and measurable.
- It treats DLQ as an operating workflow.
- It recognizes tenant skew as a core scaling problem.

Production caveats to add:

- Event replay and schema evolution can break old consumers unless versioned.
- Idempotency is not only request-level; update ordering and state transitions
  need idempotency too.
- Search indexes need deletes, hidden states, and stale-event protection.
- Media pipelines often dominate storage, cost, CDN behavior, and abuse review.
- AI/geocoding/translation vendors need cost controls, privacy boundaries,
  fallbacks, and batch modes.
- Webhook delivery is its own distributed system: signing, retry, backoff,
  owner endpoint failures, and replay UI.
- GDPR deletion must be designed through every projection, cache, index, and
  feature store.
- Tenant-level fairness needs state and enforcement, not just partition keys.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Top-level structure is complete for a walkthrough: requirements, capacity,
  API, data model, patterns, steps, final design, satisfies, interview script,
  level variants, and follow-ups.
- `data/book/index.json` already references `listing-platform` with path
  `data/listing-platform/interview.json`.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Main step/final view nodes and links reference high-level architecture IDs.
- `technologyChoices` is absent.
- `toProbeFurther` is absent.
- `assets` and `aiVisuals` are absent, which is acceptable but means this case
  lacks the richer generated visual layer used by some book content.
- Some option views include links whose endpoint nodes are omitted, so rendered
  option diagrams will lose edges. See issue 7 above.
- `capacityDiagram` labels average seeker QPS as peak.
- `Analytics` appears in the seeker-read view but not in the final view, despite
  owner analytics being a requirement.
- `Notif` appears in final design but is not explained by any step or flow.

No docs rebuild is required for this `REVIEW.md` file alone.

## Recommended Edits, Prioritized

### P1: Fix correctness and traceability gaps

- Add lifecycle/update/delete semantics, including state transitions,
  tombstones, version ordering, and delete propagation to search/cache/media.
- Fix option views whose links reference omitted endpoints.
- Correct the `capacityDiagram` seeker QPS label or values.
- Add SearchDoc/ranking and delete/indexing behavior.
- Add minimal support or explicit scoping for saved listings, alerts,
  report-listing, owner analytics, and webhooks.

### P2: Add production depth

- Add media processing: fetch, scan, strip metadata, thumbnail, store, moderate,
  publish, delete.
- Add outbox table shape and event schema/versioning notes.
- Add rate-limit/quota/fair-scheduler state.
- Add AI-assisted authoring state, privacy, cost, and acceptance guardrails.
- Add final design flows for FTP import, moderation, delete/update, seeker read,
  and webhook completion.
- Add GDPR erasure behavior across DB, media, index, cache, feature store, and
  audit.

### P3: Add book-quality polish

- Add `technologyChoices` for core implementation concerns.
- Add `toProbeFurther` links.
- Add optional generated visuals if this dataset should match the richer book
  cases.
- Add one or two more option comparisons where trade-offs are currently only in
  prose, especially fraud policy and search/ranking/indexing behavior.
- Tighten wording around "always available" to distinguish stale reads from
  perfect availability under regional outage.

## What Not To Change

- Do not change the step order. The current progression is pedagogically sound.
- Do not collapse dedup and fraud into one step; they teach different ideas.
- Do not remove the naive baseline. It earns the later architecture.
- Do not make indexing synchronous for freshness. The outbox/indexer pattern is
  the right core design.
- Do not over-focus on AI. It should remain a supporting capability, not the
  center of the listing platform.
- Do not turn every product feature into a full step. Many missing items can be
  handled with a data model entry, deep dive, final flow, or explicit
  out-of-scope note.

## Bottom Line

This is a strong, interview-ready listing-platform dataset with an excellent
architecture spine. It already teaches the most important system design moves:
decouple writes from reads, converge ingress into a replayable pipeline, keep
search as a projection, make dedup/fraud explainable, and operate by tenant and
lag SLOs.

To make it flagship quality, tighten the production contracts around lifecycle,
search relevance, media, product requirements, and final non-happy-path flows.
Those additions would make the design feel less like a pipeline demo and more
like a complete listing platform.
