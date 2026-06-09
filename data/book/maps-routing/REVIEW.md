# Review: Google Maps Routing - System Design

Reviewed file: `data/book/maps-routing/interview.json`
Review date: 2026-06-08

## Executive Summary

The recent revision materially strengthens this case. The dataset now has
quantitative capacity assumptions, a route API that exposes turn-by-turn output
and graph/traffic versions, a road graph model with stable edge IDs and shortcut
unpacking, a traffic model with confidence and historical fallback, privacy as a
non-functional requirement, region overlay language, and a versioned
build/canary/rollback story. Those changes address most of the previous review's
P1 findings.

This is now a strong book case. It teaches the right routing arc: start with
Dijkstra/A*, expose why continental routing cannot do that per request, model
roads as a weighted directed graph, add contraction-hierarchy preprocessing,
separate map tiles onto CDN-backed static assets, layer live traffic through
probe aggregation, then scale with geographic partitioning and immutable
artifact rollout.

The remaining gaps are narrower and more production-facing. The final
architecture still hides several stateful subsystems that the prose depends on:
traffic-speed storage, urgent closure/restriction overlays, the offline build
pipeline, geocode/place index state, and the inter-region overlay graph. The
traffic step names several ways to combine live weights with precomputed
shortest-path indexes, but the final design should commit to one default and
state the correctness/latency trade-off. Region partitioning is much clearer in
prose now, but not yet represented as a concrete model or diagram component.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.4 / 5 | Correct core design with much better API, capacity, graph, traffic, and rollout detail. |
| Production realism | 4.2 / 5 | Stronger on privacy, freshness, canary, rollback, and overlays; still missing a few stateful operational components. |
| Pedagogical flow | 4.5 / 5 | Clean sequence from baseline to graph, preprocessing, tiles, traffic, sharding, and ops. |
| Final design coherence | 4.3 / 5 | Most decisions converge well; final architecture should show the stores/pipelines behind the prose. |
| Dataset/rendering fit | 4.7 / 5 | JSON and references validate; one semantic naming issue in the ops flow should be cleaned up. |

Recommendation: keep the current structure and most of the new content. The
next revision should make hidden state explicit, choose a concrete live-traffic
routing strategy, and represent region overlays/build artifacts as first-class
architecture elements rather than prose-only details.

## What Works Well

- Capacity is now actionable: route QPS, tile reads, probe ingestion, edge-speed
  update rate, latency budget, graph/index sizing, and freshness cadences are
  all present.
- The route API now supports the promised product behavior: departure time,
  traffic model, alternatives, waypoints, avoid flags, locale, route ID,
  polyline, legs, steps, maneuvers, traffic-aware duration, warnings, and
  graph/traffic versions.
- The tile API now models immutable style/version paths and cache headers, which
  fits CDN reality much better than a bare z/x/y endpoint.
- The data model now exposes stable `edge_id`, directed edges, geometry
  references, turn restrictions, access flags, region ownership, CH shortcut
  unpacking, graph/index versions, traffic confidence, sample count, historical
  fallback, incident override, and freshness.
- Step 1 now quantifies the baseline failure: full-graph Dijkstra can settle
  tens of millions of nodes, while CH queries touch only thousands.
- Step 3 correctly explains that CH returns shortcuts and that a route must be
  unpacked into base edges before geometry and maneuvers can be returned.
- Step 5 is much stronger: it now covers map matching, noisy probe filtering,
  anonymization, sparse-road fallback, incidents/closures, and why live traffic
  should not trigger full re-preprocessing.
- Step 6 now teaches the real partitioning issue: border vertices, overlay
  graph, hot metro splits, no fanout to every region, and regional degradation.
- Step 7 now includes immutable graph/index/tile artifacts, route regression,
  canary rollout, rollback, urgent overlays, cache keys, and failure drills.
- The final design now integrates version pinning, shortcut unpacking,
  historical fallback, privacy boundaries, fast closure overlays, tile
  versioning, and inter-region overlay routing.

## Highest-Impact Issues

### 1. Several production-critical stateful components are still prose-only

