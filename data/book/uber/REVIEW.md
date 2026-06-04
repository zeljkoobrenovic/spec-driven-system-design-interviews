# Review: Uber - Ride Matching System Design

Reviewed file: `data/book/uber/interview.json`
Review date: 2026-06-04

## Executive Summary

This is a strong ride-matching walkthrough. It identifies the right core
problems: location ingest at firehose scale, fast nearby queries over moving
drivers, dispatch contention, state-machine correctness, surge, routing, and
regional sharding. The step order is coherent and most options teach real
trade-offs rather than strawmen.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4 | Core architecture is credible, but operations, privacy/security, and dispatch offer state need more substance. |
| Production realism | 3 | Good on geo and CAS; light on live-location abuse, push delivery, cancellations, overload, and regional failover. |
| Pedagogical flow | 4 | The baseline-to-final progression is clear and interview-friendly. |
| Dataset/rendering fit | 4 | Structured views and references are clean; mobile app nodes use the wrong canonical type. |
| Overall | 4 | Usable as a flagship case after a few targeted production-realism edits. |

## What Works Well

- The naive scan baseline makes the geo-index and ingest pipeline feel
  necessary instead of arbitrary.
- The dataset correctly separates high-frequency location state from durable
  trip state.
- Step 3's geohash/S2 discussion covers cell boundaries, adaptive resolution,
  and hot cells, which are the right geospatial concerns.
- Step 4 and Step 4a teach that ride matching is not just nearest-neighbor
  lookup; it is an offer, acceptance, and optimization problem.
- Step 5 introduces atomic assignment at the right moment, after dispatch has
  exposed the double-booking risk.
- `satisfies` maps requirements to real step IDs, and structural view/link
  references resolve cleanly.
- The final design integrates most components introduced by the steps.

## Highest-Impact Issues

### 1. Dispatch needs an explicit offer/attempt model

Step 4 describes time-boxed offers, declines, timeouts, and fall-through to the
next candidate, but the data model has no `offers`, `dispatch_attempts`, or
offer lease entity. The accept API is `POST /v1/trips/{id}/accept` with only
`driver_id`, which lets a driver accept a trip without proving they are
accepting the current valid offer.

Why it matters: in production, the offer is the unit that prevents late accepts,
duplicate accepts, stale mobile retries, and "accept an offer that already
expired" bugs. A trip-level CAS alone is not enough to explain offer validity,
offer TTLs, driver notification retries, or fall-through accounting.

Concrete fix: add a dispatch-offer entity with `offer_id`, `trip_id`,
`driver_id`, `status`, `expires_at`, `attempt_number`, and `idempotency_key`.
Change the accept API to include `offer_id` and an idempotency key. Clarify
that `POST /rides` creates a trip in `matching`, dispatch creates short-lived
offers, and accept CASes both `offer: offered->accepted` and
`driver: available->busy` or equivalent guarded state.

### 2. Observability and operations are underrepresented

The final design has no observability component, and the steps do not define
the operational signals that would run this system: location-stream lag, stale
location percentage, geo-query latency, candidate set size, offer timeout rate,
acceptance rate, CAS conflict rate, hot-cell cardinality, routing degradation,
regional error budget burn, and p99 time-to-match.

Why it matters: ride matching fails gradually before it fails completely.
Without these metrics, the design cannot detect that a city is silently matching
from stale driver positions, routing is producing bad ETAs, or a hot cell is
causing assignment contention.

Concrete fix: add an observability node to the high-level architecture and final
design, plus an operations/failure drill section. Tie metrics to user-visible
SLOs: time to first offer, time to matched trip, location freshness, dispatch
success rate, ETA error, and regional availability.

### 3. Live-location security, privacy, and fraud are scoped too far out

The dataset stores and streams millions of driver locations, but security and
privacy appear mainly as a follow-up about GPS spoofing. The location endpoint
does not mention authentication, replay protection, signed device telemetry,
rate limiting, consent, location retention, or separation between latest
location and historical/audit location.

Why it matters: live location is sensitive and adversarial. Drivers can spoof
position to game surge or airport queues; attackers can scrape movement; stale
or replayed pings can poison matching. These concerns materially change API
shape and ingest validation.

Concrete fix: add a non-functional requirement for location privacy and abuse
resistance. Add fields or notes for authenticated driver/device identity,
ping timestamp validation, monotonic sequence numbers, TTL on latest location,
retention policy for any history, and fraud/risk checks before updating the geo
index.

### 4. Capacity estimates stop before partition sizing and bottleneck math

The capacity section correctly estimates roughly 2-3M location updates/sec and
10k-100k peak ride requests/sec, but it does not translate that into stream
partitions, per-region skew, hot-city budget, geo-query fanout, candidate caps,
routing QPS, index memory, or network/write volume.

Why it matters: the architecture's most important decisions are partition
decisions. "10M drivers" is useful, but an interview candidate should connect it
to "how many pings per hot city", "how many partitions per region", "how many
candidate drivers per query", and "how many ETA calls per ride request".

