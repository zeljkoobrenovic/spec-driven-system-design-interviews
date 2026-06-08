# Review: Nearby Search (Yelp / Maps) - System Design

Reviewed file: `data/book/nearby-search/interview.json`
Review date: 2026-06-08

## Executive Summary

The current nearby-search dataset is substantially stronger than the earlier
reviewed version. The recent changes addressed the largest gaps: capacity now
turns raw scale into cells, candidates, cache reads, shard skew, and latency
budget; the API includes create, update, delete, idempotency, versioning, and
tombstones; the data model covers place lifecycle and change events; final
design now has explicit search and write sequence flows; ranking and indexing
have realistic failure drills; and the renderer-facing dropped-edge issues are
fixed.

This is now a strong book case. It teaches the essential nearby-search arc in a
clean sequence: reject a table scan, add a spatial index, handle radius
boundaries, adapt to density, separate recall from ranking, and operate the
derived index asynchronously. The remaining issues are narrower and mostly
about tightening the quantitative story and making a few production contracts
fully explicit.

Overall assessment:

| Dimension | Rating | Notes |
|---|---:|---|
| System design soundness | 4.5 / 5 | Architecture, API, data model, ranking, and async indexing are credible; cell-size math and hot-path metadata need tightening. |
| Production realism | 4.3 / 5 | Stronger on events, replay, rebuild, lag, ranking fallback, and cache failure; still needs explicit outbox/CDC and global/privacy/abuse treatment. |
| Pedagogical flow | 4.7 / 5 | The step progression is clear, compact, and interview-friendly. |
| Final design coherence | 4.6 / 5 | Final design now integrates query and write paths with sequence flows; the selected geo-index policy could be more concrete. |
| Dataset/rendering fit | 4.8 / 5 | JSON and references validate; no current diagram endpoint blockers. Optional visual polish remains. |

Recommendation: keep the shape and step order. Make targeted edits to correct
the cell-covering arithmetic, align `geo_index.entry_meta` with the promised
hot-path filters and idempotency, state how place writes and change events are
made atomic, and promote privacy/abuse/global availability concerns from
follow-ups into the main design if this should be a flagship case.

## What Works Well

- The case teaches the core insight well: radius search needs a spatial index
  so the system touches a covering set of cells instead of scanning all places.
- The capacity section now gives useful design constraints: cells per query,
  candidates per query, cache reads, index size, hot-region skew, and p99
  budget.
- The API now supports the place lifecycle: create, update, delete, idempotent
  writes, optimistic versions, tombstones, and old-cell/new-cell move events.
- The data model is much more production-shaped: authoritative `places`,
  derived `geo_index`, and replayable `place_change_events`.
- Step 3 correctly teaches covering sets and demotes "cell + 8 neighbors" to a
  small-radius special case.
- Step 5 bounds ranking cost with a two-stage rank path, top-N ETA calls,
  timeout fallback, and top-K hydration.
- Step 6 now explains derived-index operation: idempotency, replay/backfill,
  dead-letter handling, shadow rebuild, atomic swap, lag SLOs, hot-cell
  splitting, and read replicas.
- Final design now includes both search and write flows, which closes a major
  teaching gap from the earlier review.
- `technologyChoices` gives useful implementation comparisons across PostGIS,
  OpenSearch, S2/H3 over KV stores, Redis/Valkey, cloud streams, caches, and
  routing services.

## Highest-Impact Issues

### 1. The capacity cell-size arithmetic is still inconsistent

The capacity section says that at `~150 m` cells a `0.5 km` radius covers a
`3x3` ring (`~9 cells`). That arithmetic is not defensible: a 500 m radius has a
1 km diameter, so 150 m cells need several cells across the diameter before
counting boundary over-cover. A 3x3 neighborhood only works when the radius is
small relative to cell size.

Why it matters: this dataset now correctly emphasizes covering sets, candidate
counts, and latency. A wrong numerical example weakens the main quantitative
argument and can teach candidates the exact shortcut the boundary step warns
against.

Concrete fixes:

- Align the example cell size with the claimed cell count, or align the claimed
  cell count with `150 m` cells.
- Show the rough formula: cells touched is proportional to query-circle area
  divided by cell area, plus boundary over-cover.
- Split examples by precision, such as "coarser cells for 0.5 km keep the cover
  near one ring; fine 150 m cells require many cells but reduce candidates per
  cell."
- Keep `~9-50` only if the chosen precision policy can justify it for the
  stated `0.5-5 km` radius range.

### 2. Hot-path filter metadata does not fully match the promised behavior

