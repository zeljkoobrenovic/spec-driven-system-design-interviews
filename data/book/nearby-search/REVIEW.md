# Review: Nearby Search (Yelp / Maps) - System Design

Reviewed file: `data/book/nearby-search/interview.json`  
Review date: 2026-06-08

## Executive Summary

This is a strong, compact geospatial-search walkthrough. The step order is
natural: start with a naive scan, introduce a spatial index, fix boundary
misses, handle uneven density, separate candidate generation from ranking, and
then close the write path with asynchronous index maintenance. The core
interview signal is clear and the options compare real choices instead of
strawmen.

The dataset is not yet flagship-level because several production claims are
asserted more than they are designed. The capacity section gives labels rather
than work-unit math, the data model does not fully support the advertised
filters and place lifecycle, the boundary section overuses "cell + 8 neighbors"
for a radius that may span many cells, and the index-freshness story needs
event versioning, replay, rebuild, lag, and observability details. There are
also three renderer-facing step diagrams whose referenced links are dropped
because one endpoint is not in the view.

Overall assessment:

| Dimension | Rating | Notes |
|---|---:|---|
| System design soundness | 4.0 / 5 | The geospatial core is right, but capacity math, filter/index state, and freshness mechanics are thin. |
| Production realism | 3.5 / 5 | Good acknowledgement of async indexing and density, but weak on replay, rebuilds, p99 budgets, hot regions, privacy, and observability. |
| Pedagogical flow | 4.3 / 5 | The problem-by-problem progression is clear and interview-friendly. |
| Final design coherence | 4.0 / 5 | The final design integrates the introduced components, but lacks final flows and operational closure. |
| Dataset/rendering fit | 3.8 / 5 | JSON and references mostly validate; three step-view links are filtered out at render time. |

Recommendation: keep the step order and core scope. Improve the dataset by
adding concrete capacity math, tightening boundary/query-covering language,
expanding the place/index schemas, adding operational failure details, and
fixing the dropped diagram links.

## What Works Well

- The dataset teaches the central insight well: radius search needs a spatial
  index so the system looks up a small set of cells instead of scanning all
  places.
- The step sequence exposes one problem at a time: scan cost, boundary misses,
  density skew, ranking, and freshness.
- The geohash/S2/quadtree options are meaningful and have credible trade-offs.
- The ranking step correctly separates cheap recall from richer scoring.
- The write path correctly treats the geo index as derived state maintained
  asynchronously from the authoritative place store.
- The follow-ups are aligned with real extensions: moving objects, ETA-aware
  ranking, re-keying moved places, and dense-city hotspots.

## Highest-Impact Issues

### 1. Capacity is not converted into design constraints

The capacity section lists `~100M` places, `~10K` searches/sec, `~1K` updates/sec,
typical radius, and top-K size. It does not turn those into the numbers that
drive the architecture.

Why it matters: the p99 target of `< 200 ms` depends on candidate count, number
of cells touched, cache hit rate, ranker cost, ETA calls, and index shard load.
Without those estimates, the design cannot justify whether the geo index,
ranker, cache, and store are sized correctly.

Concrete fixes:

- Estimate cells per query for common radii and chosen cell precision.
- Bound candidates per query in dense and sparse areas, before and after
  exact-distance filtering.
- Derive cache and storage pressure: `10K qps * top 20-50` hydrated results,
  plus cache misses to `PlaceDB`.
- Split query volume by hot region because city centers, not global average
  traffic, dominate shard sizing.
- Add a latency budget such as geo-index lookup, filter/rank, ETA fallback,
  hydration, and network overhead.

### 2. The boundary section overstates "target cell + 8 neighbors"

Step 3 says to query the user's cell plus its 8 neighbors. That is useful as a
first explanation, but it is not generally correct for the dataset's stated
`0.5-5 km` radius range or for variable-precision cells.

Why it matters: a radius can span more than one neighbor ring, and S2/H3-style
covering queries usually compute a covering set of cells at one or more levels.
If candidates learn "8 neighbors" as the rule, they will miss larger-radius or
mixed-precision cases.

Concrete fixes:

- Reword the default mechanism as "compute all cells covering the query circle,
  plus enough neighboring cells/rings for the selected precision."
