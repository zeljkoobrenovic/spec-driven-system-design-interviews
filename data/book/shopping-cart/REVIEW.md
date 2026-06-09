# Review: Shopping Cart & Order Management - System Design

Reviewed file: `data/book/shopping-cart/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong teaching case with a clean arc: expose the naive cart/checkout
failure, split carts from orders, add pricing, reserve inventory, coordinate
checkout as a saga, publish order events through an outbox, and scale the cart
and order workloads independently.

The biggest gaps are not schema failures. They are places where the dataset says
the right production words but leaves the underlying state model ambiguous. The
checkout flow currently charges before it creates an order even though the
requirements say "never charge without an order"; the inventory step mixes CAS
decrement and TTL reservations; and the order state/outbox path is not backed by
data-model entities. These are fixable, but they are important because they are
exactly the parts an interviewer will push on.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 3.5/5 | Good architecture shape, but checkout, reservation, payment, and order-state invariants need tighter state modeling. |
| Production realism | 3/5 | Covers sagas, idempotency, reservations, and outbox, but under-specifies payment authorization/capture, webhook ambiguity, cancellation, recovery, and operations. |
| Pedagogical flow | 4/5 | The seven-step progression is clear and useful; the main issue is that some steps combine multiple production decisions without making the chosen invariant explicit. |
| Dataset/rendering fit | 4/5 | JSON parses and references resolve; one final-design diagram relationship is misleading, and book-level enrichment fields are missing. |
| Overall | 3.5/5 | Usable and coherent as a walkthrough, with a focused follow-up pass needed before treating it as a flagship commerce case. |

## What Works Well

- The dataset focuses on the right core problem: cart intent is availability-first, while checkout, inventory, payment, and orders are correctness-critical.
- The naive baseline is effective because it exposes cart volatility and the impossible "one transaction across payment, inventory, and order" assumption.
- Step ordering is strong: persistent cart, pricing, inventory reservation, idempotent saga, order state/outbox, and scaling each solve the previous step's exposed weakness.
- The API includes the important public surfaces: cart item update, cart read, idempotent checkout, and cancellation.
- The patterns, traps, failure drills, interview script, level variants, and follow-ups are concrete enough to help a candidate practice.
- Structured views and sequences are used consistently; there are no raw step/final-design Mermaid diagrams.

## Highest-Impact Issues

### 1. Checkout charges before the order exists, conflicting with the stated invariant

The non-functional requirements say "never charge without an order." But the
checkout API sequence and Step 5 flow are `reserve -> charge -> create order`,
and the failure drill explicitly handles "Payment ok but order-create fails" by
refund and release. That is a valid saga failure mode, but it means the design
does temporarily charge without an order, which weakens the advertised invariant.

Why it matters: payment systems can be asynchronous, refunds are not immediate,
webhooks can arrive later, and support/reconciliation need a durable local record
before money moves. A candidate should not imply that refund compensation is the
same as never entering the bad state.

Concrete fix: model a durable `checkout_attempt` or `orders` row before capture.
One production shape is `reserve inventory -> create PENDING_PAYMENT order with
frozen price and reservation IDs -> authorize payment using order/checkout ID as
the gateway idempotency key -> mark PAID and capture -> emit order.paid via the
outbox`. If capture happens before the final order transition, explicitly state
the temporary risk and the reconciliation workflow.

### 2. Inventory reservation semantics mix two different defaults

Step 4's description says checkout creates a short-lived reservation with TTL.
The default option is named "CAS decrement of available", which sounds like a
plain atomic counter decrement. The second option is "Reservation hold with TTL".
The final design then says "atomic CAS holds with TTL." The data model includes
`reservations`, so the intended answer seems to be a CAS-protected reservation
hold, but the option list teaches it as two competing designs.

Why it matters: this is the oversell invariant. Candidates need to state exactly
what is authoritative: `available`, `reserved`, `sold`, active holds, or a
combination. Without that, release-on-expiry, payment failure, duplicate retries,
and reconciliation are hand-wavy.

Concrete fix: choose the default explicitly, for example "CAS create hold with
TTL". Add reservation state fields such as `checkout_id`, `idempotency_key`,
`status(held, confirmed, released, expired)`, `created_at`, `expires_at`, and a
unique key for `(checkout_id, sku)`. State the invariant, such as `available +
reserved + sold = stock_on_hand`, and describe the sweeper/reconciler that
expires stale holds.

### 3. The order state machine and outbox are asserted but not modeled

Step 6 correctly introduces guarded transitions and a transactional outbox, but
the data model only has an `orders.status` enum. There is no `order_events`,
`outbox`, `shipments`, `fulfillment_attempts`, transition table, event ID, or
consumer dedupe state. The cancel API also says it compensates based on current
state, but the legal-state matrix is not defined.

Why it matters: "outbox + idempotent consumers" is a production pattern only if
the data that makes it reliable is visible. Without the table shape and transition
rules, the walkthrough risks turning an important correctness mechanism into a
diagram label.

Concrete fix: add an `outbox_events` table and either an `order_events` table or
an explicit state transition section. Include event ID, aggregate ID, event type,
payload, status, attempt count, and published timestamp. Add a cancellation
matrix: pending payment can release holds, paid-not-fulfilled can void/refund and
release, fulfilled becomes return/refund flow rather than simple cancel.

### 4. Capacity and reliability claims are too qualitative for the design choices

The capacity section gives useful headline numbers (`~50k/s` cart operations,
`~2k/s` checkouts, hundreds of millions of active carts), but it does not convert
them into data size, storage, partitioning, throughput, backlog, or failover
requirements. It also says an accepted order survives service/region failure, but
the architecture does not specify replication, RPO/RTO, idempotency-store
recovery, or outbox replay after regional failover.

Why it matters: the final step recommends sharded AP cart storage and a
consistent order database, but the capacity math does not justify shard counts,
cart TTL storage, order write volume, inventory hotspot treatment, or whether one
region can safely own checkout.

Concrete fix: add assumptions and ranges: average cart payload size, cart TTL,
daily active carts, order line count, checkout write amplification, idempotency
record retention, inventory hot-SKU QPS, queue/outbox throughput, and order DB
replication target. Name the multi-region stance: active-passive checkout with
regional cart stores, active-active carts with single-writer orders, or another
explicit model.

### 5. The final design diagram makes the Cart Service relationship unclear

The final design includes `Cart` but links `API -> Router -> ShardA/ShardB` and
`Cart -> ShardA`; it does not show the Commerce API calling the Cart Service or
the Cart Service using the shard router. Step 2 teaches `API -> Cart -> CartStore`,
so the final view makes the Cart Service look partially disconnected.

Why it matters: the final diagram is the visual synthesis of the walkthrough.
If a component is shown but not on the request path, readers can infer that carts
are written directly through the API/router, bypassing the Cart Service.

Concrete fix: change the final view to `Client -> API -> Cart -> Router ->
ShardA/ShardB`, or `API -> Cart` and `Cart -> ShardA/ShardB` if the router is
folded into the Cart Service.

## System Design Soundness

The requirements identify the right business invariants: cart persistence,
pricing, inventory correctness, checkout idempotency, order durability, and
separate scaling profiles. The main wording problem is "never charge without an
order." The current saga can recover from that state, but it does not prevent it.
Either the requirement should be softened to "never leave a charge without a
recoverable order or compensation record" or the design should create durable
order/checkout state before capture.

The API shape is good but underspecified. `POST /v1/checkout` should describe
what happens when the same idempotency key arrives with a different payload, when
the first request is still `in_progress`, and whether the response is a final
order or an accepted checkout attempt. `PUT /v1/carts/{id}/items` should state
that the cart is scoped to the authenticated user/session to avoid insecure
direct object reference problems, and it should mention versioning or merge rules
for multi-device cart edits.

The data model is enough for a high-level sketch, but not enough for the
correctness claims. It needs price snapshots, reservation state, payment attempt
state, outbox events, and order event history. `orders.items` should include
currency, unit price, discounts, tax, and promotion/coupon snapshot fields if the
dataset wants to claim that checkout pricing is honored. Coupon usage limits
also need an authoritative record if the pricing step wants to prevent abuse.

The architecture split is sound: AP carts, CP inventory/orders, pricing on the
checkout path, idempotency store, payment boundary, and outbox to fulfillment.
The weaker areas are operational: no backpressure/admission control during hot
inventory events, no payment webhook/reconciliation path, and no explicit
regional failover strategy for orders and idempotency.

## Step-by-Step Pedagogical Review

### Step 1: Naive Cart & Buy (the baseline)

This is a useful baseline. It exposes volatile carts and the cross-service
transaction problem quickly. Keep this as the opening contrast.

One improvement: make the failure example include "payment provider accepted the
charge but the local order write failed" so the later payment/order-state fix is
motivated before Step 5.

### Step 2: Persistent Cart Store

The availability-first cart framing is strong, and guest-to-user merge is a good
commerce-specific concept. The AP cart store default is the right default for a
large shopping workload.

The failure drill says an occasional lost write is acceptable and recoverable at
checkout. That is too casual for a logged-in cart. Better wording: writes can be
retried and reconciled, stale replicas are acceptable for reads, and checkout
revalidates price/stock, but confirmed cart mutations should not simply vanish.
Add cart versioning or last-write-wins merge semantics for multi-device edits.

### Step 3: Pricing & Promotions

This step teaches a real trade-off: display pricing can be approximate or live,
but checkout must freeze the authoritative total. The options are good because
they contrast reprice-at-checkout, lock-at-add, and short-TTL price locks.

The data model should support the lesson. Add `price_quote_id` or order-line
snapshot fields for unit price, currency, discount, tax, promo IDs, coupon code,
and quote expiration. If coupon limits matter, add a coupon redemption ledger or
make it clear that the promotion system owns that state.

### Step 4: Inventory Reservation & Oversell Prevention

This is the right place for the hardest inventory concept, and the race sequence
is helpful. The step should be tightened so the default is not ambiguous between
plain CAS decrement and TTL reservation.

The strongest teaching version is to say: a conditional write creates or updates
a hold only if enough stock remains; the hold has a TTL; payment success confirms
it as sold; failure or expiry releases it. That preserves both oversell
prevention and abandoned-checkout recovery.

### Step 5: Checkout as a Saga (idempotent)

This is the central step and it has the right vocabulary: orchestrator,
idempotency key, compensation, release reservation, refund. It needs a more
precise order/payment sequence.

Add durable checkout state, gateway payment IDs, retry status, and reconciliation.
Payments should distinguish authorization, capture, void, refund, and asynchronous
webhook confirmation. The idempotency store should say how long keys are retained
and how payload mismatch is handled.

### Step 6: Order State Machine & Fulfillment

The outbox option is correct and should remain the default. The step should make
the state machine concrete: legal transitions, transition owner, event names, and
consumer dedupe key.

Add a small state table or diagram for `created/pending_payment`, `paid`,
`fulfillment_requested`, `fulfilled`, `cancel_requested`, `cancelled`, and
`failed`. The current enum skips several states a real system needs to avoid
shipping cancelled orders or refunding fulfilled orders incorrectly.

### Step 7: Scaling Carts vs Orders

This is a good synthesis step. It reinforces that carts and orders deserve
different stores and consistency models.

It would be stronger with concrete scaling mechanics: cart shard key, shard
rebalance strategy, hot-key handling, order partitioning key, order lookup paths,
and what happens when the cart store is multi-region but checkout/orders are
single-writer.

## Final Design Review

The final design includes the right components: shopper app, Commerce API,
sharded cart storage, pricing/promotion rules, checkout orchestrator,
idempotency store, inventory service/store, payment system, order service/DB,
outbox, queue, and fulfillment.

The final design should be revised to match the decisions made in the steps:
make Cart Service visibly own cart writes, choose CAS TTL holds as the inventory
default, create durable checkout/order state before or alongside payment, and
back the outbox with a data model. Once those are explicit, the design will read
as coherent end to end.

## Concept Introduction and Learning Flow

The concept sequence is strong. Each concept appears near the step that needs it:
distributed transactions, AP carts, price freezing, reservation TTL, CAS,
orchestrated saga, compensation, guarded transitions, transactional outbox, and
workload separation.

The only learning-flow weakness is that Step 4 and Step 5 each introduce two
important choices at once. Step 4 combines "atomic decrement" with "reservation
hold"; Step 5 combines "saga" with "payment ordering". Split those concepts more
deliberately and the interview will be easier to defend under follow-up
questions.

## Step-to-Final-Design Coherence

Most step-to-final-design links are present. The final design carries forward
the cart split, pricing service, checkout orchestrator, idempotency store,
inventory, payment, order DB, outbox, queue, and fulfillment.

The coherence gaps are specific: the final diagram's Cart Service path differs
from Step 2, the final text chooses CAS holds with TTL while the inventory
default is labeled CAS decrement, and the final design mentions outbox events
without a data-model backing table.

## Realism Compared With Production Systems

For an interview, the case is realistic enough to teach the right shape. For a
production-shaped book dataset, add more detail in these areas:

- Payment lifecycle: authorization, capture, void, refund, gateway idempotency,
  asynchronous webhooks, and reconciliation jobs.
- Inventory lifecycle: hold, confirm, release, expire, reconciliation against
  warehouse or ERP stock, and hot-SKU admission control.
- Order lifecycle: legal transition matrix, event history, cancellation rules,
  partial shipment, and return/refund handoff.
- Security and privacy: authenticated cart ownership, guest cart token security,
  address/payment token handling, PII retention, audit logs, and fraud checks.
- Operations: SLOs, metrics, alerting, runbooks, outbox lag, stuck checkouts,
  reservation expiry lag, payment reconciliation mismatches, and fulfillment
  duplicate suppression.

## Dataset and Renderer-Facing Observations

- JSON parses successfully.
- Step view nodes resolve to `highLevelArchitecture.nodes`.
- Step view string links, option view string links, and final-design string
  links resolve to `highLevelArchitecture.links`.
- `satisfies.functional[*].steps` and `satisfies.nonFunctional[*].steps` resolve
  to real step IDs.
- Structured sequence data is used for API and step flows.
- `highLevelArchitecture.types` is empty. That is schema-valid, but grouped
  architecture categories would make larger diagrams easier to scan.
- `technologyChoices`, `aiVisuals`, and `explainerComic` are absent. They are
  optional, but this book dataset would benefit from technology choices for cart
  KV stores, order databases, inventory conditional writes, workflow engines,
  payment providers, queues, and observability.
- Several `probeLinks` are too generic or mismatched. For example, `cart-store`
  points only to `debezium-outbox`, and `pricing` points to outbox/isolation
  links rather than pricing, coupon, tax, or payment references.
- `REVIEW.md` is repo-only; no docs rebuild is needed for this review file.

## Recommended Edits, Prioritized

### P1: Align checkout, payment, and order state

Revise the checkout flow so the "never charge without an order" invariant is
true or reword the invariant to match a compensating saga. Add checkout/payment
state with authorization, capture, void/refund, gateway IDs, webhook handling,
and reconciliation.

### P1: Make inventory reservation the explicit default

Rename or revise the default option to CAS-protected TTL reservation. Add
reservation status fields and state the inventory invariant. Show confirm and
release/expire paths.

### P1: Add order events/outbox and legal transitions to the data model

Back Step 6 with `outbox_events` and order-event/history state. Define legal
cancel/refund/fulfillment transitions and idempotent consumer dedupe keys.

### P2: Add capacity math and regional reliability assumptions

Turn the capacity bullets into assumptions that justify cart storage, shard
counts, checkout write throughput, idempotency retention, order DB replication,
outbox throughput, and regional failover behavior.

### P2: Add price quote and order-line snapshot state

Persist authoritative checkout price, currency, tax, discount, coupon/promo IDs,
quote expiry, and coupon usage/redemption state.

### P2: Tighten cart API and merge semantics

State authentication/session ownership, cart versioning, conflict handling, and
guest-to-user merge rules. Avoid implying that confirmed cart writes can be
silently lost.

### P3: Fix the final design diagram path

Show the Commerce API calling the Cart Service, and show the Cart Service using
the shard router or shards. Keep the visual consistent with Step 2.

### P3: Retarget probe links and add book enrichments

Add better step-level links for cart stores, pricing/tax/coupons, payment
lifecycle, reservation patterns, and workflow/outbox operations. Consider adding
`technologyChoices` for the book group's wrap-up experience.

## What Not To Change

- Keep the seven-step arc.
- Keep the naive baseline.
- Keep AP carts separate from CP orders/inventory.
- Keep server-side pricing and checkout-time price freeze.
- Keep idempotency key and saga compensation as central concepts.
- Keep transactional outbox as the default fulfillment event pattern.
- Keep the scaling step as synthesis rather than moving it earlier.

## Bottom Line

The dataset already teaches the right shopping-cart and checkout architecture.
The next pass should make the correctness state explicit: checkout/order/payment
ordering, reservation lifecycle, order events/outbox, and capacity/reliability
assumptions. That would turn a good walkthrough into a production-realistic
commerce interview case.
