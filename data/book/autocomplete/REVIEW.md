# Review: Search Autocomplete - System Design

Reviewed file: `data/book/autocomplete/interview.json`
Review date: 2026-06-09

This review updates the previous audit after the recent autocomplete changes in
`99ba4d4 Apply REVIEW.md fixes to autocomplete interview`.

## Executive Summary

The updated dataset is a strong, book-quality autocomplete case. The recent
changes resolved the major stale findings from the prior review: the final read
path now has cache miss -> API -> router -> range map -> shard, the final
sequence includes fuzzy matching and safety, event normalization is clearly
server-owned, `locale` is mostly treated as the single market key, rebuilds are
described as shard/range-local, safety-aware cache semantics are explicit, and
the `Builder`, `Cache`, and shard visual labels now match their production
roles.

The remaining issues are narrower contract and teaching-polish items. They are
worth fixing because this interview is otherwise close to production-realistic:
one lingering `market` field description conflicts with the new keying model,
the bounded trending overlay is present in the data model and capacity notes but
not clearly declared as part of the target final design, and Step 7 still names
the default strategy as "leading characters" even though the real lesson is
adaptive prefix-range sharding.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.7/5 | Core architecture is sound; remaining gaps are mostly precise key/cache and overlay contracts. |
| Production realism | 4.6/5 | Strong on latency, skew, freshness, abuse, safety, privacy, rollback, and observability. |
| Pedagogical flow | 4.7/5 | Excellent staged progression; Step 7 wording should push adaptive ranges more clearly. |
| Dataset/rendering fit | 4.6/5 | References validate; only minor rendered-polish and optional asset gaps remain. |
| Overall | 4.65/5 | Ready as a flagship case after a small cleanup pass. |

## What Works Well

- The seven-step path is the right interview arc: naive prefix scan, trie,
  precomputed top-k, edge caching, stream freshness, fuzzy/personalized quality,
  and prefix-range sharding.
- The capacity section now names the real bottlenecks: 1M QPS, p99 latency,
  100M+ terms, 10^8-10^9 prefix nodes, cache-hit target, event ingest, memory
  footprint, and shard-local rebuild timing.
- The API is much better aligned with production boundaries. `GET /v1/suggest`
  separates cacheable global suggestions from origin-side personalization, and
  `POST /v1/events/query` now makes the collector responsible for canonical
  normalization.
- The data model includes the state a production service needs:
  `prefix_topk`, `index_versions`, `prefix_range_map`, `event_dedupe`,
  `moderation_decisions`, `trending_overlay`, `query_counts`, and
  short-retention `user_history`.
- Step 5 is especially strong. It teaches collector filtering, stream
  aggregation, decayed counts, shard-local rebuilds, atomic swaps, canary,
  rollback, real-time overlay, and freshness observability.
- Step 6 handles quality and risk without pretending they are free: fuzzy
  expansion is bounded, personalization is capped and consent-based, and safety
  screens merged suggestions.
- The final sequence now reflects the intended control flow: hot global
  post-safety cache hit, otherwise API-owned exact lookup, bounded fuzzy
  expansion, optional personalization, safety screening, and response.

## Resolved By Recent Changes

- The final view no longer shows `Cache -> Router` as a bypass around the API.
- `api-router`, `router-routing`, and adaptive shard links are now present in
  the final architecture view.
- The final read sequence includes `Spell`, `Personalizer`, and `Safety` rather
  than compressing those roles away.
- `normalized_query` is no longer client-provided in the event ingest request;
  it is returned as a server-derived value after collector normalization.
- The rebuild-duration capacity note now explains shard/range-local parallel
  builds and the full freshness SLO.
- `Builder` is now a `worker`, `Cache` is now a `cache`, and shard labels now
  say `Hot Prefix Range Shard` / `Long-Tail Range Shard`.
- Cache-hit safety semantics are explicit: only post-safety global responses are
  edge-cacheable, keyed by `safe_mode` and index/policy version.

## Highest-Impact Issues