The architecture diagram has `TrafficSvc` as a stateless service and
`TrafficAgg` writing directly to it, but the dataset now claims roughly 1-5M
edge-speed updates per minute. That needs an explicit stateful traffic store or
regional cache. Similarly, urgent closures/restrictions, graph/index build
artifacts, route-regression/canary state, geocode/place indexes, and the
inter-region overlay graph are important to the design but not visible as
components.

Why it matters: the prose is production-realistic, but the diagram currently
makes the system look more stateless than it is. A candidate copying the diagram
could omit the very stores that make freshness, rollback, probe aggregation,
and cross-region routing operational.

Concrete fixes:

- Add a `TrafficStore` or regional edge-speed cache between `TrafficAgg`,
  `TrafficSvc`, and `RouteSvc`; include read/write/freshness expectations.
- Add a `RestrictionOverlay` or `IncidentStore` for closures, turn bans, and
  temporary penalties that bypass the slow base-graph rebuild cadence.
- Add a `BuildPipeline` node for graph validation, CH build, route regression,
  artifact publish, canary, and rollback.
- Add a `GeocodeIndex` or `PlaceIndex` if geocoding remains a functional
  requirement rather than an external dependency.
- Add an `OverlayGraph`/`RegionIndex` concept for border vertices and
  inter-region high-rank shortcuts.

### 2. Live traffic names multiple algorithms but does not pick a final default

Step 5 now honestly states that plain CH assumes fixed weights and lists
customizable CH, time-dependent CH, and CH-plus-local-A* corridor repair as
practical options. That is the right nuance. The final design, however, still
says the router "overlays" live weights as dynamic weights without choosing the
default strategy or stating whether routes are exact, bounded-suboptimal, or
best-effort under very fresh traffic.

Why it matters: live traffic is the hardest algorithmic part of this case.
Without a chosen strategy, the answer can sound correct while hiding the central
trade-off between fresh weights, query latency, preprocessing cost, and optimal
route guarantees.

Concrete fixes:

- Pick one default, for example customizable CH for live speed updates plus
  closure overlays as hard bans.
- If using corridor repair, say CH on base/historical weights finds a candidate
  corridor, then local A* reranks/repairs within that corridor under live
  weights; call out possible bounded suboptimality.
- If using time-dependent CH, say how departure-time buckets align with
  `edge_speed.time_bucket` and what happens for "leave now" versus future
  departure.
- Update the traffic option's default and final design to use the same wording.
- Add one sentence to `satisfies` explaining the freshness/correctness contract
  for live traffic in routing.

### 3. Region partitioning is clearer, but still under-modeled

The text now describes duplicated/coordinated border vertices, a thin
inter-region overlay graph, hot metro splits, and regional degradation. The data
model and architecture view still only show `region_id` on edges and the generic
`GraphStore`/`CH` components.

Why it matters: geographic partitioning is one of the core staff-level signals
for a routing system. It should be represented by at least one concrete artifact
so the candidate can explain ownership, cross-region planning, and failure
behavior without relying on prose.

Concrete fixes:

- Add model entries for `region_shard`, `border_vertex`, and `overlay_edge` or
  fold those fields into a dedicated `region_overlay` entity.
- Show the overlay graph as a derived index or part of the CH/index layer in
  Step 6 and the final design.
- State whether border vertices are duplicated with reconciliation, owned by a
  parent partition, or materialized in an overlay service.
- Add a cross-region cache key example that includes source/destination cells,
  graph/index version, avoid flags, mode, and traffic freshness bucket.
- Add one regional failure drill: traffic unavailable in a region, graph shard
  stale, or overlay graph publish failure.

### 4. Geocoding is in scope but still light compared with routing

The requirements and API include geocoding, and the route API sequence snaps
endpoints to graph nodes. The dataset does not yet show the place/address index,
normalization, ambiguity handling, or nearest-edge snapping quality that makes
geocoding reliable enough for routing.

Why it matters: a route request often starts from user-entered addresses or
place names. Bad geocoding or snapping can produce a perfectly computed route
from the wrong point.

Concrete fixes:

- Either explicitly scope geocoding as an external subsystem, or add a
  lightweight `geocode_index` data model and `GeocodeIndex` node.
- Include response ambiguity fields such as confidence, candidate places, and
  snapped edge/node metadata.
