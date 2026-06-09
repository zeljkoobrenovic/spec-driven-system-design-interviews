# Review: Web Search Engine - System Design

Reviewed file: `data/book/search-engine/interview.json`
Review date: 2026-06-09

## Executive Summary

This review has been updated against the current dataset. The recent changes
materially improve the case: the capacity section now includes shard, replica,
fan-out, deadline, and crawl-rate math; the crawler step covers canonicalization,
robots caching, host backoff, retries, traps, and recrawl policy; ranking now
includes spam/quality and freshness signals; caching covers skew, TTLs, and
stampede control; and freshness now explains immutable segments, tombstones,
atomic publish, reader refresh, rollback, and cache invalidation.

The dataset is now a strong book-quality walkthrough of a web search engine. It
teaches the right backbone - crawl, index, shard, scatter-gather, rank, cache,
and refresh - and it now exposes many of the production concerns that were
previously missing.

The remaining gap is not that major mechanisms are absent. It is that the
serving scale model is still a little too hand-wavy after it reveals a very
large number: roughly 300M shard requests per second on cache misses. The review
should now push the dataset to reconcile that fan-out with broker topology,
per-replica capacity, top-k sizes, partial results, observability, and cost.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5 | Correct architecture with much better capacity, crawl, ranking, caching, and freshness detail; serving fan-out economics still need tighter reconciliation. |
| Production realism | 4 | Strong production coverage now; remaining realism gaps are broker topology, observability, host crawl state, and operational runbooks. |
| Pedagogical flow | 4.5 | Natural progression and good trade-off choices; Step 4 is now dense enough that one more serving-scale sub-step may help. |
| Dataset/rendering fit | 4.5 | Structured views and references validate cleanly; only minor renderer-facing polish remains. |
| Overall | 4.5 | A strong search-engine case, close to flagship depth with a few scale and operations refinements. |

## What Works Well

- The case now has a credible quantitative spine: documents, index size, shard
  count, replicas, cache-miss QPS, fan-out, top-k work, deadline budget, and
  crawl throughput.
- The crawler step now feels domain-specific instead of generic queue-worker
  material. Canonicalization, robots caching, retries, host backoff, traps,
  duplicate clusters, sitemaps, and recrawl frequency are all present.
- The inverted-index step explains term dictionaries, compressed postings,
  positions, skip lists/block-max metadata, immutable segments, and merge
  policy at an appropriate interview depth.
- The serving steps correctly teach document partitioning first, then use the
  sub-step to compare document and term partitioning with useful nuance.
- Ranking now goes beyond BM25 and PageRank by naming freshness, spam/quality,
  suppressions, and explicit out-of-scope areas.
- Caching now ties directly to the capacity plan and includes TTLs, invalidation,
  single-flight, TTL jitter, and cache warming.
- Freshness now has proper update semantics: new document versions, tombstones,
  segment generations, publish markers, reader refresh, rollback, and merge
  compaction.
- The final design is concise but integrates the mechanisms introduced across
  the steps.

## Highest-Impact Issues

### 1. The 300M shard-requests/s plan needs a clearer serving topology

The capacity section now does the right thing by exposing the cost of
document-sharded scatter-gather: roughly `30K cache-miss QPS x 10K shards =
300M shard-requests/s`. That is useful, but it creates a new teaching problem:
the dataset does not yet show how the query-serving fleet actually absorbs that
load.

Why it matters: once the review says 300M shard requests per second and about
10MB gathered per cache-miss query, the candidate should be expected to reason
about broker fan-out trees, per-replica request rates, network egress,
connection management, queueing, and top-k limits. Otherwise the capacity math
names a huge number without proving the design can survive it.

Concrete fix:

- Add a short "broker topology" note: many stateless query frontends hand off to
  broker workers or a two-level fan-out tree, rather than one `QuerySvc` box
  opening 10K shard calls.
- Reconcile the per-replica load. The current math implies about 10K shard
  requests/s per shard replica at 3x replication; state whether that is
  acceptable, requires more replicas, or assumes each "shard" is a logical
  partition spread over multiple serving nodes.
- Tighten top-k numbers. `top-k ~100-1000 per shard` across 10K shards means
  one million to ten million candidates before merge; clarify the default
  target and when a larger top-k is used.
- Mention hierarchical merge or early pruning so the broker does not gather and
  sort an unnecessarily large candidate set for every miss.
- Add a cost caveat: a 60-70% result-cache hit rate helps, but a real 100K-QPS
  web search service probably needs tiering, hot-query precomputation, query
  classification, and aggressive overload controls.

### 2. Step 4 now carries too much of the hardest material

Step 4 has to teach document partitioning, scatter-gather, replication, broker
responsibility, deadline propagation, hedging, top-k limits, partial results,
tail latency, and fan-out amplification. That is all relevant, but it is a lot
for one step.

