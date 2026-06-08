# Review: Hotel / Airbnb Booking - System Design

Reviewed file: `data/book/hotel-booking/interview.json`
Review date: 2026-06-08

## Executive Summary

This dataset is now a strong book-quality walkthrough for lodging reservations.
The recent edits fixed the previous major gaps: the reservable key is explicit,
capacity has concrete numbers, cancellation is represented as an idempotent
lifecycle path, confirm is no longer described as an impossible atomic
payment-plus-database transaction, and the browse freshness pipeline now has a
named change stream and projector.

The central teaching spine is clear: search can be approximate, booking must be
exact, and no-double-booking is enforced by per-unit, per-night inventory plus
an atomic range reservation. The remaining issues are narrower and mostly about
precision at production boundaries: hotel room-type quantity inventory needs a
slightly stronger schema, hold-time payment authorization is inconsistent
between prose/API response and the API sequence, and the cancel/recovery path
would benefit from more explicit outbox/reconciliation mechanics.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.5 / 5 | Core invariant, consistency split, capacity, idempotency, and lifecycle states are strong; quantity inventory semantics need tightening. |
| Production realism | 4.2 / 5 | Much better recovery, cancellation, and freshness story; still light on durable event publication, reconciliation, and payment authorization details. |
| Pedagogical flow | 4.6 / 5 | Excellent step progression from naive race to inventory, search, holds, atomic reserve, confirm saga, and scale. |
| Final design coherence | 4.4 / 5 | Final design now incorporates the introduced components and decisions; a few API/sequence details lag the prose. |
| Dataset/rendering fit | 4.8 / 5 | JSON parses; structured views, links, highlights, and satisfies references resolve cleanly. |

Recommendation: keep the current architecture spine. The next pass should make
hotel quantity inventory precise, align the hold API sequence with payment
authorization, and add a small amount of durable event/reconciliation detail for
cancel, confirm, and browse-store projection.

## What Works Well

- The dataset now consistently frames the booking key as `unit_id`, with a
  clear note that hotels may use `room_type_id` and counts.
- Capacity is concrete enough to support design tradeoffs: `1M x 365 = 365M`
  availability rows, `~50k` search QPS, `~500` hold/confirm QPS, average stay
  length, invalidation volume, hot-unit contention, and hold TTL.
- The API is much stronger: hold and confirm carry idempotency, hold includes
  guest/quote/payment context, cancel is a real endpoint, and responses expose
  lifecycle states.
- The data model now includes `holds.state`, `payment_authorization_id`,
  `bookings.state`, `payment_reference`, cancellation timestamps, and
  `idempotency_keys`.
- Step 3 now gives derived browse freshness an explicit owner: availability
  changes flow through `AvailStream` and `CacheProjector` to cache and search.
- Step 5 correctly calls out the subtle affected-row-count check for atomic
  range reservation.
- Step 6 now teaches confirm as a retry-safe saga/state machine rather than a
  distributed transaction.
- Cancellation is now integrated into requirements, API, patterns, final
  design, satisfies, interview script, and follow-ups.
- The step order remains strong and interview-friendly: each step exposes the
  next design pressure without jumping prematurely.

## Highest-Impact Issues

### 1. Hotel room-type quantity inventory is still underspecified

The dataset says the default unit is a listing with capacity 1 per night, while
hotels add `room_type_id` with counts. That is the right framing, but the
`availability` entity mixes a scalar `state: open|held|booked` with
`available_count`. For a hotel room type with many identical rooms, a single
state is not enough unless the dataset explains exactly how counts are updated
and when the row becomes sold out.

Why it matters: no-double-booking for capacity-1 listings is a binary state
transition; no-overselling for room types is a counter invariant. A candidate
should see whether the design reserves one unit from a count, assigns an
individual room, or treats hotels as an extension outside the main flow.

Concrete fix: choose one of these and make it explicit.

- If the main case is Airbnb-like, say the primary model is capacity 1 and move
  room-type counts into an extension note.
- If hotel room types are in scope, change `availability` to use counters such
  as `available_count`, `held_count`, and `booked_count`, with a conditional
  update like `available_count >= requested_rooms`.
- If individual room assignment matters, add `room_id` allocation as a later
  operational step rather than blending it into the room-type count model.

