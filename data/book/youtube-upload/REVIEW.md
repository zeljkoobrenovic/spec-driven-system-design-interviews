# Review: YouTube - Upload & Streaming - System Design

Reviewed file: `data/book/youtube-upload/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong, coherent walkthrough for a YouTube-style upload and playback pipeline. The step order is natural: naive baseline, resumable upload, async queue, transcode fanout, CDN playback, view counting, and storage/reliability. The structured diagrams are clean and the option sets for transcoding, streaming, and counting teach real trade-offs.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4/5 | Correct high-level architecture, but upload, job, playback, and count contracts need more concrete state. |
| Production realism | 3/5 | Mentions retries, idempotency, CDN, and cost, but operational details are compressed and several edge cases are only implied. |
| Pedagogical flow | 4/5 | Clear problem-by-problem progression with good prompts and recaps. |
| Dataset/rendering fit | 4/5 | JSON parses; structured node/link references, pattern steps, probe links, and `satisfies` step IDs resolve. |
| Overall | 4/5 | Usable as a book case after adding more quantitative and state-machine depth. |

## What Works Well

- The naive baseline is effective: it exposes why the design needs resumable upload, asynchronous processing, renditions, CDN delivery, and eventual view counts.
- The core architecture uses the right split: transactional metadata, raw/rendition object storage, transcode workers, job queue, playback service, CDN, and async view-count pipeline.
- The option sets are practical. Segment-parallel transcoding, pull-through CDN, pre-warming, progressive download, direct counters, and aggregate counters are real alternatives rather than strawmen.
- The wrap-up maps requirements to steps cleanly, and the interview script gives a candidate a usable time-boxed narrative.
- Renderer-facing structure is mostly healthy: main step views, option views, final-design links, patterns, `satisfies` steps, and probe links all resolve.

## Highest-Impact Issues

### 1. Capacity is too qualitative to drive design choices

The capacity section uses broad labels such as "100s of hours/min", "~5-8 renditions", "millions", and "watch >> upload". Those are directionally right, but they do not convert into the quantities the architecture depends on: upload ingress bandwidth, transcode-hours per uploaded hour, worker fleet size, object storage growth, CDN cache miss/origin bandwidth, view-event throughput, or metadata write rate.

Why it matters: the later choices depend on those numbers. Segment-parallel transcoding is easier to justify if the case says, for example, that one uploaded hour may require several compute-hours across codec/rendition ladders. CDN pull-through versus proactive pre-warm is easier to compare if origin miss traffic and hot/long-tail ratios are estimated.

Concrete fix: expand `capacity` with calculated bullets: uploaded GB/min, source-plus-rendition storage multiplier, transcode compute multiplier, approximate segment requests/sec at CDN edge, expected origin miss ratio, and view event rate. Tie each number to the step it motivates.

### 2. Resumable upload is underspecified as an API and state machine

The API has `POST /v1/uploads`, but the chunk upload mechanics are only described in prose. There is no explicit chunk endpoint, complete/commit endpoint, offset reconciliation, checksum/ETag handling, idempotency key, upload expiration, duplicate chunk behavior, or conflict response when the client and server disagree about `received_bytes`. The `upload_sessions` model only has `upload_id`, `video_id`, `received_bytes`, and `total_bytes`.

Why it matters: resumable upload is one of the core requirements. In interviews, the difference between "upload in chunks" and a production-ready resumable protocol is the server-side state and retry semantics.

Concrete fix: add API entries for `PUT/PATCH /v1/uploads/{uploadId}/chunks`, `GET /v1/uploads/{uploadId}` for resume offset, and `POST /v1/uploads/{uploadId}/complete`. Extend `upload_sessions` with owner, status, part size, checksum/ETag list or manifest, expires_at, created_at/updated_at, idempotency key, and committed source object key.

### 3. Transcode fanout needs explicit job and segment state

Step 4 says jobs are idempotent and retryable, split on keyframe boundaries, and stitch outputs. Step 7 mentions dead-lettering. The data model, however, has no transcode job table, segment task table, attempt/lease fields, idempotency key, coordinator state, dead-letter representation, partial output naming, or quality-validation result.

Why it matters: segment-parallel transcoding is the staff-level concept in the case. Without modeling how tasks are claimed, retried, deduplicated, stitched, and marked failed, the design risks sounding like "put it in a queue" rather than a real media-processing pipeline.

Concrete fix: add a `transcode_jobs` or `rendition_tasks` model with `(video_id, rendition, segment_id)`, `state`, `attempt`, `lease_until`, `input_range/keyframe_range`, `output_key`, `checksum`, `error_code`, and timestamps. Add a coordinator/orchestrator node or clarify that `MetaSvc` owns coordination. Add a sequence flow for worker crash/retry and dead-letter handling.

### 4. Playback/CDN security and cache boundaries are blurry

The playback path says the playback service returns a manifest and signed segment URLs, and the diagram includes a `play-cdn` link labeled "signed segment URLs". This can imply the service calls the CDN for every playback request. The design also does not clarify how authorization, private/unlisted videos, TTLs, CDN cache keys, origin shielding, invalidation, geo restrictions, or DRM/signed-cookie trade-offs work.

Why it matters: global playback is where the read fanout lives. A strong answer needs to keep the playback service out of the hot segment path while still enforcing access control and preserving CDN cacheability.

Concrete fix: make the control-plane/data-plane split explicit: playback service authorizes and returns a manifest plus tokenized URLs/cookies; the player fetches segments directly from CDN; CDN origin-fetches from rendition storage on miss. Add cache key/TTL notes and explain how private content avoids leaking while public content remains cacheable.

### 5. View counting lacks the semantics that make counts credible

The view-count step correctly rejects synchronous counter increments, but it does not define the view event schema, dedup key, watch-duration threshold, bot/fraud filters, late-event handling, windowing, exact-versus-approximate boundary, or which counts are public display versus monetization/audit counts.

Why it matters: view counting is a business-facing metric. A public eventually consistent counter is fine, but revenue, recommendations, abuse detection, and analytics may need different accuracy and retention guarantees.

Concrete fix: add a view event shape `(video_id, viewer/session/device, playback_start, watched_seconds, event_time, request_id)`, define when a view is counted, and separate public approximate counts from authoritative analytics/monetization pipelines if they are in scope.

## System Design Soundness

Requirements are scoped well for upload, transcode, stream, status, and counts. The non-functional list captures resumability, asynchronous processing, durability, CDN playback, and independent scaling. The main weakness is that the requirements do not name privacy/security, abuse/moderation, content validation, or operational SLOs, even as follow-ups mention DRM and codec migration.

Capacity is directionally correct but not yet actionable. It should quantify the multiplier effects: one source produces multiple renditions and many segments; upload throughput becomes transcode queue depth; watch traffic becomes CDN segment QPS and origin miss bandwidth; view events become stream-processing load.

The API is serviceable for a first pass, but it is too compact for this domain. Upload status, chunk writes, completion, playback manifest retrieval, and view-event ingestion should be separate contracts, even if some are summarized. The status endpoint should distinguish `uploading`, `processing`, `ready_to_watch`, `fully_processed`, `failed`, and per-rendition failure.

The data model captures the basic entities but misses the most important operational entities: upload parts/checksums, transcode jobs, segment tasks, attempts, DLQ records, manifests/segments, and view events/windows. Adding those would make the case much more production-realistic without changing the high-level architecture.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One-Shot Upload, Serve the Original File

Strong baseline and a useful decision prompt. The diagram includes `Viewer` but does not show a link from the stored original/origin to the viewer, so the visual does not fully match "serve the original file". Add a local view link such as `RawStore -> Viewer` or `UploadSvc -> Viewer` labeled "serve original" to make the failure visible.

### Step 2: Resumable Chunked Upload

The concept is introduced at the right time. The step should go deeper on offset reconciliation, duplicate chunks, checksums, chunk manifests, idempotency, and upload finalization. The explicit highlight only marks `UploadSvc` and `RawStore`, but this step also introduces `MetaSvc` and `MetaDB`; highlighting the metadata state would better match the lesson.

### Step 3: Decouple Processing with a Job Queue

Good transition from durable source to asynchronous processing. The step should clarify who enqueues jobs and when: only after the upload is committed, not merely after the first chunks arrive. Consider adding a short failure path for an upload that never completes or a queue publish that fails after metadata is updated.

### Step 4: Transcode Fanout into Renditions

This is one of the strongest steps. The three options are useful and realistic. The missing part is state: segment tasks, coordinator ownership, retries, leases, idempotent output keys, partial-output cleanup, and quality validation should be explicit. A failure drill exists for worker crash, but the architecture/data model does not yet show where that retry state lives.

### Step 5: Adaptive Bitrate Streaming via CDN

Good explanation of HLS/DASH and pull-through CDN. The progressive-download alternative is a good teaching contrast. Tighten the data-plane/control-plane explanation so the playback service is not perceived as proxying segment traffic or calling the CDN on every segment. Add cache TTL, signing, private-video authorization, and CDN origin-shield notes.

### Step 6: View Counting at Scale

The option comparison is good. To raise the bar, define a view event, counting threshold, dedup window, late-arrival behavior, and bot/fraud filtering. Also separate public approximate counts from analytics or monetization-grade records.

### Step 7: Storage, Cost, and Reliability at Scale

The step closes the case with the right themes: storage tiers, retryable jobs, dead letters, per-rendition status, and independent scaling. It is doing too much at once, though. Some reliability and observability concerns should be introduced earlier where the relevant mechanism appears, then summarized here.

## Final Design Review

The final design accurately integrates the main nodes and links introduced in the steps. It says jobs are idempotent and retryable, view events are deduped, and ingestion/serving scale independently. This is the right final architecture.

The final design would be stronger if it named the missing state surfaces: upload session/part state, transcode task/coordinator state, manifest/segment metadata, view-event aggregation state, and operational monitoring. It should also mention the playback service as a control-plane service that authorizes and returns manifests/tokens, not as part of the segment delivery path.

## Concept Introduction and Learning Flow

Concepts are staged well: resumable upload, async pipeline, fanout, ABR/CDN, and async counting arrive just before they are used. The pattern tags reinforce that flow.

The main learning gap is that several production concepts are referenced only after the design already depends on them. Idempotency, retries, leases, DLQs, cache keys, signed URL TTLs, and dedup windows should each appear near the step where the reader first needs them.

## Step-to-Final-Design Coherence

The sequence of steps builds cleanly toward the final design. Each step's recap exposes the next problem, which is excellent for interview pacing. The final design contains all major components introduced by the steps.

The weak spots are semantic rather than structural: Step 1 visually omits serving to the viewer; Step 2 introduces metadata but does not highlight it; Step 4 relies on unmodeled task state; Step 5 has a potentially misleading playback-to-CDN link; Step 6 introduces an event pipeline without event semantics.

## Realism Compared With Production Systems

For a book-style interview case, the high-level architecture is realistic. The design correctly avoids serving from origin, treats transcoding as asynchronous, stores immutable media in object storage, and separates read-heavy playback from write-heavy processing.

Production systems would also need:

- Upload part manifests, checksums, resumability probes, and failed/expired session cleanup.
- Virus/malware scanning, content policy/moderation hooks, and possibly copyright matching before publishing.
- Worker leases, attempts, retry backoff, dead-letter queues, and idempotent output paths.
- Codec ladder policy, device compatibility, quality scoring, thumbnail/preview generation, and re-transcode workflows.
- CDN cache policy, signed URL/cookie strategy, private video authorization, origin shielding, and invalidation.
- View-event dedup/fraud rules, late event handling, and separate public/analytics/monetization counts.
- Observability: queue age, transcode latency percentiles, per-rendition failure rate, playback start latency, rebuffering ratio, CDN hit ratio, origin egress, and upload completion rate.

## Dataset and Renderer-Facing Observations

- JSON parses successfully.
- Main step `view.nodes`, option `view.nodes`, and final-design nodes resolve to `highLevelArchitecture.nodes`.
- Main step `view.links`, option `view.links`, and final-design links resolve to `highLevelArchitecture.links` when they are string references.
- `satisfies.functional[*].steps`, `satisfies.nonFunctional[*].steps`, dataset pattern steps, and step `probeLinks` resolve.
- Canonical node types are valid for the current template set: `client`, `database`, `edge`, `object-storage`, `queue`, `service`, `stream`, and `worker`.
- No raw `diagram` fields appear under structured step/final-design areas.
- Step 1 has an isolated `Viewer` node in its view. That is valid JSON but weak rendering semantics.
- The API examples use stringified request/response bodies. If the schema supports richer structured examples, structured request/response fields would make the API section easier to compare and evolve.

## Recommended Edits, Prioritized

### P1: Make capacity numeric and tie it to architecture decisions

Add concrete estimates for upload GB/min, transcode compute multiplier, worker count/backlog, storage multiplier, CDN edge QPS, origin miss bandwidth, and view-event throughput. Reference the steps each estimate motivates.

### P1: Expand resumable upload API and data model

Add chunk upload, resume status, and complete endpoints. Extend `upload_sessions` and/or add `upload_parts` with checksums, offsets, part IDs, status, ownership, expiration, and commit metadata.

### P1: Add transcode job/task state

Model segment/rendition jobs, leases, attempts, idempotency keys, output keys, state transitions, DLQ records, and coordinator ownership. Add at least one failure/retry sequence.

### P2: Tighten playback/CDN control-plane language

Clarify that playback service authorizes and returns manifests/tokens while the player fetches segments directly from CDN. Add cache key, TTL, signed URL/cookie, origin shield, and private content notes.

### P2: Define view-count semantics

Add event schema, counting threshold, dedup window, late-event behavior, bot/fraud filtering, and public-versus-authoritative count distinction.

### P2: Improve diagram semantics

Add a naive serving link to Step 1, highlight metadata in Step 2, and reconsider the `play-cdn` link label so it does not imply a hot-path CDN call from playback service.

### P3: Spread operations throughout the steps

Introduce observability, backpressure, and failure modes near the mechanism they belong to, then keep Step 7 as the synthesis.

## What Not To Change

- Keep the seven-step arc. It is clean and interview-friendly.
- Keep the naive baseline; it is a strong teaching device.
- Keep the option sets for transcode, streaming, and view counting.
- Keep the metadata/blob/CDN split as the central design frame.
- Keep view counting eventually consistent for the public display counter.

## Bottom Line

This dataset is structurally sound and already teaches the core YouTube upload/streaming architecture well. The next improvement pass should make the design more concrete: quantitative capacity, explicit upload protocol state, transcode task state, CDN/security boundaries, and view-count semantics.