### 1. The locale-as-market contract has one remaining contradiction

The dataset now mostly says `locale` is the single market key, which is a good
choice for an interview: `en-US` can carry both language and region. The
contract is still slightly inconsistent in a few places:

- `term_metadata.note` says `market` is descriptive and not a separate keying
  dimension.
- The `term_metadata.market` field type still says `e.g. US, GB - per-market
  ranking/index`, which sounds like an independent ranking/index key.
- The `terms.score` field can read as a global popularity score even though the
  actual ranking path is per-locale through `query_counts` and `prefix_topk`.
- Some prose says `locale/market`, while the API says `locale` is the full
  market key.

Concrete fix:

- Rename the descriptive field to `region` or make the `market` field type say
  "derived display/reporting attribute, not a key".
- Clarify that `terms.score` is either a default/global feature or remove it
  from the base `terms` table and keep ranking in `query_counts` /
  `prefix_topk`.
- Use one phrase everywhere: `locale` as the market key, with language/region as
  derived attributes.

### 2. The target role of `trending_overlay` is still ambiguous

The capacity section and Step 5 deep dive explain a bounded real-time overlay
for viral terms, and the data model includes `trending_overlay`. But the default
Step 5 option is periodic rebuild, `satisfies.functional` says trending queries
are handled by "Query stream -> rolling counts -> periodic rebuild", and the
final design view does not include the `builder-overlay-topk` / `Agg -> TopK`
overlay link.

This leaves a candidate unsure whether the overlay is part of the target design
or an optional alternative. Either answer is acceptable, but the dataset should
make the choice explicit.

Concrete fix:

- If the overlay is part of the final design, add it to `finalDesign.view.links`
  and mention it in the "Reflect trending queries" `satisfies` row.
- If the overlay is optional, say so in the `trending_overlay` table note and
  keep the final design focused on periodic shard-local rebuilds.
- In either case, make the freshness language distinguish "minutes via base
  rebuild" from "seconds via overlay" only when both are actually in scope.

### 3. Step 7 still teaches "leading characters" before adaptive ranges

The Step 7 deep dive and final design now teach adaptive prefix ranges well, but
the default option is still named "Shard by leading characters + replicas
(default)" and the pattern catalog says "Partition the index by leading
characters across nodes." That phrasing can pull readers back toward static
first-letter or alphabet-split sharding.

Concrete fix:

- Rename the option to "Adaptive prefix-range sharding + replicas".
- Change the pattern `what` to "Partition the index by adaptive ranges over the
  leading prefix key, splitting hot ranges finer."
- In the option view, reuse the more explicit `router-sharda-by-prefix-range`
  link so the selected visual carries the same label as the main Step 7 view.

### 4. Cache-key details are nearly complete, but `limit` needs a sentence

The GET request includes `limit=8`, while the cache-key prose lists
`prefix + locale + safe_mode + index version`. That can be correct if the cache
stores a fixed maximum top-k response and the API/CDN slices to the requested
limit, but it should be stated. Otherwise different limits need different cache
keys.

Concrete fix:

- Add a short API/cache note: either cache the max supported global list and
  slice per request, or include `limit` in the edge cache key.
- Keep `personalize=on` out of edge cache storage; current prose already says
  personalization reranks at origin.

## System Design Soundness

The architecture is sound for high-scale typeahead. A read-optimized prefix
structure with precomputed top-k, edge caching for skew, asynchronous popularity
collection, versioned rebuilds, optional real-time overlay, bounded fuzzy
matching, consent-based personalization, safety screening, and adaptive
prefix-range sharding is the right shape.

The requirements are comprehensive. They cover prefix suggestions, popularity
and recency ranking, freshness, fuzzy tolerance, personalization, locale-aware
normalization, safety, manipulation resistance, low p99 latency, large
vocabulary, graceful degradation, eventual consistency, and privacy.

The capacity math is useful and teachable. It explains why memory footprint and
node count dominate the design, not just QPS. The rebuild note now avoids the
old "one global artifact every few minutes" problem by calling builds
shard/range-local and parallelized.