The dataset says category, price, and open-now filters are applied from
index/entry metadata before hydration. The `geo_index.entry_meta` currently
lists `lat`, `lng`, `category`, `price_level`, `popularity`, and `status`, but
not the fields needed to compute open-now without a detail fetch. It also does
not explicitly include the per-entry `place_version` that Step 6 relies on for
idempotent index updates.

Why it matters: open-now is one of the advertised product filters, and it is on
the hot query path. If it requires hydrating hundreds of candidates from
`PlaceDB`, the ranking cost story breaks. Similarly, idempotent event handling
needs the index entry to remember which place version it reflects.

Concrete fixes:

- Add `timezone` and an `opening_hours_summary` / `open_state_until` field to
  `geo_index.entry_meta`, or state that open-now is precomputed periodically and
  stored as a time-bucketed bit.
- Add `place_version` to `entry_meta` so duplicate and out-of-order events can
  be skipped locally.
- Clarify whether `status=temp_closed` is a lifecycle flag, an open-now signal,
  or both. It should not be the only representation of business hours.
- Update the "Filter by category / price / open-now" satisfies entry to point
  to the exact metadata fields used.

### 3. The write-event atomicity contract is only implicit

Step 6 says the place service writes the authoritative store and emits a change
event, and `technologyChoices` mentions CDC/outbox trade-offs. The main step
should explicitly close the dual-write hole: what prevents a place write from
committing while the change event is lost?

Why it matters: the geo index is derived state. Replay and rebuild help repair
drift, but the clean production answer is usually transactional outbox or CDC
from `PlaceDB`, not a best-effort app publish after commit.

Concrete fixes:

- In Step 6, state the default mechanism: transactional outbox table in
  `PlaceDB` drained to `ChangeQ`, or CDC from the place table/change table.
- Show this in the write flow label, for example "persist place + outbox event"
  before `ChangeQ`.
- Keep the app-emitted event option as a trade-off only if it is explicitly
  transactional with the write.
- Add a failure drill for "DB write succeeds but event publish fails."

### 4. Global availability, privacy, and abuse controls are still mostly wrap-up topics

The follow-ups and interview script now mention location privacy, radius caps,
result limits, and rate limiting. That is good, but these concerns are not yet
visible in the requirements, API, high-level architecture, or final design.

Why it matters: nearby search handles sensitive coordinates and public
high-QPS read endpoints. A production-grade answer should not leave retention,
access controls, query validation, and abuse limits as optional afterthoughts.

Concrete fixes:

- Add a non-functional requirement for user-location privacy: log minimization,
  short retention, access controls, and coarse-grained analytics.
- Add API notes for coordinate validation, maximum radius, maximum `limit`, and
  per-client/API-key rate limits.
- Mention gateway enforcement in the `LB` / API gateway node description or a
  small failure drill.
- Add a short global-read strategy: region/cell-prefix routing, read replicas,
  graceful degradation when a regional index shard is unavailable, and what
  happens to cross-region writes.

### 5. The final design compares index families but does not clearly choose one

The dataset offers geohash, S2, quadtree, and H3 concepts/technology choices.
That is useful, but the final design keeps `GeoIndex` generic. The default
option in Step 2 is "Geohash prefix index"; Step 3 leans on S2/H3-style region
coverers; Step 4 discusses variable precision. Those can coexist, but the final
answer should tell the candidate which concrete policy is being defended.

Why it matters: the interviewer wants to hear a chosen design and its trade-offs,
not only a catalog of possible spatial indexes.

Concrete fixes:

- State a default final choice, such as "S2/H3 region covering backed by a KV
  cell index" or "geohash prefix index with per-region precision tuning."
- Tie that choice back to the capacity examples: chosen cell levels, fanout cap,
  target candidates per cell, and hot-prefix sharding.
- Leave the other options as alternatives, but make the selected option the one
  used consistently in final design prose, diagrams, and capacity.

## System Design Soundness

The functional requirements cover the right product behavior: radius query,
filters, ranking, place lifecycle, and details. The non-functional requirements
also name the right axes: read-heavy traffic, p99 latency, global scale,
availability, eventual consistency, and boundary correctness.

The capacity section is now useful rather than decorative. It links `100M`
places and `10K` searches/sec to query fanout, candidate counts, cache pressure,
hot-region skew, index storage, and a p99 budget. The remaining work is to make
the cell-size example mathematically consistent with the selected precision
policy.

The API is strong for this scope. `GET /v1/nearby` exposes the core search
shape, `POST /v1/places` has idempotency, and `PATCH`/`DELETE` make move and
remove semantics explicit. A production version should add request validation
and caps directly to the API notes: maximum radius, maximum limit, valid
coordinate bounds, and rate-limit identity.