Why it matters: pedagogically, this is the core senior/staff part of the case.
If it is too compressed, readers may memorize the answer without understanding
which part solves which bottleneck.

Concrete fix:

- Keep Step 4 focused on partitioning and the basic scatter-gather path.
- Add a child step such as `4b. Make Scatter-Gather Survive 100K QPS` for
  broker topology, deadlines, hedging, top-k, partial results, cache-miss math,
  and overload behavior.
- Move the existing slow-replica and cache-stampede failure drills into that
  child step so each drill lands near the mechanism it tests.
- In the decision-tree overview, this would make the flow clearer: choose
  document partitioning, then harden the serving path.

### 3. Observability and operations are still underdeveloped

The dataset now includes several failure drills, but it does not yet define what
the system measures or alerts on.

Why it matters: search engines are operated through freshness, quality, and tail
latency metrics. Without observability, the design cannot explain how operators
detect crawl stalls, bad segment publishes, ranking regressions, cache
stampedes, or shard tail latency.

Concrete fix:

- Add an observability paragraph or a small data-model/control-plane entity for
  metrics.
- Include crawl metrics: frontier backlog by host/priority, fetch success rate,
  robots/blocked rate, 429/5xx rate, duplicate rate, crawl lag, and recrawl
  freshness.
- Include indexing metrics: segment build lag, validation failures, publish
  generation, merge backlog, tombstone ratio, and rollback count.
- Include serving metrics: result-cache hit rate, doc-cache hit rate,
  cache-miss QPS, shard p95/p99, hedge rate, partial-result rate, timeout rate,
  candidate count, and merge/rank latency.
- Include quality metrics: spam demotion rate, suppression count, ranker model
  version, click/feedback quality indicators if in scope.

### 4. Crawl state deserves one more explicit model boundary

The `url_frontier` model now includes canonical URL, host, status, attempts,
robots policy, change frequency, and `next_fetch_at`. That is much better than
before. The remaining ambiguity is that host-level politeness and robots state
are modeled only as fields on URL-level entries.

Why it matters: the crawler's hardest invariant is per-host behavior. A
production crawler usually needs host/domain buckets with their own next-fetch
time, rate limits, robots cache, backoff state, and error budget. If this is
buried in each URL row, readers may miss that the frontier is really scheduling
hosts as well as URLs.

Concrete fix:

- Add a `host_crawl_state` or `robots_cache` data-model entity with host,
  crawl-delay/rate limit, robots version/TTL, next host fetch time, recent
  errors, and backoff state.
- In the crawl flow, show that the frontier selects an eligible host bucket and
  then a URL within that bucket.
- Keep the current `url_frontier` fields, but make `robots_policy` a reference
  to the host-level cache rather than the only place that policy lives.

### 5. API and response semantics need a few search-specific caveats

The `/search` API now supports quoted phrases, boolean operators, locale, cursor
pagination, freshness bias, titles, URLs, snippets, and `nextCursor`. That is a
good improvement. A few production search details should still be made explicit.

Why it matters: the external API sets user-visible expectations. Exact counts,
deep pagination, partial results, and freshness controls can conflict with the
serving plan if they are not scoped carefully.

Concrete fix:

- Change `total` to `approxTotal` or note that exact totals are approximate or
  capped at web scale.
- Add response fields such as `partialResults`, `timedOutShards`, or
  `servedFromCache` if the design intentionally returns partial results under
  deadline pressure.
- State cursor limits and expiry, since deep pagination over a changing index is
  expensive and unstable.
- Clarify the freshness parameter as a ranking bias or filter, because the
  system does not guarantee all new pages are visible instantly.

## System Design Soundness

The core design is sound. A politeness-aware frontier feeds a crawler fleet; raw
pages and parsed content land in the document store; the indexer builds
document-partitioned inverted-index segments and link-graph/page-quality
signals; the query path checks a result cache, scatters cache misses to one
replica per primary partition, merges per-shard candidates, re-ranks, hydrates
snippets from a doc cache, and returns partial results if shards miss deadlines.

The data model now supports more of the promised behavior. `documents` includes
canonical URL, content hash, page score, quality score, current version,
suppression, and last crawl time. `doc_versions` and `index_segments` cover
content lifecycle and segment publish state. `url_frontier` covers crawl
priority, attempts, robots policy, change frequency, and next fetch time.

The biggest remaining soundness question is serving economics. The dataset
correctly admits that document partitioning trades term-local lookups for large
fan-out. Now it should go one level deeper: how many broker workers, how many
connections, how much network, what per-shard top-k, and what overload mode keep
300M shard requests/s from dominating the design.

The API is much better aligned with the requirements than before. The remaining
API polish is mostly about honesty: approximate totals, partial-result flags,
cursor limits, and freshness semantics.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Scan Every Document for the Query Terms

