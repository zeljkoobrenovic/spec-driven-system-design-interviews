# Review: Instagram - System Design

Reviewed file: `data/book/instagram/interview.json`
Review date: 2026-06-05

## Executive Summary

This is a strong media-feed walkthrough. The core teaching arc is coherent:
start from synchronous upload and assemble-on-read, then add async media
processing, pre-generated variants, CDN delivery, hybrid fanout, ranking,
engagement counters, and rebuildable feed caches. The final design integrates
the main components introduced by the steps.

The highest-impact gaps are scope closure and production realism. The
requirements include profile grid, follow/unfollow, likes, and comments, but
the API surface only covers post creation, feed reads, and follow creation,
while the data model only covers posts, follows, and home-feed cache entries.
Capacity is qualitative rather than converted into work units. Upload
correctness, ranker fallback, fanout backpressure, privacy/deletion, and two
diagram endpoint omissions should be tightened before treating this as a
flagship book case.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 3.75/5 | The media/feed architecture is plausible; profile grid, interactions, unfollow, deletes/privacy, and ranker fallback are underspecified. |
| Production realism | 3.5/5 | Good CDN/async/fanout instincts, but thin on idempotency, state transitions, retry/DLQ behavior, moderation, privacy filtering, and operational budgets. |
| Pedagogical flow | 4.25/5 | The step progression is clean and interview-friendly; most options are real trade-offs, not strawmen. |
| Dataset/rendering fit | 4/5 | JSON parses and references mostly resolve; two top-level diagrams reference links whose endpoints are omitted from the visible node list. |

## What Works Well

- The case has the right central thesis for Instagram: media processing and
  CDN delivery are not an afterthought to feed fanout
  (`data/book/instagram/interview.json:2`).
- The naive baseline is useful because it exposes three separate bottlenecks:
  inline media work, origin media serving, and assemble-on-read feed fan-in
  (`data/book/instagram/interview.json:619`).
- Step 2 makes async media processing the first real design move and correctly
  separates upload latency from resize/transcode throughput
  (`data/book/instagram/interview.json:676`).
- Step 3 presents the right read-path trade-off: pre-generate variants for
  predictable CDN reads versus on-the-fly resizing for storage efficiency
  (`data/book/instagram/interview.json:982`).
- Step 4 teaches hybrid fanout clearly, including the celebrity-pull threshold
  and id-only feed entries (`data/book/instagram/interview.json:1126`).
- Step 5 uses candidate generation plus ranking, which is the right model for
  a modern social media home feed (`data/book/instagram/interview.json:1374`).
- Step 7 correctly frames feed cache as rebuildable derived state rather than
  authoritative storage (`data/book/instagram/interview.json:1861`).
- The final design includes the main upload, processing, CDN, fanout, cache,
  feed, and ranking components introduced during the walkthrough
  (`data/book/instagram/interview.json:1924`).

## Highest-Impact Issues

### 1. Several functional requirements are not closed by the API and data model

The requirements include follow/unfollow, profile grid, likes, and comments
(`data/book/instagram/interview.json:330`,
`data/book/instagram/interview.json:331`). The API only exposes
`POST /v1/posts`, `GET /v1/feed`, and `POST /v1/follow`
(`data/book/instagram/interview.json:368`). There is no unfollow endpoint, no
profile-grid endpoint, and no like/comment endpoints. The data model only has
`posts`, `follows`, and `home_feed`
(`data/book/instagram/interview.json:501`), so comments, like identity/dedup,
view events, profile-grid ordering, privacy status, and delete/moderation
state have nowhere to live.

Why it matters: the walkthrough claims these product behaviors, but the system
cannot currently prove how they are served or updated. The `satisfies` mapping
also covers likes/comments but not the profile grid
(`data/book/instagram/interview.json:2006`), so the requirement-to-design
closure is incomplete.

Concrete fix: add APIs for `DELETE /v1/follow/{targetUserId}`,
`GET /v1/users/{userId}/posts?cursor=&limit=`, `POST /v1/posts/{postId}/likes`,
`DELETE /v1/posts/{postId}/likes`, and `POST /v1/posts/{postId}/comments`.
Add data-model entries for `comments`, `likes` or `interaction_events`,
`profile_posts` or an author/time index, and post/user visibility state. Add a
`satisfies.functional` row for profile grid.

