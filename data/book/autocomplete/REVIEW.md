# Review: Search Autocomplete - System Design

Reviewed file: `data/book/autocomplete/interview.json`
Review date: 2026-06-04

## Executive Summary

The recent changes moved this autocomplete interview from a solid walkthrough to
a near-flagship case. Earlier high-impact gaps are now addressed in the current
JSON: the API is richer, capacity math names prefix-node memory pressure,
locale/analyzer support is introduced, safety and abuse handling are explicit,
the event collector and dedupe path exist, the data model now includes
control-plane state, and the final design includes versioned rebuilds, adaptive
prefix routing, and operational guardrails.

The remaining issues are mostly coherence and precision, not missing core
architecture. The final diagram still carries one stale `Cache -> Router` edge
that contradicts the newer API-owned read path, the shard labels still imply a
static `A-M / N-Z` split even though the text now teaches adaptive ranges, and
the locale/market/cache-key model should be made fully consistent across API,
data model, cache, and range map.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.7/5 | Strong read path, freshness path, capacity framing, safety, and sharding. |
| Production realism | 4.5/5 | Operational metrics, rollback, dedupe, and moderation are now credible; a few semantics need tightening. |
| Pedagogical flow | 4.7/5 | Excellent staged progression from naive scan to production sharded service. |
| Dataset/rendering fit | 4.6/5 | JSON and structured references validate; minor visual/link polish remains. |
| Overall | 4.6/5 | Production-grade interview with a small set of cleanup edits left. |

## What Works Well

- The seven-step sequence remains the main strength: naive scan, trie, top-k,
  edge cache, freshness, quality layers, and sharding each solve the pressure
  exposed by the previous step.
- Capacity now teaches the real scaling driver. Prefix-node count, top-k bytes
  per node, cache hit rate, event ingest, and rebuild duration are all called
  out instead of only quoting QPS.
- The API now supports the later architecture: `locale`, `market`,
  `safe_mode`, `personalize`, `anon_id`, `indexVersion`, rich suggestion
  objects, and an idempotent query-event endpoint.
- The data model now covers the important production state: term metadata,
  `prefix_topk`, index versions, prefix range map, event dedupe,
  moderation decisions, trending overlay, decayed counts, and short-retention
  user history.
- Step 2's locale-aware analyzer deep dive is a major improvement. It explains
  normalized text versus display text, CJK/Thai segmentation, transliteration,
  per-market ranking, and analyzer versioning.
- Step 5 now has a realistic freshness story: collector, stream, decayed counts,
  versioned rebuilds, canary, rollback, bounded overlay, and freshness metrics.
- Step 7 now teaches adaptive prefix ranges rather than a naive alphabet split,
  and it includes SLOs, per-layer metrics, guardrails, and a bad range-map
  rollout drill.
- `technologyChoices` is present and usefully grouped around the prefix index,
  edge/cache, event stream, and stream aggregation.

## Highest-Impact Issues

### 1. Final diagram still has one stale read-path edge

The updated final caption and final sequence correctly say the API owns the
request: cache miss goes to API, API asks the router/range map for the owning
shard, then API orchestrates fuzzy expansion, personalization, and safety.

The final view still includes both `cache-api-miss` and `cache-router-miss`.
That creates two miss paths from cache and makes the diagram imply the cache can
bypass the API and call the router directly.

Concrete fix:

- In `finalDesign.view.links`, remove `cache-router-miss`.
- Keep `cache-api-miss`, `router-routing`, and the router-to-shard links.
- If Step 7 keeps a simplified `Cache -> Router` view for teaching sharding,
  make the caption explicit that it is omitting the API for focus.

### 2. Adaptive range naming is still mixed with static shard labels

The text now correctly teaches a `Prefix Range Map` with adaptive ranges, hot
range splits, per-range rollout, and rollback. The shared architecture nodes
still label the shards as `Index Shard A-M` and `Index Shard N-Z`, and Step 7's
main view still uses `router-sharda-by-first-char`.

Why it matters:

- The dataset explicitly warns against static alphabet splits, but the visual
  labels keep reinforcing that simplified model.
- The final design is intended to be the target production design, so the
  diagram should not leave the older teaching split as the first visual signal.

Concrete fix:

- Rename `ShardA`/`ShardB` labels to adaptive examples such as `Index Shard:
  hot s* ranges` and `Index Shard: long-tail ranges`, or `Shard 1` and
  `Shard 2`.
- Replace `router-sharda-by-first-char` in the Step 7 main view with
  `router-sharda-by-prefix` or a new link labelled `by range map`.
- Keep the `A-M / N-Z` wording only inside the deep dive as an explicit
  teaching simplification.

### 3. Locale, market, and version keying need one canonical contract

Locale support is now much stronger, but the key fields are not fully
consistent. The API request has both `locale=en-US` and `market=US`.
`term_metadata` has `locale`, `language`, `market`, `script`, and analyzer
versions. `prefix_topk`, `query_counts`, and `trending_overlay` use `locale`
but not `market`. The cache key prose says `prefix + locale + safe_mode + index
version`.

