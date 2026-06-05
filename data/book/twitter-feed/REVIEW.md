# Review: Twitter / X Feed - System Design

Reviewed file: `data/book/twitter-feed/interview.json`
Review date: 2026-06-05

## Executive Summary

This is a strong, readable feed-design case. The central teaching arc is right:
start with naive read-time assembly, show why read-heavy fan-in collapses, move
to fanout-on-write, expose the celebrity problem, converge on hybrid fanout,
then finish with hydration, ranking, pagination, and sharding.

The remaining gaps are mostly production-realism gaps rather than structural
breaks. The largest issue is that follow/unfollow is stated as a current-state
requirement, but the design only explains future fanout behavior. The next
largest issue is that deletes, edits, blocks, and visibility filtering are left
as follow-ups even though the chosen "store ids, hydrate bodies" approach
depends on these semantics. The fanout queue is also under-specified for a
system whose hardest operational risk is async backlog and partial fanout.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Core hybrid fanout design is sound; follow/unfollow, deletes, and ranked pagination need more precise semantics. |
| Production realism | 3.5/5 | Good fanout and cache intuition; thin on queue operations, idempotency keys, visibility filtering, and monitoring. |
| Pedagogical flow | 4.5/5 | The six-step progression is clean and interview-friendly. |
| Dataset/rendering fit | 4.5/5 | JSON parses and reference checks are clean; only minor renderer-facing polish found. |

## What Works Well

- The case names the real tension immediately: fanout-on-write versus
  fanout-on-read for a heavy-tailed follower graph
  (`data/book/twitter-feed/interview.json:3`).
- The capacity section gives memorable anchor numbers for read volume, write
  volume, average followers, and celebrity followers
  (`data/book/twitter-feed/interview.json:355`).
- Step 1 forces the candidate to quantify the naive fan-in path:
  300K reads/sec times about 200 followees becomes about 60M tweet-store
  lookups/sec (`data/book/twitter-feed/interview.json:681`,
  `data/book/twitter-feed/interview.json:696`).
- Step 2 teaches the important storage trade-off: store tweet ids in timelines,
  not full tweet bodies (`data/book/twitter-feed/interview.json:742`).
- Steps 3 and 4 make the celebrity exception clear and converge on hybrid
  fanout with an explicit threshold knob
  (`data/book/twitter-feed/interview.json:935`,
  `data/book/twitter-feed/interview.json:1005`).
- The final design integrates write fanout, pull-for-celebrities, tweet
  hydration, ranking, media CDN, and search in one coherent diagram
  (`data/book/twitter-feed/interview.json:1646`).

## Highest-Impact Issues

### 1. Follow/unfollow does not actually satisfy "current follow set"

The requirements say follow/unfollow must be reflected in the current timeline
(`data/book/twitter-feed/interview.json:343`). The API only has `POST
/v1/follow`, not an unfollow operation, and its description says future tweets
fan out to the follower (`data/book/twitter-feed/interview.json:503`). The
wrap-up similarly says the graph edge changes which timelines a post fans out
to (`data/book/twitter-feed/interview.json:1717`).

That is not enough for current-state correctness. If a user unfollows an
author, the precomputed timeline can still contain that author's old tweet ids.
If a user follows a new author, the cached home timeline may not contain any of
that author's recent tweets unless there is a backfill or read-time merge. The
dataset knows this is an issue because it asks about follow backfill as a
follow-up (`data/book/twitter-feed/interview.json:1833`), but it does not teach
the answer in the design.

Concrete fix: add explicit follow and unfollow semantics. A good minimal design
is: `POST /v1/follows/{targetUserId}` and `DELETE /v1/follows/{targetUserId}`;
on follow, lazily backfill the target author's recent tweet ids or temporarily
merge them on read; on unfollow, filter by the current follow graph at hydrate
time and optionally run async timeline cleanup. Mention that timeline entries
may need author ids or that hydration must return author ids cheaply so
unfollow/block filtering is not an expensive store hit.

### 2. Delete, edit, block, and visibility propagation are left out of the core design

