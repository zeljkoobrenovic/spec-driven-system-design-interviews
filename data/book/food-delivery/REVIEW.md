# Review: DoorDash - Food Delivery - System Design

Reviewed file: `data/book/food-delivery/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a strong and interview-ready walkthrough. It has a clean progression from baseline order placement to state machine, geo indexing, dispatch, tracking, saga reliability, and regional scale. The teaching flow is especially good: every step exposes the next missing mechanism instead of dumping the full architecture at once.

The highest-impact gaps are mostly production-detail omissions rather than structural defects. The dataset should make capacity math concrete, expose the lifecycle/dispatch APIs that the architecture relies on, add explicit data structures for transition history, idempotency, payment and assignment attempts, and show the last-known location/cache and event/outbox path as first-class architecture elements rather than prose-only mechanisms.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4 | Strong core mechanisms; needs more explicit state, idempotency, and partitioning details. |
| Production realism | 3.5 | Covers sagas and geo writes, but understates leases, retries, outbox, provider callbacks, and operational safety. |
| Pedagogical flow | 4.5 | Excellent step sequencing and problem revelation. |
| Dataset/rendering fit | 4 | JSON is valid and references resolve; missing concrete visual nodes for prose-only mechanisms. |
| Overall | 4 | A solid case that would become excellent with more implementation-level specificity. |

## What Works Well

- The interview has a clear teaching spine: naive order row -> lifecycle state machine -> geo index -> dispatch -> tracking -> saga -> regional scale.
- Food delivery is treated as a three-sided workflow, not a generic ride-matching problem. Restaurant readiness and courier offer/accept are called out.
- The geo-index options are realistic and balanced: geohash/S2, Redis GEO, and adaptive spatial indexing each have meaningful pros and cons.
- Dispatch options teach real tradeoffs between greedy matching, batched optimization, and broadcast/pull acceptance.
- The reliability step correctly centers the state machine as the saga ledger and names idempotent transitions.
- Renderer-facing basics are clean: source JSON parses, step view nodes resolve to `highLevelArchitecture.nodes`, step view link ids resolve, sequence participants map to canonical node ids, `satisfies[*].steps[*]` slugs resolve, pattern references resolve, probe links resolve, and final-design groups resolve through `highLevelArchitecture.types`.

## Highest-Impact Issues

### 1. Capacity is qualitative, not worked through

The capacity section says "millions", "100Ks", and "every few sec/courier", but the design depends heavily on rates. A candidate needs concrete derived numbers to defend stream partitions, geo-index writes, tracking fanout, and dispatch latency.

Recommended edit: add a worked example such as 2M orders/day with a 5x dinner peak, 100K live couriers pinging every 4 seconds, about 25K location writes/sec before peak multiplier, matching QPS tied to ready orders, and tracking fanout tied to active deliveries. Then map each rate to the component it stresses.

### 2. The API surface does not expose the lifecycle the architecture teaches

The API only lists order creation, tracking fetch, and courier location updates. The walkthrough depends on restaurant confirm/ready/reject transitions, courier accept/decline/pickup/dropoff transitions, eater cancel, payment auth/capture, and possibly a push tracking subscription, but these are not represented.

Recommended edit: add APIs or explicitly scoped internal endpoints for:

- `POST /v1/orders/{id}/restaurant-transition` or concrete confirm/ready/reject endpoints.
- `POST /v1/orders/{id}/courier-offers/{offerId}:accept|decline`.
- `POST /v1/orders/{id}:cancel`.
- idempotency keys on order placement and every lifecycle transition.
- version or expected-state fields for compare-and-set transition safety.

### 3. The data model is too thin for the promised reliability behavior

The `orders`, `courier_location`, and `assignments` entities are a reasonable start, but they cannot fully support the described saga, auditing, retries, and compensations. The reliability step says transitions are idempotent and resumable, but the schema has no transition log, idempotency key table, payment authorization/capture record, offer attempt lease, or outbox/event table.

Recommended edit: add entities such as:

- `order_state_transitions(order_id, from_state, to_state, actor, transition_id, idempotency_key, created_at)`.
- `payment_attempts(order_id, provider_payment_id, auth_state, capture_state, retry_count)`.
- `courier_offers(offer_id, order_id, courier_id, expires_at, state, accepted_at)`.
- `outbox_events(order_id, event_type, payload, published_at)`.
- optional `delivery_tracking(order_id, courier_id, last_location_id, eta_version)`.

### 4. "Last-known store" and event/outbox are prose-only mechanisms

The text repeatedly says tracking reads a last-known store and state changes emit events, but the canonical architecture only shows `LocStream`, `GeoIndex`, `Tracking`, `OrderDB`, and `Notify`. That makes diagrams understate the hot read path and the reliability boundary between state transitions and notifications.

Recommended edit: add explicit nodes for a `LastKnownLocation` cache/store and an `OrderEvents` stream or outbox. Wire courier pings to stream -> last-known -> tracking, and order state changes to outbox/events -> notification/dispatch consumers. This would make the diagrams match the prose and improve the final design.

### 5. Dispatch needs stronger concurrency and failure semantics

The dispatch step mentions atomic claims and time-boxed offers, but the model should make leases and expiry concrete. The hard production bugs are double booking, stale courier availability, courier app reconnects, partial acceptance races, and re-offering after timeout.

Recommended edit: teach the offer as a lease:

- offer has `expires_at` and a monotonic `offer_version`.
- accept uses compare-and-set from `offered` to `accepted`.
- courier availability changes atomically with assignment.
- timeout worker expires stale offers and requeues the order.
- reassignment increments an assignment attempt counter and preserves history.

## System Design Soundness

Requirements are well scoped for a food-delivery platform: order placement, restaurant prep, courier dispatch, live tracking, ETA, and lifecycle notifications. The non-functional requirements correctly prioritize consistency, seconds-level freshness, scale, and dispatch quality.

The main missing requirement is privacy and safety around location data. Courier GPS is sensitive, eater access should be limited to assigned active orders, and location retention should be short or explicitly justified. Another useful requirement is graceful degradation: under map/ETA provider failure, the system should still accept orders, dispatch with degraded scoring, and show coarse ETAs.

The architecture is directionally sound. Order service as lifecycle owner, geo index for nearby couriers, dispatch scoring through ETA, and saga-based reliability are credible. The final design coherently integrates the steps, but it compresses several production-critical mechanisms into prose. Last-known location storage, order event publishing, idempotency storage, and payment/provider callback handling should be first-class components or data entities.

The capacity section should be upgraded from labels to calculations. This design is dominated by peak location writes, hot geo cells, tracking fanout, and dispatch candidate scoring. Without rates, it is hard to justify stream partitioning, cache sizing, regional dispatch isolation, or whether WebSocket/SSE push is affordable.

## Step-by-Step Pedagogical Review

### Step 1: Naive baseline

Strong baseline. It clearly shows why a single order row and manual dispatch fail. The trap is useful.

Improvement: make the baseline explicitly fail on duplicate order submissions and payment retry, not just manual dispatch and no tracking. That would prepare the reader for idempotency earlier.

### Step 2: Order lifecycle state machine

This is the right backbone. The description explains allowed transitions, party-triggered transitions, and notification events.

Improvement: add a compact transition table or examples with actor and allowed previous states. For example, restaurant can move `confirmed -> preparing -> ready`; courier can move `assigned -> picked_up -> in_transit -> delivered`; cancellation branches differ before and after prep.

### Step 3: Live courier locations

The geo-index explanation and alternatives are strong. It correctly warns against writing every GPS ping to the order DB.

Improvement: include TTL/staleness handling and privacy retention. The index should drop couriers whose `updated_at` is old, distinguish available vs on-delivery couriers, and avoid retaining full GPS history unless needed for fraud/support with bounded retention.

### Step 4: Dispatch

This is the strongest system-design step. It teaches ready-time-aware matching, scoring, offer/accept, and alternatives beyond nearest courier.

Improvement: make the assignment record and offer lease explicit. The flow should include courier accept updating `assignments` and `orders`, and the timeout branch should requeue the order or advance to the next candidate with attempt history.

### Step 5: Live tracking and ETA

The step correctly separates tracking from the order database and compares push with polling.

Improvement: add the connection tier or fanout layer needed for millions of long-lived connections. Also separate the stream from the last-known cache: consumers do not usually query a log-like stream for "latest position"; they read a materialized last-known view.

### Step 6: Consistency across failures

The saga framing is right and the failure drills are useful.

Improvement: the sequence diagram only covers restaurant rejection after payment auth. Add branches for payment provider timeout/callback ambiguity, courier accepts then disappears, duplicate transition retry, and cancellation after capture. Add outbox/inbox or dedup semantics so "transition persisted" and "event emitted" do not split-brain.

### Step 7: Scaling spikes, geo hotspots, and regions

The scale step correctly focuses on meal-time spikes, regional dispatch, rebuildable geo state, and graceful degradation.

Improvement: make the scaling decisions more concrete. Add options or sub-bullets for partitioning by region/cell, hot-cell splitting, backpressure on GPS pings, degraded ETA mode, dispatch queue prioritization, and cross-region boundary orders.

## Final Design Review

The final design is coherent and maps to the step journey. It includes the three clients, gateway, order service/store, payment, dispatch, geo index, location stream, tracking, ETA, and notification service. The description correctly states that orders are authoritative while geo/last-known state is rebuildable.

The gap is that the diagram does not actually include all the mechanisms the final description names. In particular, "last-known store" is not a node, and state-change event/outbox handling is represented only as `OrderSvc -> Notify`. For a reliability-focused interview, that path should show durable event publication or an outbox so notifications, dispatch triggers, and saga recovery are grounded.

## Concept Introduction and Learning Flow

Concepts are introduced just in time. State machine appears before geo and dispatch; dispatch appears before tracking; saga appears after the happy path. That sequence is easy for a candidate to present.

The next improvement is to connect concepts to concrete artifacts. "Order state machine" should map to a transition table and transition log. "Saga with compensation" should map to an orchestrator state record, idempotency keys, and outbox events. "Location streaming + last-known" should map to a stream plus materialized cache/store.

## Step-to-Final-Design Coherence

The final design includes the components introduced by the steps, and the `satisfies` section maps requirements to the right steps. The strongest coherence issue is that scale-related details do not alter the final design much. The final design says "shard by region" and "per-region dispatch", but the architecture still looks single-region and single-instance.

Recommended edit: either add a final-design option or caption details that show region/cell partitioning, stream partitions, and per-region dispatch workers. That keeps the final design from sounding like a single-city diagram with scale added in text.

## Realism Compared With Production Systems

The dataset captures the most important production themes: moving-object geo indexing, offer/accept dispatch, live tracking, and distributed workflow compensation. It is more realistic than a generic marketplace design.

The realism gaps are:

- Payment provider ambiguity: duplicate callbacks, auth expiration, capture failure, chargeback/refund workflows.
- Restaurant integration ambiguity: tablet/app offline, rejection after delay, prep-time estimates, throttling busy restaurants.
- Courier operations: accept timeout, location spoofing, app offline, reassignment, multi-order batching.
- Observability: no explicit metrics for dispatch latency, offer acceptance rate, stale location percentage, ETA error, state-transition failure rate, or saga compensation rate.
- Security/privacy: no access control for tracking, location retention, GPS precision reduction after delivery, or auditability of support/admin access.
- Operations/cost: ETA/routing provider rate limits and fallback are not discussed.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Step view node ids resolve to canonical high-level nodes.
- Step view link ids resolve to high-level links.
- Option view nodes and links resolve.
- Sequence participants resolve to high-level node ids.
- `satisfies.functional[*].steps` and `satisfies.nonFunctional[*].steps` resolve to real step ids.
- `patterns[].steps` and `step.patterns` references resolve.
- Step `probeLinks` resolve to entries in `toProbeFurther.links`.
- `finalDesign.view.groups` resolves to `highLevelArchitecture.types`.
- No source-vs-generated docs edit is needed for this review-only change.

Renderer-facing improvement: if the dataset adds `LastKnownLocation`, `OrderEvents`, or `Outbox` nodes, update all affected step views, option views, final design view, and `satisfies` text together so the diagram diff remains meaningful.

## Recommended Edits, Prioritized

### P1: Make capacity concrete

Add assumptions and derived QPS/write-rate/fanout numbers for orders, location pings, dispatch matches, tracking sessions, and notification events. Tie each number to the component it sizes.

### P1: Expand data model for reliability

Add state transition history, idempotency keys, payment attempts, courier offer leases, and an outbox/event table.

### P1: Add lifecycle and dispatch APIs

Represent restaurant transitions, courier offer accept/decline, cancel, and idempotent state updates.

### P2: Add last-known location and order-event/outbox architecture nodes

Make prose-only mechanisms visible in high-level architecture, step views, option views, and final design.

### P2: Deepen dispatch failure handling

Document leases, CAS assignment, timeout requeue, stale courier filtering, and reassignment history.

### P2: Strengthen operations and privacy

Add observability metrics, access control for tracking, bounded location retention, and degraded mode for routing/ETA provider failure.

### P3: Add scale options

Turn the final scale step into explicit alternatives: regional partitioning, dynamic hot-cell splitting, GPS ping backpressure, dispatch batching, and degraded ETA mode.

## What Not To Change

- Preserve the current step order; it teaches the problem well.
- Keep the geo-index and dispatch alternatives; they are practical and non-strawman.
- Keep the saga step after tracking; the reader has enough happy-path context by then.
- Keep the `satisfies` mapping concise, but enrich it after adding concrete entities/APIs.

## Bottom Line

This is a strong book case with a clear interview narrative. The next revision should make the implicit production mechanisms explicit: numbers, lifecycle APIs, durable transition/idempotency records, offer leases, last-known location storage, and outbox/event publication. Those changes would move it from a solid conceptual design to a production-realistic flagship interview.
