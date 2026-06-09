# Review: Search Autocomplete - System Design

Reviewed file: `data/book/autocomplete/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong, production-oriented autocomplete interview. The core journey is
well staged: start with a failing database scan, introduce a trie, move ranking
into precomputed top-k lists, use edge caching for prefix skew, feed freshness
from the query stream, add fuzzy/personalized quality layers, and then shard by
adaptive prefix ranges.

The dataset already covers many topics that weaker autocomplete cases miss:
memory pressure from prefix nodes, cache hit targets, decayed counts, collector
dedupe and trust filtering, versioned rebuilds, canary/rollback, safety
moderation, short-retention personalization, locale analyzers, and operational
metrics. The remaining issues are not about the broad architecture being wrong;
they are about making the contract precise enough that the diagrams, API, data
model, and final sequence all teach the same production system.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | Strong target architecture; cache/index/keying and ingest trust boundaries need tightening. |
| Production realism | 4.3/5 | Good guardrails and ops coverage; full rebuild timing and policy/cache semantics need more precision. |
| Pedagogical flow | 4.6/5 | Excellent staged progression; a few visuals still reinforce older simplifications. |
| Dataset/rendering fit | 4.4/5 | References validate; node types and final read-path links should be cleaned up. |
| Overall | 4.4/5 | A credible book-quality case with a focused set of cleanup edits left. |

## What Works Well

- The seven-step sequence has the right shape for an interview: each step
  exposes the pressure that motivates the next one.
- The capacity section names the real drivers: 1M QPS, p99 latency, 100M+
  terms, top-k size per node, prefix-node count, cache hit rate, event ingest,
  and rebuild duration.
- The API supports both read and write sides: `GET /v1/suggest` for cacheable
  global suggestions and `POST /v1/events/query` for popularity events.
- The data model includes production state that matters: `prefix_topk`,
  `index_versions`, `prefix_range_map`, `event_dedupe`,
  `moderation_decisions`, `trending_overlay`, `query_counts`, and
  short-retention `user_history`.
- Step 2's analyzer/locale deep dive is useful and unusually concrete. It
  explains normalized text, display text, scripts, tokenizer versions, and
  per-market ranking.
- Step 5 is strong: it includes collector filtering, stream aggregation,
  decayed counts, offline rebuilds, atomic swaps, canaries, rollback, a bounded
  overlay, and freshness observability.
- Step 7 teaches the right sharding principle: prefix-range routing with hot
  ranges split finer, replicas for read load, and range-map rollback.
- `technologyChoices` is well grouped around index/top-k storage, edge caching,
  event streams, and stream aggregation.

## Highest-Impact Issues

### 1. The final read-path diagram contradicts the API-owned orchestration

The prose and final sequence say the API owns the read request: cache miss goes
to the API, the API consults the router/range map, then it orchestrates fuzzy
matching, personalization, and safety.

The final view still includes both `cache-api-miss` and `cache-router-miss`.
That creates two miss paths out of the cache and visually implies that the cache
can bypass the API and call the prefix router directly. There is also no explicit
API-to-router link in the final architecture view, even though the final
sequence has `API -> Router`.

Concrete fix:

- Add a high-level `api-router` link or equivalent, then use
  `cache-api-miss` followed by `api-router` in `finalDesign.view.links`.
- Remove `cache-router-miss` from the final target design, unless the caption
  explicitly says the diagram is simplifying away the API for a sharding-only
  teaching view.
- Consider adding `Spell` to the final sequence, or make the sequence message
  clear that the API is internally invoking the fuzzy matcher before routing
  bounded fuzzy variants.

### 2. Locale, market, analyzer, policy, and version keying need one contract

The dataset correctly says autocomplete must be locale/language/market aware,
but the fields are not applied consistently:

- The request has both `locale=en-US` and `market=US`.
- `term_metadata` includes `locale`, `language`, `market`, `script`,
  `tokenizer_version`, and `normalization_version`.
- `prefix_topk`, `query_counts`, and `trending_overlay` use `locale` but not
  `market`.
- The cache-key prose names `prefix + locale + safe_mode + index version`, but
  omits `market` and policy/analyzer dimensions.

Why it matters: if ranking, moderation, or analyzer behavior differs by market
or policy version, a cache or index keyed too narrowly can serve plausible but
wrong suggestions.

Concrete fix:

- Decide whether `locale` is the full market key (`en-US`) or whether
  `locale` and `market` are separate dimensions.
- Apply the chosen key to `prefix_topk`, `query_counts`, `trending_overlay`,
  cache keys, and any `prefix_range_map` scope.
- Explain how `indexVersion` relates to `tokenizer_version`,
  `normalization_version`, and moderation `policy_version`.

### 3. The event ingest API appears to trust client-provided normalization

`POST /v1/events/query` includes both `query` and `normalized_query` in the
client request, while the description says the collector normalizes events
before counts move. That is a trust-boundary mismatch.

Why it matters: normalized text is part of the ranking signal. If the client
supplies it, a bad or buggy client can distort counts, bypass locale analyzers,
or create inconsistencies between query-time normalization and build-time
normalization.

Concrete fix:

- Remove `normalized_query` from the client request example, or mark it as a
  server-derived field written after collector normalization.
- If client analyzers exist for latency or UX, include an analyzer/version hint
  but make the collector recompute canonical normalized text server-side.
- Add this to the event-collector trap: never count client-supplied normalized
  keys without server-side canonicalization.

### 4. The minutes-level full rebuild promise is under-specified

The capacity section says full rebuild duration is "minutes per full build",
and Step 5 uses periodic full rebuild plus atomic swap as the default freshness
path. That is directionally right for a teaching case, but at 100M+ terms and
10^8-10^9 prefix nodes it needs more explanation.

Why it matters: candidates should not leave thinking one monolithic trie/top-k
artifact is rebuilt and globally distributed every few minutes without naming
parallelism, shard-local builds, artifact rollout, or dirty-prefix overlays.

Concrete fix:

- State that rebuilds are shard/range-local and parallelized, not a single
  global artifact.
- Distinguish base-index rebuild freshness from the bounded overlay freshness:
  overlay can surface viral terms quickly; base rebuild absorbs them later.
- Add a build SLO note: input count lag, build duration, artifact publish time,
  canary hold time, and cache adoption together define freshness.

### 5. Some node types and visual labels still teach the older model

The dataset references validate, but a few visual semantics are misleading:

- `Builder` is typed as `index`, so the renderer describes it as a derived
  lookup structure rather than a background worker/build pipeline.
- `Cache` is typed as `edge`, although this component is often an edge or
  prefix cache; the canonical `cache` type may communicate the role better
  while leaving `CDN` as `edge`.
- `ShardA` and `ShardB` are labelled `Index Shard A-M` and `Index Shard N-Z`,
  while Step 7 warns that static alphabet splits are only a simplification.
- Step 7's main view still uses `router-sharda-by-first-char`, which conflicts
  with the adaptive range-map lesson.

Concrete fix:

- Change `Builder` to a worker-like type and adjust its description.
- Consider changing `Cache` to canonical `cache`.
- Rename shard labels to adaptive examples such as `Hot Prefix Range Shard`
  and `Long-Tail Range Shard`, or neutral `Index Shard 1` and `Index Shard 2`.
- Use a `by prefix range` link in the Step 7 main view.

### 6. Safety-aware caching needs one explicit sentence in the final path

The design says the safety filter screens suggestions before return, but the
final cache-hit branch returns directly from the edge. That is valid only if the
cached response was already filtered under the right `safe_mode`, locale, and
moderation policy version.

Concrete fix:

- State that only post-safety global responses are edge-cacheable.
- Include `safe_mode` and moderation policy/version in the cache/index version
  explanation, or state how policy changes purge/age out cached responses.
- For `personalize=on`, state that cached global candidates may be reused only
  as input to an origin-side re-rank followed by safety screening.

## System Design Soundness

The core architecture is sound. A read-optimized prefix structure with
precomputed top-k, edge caching for skew, asynchronous popularity collection,
versioned rebuilds, bounded trending overlays, optional personalization, safety
screening, and adaptive prefix-range sharding is the right shape for a large
autocomplete service.

The requirements are broad enough for a production discussion. They include low
latency, extreme read QPS, freshness, eventual consistency, privacy,
locale/language behavior, typo tolerance, safety, and abuse resistance.

The capacity section is one of the dataset's strengths. It makes the memory
cost of per-prefix top-k visible and explains why sharding is driven by memory
footprint as much as by read QPS. The next improvement is to tie the rebuild
duration estimate to shard-local parallel builds and artifact rollout.

The API is close. The GET endpoint usefully separates cacheable global
suggestions from origin-side personalization, but the example should avoid
sending `anon_id` when `personalize=off` unless there is a clear consent/use
case. The event POST endpoint should not present `normalized_query` as a
trusted client field.

The data model is strong but needs key consistency. If rankings are per market,
then the prefix index, counts, overlay, cache, and routing contracts need the
same market/analyzer/policy dimensions.

## Step-by-Step Pedagogical Review

### Step 1: Naive Prefix Scan

Strong baseline. It correctly rejects `LIKE 'prefix%' ORDER BY popularity` and
uses one-character prefixes to make the failure mode concrete.

### Step 2: Trie Prefix Index

Excellent teaching step. It introduces the trie simply, then adds compressed
tries, FSTs, DAWGs, and locale-aware analyzers without derailing the main flow.

### Step 3: Precomputed Top-K per Prefix

This is the key design step and it lands well. The bottom-up top-k explanation
and the sorted-set alternative teach the read/write asymmetry and write
amplification trade-off.

### Step 4: Edge Caching

The edge-cache argument is strong because it uses traffic skew, TTLs,
stale-while-revalidate, and the personalization conflict. Add the safety/policy
cache semantics so the final cache-hit path remains credible.

### Step 5: Freshness from the Query Stream

This is production-realistic. The collector, decayed counts, canary, rollback,
overlay option, and freshness metrics give a senior candidate enough depth. The
only gap is making rebuild scope and timing explicit.

### Step 6: Typo Tolerance & Personalization

Good placement after the fast/fresh core. The step keeps fuzzy expansion
bounded and treats personalization as a capped re-rank. It also carries privacy
and safety material. This makes the step rich, but slightly overloaded; that is
acceptable if the final sequence clearly preserves the roles of `Spell`,
`Personalizer`, and `Safety`.

### Step 7: Scaling by Prefix Sharding

The adaptive range-map material is strong. The bad range-map rollout drill is
especially useful. Update shard labels and the main link label so the visual
does not keep teaching fixed `A-M / N-Z` sharding.

## Final Design Review

The final design integrates most components introduced along the way: `CDN`,
`Cache`, `API`, `Router`, `Routing`, shards, `TopK`, `Spell`, `Personalizer`,
`Profile`, `Safety`, `Collector`, `Stream`, `Agg`, `Counts`, and `Builder`.

The target behavior is clear in prose: read requests are mostly edge hits; cache
misses route to sharded top-k indexes; fuzzy and personalization layers are
bounded; safety screens the result; executed searches feed freshness through a
collector and stream; versioned rebuilds plus a bounded overlay update the
served suggestions.

The final artifacts should be tightened:

- Align the view links with the sequence: cache miss to API, API to router, then
  router/range map to shard.
- Include or explicitly abstract the `Spell` participant in the final sequence.
- Make cache-hit safety and policy/version semantics visible.
- Rename static shard labels or add adaptive-range labels in the final diagram.

## Concept Introduction and Learning Flow

The concept order is strong: prefix lookup, trie, top-k, skew/caching,
freshness, atomic swap, fuzzy expansion, personalization, privacy, safety,
sharding, range-map rollout, and observability all arrive when they are needed.

The biggest learning-flow risk is visual mismatch. When the prose teaches
adaptive prefix ranges but the diagram says `A-M / N-Z`, or when the sequence
says API-owned routing but the final view says `Cache -> Router`, candidates can
retain the simplified model instead of the production model.

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

The coherence gaps are concentrated in the final diagram contracts:

- final view has both `Cache -> API` and `Cache -> Router`;
- final sequence compresses the fuzzy matcher role;
- adaptive range-map text is stronger than the shard labels;
- locale/market/version fields need one canonical key contract.

## Realism Compared With Production Systems

The dataset reads like a realistic production design. It covers the major
operational concerns: hot-prefix skew, memory footprint, cache hit targets,
event ingest, dedupe, trust filtering, privacy retention, moderation, versioned
rebuilds, range-map rollout, automatic rollback, and per-layer observability.

The remaining realism gaps are narrow but important:

- full rebuild freshness needs shard-local/parallel build semantics;
- cache hits need explicit safety and policy-version semantics;
- per-market keying needs to be exact enough to prevent accidental cross-market
  or cross-analyzer leakage;
- event normalization should be server-owned;
- A/B testing is only a follow-up, which is acceptable, but a staff-level
  version could add one short ranking-experiment note.

## Dataset and Renderer-Facing Observations

Validated:

- `interview.json` parses as JSON.
- Step string `view.nodes` references resolve to `highLevelArchitecture.nodes`.
- Step string `view.links` references resolve to `highLevelArchitecture.links`.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.
- `satisfies[*].steps[*]`, `patterns[*].steps[*]`, and
  `technologyChoices[*].steps[*]` resolve to real step IDs.
- Step `probeLinks` resolve to `toProbeFurther.links`.
- Structured sequence participants resolve to canonical high-level node IDs.
- Authored highlights resolve to known high-level nodes.
- The dataset uses structured views and structured sequence flows for steps and
  final design, not raw Mermaid architecture diagrams.

Renderer-facing cleanup:

- `Builder` should not render as an `index` node if it is the build worker.
- `Cache` may be clearer as `cache` rather than a second `edge` node.
- Static shard labels should not be the dominant final visual.
- `REVIEW.md` is repo-only; no `docs/` rebuild is needed for this review
  update.

Optional polish:

- Many technology-choice chips still use `assets/tech-icons/tech.png`; curated
  provider icons would improve rendered polish.
- There are no AI visual or comic assets for this dataset. That is optional and
  not a correctness issue.

## Recommended Edits, Prioritized

### P1: Align the final read path

Remove `cache-router-miss` from `finalDesign.view.links`, add or use an
API-to-router link, and make the final sequence/view agree about who owns
routing and fuzzy orchestration.

### P1: Make locale/market/version keying canonical

Choose the canonical key dimensions and apply them to API examples, cache keys,
`prefix_topk`, `query_counts`, `trending_overlay`, and `prefix_range_map`.

### P1: Move normalization ownership to the collector

Remove client-supplied `normalized_query` from the event request example or
mark it as server-derived after collector normalization.

### P2: Explain rebuild scope and freshness timing

Clarify that base rebuilds are shard/range-local and parallelized, while the
bounded overlay covers faster viral-term freshness between rebuilds.

### P2: Fix node types and shard labels

Change `Builder` to a worker-like type, consider `Cache` as `cache`, replace
static shard labels, and update Step 7's `by first char` link.

### P2: Clarify safety-aware caching

State that cacheable global responses are post-safety responses keyed by
`safe_mode` and policy/version, or explain cache invalidation on policy change.

### P3: Polish rendered extras

Replace generic `tech.png` icon fallbacks where curated icons exist. Consider
adding Staff+ expectations for adaptive range-map rollout, policy-aware caching,
and ranking experiments.

## What Not To Change

- Keep the seven-step progression.
- Keep the naive scan baseline.
- Keep precomputed top-k as the central read-path optimization.
- Keep edge caching as the QPS and latency lever for the skewed hot head.
- Keep periodic rebuild plus atomic swap as the default freshness strategy.
- Keep the bounded real-time overlay as an option layered over the base index.
- Keep the event collector, safety, privacy, and abuse-resistance material.
- Keep structured `view` and `sequence` data instead of raw Mermaid.

## Bottom Line

This is a strong autocomplete system design interview. The next best work is
focused cleanup: align the final diagram with API-owned routing, make
locale/market/version keying exact, move event normalization fully inside the
collector, and update visual labels so the diagrams teach the same production
model as the prose.