- Mention reverse geocoding and nearest-road snapping separately if the route
  API accepts raw lat/lng.
- Add a trap or follow-up: "The shortest path is correct, but the origin was
  snapped to the wrong frontage road."

## System Design Soundness

### Requirements and Capacity

The requirements are now well scoped for a maps-routing interview: fastest route
between locations, geometry/distance/ETA/turn-by-turn, tile serving, live
traffic, and geocoding. The privacy non-functional requirement is a strong
addition because probe-based traffic is impossible to discuss responsibly
without it.

Capacity is now one of the stronger parts of the dataset. It separates route
QPS from tile reads, gives a p99 route budget, quantifies graph size, estimates
CH expansion and region shard sizing, and separates traffic freshness from base
graph rebuild cadence. The next useful capacity addition is a traffic-store
budget: edge-speed rows, update QPS, route-time read QPS, cache memory, and
multi-region replication.

### API

`GET /v1/route` now matches the stated product behavior well. It includes
traffic-aware request parameters and returns route legs, steps, maneuvers,
polyline, traffic-aware duration, warnings, and version metadata. That is a big
improvement over the previous shape.

Two API refinements would make it more production-like:

- For many waypoints or route-shape options, mention when the route endpoint
  becomes `POST` instead of a very long `GET` query string.
- Add an optional response-shape control such as overview-only versus full
  turn-by-turn, because mobile clients often need to bound payload size.

The tile API is now solid: style/version/z/x/y/format plus immutable caching is
the right mental model. The geocode API is acceptable for the case, but it needs
either a backing index model or an explicit "provided by a separate geocoding
system" boundary.

### Data Model

The data model now supports the main routing behavior. `road_graph (edge)` has
the fields needed for directed routing, avoid flags, geometry, restrictions,
region ownership, and versioning. `ch_index` now carries shortcut unpacking and
compatible graph/index versions. `edge_speed` now supports live speed,
time-bucketed historical fallback, confidence, sample count, incident overrides,
and freshness.

The remaining model gaps are the stateful artifacts around the model:
`TrafficStore`, `RestrictionOverlay`, `BuildArtifact`/`GraphRelease`,
`RegionOverlay`, and possibly `GeocodeIndex`. These do not need exhaustive
schemas, but naming them would make the final architecture more honest.

### Architecture

The high-level architecture is coherent: client, gateway, routing service,
geocoder, graph store, CH index, tile service/store/CDN, probe stream, traffic
aggregator, and traffic service. The separation between routing, tiles, and
traffic is correct and easy to teach.

The architecture still underrepresents derived state and offline work. The
`TrafficSvc` is marked stateless, but it is the read API for continuously
updated traffic state. The build pipeline is represented in the ops sequence by
relabeling the `TrafficAgg` participant as "Build Pipeline", which is
semantically confusing because the traffic aggregator and graph/index builder
are different systems. Add a real `BuildPipeline` node and, ideally, a
`TrafficStore`/`RestrictionOverlay` node.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Dijkstra/A* Over the Whole Graph Per Request

This is now an excellent opener. It starts with the familiar correct baseline,
then gives concrete scale language: plain Dijkstra can settle tens of millions
of nodes while CH touches thousands. That makes the need for preprocessing
obvious.

Keep this step compact. It should not teach all routing algorithms yet; it
should motivate why the next steps exist.

### Step 2: Model Roads as a Weighted Graph

The graph abstraction is introduced cleanly: intersections as nodes, road
segments as directed weighted edges, one-way streets, restrictions, penalties,
and geometry. The data model now reinforces those details, so this step no
longer feels disconnected from the schema.

One possible improvement is to mention edge-based routing for turn costs: some
systems model state as "arrived via edge" so turn restrictions and penalties are
handled accurately. That can be a note, not a main branch.

### Step 3: Make Shortest-Path Fast with Preprocessing

This is the core teaching step and it now lands well. The shortcut-unpacking
paragraph is especially important because it connects the algorithmic answer to
the product output: geometry and maneuvers.

Keep CH as the default. It is the right interview choice when paired with the
live-traffic caveats introduced later.

### Step 3a: Preprocessing Choices: CH vs Hub Labeling vs A*