Why it matters:

- If ranking is per market, then `en-US` versus `en-GB`, policy version, and
  analyzer version affect which suggestions are correct.
- If those fields are not consistently part of the index/cache/range-map key,
  the system can serve suggestions produced by the wrong analyzer, market, or
  safety policy.

Concrete fix:

- Decide whether `locale` is the canonical compound key (`en-US`) or whether
  `locale` and `market` are separate dimensions.
- Apply that choice consistently to `prefix_topk`, `query_counts`,
  `trending_overlay`, cache keys, and `prefix_range_map`.
- Consider adding `policy_version`, `tokenizer_version`, or
  `normalization_version` to the cache/index-version explanation if those can
  change the served result.

### 4. Safety and cache semantics should be stated more explicitly

The design says global responses are edge-cacheable and that the safety filter
screens suggestions before return. That can work, but the cache-hit path in the
final sequence returns directly from the edge and never calls the safety filter.

Concrete fix:

- State that edge-cached global responses are already safety-filtered and keyed
  by `safe_mode` plus the active moderation policy/version, or state that
  safety runs before cache population and unsafe-policy changes purge/age out
  affected cache entries.
- Add one sentence explaining what happens when `personalize=on`: the request
  bypasses the shared edge cache or uses cached global candidates only as input
  to an origin-side re-rank and safety screen.

## System Design Soundness

The architecture is sound. A read-optimized prefix index with precomputed top-k,
edge caching for the skewed hot head, async popularity ingestion, versioned
offline rebuilds, bounded freshness overlay, optional personalization, safety
filtering, and adaptive prefix sharding is the right shape for this problem.

Requirements are now broad enough for a production autocomplete service. Safety,
privacy, abuse resistance, locale/language, freshness, low latency, and graceful
degradation all appear in the right places.

The capacity section is especially useful. It makes clear that 1M QPS is only
one pressure; memory footprint and prefix-node count are equally important. The
top-k math now justifies sharding by memory as well as by traffic.

The API is credible and aligned with the architecture. The only recommended
improvement is to formalize which request dimensions affect cacheability and
index selection: locale/market, safe mode, policy version, analyzer version,
personalization, and index version.

The data model is now much more complete. The remaining polish is semantic:
make per-market ranking keys consistent, add any missing audit fields implied
by `moderation_decisions` if desired, and decide whether `terms.score` is a
global score or whether all ranking scores live in per-locale derived tables.

## Step-by-Step Pedagogical Review

### Step 1: Naive Prefix Scan

Strong baseline. The added trap about one-character prefixes makes the failure
mode concrete: even an indexed range scan still has to read and sort a huge
range under per-keystroke load.

### Step 2: Trie Prefix Index

This step is now excellent. It teaches the simple trie first, then immediately
places it in production context with compressed tries, FSTs, DAWGs, and
locale-aware analyzers. Keep both deep dives.

### Step 3: Precomputed Top-K per Prefix

This remains the core design step. The current wording correctly explains that
top 5-10 per node is locally small but globally huge because node count
dominates storage. The sorted-set alternative is useful because it illustrates
write amplification without being a strawman.

### Step 4: Edge Caching

The cacheability and personalization conflict is handled well: global responses
are shared; personalized responses re-rank at origin. The version discovery
sentence is a good addition.

Recommended polish: make safety policy/version part of the cache story, since
cache hits bypass the origin-side safety filter in the final sequence.

### Step 5: Freshness from the Query Stream

This step is now production-realistic. The collector, dedupe/trust trap,
versioned rebuilds, overlay option, rollback drills, and freshness metrics give
candidates enough material for a senior answer.

### Step 6: Typo Tolerance & Personalization

Good placement after the fast/fresh core. The ranking merge order is clear:
exact matches win, fuzzy fills gaps, personalization is capped, and global
fallback remains. The privacy and safety traps are valuable.

Recommended polish: in the final design, keep the ownership consistent with
this step: API orchestrates `Spell`, `Personalizer`, and `Safety`; router owns
range lookup only.

### Step 7: Scaling by Prefix Sharding

The new adaptive range-map content is strong and fixes the old static-sharding
weakness. The SLO/observability deep dive and bad range-map rollout drill are
exactly the right operational additions.

Recommended polish: update shard labels and the Step 7 main link labels so the
visual no longer suggests a fixed `A-M / N-Z` split.

## Final Design Review

The final design now integrates the components introduced during the journey:
`CDN`, `Cache`, `API`, `Router`, `Routing`, sharded indexes, `TopK`, `Spell`,
`Personalizer`, `Profile`, `Safety`, `Collector`, `Stream`, `Agg`, `Counts`,
and `Builder`.

The final read sequence is also useful. It rehearses cache hit, miss, prefix
routing, shard lookup, bounded fuzzy expansion, optional personalization,
safety screening, and response with `indexVersion`.