Concrete fix: add a capacity row or deep dive that sizes a hot region: online
drivers, pings/sec, event size, stream partitions, expected cell cardinality,
candidate cap, ETA calls per request, and write/read amplification from
location ping to latest store plus geo index.

### 5. Graceful degradation is promised but not designed end to end

The non-functional requirements promise "widen search or queue rather than fail"
and the `satisfies` section mentions geo-distance fallback when routing
degrades. The steps do not yet define a unified degradation policy for no
candidates, stale index data, push notification failure, region-router outage,
surge-store staleness, lock-store contention, or a routing brownout.

Why it matters: this system's normal failure mode is not a total outage; it is
degraded match quality and longer rider wait. The design should show how the
system chooses between widening radius, relaxing filters, queueing requests,
falling back to approximate ETA, or returning "no drivers available".

Concrete fix: add a dedicated failure drill or wrap-up subsection with
degradation tiers. Include the trigger metric, fallback action, user-visible
behavior, and recovery condition for ingest lag, routing degradation, no
candidates, push failures, and regional overload.

## System Design Soundness

The requirements cover the main user workflow and the core scaling challenge.
The strongest parts are the location ingest split, geospatial indexing, atomic
assignment, ETA ranking, and regional sharding. These map well to a real
ride-hailing platform.

The API is plausible but underspecified for production. `POST /v1/rides` should
include rider identity through auth, quote/fare context, pickup/dropoff
validation, product constraints, and an idempotency key. The driver location
endpoint needs driver/device authentication and stale/replayed ping handling.
The accept endpoint should accept an `offer_id`, not only `trip_id` and
`driver_id`.

The data model supports the high-level story but misses several operational
records: dispatch offers, idempotency records, quote snapshots, surge multiplier
at acceptance, driver availability lease, state-transition audit, cancellation
reason, and location TTL. These omissions are fixable without changing the
overall design.

The architecture correctly avoids scanning every driver and avoids durable
writes for every ping. The remaining soundness gap is that the final design
looks cleaner than the real system would be: no auth/risk boundary, no
observability path, no push delivery retry model, no location validation, and no
explicit backpressure mechanism.

## Step-by-Step Pedagogical Review

### Step 1: Request a Ride (the naive baseline)

This is an effective baseline. It exposes the O(drivers) scan and motivates
spatial indexing. Improve it by explicitly naming the first invariant: a rider
request creates at most one active matching trip for the rider/idempotency key.

### Step 2: Driver Location Ingestion at Scale

The stream plus latest-location store is the right default. The step would be
stronger if it separated "latest location for matching" from "retained location
history for safety, fraud, support, or legal/audit use" and explained TTL/stale
handling for drivers whose app stops pinging.

### Step 3: Geospatial Index for Nearby Drivers

This is one of the best steps. It covers cell plus neighbor lookup, hot cells,
and adaptive resolution. Add one concrete sizing example: at a chosen cell
level, cap to N candidates, then rank by true ETA after the coarse geo filter.

### Step 4: Matching & Dispatch

The offer/accept framing is correct and avoids force assignment. The main
improvement is to model offers explicitly. Late accept, duplicate accept,
driver notification failure, and timeout fall-through all become much easier to
teach once an offer has its own ID, expiry, and status.

### Step 4a: Matching Strategy: Greedy vs Batched

The sub-step is valuable because it moves beyond "nearest driver". The text is
strong, but the default option label says greedy is default while the prose says
real systems lean batched in dense markets and greedy in sparse markets. Make
the default conditional or name it "market-density adaptive policy" to avoid
teaching a single global default.

### Step 5: Trip State Machine & Atomic Assignment

This is the right correctness step. The CAS/lock/single-writer options are
useful. Tighten the model by distinguishing trip state, driver availability
state, and offer state. Also explain cancellation transitions: rider cancels
while matching, driver cancels after accept, trip expires, and payment/fare
finalization after completion.

### Step 6: Surge Pricing

The step correctly stresses smoothing, caps, and quote-time freezing. It should
add fairness and abuse controls: surge should not update from spoofed supply,
should use robust demand signals, and should have auditability because pricing
trust and regulation are material concerns.

### Step 7: ETA & Routing

The step correctly rejects straight-line distance and introduces routing as a
heavy subsystem. It would benefit from capacity math: if each match ranks 20
candidate drivers, routing QPS is much higher than ride-request QPS unless
batched, cached, approximated, or precomputed.

### Step 8: Scaling by Region (geo-sharding)

The locality and blast-radius argument is correct. Add region ownership and
handoff mechanics: how driver pings are routed to a region, what happens near a
boundary, how a driver moves between regions, and how one region fails over or
degrades without corrupting driver availability.

## Final Design Review

The final design ties together ingest, regional indexes, matching, ETA, surge,
dispatch, push notification, and atomic trip state. That is the right shape.