### 2. Hold-time payment authorization is inconsistent in the API flow

`POST /v1/holds` says it authorizes payment and returns
`paymentAuthorizationId`; Step 4's view also includes `PaySvc`. But the API
sequence for `/v1/holds` only shows `BookingSvc -> AvailSvc -> AvailDB` and
`BookingSvc -> HoldStore`; it never calls `PaySvc`.

Why it matters: the hold step is where the dataset teaches a user-visible
checkout boundary. Whether payment is authorized before, during, or after a
successful inventory hold affects failure handling: inventory held but auth
failed, auth succeeded but hold write failed, and auth reversal on hold expiry.

Concrete fix: add `PaySvc` to the hold API sequence or change the hold endpoint
to reserve inventory only and defer all payment work to confirm. If keeping
authorization at hold time, show the order and failure branches:

- Reserve date range.
- Create hold/idempotency record.
- Authorize payment.
- Return hold plus authorization id.
- Void/release on authorization failure or hold expiry.

### 3. Durable publication and reconciliation are implied, not designed

The change stream and projector are good additions, but the dataset still
compresses how availability changes are published durably after hold, confirm,
cancel, and expiry. Similarly, confirm and cancel recovery mention stable
references and idempotency, but do not name a reconciliation loop for stuck
payment/booking states.

Why it matters: this is where production systems usually fail quietly. A
booking can be correct in the truth store while search remains stale if the
projection event is lost. A payment can be captured while booking state remains
`confirming` unless a worker reconciles it.

Concrete fix: add one concise production note in Step 6 or Step 7:

- Availability state changes are committed with an outbox/change record in the
  same local transaction as the truth-store update.
- The projector consumes with at-least-once delivery and idempotent updates.
- A reconciliation worker scans stuck `confirming`/`cancelling` states and
  compares local records with payment-provider references.
- Metrics alert on projector lag, stale cache age, stuck saga age, and unmatched
  payment references.

### 4. Cancellation exists, but refund/availability ordering could be clearer

The cancel API and sequence now exist and are directionally correct:
`confirmed -> cancelling -> cancelled`, release nights once, refund per policy.
The remaining ambiguity is ordering and compensation: should nights be released
before a refund succeeds, after refund succeeds, or once cancellation is
accepted with refund handled asynchronously?

Why it matters: release-before-refund maximizes inventory reuse but can create
customer-support ambiguity if refund fails. refund-before-release can keep
inventory unavailable longer. Either is defensible, but the chosen behavior
should be deliberate.

Concrete fix: add a short statement such as: cancellation acceptance is the
source-of-truth transition; nights are released once the booking enters
`cancelling`, while refund runs asynchronously and is reconciled by policy. Or
choose the stricter alternative and explain the tradeoff.

## System Design Soundness

### Requirements and Capacity

The functional and non-functional requirements are now aligned with the actual
design. Search, calendar availability, hold/confirm, cancel, and no
double-booking are all represented in the architecture and wrap-up material.
The non-functional requirements correctly distinguish approximate browse from
strongly consistent booking.

The capacity section is a major improvement. It now lets a learner reason about
row count, search/write traffic split, stay-length write amplification, cache
invalidation volume, and hot-unit serialization. The only caveat is that the
numbers assume one requested unit per booking; if hotel room types with counts
are kept in scope, capacity should mention requested room quantity and count
updates.

### API

The API surface is strong for an interview case:

- `GET /v1/search` exposes approximate availability and returns `unitId`.
- `POST /v1/holds` includes an idempotency key, guest, quote, payment method,
  hold expiry, and authorization reference.
- `POST /v1/bookings` describes confirm as retry-safe and capable of returning
  transitional states.
- `POST /v1/bookings/{bookingId}/cancel` is idempotent and includes refund
  policy output.

The main API issue is consistency of the payment story. The hold endpoint
claims authorization but the hold sequence does not show payment. The confirm
endpoint also has no API-level sequence, while Step 6 has good confirm and
recovery flows. Adding the confirm sequence to the API section is optional, but
adding payment authorization to the hold sequence would prevent confusion.

### Data Model