The data model is much better than before. It now distinguishes source of truth,
derived index, and change log. The highest-value adjustment is to add the exact
metadata needed by the read path: open-now fields and per-entry version in
`geo_index.entry_meta`.

The architecture is directionally right: `SearchSvc`, `GeoIndex`, `Ranker`,
`ETA`, `PlaceCache`, `PlaceDB`, `PlaceSvc`, `ChangeQ`, and `Indexer` are the
right components. The read path bounds expensive work, and the write path treats
the index as derived state. The main missing production contract is making the
PlaceDB write and change-event emission atomic through outbox or CDC.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Scan and Compute Distance

This remains the right opening. It creates a clear baseline, shows why two
independent lat/lng indexes are insufficient, and motivates a spatial index.
The earlier diagram problem is fixed: the view now uses an inline
`SearchSvc -> PlaceDB` scan edge, so the rendered diagram shows the intended
lesson.

### Step 2: Geospatial Index: Geohash / S2 Cells

This is a strong core step. The options compare real alternatives: geohash
prefix index, S2 cells, and quadtree. The added H3 concept is useful because it
explains why H3 appears in further reading and technology choices.

The improvement to make is commitment. If geohash remains the default, explain
how per-region precision and covering sets are implemented with prefix ranges.
If S2/H3 is the intended final answer, make that the default and present
geohash as the simpler baseline.

### Step 3: Handle Cell Boundaries and the Radius

This step is now much better. It explicitly teaches covering sets, exact
haversine filtering, and the trap of assuming one neighbor ring always covers
the radius. That fixes the previous review's largest pedagogical concern.

The remaining problem is the capacity example, not the step explanation. Keep
the Step 3 wording and update the capacity numbers so they reinforce the same
covering-set lesson.

### Step 4: Adapt to Uneven Density

This is a good follow-up to boundaries. It explains why one fixed cell size
fails and introduces variable precision, fixed cells, and expanding rings as
real trade-offs. The new mixed-precision warning about parent/child dedupe and
fanout caps is exactly the right teaching detail.

For further polish, add one concrete threshold example: target candidates per
cell, maximum cells per query, and what fallback happens when the cap is hit.

### Step 5: Rank and Filter Candidates

This step is strong. It correctly separates candidate generation from ranking,
applies cheap filters before hydration, bounds ETA/ML to top-N, and adds
timeout fallback. The failure drills for ETA, ranking timeout, and cache outage
make the p99 story credible.

The main fix is schema alignment: the index metadata must contain the fields
the step says are used for open-now and versioned filtering.

### Step 6: Keep the Index Fresh (Async Write Path)

This is the most improved step. It now teaches the right production mechanics:
event shape, idempotent `(place_id, version)` updates, old/new cell handling,
dead-letter and replay, shadow rebuild, atomic swap, reconciliation, lag SLOs,
hot-cell splitting, and read replicas.

The remaining gap is atomic event creation. Add outbox or CDC to the step
itself so candidates do not accidentally describe a fragile dual write from
`PlaceSvc` to both `PlaceDB` and `ChangeQ`.

## Final Design Review

The final design now coherently combines the read and write paths:

- Search computes a covering set for the radius.
- The geo index returns candidate ids and lightweight metadata.
- Exact-distance filtering and stage-one ranking bound the candidate set.
- ETA is optional, top-N only, and timeout-protected.
- Place details are hydrated for top-K through the cache.
- Place writes persist authoritative state and emit versioned change events.
- The indexer applies idempotent add/remove updates to the derived geo index.

The two final sequence flows are valuable. They make the design easier to
evaluate than prose alone, and they expose the right operational concerns.

The final design would be stronger with two small additions:

- Name the selected geo-index implementation/policy in the final design, not
  only in options.
- Show the outbox/CDC boundary in the write flow so event publication is not a
  hidden best-effort side effect.

## Concept Introduction and Learning Flow

The concept staging is now excellent for an interview:

- Geohash, S2/quadtree, and H3 appear when the spatial index is introduced.
- Covering set and neighbor expansion appear exactly when boundary correctness
  becomes the problem.
- Adaptive precision appears when density skew is introduced.
- Candidate generation plus ranking appears when the index has solved recall.
- Idempotent derived-index update and rebuild/atomic swap appear when freshness
  becomes the problem.

The traps are also well targeted: 1D lat/lng indexes, only querying one cell,
assuming one neighbor ring is always enough, mixed-precision duplicates,
hydrating every candidate, and calling routing for every candidate.