- Keep "cell + 8 neighbors" as a small-radius fixed-grid example, not the
  general algorithm.
- Tie Step 3 to Step 4 by explaining how variable precision changes the cell
  covering logic.
- Add a trap for assuming one neighbor ring always covers the requested radius.

### 3. The API and data model do not fully support the promised filters

The requirements and API promise category, price, and open-now filters. The
`places` table has `category`, `rating`, and `popularity`, but it lacks price,
hours shape, status, tombstones, source metadata, update version, and explicit
fields needed to compute "open now" correctly.

Why it matters: filtering is on the hot read path. If open-now and price require
expensive detail hydration before ranking, the design loses its bounded
candidate-cost story.

Concrete fixes:

- Add fields or tables for `price_level`, `status`, `timezone`, normalized
  opening hours, temporary closures, and `updated_at`/`version`.
- Model delete/remove with a status or tombstone so stale geo-index entries can
  be filtered safely while async cleanup catches up.
- Add old-cell/new-cell or previous-location state to the change event so moves
  can remove the old index entry reliably.
- Clarify which filters are stored in the geo index versus applied after
  candidate fetch.
- Add `PUT/PATCH /v1/places/{id}` and `DELETE /v1/places/{id}` or state that
  `POST /v1/places` is an upsert with idempotency/version semantics.

### 4. Async index freshness needs operational mechanics

Step 6 correctly chooses an async change queue and says duplicated or lost
events need idempotent upserts and replay. The design stops before showing the
mechanisms.

Why it matters: the geo index is derived state. In production, correctness comes
from replayability, idempotent event handling, backfills, lag monitoring, and
repair jobs, not just from having a queue.

Concrete fixes:

- Add an event shape with `place_id`, `event_id`, `place_version`,
  `old_cell`, `new_cell`, operation type, and event time.
- Define idempotent index updates keyed by `(place_id, version)` or equivalent.
- Add dead-letter handling and replay/backfill from `PlaceDB`.
- Add lag SLOs and metrics: queue lag, index age by region, stale-result rate,
  cell candidate count, and rebuild progress.
- Explain how a full index rebuild swaps into service without corrupting reads.

### 5. The p99 story does not bound ranking and ETA cost

The final design includes a Ranking Service and optional Routing / ETA Service,
but the latency strategy is too open-ended for `< 200 ms`.

Why it matters: per-candidate ETA calls or slow model inference can dominate the
query path. A candidate may say "call routing for every result" and accidentally
turn a geo-search problem into a slow fanout service.

Concrete fixes:

- Rank in stages: cheap geo/filter score first, then expensive ETA or ML only
  for a small top-N.
- Add timeout/fallback behavior for the ETA service.
- State whether travel distance is precomputed, cached, approximated, or only
  used when the UI asks for directions.
- Track ranker and ETA p95/p99 separately from overall search p99.

### 6. Three step diagrams contain links that the renderer drops

The JSON validates that the link IDs exist, but `graphViewToMermaid` only emits
a link when both endpoints are listed in `view.nodes`. Three step views violate
that rule:

- `naive.view.links` references `place-placedb` (`PlaceSvc -> PlaceDB`) but the
  view nodes are `Client`, `LB`, `SearchSvc`, and `PlaceDB`. The intended edge
  is probably `SearchSvc -> PlaceDB` for a scan.
- `geohash.view.links` references `lb-search` (`LB -> SearchSvc`) while `LB` is
  omitted from the view.
- `indexing.view.links` references `lb-place` (`LB -> PlaceSvc`) while `LB` is
  omitted from the view.

Why it matters: those edges disappear in the rendered diagrams. In `naive`, the
database scan is especially important pedagogically, so the missing edge weakens
the first step.

Concrete fixes:

- For `naive`, add an inline link from `SearchSvc` to `PlaceDB` or add a
  high-level `search-placedb` link.
- For `geohash`, either add `LB` to `view.nodes` or remove the `lb-search` link
  if the step is meant to focus only on the search/index/cache path.
- For `indexing`, either add `LB` and `client-lb`, or remove `Client` and the
  `lb-place` link from the local view.

## System Design Soundness

The functional requirements cover the right base behavior: radius query,
filters, ranking, updates, and details. The non-functional requirements also
name the important axes: read-heavy traffic, low latency, global scale,
eventual consistency, and boundary correctness.