### 2. Capacity is too qualitative to defend the architecture

The capacity section says `100M+` posts/day, `several` variants per post, feed
reads `>> posts`, and average followers around hundreds
(`data/book/instagram/interview.json:341`). Those are useful signals, but they
do not convert into the work units that justify the design.

Why it matters: the design choices depend on concrete amplification. For
example, 100M posts/day is about 1.2k posts/sec on average before burst
factor. With hundreds of followers, pure fanout can mean hundreds of thousands
of feed writes/sec at average load and much more during spikes. Media variants
drive storage, CDN egress, and transcode CPU. Feed reads drive candidate-cache
memory and hydration QPS. None of those budgets are shown.

Concrete fix: add bullets for average and peak upload QPS, average media size,
variant storage amplification, CDN egress/read QPS, fanout write amplification,
feed-cache memory per active user, candidate count per read, ranker timeout
budget, and processing queue backlog SLO.

### 3. Upload correctness needs an explicit state machine and retry contract

`POST /v1/posts` accepts media directly and returns a processing post
(`data/book/instagram/interview.json:370`). Step 2 says the upload service
stores the original, queues processing, and workers mark the post ready
(`data/book/instagram/interview.json:676`). That is the right outline, but it
omits several correctness details: large/resumable direct uploads, idempotency
keys, duplicate request handling, failed processing, retry limits, DLQs,
poison media, validation, content moderation, EXIF stripping, and client
status polling.

Why it matters: media upload is the first critical workflow. Without an
idempotency and state-transition contract, client retries can create duplicate
posts, worker retries can publish twice, and failed transcodes can leave
permanent `processing` posts.

Concrete fix: model `POST /v1/uploads` or pre-signed object-store upload
creation, then `POST /v1/posts` with an `uploadId` and `Idempotency-Key`. Expand
post status to `uploading`, `processing`, `ready`, `failed`, `deleted`, and
`blocked`; add worker retry/DLQ behavior and a `GET /v1/posts/{postId}/status`
or status field in profile/feed hydration.

### 4. Hybrid fanout is directionally right but underspecified operationally

The hybrid fanout explanation is solid and explicitly mentions dedup and the
threshold knob (`data/book/instagram/interview.json:1161`). The scale step
adds feed length caps, cold-user eviction, and rebuildable feeds
(`data/book/instagram/interview.json:1864`). The missing pieces are operational
rules: how many pulled-celebrity posts are fetched per read, what happens when
an account crosses the push/pull threshold, how fanout lag is surfaced, how
the queue is partitioned, and how duplicate or late fanout writes are made
idempotent.

Concrete fix: add a short deep dive or Step 7 bullets: fetch at most `M`
pull-mode authors and `K` recent posts per author, dedupe by `post_id`, use a
classification version or cutoff timestamp when an author flips modes, batch
fanout writes by follower shard, make feed-cache insertions idempotent, and
alert on per-author fanout lag.

### 5. Ranking is on the read path without fallback or cursor semantics

Step 5 says ranking runs on the candidate set and stays within the latency
budget (`data/book/instagram/interview.json:1377`). The API promises an
opaque cursor (`data/book/instagram/interview.json:434`), and the final design
returns ranked, cursor-paginated posts (`data/book/instagram/interview.json:1926`).
The dataset does not say what happens when ranker or feature fetch is slow,
how a ranked cursor remains stable across pagination, or whether a degraded
read can fall back to chronological or cached scores.

Concrete fix: add a failure drill: "Ranker timeout after N ms: return
reverse-chronological or cached-score candidates and alert on timeout rate."
For cursor stability, say the first page creates a short-lived candidate
snapshot or cursor token containing rank position, score/version, and a high
watermark so page 2 does not reshuffle under the user.

## System Design Soundness

