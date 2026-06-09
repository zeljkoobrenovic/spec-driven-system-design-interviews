# Review: Instagram - System Design

Reviewed file: `data/book/instagram/interview.json`
Review date: 2026-06-05

## Executive Summary

The recent dataset changes materially improved this case. The old review's
largest gaps around functional closure, qualitative capacity, upload
correctness, ranker fallback, fanout operations, privacy filtering, and diagram
endpoint omissions are now mostly addressed in the source JSON.

This is now a strong media-feed interview. It has a clear arc from a naive
upload/read design to async media processing, pre-generated variants, CDN
delivery, hybrid fanout, candidate ranking, engagement counters, and
rebuildable feed caches. The current remaining issues are narrower but still
worth fixing before treating the case as fully polished: one capacity number is
off by orders of magnitude, the upload API contract is still compressed, the
privacy/deletion model is named more than modeled, and the derived feed/ranking
state could be made more explicit.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.25/5 | The core media/feed architecture is credible; storage math, upload-session flow, access-control data, and feed metadata need refinement. |
| Production realism | 4.1/5 | Much stronger on idempotency, retries, fallback, and operational lag; still thin on private accounts, blocks/mutes, deletes, model features, and lifecycle workflows. |
| Pedagogical flow | 4.5/5 | The step progression is clean and interview-friendly; each step now solves the previous step's exposed problem. |
| Dataset/rendering fit | 4.6/5 | JSON and references validate cleanly; remaining observations are polish, mostly pattern tagging and local-node clarity. |

## What Works Well

- The case is correctly framed as a media-heavy feed problem, not just a
  generic social timeline (`data/book/instagram/interview.json:2`).
- Requirements now map to a broader API and data model: follow/unfollow,
  profile grid, likes, comments, and post status are represented
  (`data/book/instagram/interview.json:383`,
  `data/book/instagram/interview.json:565`).
- Capacity is mostly quantitative now: upload QPS, processing jobs, feed reads,
  fanout writes, cache memory, candidates per read, and ranker latency are
  stated (`data/book/instagram/interview.json:341`).
- Step 2 now teaches async media correctness, including idempotency, explicit
  states, retries, DLQ, validation, EXIF stripping, and moderation
  (`data/book/instagram/interview.json:824`).
- Step 4 now explains hybrid fanout operationally: bounded celebrity pull,
  dedupe, follower-shard partitioning, idempotent feed-cache inserts, threshold
  flips, and fanout-lag metrics (`data/book/instagram/interview.json:1287`).
- Step 5 now has a realistic read-path timeout, chronological/cached-score
  fallback, and stable pagination snapshot (`data/book/instagram/interview.json:1536`).
- Step 6 now separates exact like state from approximate aggregate counters and
  gives comments their own paginated/moderated storage path
  (`data/book/instagram/interview.json:1824`).
- Step 7 and the final design now make hydration-time visibility filtering
  explicit for deleted, private, blocked, and unfollowed content
  (`data/book/instagram/interview.json:2045`,
  `data/book/instagram/interview.json:2119`).
- The `satisfies` mapping now closes the previously missing profile-grid row
  and has clean step references (`data/book/instagram/interview.json:2169`).

## Highest-Impact Issues

### 1. Media storage capacity is off by orders of magnitude

The capacity table says `100M posts/day`, assumes an average `2MB` original,
and then says variants bring each post to about `10MB`, but labels storage as
`~PB/yr` (`data/book/instagram/interview.json:341`). At those assumptions:

- Originals alone: `100M * 2MB/day` is about `200TB/day`, roughly `73PB/year`.
- Originals plus variants at `10MB/post`: about `1PB/day`, roughly
  `365PB/year`, before replication, metadata, video skew, and retention tiers.

Why it matters: this case uses storage amplification to justify pre-generated
variants, CDN delivery, lifecycle management, and backfills. A wrong unit makes
the architecture look much cheaper than it is.

Concrete fix: change the storage line to something like `~1PB/day raw at
10MB/post, ~100s PB/year before retention/replication controls`, or lower the
input assumptions. Add one note on lifecycle tiers, retention, and replication
factor so the number is defensible.

