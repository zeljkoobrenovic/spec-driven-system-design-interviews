# Review: DoorDash - Food Delivery - System Design

Reviewed file: `data/book/food-delivery/interview.json`
Review date: 2026-06-08

## Executive Summary

This review reflects the current dataset after the recent food-delivery revision. The prior high-impact gaps around capacity math, lifecycle APIs, reliability schema, offer leases, last-known location storage, and outbox/event publication have been materially addressed. The case is now a strong book-quality interview walkthrough with a credible production spine: durable order state machine, geo-indexed courier matching, live tracking via a last-known cache, saga compensation, transactional outbox, and region/cell scaling.

The remaining issues are narrower. The dataset should remove a few semantic inconsistencies around tracking reads and direct notification links, make the state machine's rejection/terminal states explicit, and turn several real failure modes into concrete flows rather than prose or follow-up questions. The design is no longer missing its core production mechanisms; the next improvements are about precision and operational completeness.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5 | Strong core architecture with concrete capacity, state, idempotency, geo, tracking, and outbox mechanisms. |
| Production realism | 4 | Good treatment of leases, retries, provider ambiguity, privacy, and degradation; still light on observability, connection fanout, and some edge workflows. |
| Pedagogical flow | 4.5 | Excellent step progression from baseline to lifecycle, geo, dispatch, tracking, saga, and scale. |
| Dataset/rendering fit | 4.5 | JSON and references resolve; remaining issues are semantic diagram/API consistency rather than schema breakage. |
| Overall | 4.5 | A strong flagship case that mostly needs final production polish. |

## What Works Well

- The recent revision fixed the old review's biggest concerns: capacity is now quantified, APIs include lifecycle and dispatch transitions, and the data model includes transition history, idempotency keys, payment attempts, courier offer leases, and outbox events.
- The narrative remains clear: the reader discovers one missing mechanism at a time instead of seeing the final architecture too early.
- Food delivery is modeled as a three-party workflow with restaurant readiness, courier availability, eater tracking, and payment compensation, not just a generic matching system.
- Dispatch is now much more credible: time-boxed offer leases, `expires_at`, `offer_version`, CAS accept, timeout requeue, assignment attempts, and stale/busy courier filtering are all named.
- The architecture now has first-class `LastKnown` and `OrderEvents` nodes, so the final design matches the core reliability and hot-read mechanisms described in prose.
- Privacy and graceful degradation are now explicit non-functional requirements, and the satisfies mapping explains how the design addresses them.

## Highest-Impact Issues

### 1. Tracking still mixes "read the stream" with "read last-known"

The final design correctly says tracking reads a materialized `LastKnown` cache, not the log-like `LocStream`. Some dataset surfaces still imply the older model: the `GET /v1/orders/{id}/track` API sequence reads "latest courier position" from `LocStream`, the high-level architecture still has a `locstream-tracking` link, and the scale step uses `locstream-tracking` in its main view.

Why it matters: this distinction is one of the interview's important lessons. Streams are for ingestion and fanout; last-known stores serve the current-position query. Mixing the two can confuse candidates and weakens the "do not query the log for latest state" teaching point.

Recommended edit: make the canonical tracking read path `LocStream -> LastKnown -> Tracking -> Eater` everywhere. Keep a stream-to-tracking path only if it is explicitly labeled as a push/update subscription, not a point read for latest position.

### 2. The state enum does not fully match the lifecycle prose

The lifecycle text includes restaurant rejection, and the restaurant-transition API accepts `reject`, but the `orders.state` enum does not include `rejected`. The enum also compresses some terminal/failure cases into `cancelled`, while the prose distinguishes restaurant rejection, eater cancellation before prep, refund after capture, and delivery/courier failure.

Why it matters: this interview teaches "state machine as source of truth." If the states are ambiguous, the candidate cannot reason precisely about allowed transitions, compensations, metrics, or support workflows.

Recommended edit: add a compact transition table and align the schema enum with it. At minimum, include `rejected` or document that restaurant rejection maps to `cancelled` with a reason. Consider explicit terminal states or reason fields for `cancelled_by_eater`, `rejected_by_restaurant`, and `delivery_failed` if the dataset wants to discuss support and refunds.

### 3. Direct notification links and outbox links need clearer progression

The final design correctly uses `OrderEvents` as the durable event/outbox path for notifications and dispatch. Earlier views still show `OrderSvc -> Notify` directly through the `order-notify` link. That can be acceptable as a teaching simplification in Step 2, but the dataset should say when the design moves from direct notification calls to durable outbox publication.

Why it matters: the reliability step's point is that "state persisted" and "event emitted" must not split-brain. A lingering direct link can make the final architecture look less reliable than the text claims.

Recommended edit: either label the Step 2 direct notification edge as the pre-reliability simplification, or introduce `OrderEvents` in Step 2 as "state-change event" and deepen it into the transactional outbox in Step 6. In final/reliability views, prefer `OrderSvc -> OrderEvents -> Notify`.

### 4. Several hard failure modes remain prose-only

