# Review: YouTube - Upload & Streaming - System Design

Reviewed file: `data/book/youtube-upload/interview.json`
Review date: 2026-06-09

## Executive Summary

This review reflects the dataset after the follow-up pass that addressed the three remaining P1 findings below. The earlier pass had already made capacity numeric, given resumable upload explicit chunk/resume/complete APIs, modeled upload parts and transcode tasks, separated CDN control plane from data plane, and added view-event semantics.

The latest pass closed the remaining gaps: `POST /v1/uploads` now shows session creation only (201) and the full upload/commit/enqueue lifecycle with `202 processing` moved to `POST /complete`; transcode task ownership is now unambiguous (rendition_tasks in MetaDB is the source of truth, queue messages are wake-ups, workers claim rows by atomic CAS); access control is backed by `videos.visibility`/`geo_policy_id`/`moderation_state`, an `access_policies` table, and a `satisfies.nonFunctional` entry. A view-count sequence flow, capacity assumptions/ranges, and retargeted step-level probe links were also added.

The case is now a strong, production-shaped book-quality walkthrough.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.5/5 | Much stronger quantitative and state-machine detail; a few ownership and policy-state details remain. |
| Production realism | 4/5 | Good upload, transcode, CDN, and view-count realism; access-control/moderation state and queue-vs-task-store semantics need one more pass. |
| Pedagogical flow | 4.5/5 | The seven-step arc remains clean, and the old gaps now mostly become teaching strengths. |
| Dataset/rendering fit | 4/5 | JSON parses, structured references resolve, and diagrams fit the renderer; step-level probe links are still too generic. |
| Overall | 4.5/5 | Ready to use, with a small follow-up pass recommended before treating it as a flagship media case. |

## What Works Well

- The previous P1 findings were materially addressed. Capacity now ties numbers to upload, transcode, CDN, storage, and view-event design choices.
- Resumable upload is now concrete: session create, part upload, resume probe, completion, checksums/ETags, idempotency, expiry, and committed source keys are all represented.
- Transcoding now teaches the important production idea: segment/rendition tasks, leases, attempts, deterministic output keys, dead-lettering, and coordinator validation.
- The playback/CDN step is much clearer. It says the playback service authorizes and mints tokens, while segment traffic goes directly from player to CDN.
- View counting now defines the event shape, threshold, dedup window, late events, bot/fraud filtering, and the public-versus-authoritative count split.
- The naive baseline diagram now shows direct serving of the original file, and Step 2 now highlights metadata state.

## Highest-Impact Remaining Issues

### 1. The upload API sequence conflates session creation with the full upload lifecycle

The API entry for `POST /v1/uploads` has a sequence that includes `PUT chunks`, storing the source, creating the video as `processing`, enqueueing transcode jobs, and returning `202 processing`. That is a useful lifecycle diagram, but it is attached to the session-create endpoint whose response is only `uploadId`, `videoId`, `partSize`, and `expiresAt`.

Why it matters: readers may infer that `POST /v1/uploads` blocks until chunks are uploaded and transcode jobs are enqueued. The prose correctly says jobs start only after `POST /complete`, so the API sequence should not undercut that.

Concrete fix: make `POST /v1/uploads` show only session creation and return `201/200` with the upload session. Move the lifecycle sequence to `POST /v1/uploads/{uploadId}/complete` or to Step 2 as "resumable upload lifecycle". The `202 processing` response belongs after complete, not after start.

### 2. Transcode lease ownership is still ambiguous between `JobQ` and `rendition_tasks`

The data model adds `rendition_tasks` with `state`, `attempt`, and `lease_until`, but the failure sequence says workers claim the task from `JobQ`. That leaves the source of truth unclear: is the queue visibility timeout the lease, or is `rendition_tasks` in the metadata store the leaseable task table?

Why it matters: this is the core correctness mechanism for retries and dead-lettering. A candidate needs a coherent answer for atomic claim, duplicate deliveries, crash recovery, and task completion.

Concrete fix: choose one model explicitly. One good version: queue messages are wake-ups, while `rendition_tasks` in `MetaDB` is the source of truth; workers atomically claim rows by setting `state=leased, lease_until=T`, then ack or let queue messages expire. Another valid version: the queue owns delivery leases and `rendition_tasks` only stores durable result state. The current text mixes both.

### 3. Access control is now a requirement, but the data model and `satisfies` section do not back it