The main issue is that the design does not yet turn these requirements into
operational constraints. For a nearby-search interview, the useful math is not
only "100M places"; it is how many cells a query touches, how many candidates
those cells return in Manhattan versus a rural region, how many cache reads the
top-K hydration creates, and how much index lag is acceptable before users
notice stale or missing places.

The architecture itself is directionally correct. `GeoIndex`, `SearchSvc`,
`Ranker`, `PlaceCache`, `PlaceDB`, `ChangeQ`, and `Indexer` are the right
components for this scope. The design should be strengthened around:

- Region and cell-prefix sharding, including hot-cell splitting and read
  replicas.
- Cache invalidation and stale detail handling after place updates.
- Partial failure behavior when `GeoIndex`, `Ranker`, `ETA`, or `PlaceCache`
  times out.
- Rebuild and reconciliation flows for derived index state.
- User-location privacy, retention, logging minimization, and rate limiting by
  client or API key.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Scan and Compute Distance

This is the right opening. It makes the complexity problem obvious and gives
the candidate a baseline to reject.

The diagram should be fixed because the scan edge is currently dropped. The
view uses a `PlaceSvc -> PlaceDB` link but does not include `PlaceSvc`, and the
actual pedagogical edge is `SearchSvc -> PlaceDB`.

### Step 2: Geospatial Index: Geohash / S2 Cells

This is the core step and is generally strong. The options give real choices:
geohash prefix index, S2 cells, and quadtree. The explanation correctly teaches
locality-preserving cell IDs and cell-to-place-id lookup.

Two improvements would raise the quality:

- Add a little more about why H3 appears in probe links but not in the option
  set, or include it as a named variant in the S2/geospatial-index discussion.
- Clarify where category/price/open-now filter fields live if the geo index is
  only `cell -> place_ids`.

### Step 3: Handle Cell Boundaries and the Radius

This step teaches the classic correctness problem and includes the necessary
exact-distance filter. That is good.

The main fix is wording: "target cell + 8 neighbors" should be presented as a
fixed-grid small-radius example, not the general covering algorithm. The step
should lead candidates toward computing a covering set and then exact-filtering
the over-fetch.

### Step 4: Adapt to Uneven Density

The step correctly introduces the city-versus-rural problem. The options are
useful and not strawmen: variable precision, fixed cell size, and expanding
rings each teach a real trade-off.

The missing piece is concrete query logic for mixed precision. If dense and
sparse regions use different cell sizes, the system needs rules for selecting
levels, avoiding duplicate candidates across parent/child cells, and capping
fanout.

### Step 5: Rank and Filter Candidates

This step is well placed and important. Candidate generation plus ranking is
the right search architecture.

The design should be stricter about cost. Apply cheap filters before ranking,
but also state which filters are available without hydrating every candidate.
Use ETA or ML only for a bounded top-N with timeout fallback. Otherwise the
optional `ETA` node can silently break the p99 target.

### Step 6: Keep the Index Fresh (Async Write Path)

The async index-update choice is correct for read-heavy nearby search. The step
also names the right trade-off: the index may lag writes, and duplicate/lost
events need idempotency and replay.

This should be expanded with the event and repair mechanics. A production
candidate should be able to explain what happens when the indexer falls behind,
when an event is replayed, when a place moves cells, and when the index must be
rebuilt from the authoritative store.

## Final Design Review

The final design coherently combines the query path and write path:

- Search resolves a radius into cells.
- Geo index returns candidates.
- Exact filter and ranking produce top-K.
- Place cache hydrates details.
- Place writes emit change events.
- Indexer updates derived geo-index state asynchronously.

The final description is accurate but high level. It would benefit from
`finalDesign.flows[]` showing two end-to-end flows:

- Search flow: request -> cell covering -> candidate fetch -> exact filter ->
  rank -> hydrate -> response.
- Write flow: create/update/delete -> authoritative write -> event -> indexer
  idempotent remove/add -> query-visible update.

Those flows would also expose the operational concerns that are currently only
mentioned in prose.

## Concept Introduction and Learning Flow

The concepts are introduced at the right time: geohash/S2, neighbor expansion,
adaptive precision, and candidate generation plus ranking. The pattern list is
useful and the interview script matches the actual teaching path.

