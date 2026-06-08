# Review: Ticketmaster - System Design

Reviewed file: `data/book/ticketmaster/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a strong book-style interview dataset. It now covers the hard parts of
high-demand ticketing: fixed scarce inventory, flash-crowd admission, atomic
reserved-seat holds, GA counters, payment state, expiry, reconciliation, and
hot-event isolation. The earlier gaps around admission tokens, payment attempts,
GA inventory, and final checkout/expiry edges have mostly been addressed. The
latest source changes also resolve the previous `Lottery` node issue and make
the lock-TTL-only option clearly show stale durable state rather than implying
automatic inventory cleanup.

| Axis | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.5 / 5 | Correct invariant framing, strong write-path mechanics, good data model. |
| Production realism | 4.2 / 5 | Good payment, queue, and capacity treatment; a few ops paths remain implicit. |
| Pedagogical flow | 4.5 / 5 | The main steps and substeps build cleanly from failure to robust design. |
| Dataset/rendering fit | 4.5 / 5 | Targeted structural checks are clean; remaining issues are content coherence. |
| Overall | 4.4 / 5 | Very usable; remaining work is tightening final-wrap coherence. |

## What Works Well

- The walkthrough starts from the right failure: naive check-then-write creates a
  double-sell race under contention.
- Reads and writes are separated well: CDN/read model for browsing, authoritative
  reserve/checkout paths for correctness.
- The substeps are high-value and well placed: `multi-seat-locking`,
  `admission-tokens`, `checkout-state-machine`, and `ga-counters` each deepen a
  concrete correctness gap without bloating the main story.
- The API now enforces hot-event admission with `X-Admission-Token` and includes
  a queue-status endpoint.
- The data model is much more credible than a simple seats/orders sketch:
  composite seat keys, `hold_seats`, `order_seats`, `payment_attempts`,
  `queue_tokens`, and `ga_inventory` all support behavior later discussed.
- The lottery/scheduled-window alternative now uses a canonical architecture
  node, and the lock-TTL-only option now teaches the stale-hold failure clearly.
- Traps, failure drills, interviewer signals, and level variants are practical
  and domain-specific.

## Highest-Impact Issues

### 1. Final Design Underrepresents the Newer Correctness Components

The final design shows the main reserved-seat flow and now includes the critical
checkout-to-router `held -> sold CAS` plus expiry-to-shard release edges. That is
a good fix. But it still omits several components introduced as important in the
steps: `GA`, `Idem`, `Recon`, `Outbox`, `Stream`, and `Audit`.

Why it matters: the Final Design page is the learner's consolidated answer. If a
candidate studies that diagram alone, GA support, idempotent retry state,
payment reconciliation, and the outbox/audit path look optional or absent even
though the walkthrough teaches them as important for correctness.

Concrete fix: add a small GA/reconciliation lane to `finalDesign.view` or state
explicitly in the caption that GA/reconciliation are not drawn. Consider adding
`Idem` near `Reserve`/`Checkout`, `Recon` near `Order`/`Payment`, and replacing
the direct shard-to-cache links with an optional `Outbox -> Stream -> Cache/Audit`
path if the final diagram can tolerate the extra nodes.

### 2. Anti-Abuse Placement Is Inconsistent Across Step 8 and Final Design

The `scale` step view routes `Gate -> AntiBot -> Router`, while the final design
routes `Client -> AntiBot -> WaitRoom -> Gate -> API`. The deep dive says to
rate-limit and fingerprint before tokens are issued, which matches the final
design better than the step diagram.

Why it matters: for ticketing, anti-abuse is part of fairness. If it happens
after admission, bot traffic may already have queue positions or tokens.

Concrete fix: align Step 8 with the final design by showing anti-abuse before
waiting-room token issuance, then optionally a second reserve-side recheck after
`Gate`. If the intent is "defense in depth", label the two checks separately.

### 3. Wrap-Up Links Understate the Substep-Level Design

The `satisfies` section resolves structurally, but most requirements point only
to parent steps. Several requirements are actually satisfied by substeps:
`multi-seat-locking`, `admission-tokens`, `checkout-state-machine`, and
`ga-counters`.

Why it matters: the wrap-up page is where learners connect requirements to
design mechanisms. If substeps are not linked, the strongest parts of the
dataset look like optional elaboration rather than the concrete reason the
requirements are met.

Concrete fix: add the relevant substep IDs to the affected `satisfies` rows,
especially "Reserve specific seats", "Complete purchase", "Support GA and
reserved seating", "Never double-sell or oversell", "Fairness", and "Graceful
degradation".

### 4. A Few Production Details Are Still Mentioned More Than Modeled

The capacity section now names PSP throughput as a likely bottleneck and the API
has a queue-status endpoint, which are good improvements. The architecture still
does not model what happens when the PSP is the slow lane, how queue-status
polling is kept from becoming another herd, or how queue state recovers after a
waiting-room outage.

Concrete fix: add concise notes or a small deep-dive paragraph covering PSP
backpressure, queue polling/backoff, and persisted queue/admission state. Keep
these as operational refinements, not new top-level steps.

## System Design Soundness

Requirements are well scoped: browse, reserve, checkout, expiry, reserved seats,
GA, no oversell, fairness, burst handling, bot resistance, and graceful
degradation. The capacity section is also strong because it frames the bottleneck
as buyers-per-seat and admission rate, not generic request throughput.

The API surface supports the architecture. `POST /reservations` requires an
admission token and idempotency key, and checkout is separated from reserve. One
minor production caveat: the reservation request includes `user_id` in the body.
In a real system, identity should come from auth/session context, with the token
bound to that identity, not from a client-supplied field.

The data model supports the promised behavior. The composite seat key, join
tables for seats, payment attempts, queue token metadata, and GA inventory table
all map to real invariants. For additional rigor, `ga_inventory` could include
an original capacity or sold count field so the reconciliation statement
`remaining + reserved + sold == pool` is directly backed by modeled columns.

The architecture is mostly sound. The write path treats inventory CAS / GA
decrement as authoritative, and the lock store is correctly framed as an
accelerator. Expiry, checkout, and reconciliation are present in the steps. The
main remaining architecture issue is final-design selectivity: it chooses a
clean diagram at the cost of hiding some components that are important to the
book-level answer.

## Step-by-Step Pedagogical Review

### Step 1: Naive Buy

Good baseline. It exposes the exact race the rest of the design solves. Keep it
short and intentionally flawed.

### Step 2: Browse Read Model

Strong just-in-time introduction of stale reads plus authoritative write checks.
The deep dive correctly says displayed availability is a hint. This step gives a
candidate permission to optimize reads without weakening no-oversell.

### Step 3: Atomic Reservation with Seat Locking

Good main step and options. It compares lock-store speed against DB CAS
simplicity without making the lock store the final source of truth. The
multi-seat substep is the right place for ordered acquisition, rollback, fencing,
and idempotent retries.

### Step 4: Holds and TTL Expiry

The default sweeper plus lazy check option is realistic. The bad TTL-only option
now teaches the intended failure: a lock TTL can lapse while the durable hold and
inventory row remain stale. That is much clearer than implying automatic
propagation from the lock store to the inventory DB.

### Step 5: Virtual Waiting Room

Strong core step: queue position, admission gate, and metered entry are exactly
the right interview concepts. The `admission-tokens` substep is especially good
because it turns the waiting room from UI theater into an enforced control
plane. The lottery/scheduled-window option now has a canonical architecture node,
so it reads as a legitimate alternative rather than an implicit renderer node.

### Step 6: Checkout and Payment Integration

Good payment story. The default option handles hold verification, idempotent
charge, and held-to-sold conversion; the state-machine substep adds the needed
payment attempt and reconciliation details. Consider cross-linking the substep
from `satisfies.functional["Complete purchase"]`.

### Step 7: Overbooking and GA Counters

This is one of the strongest sections. It clearly says lock state is not
authoritative and separates reserved seats from GA counters. The GA substep is
necessary because GA cannot be hand-waved as "just seats without seat IDs".

### Step 8: Scaling and Anti-Abuse

The event-sharding and blast-radius story is strong. The anti-abuse ordering
should be made consistent with the final design and deep dive: screen before
queue-token issuance, then optionally recheck at reserve.

## Final Design Review

The final design is coherent for the reserved-seat happy path:

- Client reads static/availability data through CDN/search/cache.
- Anti-abuse and waiting-room admission gate load before it reaches the booking
  API.
- Event router sends reserve traffic to per-event reservation services, lock
  stores, and inventory shards.
- Expiry releases holds, locks, and inventory shard state.
- Checkout verifies/renews the hold, charges payment, routes held-to-sold CAS,
  and writes orders.

The missing piece is coverage of the substep-level correctness systems. If the
final diagram remains intentionally simplified, its caption should say so. If it
is intended as the full senior/staff design, add GA, idempotency, reconciliation,
and outbox/audit components.

## Concept Introduction and Learning Flow

The concept staging is excellent: contention first, read-model staleness second,
atomic reservation third, expiry fourth, admission fifth, checkout sixth,
authoritative consistency seventh, and blast-radius/abuse last. Substeps are
used correctly for depth rather than as extra top-level detours.

The concepts and traps are concrete enough to coach an interview answer. The
best examples are fencing tokens, admission windows, hold renewal during
payment, and decrement-if-positive. These are precise mechanisms, not generic
"make it scalable" advice.

## Step-to-Final-Design Coherence

Most main steps now appear in the final design. The coherence gaps are:

- `ga-counters` is not represented in the final view even though GA is a stated
  functional requirement.
- `checkout-state-machine` introduces `Recon`, but final design omits it.
- `overbooking` introduces outbox/stream/audit as a staff-level freshness and
  reconciliation path, while final design uses direct shard-to-cache updates.
- `multi-seat-locking` teaches idempotency storage, but final design omits
  `Idem`.
- `satisfies` links point mostly to parent steps. They resolve, but the wrap-up
  would teach better if it also linked to `multi-seat-locking`,
  `admission-tokens`, `checkout-state-machine`, and `ga-counters`.

## Realism Compared With Production Systems

The dataset is production-realistic for an interview. It covers the concerns
that usually separate a shallow ticketing answer from a credible one: admission
control, identity-bound tokens, all-or-nothing multi-seat holds, fencing,
payment idempotency, reconciliation, event isolation, and bot resistance.

Remaining realism opportunities are refinements, not missing foundations:

- Model how queue admission is persisted and recovered if the waiting-room
  service fails during an on-sale.
- Add queue polling/backoff and client retry guidance so 1M users do not create
  a status-polling herd.
- Expand PSP backpressure: if the payment provider caps at 1-2k TPS, checkout
  should queue, shed, or meter downstream calls explicitly.
- Mention seat-map versioning, seat adjacency, ticket delivery/barcodes, and
  resale/transfer only as follow-ups. They should not become main steps.

## Dataset and Renderer-Facing Observations

- JSON parses successfully.
- `steps[*].parent` references resolve.
- `satisfies[*].steps[*]`, `patterns[*].steps[*]`, and `probeLinks` resolve.
- Main step, option, and final `view.nodes` / `view.links` references resolve.
- Highlights resolve to known architecture nodes.
- Sequence participants resolve to canonical node IDs.
- The latest source change fixed the previous `Lottery` option node miss.
- The book-wide verifier still fails on unrelated datasets, but reports no
  `ticketmaster` issues.
- `REVIEW.MD` is repo-only and skipped by the build; the built Ticketmaster JSON
  copy already matches the source JSON for the current data changes.

## Recommended Edits, Prioritized

### P1: Decide how complete the Final Design should be

Either add GA, idempotency, reconciliation, and outbox/audit paths to the final
view, or explicitly label them as omitted substep/deep-dive components.

### P2: Align anti-abuse ordering

Make Step 8's view match the final design: anti-abuse before waiting-room token
issuance, with optional reserve-side recheck if desired.

### P2: Improve wrap-up cross-links

Add substep links in `satisfies` for requirements that depend on them:
`multi-seat-locking`, `admission-tokens`, `checkout-state-machine`, and
`ga-counters`.

### P3: Add small production refinements

Add GA capacity/sold fields, queue recovery/backoff notes, PSP backpressure
handling, and auth-derived identity language for reservation requests.

## What Not To Change

- Do not add more top-level steps; the eight-step spine is already the right
  interview length.
- Keep the naive baseline. It makes the double-sell race concrete.
- Keep stale browse reads separate from authoritative reserve writes.
- Keep GA as a substep under consistency; that is the right level of detail.
- Keep ticket delivery, resale, dynamic pricing, presales, and venue versioning
  as follow-ups unless this becomes a broader ticketing-platform case.

## Bottom Line

This is a high-quality ticketing system design walkthrough. The remaining work
is not adding more material; it is tightening final-design completeness,
anti-abuse ordering, and wrap-up links so the rendered experience matches the
strong correctness story already present in the JSON.
