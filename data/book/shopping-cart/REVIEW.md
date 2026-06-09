# Review: Shopping Cart & Order Management - System Design

Reviewed file: `data/book/shopping-cart/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent changes materially improved this dataset. The previous top risks
around checkout ordering, reservation lifecycle, and outbox modeling are mostly
resolved: the API sequence now creates a durable `PENDING_PAYMENT` order before
payment capture, reservations have TTL/status fields, `order_events` and
`outbox_events` are present, capacity math is more concrete, and the final
diagram now shows the Cart Service on the sharded cart path.

The dataset is now a strong book-quality walkthrough. The remaining problems
are narrower: a few rendered captions and the Design vs. Requirements mapping
still teach the old `reserve -> charge -> create order` sequence; the payment
and pricing records are still compressed into too few fields for the lifecycle
claimed in the text; and the inventory invariant names `sold` and
`stock_on_hand` without modeling them explicitly.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.2/5 | Correct architecture split and much clearer checkout invariant; a few state records need to catch up with the prose. |
| Production realism | 4.0/5 | Payment reconciliation, TTL holds, idempotency, and outbox are present; payment attempts, webhook dedupe, coupon redemption, and hot-SKU operations remain thin. |
| Pedagogical flow | 4.5/5 | The seven-step progression is coherent and teaches one major pressure at a time. |
| Dataset/rendering fit | 4.1/5 | JSON and references are clean, but stale captions/cross-references will confuse readers in the rendered step views. |
| Overall | 4.2/5 | Strong and usable; one focused cleanup pass would make it a polished flagship commerce case. |

## What Works Well

- The scope is clear: carts are user intent and availability-first; checkout,
  orders, inventory, and payment are correctness-critical.
- The revised non-functional invariant is honest: "never leave a charge without
  a recoverable order or compensation record" fits a real saga better than a
  strict "never charge before order" claim.
- Capacity now gives useful operating numbers: cart working set, checkout write
  amplification, hot-SKU contention, idempotency retention, outbox throughput,
  and single-writer order durability.
- The checkout API and sequence now create `PENDING_PAYMENT` before capture and
  specify idempotency-key replay, payload mismatch, and in-progress responses.
- The data model now includes `order_events`, `outbox_events`, reservation
  status/TTL fields, cart versioning, frozen order-line price fields, and
  idempotency retention.
- Step 6's legal-transition and cancellation deep dive is a strong addition.
- The final design now integrates the Cart Service with the shard router, so
  the final architecture matches the earlier cart-store step.

## Highest-Impact Issues

### 1. Some rendered checkout text still uses the old charge-before-order order

Most of the dataset now says the right thing: reserve inventory, create a
durable `PENDING_PAYMENT` order, authorize/capture payment, then mark the order
paid and confirm holds. But three places still say or imply the old order:

- `steps[checkout-saga].view.caption` says the orchestrator "reserves
  inventory, charges the Payment System, and creates the order."
- The default `checkout-saga` option `view.caption` says it drives reserve,
  charge, and create in that order.
- `satisfies.functional` for "Check out to an order" says "Idempotent saga:
  reserve -> charge -> create order."

Why it matters: these are rendered in the walkthrough and wrap-up, so a reader
can leave with the exact inconsistency the recent changes were meant to fix.

Concrete fix: update those captions/mappings to
`reserve -> create PENDING_PAYMENT order -> authorize/capture -> mark PAID and
confirm holds`. If the diagram is kept as a flowchart with unordered edges,
make the caption carry the sequence unambiguously.

### 2. Payment lifecycle is well explained but under-modeled

Step 5 now has a good payment deep dive: order before money, gateway idempotency,
authorize/capture/void/refund, webhooks, and a reconciler. The data model still
collapses that lifecycle into `orders.payment_ref` and `orders.payment_status`.

Why it matters: retry safety at a payment boundary usually depends on durable
attempt records, gateway request/response IDs, webhook dedupe, and reconciliation
state. Without those records, the prose is stronger than the model.

Concrete fix: add a `payment_attempts` table or section with `attempt_id`,
`order_id`, `gateway_intent_id`, idempotency key, amount/currency, status,
failure code, created/updated timestamps, and last gateway response. Add a
`payment_webhook_events` or dedupe record keyed by gateway event ID. Tie the
reconciler to stale `PENDING_PAYMENT` orders and incomplete attempts.

### 3. The inventory invariant is named but not fully represented

Step 4 states the invariant `available + reserved + sold = stock_on_hand`, and
the reservation model is much better than before. The `inventory` table,
however, only lists `available`, `reserved`, and `version`; there is no
`stock_on_hand`, no `sold`/confirmed count, and no explicit explanation that
sold is derived from paid order lines or confirmed reservations.

Why it matters: this is the core "never oversell" guarantee. If the invariant is
named, the model should show where each term comes from and how expiry,
confirmation, and reconciliation preserve it.

Concrete fix: add `stock_on_hand` and either `sold`/`confirmed` counters or an
explicit note that sold is derived from immutable paid order lines. State the
state transitions: held increments `reserved`, confirmed moves reserved to
sold, released/expired decrements reserved. Add a sweeper/reconciler note for
stale holds.

### 4. Pricing and coupon correctness need one more data-model pass

Step 3 says pricing is recomputed server-side, coupons are validated at
checkout, and frozen into the order. The order item JSON includes unit price,
currency, discount, tax, promo IDs, and coupon code, which is good. But the
model does not show a `price_quotes` record, coupon redemption ledger, tax
calculation source, or promotion usage limits.

Why it matters: "pricing shown at checkout is honored" and "coupon limits are
validated" are correctness claims. They need a durable quote/snapshot and an
authoritative redemption record when coupons have usage limits.

Concrete fix: add `price_quotes` or make the order itself the quote record with
clear fields for quote version, expiry, and source rule versions. Add
`coupon_redemptions` keyed by user/coupon/order or state that the Promotion
service owns redemption idempotency and limits.

### 5. Hot-SKU and regional operational behavior is mentioned but not taught

Capacity now acknowledges hot SKUs at hundreds to thousands of writes per second
and says admission control or sharded counters may be needed. The actual steps
do not teach what happens when one SKU melts the inventory row, and the final
architecture does not show any admission/backpressure path.

Why it matters: flash-sale contention is a common e-commerce follow-up. The
dataset should either keep it explicitly out of scope or show the first
production answer.

Concrete fix: add a failure drill or deep dive under Step 4/Step 7: per-SKU
admission tokens, queueing, waitlists, sharded reservation buckets with final
settlement, or a single-writer partition for the hot SKU. State how this fits
the single-writer order/checkout region.

## System Design Soundness

The requirements are now aligned with a realistic commerce system. The updated
non-functional wording no longer over-promises absolute prevention of every
temporary bad state; it focuses on recoverability and compensation. That is the
right framing for payment and order workflows.

The capacity section is much stronger than before. It translates headline
traffic into cart storage size, checkout write amplification, idempotency
retention, outbox throughput, hot-SKU contention, and an order RPO stance. The
single-writer order/checkout region plus active-active AP carts is a defensible
default.

The API is credible. `PUT /v1/carts/{id}/items` covers ownership, LWW/versioned
multi-device edits, and checkout revalidation. `POST /v1/checkout` now specifies
the important idempotency cases: replay, mismatching payload, and in-progress
attempt. One small improvement: make `idempotency_keys.order_id` nullable or
separate success/failure result records, because out-of-stock or validation
failures may complete without an order.

The data model has caught up with most of the design. It now supports cart
versioning, frozen price snapshots, reservation status/TTL, idempotency
retention, order events, and outbox events. The remaining soundness gaps are
payment attempts/webhook dedupe, inventory invariant fields, and coupon/quote
records.

The architecture split is good: AP cart storage, CP inventory/order storage,
pricing on the checkout path, an idempotent checkout orchestrator, external
payment boundary, transactional outbox, event queue, and fulfillment consumer.

## Step-by-Step Pedagogical Review

### Step 1: Naive Cart & Buy (the baseline)

This remains a good baseline. It immediately exposes two failures: volatile cart
state and the false assumption that payment, inventory, and order creation can
be one local transaction.

The step could add one sentence foreshadowing the revised invariant: the worst
case is not just a failed request, but money moved or stock held without a
recoverable local record.

### Step 2: Persistent Cart Store

This step is strong. It correctly treats the cart as user intent, separates cart
storage from order/inventory storage, and now avoids the old "lost writes are
fine" phrasing by mentioning per-line LWW or versioned merge semantics.

One possible addition is guest-cart token security: guest cart IDs should be
unguessable and bound to a session/device so cart ownership is not just a path
parameter.

### Step 3: Pricing & Promotions

The teaching arc is good: display pricing can be refreshed, but checkout must
recompute and freeze the authoritative total. The options compare real choices:
reprice at checkout, lock at add, and short TTL price locks.

The next improvement is data support. Add a quote or redemption model so the
reader can see how a frozen price, tax rule version, promotion IDs, and coupon
usage limit survive retries and audits.

### Step 4: Inventory Reservation & Oversell Prevention

This step is much clearer after the revisions. The default is now a
CAS-protected TTL hold, not an ambiguous plain decrement. The race sequence is
useful and the trap list teaches why separate read/write stock updates fail.

Tighten the model around the stated invariant. If `sold` is not a column, say
where it is derived from. Add expiry lag and reconciliation metrics so the TTL
hold story has an operational endpoint.

### Step 5: Checkout as a Saga (idempotent)

This is now the centerpiece of the dataset and it mostly works. The revised
description, API sequence, deep dive, traps, failure drill, and final design all
teach the right production idea: create a durable order record before capture,
use idempotency at both the client and gateway boundary, and reconcile lost
payment responses.

Fix the stale main view caption, default option caption, and `satisfies`
sentence. Then add durable payment-attempt/webhook records to make the excellent
prose visible in the schema.

### Step 6: Order State Machine & Fulfillment

This step is substantially improved. It has guarded transitions, an append-only
event history, transactional outbox, idempotent consumers, and a cancellation
matrix that distinguishes pending, paid, and fulfilled states.

A small data-model addition would make it complete: show where consumers record
processed `event_id`s, or state that each downstream service owns a dedupe table.
That makes the "idempotent consumers" claim concrete.

### Step 7: Scaling Carts vs Orders

The synthesis is good. It reinforces the main architectural decision: carts and
orders need different stores, consistency models, and scaling strategies.

This step would be stronger with one more operational scenario: cart shard
rebalance, hot-SKU backpressure, or regional failover. The capacity section now
has the raw material; this step should teach how the design responds.

## Final Design Review

The final design now integrates the walkthrough well. It includes the shopper
app, Commerce API, Cart Service, shard router, cart shards, Pricing &
Promotions, Checkout Orchestrator, Idempotency Store, Inventory Service/DB,
Payment System, Order Service/DB, Outbox, Queue, and Fulfillment Service.

The important fix from the previous review is present: the final path now shows
the Commerce API calling the Cart Service and the Cart Service using the shard
router. The final caption also states the correct checkout sequence: reserve,
create the order, charge payment, and mark paid.

The final design will be fully coherent once the Step 5 rendered captions and
Design vs. Requirements row are updated to match it.

## Concept Introduction and Learning Flow

The concepts are introduced in the right order:

- baseline distributed-transaction failure
- availability-first persistent carts
- authoritative pricing at checkout
- CAS-protected reservation holds
- idempotent saga and payment compensation
- guarded order state machine and transactional outbox
- AP/CP workload separation and scaling

This is a good interview progression. It lets a candidate start simple, then
earn each production mechanism as a response to a concrete failure.

The one learning-flow hazard is stale text in Step 5. Because payment ordering
is one of the hardest concepts, every rendered view should use exactly the same
sequence.

## Step-to-Final-Design Coherence

Coherence is now high. Each major component in the final design is introduced by
an earlier step, and the final design carries forward the chosen defaults:
persistent cart store, server-side pricing, CAS TTL holds, idempotent
orchestrated saga, order state machine, outbox, event queue, and separate cart
and order scaling.

The main mismatch is no longer architectural; it is textual. Step 5's captions
and one `satisfies` row still describe the previous checkout order. Fixing those
will align the step, API, data model, and final design.

## Realism Compared With Production Systems

This is realistic enough for a strong senior interview and close to a
book-quality commerce case. The most production-shaped parts are the
availability/correctness split, bounded cart TTL, checkout idempotency, durable
pre-payment order, payment reconciliation, reservation TTL, outbox, and guarded
order transitions.

The remaining production realism gaps are specific:

- Payment attempts and webhook dedupe should be durable records, not just fields
  on `orders`.
- Coupon redemption and quote snapshots need an authoritative owner.
- Inventory reconciliation should say how `stock_on_hand`, `reserved`, and
  sold/confirmed counts are audited against warehouse state.
- Hot-SKU admission control should be either in scope or explicitly deferred to
  the follow-up section.
- Fraud, risk checks, partial shipments, returns, and warehouse reconciliation
  are good follow-ups and do not need to be in the core path unless this becomes
  a larger order-management case.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Step view nodes resolve to `highLevelArchitecture.nodes`.
- Step view string links, option view string links, and final-design links
  resolve to `highLevelArchitecture.links`.
- `satisfies.functional[*].steps` and `satisfies.nonFunctional[*].steps`
  resolve to real step IDs.
- Structured `view` and `sequence` data are used; there are no raw Mermaid
  diagrams in steps or final design.
- The source dataset has `assets.icon` and `technologyChoices`. `aiVisuals`
  and `explainerComic` remain optional future book enrichments.
- `probeLinks` are valid, but some are still generic: Step 3 only points to
  PostgreSQL isolation, Step 7 has none, and a pricing/tax/coupon reference set
  would make the further-reading path stronger.
- `REVIEW.md` is repo-only. No docs rebuild is needed for this review change.

## Recommended Edits, Prioritized

### P1: Fix stale checkout sequence text

Update Step 5's main view caption, the default option caption, and
`satisfies.functional` so every rendered place uses
`reserve -> create PENDING_PAYMENT order -> authorize/capture -> mark PAID and
confirm holds`.

### P1: Add payment-attempt and webhook-dedupe records

Back the payment lifecycle with durable `payment_attempts` and
`payment_webhook_events`/dedupe state. Tie retry, reconciliation, and gateway
idempotency to those records.

### P1: Make the inventory invariant data-backed

Add `stock_on_hand` and either a `sold`/`confirmed` counter or a derivation rule
from paid order lines. Spell out held/confirmed/released/expired counter
transitions.

### P2: Add price quote and coupon redemption state

Model frozen quotes, tax/promotion rule versions, and coupon redemption/usage
limits, or explicitly assign that responsibility to the Promotion service.

### P2: Teach one hot-SKU operational response

Add a drill or deep dive for admission control, per-SKU queues, sharded
reservation buckets, or single-writer inventory partitions under flash-sale
contention.

### P2: Clarify idempotency records for failed outcomes

State whether out-of-stock, validation failures, and permanent payment failures
are stored as completed idempotency results, and make `order_id` nullable where
no order is created.

### P3: Retarget probe links and add optional visuals

Add pricing/tax/coupon, inventory reservation, payment webhook, and hot-SKU
contention links. Consider `aiVisuals` or an `explainerComic` for the book
wrap-up experience.

## What Not To Change

- Keep the seven-step arc.
- Keep the naive baseline.
- Keep AP carts separate from CP orders/inventory.
- Keep server-side checkout pricing and frozen order-line prices.
- Keep CAS-protected TTL holds as the inventory default.
- Keep durable `PENDING_PAYMENT` order creation before capture.
- Keep the idempotent orchestrated saga as the default checkout answer.
- Keep the guarded order state machine plus transactional outbox.

## Bottom Line

The dataset has moved from "good but correctness-ambiguous" to a strong,
coherent shopping-cart and checkout walkthrough. The next pass should be small
and precise: remove stale charge-before-order wording, add payment and pricing
records that support the prose, and make the inventory invariant explicit in the
schema. After that, the case is ready to stand as a polished commerce-system
interview.