The API contract is close to production-ready for the interview. The remaining
precision is cache-key shape around `limit` and consistent wording around
`locale` versus `market`.

The data model is strong. The remaining polish is to make `term_metadata.market`
and `terms.score` not look like competing sources of truth for per-locale
ranking.

## Step-by-Step Pedagogical Review

### Step 1: Naive Prefix Scan

Good baseline. It gives candidates a bad starting point that fails clearly:
`LIKE 'prefix%' ORDER BY popularity` per keystroke cannot meet tens-of-ms
latency at 1M QPS.

### Step 2: Trie Prefix Index

Strong teaching step. It introduces trie lookup, then adds production depth
through compressed tries, FSTs, DAWGs, and locale-aware analyzers. The
normalization/analyzer material is now tied to versioned rebuilds, which is the
right production hook.

### Step 3: Precomputed Top-K per Prefix

This is the central design move and it lands well. The default option teaches
offline top-k build and direct read; the rejected options make query-time
subtree ranking and per-prefix sorted sets concrete trade-offs.

### Step 4: Edge Caching

Strong. It uses prefix skew, TTLs, stale-while-revalidate, and personalization
conflict to motivate edge caching. The new trap about post-safety caching is
important and should stay.

### Step 5: Freshness from the Query Stream

This is one of the strongest steps in the dataset. It covers collector trust
boundaries, dedupe, abuse filtering, decayed counts, offline rebuilds, atomic
swaps, overlay, canaries, rollback, and freshness observability. Clarify
whether the overlay is in the target design or only an alternative.

### Step 6: Typo Tolerance & Personalization

Good placement after the core read/freshness path. Bounded fuzzy expansion and
optional personalization are framed as re-rank/merge stages, not replacements
for global suggestions. Safety and privacy are correctly treated as product
requirements, not polish.

### Step 7: Scaling by Prefix Sharding

The concepts are correct: avoid hash scatter-gather, route exact prefix lookup
to one owning shard, split hot ranges finer, replicate hot shards, and make
range-map rollout versioned and observable. Rename the option/pattern language
so "adaptive prefix range" is the primary lesson.

## Final Design Review

The final design now coherently integrates `CDN`, `Cache`, `API`, `Router`,
`Routing`, shards, `TopK`, `Spell`, `Personalizer`, `Profile`, `Safety`,
`Collector`, `Stream`, `Agg`, `Counts`, and `Builder`.

The read path is credible:

- Hot global responses can return from the edge because they are post-safety
  and keyed by policy/index inputs.
- Cache misses go to the API.
- The API resolves the exact prefix through the router/range map.
- Fuzzy expansion is bounded and routes only a few variants.
- Personalization is optional and origin-side.
- Safety screens before return.

The write/freshness path is also credible: executed searches go through a
collector, clean events go to a stream, aggregation updates decayed counts, and
the builder publishes versioned shard-local artifacts. The only final-design
question is whether the overlay is target architecture or an optional
alternative.

## Concept Introduction and Learning Flow

The concept order is excellent: prefix lookup, trie, top-k, skew/caching,
freshness, atomic swap, analyzer versioning, fuzzy expansion, personalization,
privacy, safety, sharding, range-map rollout, and observability all arrive at
the point where the prior step creates the need.

The main learning-flow improvement is naming. The prose has moved to adaptive
prefix ranges, but Step 7's default option and pattern still foreground
"leading characters." A candidate should leave saying "adaptive prefix-range
map with hot-range splitting", not "split A-M and N-Z."

## Step-to-Final-Design Coherence

Coherence is high:

- `naive-prefix` motivates replacing live DB scans.
- `trie` introduces the prefix lookup structure.
- `topk` moves ranking off the hot path.
- `caching` absorbs the skewed hot head.
- `freshness` adds collector, stream, decayed counts, rebuilds, overlay,
  canary, and rollback.
