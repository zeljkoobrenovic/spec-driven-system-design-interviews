# Ticketmaster Dataset Review

## Verdict

This is a realistic and useful system-design interview walkthrough for the core
high-demand ticketing problem: scarce fixed inventory, flash-crowd contention,
seat holds, no double-sell, waiting-room admission, checkout, and hot-event
isolation. The learning flow is clear and the top-level step count is about
right for a book-style case.

I would not add more top-level steps. Add targeted substeps/deep dives instead,
because the current narrative already has the right arc. The main improvements
should be around transaction boundaries, queue-token enforcement, final-diagram
edges, and a few missing data-model relationships.

## Validation Notes

- JSON parses successfully.
- `node data/book/_verify.mjs` reports no missing highlights, implicit flowchart
  nodes, bad parent references, or broken `patterns`/`satisfies` step links.
- Mermaid node IDs and highlighted IDs are valid for the current renderer.

## What Works Well

- The interview starts with the right failure mode: a naive check-then-write
  purchase path that double-sells under contention.
- The design correctly separates read-heavy browsing from authoritative writes.
- The walkthrough emphasizes the key invariant: reads can be stale, but reserve
  and checkout must use an atomic authoritative write path.
- Seat locking, TTL holds, idempotency keys, waiting-room admission, payment
  compensation, and per-event sharding are all appropriate system-design topics
  for this case.
- The step order is educational: baseline failure, read model, atomic reserve,
  expiry, admission control, checkout, consistency, then scale/abuse.
- The traps and interviewer signals are strong. They teach candidates what to
  say and what not to hand-wave.

## Realism Assessment

The case is realistic for an interview, but still simplified compared with a
production ticketing platform. That is acceptable, as long as the simplification
is explicit.

Strong realistic elements:

- Flash-crowd load is treated as contention against scarce seats, not just
  generic throughput.
- Holds have short leases and must expire.
- Checkout is idempotent and has compensation for payment/inventory races.
- The lock store is eventually demoted to an accelerator while inventory CAS is
  the source of truth.
- Hot events are isolated by event-level routing/sharding.
- Bot and scalper defense is included as part of fairness, not as an afterthought.

Simplifications worth either documenting or deepening:

- The waiting-room fairness model is underspecified. Real systems may use FIFO,
  randomized queue assignment, presale priority, access codes, or identity tiers.
  The dataset currently says "roughly first-come"; that is fine, but the policy
  should be named.
- The reserve API does not show a required admission token. Without token
  validation, the waiting room is not actually enforcing load or fairness.
- General-admission support is listed as a requirement, but the API and data
  model are mostly reserved-seating-only. Step 7 mentions an atomic counter, but
  there is no GA inventory table/counter in the model.
- Payment state is too compressed. A production design needs durable payment
  attempts, order state transitions, refund/void handling, and reconciliation.
- Availability cache updates are shown, but the eventing/outbox/reconciliation
  path is not modeled. That is fine for a mid-level answer, but staff-level
  candidates should explain it.

## Node And Relation Review

The node choices are mostly logical:

- `Client`, `API`, `Reservation Service`, `Checkout Service`, `Admission Gate`,
  and `Event Router` are appropriate service/process nodes.
- `Inventory DB`, `Holds`, `Orders DB`, `Availability Cache`, and `Seat Lock
  Store` are appropriate stateful nodes.
- `Payment System` is correctly modeled as an external dependency.
- `Waiting Room Queue` is the right abstraction for admission control.
- The step diagrams use the right node types and highlight the important new
  components.

Concrete relation issues to fix:

1. Final design is missing checkout-to-inventory conversion.
   - Current final diagram has `Checkout --> Hold`, `Checkout --> Payment`, and
     `Checkout --> Order`.
   - But checkout must also convert held seats to sold in the authoritative
     inventory shard, either by calling the reservation/inventory service or by
     routing to the correct shard.
   - Add an edge such as `Checkout --> Router` or `Checkout --> ShardA/ShardB`
     with a label like `held -> sold CAS`.

2. Final design is missing expiry-to-inventory release.
   - Step 4 correctly shows expiry updating hold, lock, inventory, and cache.
   - Final design only shows `Expiry --> Hold` and `Expiry --> Lock`.
   - Add expiry release edges to the authoritative inventory shard(s), and
     optionally to the cache/update stream.

3. Anti-abuse placement is inconsistent.
   - Step 8 says rate-limit and fingerprint before tokens are issued.
   - Final design places `AntiBot` after `Gate`, so bad clients may already have
     queue positions.
   - Better relation: put anti-abuse in front of queue-token issuance and also
     enforce it at admission/reserve.

4. The lock store should match the sharding story.
   - Final design has one shared `Seat Lock Store` behind both `ReserveA` and
     `ReserveB`.
   - If hot-event isolation is the lesson, model lock storage as event-scoped or
     sharded too, for example `LockA` and `LockB` or `Lock[(Seat Lock Store -
     event partitioned)]`.