The core high-level architecture is sound for a media-heavy home-feed
interview. The source of truth is post metadata and media objects; generated
variants are derived state; CDN edges serve media; home feeds are derived
candidate lists; the feed service hydrates and ranks ids. That separation
keeps media reads off the origin, avoids copying full posts into every feed,
and makes feed caches rebuildable.

The largest soundness gap is requirement closure. A profile grid can be served
with an author/time index over ready posts plus media URL hydration, but the
dataset never makes that path explicit. Likes and comments are discussed in
Step 6, but the API and storage model do not include exact like dedup,
comment ordering, comment pagination, moderation state, or delete behavior.
Follow/unfollow is especially thin: follow is modeled as an API, but unfollow
semantics are only present in the requirement.

The design also needs a current-state filtering story. A post id may exist in
millions of feed caches, so deletes, moderation takedowns, private-account
changes, blocks, and unfollows should be enforced during hydration. That rule
can keep feed cache entries cheap while preserving correctness.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Synchronous Upload + Assemble-on-Read Feed

Strong. It is intentionally simple, and the three reasons it fails map cleanly
to the next three steps. This is a good first interview move.

### Step 2: Async Media Upload and Processing

Strong conceptually. The default option is the right answer for this scale.
Add the upload state machine, retry/idempotency behavior, and failure path so
the candidate learns that async processing is not just "queue plus workers."

### Step 3: Variants and CDN Delivery

Strong. The options teach the key trade-off between storage amplification and
cold-miss generation cost. The next useful addition is a brief note on signed
media URLs, cache invalidation/purge on deletion, and variant backfill when a
new device size is introduced.

### Step 4: Feed Generation: Hybrid Fanout

Strong and central to the case. The default option is realistic, and the pure
push/pull alternatives are meaningful. Tighten it with bounded celebrity pull,
threshold-transition behavior, queue partitioning, and idempotent feed-cache
writes.

### Step 5: Feed Ranking

Good teaching step. Candidate generation plus ranking is introduced at the
right time. The missing production lesson is that ranker/model serving is now
a read-path dependency and needs a hard timeout, fallback ordering, candidate
cap, and stable pagination token.

### Step 6: Likes, Comments, and Counters

Good direction, but the implementation surface is too thin for a stated
functional requirement. The async counter options are useful. Add like
idempotency per user/post, comment storage and pagination, comment moderation,
and the distinction between exact user-visible state ("I liked this") and
approximate aggregate counters.

### Step 7: Scaling, Hot Content, and Rebuildable Feeds

Strong closing step. Treating feed cache as derived state is exactly right.
Make it more operational by adding fanout lag metrics, DLQ/replay behavior,
cache rebuild budgets, and regional degradation behavior.

## Final Design Review

The final design integrates the main walkthrough: upload service, object
storage, processing queue, workers, variant store, CDN, post service, post
store, fanout service, graph service, feed cache, feed service, and ranker
(`data/book/instagram/interview.json:1928`). It is coherent for the primary
home-feed path.

It does not yet integrate profile grid, likes/comments storage, unfollow
cleanup/filtering, deletes/moderation, privacy, ranker fallback, or upload
failure states. Those do not require a different architecture, but they should
be explicitly layered into the final design so the wrap-up matches the stated
requirements.

## Concept Introduction and Learning Flow

The concept order is good: naive baseline, async media pipeline, CDN variants,
hybrid fanout, ranking, counters, and rebuildable feeds. The concepts are
introduced just in time, and the option sets generally compare real choices.

The main learning-flow gap is that some product features arrive as
requirements but do not get their own mechanism. A candidate reading this could
answer the home-feed problem well but still be unable to explain profile-grid
reads, unfollow cleanup, exact like state, comment pagination, or takedowns.

## Step-to-Final-Design Coherence

Most steps build directly toward the final design. Step 2 adds processing,
Step 3 adds CDN/variants, Step 4 adds hybrid feed generation, Step 5 adds
ranking, Step 6 adds engagement signals, and Step 7 explains derived feed
state. This coherence is the dataset's biggest strength.

The weak transition is Step 6 to final design: Step 6 option diagrams introduce
`EventQ`, `Aggregator`, and `ShardedCtr` as local nodes, but the final design
only shows `Ranker` and `PostDB`. That is acceptable if interaction processing
is intentionally folded into the post service, but the text should say so or
the final view should include the event stream and aggregator.