The non-functional requirements now include public, unlisted, private, and geo-restricted playback. Step 5 explains tokenized CDN access well, but `videos` lacks visibility/policy fields, there is no ACL or geo-policy model, and `satisfies.nonFunctional` does not include the access-control requirement.

Why it matters: the dataset correctly calls out CDN cacheability plus authorization as a requirement. Without backing state, the playback service has no clear source for deciding who may receive a manifest/token.

Concrete fix: add `visibility`, `owner_id`, `geo_policy_id`, `policy_status` or `moderation_state`, and either an ACL/share table or an explicit "private videos require an authorization check against creator-owned ACLs" note. Add a `satisfies.nonFunctional` entry for access control, mapped to `stream` and possibly `upload`.

## System Design Soundness

The core architecture is now sound: resumable upload to object storage, metadata-backed state, asynchronous processing through a queue and worker fleet, durable rendition storage, CDN-backed playback, and async view counting. The latest changes make the architecture much more defensible because the state surfaces are visible instead of implied.

Capacity is substantially better than before. The estimates now connect upload ingress, transcode compute multiplier, worker backlog, storage growth, CDN QPS, origin miss traffic, and view-event throughput to specific steps. The main improvement left is to expose assumptions and ranges: `300 hr/min -> 0.5 GB/s` depends heavily on source bitrate, and source-plus-rendition storage can vary widely by codec ladder and retention policy.

The API shape is mostly strong. The separate chunk upload, resume probe, complete endpoint, status endpoint, playback endpoint, and view-ingest endpoint are exactly the right direction. The main API flaw is the misplaced lifecycle sequence under `POST /v1/uploads`.

The data model now covers the important operational entities: `upload_sessions`, `upload_parts`, `rendition_tasks`, and `view_events`. It should add access/policy state and either explicit manifest/segment metadata or a note that `renditions.manifest_key` is the manifest root from which segments are derived.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One-Shot Upload, Serve the Original File

This is now a strong baseline. The added `naive-serve` link fixes the old visual gap, and the trap makes the failure mode clear. Keep it as the opening contrast.

### Step 2: Resumable Chunked Upload

This step is much stronger after the update. It teaches session state, part checksums, idempotent resends, resume probes, conflict detection, completion, and expiry. The only remaining issue is presentation: the API sequence should not make start-session look like it includes chunk upload and transcode enqueue.

### Step 3: Decouple Processing with a Job Queue

Good progression from durable upload to async processing. The reconciler note for "metadata write succeeds but queue publish fails" is an important production detail. Consider tying it to the `rendition_tasks` source-of-truth decision so Step 3 and Step 4 use the same queue/task mental model.

### Step 4: Transcode Fanout into Renditions

This is now one of the best parts of the dataset. Segment-parallel fanout, task leases, deterministic output keys, retry, dead-letter, and coordinator validation are exactly the right concepts. Clarify whether the lease is held in `JobQ` or `rendition_tasks`, and the step will be very strong.

### Step 5: Adaptive Bitrate Streaming via CDN

The control-plane/data-plane explanation is now clear and production-shaped. Cache keys, TTLs, origin shield, private/unlisted access, and tokenized URLs are all useful details. The next improvement is to back this with data model fields and a `satisfies` row for access control.

### Step 6: View Counting at Scale

This step is much more realistic after the update. It defines the event, counting threshold, dedup window, late events, bot/fraud filtering, and approximate versus authoritative counts. A small sequence flow for view ingestion, windowing, and writeback would make the renderer experience match the quality of the prose.

### Step 7: Storage, Cost, and Reliability at Scale

This works well as synthesis rather than a catch-all. It now references mechanisms introduced earlier and names useful SLO signals. It could be slightly stronger with concrete retention/tiering policies, but that is lower priority.

## Final Design Review

The final design now integrates the steps well. It names upload session/part state, transcode task/coordinator state, manifest/segment metadata, view-event aggregation state, and operational SLO monitoring. The description also correctly keeps the playback service out of the segment hot path.

The final design should inherit the same two clarifications as the steps: where transcode leases live, and where playback authorization policy lives. Once those are explicit, the final architecture will read as coherent end to end.

## Concept Introduction and Learning Flow

The concept sequence is strong: naive upload, resumability, async queue, fanout, ABR/CDN, async counting, and operational synthesis. Concepts arrive near the step where they matter, and the recaps expose the next problem naturally.

The remaining learning-flow issue is mostly in supporting links. The dataset has good references in `toProbeFurther`, but several step-level `probeLinks` are generic or mismatched. For example, `views` should point to stream-processing/counting references such as `kafka-design`, and `scale` should point to `sre-monitoring` and possibly `borg-paper`.