The chosen option correctly says storing ids makes edits/deletes easier because
tweet bodies are hydrated from a shared source
(`data/book/twitter-feed/interview.json:746`). But the actual data model has no
tweet status, version, deleted timestamp, visibility policy, or author state
(`data/book/twitter-feed/interview.json:517`). Deletes and edits appear only as
a follow-up question (`data/book/twitter-feed/interview.json:1830`).

Why it matters: a real timeline cannot rely on "the tweet id is still in many
caches, but hydration will sort it out" without defining what hydration sees.
Deletes, protected accounts, mutes, blocks, suspensions, age restrictions, and
policy takedowns are all read-time filters that can determine whether a cached
id is renderable. Search indexing also needs de-index or tombstone behavior
(`data/book/twitter-feed/interview.json:282`).

Concrete fix: add a small "Visibility and mutations" subsection or step extra.
The tweet model should include `status`, `deleted_at`, `updated_at`, `version`,
and maybe `visibility`. The read path should filter tombstones and denied
authors after hydration, then backfill more candidates if filtering creates a
short page. The write path should invalidate `TweetCache`, update `Search`, and
avoid trying to delete the id from every timeline synchronously.

### 3. Async fanout operations are too thin for the main reliability risk

The design uses a fanout queue and workers, which is the right shape
(`data/book/twitter-feed/interview.json:204`,
`data/book/twitter-feed/interview.json:855`). It also includes one useful
failure drill for a fanout worker crash
(`data/book/twitter-feed/interview.json:926`). But it does not specify how
fanout jobs are partitioned, retried, deduplicated, rate-limited, or observed.

Why it matters: the product promise is "followers see posts within seconds"
(`data/book/twitter-feed/interview.json:350`). That promise is governed less by
the existence of a queue and more by queue lag, worker saturation,
per-author/per-follower idempotency, poison messages, DLQs, and backpressure
when a burst or celebrity misclassification happens. The `sre-monitoring`
reference is present but unused by steps (`data/book/twitter-feed/interview.json:1901`).

Concrete fix: add a deep dive under Step 2 or Step 6 for fanout operations:
partition jobs by author or follower shard, carry a stable `tweet_id` and
`fanout_job_id`, make timeline writes idempotent by `(user_id, tweet_id)`,
retry with exponential backoff, send poison jobs to a DLQ, cap per-user timeline
length atomically, and alert on fanout lag, queue depth, retry rate, duplicate
suppression, and cache write errors.

### 4. Capacity math needs sharper derivations

The capacity section has good anchor numbers, but the derived fanout number is
hand-wavy. It says peak fanout writes are "tens of millions" and notes
"5K tweets/s x avg fanout" (`data/book/twitter-feed/interview.json:381`). With
the stated average follower count of about 200
(`data/book/twitter-feed/interview.json:371`), the average fanout write load is
about 1M timeline pushes/sec, not tens of millions. Tens of millions is
plausible for bursty events or a 100M-follower celebrity post, but the math
should say that explicitly.

Concrete fix: split average and peak math. For example: average push work is
`5K tweets/sec * 200 followers = 1M timeline writes/sec` before excluding
celebrities; a 100M-follower account cannot be pushed within a few seconds
without about 10M-50M timeline writes/sec for that one post; a capped
`home_timeline` of 800 ids for 250M active users is about 200B ids before cache
overhead. Add read-side candidate math too: timeline ids fetched per request,
hydration batch size, tweet-cache hit ratio, and ranker candidate count.

### 5. Ranked pagination is under-specified

Step 5 says pagination can use the last tweet's snowflake id so infinite scroll
is stable (`data/book/twitter-feed/interview.json:1312`). That works for a
reverse-chronological feed, but the default option is a relevance-ranked
timeline (`data/book/twitter-feed/interview.json:1343`). Its own cons mention
that pagination must remain stable as scores change
(`data/book/twitter-feed/interview.json:1352`), but the design never gives a
mechanism.

Concrete fix: distinguish the two cursor modes. Reverse chronological can use a
snowflake boundary. Ranked timelines should use an opaque cursor containing a
snapshot id or candidate-window version, plus the last `(score, tweet_id)` tie
breaker. If scores are recalculated every request, say the product accepts some
reordering; otherwise pin the candidate set for a short TTL.

## System Design Soundness

