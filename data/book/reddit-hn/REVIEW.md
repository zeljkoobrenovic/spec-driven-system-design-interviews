# Review: Reddit / Hacker News - System Design

Reviewed file: `data/book/reddit-hn/interview.json`
Review date: 2026-06-05

## Executive Summary

The recent updates substantially improved this interview. The previous high
impact gaps around quantitative capacity, comment/moderation APIs, vote event
idempotency, listing semantics, and Step 7 moderation propagation are now
addressed in the dataset. The case has moved from a good conceptual walkthrough
to a strong production-oriented teaching artifact.

The remaining issues are narrower. The main risk is that the cache and hot-key
capacity story is still too optimistic for the scale being claimed: 100k active
communities, multiple sort/window sets, top-1000 members, and replicas likely
cost far more than the stated 5-10 GB once real sorted-set overhead is counted.
The dataset also names stable listing snapshots, moderation restore, fraud
signals, and operational SLOs, but it does not yet define those contracts in
enough detail for a top-tier production interview.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | Core mechanisms are now coherent: idempotent versioned votes, time-decay ranking, precomputed listings, materialized-path comments, fraud discounting, and explicit moderation propagation. |
| Production realism | 4.25/5 | Much stronger after the latest pass; cache sizing, hot-key mitigation, audit/privacy, and operational contracts still need precision. |
| Pedagogical flow | 4.5/5 | The sequence teaches one pressure point at a time and the new details are introduced where they belong. |
| Dataset/rendering fit | 4.75/5 | JSON parses, structured views resolve, option/final diagrams are clean, and the old Step 7 dropped-edge problem is fixed. |

## What Works Well

- The capacity section now gives concrete sizing anchors: ~50M DAU, ~150k
  listing reads/sec, ~50k comment reads/sec, ~10k votes/sec, ~12k score-worker
  events/sec, ~100k active communities, and a < 5 s ranking freshness target
  (`data/book/reddit-hn/interview.json:282`).
- The API now covers the behaviors promised by the requirements: community
  listing, global front page, comment read/create, comment vote, and moderation
  removal (`data/book/reddit-hn/interview.json:448`,
  `data/book/reddit-hn/interview.json:455`,
  `data/book/reddit-hn/interview.json:462`,
  `data/book/reddit-hn/interview.json:469`,
  `data/book/reddit-hn/interview.json:476`).
- The data model now supports the main invariants. Posts and comments carry
  status/tombstone fields, votes include `item_type`, `version`, and
  `trust_status`, and listing cache state is explicitly derived
  (`data/book/reddit-hn/interview.json:484`,
  `data/book/reddit-hn/interview.json:538`,
  `data/book/reddit-hn/interview.json:588`,
  `data/book/reddit-hn/interview.json:622`).
- Step 2 now teaches idempotency end-to-end, including duplicate queue delivery
  and up-to-down vote deltas (`data/book/reddit-hn/interview.json:755`).
- Step 3 now calls out the periodic drift pass needed because time decay changes
  even without new votes (`data/book/reddit-hn/interview.json:895`).
- Step 4 now distinguishes hot, top, new, and global front-page maintenance, and
  introduces seek cursors plus bounded listing snapshots
  (`data/book/reddit-hn/interview.json:1124`,
  `data/book/reddit-hn/interview.json:1125`).
- Step 5 now treats comments as first-class voted items and handles tombstones,
  incremental loading, and per-subtree cursors
  (`data/book/reddit-hn/interview.json:1274`,
  `data/book/reddit-hn/interview.json:1275`).
- Step 7 is now a real operational close-out. It explains queue backpressure,
  moderation status writes, rank/comment cache invalidation, status-filtered
  reads, and cache rebuilds (`data/book/reddit-hn/interview.json:1647`,
  `data/book/reddit-hn/interview.json:1648`,
  `data/book/reddit-hn/interview.json:1753`).

## Highest-Impact Issues

### 1. Listing-cache sizing is likely too optimistic

The capacity section estimates listing-cache memory at 5-10 GB for roughly
100k communities x 3 sorts x top-1000 ids, plus overhead and replicas
(`data/book/reddit-hn/interview.json:324`). The raw member id math is useful,
but it underplays the actual cost of a production sorted-set tier. Sorted-set
members need keys, scores, object overhead, indexes/skip lists or equivalent
structures, allocator overhead, windows for top/day/week/all, global candidate
sets, replicas, and possibly per-region copies.