## Step-to-Final-Design Coherence

Coherence is now high. The final design contains the main components introduced by the steps, and the major old mismatches were fixed: Step 1 shows direct serving, Step 2 highlights metadata, Step 4 models retry state, Step 5 separates CDN data path from playback control plane, and Step 6 defines counting semantics.

The only coherence gaps left are semantic: API sequence placement, transcode task ownership, and access-policy state.

## Realism Compared With Production Systems

For a system-design interview, this is now realistic. It does not pretend that "put it in a queue" solves transcoding; it describes the state needed for retries. It does not put the playback service in the hot path. It treats view counts as business metrics with different accuracy requirements.

Production systems would still need more detail on:

- Creator quotas, upload admission control, and rate limiting.
- Visibility, ACLs, geo policy, moderation/copyright state, and publish gates.
- Exact queue/task-store ownership for transcode leases.
- Manifest versioning, segment metadata, codec ladder policy, and re-transcode workflows.
- Alerting thresholds and runbook actions for queue age, upload failures, CDN hit ratio, origin egress, and playback quality.

## Dataset and Renderer-Facing Observations

- JSON parses successfully.
- Main step views, option views, and final-design view nodes resolve to `highLevelArchitecture.nodes`.
- Main step views, option views, and final-design link references resolve to `highLevelArchitecture.links` when they are string references.
- `satisfies[*].steps` and dataset pattern steps resolve to real step IDs.
- Canonical node types used by the dataset are valid for the current template set: `client`, `database`, `edge`, `object-storage`, `queue`, `service`, `stream`, and `worker`.
- No raw `diagram` fields appear under structured step/final-design areas.
- Step-level `probeLinks` need retargeting. Several steps point to a repeated media/storage set even when better local references exist for queues, operations, and view-event pipelines.
- `REVIEW.md` is repo-only; no docs rebuild is needed for this review update.

## Recommended Edits, Prioritized

### P1: Fix the upload lifecycle sequence — DONE

`POST /v1/uploads` now shows session creation only and returns `201` with the session handle (no chunk transfer or transcode enqueue). The full upload/commit/enqueue lifecycle and `202 processing` moved to `POST /v1/uploads/{uploadId}/complete`.

### P1: Clarify transcode task ownership — DONE

The `rendition_tasks` table in `MetaDB` is now stated as the durable source of truth; `JobQ` messages are scheduling wake-ups. Workers claim a row by atomic CAS (pending→leased, lease_until=T), and crash recovery/dead-lettering reconcile against the row, not the queue. The Step 4 prose, data-model note, failure drill, and the lease-reclaim sequence flow were all updated to this single model, and Step 3's reconciler note was tied to it.

### P1: Back access control with data and `satisfies` — DONE

`videos` gained `visibility`, `geo_policy_id`, and `moderation_state`; a new `access_policies` table holds geo allow/deny lists and the private-share ACL. A `satisfies.nonFunctional` "Access control on playback" entry maps to `stream` and `upload`, and Step 5 + the final design now reference reading this policy state before minting a token.

### P2: Add a view-count sequence flow — DONE

Step 6 now has a `Viewer -> ViewPipe -> dedup/window -> MetaSvc/MetaDB` flow, with the public approximate count separated from an authoritative analytics/monetization branch.

### P2: Add ranges or assumptions to capacity — DONE

Each capacity bullet now states its assumption explicitly (source bitrate, rendition ladder/codec cost, storage multiplier, CDN hit/miss ratio, view-event heartbeat rate) alongside the numbers.

### P3: Retarget step-level probe links — DONE

`s3-multipart` for upload, `ffmpeg-docs`/`netflix-vmaf`/`borg-paper` for transcoding and fleet, `apple-hls`/`dash-if` for streaming, `kafka-design` for the async queue and view counting, and `sre-monitoring`/`borg-paper` for operations.

## What Not To Change

- Keep the seven-step arc.
- Keep the naive baseline.
- Keep the concrete capacity bullets.
- Keep the upload session/part model.
- Keep segment-parallel transcoding as the default option.
- Keep the control-plane/data-plane CDN explanation.
- Keep public view counts eventually consistent and separate from authoritative analytics/monetization.

## Bottom Line

The recent changes turned this from a good high-level case into a strong, production-shaped interview walkthrough. One targeted cleanup pass on API sequencing, task ownership, and access-policy state would make it ready as a flagship media-system dataset.
