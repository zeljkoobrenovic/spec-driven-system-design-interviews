# Review: Twitter / X Feed - System Design

Reviewed file: `data/book/twitter-feed/interview.json`
Review date: 2026-06-05

## Executive Summary

This review was updated against the current `interview.json` after the recent
dataset changes. The case is now materially stronger than the previous review:
the capacity section separates average fanout from celebrity burst work, tweet
creation has an idempotency key, follow and unfollow have explicit API
semantics, tweet/author visibility state is in the data model, fanout queue
operations are covered, ranked cursor stability is explained, and the local
`Scorer` node now has an explicit type.

The remaining issues are narrower. The profile timeline requirement is still
not represented in the API or `satisfies` mapping. Search is present in the API
and final design, but it is still treated as a thin extension despite being a
functional requirement. The read path has a ranking dependency on the critical
path, but the fallback/latency behavior remains a follow-up rather than part of
the design. The core fanout teaching path is sound.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | Hybrid fanout, visibility filtering, id hydration, and operational queue behavior are now coherent; profile/search scope still needs tightening. |
| Production realism | 4.25/5 | Much better on idempotency, tombstones, filtering, DLQs, lag metrics, and cache rebuilds; ranker fallback and search visibility remain light. |
| Pedagogical flow | 4.5/5 | The six-step progression remains clean and interview-friendly, with useful deep dives added at the right points. |
| Dataset/rendering fit | 4.75/5 | JSON parses; node/link/probe/satisfies references resolve; only optional API-flow coverage is thin. |

## What Works Well

- The case keeps the right central tension in focus: fanout-on-write versus
  fanout-on-read for a heavy-tailed follower graph
  (`data/book/twitter-feed/interview.json:3`).
- Capacity math now distinguishes steady-state average work from bursty
  celebrity fanout, timeline-cache memory, and read-side hydration
  (`data/book/twitter-feed/interview.json:382`,
  `data/book/twitter-feed/interview.json:397`).
- `POST /v1/tweets` now carries an idempotency key, so retry behavior is part
  of the API contract instead of an unstated assumption
  (`data/book/twitter-feed/interview.json:404`).
- Follow and unfollow semantics now include lazy follow backfill, read-time
  filtering after unfollow, and async cleanup
  (`data/book/twitter-feed/interview.json:527`,
  `data/book/twitter-feed/interview.json:534`).
- The data model now has the fields needed for visibility and mutation
  semantics: tweet status, visibility, version, deleted timestamp, protected
  users, suspended users, and block/mute relationships
  (`data/book/twitter-feed/interview.json:549`,
  `data/book/twitter-feed/interview.json:658`).
- Step 2 now explains fanout operations with partitioning, chunking,
  idempotent timeline writes, retries, DLQs, capped lists, backpressure, and
  lag alerts (`data/book/twitter-feed/interview.json:998`).
- Step 5 now teaches that cached timeline ids are candidates, not guarantees;
  hydration is followed by current-state filtering and backfill
  (`data/book/twitter-feed/interview.json:1603`).
- Ranked pagination is now separated from chronological pagination with an
  opaque cursor/snapshot design (`data/book/twitter-feed/interview.json:1630`).

## Highest-Impact Issues

### 1. Profile timeline is still a stated requirement without design coverage

The requirements include viewing a single user's profile timeline
(`data/book/twitter-feed/interview.json:344`). The final design mentions it as
a "first-class extension" and says it is the author's own tweet range
(`data/book/twitter-feed/interview.json:1825`), but there is no API endpoint,
no `satisfies.functional` row, and no step or deep dive explaining the access
path.

Why it matters: profile timeline reads are simpler than home timelines, but
they exercise different storage behavior. They need an author-scoped range
query, privacy filtering for protected accounts, tombstone filtering, media
hydration, cursor semantics, and potentially different cache policy. Leaving it
out makes the "functional requirements -> final design" mapping incomplete.

Concrete fix: add `GET /v1/users/{userId}/tweets?cursor=&limit=` or
`GET /v1/profiles/{userId}/timeline`, add a `satisfies.functional` row for the
profile timeline requirement, and add a short Step 5 or Step 6 note explaining
that it is served by an author-id/time range over `TweetDB` or an author
timeline index, then hydrated and filtered through the same read path.

### 2. Search is represented, but still under-taught

Search is marked as a functional requirement, even if secondary
(`data/book/twitter-feed/interview.json:345`). The dataset now includes
`GET /v1/search`, `Search` in the final design, write-time indexing, and
tombstone de-indexing (`data/book/twitter-feed/interview.json:541`,
`data/book/twitter-feed/interview.json:1843`,
`data/book/twitter-feed/interview.json:1909`). That closes the previous
"missing component" gap.