### 2. The upload API still skips the actual upload-session contract

`POST /v1/posts` now says the media was already uploaded and uses an
`uploadId` plus an `Idempotency-Key` (`data/book/instagram/interview.json:385`).
That is the right direction. But the API list has no `POST /v1/uploads`
endpoint to create a resumable/pre-signed upload, no completion/commit
contract, and the sequence still describes the client sending "upload media +
caption" to the upload service (`data/book/instagram/interview.json:414`).

Why it matters: for large photos and videos, the upload session is the
front-door workflow. Without it, the reader cannot tell where validation,
object-store key allocation, resumability, checksum verification, and orphaned
upload cleanup happen.

Concrete fix: add `POST /v1/uploads` returning an `uploadId` and pre-signed
parts/URL, optionally `POST /v1/uploads/{uploadId}/complete`, and then keep
`POST /v1/posts` as the metadata/idempotent publish command. Update the API
sequence label so it does not imply raw media still flows through `POST /v1/posts`.

### 3. Privacy, blocks, mutes, deletion, and takedown are enforced but not modeled

The final design says feed hydration filters deleted/private/blocked/unfollowed
ids, and Step 7 adds a failure drill for deleted or private posts
(`data/book/instagram/interview.json:2051`,
`data/book/instagram/interview.json:2112`). The `posts` table has `status` and
`visibility`, and comments have moderation status
(`data/book/instagram/interview.json:587`,
`data/book/instagram/interview.json:681`). But there is no API or data model
for private follow requests, blocks, mutes, account visibility, delete/takedown
commands, or CDN purge state.

Why it matters: hydration-time filtering is the right design choice for
already-fanned-out post ids, but it needs current relationship and content
lifecycle state to consult. Otherwise the stated correctness rule has no
authoritative source.

Concrete fix: add concise data-model entries for `users` or `account_settings`,
`blocks`, `mutes`, and `follow_requests` or `follows.status`; add `DELETE
/v1/posts/{postId}` or a moderation/takedown workflow; mention CDN purge and
eventual edge expiry in the delete/takedown path.

### 4. Feed-cache and cursor metadata are still underspecified

The data model keeps `home_feed` as a list of post ids
(`data/book/instagram/interview.json:614`). That is good for teaching
reference-by-id feeds, but later sections depend on more metadata: idempotent
fanout writes, celebrity pull dedupe, classification-version/cutoff behavior,
stable ranked cursors, high-watermarks, and rebuild windows
(`data/book/instagram/interview.json:1293`,
`data/book/instagram/interview.json:1542`).

Why it matters: the design now claims stronger operational guarantees than the
cache schema can explain. A candidate needs to know what is stored in the feed
entry versus what is stored in a short-lived cursor snapshot.

Concrete fix: extend `home_feed` or add a `feed_entry` note with `user_id`,
`post_id`, `author_id`, `published_at`, `inserted_at`, `source(push|pull)`, and
maybe `fanout_version`. Add a separate short-lived `feed_cursor_snapshot` or
cursor-token note for ranked page stability.

### 5. Ranking and engagement are still compressed into the post service

Step 6's default option correctly introduces an interaction event stream and a
counter aggregator (`data/book/instagram/interview.json:1857`). The final design
description says these are folded into the post service, which is acceptable
for a compact final diagram (`data/book/instagram/interview.json:2121`). The
remaining gap is that ranking depends on fresh features, offline/nearline
training, model rollout, and feature freshness, but the dataset mostly treats
the ranker as a synchronous scoring service.

Why it matters: ranking is the main reason interactions are in the case. If
the feature path is too hand-wavy, the candidate may miss how likes/comments
become ranking signals without overloading the feed read path.

Concrete fix: add a small note or deep dive that interaction events update
nearline counters/features, offline jobs train models, model versions are
rolled out safely, and the feed service can fall back to cached scores. If the
final diagram remains compact, keep the current "folded into post service"
wording but add `EventQ`/`Aggregator` as optional final-design nodes or a
caption note.

## System Design Soundness