The learning flow would be stronger with:

- A concept or trap for "covering set versus one neighbor ring."
- A concept for "derived index rebuild/replay."
- A trap for "calling routing/ETA for every candidate."
- More failure drills outside the indexing step.

## Step-to-Final-Design Coherence

The final design uses the components introduced by the steps, so the coherence
is good. The weakest transitions are:

- Step 3 to Step 4: fixed neighbor expansion does not naturally transition to
  mixed-precision covering.
- Step 4 to Step 5: density bounds candidate count, but the ranking/filter data
  placement is not specified.
- Step 6 to final design: async index maintenance appears, but replay,
  reconciliation, rebuild, and lag controls do not make it into the final
  design.

## Realism Compared With Production Systems

Compared with production map/search systems, this dataset has the right
high-level shape but should be more explicit about operating the index.

Important missing or underdeveloped details:

- Index lag SLOs and dashboards by region/cell prefix.
- Full and partial index rebuilds from the source of truth.
- Idempotent events, event ordering, old-cell removal, tombstones, and
  dead-letter queues.
- Hot-city shard handling beyond "finer cells + dedicated shard + replicas."
- Cache invalidation and stale detail fallback.
- Query validation, radius caps, abuse protection, and API rate limits.
- Location privacy: minimizing logs, retention, and access controls for user
  coordinates.
- Ranking observability: score distribution, quality metrics, latency, and
  fallback when optional services fail.

## Dataset and Renderer-Facing Observations

Validated:

- `interview.json` parses as JSON.
- Top-level keys match the expected dataset style for this repo.
- `steps[]` exists and `patternCatalog[]` is not required.
- Step `view.nodes` string references resolve to high-level architecture nodes.
- Step `view.links` string references resolve to high-level architecture links.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- API and step sequence participants reference declared participant IDs.
- Option-level views and final-design view links do not have missing endpoints.

Issues:

- `naive`, `geohash`, and `indexing` have step-level view links that are
  filtered out because one endpoint is omitted from `view.nodes`.
- The dataset has no `technologyChoices` section. That field is optional, but
  this book case would benefit from a technology-choice wrap-up comparing
  PostGIS, Elasticsearch/OpenSearch geo queries, S2/H3 plus KV stores,
  Redis/Valkey geo structures, Bigtable/DynamoDB-style cell indexes, and
  managed cloud map/search services.
- There are no AI visuals or explainer comic fields. That is optional and not a
  correctness issue.

## Recommended Edits, Prioritized

### P1: Make the core design more defensible

- Add capacity math for cell fanout, candidate counts, cache reads, shard load,
  storage size, and latency budget.
- Reword Step 3 around computed covering cells; keep 8-neighbor expansion only
  as a simple example.
- Expand the place and geo-index data models so filters, lifecycle, and moves
  are represented explicitly.
- Add index event schema, idempotency, replay, rebuild, and lag observability.
- Fix the three dropped diagram links.

### P2: Improve production realism and final-design closure

- Add final-design query and write flows.
- Add failure drills for geo-index outage, cache outage, ranker timeout, ETA
  timeout, and stale index rebuild.
- Add timeout/fallback behavior for ranking and ETA.
- Add query validation, radius caps, API abuse controls, and location privacy
  notes.
- Add cache invalidation and stale-detail handling.

### P3: Polish the learning material

- Add a trap for assuming one neighbor ring always covers the radius.
- Add a trap for hydrating every candidate before filtering/ranking.
- Clarify the role of H3 or remove it from probe emphasis if the case only
  wants geohash/S2/quadtree.
- Add `technologyChoices` if this should match richer book-group cases.

## What Not To Change

- Do not change the step order. It is the strongest part of the dataset.
- Do not over-expand the scope into full text search, ads, recommendation, or
  route planning. ETA-aware ranking can stay optional.
- Keep the naive first step; it is a useful teaching baseline.
- Keep async index maintenance as the default write-path choice.
- Keep the final design compact, but make the operational details visible.

## Bottom Line

This is a credible and teachable nearby-search interview. It already explains
the core geospatial idea well. To reach flagship quality, it needs more
quantitative grounding, a fuller filter/index data model, stronger async-index
operations, and a few renderer fixes so the diagrams show the intended edges.