The remaining gap is teaching depth. There is no search sequence, no index data
model, no freshness target, and no explanation of how search results are
filtered for protected accounts, blocks/mutes, suspensions, deleted tweets, or
viewer-specific permissions. The `satisfies` row points search to `read-path`,
which is only partially true: search has its own indexing and query-serving
path, then reuses hydration and visibility filtering.

Concrete fix: either explicitly scope search as an extension, or add a small
search subsection with: async index write from `WriteSvc`, tombstone/de-index
behavior, inverted-index query, hydration through `TweetCache`, viewer-specific
visibility filtering, and an eventual-consistency freshness caveat.

### 3. Ranker fallback is still outside the main design

The default Step 5 option uses a ranking service on the read path
(`data/book/twitter-feed/interview.json:1457`). The non-functional target is
p99 timeline reads under 200 ms (`data/book/twitter-feed/interview.json:348`),
but ranker slowness or outage is only a follow-up question
(`data/book/twitter-feed/interview.json:2014`).

Why it matters: once relevance ranking is the default option, ranking is part
of the read availability story. A strong interview answer should say what the
read service does when feature fetch or model serving is slow: fall back to
reverse chronological, use a cached score, cap candidate count, set a hard
ranker timeout, or return unranked results with a degraded marker.

Concrete fix: add one bullet to Step 5 or a failure drill: "Ranker timeout:
after N ms, skip the ranking service and return reverse-chronological hydrated
candidates; alert on timeout rate and keep the timeline p99 SLO intact."

### 4. Celebrity pull budgets and threshold transitions need one more precise rule

The hybrid design correctly uses a threshold and notes that account
classification can change (`data/book/twitter-feed/interview.json:1122`,
`data/book/twitter-feed/interview.json:1394`). The read path also merges pushed
and pulled ids. The missing piece is the bounded work rule for users who follow
many high-volume accounts and for accounts that cross the threshold while old
ids may already exist in follower caches.

Concrete fix: add a small rule of thumb: fetch the last `K` tweets from at most
`M` pulled celebrities per read, dedupe by `tweet_id` against pushed timeline
ids, and use a cutoff timestamp or version when an account flips between push
and pull so the read path avoids gaps and duplicates during the transition.

## System Design Soundness

The main architecture is sound for a classic home-timeline interview. Tweets
are authoritative in `TweetDB`, follower relationships are authoritative in
`GraphDB`, home timelines are derived cache state, fanout is asynchronous, and
reads hydrate ids from shared tweet storage/cache. That separation is exactly
what keeps fanout storage bounded and makes edits/deletes feasible.

The strongest recent improvement is that state changes after fanout are no
longer hand-waved. The design now says cached ids must be filtered against
current tweet status, author status, visibility, unfollows, mutes, and blocks
before rendering (`data/book/twitter-feed/interview.json:1424`,
`data/book/twitter-feed/interview.json:1603`). This fixes the previous
correctness gap around precomputed timeline entries.

The weak area is scope closure. Home timeline is covered deeply. Profile
timeline and search are listed as requirements, but they are not developed with
the same rigor. This can be solved without adding new top-level architecture:
profile timeline is an author range read plus existing hydration/filtering;
search is an index query plus existing hydration/filtering.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Assemble Timeline on Every Read

Strong. The step is intentionally correct first, then fails on quantified
fan-in load. The trap is useful because it forces candidates to abandon
read-time assembly at this scale.

### Step 2: Fanout-on-Write: Precompute Timelines

Now very strong. The "ids not full copies" default is the right choice, and
the new operations deep dive turns the queue from a box on the diagram into a
real production mechanism: partitioning, chunking, idempotency, retries, DLQs,
lag metrics, and backpressure.

### Step 3: The Celebrity Problem: Fanout-on-Read

Strong. It explains why pure fanout-on-write collapses for mega-accounts and
why recent celebrity tweets are likely cache-hot. The next useful addition is a
bounded read budget for pulled celebrity candidates.

### Step 4: Hybrid Fanout

This remains the best teaching step. The options are real alternatives, not
strawmen, and the default hybrid choice follows naturally from the previous two
steps. Add a little more precision around dedupe/cutoff behavior when an
account crosses the celebrity threshold.

### Step 5: Read Path: Hydrate, Rank, Paginate

Much improved. It now teaches visibility filtering, short-page backfill,
delete/edit behavior through shared hydration, and distinct cursor semantics
for chronological versus ranked feeds. The remaining production gap is ranker
timeout/fallback behavior on the p99 read path.

### Step 6: Scaling the Social Graph and Stores

Strong. The two adjacency indexes are the right interview pressure point, and
the bottlenecks section now covers cache shard loss, fanout lag, hot author
shards, graph hot edges, cold rebuild budgets, memory pressure, and regional
read degradation.

## Final Design Review

The final design now integrates the main components introduced during the
walkthrough: write service, tweet store, media store/CDN, fanout queue, fanout
service, graph service/store, timeline cache, read service, tweet cache,
ranker, and search (`data/book/twitter-feed/interview.json:1823`).