This remains a useful baseline. The view now includes both `QuerySvc` and
`DocStore` with an inline "scan every document" edge, so the diagram matches the
text. The trap is clear and motivates the inverted index.

Keep it short. It does its job as the intentionally bad starting point.

### Step 2: Crawl the Web with a URL Frontier

This step is now substantially stronger. It covers the important web-crawling
concerns: canonicalization, robots caching, DNS/fetch timeouts, retry/backoff,
429/5xx host backoff, duplicate clusters, crawler traps, per-host caps,
sitemaps, and recrawl policy.

The failure drills are good and domain-specific. The remaining improvement is
to make host-level state explicit in the data model or flow so politeness is
visibly enforced per host, not just implied by URL rows.

### Step 3: Build the Inverted Index

The step now teaches enough of the real index internals: term dictionary,
postings with positions/frequency, compact docIDs, normalization, gap
compression, skip lists/block-max metadata, immutable segments, and merges.

This is a good balance for an interview dataset. Avoid adding too much Lucene
implementation detail unless it supports a later trade-off.

### Step 4: Shard the Index and Scatter-Gather Queries

This is still the most important step and now contains the right concepts:
document partitioning, one chosen replica per primary partition, query parsing,
broker fan-out, per-shard top-k, deadlines, hedging, and partial results.

The issue is density. Consider splitting operational scatter-gather hardening
into a child step. That would preserve the clean partitioning lesson while
giving the 100K-QPS plan room to breathe.

### Step 4a: Document vs Term Partitioning

This sub-step is worth keeping. It now avoids the earlier overclaim by saying
document partitioning is the right starting point while leaving room for tiered,
hybrid, and hot/common-term treatment.

The one small caution: the example line saying "Google/Elasticsearch use
document partitioning + scatter-gather" is useful, but phrase it as a broad
pattern rather than a proof that all web-search retrieval tiers work this way.

### Step 5: Rank Results

This step is much better now. Two-phase ranking is the right default, and the
dataset now names authority, freshness, spam/quality, suppressions, and scoped
exclusions.

One remaining nuance: the "PageRank only" option says link authority is strong
against spam/low-quality pages. Link authority helps, but link farms and SEO
abuse are exactly why explicit spam/quality signals are needed. Consider softening
that pro or adding a con that PageRank-only ranking is vulnerable to link
manipulation.

### Step 6: Caching for QPS and Latency

The step now connects directly to capacity: 60-70% result-cache hit rate reduces
100K QPS to 30-40K scatter QPS. It also includes doc-cache hydration, staleness
TTLs, segment-publish invalidation, single-flight, TTL jitter, and warming.

The next improvement is operational: add metrics and alerts for result-cache hit
rate, stampede prevention, stale-hit rate, and invalidation lag.

### Step 7: Freshness and Continuous Indexing

This step now addresses the major lifecycle gaps. It explains immutable
segments, new versions, tombstones for updates/deletes/suppressions, publish
markers, reader refresh, rollback, cache invalidation, and merge compaction.

That is the right model. Add a metric or control-plane note for segment build
lag, publish generation, validation failure, merge backlog, and rollback rate.

## Final Design Review

The final design now integrates the important mechanisms introduced in the
steps:

- Crawler fleet, URL frontier, seen/dedup store, and document store.
- Indexing pipeline, immutable index segments, index shards, and link graph.
- Query service/broker, result cache, index shard replicas, ranker, and doc
  cache.
- Ranking signals: text relevance, page authority, freshness, quality, and
  suppressions.
- Operational behaviors: deadline propagation, hedging, partial results,
  single-flight caching, TTL jitter, generation-based publish, and rollback.

The final design description is dense but effective. The diagram stays concise,
which is good, but it may now under-represent important logical components named
in the text: query broker/fan-out tree, segment metadata/publish control, and
host crawl state. These do not necessarily need to be top-level diagram nodes,
but the dataset should decide whether they are first-class components or
implementation details.

## Concept Introduction and Learning Flow

The concept flow is strong:

1. Linear scan creates the pain.
2. The crawler creates the corpus.
3. The inverted index makes lookup fast.
4. Sharding and scatter-gather make the index serve at scale.
5. The partitioning sub-step teaches the key sharding trade-off.
6. Ranking makes results useful.
7. Caching makes the target load economically plausible.
8. Incremental segment indexing keeps the system fresh.

The best improvement would be one additional serving-scale child step between
partitioning and ranking. It would let the candidate reason about the cost of
scatter-gather before moving on to ranking.

## Step-to-Final-Design Coherence

The coherence is now strong:

- `crawl` introduces `Frontier`, `Crawler`, `SeenStore`, `DocStore`, crawl
  failures, and crawler-specific probe links.