The learning flow no longer has a major missing concept. The main improvement is
to connect the final selected index policy back through all concepts so the
candidate sees one concrete answer, not only a menu of valid approaches.

## Step-to-Final-Design Coherence

Coherence is strong. Each step introduces a component or rule that appears in
the final design:

- Step 1 motivates replacing scans with an index.
- Step 2 introduces `GeoIndex`.
- Step 3 explains covering sets and exact filtering.
- Step 4 explains adaptive cell precision and hot-region handling.
- Step 5 introduces `Ranker`, `ETA`, and `PlaceCache` hydration boundaries.
- Step 6 introduces `PlaceSvc`, `ChangeQ`, `Indexer`, derived-state rebuild,
  and lag controls.

The old gaps are mostly closed. Final design now includes sequence flows, and
the renderer shows the intended step edges. The remaining coherence issue is
choice specificity: the final design should make the same concrete geo-index
choice that the capacity math assumes.

## Realism Compared With Production Systems

Compared with a production maps or local-search system, the current dataset is
credible for an interview-sized case. It does not over-expand into full text
search, ads, personalization, or route planning, but it acknowledges the
important operational realities of a derived spatial index.

Production details now handled well:

- Event versioning and idempotent index updates.
- Old-cell/new-cell movement.
- Tombstoning and stale index cleanup.
- Dead-letter handling, replay/backfill, shadow rebuild, and atomic swap.
- Queue lag, index age, stale-result rate, and rebuild progress.
- Dense-region sharding, hot-cell splitting, and read replicas.
- ETA/ranker timeout fallback.
- Cache failure fallback for bounded top-K hydration.

Details that should move from optional to first-class if this becomes a
flagship case:

- Transactional outbox or CDC for reliable change event creation.
- Global routing/read-replica strategy for user-to-region and cell-prefix
  ownership.
- Geo-index shard outage behavior and degraded responses.
- Coordinate privacy: log minimization, short retention, access controls, and
  coarse analytics.
- Abuse controls: radius caps, result limits, invalid coordinate rejection, and
  per-client/API-key throttling.

## Dataset and Renderer-Facing Observations

Validated:

- `interview.json` parses as JSON.
- Top-level keys match the expected book-case style, including
  `technologyChoices`.
- `steps[]` exists and the case does not rely on `patternCatalog[]`.
- Step `view.nodes` string references resolve to high-level architecture nodes.
- Step, option, and final-design `view.links` references resolve to existing
  links or valid inline links.
- Step, option, and final-design view links have both endpoints present in the
  local view, so links should not be silently filtered out.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- API sequence participants reference declared participant IDs.
- Final-design flows are present for both search and write paths.

Observations:

- No current renderer-blocking issues found.
- `technologyChoices` uses bare string chips. That is schema-valid; if the case
  should match richer book visuals, run the tech-icon assignment workflow later.
- There are no AI visuals or explainer comic fields. That is optional and not a
  correctness issue.
- Since only `REVIEW.md` is being updated, there is no need to rebuild `docs/`.

## Recommended Edits, Prioritized

### P1: Tighten correctness contracts

- Correct the capacity section's `150 m` cell / `0.5 km` radius / `3x3` example.
- Add open-now metadata and `place_version` to `geo_index.entry_meta`.
- State transactional outbox or CDC as the default way to create change events.

### P2: Strengthen production realism

- Promote privacy, abuse controls, radius caps, and result limits into
  requirements/API/final design rather than leaving them only in follow-ups.
- Add a short global-read strategy: region routing, cell-prefix ownership, read
  replicas, and degraded behavior during a regional index outage.
- Make the final selected geo-index implementation explicit and tie it to the
  capacity numbers.

### P3: Polish the book experience

- Add one concrete fanout threshold example for mixed precision.
- Assign technology icons for `technologyChoices` if visual consistency matters.
- Add AI visuals or an explainer comic only if this case needs the same visual
  treatment as the most polished book datasets.

## What Not To Change

- Do not change the step order. It is the strongest part of the case.
- Keep the naive scan first; it is the right teaching baseline.
- Keep the boundary step before density; correctness should come before
  optimization.
- Keep candidate generation and ranking separate.
- Keep async index maintenance as the default write-path answer.
- Do not expand the case into full-text search, ads, recommendation, or route
  planning. ETA-aware ranking can stay bounded and optional.

## Bottom Line

The recent changes moved this from a good compact case to a strong book-quality
nearby-search interview. The remaining work is targeted: fix one quantitative
cell-covering inconsistency, align the geo-index metadata with the promised hot
path, make event creation atomic, and promote privacy/abuse/global-read details
into the main design. The core teaching path is solid and should be preserved.