The final diagram should include observability and probably auth/risk as
first-class production components. It should also make the offer lifecycle
visible. `Notify` appears in the final design even though push delivery
semantics are not taught in an earlier step; either introduce push failure in
Step 4 or keep notification as a minor implementation detail.

## Concept Introduction and Learning Flow

Concepts are introduced mostly just in time. The flow from proximity query to
ingestion to geo-indexing to dispatch to atomic assignment is strong. The later
steps are also sensible: once correctness exists, pricing and ETA improve market
quality, then regional sharding handles global scale.

The main teaching gap is that production operations arrive too late or not at
all. Candidates need to learn that a ride-matching system is operated by
freshness, latency, acceptance, and conflict metrics. A small operations step
or wrap-up would make the case more realistic without bloating the core path.

## Step-to-Final-Design Coherence

Each step contributes visible final-design components, and the `satisfies`
mapping is coherent. The strongest transitions are:

- Step 2 to Step 3: ingest feeds the geo index.
- Step 3 to Step 4: nearby candidates become dispatch offers.
- Step 4 to Step 5: offer races motivate atomic assignment.
- Step 7 to final design: ETA improves both ranking and rider-facing estimates.
- Step 8 to final design: regional shards isolate hot-city load.

The weakest transition is the offer lifecycle: final design persists trip state
and claims drivers, but the intermediate offer/attempt record is invisible.
That makes dispatch look simpler than the prose says it is.

## Realism Compared With Production Systems

The dataset is credible on geospatial indexing and marketplace matching, but
production ride-hailing systems also need:

- location-authentication and anti-spoofing controls before pings affect supply;
- explicit location retention and deletion policy;
- push notification delivery retries, expiry, and acknowledgement;
- operational metrics and alerting tied to city/region SLOs;
- region failover and degraded mode;
- quote/fare snapshots that preserve the accepted price;
- cancellation and support/audit state transitions;
- backpressure when a city is overloaded or routing is degraded.

These do not need to dominate the interview, but at least the highest-impact
ones should appear in requirements, the data model, or failure drills.

## Dataset and Renderer-Facing Observations

- JSON parses successfully.
- Step and option `view.links` string references resolve to
  `highLevelArchitecture.links`.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- `highLevelArchitecture.types` is an empty array; this is valid for the
  renderer but means group-level architecture type sections are unused.
- `Rider` (`Rider App`) and `Driver` (`Driver App`) are currently typed as
  `service`. Repo conventions say outside software such as mobile apps should
  use canonical type `client`. Human roles should use `actor`.
- Several option-local nodes such as `BatchSolver`, `DriverLock`, `DriverQ`,
  and `CH` are valid because the renderer can fall back to local node metadata,
  but they render without canonical type styling unless authored as objects with
  type/render metadata or added to the architecture catalog.
- Raw overview Mermaid diagrams are appropriate for requirements and capacity.

## Recommended Edits, Prioritized

### P1: Add dispatch-offer state and tighten accept semantics

Add `dispatch_offers` or `offer_attempts` to the data model, update the accept
API to use `offer_id`, and clarify the trip/driver/offer CAS relationship in
Step 4 and Step 5.

### P1: Add observability and degradation policy

Add an observability node and a failure drill that covers location lag, hot
cells, route-service brownout, push notification failure, lock contention, and
regional overload.

### P1: Add location privacy, auth, and anti-spoofing requirements

Add a non-functional requirement plus API/data-model notes for authenticated
driver pings, replay protection, TTL, retention, and fraud validation before
index updates.

### P2: Expand capacity math into partition and fanout sizing

Add hot-region sizing: event bytes/sec, stream partitions, geo-index memory,
candidate cap, ETA calls/request, routing cache hit expectations, and expected
assignment conflict rate in dense cells.

### P2: Fix canonical node types

Change `Rider` and `Driver` app nodes from `service` to `client`. Keep true
human roles as `actor`.

### P2: Make matching strategy default conditional

Replace the greedy default with an adaptive policy: greedy in sparse markets,
short-window batched optimization in dense markets.

### P3: Add cancellation and quote/fare records

Represent cancellation reasons, quote snapshots, accepted surge multiplier, and
state-transition audit records.

### P3: Introduce notification reliability where `Notify` appears

Either add a small dispatch/push failure drill or make `Notify` less prominent
in final design.

## What Not To Change

- Keep the naive baseline; it is pedagogically useful.
- Keep geohash/S2 as the central data-structure lesson.
- Keep the Step 4a greedy-vs-batched sub-step; it is a strong differentiator
  for a senior-level interview.
- Keep CAS/lock/single-writer as explicit alternatives in Step 5.
- Keep regional sharding as the final scaling move rather than introducing it
  at the beginning.

## Bottom Line

This is a strong dataset with the right architecture spine. The most valuable
next edits are not more components for their own sake; they are production
clarity around dispatch offers, live-location trust, observability, degradation,
and region-scale operations.