The main architecture is sound. Media originals and variants are separate from
post metadata; CDN edges absorb media fanout; feed caches store ids, not copied
posts; the feed service hydrates and ranks a bounded candidate set; and the
fanout strategy handles heavy-tailed follower counts.

The recent changes fixed the biggest requirement-closure problem. The API now
covers unfollow, profile-grid reads, likes/unlikes, comments, and post status
in addition to post creation and feed reads (`data/book/instagram/interview.json:508`).
The data model now includes `profile_posts`, `likes`, `comments`, and
`post_counters` (`data/book/instagram/interview.json:628`). The final design
also explicitly states that profile grids use an author/time index and that
cached feed ids are filtered during hydration (`data/book/instagram/interview.json:2121`).

The strongest remaining soundness issue is not architecture shape; it is
contract precision. Upload sessions, access-control state, feed-entry
metadata, and ranking-feature state are the mechanisms that make the described
architecture correct under retries, deletes, privacy changes, and pagination.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Synchronous Upload + Assemble-on-Read Feed

Strong baseline. It exposes the three real pressures: inline media processing,
origin media serving, and read-time fan-in across followees. The trap also
keeps the naive design framed as a teaching step, not a plausible final answer.

### Step 2: Async Media Upload and Processing

Much improved. This step now teaches idempotency, states, DLQ behavior, media
validation, EXIF stripping, and moderation. Add the missing upload-session API
flow so the step and API agree on how large media reaches object storage.

### Step 3: Variants and CDN Delivery

Strong. The default option is the right design for predictable global reads,
and the on-the-fly resize option is a real trade-off. After fixing the storage
capacity math, this step will have an even stronger quantitative motivation.

### Step 4: Feed Generation: Hybrid Fanout

Strong and central to the case. The new operational paragraph covers the
important production concerns: bounded pull, dedupe, follower-shard
partitioning, idempotent inserts, threshold flips, and lag metrics. Consider
connecting this more directly to the `home_feed` schema.

### Step 5: Feed Ranking

Good. Candidate generation plus ranking is introduced at the right point, and
the timeout/fallback/cursor additions are valuable. The next improvement is a
small feature-pipeline note so the ranker is not just a black-box RPC.

### Step 6: Likes, Comments, and Counters

Good direction and much more complete than before. It now separates exact
per-user like state from approximate aggregate counters and gives comments a
paginated storage model. Add a dataset-level "Async engagement counting"
pattern so the step's main lesson appears in the pattern section.

### Step 7: Scaling, Hot Content, and Rebuildable Feeds

Strong close. The hydration-time filtering rule is the right way to preserve
correctness without rewriting millions of feed caches. Make the relationship
and lifecycle state behind that filter explicit.

## Final Design Review

The final design integrates the core walkthrough well: upload service, object
storage, processing queue, workers, variant store, CDN, post service, post
store, fanout service, graph service, feed cache, feed service, and ranker
(`data/book/instagram/interview.json:2122`). The description is now much more
complete than the previous review version, especially around idempotent jobs,
DLQs, ranker fallback, stable cursor pagination, hydration filtering, exact
likes, approximate counters, comments, profile grids, and rebuildable feeds
(`data/book/instagram/interview.json:2121`).

The compact final diagram is acceptable. If this becomes a flagship case, add
one of two clarifications: either show interaction stream/aggregator and
profile index as final-design nodes, or explicitly state in the caption that
they are represented inside the post store/post service boundary.

## Concept Introduction and Learning Flow

The concept order is now excellent for an interview: start naive, move media
work off the request path, make media globally cacheable, precompute feed
candidates, rank the small candidate set, handle high-volume interactions, and
close with rebuildable derived state.

The only concept that is under-promoted is async engagement counting. It exists
as a Step 6 concept, but the dataset-level `patterns` section does not include
it, and the step's `patterns` tag points to "Candidate generation + ranking"
instead (`data/book/instagram/interview.json:709`,
`data/book/instagram/interview.json:2017`). Add a dedicated pattern so the
book's pattern view captures the counter lesson.

## Step-to-Final-Design Coherence