## Realism Compared With Production Systems

The dataset correctly names the biggest scale levers: async media processing,
CDN, id-only feeds, hybrid fanout, candidate ranking, approximate counters,
and rebuildable caches.

Production Instagram-like systems also need: abuse/media validation, private
accounts, blocks/mutes, deleted or moderated posts, CDN purge, copyright or
unsafe-media workflows, regional replication, feature-store freshness,
observability for processing lag and fanout lag, and clear degraded modes for
ranker and graph-service outages. These can be short notes; they do not need
to dominate the interview.

## Dataset and Renderer-Facing Observations

- JSON parse validation succeeds.
- `satisfies[*].steps[*]` references resolve to real step ids.
- Step `probeLinks` references resolve to `toProbeFurther.links`.
- String node references in step and option views resolve to
  `highLevelArchitecture.nodes`.
- String link references in step and option views resolve to
  `highLevelArchitecture.links`.
- The top-level `ranking` view includes `Client`, `FeedSvc`, `FeedCache`,
  `Ranker`, and `PostDB`, but references `lb-feed`, whose source endpoint is
  `LB`; either add `LB` to the view nodes or replace the link with an inline
  `Client -> FeedSvc` link (`data/book/instagram/interview.json:1382`,
  `data/book/instagram/interview.json:1391`).
- The top-level `interactions` view includes `Client`, `LB`, `PostSvc`,
  `PostDB`, and `Ranker`, but references `feed-ranker`, whose source endpoint
  is `FeedSvc`; either add `FeedSvc` or use an inline `PostSvc -> Ranker`
  engagement-signal link (`data/book/instagram/interview.json:1653`,
  `data/book/instagram/interview.json:1662`).
- The option views already avoid those two endpoint omissions.

## Recommended Edits, Prioritized

### P1: Close the stated functional requirements

Add profile-grid, unfollow, like, unlike, and comment APIs; add the supporting
data-model entries; map profile grid in `satisfies.functional`; explain
hydration and visibility filtering for cached feed/profile ids.

### P1: Quantify capacity and work amplification

Turn the current qualitative capacity list into concrete average/peak work:
upload QPS, processing jobs/sec, media storage amplification, CDN egress,
fanout writes/sec, feed-cache memory, read QPS, candidate cap, and ranker
latency budget.

### P2: Add upload state, retries, and idempotency

Introduce upload sessions or pre-signed uploads, post idempotency keys,
processing states, worker retry/DLQ behavior, and validation/moderation
gates.

### P2: Add ranker and graph degraded modes

Document read-path timeout budgets, fallback ordering, cached scores, stable
ranked cursors, and what users see if the graph service or ranker is slow.

### P2: Make hybrid fanout operational

Add bounded celebrity pull, threshold-transition dedupe/cutoff rules,
partitioned fanout queues, idempotent feed-cache inserts, fanout lag metrics,
and replay/backfill behavior.

### P3: Fix the two top-level diagram endpoint omissions

Patch the `ranking` and `interactions` views so every canonical link endpoint
is included in the diagram's visible node list or replace those references with
inline links matching the nodes shown.

### P3: Add privacy, deletion, and moderation notes

Add concise notes on private accounts, blocks/mutes, post deletion, takedown,
CDN purge, and hydration-time filtering. These should stay scoped, but they
are important for a photo/video social product.

## What Not To Change

- Keep the media pipeline early; it differentiates this case from a generic
  text-feed interview.
- Keep the option-based trade-off structure for upload, variants, fanout,
  ranking, and counters.
- Keep feed cache as derived state and store feed entries by post id rather
  than copying full post/media data.
- Keep Stories and Explore as follow-up prompts; they are good extensions and
  do not need to be pulled into the core walkthrough.

## Bottom Line

This is a good Instagram-style media-feed case with a clean teaching arc. To
make it production-grade, close the stated product requirements in the API and
data model, quantify capacity, add correctness and degraded-mode details, and
fix the two diagram endpoint omissions.