- `index` introduces `Indexer`, `IndexShards`, `LinkGraph`, and index internals.
- `serve` introduces `QuerySvc`, `ResultCache`, `IndexShards`, broker behavior,
  hedging, deadlines, and partial results.
- `partitioning-scheme` explains why the final design chooses document
  partitioning.
- `rank` introduces `Ranker`, `LinkGraph` usage, quality signals, and ranking
  exclusions.
- `cache` introduces `ResultCache`, `DocCache`, cache hit-rate assumptions, TTLs,
  invalidation, warming, and stampede protection.
- `freshness` closes the loop with segment publish, tombstones, reader refresh,
  rollback, and score recomputation lag.

The older coherence problems have been fixed: the naive scan view includes the
scan edge, `freshness.view.nodes` includes `DocStore`, the cache pattern points
to `cache`, `User` is typed as an `actor`, and the multi-term requirement is
mapped in `satisfies.functional`.

## Realism Compared With Production Systems

The dataset is now realistic at the architecture-pattern level and reasonably
realistic at the operational level. It names the web-search-specific problems
that matter: politeness, duplicate pages, crawler traps, index compression,
segment merges, ranking quality, spam suppression, cache skew, and freshness.

To reach the next level, add:

- Broker/fan-out topology and per-replica capacity reasoning.
- Host/domain crawl-state modeling.
- Observability and alerting across crawl, index, serving, cache, and ranking.
- A clearer overload policy for cache-miss bursts beyond "partial results".
- Explicit approximate-total and partial-result semantics in the public API.
- One or two runbook-style drills: bad ranker model rollout, publish generation
  stuck, frontier backlog explosion, or a cache hit-rate collapse.

## Dataset and Renderer-Facing Observations

- JSON validation passed.
- Step `view.nodes` all resolve to high-level architecture nodes or inline view
  nodes.
- Step and option `view.links` references resolve to high-level link IDs when
  they are string references.
- `view.highlight` IDs resolve within their step views.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Dataset-level `patterns[*].steps[*]` references resolve to real step IDs.
- Step `probeLinks` references resolve to `toProbeFurther.links`.
- `step.parent` references resolve.
- `User` is now correctly typed as `actor`.
- `freshness.view.nodes` now includes `DocStore`, so the `doc-indexer` link is
  valid in that view.
- Dataset-level `Result + doc caching` now points to `cache`.
- `satisfies.functional` now explicitly maps "Multi-term queries and basic
  operators."
- Minor polish: the inline `TermShards` option node could declare `type:
  "index"` for visual consistency with `IndexShards`.

## Recommended Edits, Prioritized

### P1: Reconcile the serving scale model

Add broker topology, per-replica load assumptions, connection/network budget,
top-k defaults, hierarchical merge/early pruning, and explicit overload
behavior for the 300M shard-requests/s cache-miss plan.

### P1: Split scatter-gather hardening into a child step

Move the 100K-QPS operational details into a `4b` sub-step so Step 4 remains the
partitioning lesson and the new sub-step becomes the tail-latency/fan-out lesson.

### P2: Add observability and runbook coverage

Add metrics and alerts for crawl lag, frontier backlog, robots/fetch errors,
segment publish lag, merge backlog, rollback count, cache hit rate, hedge rate,
partial-result rate, shard p99, ranker version, and quality regressions.

### P2: Add host-level crawl state

Represent host politeness and robots state as a first-class data model entity or
control-plane concept, and show how the frontier schedules eligible host buckets.

### P2: Tighten API semantics

Use approximate totals, expose partial-result/timed-out-shard information, state
cursor limits/expiry, and clarify freshness as a ranking bias or filter.

### P3: Polish ranking and renderer details

Soften the PageRank-only spam-resistance claim, add `type: "index"` to the
inline `TermShards` option node, and consider one more failure drill for a bad
ranker or quality-score rollout.

## What Not To Change

- Keep the main sequence: naive scan -> crawl -> index -> shard/serve ->
  partitioning trade-off -> rank -> cache -> freshness.
- Keep document partitioning as the default and term partitioning as the
  contrast option.
- Keep two-phase ranking as the default ranking path.
- Keep the final design concise; add detail in steps and notes rather than
  overloading the final diagram with every internal control-plane object.
- Keep the explicit scoped exclusions. They prevent the case from ballooning
  into ads, personalization, semantic search, query suggestions, and takedown
  workflow.

## Bottom Line

The search-engine dataset is now strong. The recent updates fixed the biggest
previous gaps in capacity, crawler realism, freshness semantics, ranking quality,
and dataset references. The main remaining work is to make the 100K-QPS
scatter-gather plan operationally explicit and observable, so the case teaches
not just the right architecture but the mechanics that keep it alive at scale.