The core architecture is sound for the classic home-timeline problem. Tweets
are authoritative in `TweetDB`, follower edges are authoritative in `GraphDB`,
home timelines are derived cache state, and tweet ids are hydrated from a
shared tweet cache. That separation is exactly what keeps fanout storage under
control (`data/book/twitter-feed/interview.json:562`).

The main soundness gap is semantics around state changes after fanout. The
design is strongest when a new public tweet is posted by an account whose
follower classification is known. It is weaker for after-the-fact changes:
unfollow, block, delete, edit, protect/unprotect, suspension, and search
de-index. These do not require a new top-level architecture, but they do need
explicit read-time filtering and cache invalidation rules.

The API should also carry more production contract details. `POST /v1/tweets`
should include an idempotency key or client-generated request id so client
retries cannot duplicate tweets (`data/book/twitter-feed/interview.json:389`).
The read API is described as authenticated, but the sequence jumps from
`Client` directly to `ReadSvc` and bypasses `API`
(`data/book/twitter-feed/interview.json:456`), unlike the main architecture's
`API -> ReadSvc` link (`data/book/twitter-feed/interview.json:186`).

## Step-by-Step Pedagogical Review

### Step 1: Naive: Assemble Timeline on Every Read

Strong. The step is intentionally correct first, then fails on quantified fan-in
load. The trap is useful because it forces candidates to abandon read-time
assembly at this scale (`data/book/twitter-feed/interview.json:693`).

### Step 2: Fanout-on-Write: Precompute Timelines

Strong core step. The "ids not full copies" option is the right default and the
trade-off list is crisp. Add operational depth here: job partitioning,
idempotency, dedup, queue lag, DLQ behavior, and rate limiting. The existing
failure drill is a good seed but should be expanded
(`data/book/twitter-feed/interview.json:928`).

### Step 3: The Celebrity Problem: Fanout-on-Read

Strong. It explains why pure fanout-on-write collapses for mega-accounts and
why recent celebrity tweets are likely cache-hot
(`data/book/twitter-feed/interview.json:937`). The next improvement is to
connect this to a concrete candidate budget on reads: how many celebrity
followees do we pull, how many recent tweets per celebrity, and what happens
when a user follows many high-volume accounts?

### Step 4: Hybrid Fanout

This is the best teaching step. The options are real alternatives, not straw
men, and the default hybrid choice follows naturally from the previous two
steps. The deep dive on threshold selection is good
(`data/book/twitter-feed/interview.json:1277`).

Add one transition-state detail: when an account crosses the threshold, the
dataset says to stop pushing and optionally backfill lazily
(`data/book/twitter-feed/interview.json:1300`), but the read path should also
explain how it avoids duplicates and gaps across the cutoff time.

### Step 5: Read Path: Hydrate, Rank, Paginate

Good separation of timeline ids from tweet bodies. The cache-aside sequence is
clear, and the three ordering options are useful. The missing part is ranked
cursor stability, plus short-page handling after filtering tombstones, blocks,
or unavailable tweets.

### Step 6: Scaling the Social Graph and Stores

Good access-pattern-based sharding discussion. The two adjacency indexes are
the right point to test in an interview
(`data/book/twitter-feed/interview.json:1581`). The bottlenecks section is too
short for a staff-level case. Add fanout lag, hot author shards, graph hot
edges, cold timeline rebuild budgets, cache memory limits, and regional
replication/read availability.

## Final Design Review

The final design correctly integrates the main components introduced during the
walkthrough (`data/book/twitter-feed/interview.json:1646`). It is a credible
target design for a classic timeline interview.

The final design should be tightened in two places. First, it should say that
the read service filters hydrated candidates against current visibility and
relationship state before returning them. Second, search and media should either
be framed as extensions or given minimal first-class behavior. Search is listed
as a requirement (`data/book/twitter-feed/interview.json:345`) and a final
design component (`data/book/twitter-feed/interview.json:1666`), but no step
teaches indexing, freshness, deletion, or query fanout.

## Concept Introduction and Learning Flow

The concept flow is excellent for fanout: naive read fan-in, fanout-on-write,
fanout-on-read, hybrid fanout, cache-aside hydration, and Snowflake ids. The
case introduces each concept close to where the candidate needs it.

