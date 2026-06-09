# Review: Web Search Engine - System Design

Reviewed file: `data/book/search-engine/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong teaching walkthrough for the core shape of web search: crawl,
index, scatter-gather, rank, cache, and refresh. The step ordering is natural,
the option trade-offs are useful, and the final design integrates most of the
components introduced along the way.

The main gap is that the dataset currently explains the architecture pattern
better than it explains production scale. The capacity section names large
numbers but does not turn them into shard counts, replica counts, crawl
bandwidth, index write rates, or per-query fan-out budgets. A candidate could
recite the design and still avoid the hard reasoning behind whether 100K QPS
and sub-second p99 are achievable.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4 | Correct core architecture, but capacity math, update semantics, and ops need more detail. |
| Production realism | 3 | Good crawler/index/serving split; missing several real crawler, index deploy, spam, and failure workflows. |
| Pedagogical flow | 4 | Clear progression from naive scan to final design; a few steps need sharper motivation and concrete numbers. |
| Dataset/rendering fit | 4 | Mostly valid structured views; a few exact view/type/pattern issues should be fixed. |
| Overall | 4 | Strong base, but not yet flagship-depth for a book-scale search-engine case. |

## What Works Well

- The walkthrough starts from an intentionally bad linear scan and uses it to
  motivate the inverted index, sharding, scatter-gather, ranking, caching, and
  freshness.
- The `serve` and `partitioning-scheme` steps teach a real senior-level fork:
  document partitioning versus term partitioning.
- The `rank` step correctly introduces two-phase ranking and separates cheap
  recall from more expensive re-ranking.
- The final design is concise and includes the major components introduced in
  the steps.
- The dataset uses structured `view` and `sequence` fields consistently instead
  of raw Mermaid for architecture steps.

## Highest-Impact Issues

### 1. Capacity is named but not reasoned through

The capacity section lists `100B+` documents, `~100,000` QPS, PB-scale index
size, and billions of crawls per day, but it does not derive any operational
numbers from them.

Why it matters: search-system interviews turn on fan-out and work budgeting. If
every cache miss scatters to every shard, then QPS multiplied by shard fan-out
can explode into millions or billions of shard requests per second. The dataset
mentions shard replication and caching, but it does not force the candidate to
show what cache hit rate, shard count, replica count, top-k size, and timeout
budget make the target plausible.

Concrete fix:

- Add rough document/index sizing: average fetched page bytes, parsed content
  bytes, postings bytes per term occurrence, metadata bytes, and total index
  multiplier.
- Add shard sizing: target GB/TB per shard, number of primary shards, number of
  replicas, and why that keeps per-shard working sets manageable.
- Add serving math: cache hit-rate assumption, cache-miss QPS, fan-out per
  query, per-shard QPS, per-shard top-k, merge cost, timeout budget, and
  expected partial-result behavior.
- Add crawl math: pages/day to fetches/sec, average page size to bandwidth, and
  how per-host politeness changes throughput.

### 2. The crawler pipeline is too simple for production web crawling

The `crawl` step covers frontier, robots/politeness, dedupe, and discovered
links, which is the right center of gravity. But production crawling also needs
URL canonicalization, robots caching, DNS/fetch isolation, fetch retries,
redirect handling, sitemap/seeding, host-level backoff, duplicate clusters,
content extraction failures, malware/adult/spam filtering, and a recrawl policy
based on observed change frequency.

Why it matters: without these details, the crawl stage looks like a generic
queue-worker problem. For web search, crawl quality determines index quality,
freshness, cost, and whether the crawler gets blocked.

Concrete fix:

- Extend `url_frontier` with canonical URL, crawl status, fetch attempts,
  robots policy/cache key, next retry time, and change-frequency/freshness
  priority.
- Add a short crawl failure drill: host starts returning 429/5xx, robots changes,
  duplicate-content storm, or crawler trap.
- Add a parser/extractor or fetch-result queue between `Crawler`, `DocStore`,
  and `Indexer` so retries, backpressure, and poison documents are explicit.
- Use the existing Nutch and Heritrix probe links on the crawl step; they are
  better crawl references than the current generic storage/index links.

### 3. Serving topology needs a more believable 100K-QPS plan

The `serve` step says every query is scattered to all document-partitioned
shards and that shards are replicated for QPS and availability. That is a good
first explanation, but not enough for the stated load.

Why it matters: at large shard counts, the query broker, replica selection,
timeouts, hedging, and partial-result policy are first-class design elements.
The dataset currently treats `QuerySvc` as one box and `IndexShards` as one box,
so the hardest production problem is compressed into one arrow.

Concrete fix:

- Split the serving path conceptually into query parsing/rewrite, broker/fanout,
  shard replicas, merge, rank, and hydration.
- Add a short note on replica selection, request hedging, deadline propagation,
  per-shard top-k limits, and graceful degradation when a shard times out.
- Clarify whether "all shards" means all primary partitions, a tiered subset, or
  all replicas. The current text can be read as broadcasting to every replica.
- Add a bottleneck or failure drill for slow shard, hot shard, bad replica, or
  result-cache stampede.

### 4. Freshness and update semantics need more than segment append

The `freshness` step correctly introduces immutable segments and background
merge, but changed/deleted pages and deploy consistency are under-specified.

Why it matters: web search must remove pages, update changed content, handle
redirects/canonical IDs, hide spam/takedowns, and keep serving indexes
consistent during segment rollout. Appending fresh segments alone does not
explain deletion tombstones, version visibility, rollback, or cache invalidation.

Concrete fix:

- Add data-model entities for `index_segments`, `doc_versions`, and deletion or
  suppression tombstones.
- Explain the serving visibility contract: segment generation, publish marker,
  atomic reader refresh, rollback, and merge compaction.
- Tie result-cache invalidation to term/doc updates more concretely than
  "materially".
- Add a failure drill for a bad segment rollout or stale cache after a high-news
  crawl.

### 5. Ranking quality and abuse are mostly pushed to follow-ups

The `rank` step is good for BM25 plus PageRank, but spam/quality, safe search,
freshness scoring, language/locale, and personalization are only lightly
mentioned or left as follow-ups.

Why it matters: a web search engine that returns "ranked relevant documents"
must defend ranking quality from spam and low-quality pages. Even if
personalization is out of scope, spam/quality should not be purely optional.

Concrete fix:

- Add a quality/spam signal to the ranking description and data model.
- Add a component or derived dataset for spam/quality scores if the final design
  wants to claim production realism.
- State which ranking features are intentionally out of scope: ads,
  personalization, semantic/vector retrieval, query understanding, and safe
  search.

## System Design Soundness

The core architecture is sound. A crawler frontier feeds fetched documents into
a durable document store, an indexer builds an inverted index and link graph,
query serving scatters to document-partitioned shards, and a ranking stage
reorders candidates. That is the right backbone for an interview.

The weakest part is quantitative design. The dataset should turn `100B+`
documents and `100K QPS` into the concrete work units the candidate must manage:
documents per shard, postings size, query fan-out, per-shard QPS, network bytes
per query, top-k merge cost, and cache hit-rate assumptions.

The API is intentionally minimal, but it does not yet support the stated
"multi-term queries and basic operators" requirement beyond a plain `q`
parameter. Add examples or fields for phrases, boolean operators, pagination
cursor/offset limits, language/locale, freshness controls, and safe-search or
adult-content mode if those are in scope.

The data model covers the most important artifacts: postings, documents, and the
frontier. It should add segment metadata, document-version lifecycle, canonical
URL mapping, tombstones/suppression records, and ranking/quality signals.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Scan Every Document for the Query Terms

This is a useful baseline. It clearly explains why linear scanning fails over
100B documents and motivates the inverted index.

Improve the diagram: the view includes `User`, `QuerySvc`, and `DocStore`, but
only renders `user-query`. Add an inline edge or high-level link from
`QuerySvc` to `DocStore` so the diagram matches the caption's "scans every
document" behavior.

### Step 2: Crawl the Web with a URL Frontier

This step introduces the right central concept: a prioritized,
politeness-aware URL frontier. The flow is also helpful.

Deepen it with production crawler concerns: canonicalization, per-host queues,
robots caching, retry/backoff, redirects, content extraction, duplicate
clusters, crawl traps, and recrawl scheduling. Add crawler-specific probe links
to Nutch and Heritrix here.

### Step 3: Build the Inverted Index

The inverted-index explanation is clear and correctly ties postings, positions,
term frequency, and link extraction together.

The next improvement is to make index construction more concrete: term
dictionary, immutable segment files, compression, skip lists/block-max metadata,
docID assignment, and merge policy. Not all of those need full treatment, but a
book case should expose enough that the candidate can answer a follow-up about
why posting-list lookup is fast.

### Step 4: Shard the Index and Scatter-Gather Queries

This is one of the strongest steps. The document versus term partitioning option
comparison is realistic and useful.

The serving path needs more operational detail. Add query brokers, replica
choice, fan-out limits, hedged requests, shard timeouts, and partial-result
behavior. The current statement that every query fans out to all shards is fine
as a conceptual model, but the production plan needs the numbers and guardrails
that keep it from collapsing under 100K QPS.

### Step 4a: Document vs Term Partitioning

This sub-step is worth keeping. It reinforces a real design fork and helps
interviewers probe the trade-off more deeply.

Avoid overclaiming that web search "overwhelmingly uses" document partitioning
without caveat. It is the right default for this walkthrough, but hybrid
partitioning, tiered indexes, and special treatment for hot/common terms are
common enough that the text should leave room for nuance.

### Step 5: Rank Results

Two-phase ranking is the right teaching choice. The options are strong:
full scoring is correctly rejected as too expensive, and PageRank-only ranking
is correctly rejected as query-insensitive.

Add spam/quality and freshness signals to the default path, and say where those
features are computed. The `LinkGraph` alone is not enough to explain modern
result quality or abuse resistance.

### Step 6: Caching for QPS and Latency

The result-cache/doc-cache split is good, and the staleness trade-off is
introduced at the right time.

This step should quantify the cache assumption. For example, define a hot-query
hit-rate target, cache TTL policy, invalidation triggers, and stampede
protection. Also fix the pattern metadata: the dataset-level `Result + doc
caching` pattern declares `steps: ["serve"]`, but the actual step using that
pattern is `cache`.

### Step 7: Freshness and Continuous Indexing

The immutable-segment model is the right answer for incremental freshness.

Strengthen this step with deletion/update semantics, segment versioning, atomic
publish, reader refresh, rollback, and bad-segment failure handling. Also fix
the step view: it includes the `doc-indexer` link, whose source is `DocStore`,
but `DocStore` is not listed in this view's nodes. Add `DocStore` to
`freshness.view.nodes` or remove the `doc-indexer` link from that view.

## Final Design Review

The final design integrates the major components introduced in the steps:
frontier, crawler, seen store, document store, indexer, index shards, link
graph, query service, ranker, result cache, and document cache.

What is missing is mostly operational rather than conceptual:

- No explicit fetch-result or indexing queue/log for backpressure and retry.
- No index segment/version metadata in the final design.
- No clear query-broker/replica-selection responsibility inside `QuerySvc`.
- No bad-index rollout, shard loss, or cache-stampede operational path.
- No quality/spam/takedown path.

The final design description should also state the major scoped exclusions so
readers do not mistake omissions for oversights: ads, personalized ranking,
semantic/vector retrieval, query suggestions, image/video search, and legal
takedown workflow.

## Concept Introduction and Learning Flow

The concept flow is mostly excellent:

1. Linear scan creates the pain.
2. The crawler creates the corpus.
3. The inverted index makes lookup fast.
4. Sharding and scatter-gather make the index serve at scale.
5. Ranking makes results useful.
6. Caching makes the target affordable.
7. Incremental indexing keeps the system fresh.

The main pedagogical improvement is to introduce more numbers exactly where a
candidate would be expected to reason. The `serve`, `cache`, and `freshness`
steps are the best places to add quick calculations and deadline budgets.

## Step-to-Final-Design Coherence

Most steps map cleanly to final-design components:

- `crawl` introduces `Frontier`, `Crawler`, `SeenStore`, and `DocStore`.
- `index` introduces `Indexer`, `IndexShards`, and `LinkGraph`.
- `serve` introduces `QuerySvc`, `IndexShards`, and `ResultCache`.
- `rank` introduces `Ranker` and `LinkGraph` usage at query time.
- `cache` introduces `ResultCache` and `DocCache`.
- `freshness` closes the loop on continuous crawl and segment-based indexing.

The weaker links are:

- The baseline `naive` step uses `DocStore` before the crawl step has introduced
  how pages arrive there. This is acceptable as a baseline, but the text should
  explicitly say "assuming pages have been fetched somehow" or move the crawl
  before the naive serving baseline.
- The `freshness` step depends on `DocStore -> Indexer`, but the view omits
  `DocStore`.
- The cache pattern metadata points to the wrong step.

## Realism Compared With Production Systems

The dataset captures the standard high-level production shape. To feel more
like a production design, add coverage for:

- URL canonicalization, robots caching, host backoff, and crawl traps.
- Fetch, parse, and index queues with retries, dead-lettering, and backpressure.
- Index segment lifecycle: build, validate, publish, refresh, merge, rollback.
- Deletions, redirects, duplicate clusters, takedowns, and spam suppression.
- Query broker deadlines, hedging, replica selection, partial results, and
  overload behavior.
- Cache stampede protection, cache warming, and freshness-aware invalidation.
- Observability: crawl lag, index freshness, shard p99, timeout rate, cache hit
  rate, bad segment rollbacks, and ranking-quality metrics.

## Dataset and Renderer-Facing Observations

- JSON validation passed.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- `probeLinks` references resolve to `toProbeFurther.links`.
- `view.highlight` IDs resolve within their step views.
- Step and option `view.links` references resolve to high-level link IDs.
- `freshness.view.links` includes `doc-indexer`, but `freshness.view.nodes`
  omits `DocStore`, the source endpoint of that link. This can produce a
  misleading generated diagram.
- `highLevelArchitecture.nodes[]` defines `User` as type `client`; repo
  conventions reserve `actor` for human or organization roles and `client` for
  software outside the backend boundary. `User`/`Searcher` should be `actor`.
- Dataset-level pattern `Result + doc caching` declares `steps: ["serve"]`, but
  the actual step using the pattern is `cache`.
- `satisfies.functional` does not explicitly map the requirement "Support
  multi-term queries and basic operators." It is partially covered by inverted
  index/scatter-gather, but basic operators need an explicit mapping or
  requirement adjustment.

## Recommended Edits, Prioritized

### P1: Add capacity math and serving budgets

Add document/index sizing, shard counts, replica counts, cache hit-rate
assumptions, fan-out math, per-shard QPS, per-query top-k, merge cost, and
deadline/timeout behavior.

### P1: Strengthen crawl and freshness lifecycle

Add canonicalization, robots cache, retry/backoff, crawl traps, recrawl policy,
segment publish/versioning, deletion/tombstone handling, and bad-segment
rollback.

### P1: Make 100K-QPS scatter-gather operationally credible

Split the query path into parsing/rewrite, broker/fanout, shard replicas,
merge/rank, and hydration. Add hedging, partial results, and cache stampede
behavior.

### P2: Add quality/spam and ranking-signal coverage

Add spam/quality/freshness signals to ranking, plus where they are computed and
stored. Explicitly scope out ads, personalization, and semantic retrieval if
they are not part of this case.

### P2: Expand API and data model for promised features

Represent basic operators, pagination limits/cursors, language/locale, snippet
requirements, segment metadata, doc versions, canonical URLs, and suppression
tombstones.

### P3: Fix dataset metadata and diagrams

Fix `freshness.view.nodes`, the `User` node type, the cache pattern step, and
the naive scan diagram edge. Add crawl-specific probe links to the crawl step.

## What Not To Change

- Keep the main sequence: naive scan -> crawl -> index -> shard/serve -> rank
  -> cache -> freshness. It teaches the system in a good order.
- Keep the document-versus-term partitioning sub-step. It is one of the most
  valuable parts of the dataset.
- Keep two-phase ranking as the default ranking option.
- Keep the final design concise, but add supporting mechanics in the relevant
  steps so the final diagram does not become overloaded.

## Bottom Line

This is already a good search-engine interview walkthrough. To make it
flagship-quality, add the quantitative reasoning and operational lifecycle that
turn the correct high-level architecture into a credible production design.
