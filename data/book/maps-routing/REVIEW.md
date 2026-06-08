# Review: Google Maps Routing - System Design

Reviewed file: `data/book/maps-routing/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a clear, compact routing-and-map-serving case. It teaches the main
interview arc well: naive graph search fails on a continental road network,
road data becomes a weighted directed graph, preprocessing makes shortest-path
queries fast, tiles are better served as mostly static CDN content, live traffic
comes from probe aggregation, and scale is handled through geographic
partitioning plus offline graph/index rebuilds.

The dataset is structurally healthy. The JSON parses, generated architecture
views use structured `view` objects, step and option link references resolve,
sequence participants resolve, `satisfies[*].steps[*]` points to real step IDs,
and there are no raw Mermaid `diagram` fields in step/final-design surfaces.

The main weakness is that the production details are thinner than the topic
deserves. Capacity is qualitative, the route API and route data model do not
yet support the full stated behavior, live traffic is treated as a simple
multiplier store, and region partitioning/index updates need a more precise
operating model. This is a good book case, but not yet a flagship one.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 3.9 / 5 | Correct core architecture; capacity, route schema, and dynamic-weight details need more precision. |
| Production realism | 3.5 / 5 | Strong directionally, but light on privacy, map matching, closures, versioning, rollout, and observability. |
| Pedagogical flow | 4.2 / 5 | The step progression is interview-friendly and easy to follow. |
| Final design coherence | 4.0 / 5 | Final design integrates the chosen components, but several promised behaviors remain prose-only. |
| Dataset/rendering fit | 4.7 / 5 | JSON and references validate; no renderer-facing blockers found. |

Recommendation: keep the current step order and compact narrative. The next edit
should add quantitative capacity assumptions, make the API/data model support
turn-by-turn and traffic-aware routing explicitly, deepen the live-traffic and
graph-update model, and make regional partitioning/operations concrete enough
for a senior/staff interview answer.

## What Works Well

- The opening baseline is strong. Step 1 correctly starts with Dijkstra/A* and
  uses the continental-scale latency failure to motivate preprocessing.
- The graph-model step introduces the right core abstraction: directed weighted
  edges, one-way streets, turn restrictions/penalties, and geometry expansion.
- The preprocessing section teaches the most important maps-routing insight:
  pay offline build/storage cost so online route queries touch a small fraction
  of the road graph.
- Step 3a gives a useful comparison between contraction hierarchies, hub
  labeling, and ALT/A*-with-landmarks.
- Tile serving is separated from routing, which prevents the common mistake of
  putting all "maps" behavior on the route hot path.
- The traffic step explains the desired default: aggregate probes into live
  edge speeds and apply them at query time instead of rebuilding the whole
  index every few minutes.
- The final design ties the major components together: API gateway, routing
  service, graph store, CH index, geocoder, tile service/store/CDN, probe
  stream, traffic aggregator, and traffic service.
- The wrap-up traceability is complete at a high level: every listed functional
  and non-functional requirement maps to at least one step.
- Renderer-facing structure is clean: structured views, valid references,
  valid sequence messages, and no generated-doc changes required for the review.

## Highest-Impact Issues

### 1. Capacity is too qualitative for a routing system

The capacity section uses labels like "high", "massive", and "minutes". Those
are directionally correct, but they do not force design decisions. A maps
routing interview needs at least rough numbers for route QPS, tile QPS, graph
size, probe ingestion, edge-speed updates, p99 latency, and storage/index size.

Why it matters: the dataset says the goal is millisecond routing on hundreds of
millions of nodes. Without numbers, the candidate cannot reason about memory
fit, region shard count, index replication, cache hit rates, traffic aggregation
fanout, or whether a route request can afford geocoding, CH query, traffic
overlay, and geometry expansion in one synchronous path.

Concrete fixes:

- Replace "Route QPS: high" with an example such as `50k route requests/sec`
  globally, `5k/sec` in a hot region, and a `p99 < 100 ms` budget split across
  gateway, geocoding/snap, index query, traffic lookup, and geometry expansion.
- Quantify tile load separately, for example `1M+ tile reads/sec`, `95-99% CDN
  hit rate`, and origin QPS after cache misses.
- Quantify probe ingestion: devices/sec, events/sec, aggregation window, number
  of edge-speed updates/minute, and how sparse roads fall back to historical
  speeds.
- Give a rough graph/index size: nodes, directed edges, bytes per edge, CH
  shortcut growth, per-region shard size, and replica count.
- State a freshness SLO for graph data separately from traffic: traffic in
  `2-5 min`, incidents/closures in `seconds-minutes`, base-road rebuilds in
  `hours-days`.

### 2. The API and data model do not fully support the stated route behavior

The requirements promise route geometry, distance, ETA, and turn-by-turn. The
current `GET /v1/route` response shows distance, ETA, and geometry only. The
data model also lacks several fields that the prose depends on: stable
`edge_id` in `road_graph.edges`, route-leg/step/maneuver output, turn
restrictions, shortcut-unpacking metadata, graph/index version, region ID, and
time-dependent speed fields.

Why it matters: routing correctness lives in these details. A system can find a
node path but still fail product requirements if it cannot unpack shortcuts into
road geometry, produce maneuvers, honor turn restrictions, avoid tolls/highways,
or compute ETAs against the same graph/index/traffic versions used for the
selected path.

Concrete fixes:

- Extend `/v1/route` request parameters with `departure_time`,
  `traffic_model`, `alternatives`, `waypoints`, `avoid`, `locale`, and a
  bounded response-shape option.
- Extend the response with `route_id`, `polyline`, `legs[]`, `steps[]`,
  `maneuver`, `duration`, `duration_in_traffic`, `warnings`, and
  `graph_version` / `traffic_version`.
- Add `edge_id`, `from_node`, `to_node`, `geometry_ref`, `region_id`,
  `turn_restrictions`, `access_flags`, and `road_class` to the road-graph model.
- Add shortcut unpacking to `ch_index`, such as skipped edge references or an
  unpack tree, so the final route can become geometry and turn-by-turn steps.
- Make `edge_speed` versioned/time-bucketed rather than a single `live_speed`
  row if the design wants departure-time-aware ETAs.

### 3. Live traffic is underspecified for production

Step 5 correctly says that live traffic should not trigger a full CH rebuild.
However, the dataset compresses the hard production work into "dynamic edge
weights at query time". It does not explain map matching, noisy probe filtering,
privacy controls, sparse-road fallback, traffic smoothing, incident/closure
overrides, or the exact way dynamic weights interact with a precomputed
shortest-path index.

Why it matters: static CH assumes fixed weights. Real traffic can change edge
ordering and route optimality. A credible answer needs to say whether the
system uses customizable CH, time-dependent CH, live-weight overlays on
candidate corridors, local A* repair, or bounded suboptimality for very fresh
traffic.

Concrete fixes:

- Add a traffic data model with `edge_id`, speed buckets, confidence,
  sample_count, source, updated_at, historical fallback, and incident/closure
  override fields.
- Add a short map-matching note: probes are snapped to candidate road segments,
  filtered for GPS quality, deduped by anonymized device/session, then
  aggregated with privacy-preserving retention.
- Clarify the routing algorithm under live weights: customizable CH update
  phase, time-dependent CH, corridor reranking, or a hybrid CH-plus-local-A*
  approach.
- State what happens when traffic is stale or missing: fall back to historical
  speed by time-of-day and road class, not only free-flow speed.
- Add privacy as a first-class non-functional requirement: opt-in/consent,
  short retention, coarse analytics, access controls, and no raw trace exposure
  to operators.

### 4. Graph updates need a stronger versioning and rollout story

Step 7 says the graph/index is rebuilt offline and swapped atomically. That is
the right default for slow road-data changes, but maps systems also need faster
updates for closures, restrictions, incidents, construction, and bad map edits.
The dataset does not yet define graph/index versions, compatibility between
graph and CH artifacts, canary rollout, rollback, or how a route request stays
consistent while artifacts are changing.

Why it matters: a stale or mismatched graph/index can produce invalid routes.
Atomic swap is necessary, but the candidate should also show how derived
artifacts are built, validated, rolled out, observed, and rolled back.

Concrete fixes:

- Add `graph_version`, `index_version`, and `tile_version` fields to relevant
  data-model entities and response metadata.
- Describe the build pipeline: ingest map changes, validate topology, build CH,
  run route-regression tests, publish immutable artifacts, canary by region, and
  roll back on bad route metrics.
- Separate urgent overlays from base rebuilds: closures and restrictions should
  be pushed in minutes through an overlay/restriction store, while base graph
  and CH rebuilds can remain slower.
- State that a route request pins one graph/index version through query,
  shortcut unpacking, and geometry expansion.
- Add a failure drill for a bad graph release or partially published index.

### 5. Region partitioning is plausible but too hand-wavy

Step 6 says most routes are local and long routes use high-rank CH shortcuts
spanning regions. That is a good interview-level intuition, but the dataset does
not define boundary handling, overlay graphs, duplicated border nodes,
cross-region route stitching, region failover, or hot metro partitioning.

Why it matters: geographic sharding is one of the hardest parts of a continental
routing service. If the design simply says "partition by region", it hides the
problem that routes regularly cross boundaries and dense metros can dominate
load.

Concrete fixes:

- Add an overlay/border graph concept: each region owns local graph data,
  boundary vertices are duplicated or coordinated, and long routes use a
  higher-level inter-region graph before local unpacking.
- Explain how a cross-region query is planned without synchronous fanout to
  every region.
- Discuss hot-region splitting for dense cities and why administrative borders
  are often worse than traffic/topology-aware partitions.
- Add cache keys that include origin/destination cells, mode, avoid flags, graph
  version, and traffic freshness bucket.
- Add a regional degradation story: what routes can still be served if one
  region's graph shard, traffic feed, or tile origin is unavailable.

## System Design Soundness

### Requirements and Capacity

The requirements cover the right product surface: route computation, geometry
and ETA, tiles, live traffic, and geocoding. The non-functional requirements
name the right broad constraints: low latency, continental scale, CDN tiles,
fresh traffic, and read-heavy workloads.

The weak point is capacity. The current numbers are not wrong, but they are not
actionable. This case should convert "high route QPS" and "massive tile reads"
into route-hot-path budgets, edge-speed update rates, artifact sizes, and shard
counts. That would make the later choices around CH, CDN, region partitioning,
and traffic freshness more defensible.

### API

The API is intentionally compact, which helps readability. It is not yet strong
enough for the stated behavior. `/v1/route` should expose departure time,
traffic behavior, alternatives, waypoints, avoid flags, and bounded response
size. The response should include turn-by-turn structures, route legs, encoded
polyline/geometry references, traffic-aware duration, warnings, and version
metadata.

`/v1/tiles/{z}/{x}/{y}` is acceptable as the minimal tile shape, but a production
case should mention style/version, raster vs vector content type, cache headers,
and CDN URL versioning. `/v1/geocode` is present, but the dataset should either
scope geocoding as a dependency or add the index/model used to resolve
addresses and snap points to graph nodes.

### Data Model

The three current entities are the right starting point: road graph, CH index,
and edge speed. They are too thin for the behavior promised by the rest of the
case.

The road graph should expose stable edge IDs, directed from/to nodes, geometry
references, turn restrictions, access/avoid flags, region ownership, and version.
The CH index should store shortcut-unpacking metadata and version/build
metadata. The traffic model should carry confidence, sample count, historical
fallback, time buckets, incident overrides, and freshness. If geocoding stays in
scope, add a small geocode/place index or explicitly say it is provided by an
external subsystem.

### Architecture

The high-level architecture is coherent. The routing service reads the graph,
CH index, geocoder, and traffic service; tiles are backed by object storage and
CDN; probes flow through a stream and aggregator into traffic state.

The missing architecture surfaces are operational: build pipeline, artifact
versioning, traffic quality controls, privacy boundary, observability, and
regional failover. These do not need to dominate the diagram, but they should be
visible enough that the final design feels production-operated rather than only
algorithmically correct.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Dijkstra/A* Over the Whole Graph Per Request

This is the right opener. It gives the candidate a familiar baseline and then
explains why it breaks at continental scale. The step would be stronger with one
rough number: nodes settled or latency for a long route under naive Dijkstra/A*
versus a CH query.

### Step 2: Model Roads as a Weighted Graph

The graph abstraction is introduced well. It mentions directed edges, one-way
streets, turn restrictions, and geometry. The next edit should make those
details visible in the data model so turn-by-turn output and traffic edge-speed
rows have concrete fields to attach to.

### Step 3: Make Shortest-Path Fast with Preprocessing

This is the key teaching step and it is effective. It explains the offline
build/online query trade-off clearly. Add a note that CH shortcuts must be
unpacked back into base edges for route geometry and maneuvers, otherwise the
candidate can accidentally stop at "shortest distance" instead of "usable
route".

### Step 3a: Preprocessing Choices: CH vs Hub Labeling vs A*

The option comparison is useful and not a strawman. The CH default is
reasonable. This step should be the place where dynamic traffic compatibility is
made precise: plain CH, customizable CH, time-dependent CH, hub-label storage
cost, and ALT's behavior under frequent weight changes.

### Step 4: Serving Map Tiles

This is a good separation of concerns. The options cover CDN pre-rendering,
client-rendered vector tiles, and origin rendering. Add cache/version details:
style version in the URL, immutable tile assets, cache-control, invalidation by
publishing a new tile version, and origin protection when a popular area misses.

### Step 5: Live Traffic from GPS Probes

The step has the right default choice. It needs the most production depth:
probe consent/anonymization, map matching, noisy data filtering, speed
confidence, sparse coverage, incidents/closures, historical fallback, and the
specific dynamic-weight routing algorithm. This would also be a good place for
a sequence flow that shows probe ingestion separately from route-time traffic
lookups.

### Step 6: Scaling: Region Partitioning

The locality argument is good. The step currently hides boundary and overlay
complexity. Add region border nodes, an inter-region/overlay graph, cross-region
planning, hot-city splits, and failure behavior when a regional shard is stale
or unavailable.

### Step 7: Graph Updates, Caching, and Reliability

This is the correct final architecture step, but it is too compressed. It should
name artifact versions, build validation, canary rollout, rollback, urgent
closure overlays, cache keys, route regression tests, freshness metrics, and
traffic fallback. A small failure drill for "bad graph release" would make this
step much more interview-realistic.

## Final Design Review

The final design accurately integrates the selected components from the steps.
It states the important defaults: weighted directed road graph, offline-built CH
index, stateless routing service, geometry expansion from the graph store, live
probe-derived edge speeds, CDN-backed tiles, geo partitioning, atomic graph/index
swap, and fallback to free-flow weights when traffic lags.

The final design should become more explicit about version consistency and
operational boundaries. A polished final answer would say:

- Route requests pin a graph/index version and use traffic speeds from a bounded
  freshness window.
- Shortcuts are unpacked into base edges before returning geometry and
  turn-by-turn maneuvers.
- Closures/restrictions use a fast overlay path, while base graph/CH artifacts
  are rebuilt and canaried offline.
- Regional routing uses local shards plus an overlay/border graph for long
  routes.
- Tiles are versioned immutable assets served by CDN, with origin protection and
  style/content-type choices.
- Raw GPS probes are short-lived, privacy-controlled data; the routing service
  reads only aggregated edge-speed state.

## Concept Introduction and Learning Flow

The concepts are introduced in a good order: road graph, preprocessing,
preprocessing trade-off triangle, tile pyramid/CDN, probe-based traffic, geo
region sharding, and dynamic edge weights. That flow is easy for a candidate to
replay in an interview.

The missing concept is artifact/version management. In this domain, graph
versions, index versions, tile versions, and traffic freshness are not
operations-only details; they are part of correctness. Add a concept card or
Step 7 concept for immutable map artifacts and versioned rollout.

## Step-to-Final-Design Coherence

The final design includes every major component introduced in the steps. The
coherence is good:

- Step 1 motivates why naive online search is unacceptable.
- Step 2 introduces `GraphStore` and `Geocode`.
- Step 3 and 3a introduce `CH` as the default online index.
- Step 4 introduces `TileSvc`, `TileStore`, and `CDN`.
- Step 5 introduces `ProbeStream`, `TrafficAgg`, and `TrafficSvc`.
- Step 6 explains why graph, index, tiles, and traffic need regional locality.
- Step 7 explains offline rebuilds, caching, replication, and degradation.

The largest coherence gap is between the promised product outputs and the data
shown in final design. Geometry, turn-by-turn, traffic-aware duration,
alternatives, closures, and route versioning should be visible either in the API
or data model so the final design can claim them without relying only on prose.

## Realism Compared With Production Systems

The design is directionally similar to real routing systems: static map graph,
preprocessed route index, CDN tiles, live traffic aggregation, regional
partitioning, and offline artifact rebuilds. The realism gaps are mostly in the
operating details:

- Real route APIs expose route options, departure-time semantics, alternatives,
  avoid flags, waypoints, route legs, warnings, and encoded polylines.
- Real road graphs include turn restrictions, access rules, closures, geometry,
  versions, and map-matching concerns.
- Real traffic systems spend substantial effort on privacy, probe quality,
  confidence scoring, sparse-road fallback, incidents, and freshness alerts.
- Real map releases are versioned artifacts with validation, canary rollout,
  rollback, and route-regression test suites.
- Real region partitioning uses border/overlay graphs and hot-area splits rather
  than simple administrative partitions.
- Real map tile serving depends on immutable versioned URLs, cache headers,
  content negotiation, and origin protection.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level structure is valid for this project: requirements, capacity, API,
  data model, high-level architecture, steps, final design, satisfies, script,
  level variants, follow-ups, and probe links are present.
- No raw Mermaid `diagram` fields were found in step, option, flow, or final
  design surfaces.
- Step `view.nodes` and string `view.links` references resolve against
  `highLevelArchitecture`.
- Option-local nodes and inline links are used for alternate designs such as
  `HubLabels`, `Landmarks`, `VectorStore`, and `Preproc`; this is supported by
  the renderer.
- Flow sequence messages reference declared participants.
- `satisfies.functional[*].steps[*]` and
  `satisfies.nonFunctional[*].steps[*]` resolve to real step IDs.
- Step-level `probeLinks` reference known links in `toProbeFurther`.
- No generated `docs/` rebuild is needed for this review-only change.

Optional renderer/content polish:

- Add `aiVisual` assets if this case should match the most visual flagship
  datasets.
- Add one or two more sequence flows: route query with geocode/CH/traffic/graph
  expansion, and offline graph/index build plus atomic publish.
- If the decision-tree overview feels dense, the sub-step `3a` is correctly
  modeled as a child of `preprocess`; keep that hierarchy.

## Recommended Edits, Prioritized

### P1: Make capacity quantitative and tied to work units

Add route QPS, tile QPS, probe ingestion, graph/index size, edge-speed update
rate, latency budget, region shard sizing, and cache hit-rate assumptions.

### P1: Align API and data model with route outputs

Add route options, turn-by-turn response fields, version metadata, road-edge
IDs, geometry references, turn restrictions, shortcut unpacking, and traffic
speed buckets.

### P1: Deepen live-traffic correctness and privacy

Add map matching, quality/confidence, historical fallback, incidents/closures,
privacy/retention, and the exact algorithmic approach for using dynamic weights
with preprocessed routing.

### P2: Add graph/index/tile versioning and rollout mechanics

Represent immutable artifacts, build validation, canary rollout, rollback,
urgent overlays, and route-regression tests in Step 7 and the final design.

### P2: Make region partitioning operationally concrete

Add border nodes, overlay/inter-region graph, cross-region route stitching,
hot-metro splitting, and regional degradation behavior.

### P2: Add route and build sequence flows

The API route sequence exists, but the step walkthrough would benefit from a
main route-query flow and an offline build/publish flow.

### P3: Improve tile-serving details

Add tile version/style, vector vs raster content-type, cache headers, immutable
URLs, and CDN origin protection.

### P3: Decide how much geocoding is in scope

Either add a small geocode/place-index model and snapping behavior, or state
that geocoding is an external dependency and the routing service receives graph
node IDs after resolution.

## What Not To Change

- Keep the baseline-to-preprocessing teaching arc. It is the strongest part of
  the case.
- Keep the separation between routing, tiles, and traffic. Combining them would
  make the design harder to teach.
- Keep CH as the default preprocessing choice; it is a defensible interview
  default when paired with the right live-traffic caveats.
- Keep the `preprocessing-choice` sub-step under preprocessing. It is a good
  way to teach alternatives without disrupting the main spine.
- Keep the final design compact. Add missing contracts through targeted fields,
  flows, and captions rather than turning the case into a routing textbook.

## Bottom Line

The dataset is a good, readable maps-routing walkthrough with clean renderer
structure and a coherent final design. To make it production-grade, the next
revision should quantify capacity, make route outputs and graph/index versions
explicit, and deepen live traffic, graph updates, region partitioning, and
privacy. Those changes would turn a solid overview into a strong senior/staff
system-design case.