Why it matters: the design's central read-path answer is "precompute listings
in cache." If the memory estimate is low by an order of magnitude, the
candidate may miss the real trade-off between caching every community/sort and
caching only active communities, shrinking top-N, using tiered storage, or
building cold listings lazily.

Concrete fix: replace the single 5-10 GB estimate with a two-line model: raw
member bytes versus realistic in-memory sorted-set overhead plus replicas. Then
state a policy such as "maintain top-1000 for active communities, top-100 for
cold communities, evict inactive sort/window sets, and rebuild cold listings on
demand." This keeps the same architecture but makes the cost and cache-coverage
trade-off honest.

### 2. Hot-key and partition behavior needs one more explicit design decision

Step 7 says viral posts are handled by queues, batched recompute, replicated
caches, and sharding by id/post (`data/book/reddit-hn/interview.json:1647`,
`data/book/reddit-hn/interview.json:1649`). That is directionally right, but it
does not fully say how hot write keys and hot read keys are spread. A single
viral post concentrates vote writes, event traffic, score updates, and listing
updates. A single front-page or hot-community listing can also become a hot
cache key even if the cache is replicated.

Why it matters: "use a queue" is not by itself a hot-key solution. The design
should say whether vote events are partitioned by item, by user, or by vote row;
whether rank recompute coalesces many vote events for one post into one score
update; how listing writes avoid fanout storms; and how hot listing reads are
served from replicas, local process caches, CDN/edge caches, or page-sharded
keys.

Concrete fix: add a Step 7 paragraph or failure drill for hot-key handling:
coalesce score updates per post over a short interval, partition vote rows so
idempotency remains local, cap write fanout to listing sets, and serve hot
listing pages from replicated/read-through caches with stale-while-revalidate.

### 3. Operational contracts are named but not fully specified

The dataset now mentions a < 5 s rank freshness target, cursor snapshot tokens,
status-filtered reads, cache rebuilds, queue lag alerts, moderation propagation
delay, and fraud false-positive rates (`data/book/reddit-hn/interview.json:329`,
`data/book/reddit-hn/interview.json:1125`,
`data/book/reddit-hn/interview.json:1761`,
`data/book/reddit-hn/interview.json:1953`). Those are exactly the right
production concerns, but the contracts remain prose-level.

Why it matters: this interview is now strong enough that a senior/staff
candidate should be pushed on measurable behavior. What does the listing cursor
token contain? How long is a listing snapshot valid? What is the degraded-read
path when `RankCache` is rebuilding? What metric pages the team when moderation
propagation exceeds the bound? Which queue lag translates to violated rank
freshness?

Concrete fix: add a small "operational contracts" table in Step 7 or the final
design: rank freshness SLO, queue lag threshold, listing snapshot TTL, cache
rebuild target, moderation propagation SLO, and fallback read behavior.

### 4. Abuse and moderation state still lacks audit/privacy detail

The fraud step now records account age, IP/ASN, vote timing correlation, and
cohort overlap, and it persists `trust_status` on votes
(`data/book/reddit-hn/interview.json:1464`,
`data/book/reddit-hn/interview.json:612`). Moderation now writes authoritative
status and tombstones (`data/book/reddit-hn/interview.json:1648`). That is a
good mechanism, but the data model does not yet include audit records, moderator
actor/reason fields, restore state, appeal/review handling, or retention/access
rules for sensitive abuse signals.

Why it matters: fraud and moderation are high-impact product operations. Without
an audit trail and retention story, the design can remove or downrank content
but cannot explain who did it, why, how it is reviewed, and how sensitive
signals are protected.

Concrete fix: add a lightweight `moderation_actions` or audit-log model and a
short note that abuse signals have retention limits, access controls, and
aggregated features where possible. The API already mentions a mirror restore
endpoint; the model should have enough state to support it.

## System Design Soundness

The system decomposition is now sound and internally consistent. `PostSvc`
handles post/comment writes and reads, `VoteSvc` records idempotent votes,
`EventQ` decouples writes from ranking, `Ranker` recomputes time-decay scores,
`RankCache` serves precomputed listings, `CommentCache` serves hot threads,
`Fraud` discounts manipulated votes, and `ModSvc` writes status plus invalidates
derived state.

The best design choices are the ones that keep source-of-truth and derived
state separate. Votes are authoritative in `VoteStore`; posts/comments/status
live in `PostDB`; listing and comment caches are explicitly rebuildable. The
final design summarizes that clearly (`data/book/reddit-hn/interview.json:1779`).