Its description is also more honest than before: it explicitly says reads
merge pushed and pulled ids, hydrate through the tweet cache, filter against
current relationship and visibility state, optionally rank, and use a ranked
candidate-snapshot cursor where needed
(`data/book/twitter-feed/interview.json:1825`).

The final design's only notable mismatch is that search and profile timelines
are called "first-class extensions" even though one is a functional requirement
and the other is not mapped in `satisfies`. Either make them first-class in the
walkthrough, or mark them explicitly out of scope in the requirements.

## Concept Introduction and Learning Flow

The concept flow is excellent: naive fan-in, fanout-on-write, id-only timeline
entries, fanout-on-read, hybrid fanout, cache-aside hydration, visibility
filtering, ranking, cursor stability, sharding, and rebuildable derived state.
The new deep dives introduce the production concerns close to where the
candidate needs them rather than as a disconnected wrap-up.

The only learning-flow risk is scope creep near the end. Search, media, and
profile timelines appear in the requirements/final diagram, but only media has
a straightforward "serve via CDN" story and search/profile have little
interview-time development. That is fine if they are explicitly labeled as
extensions; it is weaker if they remain full requirements.

## Step-to-Final-Design Coherence

The core spine is coherent:

- Step 1 exposes read fan-in.
- Step 2 solves read latency with precomputed timeline ids.
- Step 3 exposes celebrity write amplification.
- Step 4 reconciles push and pull.
- Step 5 makes cached ids renderable, filterable, rankable, and pageable.
- Step 6 scales the stores and cache tiers.

The final design includes every core component introduced by that spine. The
remaining coherence gap is secondary functionality: profile timeline has no
step/API/satisfies mapping, and search has a component/API/satisfies mapping
without much teaching content.

## Realism Compared With Production Systems

Compared with production social feeds, the dataset is now realistic on the
core mechanics: idempotent tweet creation, async fanout, at-least-once
processing, idempotent timeline writes, tombstones, read-time visibility
filtering, cache rebuild, lag monitoring, and celebrity fanout avoidance.

A production implementation would still need more detail on:

- Ranker timeout, feature-store latency, cached scores, and degraded ordering.
- Search index freshness, protected-account filtering, and delete propagation.
- Profile timeline pagination/cache policy.
- Celebrity pull candidate budgets and duplicate/gap handling at threshold
  transitions.
- Multi-region write ownership, cache replication lag, and cross-region
  follower graph consistency.

Those are appropriate as senior/staff extensions; only profile timeline and
search need clearer treatment because they are already in the stated
requirements.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Structural checks found no missing step string node references, missing link
  references, missing pattern step links, missing `satisfies` step links, or
  missing probe-link references.
- The earlier missing-type issue on the local `Scorer` node is resolved with
  `"type": "service"` (`data/book/twitter-feed/interview.json:1554`).
- The `sre-monitoring` probe link is now used by Step 2
  (`data/book/twitter-feed/interview.json:920`).
- Follow, unfollow, and search APIs do not include sequence diagrams. That is
  not a schema problem, but adding sequences for follow/unfollow and search
  would make the API Flows wrap-up more complete.
- No docs rebuild is needed for this review-only file; `REVIEW.md` is
  repo-only and skipped by the build.

## Recommended Edits, Prioritized

### P1: Close the profile timeline requirement

Add a profile timeline read API, a `satisfies.functional` row, and a short note
that the path is an author-scoped tweet range read plus shared hydration,
visibility filtering, and cursor pagination.

### P1: Decide whether search is first-class or explicitly secondary

If first-class, add a small search path/deep dive covering async indexing,
tombstone de-indexing, query serving, hydration, and viewer-specific visibility
filtering. If secondary, label it clearly as an extension and keep the final
diagram from implying equal walkthrough depth.

### P2: Add ranker timeout/fallback behavior

Document the p99 read-path fallback when the ranker or features are slow:
timeout, return chronological or cached-score ordering, alert, and preserve the
timeline read SLO.

### P2: Bound the celebrity pull path

Specify `K` recent tweets from at most `M` pulled celebrities, dedupe by
`tweet_id`, and use a cutoff/version during threshold transitions to avoid
gaps and duplicates.

### P3: Add optional API sequences for follow/unfollow/search

The existing post and home-timeline API sequences are useful. Follow,
unfollow, and search can stay sequence-less, but adding compact sequences would
make the API Flows section more balanced.

## What Not To Change

Keep the six-step spine. It is the right interview progression and should not
be diluted with unrelated social-network features. Also keep the "store tweet
ids, hydrate later" default; it is the most important implementation choice in
the dataset.

## Bottom Line

The recent changes moved this from a clean fanout-pattern walkthrough to a
production-realistic social-feed case. The remaining work is mostly scope
closure: either teach profile timeline and search as requirements, or label
them as extensions. Add ranker fallback and celebrity pull budgets, and the
case is very close to flagship quality.
