# Review: Reddit / Hacker News - System Design

Reviewed file: `data/book/reddit-hn/interview.json`
Review date: 2026-06-05

## Executive Summary

This is a strong teaching case for the classic Reddit/Hacker News shape. The
step progression is coherent: start with sort-on-read, fix voting correctness,
introduce time-decay ranking, move ranked reads to precomputed listings, handle
threaded comments, then close with fraud and moderation. The chosen mechanisms
are mostly the right ones for the stated product.

The remaining gaps are about production specificity rather than the core idea.
Capacity is qualitative, so the p99 target and "large communities" claim are
not testable. The API and data model do not yet cover comment creation,
comment votes, moderation state, global/top/new listing semantics, or the
idempotent event details needed for safe async score updates. Step 7 also has a
small renderer-facing diagram issue: its queue edge is filtered because the
source endpoint is not in the view.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Ranking, precomputed listings, idempotent voting, comments, and fraud are directionally right; capacity and state contracts need more precision. |
| Production realism | 3.75/5 | Good async/cache framing, but thin on moderation workflow, vote-event idempotency, cursor stability, cache invalidation, and concrete hot-post budgets. |
| Pedagogical flow | 4.25/5 | The sequence teaches one pressure point at a time; a few recaps and final-step details need tightening. |
| Dataset/rendering fit | 4/5 | JSON and references validate; option diagrams are clean; Step 7's visible view drops one intended queue link. |

## What Works Well

- The requirements focus the interview on the right hard parts: ranked
  listings, one vote per item, threaded comments, moderation, read-heavy load,
  eventual ranking consistency, and viral/deep-thread scale
  (`data/book/reddit-hn/interview.json:255`,
  `data/book/reddit-hn/interview.json:262`).
- Step 1 is a useful baseline. It explicitly says sort-on-read and counter
  increments are deliberately naive, then uses that failure to motivate the
  rest of the design (`data/book/reddit-hn/interview.json:560`,
  `data/book/reddit-hn/interview.json:604`).
- Step 2 teaches the correct vote invariant: one row per `(user, item)`, with
  repeat votes treated as upserts rather than extra increments
  (`data/book/reddit-hn/interview.json:614`).
- The ranking step gives real alternatives instead of strawmen: time-decay hot
  score, Wilson confidence, and raw net upvotes
  (`data/book/reddit-hn/interview.json:779`,
  `data/book/reddit-hn/interview.json:813`,
  `data/book/reddit-hn/interview.json:851`).
- The listing step makes the central read-path trade-off clear: precompute a
  per-feed sorted set so listing reads are top-N cache reads rather than
  per-request sorts (`data/book/reddit-hn/interview.json:981`,
  `data/book/reddit-hn/interview.json:1008`).
- The comments step chooses a credible default, materialized paths, and compares
  it against parent pointers and closure tables
  (`data/book/reddit-hn/interview.json:1124`,
  `data/book/reddit-hn/interview.json:1150`,
  `data/book/reddit-hn/interview.json:1233`).
- The final design integrates the main concepts: idempotent voting, queued
  score recompute, fraud discounting, time-decay scores, precomputed listings,
  materialized-path comments, hot-thread cache, moderation, and rebuildable
  derived state (`data/book/reddit-hn/interview.json:1550`).

## Highest-Impact Issues

### 1. Capacity is qualitative, so the design cannot be checked against scale

The requirements include a concrete latency goal, p99 listing reads under
200 ms, and a broad scale claim for large communities and viral posts
(`data/book/reddit-hn/interview.json:264`,
`data/book/reddit-hn/interview.json:267`). The capacity section then uses
labels like "the dominant load", "high", "low", "deep / wide", and "seconds"
(`data/book/reddit-hn/interview.json:270`). That is useful for intuition, but
it does not convert product load into work units.

Why it matters: the design's main claims depend on numeric thresholds. A
candidate should be able to say roughly how many listing reads/sec, votes/sec,
comment reads/sec, hot-post vote bursts, sorted-set writes/sec, score-worker
events/sec, and cache entries are being handled. Without numbers, the choice of
sorted sets, batching, cache replication, and comment incremental loading cannot
be pressure-tested.

Concrete fix: add a capacity table with example numbers. For instance: daily
active users, listing reads/sec, comment thread reads/sec, votes/sec, post
submits/sec, peak viral-post votes/sec, top-N listing size, number of active
communities, ranking freshness target, and memory estimate for cached listing
ids. Then tie Step 7's batching and cache replication back to those numbers.

### 2. API and data model do not yet cover the stated comment and moderation behavior