The design is less complete around physical partitioning and cost. The dataset
names sharding, batching, and replication, but it should be more explicit about
which keys define the partitions, which workloads are coalesced, and how much
memory or write amplification each sorted listing policy creates.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Vote Counter + Sort-on-Read

Strong. The baseline is intentionally simple and exposes the two reasons the
rest of the design exists: sort-on-read melts under read-heavy load, and raw
counter increments are not idempotent. Keep it.

Minor improvement: this step could include a tiny capacity callback, such as
"sorting all community posts cannot serve ~150k listing reads/sec," to connect
the new capacity section to the first failure.

### Step 2: Idempotent Voting

Strong after the update. The step now covers `(user, item_type, item)`,
versioned events, duplicate delivery, and direction flips. That is the right
place to teach event idempotency because retries can happen before and after
the queue.

Suggested improvement: add a failure drill for duplicate queue delivery or a
ranker crash after applying a delta but before committing its offset. That would
make the idempotency lesson testable.

### Step 3: The Hot-Ranking Score

Strong. The alternatives are meaningful and the new periodic drift pass fixes a
common hidden bug in hot-score systems: time decay changes without vote events.

Suggested improvement: include one sentence on formula experimentation and
guardrails. The follow-up asks about A/B testing, but the main step could name
offline replay or shadow scoring so candidates see ranking as tunable product
logic, not a fixed formula.

### Step 4: Precomputed Ranked Listings

Very strong central step. It now explains hot/top/new/global semantics and
stable pagination. The remaining production detail is physical cost: sorted-set
memory, write fanout, cold-community eviction, and stale snapshot TTLs.

Suggested improvement: add a failure drill for a cursor page where scores
change mid-scroll, or for rebuilding a hot community listing after cache loss.

### Step 5: Threaded Comments

Strong. Materialized path is a credible default, and the step now covers
comment votes, tombstones, incremental loading, sibling sort, and hot-thread
cache invalidation.

Suggested improvement: specify a maximum depth or path encoding strategy. The
model has `depth`, and the API has `depth=8`, but the step could say whether
very deep replies are capped, flattened, or loaded as continuation nodes.

### Step 6: Vote-Fraud and Abuse Prevention

Strong and realistic. Async discounting is the right default for keeping vote
latency low, and the step now handles verdict changes by re-emitting events and
recomputing affected listings.

Suggested improvement: add a short operational note for false positives and
sensitive signal handling. Fraud systems need auditability and privacy controls
because IP/ASN and account-history features are sensitive.

### Step 7: Scaling, Hot Posts, and Moderation

This is now a proper closing step. The moderation flow and failure drills make
the final operational story much more credible, and the old diagram issue is
gone because `eventq-ranker` is used in the visible view.

Suggested improvement: expand the hot-post drill from "queue lags" to "one post
is a hot key." That forces the candidate to discuss coalescing, partitioning,
write fanout, and hot listing reads.

## Final Design Review

The final design is coherent and integrates the walkthrough. It names the right
contracts: versioned vote events, idempotent scoring, fraud discounting,
periodic drift, sorted listings by scope/sort/window, `(score, id)` seek
cursors, materialized-path comments, status tombstones, moderation invalidation,
queue backpressure, and rebuildable derived caches
(`data/book/reddit-hn/interview.json:1779`).

The final design would become excellent with one additional operational table:
ranking freshness, queue lag, snapshot TTL, moderation propagation, cache
rebuild target, and observability metrics. The final paragraph already contains
the concepts; the missing piece is turning them into measurable contracts.

## Concept Introduction and Learning Flow

The concept staging is now very good:

- The naive baseline creates the need.
- Idempotent voting fixes correctness and retry safety.
- Time-decay ranking fixes stale popularity.
- Precomputed listings fix read latency.
- Materialized-path comments fix nested-thread reads.
- Fraud discounting protects rank integrity.
- Scaling/moderation closes the operational story.

The concepts are introduced just in time and reused later. The only remaining
learning-flow gap is that failure drills are concentrated in Step 7. Adding one
or two drills earlier would let the candidate practice the same concepts when
they are introduced rather than only at the end.

## Step-to-Final-Design Coherence

The mapping from steps to final design is strong:

- `naive` motivates abandoning sort-on-read and raw counters.
- `voting` introduces `VoteSvc`, `VoteStore`, versioned events, and `EventQ`.
- `ranking` introduces `Ranker`, hot score, and drift recompute.
- `listings` introduces `RankCache` and listing cursor semantics.
- `comments` introduces materialized-path comments and `CommentCache`.
- `fraud` introduces `Fraud`, `trust_status`, and re-ranking on verdict changes.
- `scale-mod` introduces `ModSvc`, authoritative status writes, cache
  invalidation, queue backpressure, and cache rebuilds.

The final design includes all of those components and its structured view links
resolve cleanly.

## Realism Compared With Production Systems

The dataset now compares well with real production feed/comment systems at the
mechanism level. It has the right split between authoritative writes and
derived reads, it treats ranking as eventually consistent, it addresses comment
tree reads separately from listing reads, and it makes moderation a state
workflow rather than a cache-only operation.

The remaining realism gaps are typical late-stage interview refinements:

- Cache memory and sorted-set overhead need a realistic estimate.
- Hot-key mitigation should be explicit for viral posts and front-page reads.
- Queue partitioning and coalesced rank updates should be spelled out.
- Listing snapshot tokens need a TTL and duplicate/gap contract.
- Moderation needs audit/restore records and propagation metrics.
- Fraud signals need retention, access control, and false-positive workflow.
- Observability should tie p99 reads, rank freshness, queue lag, cache hit rate,
  moderation delay, and fraud false positives to concrete SLOs.

## Dataset and Renderer-Facing Observations

Validation and cross-reference checks were clean:

- `interview.json` parses as JSON.
- Step view nodes resolve to canonical architecture nodes.
- Step, option, and final-design view links resolve to known architecture
  links, and their endpoints are present in the visible node sets.
- Step highlights are visible in their own views.
- `satisfies[*].steps[*]` references resolve.
- Flow participants resolve to canonical node IDs.

The previous visible Step 7 issue is fixed. Its view now includes the queue and
ranker with the `eventq-ranker` link, so the queue story is no longer visually
underconnected (`data/book/reddit-hn/interview.json:1661`).

One small content/rendering observation remains: top-level non-functional
requirements include the read-heavy load shape, but the `satisfies` wrap-up
maps only four non-functional requirements: fast listing reads, vote integrity,
eventually-consistent ranking, and viral-post scale
(`data/book/reddit-hn/interview.json:1820`,
`data/book/reddit-hn/interview.json:1861`). That is not a schema error, but a
candidate-facing "Design vs. Requirements" view would be more complete if it
also mapped read-heavy traffic to cache-served listings/comments and async
writes.

## Recommended Edits, Prioritized

### P1: Correct the listing-cache memory and fanout model

Show raw member bytes separately from realistic sorted-set overhead and
replicas. Add a policy for active versus cold communities and sort/window sets.

### P1: Add explicit hot-key mitigation

In Step 7, describe coalesced rank updates for one viral post, partitioning
choices for vote events, write-fanout caps for listing updates, and replicated
or local caching for hot listing pages.

### P2: Add an operational-contract table

Define rank freshness SLO, queue lag threshold, listing snapshot TTL,
moderation propagation SLO, cache rebuild target, and degraded-read behavior.

### P2: Add moderation audit and fraud-signal governance

Extend the model with a moderation audit/action record, restore state, and
retention/access notes for abuse signals.

### P2: Add earlier failure drills

Add focused drills for duplicate vote events, cursor stability under score
changes, comment-cache invalidation, and fraud verdict reversal.

### P3: Complete the `satisfies` mapping

Add a non-functional row for the read-heavy traffic mix, tied to `listings`,
`comments`, `voting`, and `scale-mod`.

### P3: Tighten comment depth/path wording

State the maximum depth or continuation strategy for pathological nested
threads.

## What Not To Change

- Keep the naive baseline. It is an effective teaching setup.
- Keep time-decay hot score as the default ranking answer.
- Keep precomputed sorted listings as the main read-path solution.
- Keep materialized path as the default comment-tree model.
- Keep async fraud discounting as the default integrity approach.
- Keep moderation as an authoritative state change plus cache invalidation.
- Keep caches framed as derived and rebuildable rather than source-of-truth.

## Bottom Line

This is now a strong Reddit/Hacker News system design walkthrough. The latest
dataset changes closed the major correctness and completeness gaps. The next
increment is production sharpness: realistic cache sizing, explicit hot-key
behavior, and measurable operational contracts.