The reliability step now names ambiguous payment callbacks, duplicate retries, and reassignment, but the only failure sequence still centers on restaurant rejection after payment authorization. Other practical failure branches remain in descriptions and follow-up questions.

Why it matters: food delivery systems fail at the edges: payment provider timeouts, restaurant app offline, courier accepts then disappears, routing provider throttling, and duplicate mobile retries. Showing one or two of these concretely would make the saga lesson much more production-realistic.

Recommended edit: add one additional sequence flow or failure drill for payment callback ambiguity and one for courier timeout/disappearance after accept. Show idempotency key lookup, state/version CAS, outbox event publication, and compensation/requeue in those flows.

### 5. Operations and safety are present, but not first-class enough

The dataset now mentions privacy, retention, degraded ETA, and alert-worthy follow-ups. It still lacks a concrete observability or policy surface: no metrics table, no explicit access check in the tracking API, no support/admin audit path, and no connection/fanout tier for hundreds of thousands of live tracking sessions.

Why it matters: a senior/staff-level food-delivery answer should show how the operator knows dispatch is failing before users do, and how location data is protected after assignment and delivery.

Recommended edit: add a small operations section or deepen the scale step with metrics such as dispatch latency, offer acceptance rate, stale location percentage, ETA error, order transition failure rate, saga compensation rate, outbox lag, and tracking connection count. For privacy, add an authorization check on tracking: only assigned active order participants can see courier location, with precision reduction after delivery.

## System Design Soundness

The core system design is now strong. Requirements cover the right domain shape: order placement, restaurant prep, courier dispatch, live tracking, notifications, order correctness, high-frequency location updates, reliability, dispatch quality, privacy, and graceful degradation. Capacity is no longer hand-wavy; it gives order QPS, live couriers, location writes, matching rate, tracking sessions, and freshness targets.

The architecture choices are credible. Order service owns the lifecycle, OrderDB is authoritative, `order_state_transitions` is the saga ledger, idempotency keys dedupe client and transition retries, `courier_offers` models dispatch leases, `OrderEvents` represents the outbox/event path, and `LastKnown` separates latest-position reads from the location stream.

The main design gap is precision around state semantics. If restaurant rejection and failed delivery are real transitions, they should appear in the state model or be explicitly represented as cancellation reasons. A second smaller gap is order placement depth: if this case wants to cover payment correctness in more detail, an `order_items` or `order_quote` snapshot would preserve menu price, fees, tax, and item choices at checkout. That can stay scoped out, but it should be intentional.

## Step-by-Step Pedagogical Review

### Step 1: Naive baseline

This step is now stronger because it explicitly calls out duplicate submissions and payment retry causing duplicate orders or double authorization. It motivates idempotency, lifecycle modeling, dispatch, tracking, and failure recovery cleanly.

Improvement: none required beyond keeping the baseline short. It does its job.

### Step 2: The Order Lifecycle State Machine

This is still the right backbone. The step explains allowed actors, prior states, notification events, and the order store as source of truth.

Improvement: add a compact transition table with actor, from-state, to-state, and compensation. Align it with the data model enum, especially restaurant rejection and cancellation branches.

### Step 3: Live Courier Locations

The geo step is solid. It now ties the 25K writes/sec peak to stream/index design, names stale-location filtering, distinguishes available vs on-delivery couriers, and discusses bounded location retention.

Improvement: keep the default geohash/S2 choice, but add one sentence about partition keys and hot-cell mitigation linking forward to Step 7.

### Step 4: Dispatch

This is one of the strongest steps. It now teaches offer leases, CAS accept, timeout requeue, `assignment_attempts`, stale/busy filtering, and the trade-offs between greedy, batched, and broadcast dispatch.

Improvement: if the data model is expanded later, add a small courier availability/state entity or clarify that `courier_location.status` is the authoritative live availability record used by dispatch.

### Step 5: Live Tracking and ETA

The tracking step is much improved by the `LastKnown` cache and the push-vs-polling alternatives. The option text correctly warns that millions of persistent connections need a connection/gateway tier.

Improvement: make the API sequence and scale diagram match the step: tracking should read `LastKnown`, not `LocStream`. If push is the default, consider adding a `ConnectionGateway` or `RealtimeGateway` node in the final design or tracking option.

### Step 6: Consistency Across Failures

The saga step now has the right ingredients: idempotency keys, CAS on expected state/version, transition log, payment attempts, and transactional outbox. This is a major improvement over the previous review.

Improvement: add one more concrete flow for a failure that is not restaurant rejection. Payment provider ambiguity and courier disappearance after accept are the highest-value choices.

### Step 7: Scaling Spikes, Geo Hotspots, and Regions

The scale step is now much more actionable. Region/cell partitioning, hot-cell splitting, GPS-ping backpressure, and degraded ETA mode are all useful options.

Improvement: update the main scale view so it uses `LastKnown` consistently and shows the regional/cell partitioning idea more visibly. The current text is better than the diagram.

## Final Design Review

The final design is coherent and now integrates the major mechanisms introduced by the steps. It says each transition is persisted with an idempotency key and emitted through a transactional outbox, dispatch uses time-boxed offer leases, courier pings feed a region-partitioned stream, tracking reads a last-known cache, and provider failure degrades to coarse ETA rather than failing the order.