Coherence is a major strength. Step 2 contributes the upload/processing path,
Step 3 contributes variants/CDN, Step 4 contributes hybrid fanout and feed
cache, Step 5 contributes ranker and cursor/fallback behavior, Step 6
contributes engagement state and counters, and Step 7 contributes rebuild,
visibility filtering, lag monitoring, and degraded modes.

The remaining weak links are mostly schema-level: the final text talks about
state that is not visibly modeled yet, especially upload sessions,
relationship/access-control state, and feed cursor snapshots.

## Realism Compared With Production Systems

The case now covers many production levers interviewers expect: asynchronous
processing, queue backlogs, DLQs, idempotency, CDN serving, fanout lag, hybrid
push/pull, ranker timeouts, stable pagination, exact-vs-approximate counters,
hydration filtering, and rebuildable feed caches.

For a real Instagram-like system, the next realism layer would be:

- Upload lifecycle: resumable sessions, checksums, abandoned uploads, virus or
  media validation, and moderation workflow.
- Access control: private accounts, follow requests, blocks, mutes, account
  status, post delete/takedown events, and CDN purge behavior.
- Ranking operations: feature freshness, model versioning, training data
  generation, online experimentation, and fallback score freshness.
- Data lifecycle and cost: retention tiers, backfills for new variants,
  replication factor, CDN egress/cost controls, and regional degradation.

These do not need to dominate the walkthrough, but a few concise notes would
make the design feel fully production-aware.

## Dataset and Renderer-Facing Observations

- JSON parse validation succeeds.
- `satisfies[*].steps[*]` references resolve to real step ids.
- Step `probeLinks` references resolve to `toProbeFurther.links`.
- String node references in step and option views resolve to
  `highLevelArchitecture.nodes`.
- String link references in step and option views resolve to
  `highLevelArchitecture.links`.
- Canonical link endpoints are present in the visible node list for step,
  option, and final-design views; the previous `ranking` and `interactions`
  endpoint omissions are fixed.
- The API and data model now close the previously missing profile-grid,
  unfollow, likes, and comments coverage.
- Local option nodes such as `EventQ`, `Aggregator`, `Scorer`, `ImgSvc`,
  `Functions`, and `ShardedCtr` are readable. Adding explicit local `type`
  fields is optional polish if you want more consistent node styling.

## Recommended Edits, Prioritized

### P1: Correct media storage capacity

Replace `~PB/yr` with a number consistent with `100M posts/day` and
`~10MB/post` after variants. Add retention/replication caveats.

### P1: Add the upload-session API flow

Add upload session creation/completion and align the post-create sequence with
the `uploadId` contract.

### P2: Model relationship and content lifecycle state

Add concise APIs/data-model notes for private accounts, follow requests,
blocks/mutes, post deletion/takedown, and CDN purge/expiry.

### P2: Expand feed-entry and cursor metadata

Make idempotent fanout, pull dedupe, threshold flips, rebuild windows, and
stable ranked pagination visible in the `home_feed`/cursor model.

### P2: Give ranking and engagement a small feature-pipeline note

Explain how interaction events become fresh ranking features and how model
versions/fallback scores are operated.

### P3: Add an "Async engagement counting" pattern

Promote Step 6's main lesson into the dataset-level `patterns` list and tag
the step with that pattern.

### P3: Clarify compact final-design nodes

Either show `EventQ`, `Aggregator`, and the profile index in the final diagram,
or keep them folded into the post-service/post-store boundary and say so in
the caption.

## What Not To Change

- Keep the media pipeline early; it is what differentiates this from a generic
  text-feed interview.
- Keep pre-generated variants plus CDN as the default and on-the-fly resizing
  as the storage-saving alternative.
- Keep hybrid fanout as the default feed-generation choice.
- Keep feed cache as derived state storing post ids, not copied posts/media.
- Keep ranker fallback and stable cursor pagination; those additions are now
  one of the strongest production-realism improvements.
- Keep Stories and Explore as follow-up prompts rather than pulling them into
  the core walkthrough.

## Bottom Line

This review update should supersede the prior one: most of the old P1/P2
findings have been fixed. The dataset is now strong and close to flagship
quality. Fix the storage capacity math, complete the upload-session contract,
model access-control/lifecycle state, and make feed/ranking metadata explicit.