Two concepts should be pulled forward from follow-ups into the main walkthrough:
visibility filtering and derived-state repair. Both are central to the chosen
architecture. Without them, "timeline cache is rebuildable derived state" is
present (`data/book/twitter-feed/interview.json:1641`), but the reader does not
see how that interacts with current follow state, deletes, or blocks.

## Step-to-Final-Design Coherence

The main path is coherent:

- Step 1 exposes read fan-in.
- Step 2 solves read latency with precomputed timeline ids.
- Step 3 identifies the celebrity write-amplification exception.
- Step 4 reconciles push and pull.
- Step 5 makes cached ids renderable.
- Step 6 scales the state stores.

The final design includes all core components from those steps. The weaker
coherence points are secondary requirements: profile timeline, follow/unfollow,
search, and media. They are listed in requirements/API/final design but are not
developed with the same step discipline as fanout.

## Realism Compared With Production Systems

Compared with production social feeds, the dataset is realistic on the core
read/write trade-off and less realistic on lifecycle and operations. A real
implementation would need:

- Per-request idempotency for tweet creation.
- Fanout job state, retries, DLQs, and lag SLOs.
- Read-time filtering for deleted tweets, protected accounts, muted/blocked
  authors, suspensions, and policy takedowns.
- Async cache/search invalidation for edits and deletes.
- A clear follow/unfollow backfill and cleanup strategy.
- Ranker feature freshness, fallback behavior, and cursor stability.
- Regional topology, cache replication, and degraded read modes.

The interview does not need all of that in full detail, but it should include
enough hooks that a senior or staff candidate can show judgment without having
to invent an entirely separate design outside the walkthrough.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully with `python3 -m json.tool`.
- Recursive checks found no missing string node references, missing link
  references, missing highlights, missing pattern step links, missing satisfies
  step links, or missing probe links.
- `toProbeFurther.links` contains seven links, and all `probeLinks` references
  resolve.
- The local `Scorer` node in the lightweight heuristic option has an `id` and
  label but no `type` (`data/book/twitter-feed/interview.json:1439`). This is
  not a validation break, but adding `"type": "service"` would make the
  rendering intent explicit.
- The `sre-monitoring` probe link is present but unused
  (`data/book/twitter-feed/interview.json:1901`). Either reference it from the
  fanout operations or graph-scale step, or remove it.
- No docs rebuild is needed for this review-only file; `REVIEW.md` is skipped
  by the build.

## Recommended Edits, Prioritized

### P1: Make follow/unfollow and visibility semantics first-class

Add unfollow API behavior, follow backfill/lazy merge, unfollow cleanup or
read-time filtering, and minimal visibility fields on tweets/users. This closes
the biggest gap between the stated requirements and the design.

### P1: Add fanout operations depth

Add a Step 2 or Step 6 deep dive covering fanout job partitioning,
idempotency, retries, DLQs, lag SLOs, duplicate suppression, and alerting. Use
the existing worker-crash drill as the starting point.

### P2: Tighten capacity math

Separate average fanout writes from burst/celebrity fanout, estimate timeline
cache memory, and add read-side hydration/ranking candidate numbers.

### P2: Specify ranked cursor semantics

Explain why snowflake cursors work for reverse chronological timelines and what
opaque cursor state is needed for relevance-ranked timelines.

### P2: Decide how much search, profile timelines, and media belong in scope

Either mark search/media/profile as extensions or add minimal APIs, data model
fields, and design notes that make the final diagram honest.

### P3: Polish renderer-facing details

Add `type: "service"` to the local `Scorer` node, route the GET timeline API
sequence through `API` for consistency, and either use or remove the unused
`sre-monitoring` probe link.

## What Not To Change

Keep the six-step spine. It is the right interview progression and should not
be diluted with unrelated social-network features. Also keep the "store tweet
ids, hydrate later" default; that is the most important implementation choice
in the dataset.

## Bottom Line

This is already a solid feed-system interview. Make the state-change semantics
and fanout operations more explicit, tighten the capacity math, and it becomes
a strong production-realistic case rather than just a clean fanout-pattern
walkthrough.