The API currently has post creation, post voting, community hot listing, and
comment-tree read endpoints (`data/book/reddit-hn/interview.json:299`,
`data/book/reddit-hn/interview.json:306`,
`data/book/reddit-hn/interview.json:369`,
`data/book/reddit-hn/interview.json:411`). The requirements also promise
comment votes, comment creation, global front page, top/new sorts, and
moderation removals (`data/book/reddit-hn/interview.json:255`).

The data model is similarly minimal. `votes` has `user_id`, `item_id`, and
`direction`, but no `item_type` or vote version, so a post id and comment id
can collide conceptually and event consumers cannot safely reason about
changed votes (`data/book/reddit-hn/interview.json:479`). `comments` has
`comment_id`, `post_id`, `parent_id`, `path`, and `score`, but lacks the fields
needed by the API and moderation story: author, body/content pointer, created
time, status, deleted/removed timestamp, depth, and sort metadata
(`data/book/reddit-hn/interview.json:453`). `posts` has score fields, but not
status/moderation state, title/url/text fields, or a separate listing/index
representation (`data/book/reddit-hn/interview.json:419`).

Why it matters: the architecture promises one vote per item, comment voting,
moderation removals, cache rebuilds, and sorted listings. The persisted state
needs to make those behaviors explicit. Otherwise the walkthrough teaches the
components but leaves the contracts underspecified.

Concrete fix: add endpoints for `POST /v1/posts/{id}/comments`,
`POST /v1/comments/{id}/vote`, `GET /v1/frontpage/{sort}`, and moderation
actions such as remove/restore. Extend the model with `item_type` in votes,
vote event version or previous/new direction, post/comment `status`, moderation
metadata, comment author/content/timestamps, and a derived listing-cache record
or schema note for `(scope, sort, member_id, score)`.

### 3. Moderation is a requirement, but the workflow is too thin

Moderation is present in the requirements and final design, and Step 7 mentions
spam checks, removals, shadow bans, cache eviction, and async mod actions
(`data/book/reddit-hn/interview.json:259`,
`data/book/reddit-hn/interview.json:1486`,
`data/book/reddit-hn/interview.json:1552`). That is the right scope, but it is
not yet a complete workflow.

The architecture has `ModSvc -> RankCache` and `PostSvc -> ModSvc`, but no
explicit status write to the authoritative store and no invalidation path to
`CommentCache` (`data/book/reddit-hn/interview.json:125`,
`data/book/reddit-hn/interview.json:1553`). The `satisfies` row says removals
evict ranked and comment caches, but the diagram does not show the comment
cache side and the data model has no removal state
(`data/book/reddit-hn/interview.json:1625`).

Why it matters: for Reddit/HN-like systems, moderation is not just a cache
operation. The source of truth must record removed/spam/shadowed state, reads
must filter tombstones, listings must remove or downrank entries, comments must
hide or collapse removed subtrees, and async cache invalidation needs a bounded
freshness target.

Concrete fix: add a short moderation flow: mod action writes post/comment
status to the authoritative store, emits an invalidation event, removes or
penalizes the item in `RankCache`, invalidates affected `CommentCache` entries,
and leaves a tombstone or audit record. Add a Step 7 failure drill for delayed
moderation propagation.

### 4. Listing semantics are underspecified for top/new/global and pagination

The requirements name hot, top, new, per-community listings, and a global front
page (`data/book/reddit-hn/interview.json:258`). The design mostly explains
hot ranking and a generic per `(community, sort)` sorted set
(`data/book/reddit-hn/interview.json:981`). That is a good core, but the other
listing modes need one more layer of specificity.

Why it matters: "hot", "top", "new", and global front page have different
maintenance rules. `new` can be an append/time index, `top` usually needs a
time window and vote confidence or raw score, `hot` decays even without new
votes, and global front page needs candidate aggregation across communities.
Pagination is also tricky because scores change while a user is paging through
a listing.

Concrete fix: add a small listing-policy table: `hot` sorted by time-decay
score with periodic drift recompute, `top` sorted by score within a window,
`new` sorted by `created_at`, global front page built from active community
candidates or a separate global sorted set. Add a cursor rule, such as snapshot
token plus `(score, post_id)` seek cursor, and state how stale reads are
bounded.

### 5. The async vote pipeline needs explicit idempotent event semantics

Step 2 correctly stores one vote per `(user, item)` and emits a queue event for
changed votes (`data/book/reddit-hn/interview.json:614`,
`data/book/reddit-hn/interview.json:611`). The API response returns an
optimistic score (`data/book/reddit-hn/interview.json:306`). The missing detail
is what the event contains and how the ranker handles retries, duplicates, and
vote changes.

Why it matters: changing an upvote to a downvote is not the same as adding a
new downvote. It can change net score by two, and duplicated queue delivery
must not double-apply the delta. Fraud discounting also needs to know whether a
vote is authoritative, shadow-counted, discounted, or removed.