5. The "Rely on lock-store TTL only" option diagram is misleading.
   - It shows `Lock -->|TTL expires| Inventory`.
   - A lock TTL expiring does not automatically update inventory unless there is
     a worker/listener doing that.
   - The diagram should show drift/no update, or label the edge as the missing
     cleanup problem.

6. Client-to-read-model relation should be clarified.
   - Step 2 shows `Client -> API -> Search`, but final design shows
     `Client --> Search`.
   - Direct client access may be okay if `Search` is a public read API, but the
     node label should make that clear. Otherwise route through `API`.

## Data Model Review

The model is good enough for a conceptual overview, but it needs a few changes
to be production-realistic:

- `seats.seat_id` is described as event-scoped but also marked as `PK`. Use a
  composite key `(event_id, seat_id)` or a globally unique `event_seat_id`.
- `holds.seat_ids` and `orders.seat_ids` as arrays are simple, but they hide
  important constraints. Prefer join tables such as `hold_seats` and
  `order_seats`, or model the seat state with `hold_id` / `order_id` references.
- Add a durable payment model: `payment_attempts`, `payment_status`,
  `idempotency_key`, `provider_ref`, and refund/void state.
- Add fields to `queue_tokens`: `user_id` or account/session identity,
  `issued_at`, `expires_at`, `status`, `admission_window`, and possibly
  `abuse_score`.
- Add a GA inventory table/counter if GA is a stated requirement, for example
  `ga_inventory(event_id, pool_id, remaining, version)`.
- Consider an audit/ledger table for inventory transitions. It helps with
  reconciliation after lock-store, payment, or cache failures.

## API Review

The API surface is understandable, but it should expose the enforcement points:

- `POST /v1/events/{id}/reservations` should require an admission token for hot
  events, either in the request body or an authorization header.
- Add or describe `GET /v1/queue/{event}/status` because clients usually poll or
  receive updates after receiving a queue token.
- Add a GA reservation shape, for example `{ "pool_id": "floor", "quantity": 2
  }`, since the current reserve endpoint only demonstrates specific seats.
- Checkout should be framed as a state-machine transition, not just a charge
  followed by an order row.

## Flow And Teaching Quality

The flow is clear and educative. The strongest teaching pattern is that each
step fixes a specific failure introduced by the previous design:

- Naive buy exposes double-sell.
- Read model protects browsing from write contention.
- Seat lock fixes atomic reservation.
- TTL expiry fixes leaked holds.
- Waiting room fixes herd load and fairness.
- Checkout fixes hold-to-order conversion.
- Inventory CAS fixes the lock-store-as-source-of-truth trap.
- Sharding and anti-abuse fix platform-scale blast radius and adversaries.

I would keep the eight top-level steps. More top-level steps would make the
interview feel fragmented. The missing depth is better handled as substeps or
deep dives.

Recommended substeps/deep dives:

- `3a. Multi-seat locking details`: sorted lock acquisition, all-or-nothing
  rollback, fencing token/lease id, and idempotency-key storage.
- `5a. Admission-token enforcement`: queue position assignment, token signing,
  identity binding, admission window, bypass prevention, and retry/backoff.
- `6a. Checkout state machine`: hold renewal/freezing during payment,
  `PENDING_PAYMENT -> CONFIRMED -> REFUND_PENDING/CANCELLED`, and reconciliation.
- `7a. General admission counters`: decrement-if-positive, counter/order
  reconciliation, and how GA differs from reserved seats.
- Optional staff-level deep dive: inventory event stream/outbox to update the
  availability cache and audit every transition.

## Recommended Change Priority

High priority:

- Add reservation admission-token enforcement.
- Fix final-design edges for checkout-to-inventory and expiry-to-inventory.
- Add GA inventory/counter data model or remove GA from the stated scope.
- Add payment-attempt/order-state modeling.

Medium priority:

- Clarify lock store as advisory/fenced earlier in Step 3, not only in Step 7.
- Make lock storage event-partitioned in the scaling diagrams.
- Expand queue token fields and anti-abuse placement.
- Replace `seat_ids` arrays with explicit relation tables if the dataset wants
  more realism.

Low priority:

- Add a cache-update/outbox deep dive.
- Add more capacity math for admission rate, checkout time, and payment-provider
  throughput.
- Add follow-ups for venue map versioning, ticket delivery/barcodes, transfer,
  resale, presales, access codes, and dynamic pricing.

## Bottom Line

The dataset is a strong interview case and should remain mostly as-is. The best
next edit is not "more steps"; it is tightening the correctness story where
the diagrams and data model currently skip over enforcement edges. Add a few
substeps/deep dives for queue-token enforcement, payment state, GA inventory, and
inventory reconciliation, and this becomes a very solid senior/staff-level
ticketing system design walkthrough.