The final diagram is also much closer to the prose than before because it includes `OrderEvents` and `LastKnown`. The remaining omissions are acceptable for an interview but worth noting: there is no explicit real-time connection tier, no observability/alerting component, no admin/support audit path, and no visual indication of per-region/cell partitioning beyond captions.

## Concept Introduction and Learning Flow

Concepts are introduced in a strong order. The baseline exposes the pain; the state machine gives the durable source of truth; geo indexing enables dispatch; dispatch enables assignment; tracking consumes the location pipeline; saga reliability arrives after the happy path is visible; scale then makes the hot paths concrete.

The next learning-flow improvement is to mark when an early simplification is deliberately replaced. Step 2 can show direct notification as a simple event concept, but Step 6 should clearly upgrade it to transactional outbox. Step 5 can discuss streams for ingestion, but all later surfaces should consistently teach last-known materialization for reads.

## Step-to-Final-Design Coherence

Coherence is high. Every step now contributes a visible final-design mechanism: lifecycle state in `OrderDB`, payment in `PaySvc`, dispatch in `Dispatch`, geo in `GeoIndex`, pings in `LocStream`, tracking in `LastKnown` and `Tracking`, and reliability in `OrderEvents`.

The weakest transition is still from the scale step to the final design. The text says per-region dispatch and region/cell partitioning, but the final design remains a single logical instance of each component. That is acceptable if the final diagram is logical, but a caption should explicitly say each stream/index/dispatch box is region-partitioned.

## Realism Compared With Production Systems

The dataset now captures many real production concerns: high-frequency location writes, stale courier filtering, time-boxed offer leases, idempotency, provider ambiguity, outbox publishing, privacy, retention, and degraded routing/ETA.

Remaining realism gaps:

- Payment workflows: auth expiry, duplicate callbacks, capture failure, refund status, and reconciliation jobs could be clearer.
- Restaurant operations: tablet/app offline, delayed rejection, prep-time estimate changes, and busy-restaurant throttling are not deeply modeled.
- Courier operations: app reconnect, spoofed GPS, accept-then-disappear, reassignment after pickup, and fairness are mostly follow-ups.
- Tracking operations: connection fanout, reconnect/backfill, and authorization checks need more concrete treatment.
- Observability: the case should name metrics and alerts tied to dispatch, tracking, outbox, saga, and ETA quality.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Step and option view node ids resolve to canonical `highLevelArchitecture.nodes`.
- Step and option view link ids resolve to `highLevelArchitecture.links`.
- Sequence participants in API and step flows resolve to high-level node ids.
- `satisfies.functional[*].steps`, `satisfies.nonFunctional[*].steps`, and `patterns[].steps` resolve to real step ids.
- `finalDesign.view.groups` resolves through `highLevelArchitecture.types`.
- The remaining renderer-facing concern is semantic, not structural: several valid links still imply direct stream-to-tracking reads or direct order-to-notification calls where the final design prefers `LastKnown` and `OrderEvents`.
- No docs rebuild is needed for this review-only change.

## Recommended Edits, Prioritized

### P1: Make tracking read path consistent

Change the track API sequence, high-level link usage, and scale views so latest-position reads go through `LastKnown`. Keep stream-to-tracking only for an explicitly named push/update feed.

### P1: Align the lifecycle state model

Add a transition table and align `orders.state` with restaurant rejection, cancellation, refund, and delivery failure semantics.

### P1: Clarify direct notification vs transactional outbox

Make the progression explicit: early direct notification is a simplification, while the reliable design routes state-change publication through `OrderEvents`.

### P2: Add one or two concrete failure flows

Add sequence flows or drills for payment callback ambiguity and courier disappearance after accept, showing idempotency, CAS, outbox publication, and compensation.

### P2: Add operational metrics and privacy enforcement

Name metrics/alerts and show tracking authorization or access policy around courier location visibility.

### P2: Consider a connection fanout component

If push remains the default tracking option, add a `RealtimeGateway` or similar component to make hundreds of thousands of live tracking sessions concrete.

### P3: Expand order placement only if in scope

If payment/order correctness is meant to be deeper than logistics, add order item or quote snapshot entities. Otherwise, explicitly keep menu/catalog/order-line details out of scope.

## What Not To Change

- Preserve the current step order; it teaches the design well.
- Keep the concrete capacity assumptions; they now anchor the whole case.
- Keep the geo-index and dispatch alternatives; they are practical and balanced.
- Keep the data model additions for transitions, idempotency, payment attempts, offer leases, and outbox events.
- Keep the final design focused on logistics and lifecycle reliability rather than expanding into every DoorDash adjacent subsystem.

## Bottom Line

The food-delivery interview has moved from a good conceptual design to a strong production-oriented case. The previous P1 gaps are largely fixed. The next pass should be a consistency and operations pass: tracking reads through last-known everywhere, state enum and transition prose line up, notification paths clearly evolve into outbox publication, and the hardest failure modes become concrete flows.