Concrete fix: specify that the vote store write produces an idempotent event
with `vote_id` or `(user_id, item_type, item_id, version)`, previous direction,
new direction, timestamp, and fraud/trust status. The ranker should either
re-read authoritative tallies or apply idempotent deltas keyed by version. The
API should label returned score as optimistic or estimated when ranking is
eventually consistent.

## System Design Soundness

The system's main decomposition is sound. `PostSvc` owns posts and comments,
`VoteSvc` owns idempotent vote writes, `EventQ` decouples vote ingestion from
ranking, `Ranker` maintains derived listing state, `RankCache` and
`CommentCache` serve the read-heavy paths, and `Fraud` plus `ModSvc` address
the integrity requirements (`data/book/reddit-hn/interview.json:11`,
`data/book/reddit-hn/interview.json:125`).

The strongest design decisions are treating ranked listings as derived state,
keeping vote writes fast, and acknowledging that ranking is eventually
consistent. The weaker decisions are mostly unstated rather than wrong: how
many sorted sets are maintained, how global candidates are selected, how score
drift is recomputed without vote events, how rank caches are rebuilt under load,
and how moderation state is represented in the source of truth.

The comments design is plausible for interview purposes. Materialized paths and
post-id sharding are good defaults for write-once threaded discussions
(`data/book/reddit-hn/interview.json:1121`). The next production detail would
be to define sibling ordering, collapsed/deleted comment behavior, max depth or
path encoding limits, and incremental loading cursors.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Vote Counter + Sort-on-Read

Strong. The step is intentionally simple and exposes the two failures that
matter: sort-on-read does not meet read latency at scale, and counter
increments break under retries and manipulation.

### Step 2: Idempotent Voting

Strong conceptually. The one-row-per-user-item invariant is the right teaching
point, and the sequence diagram is useful. Tighten the `recap.before`, which
currently says "Nothing" even though the learner is coming from the naive
baseline; it should refer to non-idempotent counters and sort-on-read state
(`data/book/reddit-hn/interview.json:611`).

Add event idempotency details here rather than waiting for a later step. This
is where candidates should learn that retries can happen both at the HTTP vote
request and at the queue/ranker consumer.

### Step 3: The Hot-Ranking Score

Strong. It presents the right alternatives and explains why raw vote count is
not enough. Add the continuous recompute rule: because time decay changes even
without new votes, the ranker needs periodic refresh or bucketed rescore for
active items, not only vote-event-triggered updates.

### Step 4: Precomputed Ranked Listings

Strong central step. The default sorted-set answer is the right one for the
latency target. Add maintenance semantics for each sort mode and global front
page, plus cursor stability under changing scores.

### Step 5: Threaded Comments

Good choice and good alternatives. Materialized path is a credible default for
deep, mostly append-only threads. The main missing teaching point is API/state:
the dataset should explicitly support comment creation, comment voting,
comment removal, sibling sorting, and incremental pagination.

### Step 6: Vote-Fraud and Abuse Prevention

Good topic and good trade-off between async discounting, synchronous blocking,
and trust-weighted voting (`data/book/reddit-hn/interview.json:1306`,
`data/book/reddit-hn/interview.json:1373`,
`data/book/reddit-hn/interview.json:1412`). Add one operational detail: what
signals are recorded, what happens after a fraud verdict changes, and how old
scores/listings are recomputed or invalidated.

### Step 7: Scaling, Hot Posts, and Moderation

This is the right closing step, but it is currently thinner than the preceding
decision steps. It has no options, no flow, and only one failure drill
(`data/book/reddit-hn/interview.json:1486`,
`data/book/reddit-hn/interview.json:1531`,
`data/book/reddit-hn/interview.json:1541`). Add a moderation propagation flow
and one or two more drills: vote queue lag on a viral post, delayed moderation
eviction, cache shard loss during front-page traffic, or comment-cache
invalidation for a removed subtree.

## Final Design Review

The final design integrates the components introduced in the walkthrough and
states the important derived-state principle: ranked and comment caches are
rebuildable over authoritative storage (`data/book/reddit-hn/interview.json:1552`).
That is the right final posture.

The final design would be stronger if it explicitly named the source-of-truth
tables behind moderation and comments, the listing-cache key space, and the
vote-event semantics. It currently says moderation removes items from
listings/comments, but the final view only has `ModSvc -> RankCache` and does
not show a direct comment-cache invalidation or authoritative status write
(`data/book/reddit-hn/interview.json:1553`).

## Concept Introduction and Learning Flow

The learning sequence is clear: naive read sorting, idempotent votes, ranking
formula, precomputed listings, comment trees, fraud, and final scaling. The
concepts are introduced just in time and tied to the step that uses them:
idempotent vote, time-decay ranking, precomputed listing, materialized path, and
vote discounting.