The option comparison is strong. CH, hub labeling, and ALT are described in
terms of build time, storage, query speed, and graph update frequency rather
than as strawmen.

The only remaining gap is linking this choice more explicitly to Step 5. The CH
option already says live traffic needs customizable CH or A* support; the final
design should pick which one the system actually uses.

### Step 4: Serving Map Tiles

This step is now production-realistic. It explains tiles as static, read-heavy,
CDN-friendly content and includes immutable version paths, cache headers, and
origin stampede protection. The alternatives are useful: pre-rendered CDN
tiles, client-rendered vector tiles, and origin rendering.

No major change is needed. A minor optional improvement is to state which format
is the default for the interview answer: vector tiles for flexible clients or
raster tiles for simpler serving.

### Step 5: Live Traffic from GPS Probes

This step improved the most. It now covers map matching, GPS noise,
anonymization, dedupe, confidence, sparse coverage, historical fallback,
incidents/closures, privacy, and the challenge of using dynamic weights with
preprocessed routing.

The remaining issue is decision precision. The step lists the right approaches,
but the chosen design should not leave the candidate saying only "dynamic edge
weights." Pick a default live-weight strategy and state its consequences.

### Step 6: Scaling: Region Partitioning

The locality, border, overlay, hot-metro, and degradation story is now much more
credible. This is close to a strong staff-level partitioning discussion.

The improvement should be visual/model-based: show the region overlay as an
artifact. If the final diagram only shows a generic graph store and CH index,
the most important part of Step 6 can be missed.

### Step 7: Graph Updates, Caching, and Reliability

This step now has the right operational arc: immutable artifacts, topology
validation, CH build, route regression, canary, rollback, request version
pinning, fast urgent overlays, route cache keys, and traffic fallback.

The main cleanup is semantic: do not reuse `TrafficAgg` as the "Build Pipeline"
participant in the ops sequence. Add a build-pipeline node or keep the flow
purely conceptual. Also consider adding closure-overlay storage to the diagram
because Step 7 correctly depends on it.

## Final Design Review

The final design is now much closer to a polished interview answer. It includes
the important choices: weighted directed graph, offline CH index, stateless
routing service, version pinning, shortcut unpacking, traffic overlays,
historical fallback, privacy-controlled probes, fast closure overlays,
versioned CDN tiles, geo partitioning, and inter-region overlay/border graph
routing.

The final answer should make three things more explicit:

- Where dynamic traffic and urgent restrictions are stored and served from.
- Which live-weight routing algorithm is the default.
- Which components own graph/index/tile artifact build, validation, canary, and
  rollback.

Those changes would make the final design match the quality of the improved
step prose.

## Concept Introduction and Learning Flow

The concept order is strong: road graph, contraction hierarchies, preprocessing
trade-off triangle, tile pyramid/CDN, probe-based traffic, dynamic edge weights,
geo sharding/overlay graph, and immutable versioned artifacts. The concepts are
introduced just in time and tied to steps.

Two concept additions would sharpen the staff-level learning path:

- "Traffic state store / freshness bucket": live speeds are a high-write,
  high-read regional state problem, not just a service.
- "Restriction overlay": closures and temporary turn bans are correctness
  overlays with faster freshness than base graph rebuilds.

## Step-to-Final-Design Coherence

The step-to-final-design coherence is now good:

- Step 1 motivates why naive per-request graph search fails.
- Step 2 introduces the road graph and geocoding dependency.
- Step 3 and 3a introduce CH and preprocessing alternatives.
- Step 4 introduces tile service, tile store, CDN, and immutable tile versions.
- Step 5 introduces probe stream, traffic aggregation, dynamic weights, privacy,
  incidents, and historical fallback.
- Step 6 introduces region partitioning and the overlay/border graph idea.
- Step 7 introduces immutable artifacts, version pinning, rebuild validation,
  canary, rollback, cache keys, and degradation.

The main coherence gap is that some late-step entities are not visible in the
architecture inventory. Add explicit nodes or data-model entries for traffic
state, restrictions, build pipeline, and region overlay so the final design
does not rely on prose alone.

## Realism Compared With Production Systems

