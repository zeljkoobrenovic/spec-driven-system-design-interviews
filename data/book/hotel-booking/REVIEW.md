# Review: Hotel / Airbnb Booking - System Design

Reviewed file: `data/book/hotel-booking/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a strong focused walkthrough for the central hotel-booking invariant:
search can be approximate, but booking must be exact and must never double-book
an overlapping date range. The step order is mostly right, the default choices
are defensible, and the structured diagrams fit the project conventions.

The biggest gaps are in the production boundary around that invariant. The
dataset uses `property_id` where the actual reservable unit is sometimes a room,
listing, room type, or inventory count; it promises cancellation without a real
API or flow; and it describes payment capture plus booking finalization as
atomic even though that crosses external payment and multiple stores. Capacity
is also too qualitative for a flagship book case.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 3.8 / 5 | Correct core invariant and consistency split; reservable-unit identity, cancellation, and confirm/payment semantics need tightening. |
| Production realism | 3.5 / 5 | Good contention and hold TTL treatment, but lifecycle recovery, derived-store updates, operations, and data retention are thin. |
| Pedagogical flow | 4.2 / 5 | Clear progression from naive race to inventory, search, holds, atomic reservation, confirm, and scale. |
| Final design coherence | 3.9 / 5 | The final design includes the introduced components, but some promised behavior is prose-only. |
| Dataset/rendering fit | 4.1 / 5 | JSON parses and structured views are mostly clean; a few step views reference links whose endpoints are hidden. |

Recommendation: preserve the main spine. The next pass should make the
reservable inventory key explicit, add a cancellation/release path, make confirm
a retryable saga/state machine rather than an impossible atomic cross-system
operation, and add enough capacity math to anchor storage and throughput.

## What Works Well

- The case names the right headline tradeoff: approximate browse versus
  authoritative book.
- The naive baseline is useful because it exposes both failures at once:
  check-then-write races and browse traffic hitting the truth store.
- Per-night availability rows are the right default for teaching date-range
  conflicts. The interval-record alternative is a real tradeoff rather than a
  strawman.
- Step 4's hold options compare the practical choices candidates should know:
  TTL hold, no hold, and pessimistic long lock.
- Step 5 teaches the critical mechanism: check all nights open and mark them
  held in one conditional/transactional operation.
- The distributed-lock option correctly warns about lease expiry, crash gaps,
  and fencing tokens.
- The wrap-up material is concise and aligned with the interview narrative.
- The source uses structured `view` and `sequence` data rather than raw Mermaid
  for architecture steps and flows.

## Highest-Impact Issues

### 1. The reservable unit is ambiguous

The prose alternates between property, room, and property/room, while the data
model uses only `property_id`. The capacity section says the booking unit is
`(room, date-range)`, but `availability`, `holds`, and `bookings` do not carry a
room, listing, room type, or inventory unit key.

Why it matters: no-double-booking is only meaningful at the exact inventory
unit. A single Airbnb listing can be modeled as one unit, but a hotel property
usually has rooms, room types, allotments, and possibly quantity greater than
one per night. If the model uses only `property_id`, two different rooms in the
same hotel would incorrectly conflict, while identical-room inventory cannot be
represented.

Concrete fix: choose the scope and name it everywhere.

- For an Airbnb-style listing: use `listing_id` or `unit_id` consistently and
  say each unit has capacity 1 per night.
- For hotels: model `(property_id, room_type_id, date)` with `available_count`,
  `held_count`, and `booked_count`, or model individual `room_id` rows if room
  assignment is known at booking time.
- Add the chosen key to `/v1/search`, `/v1/holds`, `availability`, `holds`,
  `bookings`, the requirements, and the capacity section.

### 2. Cancellation is promised but not designed

The functional requirements include "Cancel a booking and free the dates",
`bookings.state` includes `cancelled`, and `satisfies.functional` maps
cancel/free dates to Step 6. But there is no cancel API, no cancel sequence, no
state transition guard, no refund/payment interaction, and no architecture link
showing dates being released after a confirmed booking is cancelled.

Why it matters: cancellation is not just the inverse of confirm. It has policy
checks, refund/fee handling, idempotency, and a correctness requirement: the
released nights must become available exactly once and search caches must be
updated.

Concrete fix: either scope cancellation out explicitly or add a small
subsection/step:

- `POST /v1/bookings/{bookingId}/cancel` with an idempotency key.
- Booking state transition `confirmed -> cancelling -> cancelled`.
- Release booked nights back to open only after the booking transition is
  accepted.
- Trigger cache/search invalidation.
- Tie refund behavior to policy without turning this into a full payment case.

### 3. Confirm is described as atomically crossing payment and multiple stores

Step 6 says confirm captures payment and transitions the hold to a confirmed
booking atomically. The sequence captures payment, updates availability, and
writes the booking row; the failure drill covers a crash after payment capture
but before recording the booking. That is the right failure to discuss, but the
dataset does not show the state, identifiers, or recovery records needed to make
the expected behavior true.

Why it matters: external payment capture cannot be part of the same atomic
transaction as `AvailDB` and `BookingDB`. The design needs a retryable state
machine, not an implied distributed transaction.

Concrete fix: model confirm as a saga with explicit states and stable keys:

- `holds`: `state`, `payment_authorization_id`, `expires_at`, `confirming_at`.
- `bookings`: `state` values such as `confirming`, `confirmed`,
  `confirm_failed`, `cancelled`.
- `payment_attempts` or `payment_reference` keyed by hold/booking id.
- A confirm idempotency record that stores request fingerprint and final
  response.
- Recovery for capture-succeeded/write-failed and write-succeeded/response-lost
  cases.

### 4. Capacity is too qualitative for the design choices

The capacity section says "millions", "search >>> book", and "hold TTL minutes",
but it never converts those into rows, storage, QPS, cache invalidation volume,
or contention limits. The per-night inventory model has a direct capacity shape
that should be visible.

Why it matters: the chosen model's cost is `inventory_units x calendar_horizon`.
Without even approximate numbers, the learner cannot reason about whether
per-night rows, cache invalidation, search freshness, or property-sharded writes
are plausible.

Concrete fix: add a compact numeric pass, for example:

- `1M listings x 365 nights = 365M availability rows` before replicas/history.
- Search QPS versus hold/confirm QPS.
- Average and peak date-range length, because each hold touches N night rows.
- Cache invalidations per confirmed/cancelled booking.
- Hot listing contention: one shard/key serializes contested date ranges.

### 5. The API and data model do not yet carry the core invariants

The API has only search, hold, and confirm. `/v1/holds` lacks idempotency,
guest/user identity, unit/room key, quoted price/currency, payment method or
authorization reference, and explicit error states. `/v1/bookings` confirms a
hold with only `holdId` and an idempotency key. The model lacks an idempotency
table, payment references, hold state, hold owner, audit timestamps, and fields
that distinguish hold expiry from cancellation or successful confirmation.

Why it matters: the prose teaches retry safety and lifecycle correctness, but
the interface and schema are where those guarantees become enforceable.

Concrete fix: add the minimal fields that support the lesson:

- `Idempotency-Key` or `idempotencyKey` on hold, confirm, and cancel.
- `guest_id`, `unit_id` or `room_type_id`, `amount`, `currency`, `price_quote_id`.
- `holds.state`, `holds.owner_guest_id`, `holds.payment_authorization_id`.
- `bookings.hold_id`, `bookings.guest_id`, `bookings.cancelled_at`.
- `idempotency_keys` with scope, request hash, response, status, and expiry.

## System Design Soundness

### Requirements and Capacity

The functional and non-functional requirements are well scoped around search,
availability, hold, cancellation, and double-book prevention. The main issue is
that cancellation is listed as a first-class functional requirement but is only
handled as a sentence in Step 6.

The capacity section should be upgraded. This case has unusually teachable math:
inventory rows are bounded by unit count and calendar horizon, and hold/confirm
work scales with stay length. Add enough numbers to justify per-night rows and
to explain where caches and derived search views pay off.

### API

The three endpoints are a good starting surface, but they are too thin for the
invariants the walkthrough teaches. Hold should be idempotent and should include
the exact unit, stay range, guest, quote, and payment authorization context.
Confirm should return transitional states when payment or persistence is still
being recovered. Cancellation needs either an endpoint or an explicit
out-of-scope note.

The search API should also clarify whether results are properties, listings,
room types, or individual rooms. Its response currently returns only
`propertyId` and `price`, which hides the unit that the booking flow must later
reserve.

### Data Model

The current `availability`, `holds`, and `bookings` entities match the broad
story, but they are not yet strong enough to enforce it.

`availability` needs the exact reservable key and probably a hold expiry or
hold reference that lets reaping distinguish the currently valid hold from an
old one. `holds` needs state and ownership. `bookings` needs hold linkage,
guest/user linkage, amount/currency, cancellation timestamps, and payment
references. A small `idempotency_keys` entity would make the retry story much
more concrete.

### Architecture

The high-level architecture has the right components: search/index/cache for
browse, booking/availability stores for truth, hold store, payment service, and
reaper. The derived-store update path is too implicit, though. The final design
says cache updates come from booking events, but the diagram only shows
`AvailDB -> Cache`; there is no change stream, outbox, projector, or worker.
For an interview case, a single `AvailabilityChangeStream` or `CacheProjector`
node would make the freshness boundary clearer.

## Step-by-Step Pedagogical Review

### Step 1: Naive check-then-write

This is a useful baseline. It exposes the race and motivates both later tracks:
atomic reservation and separating browse from book. Keep it.

Improvement: make the failure example use the same reservable key that the rest
of the case chooses, such as `unit_id` or `(property_id, room_type_id)`.

### Step 2: Model inventory as date-range availability

This is the strongest conceptual step. Per-night rows are the right default for
an interview because they make overlap conflicts concrete.

Improvement: add a short note on capacity-1 versus quantity inventory. If the
case stays Airbnb-like, state that a listing has one sellable unit. If it is
hotel-like, teach counts per room type or separate room assignment.

### Step 3: Search as approximate browse

The browse/book consistency split is well explained. The options are credible,
especially the comparison against querying the authoritative store directly.

Improvement: add the update mechanism for the availability cache. The
event-driven materialized view option introduces a stream, but the default
design still needs a named projector or invalidation path.

### Step 4: Hold-then-confirm checkout

The TTL hold explanation is clear and the alternatives are useful. The
pessimistic-lock option correctly warns against holding database locks across a
human payment window.

Improvement: specify the hold's lifecycle fields and how expiry is guarded. A
reaper should release only a still-held, still-expired hold; it must not reopen
nights that have already been confirmed or re-held by a newer checkout.

### Step 5: Preventing double-booking

This is the core step and mostly works. The default option teaches the right
primitive: conditional update over the whole range. The distributed-lock option
correctly surfaces fencing-token risk.

Improvement: tighten the example SQL/conditional semantics. A naive `UPDATE ...
WHERE date IN range AND state='open'` can update a partial subset unless the
transaction also checks that the affected row count equals the number of nights
and rolls back otherwise. Name that check explicitly.

### Step 6: Confirm, idempotency, and expiry

This step has the right concerns but compresses too much. Confirm, hold expiry,
payment capture, retry dedupe, and cancellation are all separate state-machine
edges.

Improvement: split the text or add subflows:

- Confirm retry after lost response.
- Payment capture succeeded but local write failed.
- Hold expiry racing with confirm.
- Cancellation after confirmation.

### Step 7: Scaling search, hot properties, and freshness

The step lands the main scaling idea: search scales independently, while hot
property writes serialize locally. That is a good close.

Improvement: add numbers and operational signals. Examples: conflict rate on
hot inventory, hold expiry backlog, cache staleness age, booking failure rate,
and search-to-hold conversion.

## Final Design Review

The final design coherently includes the components introduced in the steps:
gateway, search service, search index, availability cache, booking service,
availability service/store, booking store, hold store, payment service, and
reaper.

The final design should not say the confirm step atomically captures payment
and transitions the hold unless it scopes "atomic" only to local state. It
should instead say the booking service drives a retry-safe confirm state machine
using idempotency and payment references, then marks the held nights booked.

The final diagram should also make cache/search updates clearer. A direct
`AvailDB -> Cache` edge is compact, but it hides the event/outbox/projector that
usually owns derived browse freshness.

## Concept Introduction and Learning Flow

The concept order is effective:

1. Date-range inventory.
2. Approximate browse versus exact book.
3. TTL hold.
4. Atomic range reservation.
5. Idempotent confirm and reaping.

The missing concept is lifecycle state management. The case uses states
throughout, but it never names the booking/hold/payment state machine as a
first-class design tool. Adding that concept in Step 6 would also make
cancellation and recovery easier to teach.

## Step-to-Final-Design Coherence

Most steps carry into the final design cleanly. The weak transitions are:

- Step 3 introduces approximate availability, but the final design does not
  show a durable update path from booking truth to derived browse stores.
- Step 6 mentions cancellation and refunds, but neither appears in the final
  architecture or API.
- Step 6's sequence calls `AvailDB` directly from `BookingSvc`, while the
  architecture mostly routes booking changes through `AvailSvc`.
- Step 7 explains hot properties, but the final design does not expose metrics
  or backpressure/admission control for that path.

## Realism Compared With Production Systems

The case is realistic about the most important invariant: do not double-sell a
date range. It also handles common interview pitfalls around search freshness,
long-held locks, and distributed locks.

The production gaps are mostly lifecycle and operations:

- No explicit owner for cache invalidation or search-index projection.
- No mention of observability for stale search, hold leaks, expired-hold
  reaping, payment ambiguity, or conflict spikes.
- No audit/history table for availability transitions.
- No data retention/privacy note for guest and payment-adjacent data.
- No host/admin workflow for closing dates, changing inventory, or blocking a
  room for maintenance.
- No policy boundary for cancellation, refund, taxes, or fees.

The case does not need all of those to be a good interview, but it should
include enough of them to avoid implying the core three-table model is complete.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level keys are in the expected project shape for a book interview.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Step view link IDs resolve to `highLevelArchitecture.links`.
- Step highlight IDs resolve inside their step views.
- The dataset uses structured `view` and `sequence` objects for steps and
  flows, which matches the renderer conventions.
- Three step views select links whose endpoints are not included in the same
  view's node list:
  - `search` selects `avail-cache` (`AvailDB -> Cache`) without `AvailDB`.
  - `hold` selects `lb-booking` (`LB -> BookingSvc`) without `LB`.
  - `scale` selects `booking-db` (`BookingSvc -> BookingDB`) without
    `BookingSvc`.

Those last three are easy to fix by adding the missing endpoint nodes or by
replacing the selected high-level link with an inline link whose endpoints are
present in that view. Otherwise Mermaid may synthesize implicit nodes without
the expected labels/types.

## Recommended Edits, Prioritized

### P1: Make inventory identity precise

Rename the reservable unit throughout the case and add it to API requests,
responses, `availability`, `holds`, `bookings`, diagrams, and examples.

### P1: Add cancellation as a real lifecycle path

Add a cancel endpoint, sequence, state transition, inventory release, cache
update, and idempotency behavior, or explicitly move cancellation out of scope.

### P1: Replace "atomic confirm" with a retry-safe confirm state machine

Model payment capture, booking persistence, availability finalization, and
response replay as recoverable steps with stable references and idempotency.

### P1: Add capacity math

Quantify inventory rows, search QPS, hold/confirm QPS, date-range write
amplification, cache invalidation rate, and hot-property contention.

### P2: Strengthen API and schema fields

Add guest/unit/quote/payment/idempotency fields and a small idempotency entity.
Add timestamps and owner/state fields needed by reapers and operators.

### P2: Show the derived-store update path

Add an availability change stream, outbox, or projector for updating the cache
and search view after hold/confirm/cancel transitions.

### P2: Add operational signals

Include conflict rate, hold expiry backlog, stale-cache age, reaper failures,
payment ambiguity, and booking state-machine stuck counts.

### P3: Fix minor view endpoint mismatches

Adjust the `search`, `hold`, and `scale` step views so each selected link's
endpoints are present.

### P3: Update wrap-up teaching prompts

Add level-variant and interview-script prompts for reservable-unit modeling,
cancel/release, confirm recovery, and cache projection.

## What Not To Change

- Keep the approximate-browse/exact-book split. It is the case's best teaching
  point.
- Keep per-night inventory as the default option unless the dataset is
  deliberately reframed around sparse interval bookings.
- Keep the TTL hold pattern and the warning against long database locks during
  human checkout.
- Keep the distributed-lock option as a rejected or caveated alternative; it
  teaches an important production trap.
- Keep the final scale step focused on hot inventory and freshness rather than
  expanding into unrelated hotel-domain features.

## Bottom Line

This dataset is close to a strong book case. The main narrative is correct and
teachable. To make it production-realistic, the next edit should turn the
currently implicit lifecycle details - inventory unit, cancellation, confirm
recovery, and derived-store updates - into explicit API, schema, flow, and
diagram elements.