The model now supports the intended lifecycle much better than before. Holds,
bookings, and idempotency records have the fields needed to explain retry-safe
behavior. The `hold_id` on availability rows is especially useful because it
lets the reaper release only the still-current hold.

The remaining modeling gap is quantity inventory. For a capacity-1 listing,
`state` plus `hold_id` is clean. For a hotel room type, `available_count` needs
counter semantics, and `hold_id` cannot represent multiple simultaneous holds
against different portions of the same room-type inventory. Either scope that
out or add count-specific fields and a `hold_allocations` concept.

### Architecture

The architecture now has the right components and ownership boundaries:
search/index/cache for browse, availability store for truth, booking service
for lifecycle orchestration, hold store and reaper for checkout expiry, payment
service for money movement, and change stream/projector for derived browse
freshness.

The final design is coherent. It should add only a small note about durable
event publication or outbox semantics so the `AvailDB -> AvailStream` edge does
not look like a best-effort side effect.

## Step-by-Step Pedagogical Review

### Step 1: Naive check-then-write

This remains a strong opening. It demonstrates the read-then-write race and
the browse-scaling problem in one simple baseline. The recent wording improves
it by naming the reservable unit before the walkthrough commits to a schema.

Improvement: none required beyond keeping examples tied to the chosen
`unit_id` model.

### Step 2: Model inventory as date-range availability

This is one of the strongest steps. Per-night inventory is the right interview
primitive because overlap conflicts become concrete and easy to test.

Improvement: clarify the extension from listing capacity 1 to hotel room-type
counts. The current text mentions both, but the schema and atomic update
mechanism are most precise for capacity 1.

### Step 3: Search as approximate browse

The browse/book consistency split is well taught. The added change stream and
projector fix the earlier issue where cache freshness had no owner.

Improvement: add one sentence that the projector's updates are idempotent and
driven from durable truth-store changes, not from transient service memory.

### Step 4: Hold-then-confirm checkout

The TTL hold explanation is clear and the alternatives are good. The step now
includes lifecycle fields and the important reaper guard: release only a
still-held, expired, unconfirmed hold.

Improvement: align payment authorization across prose, view, and API sequence.
If authorization happens during hold, show `PaySvc` in the sequence and state
what happens when authorization fails after inventory was held.

### Step 5: Preventing double-booking

This is the core step and it works well. The affected-row-count warning is
exactly the kind of practical detail that distinguishes a real answer from
"just use a transaction."

Improvement: if room-type count inventory stays in scope, add the analogous
counter condition for `available_count >= requested_rooms`.

### Step 6: Confirm, idempotency, and expiry

This step has improved the most. It now clearly rejects an atomic external
payment plus local database transaction and teaches confirm as a retry-safe
state machine. The recovery flow for capture-succeeded/write-failed is valuable
and concrete.

Improvement: add reconciliation as a named operational loop for stuck
`confirming`, `confirm_failed`, and `cancelling` states. Also clarify cancel
ordering around release and refund.

### Step 7: Scaling search, hot properties, and freshness

This is a strong closing step. It ties the earlier choices to sharding, hot-unit
contention, replicated browse stores, and operational metrics. The metric list
is practical and well scoped.

Improvement: include projector lag/outbox backlog explicitly among the
operational signals, because it is the health of the search freshness pipeline.

## Final Design Review

The final design now integrates the steps cleanly:

- `unit_id` or room-type count is named up front.
- Browse uses `SearchIdx` and `Cache`.
- Availability truth lives in `AvailDB`.
- `AvailStream` and `CacheProjector` update derived browse stores.
- Checkout uses TTL holds and atomic range reservation.
- Confirm is a retry-safe saga.
- Reaper releases expired holds.
- Cancellation releases nights once and refunds per policy.
- Stores shard by unit, and booking re-checks truth.

The final design should preserve this shape. The only substantial improvement
is to make the event/reconciliation path more explicit so the reader sees how
derived stores and payment-adjacent lifecycle states recover after partial
failure.

## Concept Introduction and Learning Flow

The concept order is now excellent:

1. Date-range inventory.
2. Precise reservable unit.
3. Approximate browse versus exact book.
4. TTL hold.
5. Atomic range reservation.
6. Idempotent confirm and hold reaping.
7. Cancel and release.
8. Change stream/projector for derived stores.
9. Hot-unit scaling and operational signals.