The case now resembles real routing systems much more closely than the previous
reviewed version. It accounts for the distinction between static graph data and
live traffic, separates tile delivery from route computation, uses immutable
artifact versions, recognizes probe privacy, and describes canary/rollback for
graph releases.

Remaining realism gaps:

- Traffic state is not modeled as a store despite high update volume.
- Closure/restriction overlays are mentioned but not represented as a data path.
- Geocoding lacks a place/address index and ambiguity handling.
- Dynamic traffic with CH needs a committed algorithm and correctness statement.
- Region overlay routing should have a concrete artifact, not only a paragraph.
- Route observability could be more explicit: p50/p95/p99 latency, no-route
  rate, ETA error, probe freshness, traffic coverage, graph-release regression,
  and tile origin miss/stampede metrics.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level sections are present: requirements, capacity, API, data model,
  high-level architecture, patterns, steps, final design, satisfies, interview
  script, level variants, follow-ups, and probe links.
- No raw Mermaid `diagram` fields were found in step, option, flow, or
  final-design surfaces.
- Step, option, and final-design string `view.nodes` references resolve against
  `highLevelArchitecture.nodes`.
- Step, option, and final-design string `view.links` references resolve against
  `highLevelArchitecture.links`.
- Flow and API sequence messages reference declared participants.
- `satisfies.functional[*].steps[*]` and
  `satisfies.nonFunctional[*].steps[*]` resolve to real step IDs.
- `patterns[*].steps[*]` and step-level `probeLinks` resolve.
- All step and option views have captions.
- Review-only changes do not require rebuilding `docs/`.

Renderer/content polish:

- The Step 7 flow uses participant ID `TrafficAgg` with label "Build Pipeline".
  Rendering is valid, but the semantic mapping is wrong. Prefer a distinct
  `BuildPipeline` node or participant.
- There are no `aiVisual` assets for this dataset. That is fine for correctness,
  but optional if this case should visually match the most illustrated book
  interviews.

## Recommended Edits, Prioritized

### P1: Add stateful traffic, restriction, build, and geocode/overlay artifacts

Add `TrafficStore`, `RestrictionOverlay`, `BuildPipeline`, and either
`GeocodeIndex` or an explicit external geocoding boundary. Consider adding an
`OverlayGraph`/`RegionIndex` as a derived routing artifact.

### P1: Commit to one live-traffic routing strategy

Choose customizable CH, time-dependent CH, or CH-plus-local-A* corridor repair
as the default. State freshness, latency, and optimality trade-offs clearly.

### P1: Represent region overlay routing in the model/diagram

Add border vertices, overlay edges, region ownership, and cross-region planning
as concrete artifacts so Step 6 is visible in the final architecture.

### P2: Add a traffic-state capacity line

Quantify edge-speed rows, update rate into the store, route-time reads, memory
footprint, and replication/freshness behavior.

### P2: Add geocoding ambiguity and snapping behavior

Model confidence, candidates, snapped edge/node, and failure behavior when the
address or coordinate maps ambiguously to the road graph.

### P2: Add observability signals

Add route latency, no-route rate, ETA error, traffic freshness, traffic coverage,
probe drop/filter rate, graph-release regression metrics, and tile-origin miss
rate.

### P3: Add optional visuals or one extra sequence flow

Optional: add `aiVisual` assets or a step-level route-query flow showing version
pinning, traffic lookup, CH query, shortcut unpacking, and response assembly.

## What Not To Change

- Keep the baseline-to-CH teaching arc. It is clear and effective.
- Keep the separate treatment of routing, tiles, and traffic.
- Keep CH as the default preprocessing family, with live-traffic caveats.
- Keep `preprocessing-choice` as a sub-step under preprocessing.
- Keep the quantitative capacity section; refine it rather than replacing it.
- Keep privacy as a first-class non-functional requirement.
- Keep the final design compact; add missing components surgically.

## Bottom Line

The maps-routing interview is now a strong, coherent walkthrough. The recent
changes fixed the largest issues in capacity, API, data model, traffic, privacy,
partitioning, and rollout. To make it flagship-level, the next pass should make
the hidden operational state visible and choose a precise live-traffic routing
strategy. Those are targeted improvements, not structural rewrites.
