# Review: Order Management System (OMS) - System Design

Reviewed file: `data/book/order-management/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent changes moved this from a strong outline to a mature OMS interview
case. The prior high-impact gaps around qualitative capacity, thin APIs, a
minimal data model, missing final flows, missing reconciliation, and absent
technology choices are now largely addressed. The dataset now has numeric load
assumptions, line-level order modeling, payment and WMS webhook APIs, richer
idempotency/reconciliation language, a `Reconciler` node, three final sequence
flows, and five technology-choice sections.

The remaining issues are more about precision than missing foundations. The
main one is the fulfillment handoff: the current flow says a WMS `shipped`
event triggers payment capture, which can conflict with the stated invariant
"never ship without payment" unless "shipped" means a pre-carrier handoff state.
The other opportunities are to make operational repair data more concrete, split
outbox table/relay/broker mechanics more clearly, and tighten a few API edge
cases.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | The core OMS mechanisms are credible; the ship/capture boundary needs sharper semantics. |
| Production realism | 4.25/5 | Strong on sagas, reservations, idempotency, callbacks, reconciliation, and line-level state; support/admin repair and provider limits could be more explicit. |
| Pedagogical flow | 4.5/5 | The sequence teaches one problem at a time and the recent transition-matrix concept improves the lifecycle step. |
| Step-to-final coherence | 4.5/5 | Final design now includes the components and flows introduced earlier, with only a few compressed operational details. |
| Dataset/rendering fit | 4.75/5 | Structured views, sequence references, highlights, step slugs, and canonical node types are internally consistent. |

## What Works Well

- The walkthrough has a clean interview arc: reject a single synchronous
  transaction, persist the lifecycle, reserve inventory, coordinate a saga,
  defer payment capture, publish status changes through an outbox, then handle
  cancellation/return compensation and scale.
- Capacity is now concrete: 1M/day baseline, 10M/day peak, roughly 350
  orders/sec at a 3x spike, item reservation writes, state writes, payment
  calls, outbox events, storage/day, and the distinction between order-id
  sharding and hot SKU+warehouse contention.
- The API surface now matches the architecture much better: order placement,
  order lookup, cancellation, returns, payment webhooks, and WMS shipment
  webhooks are all represented.
- The data model now carries the behavior promised by the narrative:
  `order_items`, `inventory_reservations`, `payment_attempts`, `shipments`,
  `returns`, `idempotency_keys`, and `outbox_events` are all present.
- The final design now includes `Reconciler / Ops Worker` and sequence flows for
  the happy path, payment ambiguity, and cancel-vs-return branches.
- Requirements now call out security/privacy and observability/operations rather
  than treating them as hidden production concerns.

## Highest-Impact Issues

### 1. The fulfillment flow blurs "ready to ship" and "shipped"

The dataset says the system must "never ship without payment." Step 5 and the
final happy-path flow say a warehouse `shipped` event arrives, then the order
service captures payment, consumes the reservation, and transitions the order.
If `shipped` means the package has left the warehouse or carrier handoff already
happened, the capture can fail after the item has shipped. That violates the
invariant the interview is trying to teach.

Concrete fix:

- Change the WMS event in Step 5 and the final happy path from `shipped` to
  `ready_to_ship`, `packed`, or `label_created`.
- Capture payment after that pre-ship event, then tell fulfillment to release
  the package to the carrier and mark the line `shipped`.
- Add a failure branch: if capture fails or auth expired, re-authorize/capture
  idempotently or park the order before carrier handoff.
- If the intent is that `shipped` means "ready for shipment" in this dataset,
  rename it anyway; interview candidates will usually read `shipped` as an
  irreversible external side effect.

### 2. Operational repair is named, but the data contract is still thin

The requirements mention stuck orders, support dashboards, audited support
actions, retry/DLQ counts, and manual repair. The architecture has a
`Reconciler / Ops Worker`, but the data model does not yet show the durable
objects that make those workflows reliable.

Concrete fix:

- Add `reconciliation_jobs` or `external_operations` for payment/WMS operations
  with provider IDs, next retry time, current state, and last error.
- Add `webhook_events` or equivalent dedupe records for payment and WMS
  callback IDs, signature validation result, received timestamp, and apply
  status.
- Add `support_actions` or `order_admin_audit` for who changed what, why, and
  which compensating action was triggered.
- Optionally add an admin/support API sketch for parking, replaying, or manually
  resolving stuck orders.

### 3. The outbox still compresses table, relay, and broker into one node

The data model and technology choices now describe outbox mechanics, relay, CDC,
broker, retries, and DLQ. The diagrams still use `Event Outbox / Bus` as a
single node. That is acceptable for a compact overview, but it hides a common
interview distinction: the outbox table is part of the local transaction, while
the relay and broker are separate delivery infrastructure.

Concrete fix:

- In the final design caption or view, split `Outbox` into `Outbox Table`,
  `Outbox Relay`, and `Event Broker` if the diagram can stay readable.
- Add a short sequence flow for transition commit -> outbox row -> relay publish
  -> notification consumer dedupe.
- Keep the warning that outbox is at-least-once delivery; consumers still need
  event-ID dedupe.

### 4. Capacity is quantified, but not tied to operational thresholds

The new capacity section is much better than before. The next step is to turn
the numbers into design thresholds: queue depth, retry budget, provider rate
limits, hot-SKU fallback behavior, and latency targets.

Concrete fix:

- Add target latency/SLO assumptions for order placement, status reads,
  fulfillment updates, and notification freshness.
- Estimate WMS/payment retry amplification during provider incidents.
- State when hot SKU+warehouse contention moves from conditional updates to a
  hold queue, token bucket, or pre-allocated reservation buckets.
- Mention PSP/WMS rate limits and backpressure, because external providers are
  often the limiting factor before the order store is.

### 5. API examples should tighten edge-case semantics

The APIs are now broad enough, but a few examples can be more precise.
`POST /v1/orders` includes `customerId` in the request body; in a secure retail
API this should normally come from the authenticated principal, or the example
should explicitly say it is validated. `POST /v1/orders/{id}/cancel` accepts
`lineIds`, but the sample response always says `"state": "cancelled"`, which is
wrong for partial cancellation.

Concrete fix:

- Say `customerId` is derived from auth context for customer calls, not trusted
  blindly from the body.
- Make cancel responses line-aware: `partially_cancelled`, per-line states, and
  refund/void status.
- Add webhook authentication/signature validation to the payment and WMS webhook
  descriptions.
- Include compensation status in responses where refund, void, release, or
  restock work is asynchronous.

## System Design Soundness

The requirements are now strong for an OMS interview. They cover multi-item
orders, line-level state, split shipments, cancellations/returns, idempotency,
crash resume, audit, scale, security/privacy, and operations. The one wording
to watch is the "never ship without payment" invariant; it should be reconciled
with the capture-on-shipment flow as described above.

The capacity model is credible and useful. It teaches that order volume turns
into multiple write streams: line reservations, state history, payment calls,
outbox events, and WMS callbacks. The best remaining addition is an operational
layer: latency targets, retry amplification, external provider budgets, and
backpressure behavior under WMS/PSP incidents.

The API and data model are now close to the design. The added webhook APIs are
important because OMS correctness depends on asynchronous provider events.
The added tables make line-level fulfillment, partial cancellation, returns,
provider IDs, idempotency, and outbox delivery explicit. The missing data is
mostly operational: webhook dedupe, reconciliation jobs, support actions, and
manual repair audit.

The architecture is sound: an order-service orchestrator owns state transitions,
inventory handles reservations, payment owns auth/capture/refund, fulfillment
integrates WMS, outbox handles status events, returns handles refund/restock,
and reconciliation handles ambiguous external work. The design correctly avoids
2PC and leans on local transactions plus compensation.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Synchronous Transaction

This remains a good rejected baseline. It creates the exact failures the rest
of the interview solves: no durable resume point, cross-service transaction
fantasy, and stranded payment/inventory side effects.

Improvement: keep explicitly framing this as an anti-pattern whose useful
output is the invariant list for the real design.

### Step 2: The Order Lifecycle State Machine

The added allowed-transition matrix concept is a meaningful improvement. It
makes the state machine concrete: triggers, guards, and invalid transitions are
checked rather than implied.

Improvement: consider adding a tiny line-state/aggregate-state example, because
the requirements now include partial shipment, partial cancel, and partial
return. That would connect this step even more directly to the later data model.

### Step 3: Inventory Reservation

This step is strong. It now consistently talks about atomic reservation per
SKU+warehouse rather than just an order-level decrement. The capacity section's
hot-SKU warning supports the lesson well.

Improvement: add one sentence about what happens when reservation TTL expires
while payment authorization is still ambiguous. That edge case connects
inventory, saga, and reconciliation.

### Step 4: Cross-Service Saga with Compensation

This is one of the strongest steps. The options compare orchestration,
choreography, and 2PC without strawmen, and the added ambiguity flow correctly
teaches "reconcile, don't blindly retry" for payment timeouts.

Improvement: the same ambiguity concept applies to WMS callbacks. A short note
that WMS state is also reconciled by event ID/status polling would round out
the provider story.

### Step 5: Fulfillment Orchestration

The auth-at-order/capture-before-shipment lesson is important and realistic.
The current wording needs the ship/capture boundary fix described in the first
highest-impact issue. This is the main remaining soundness gap in the walkthrough.

Improvement: model WMS as `packed/ready_to_ship -> capture -> release_to_ship`
instead of `shipped -> capture`. Then duplicate/out-of-order WMS callbacks can
be handled without implying the package already left unpaid.

### Step 6: Reliable Status Events (Outbox)

The outbox step is well placed and the traps are good. It correctly says the
outbox gives committed events at-least-once and consumers need dedupe.

Improvement: add one sequence flow or final-design split that shows outbox
table, relay, broker, and consumer dedupe. The technology choices already
contain the material; the teaching view just needs to surface it.

### Step 7: Cancellations, Returns, and Scale

This step is much better now that the data model supports line-level
compensation and return disposition. It still carries a lot of material:
cancellation, return, refund, restock, partial line handling, sharding, resume,
and operations.

Improvement: if the dataset grows again, split this into sub-steps or add a
more structured internal flow: cancel before ship, return after delivery, refund
failure, and restock disposition are different workflows.

## Final Design Review

The final design now integrates the step-level components cleanly. It includes
the Reconciler, uses the order store as the saga/state-machine source of truth,
keeps inventory and payment separate, routes through fulfillment/WMS, emits via
outbox, notifies the customer, and includes returns.

The three final sequence flows are the right set: happy path, payment
ambiguity, and cancel-vs-return. The payment ambiguity flow directly addresses
one of the old review's missing pieces.

The final happy path should be adjusted to avoid the "shipped before capture"
ambiguity. Otherwise the final design is coherent and does not introduce
unmotivated components.

## Concept Introduction and Learning Flow

The concept staging is strong:

- Step 2 introduces the state machine and transition guards.
- Step 3 introduces inventory reservation.
- Step 4 introduces saga, compensation, idempotent steps, and ambiguous payment
  reconciliation.
- Step 5 introduces auth/capture timing and WMS callback realism.
- Step 6 introduces transactional outbox and consumer dedupe.
- Step 7 introduces line-level compensation and return disposition.

Missing concepts worth adding, if there is room:

- Webhook event dedupe and signature validation.
- Support/admin repair workflow and audit trail.
- Backpressure/rate limits for PSP and WMS dependencies.
- A small aggregate-state derivation rule from line states.

## Step-to-Final-Design Coherence

The final design contains all major step-level nodes: client, gateway, order
service, order store, inventory, inventory store, payment, fulfillment,
warehouse/WMS, outbox, notification, returns, and reconciler. The data model and
final flows now preserve most of the details introduced along the way.

The remaining coherence gaps are narrow:

- Step 5 and final design need the same pre-ship capture semantics.
- Outbox internals are described in prose/data but compressed in the final view.
- Operations are named in requirements and architecture but not represented as
  durable support/reconciliation records.

## Realism Compared With Production Systems

This is now production-plausible for an interview case. It covers the hard OMS
themes: line-level state, inventory holds, saga resume, idempotency keys,
payment auth/capture/refund, WMS callbacks, returns, outbox delivery, and
reconciliation.

The remaining realism gaps are the kinds a senior interviewer may probe:

- Exactly when payment is captured relative to warehouse/carrier handoff.
- How webhook events are authenticated, deduped, ordered, and replayed.
- How support agents safely resolve stuck orders without breaking audit or
  double-refunding.
- How retry storms, DLQs, and external provider rate limits affect capacity.
- How aggregate order state is derived from line and shipment states.

## Dataset and Renderer-Facing Observations

- JSON parsing succeeds.
- No reviewed step uses raw Mermaid architecture diagrams; views are structured.
- Step view nodes and links resolve to high-level architecture entries.
- Explicit highlights resolve inside their views.
- Step and final sequence participants resolve for nested message blocks.
- `satisfies.functional[*].steps` and `satisfies.nonFunctional[*].steps` all
  resolve to real step IDs.
- Canonical node types used in the dataset are valid: `client`, `edge`,
  `orchestrator`, `database`, `service`, `external`, `queue`, and `worker`.
- `technologyChoices` is present and relevant. The payments concern is slightly
  schema-awkward because PSPs such as Stripe/Adyen/Braintree are described in
  tradeoff text but not represented as selectable chips.
- `finalDesign.flows` now has three useful sequence flows.
- The dataset has no generated AI visuals or explainer comic. That is optional,
  not a correctness issue.
- `toProbeFurther` has one link; adding a few more OMS/payment/WMS references
  would improve the wrap-up.

## Recommended Edits, Prioritized

### P1: Tighten fulfillment ship/capture ordering

Rename the WMS "shipped" trigger to `ready_to_ship` or `packed`, capture payment
before carrier handoff, then mark shipped only after capture succeeds. Update
Step 5, the final happy-path flow, and the WMS webhook example consistently.

### P1: Add operational repair persistence

Add durable records for reconciliation jobs/external operations, webhook event
dedupe, and audited support actions. This would make the `Reconciler / Ops
Worker` and support-dashboard requirement concrete.

### P2: Make outbox internals visible

Either split the final design into outbox table, relay, and broker nodes, or add
a short outbox sequence flow. Keep the at-least-once and consumer-dedupe lesson.

### P2: Tie capacity to thresholds and backpressure

Add latency/SLO assumptions, provider rate limits, retry amplification, queue
depth/backlog behavior, and hot-SKU fallback thresholds.

### P2: Refine API edge cases

Clarify customer identity from auth context, partial-cancel response states,
webhook signature validation, and async compensation status.

### P3: Add book polish

Add more probe links, optional AI visuals/explainer comic, and a cleaner way to
represent PSP choices in `technologyChoices`.

## What Not To Change

- Keep the current teaching order; it is still the dataset's biggest strength.
- Keep saga and outbox as separate steps; they solve different failure modes.
- Keep line-level state and compensation first-class.
- Keep the Reconciler in the final design; it is the right way to teach
  ambiguous external side effects.
- Keep the quantitative capacity model and the hot-SKU warning.

## Bottom Line

The recent changes closed the old major review gaps. This is now a credible,
book-quality OMS interview walkthrough. The highest-value next edit is to make
the warehouse/payment handoff precise so the design never implies a package can
ship before capture succeeds. After that, operational repair persistence and a
clearer outbox table/relay/broker split would move the case from strong to
excellent.