The only concept that deserves slightly more emphasis is the distinction
between binary inventory and quantity inventory. It is mentioned, but not yet
turned into a crisp design branch.

## Step-to-Final-Design Coherence

Most step decisions now carry into the final design directly. The previous
coherence gaps around reservable unit identity, cancellation, confirm
state-machine handling, capacity math, and cache projection have been addressed.

The remaining small mismatches are:

- Hold API prose and response include payment authorization, but the hold API
  sequence omits `PaySvc`.
- Room-type count inventory is mentioned in requirements/capacity/schema, but
  the main atomic reservation mechanism is still described mostly as binary
  open/held/booked rows.
- Durable projection and saga reconciliation are implied by the architecture,
  but not yet shown as first-class recovery mechanisms.

## Realism Compared With Production Systems

The dataset now feels much closer to production. It handles the hard lodging
invariant, separates browse freshness from booking correctness, models retry
safety at money-moving boundaries, includes cancellation, and names operational
signals.

Remaining production caveats:

- Quantity inventory needs count-specific reservation semantics if hotels are
  truly in scope.
- Payment authorization during hold needs failure/void behavior.
- Confirm/cancel needs a reconciliation worker or explicit stuck-state recovery
  loop.
- The availability change stream should be described as durable, outbox-backed,
  or otherwise tied to the truth-store commit.
- Data retention/privacy is still only implicit, especially around guest IDs,
  payment references, idempotency records, and audit/history.
- Host/admin workflows for owner-blocked dates, maintenance, and inventory
  changes are scoped out; that is acceptable, but worth calling out in a
  follow-up if the case is framed as "hotel" rather than "guest booking only."

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level keys match the expected book-interview shape.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Step, option, and final-design view node references resolve against
  `highLevelArchitecture.nodes`.
- Step, option, and final-design view link references resolve against
  `highLevelArchitecture.links`.
- Selected high-level links have their endpoint nodes present in the same view.
- Step highlight IDs resolve inside their step views.
- Sequence participants resolve to canonical node IDs.
- The dataset uses structured `view` and `sequence` objects for architecture
  and flow diagrams, matching renderer conventions.
- Canonical node types are used: `cache`, `client`, `database`, `edge`,
  `index`, `service`, `stream`, and `worker`.

No renderer-facing blockers were found in the current dataset.

## Recommended Edits, Prioritized

### P1: Tighten quantity inventory semantics

Decide whether the primary case is capacity-1 listings or hotel room-type
counts. If counts remain in scope, add counter fields and conditional update
semantics for reserving one or more rooms from a room-type row.

### P1: Align hold payment authorization

Add `PaySvc` and failure branches to the `/v1/holds` sequence, or move payment
authorization out of hold and into confirm. The prose, API response, step view,
and sequence should all tell the same story.

### P2: Add durable projection/reconciliation detail

Name an outbox/change-record pattern for availability events and a
reconciliation worker for stuck confirm/cancel/payment states. Keep it concise;
one production note or mini-flow is enough.

### P2: Clarify cancellation ordering

State whether inventory release happens when cancellation is accepted, after
refund success, or through an asynchronous refund workflow. Mention the
tradeoff.

### P2: Add privacy/retention caveats

Add a short note for guest IDs, payment references, idempotency-key retention,
and audit/history retention.

### P3: Add one hotel-specific follow-up

Add a follow-up or level-variant prompt asking the candidate to switch from
single-unit listings to room-type inventory with quantity, room assignment, and
overbooking policy.

## What Not To Change

- Keep the approximate-browse/exact-book split. It is the best teaching point.
- Keep per-night inventory as the default model.
- Keep the TTL hold pattern and the warning against long database locks during
  human checkout.
- Keep the affected-row-count check in the atomic reservation step.
- Keep confirm as a retry-safe saga rather than an atomic external transaction.
- Keep cancellation in the core case; it now completes the lifecycle story.
- Keep the change stream/projector path for derived browse freshness.

## Bottom Line

This is now a strong, coherent lodging-booking interview. The previous major
review findings have largely been addressed. The remaining work is polish with
real production value: make quantity inventory precise, align hold-time payment
authorization, and add a little durable projection/reconciliation detail.