- `spelling` layers fuzzy match, personalization, privacy, and safety.
- `scale` adds prefix routing, adaptive ranges, shards, replicas, and
  operational guardrails.

The remaining coherence gaps are concentrated in optional-vs-final wording:
`trending_overlay` exists as data and teaching material, but the final target
view and satisfies text do not fully commit to it; adaptive range language is
strong in the deep dive but weaker in the option/pattern labels.

## Realism Compared With Production Systems

The dataset reads like a realistic production design. It covers the major
operational concerns for autocomplete: hot-prefix skew, cache hit rate, memory
footprint, event ingest, dedupe, trust filtering, privacy retention, moderation,
versioned rebuilds, shard-local rollout, automatic rollback, and per-layer
observability.

The Staff+ `levelVariants` are useful and now mention policy-aware caching,
range-map rollout, and ranking experiments. Keeping A/B testing as a follow-up
is fine, but a future expansion could add one sentence to Step 5 or Step 6 about
experiment buckets being kept out of the shared edge-cache key unless the
variant is intentionally cache-partitioned.

## Dataset and Renderer-Facing Observations

Validated:

- `interview.json` parses as JSON.
- Step `view.nodes` references resolve to `highLevelArchitecture.nodes`.
- Step `view.links` string references resolve to `highLevelArchitecture.links`.
- Option `view.nodes` and string link references resolve; inline option nodes
  such as `PrefixZSet` and `NGramIdx` are declared in their option views.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.
- `satisfies[*].steps[*]`, `patterns[*].steps[*]`, and
  `technologyChoices[*].steps[*]` resolve to real step IDs.
- Step `probeLinks` resolve to `toProbeFurther.links`.
- Structured sequence participants resolve to canonical high-level node IDs.
- Authored highlights resolve to known high-level nodes or declared option-local
  nodes.
- The dataset uses structured `view` and structured `sequence` data for steps
  and final design, not raw Mermaid architecture diagrams.

Renderer-facing cleanup:

- Many technology-choice chips still use `assets/tech-icons/tech.png`; curated
  icons would improve rendered polish but are not a correctness issue.
- There are no AI visual or explainer comic assets for this dataset. Those are
  optional.
- This review update is repo-only; no `docs/` rebuild is needed for
  `REVIEW.md` alone.

## Recommended Edits, Prioritized

### P1: Remove the last locale/market ambiguity

Make `locale` the only ranking/index/cache/routing key in wording and field
types. Recast `market` as a descriptive region/reporting attribute, or remove
it from `term_metadata`.

### P1: Decide whether `trending_overlay` is target architecture

If yes, add the overlay to final design and `satisfies`. If no, label it as an
optional acceleration layer rather than part of the core target.

### P2: Rename Step 7 around adaptive prefix ranges

Update the option name, pattern description, and selected option link label so
the default visual and text teach adaptive range-map sharding first.

### P2: Clarify cache handling for `limit`

State whether the edge cache stores a max top-k response and slices per request,
or whether `limit` is part of the cache key.

### P3: Polish rendered extras

Replace generic `tech.png` fallbacks where curated provider icons exist. AI
visuals and an explainer comic are optional enhancements, not blockers.

## What Not To Change

- Keep the seven-step progression.
- Keep the naive scan baseline.
- Keep precomputed top-k as the central read-path optimization.
- Keep edge caching as the QPS and latency lever for the skewed hot head.
- Keep collector-owned normalization and abuse-resistant event counting.
- Keep shard-local rebuilds with atomic swap, canary, and rollback.
- Keep the bounded overlay discussion, but make its target/optional status
  explicit.
- Keep fuzzy, personalization, safety, and privacy as first-class product
  requirements.
- Keep structured `view` and `sequence` data instead of raw Mermaid.

## Bottom Line

The recent changes moved this from "strong with several stale contradictions" to
"nearly ready as a flagship autocomplete interview." The next useful edits are
small and precise: finish the locale/market wording, decide the overlay's role
in the final target, rename Step 7 around adaptive prefix ranges, and clarify
how `limit` interacts with edge cache keys.