The only sequencing concern is that moderation appears as a requirement early
but is not developed until the last step. That can still work, but Step 7
should then be a fuller operational step with explicit state and invalidation
flow, not just a short close-out.

## Step-to-Final-Design Coherence

Most step-to-final-design mapping is coherent:

- `naive` motivates the move away from sort-on-read.
- `voting` introduces `VoteSvc`, `VoteStore`, and queue emission.
- `ranking` introduces `Ranker` and score recompute.
- `listings` introduces `RankCache` as derived state.
- `comments` introduces materialized paths and `CommentCache`.
- `fraud` introduces `Fraud` and vote discounting.
- `scale-mod` introduces `ModSvc`, cache rebuilds, batching, and moderation.

The main mismatch is Step 7's diagram. It includes `EventQ` and says vote
bursts are absorbed by the queue, but its view references `vote-eventq` without
including `VoteSvc`, so the renderer filters that edge and leaves the queue
story visually underconnected (`data/book/reddit-hn/interview.json:1493`,
`data/book/reddit-hn/interview.json:1502`). Use `eventq-ranker` in that view,
or include `VoteSvc` as a node.

## Realism Compared With Production Systems

The case is realistic at the mechanism level: async scoring, sorted-set style
listings, cache-as-derived-state, materialized-path threads, trust/fraud
signals, and moderation propagation are all plausible. It is less realistic in
operational contracts. Production systems would normally spell out:

- Queue delivery and ranker idempotency.
- Ranking recompute cadence for time-decay drift.
- Listing cursor stability and duplicate/gap avoidance.
- Global/front-page candidate generation.
- Post/comment status and tombstone filtering.
- Comment-cache invalidation after moderation.
- Backpressure behavior when the vote queue lags.
- Observability for p99 listing reads, queue lag, rank freshness, cache hit
  rate, fraud false positives, and moderation propagation delay.

Those are natural additions; they do not require changing the core design.

## Dataset and Renderer-Facing Observations

Validation and cross-reference checks were clean:

- `interview.json` parses as JSON.
- Step, pattern, `satisfies`, API sequence participant, and probe-link
  references resolve.
- Option-specific architecture views have link endpoints present in their node
  lists.

One visible renderer-facing issue remains: Step 7 has no options, so its
top-level view is rendered directly. The `vote-eventq` link is dropped because
`VoteSvc` is not in that view's nodes. Replace it with `eventq-ranker` or add
`VoteSvc`.

The top-level views for `listings`, `comments`, and `fraud` also contain
shared links whose endpoints are outside the top-level view, but their option
views are clean and are what the renderer shows by default. Treat those as
low-risk cleanup rather than user-visible breakage.

## Recommended Edits, Prioritized

### P1: Add quantitative capacity and hot-post budgets

Replace qualitative capacity labels with example numbers and derived work:
reads/sec, votes/sec, hot-post burst votes/sec, active community count,
front-page candidate count, score-worker throughput, listing-cache memory, and
ranking freshness.

### P1: Complete API and state contracts for comments, votes, and moderation

Add comment create/vote endpoints, moderation action endpoints, `item_type` and
event versioning in votes, post/comment status fields, and a derived listing
state description.

### P1: Make moderation propagation explicit

Add a Step 7 flow showing authoritative status write, invalidation event,
rank-cache removal, comment-cache invalidation, and tombstone/audit behavior.

### P2: Specify listing modes and cursor semantics

Define hot/top/new/global maintenance and add a cursor rule that avoids
duplicates or gaps while scores change.

### P2: Strengthen ranker/event idempotency

Describe event payloads and consumer behavior for duplicate delivery,
up-to-down changes, fraud discount changes, and recompute from authoritative
tallies.

### P3: Fix Step 7 diagram connectivity

Use `eventq-ranker` or add `VoteSvc` so `EventQ` is connected in the visible
scaling/moderation diagram.

### P3: Refresh interview script and level rubric

The script is clear but high level (`data/book/reddit-hn/interview.json:1662`).
Add prompts for capacity math, moderation state, listing cursor semantics, and
queue/ranker idempotency. Add a Staff expectation for operating rank freshness,
fraud false positives, and moderation propagation under viral traffic.

## What Not To Change

- Keep the naive baseline. It is a good teaching setup, not wasted space.
- Keep time-decay hot score as the default ranking choice.
- Keep precomputed sorted listings as the default read-path solution.
- Keep materialized path as the default comments solution.
- Keep async fraud discounting as the default integrity approach; synchronous
  blocking is correctly framed as an alternative with latency/false-positive
  costs.
- Keep caches framed as derived and rebuildable state.

## Bottom Line

This dataset is already a usable, coherent interview walkthrough. To make it
production-grade, add numbers, complete the API/data model contracts, and turn
moderation plus async scoring from stated components into explicit workflows.
The core design should stay intact.