Remaining final-design fixes:

- Remove the direct `cache-router-miss` edge from the final view.
- Consider adding `Routing` as a sequence participant if the range map should
  be visible in the final read path rather than only mentioned in the router
  message.
- Rename static shard labels or add adaptive-range labels in the final diagram.
- Clarify that cache-hit responses are already filtered for the relevant
  `safe_mode` and policy version.

## Concept Introduction and Learning Flow

The concept progression is strong and now covers the important concepts at the
right time: prefix index, top-k precomputation, skewed hot-head caching,
stream-derived popularity, atomic rebuild, bounded overlay, fuzzy matching,
personalization blend, safety filtering, privacy, adaptive prefix ranges, and
operational observability.

The main learning-flow opportunity is to align visuals with the newer concepts.
When text says "adaptive range map" but node labels say `A-M / N-Z`, readers
can retain the wrong mental model. This is a small edit with high teaching
value.

## Step-to-Final-Design Coherence

Coherence is high:

- `naive-prefix` motivates replacing live DB scans.
- `trie` introduces the prefix lookup structure.
- `topk` moves ranking off the hot path.
- `caching` absorbs the skewed hot head.
- `freshness` adds the collector, stream, decayed counts, rebuilds, overlay,
  canary, and rollback.
- `spelling` layers fuzzy match, personalization, privacy, and safety.
- `scale` adds prefix routing, adaptive ranges, shards, replicas, and
  operational guardrails.

The remaining coherence gaps are visual and contractual:

- Final view has both `Cache -> API` and `Cache -> Router`.
- Adaptive range-map text is stronger than the static shard labels.
- Locale/market/version fields need one consistent key contract.

## Realism Compared With Production Systems

The dataset now reads like a realistic production design. It covers read-heavy
skew, memory footprint, precomputed ranking, cache hit targets, event ingest,
dedupe, trust filtering, moderation, privacy retention, versioned rebuilds,
range-map rollout, auto-rollback, and per-layer observability.

The remaining realism gaps are narrow:

- Safety cache invalidation should mention policy versions or filtered cache
  population.
- Per-market keying should be exact enough that a candidate cannot accidentally
  mix analyzer versions or markets.
- `moderation_decisions` could include reviewer/source details if the review
  workflow is meant to be teachable rather than just named.
- A/B testing is still only a follow-up; that is acceptable, but a staff-level
  answer might want a ranking-experiment note.

## Dataset and Renderer-Facing Observations

Validated:

- `interview.json` parses as JSON.
- String `view.nodes` references in steps resolve to
  `highLevelArchitecture.nodes`.
- String `view.links` references in steps resolve to
  `highLevelArchitecture.links`.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Step `probeLinks` resolve to `toProbeFurther.links`.
- `technologyChoices[*].steps[*]` references resolve.
- The dataset uses structured views and structured sequence flows, not raw
  Mermaid, for step and final architecture.

Minor observations:

- `REVIEW.md` is repo-only; no `docs/` rebuild is needed for this review update.
- Many technology-choice chips still use `assets/tech-icons/tech.png`. This is
  valid, but curated provider icons would improve rendered polish.
- There are no AI visual/comic assets for this dataset. That is optional and
  not a correctness issue.

## Recommended Edits, Prioritized

### P1: Align the final read-path diagram

Remove `cache-router-miss` from `finalDesign.view.links` or clearly mark it as a
simplified teaching edge outside the final target design.

### P1: Replace static shard labels with adaptive-range labels

Update `ShardA`/`ShardB` labels and the Step 7 main view link so the visuals
match the adaptive prefix range map now taught in the text.

### P2: Normalize locale/market/version keying

Choose one canonical contract for locale/market/analyzer/policy/index version
and apply it across API examples, cache keys, `prefix_topk`, `query_counts`,
`trending_overlay`, and `prefix_range_map`.

### P2: Clarify safety-aware caching

State whether cached global responses are already safety-filtered and keyed by
policy/safe-mode, or whether cache invalidation handles policy updates.

### P3: Polish provider icons and level variants

Replace generic `tech.png` fallbacks where curated icons exist. Consider adding
Staff+ expectations for adaptive range-map rollout, moderation policy, and
per-layer SLOs now that those concepts are in the core dataset.

## What Not To Change

- Keep the seven-step progression.
- Keep the naive scan baseline.
- Keep precomputed top-k as the central solution.
- Keep periodic rebuild plus atomic swap as the default freshness strategy.
- Keep the bounded real-time overlay as an option, not the whole design.
- Keep the safety, privacy, abuse-resistance, and event-collector material.
- Keep structured `view` and `sequence` data instead of raw Mermaid.

## Bottom Line

This is now a strong, credible autocomplete system design interview. The recent
updates fixed the major architectural and teaching gaps. The next best work is
small but important: make the final diagram match the API-owned read path, make
adaptive range labels visible, and tighten the locale/market/cache/safety
contract so the production story is precise end to end.
