# Review: Payment System - System Design

Reviewed file: `data/book/payment-system/interview.json`
Review date: 2026-06-08

## Executive Summary

The recent changes moved this from a strong correctness-first outline to a
near-flagship payment-system walkthrough. The earlier high-impact gaps are now
mostly addressed: the data model includes `payment_events`,
`ledger_transactions`, `refunds`, `payouts`, `psp_events`, and
`reconciliation_breaks`; Step 4 has an explicit `capture_unknown` recovery
flow; Step 5 persists signed PSP events before dispatch; Step 7 reserves funds
in the authoritative ledger before bank transfer; reconciliation has a break
lifecycle; `technologyChoices` is present; and requirement traceability now
covers all functional and non-functional bullets.

The remaining issues are not architecture-breaking. They are mostly alignment
problems between the newly strengthened prose and the API/diagram surfaces. The
largest remaining risk is that the API example still makes capture look
synchronously final while the core design teaches asynchronous capture and
in-doubt recovery. The webhook diagram also still routes event application
through the `Capture` node, even though the text now correctly separates
capture execution from PSP event handling.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.7 / 5 | Correct core patterns and much richer lifecycle state; API semantics and cross-shard protocol need final tightening. |
| Production realism | 4.5 / 5 | PSP ambiguity, payouts, recon, security, and observability are now represented; a few ops tables/fields remain thin. |
| Pedagogical flow | 4.7 / 5 | Strong step-by-step escalation with useful options, traps, and deep dives. |
| Final design coherence | 4.6 / 5 | Major components line up with the steps; webhook/capture ownership could be clearer in the diagram. |
| Dataset/rendering fit | 4.7 / 5 | JSON parses and checked references resolve; old `Snapshot` and `technologyChoices` findings are fixed. |

Recommendation: preserve the step order and most content. Spend the next edit
on API/state wording, separating inbound event workers from capture workers in
views, and adding a small amount of operational metadata to the schema.

## What Works Well

- The case keeps the right payment-system headline: correctness beats
  availability, and exactly-once effect is the target rather than impossible
  exactly-once delivery.
- Requirements and capacity are now better aligned. The capacity section calls
  out that ledger writes exceed the two-row minimum once fees, reserves,
  refunds, chargebacks, payouts, and corrections are included, and it separates
  webhook/payout/reconciliation bursts from the charge path.
- The API includes the important starter endpoints: idempotent payment create,
  idempotent refund, payment status/history, balance read, and PSP webhook.
- The data model now carries the guarantees the prose teaches: event history,
  transaction headers, refund and payout state, webhook inbox, reconciliation
  break workflow, idempotency fingerprinting, and outbox relay metadata.
- Step 4's in-doubt PSP recovery flow is a major improvement. It names stable
  PSP idempotency keys, `capture_unknown`, status lookup, webhook recovery,
  settlement reconciliation, and deduped ledger posting.
- Step 5 now teaches the right inbound-event pattern: verify signature, persist
  raw event, dedupe by PSP event id, defer out-of-order events, and dispatch by
  event type.
- Step 7 now fixes the previous payout safety issue. The sequence preflights
  the read model, reserves funds strongly in the ledger, calls bank rails with a
  stable reference, then finalizes or reverses.
- Reconciliation is treated as an operating model, not only a compare job:
  break states, owners, approvals, correcting transactions, stale-file alerts,
  and aging thresholds are present.
- The new `technologyChoices` section is payment-specific and useful: ledger
  stores, idempotency stores, queues/outbox, reconciliation ingestion, balance
  projection, secrets/compliance, and observability.

## Highest-Impact Issues

### 1. The API example still makes capture look synchronously final

`POST /v1/payments` accepts `"capture": true` and returns `201 Created` with
`"status": "captured"`. That is a valid product shape for a simple synchronous
gateway, but it conflicts with the main walkthrough after Step 4, where capture
is intentionally asynchronous and can enter `capturing` or `capture_unknown`.

Why it matters: the dataset now teaches that PSP capture is ambiguous and that
ledger posting must be recovered by PSP reference/webhook/reconciliation. The
front-door API should not imply the service can always synchronously know and
return final captured state.

Concrete fix: choose and document one of these shapes:

- Return `authorized`, `processing`, or `capturing` from `POST /payments` when
  capture is asynchronous, with `GET /payments/{id}` showing later transitions.
- Add a separate `POST /v1/payments/{id}/capture` endpoint if the design wants
  explicit auth-then-capture.
- If the API keeps `"capture": true`, show that the response may be
  `captured`, `capturing`, or `capture_unknown`, and include the PSP reference
  used for recovery.

### 2. Webhook event application is still visually conflated with capture

The prose and traps now correctly say that capture execution and PSP event
application are distinct. The architecture view still routes inbound webhooks
from `Queue` to `Capture`, and the final design includes `queue-capture`.
One sequence aliases the `Capture` participant as "Event Worker", but the node
identity remains `Capture`.

Why it matters: candidates should learn that outbound capture workers drive our
own requested capture, while inbound PSP event workers apply external truth
such as settlement, dispute, refund result, chargeback, or late failure. Using
one node for both can reintroduce the exact trap Step 5 warns against.

Concrete fix: add a separate canonical node such as `EventWorker` or
`PspEventWorker`, connect `WebhookSvc -> Queue -> EventWorker -> DB/Ledger`,
and keep `Capture` for `Queue -> Capture -> PSP -> Router/Ledger`. The final
diagram can still stay compact, but the ownership distinction should be visible.

### 3. The data model is much better, but a few operational records are still implicit

The model now includes the right major entities. A few details are still
prose-only or partially represented:

- Reconciliation deep dives mention settlement-file import metadata, but the
  model only has `reconciliation_breaks.statement_file_id`; there is no
  `statement_files` / `settlement_imports` entity with sequence, completeness,
  provider, file hash, and processing status.
- `reconciliation_breaks.amount_delta` lacks currency, which matters in any
  payment system.
- `psp_events` has `status` but no attempts, `last_error`, deferred-until time,
  or dead-letter/escalation marker.
- `payouts` has the core reserve/finalize IDs, but no failure reason,
  callback/event id, or retry ownership fields.
- `payments` carries amount/currency/status but does not store `order_id` or a
  tokenized source reference, even though the API request includes both.

Why it matters: these fields are where real operators recover stuck money
movement. The design does not need a banking-grade schema, but the records that
drive replay, escalation, and audit should be visible.

Concrete fix: add a small `statement_files` entity, add currency to recon
breaks, and add retry/error/callback metadata to `psp_events` and `payouts`.
Add `order_id` and `source_token` or explicitly say those live in an adjacent
orders/tokenization system.

### 4. Cross-shard ledger semantics need one more level of precision

Step 8 gives a credible default: shard by account, use clearing accounts, and
handle cross-shard transfers as sagas checked by reconciliation. That is good
interview material. The remaining ambiguity is how the system prevents a
cross-shard half-write from becoming available money before the matching side
appears.

Why it matters: "reconciliation catches it later" is useful as a safety net,
but a payment system should also define the write protocol and visibility rule
for pending cross-shard ledger transactions.

Concrete fix: add a short note in the cross-shard deep dive:

- Each side writes a shard-local entry with the same global `transaction_id`.
- Entries stay `pending` or non-available until both sides are observed.
- A coordinator/outbox record retries the missing side.
- Reconciliation pages immediately on aged half-transactions.
- Balance projections ignore pending/incomplete transactions.

### 5. The wrap-up teaching material should catch up with the stronger core

The interview script and level variants are still useful, but they read closer
to the older version of the case. They do not explicitly ask candidates to name
the new `capture_unknown` recovery path, payout reservation before bank rails,
webhook inbox/event dispatch, or reconciliation break operating model.

Why it matters: these are now the differentiating senior/staff signals in the
dataset. If the wrap-up does not mention them, interviewers may underuse the
best parts of the case.

Concrete fix: revise the script and level variants lightly:

- Senior: must explain PSP in-doubt recovery and distinguish capture worker
  from event worker.
- Staff+: must define the payout consistency guard, recon break workflow,
  cross-shard pending visibility, and money-movement observability signals.
- Follow-ups should separate "covered in the main design" from "extension
  topics" such as multi-currency FX, multi-PSP routing, fraud, and partial
  capture product semantics.

## System Design Soundness

### Requirements and Capacity

The requirements are now well scoped and traceable. All six functional and all
six non-functional bullets have corresponding `satisfies` rows. The capacity
section also now avoids an earlier simplification by saying `~4,000+ tps`
ledger writes is only the minimum and by calling webhook/payout/recon workloads
separate, bursty dimensions.

Further improvement would be optional: add merchant/account cardinality,
refund/chargeback ratios, webhook retry spikes, and settlement-file sizes if
the case needs more capacity math. The current level is sufficient for most
system-design interviews.

### API

The API surface is strong but should align with the asynchronous state machine.
The payment create response should not always be `captured` if the main design
uses an outbox and capture worker. Refund response examples are better now:
`remaining_refundable`, `psp_reference`, and partial refund state are visible.
Payment status now includes an event history that maps to `payment_events`.

Add merchant/account scope to idempotency examples if you want to make tenant
isolation explicit.

### Data Model

The data model is now one of the strengths of the case. The new entities give
the learner concrete places to attach invariants:

- `ledger_transactions` groups balanced entries and dedupes by idempotency key
  or PSP event id.
- `payment_events` backs lifecycle history.
- `refunds` and `payouts` make post-charge money movement explicit.
- `psp_events` is the webhook inbox and replay source.
- `reconciliation_breaks` turns finance discrepancies into work items.
- `idempotency_keys` includes scope, request fingerprint, lock lease, response,
  and expiry.
- `outbox` includes aggregate ordering and retry/error columns.

The remaining data-model work is operational polish rather than missing core
architecture: statement import rows, currency on breaks, callback/retry fields,
and explicit source/order correlation.

### Architecture

The architecture has the right components: gateway, payment service,
idempotency store, payments DB, outbox, queue, capture worker, PSP, webhook
receiver, ledger router, sharded ledgers, reconciliation service, settlement
file, balance read model, payout service, and bank rails.

The one architectural ownership issue is inbound PSP event processing. A
separate event worker would make the final design match the now-strong prose.

## Step-by-Step Pedagogical Review

### Step 1: Synchronous Charge

Good baseline. It exposes the unsafe external PSP call and the crash-after-PSP
hazard through the trap. This step should remain intentionally naive.

### Step 2: Idempotency Keys

Strong step. It covers client-supplied keys, atomic claims, replayed responses,
request fingerprinting, and the trade-off between primary DB and dedicated key
store. This is now grounded by a richer `idempotency_keys` model.

### Step 3: Double-Entry Ledger

Still the strongest conceptual step. The double-entry option, mutable-balance
counter-option, traps, and balanced-entry invariant are concrete and useful.
The new `ledger_transactions` entity makes the invariant much easier to teach.

### Step 4: Asynchronous Capture & State Machine

Substantially improved. The in-doubt flow is exactly the kind of production
realism this case needed: persist intent, send stable PSP idempotency key,
enter `capture_unknown`, recover through lookup/webhook/settlement, and post
ledger entries once by PSP reference.

The main API example should now be updated so this step does not contradict the
front-door response shape.

### Step 5: Webhooks & Exactly-Once Inbound Events

The content is strong: signature verification, fast ack, dedupe, raw inbox,
deferred out-of-order events, and dispatch by event type. The remaining issue is
diagram/node naming. Make `EventWorker` a visible node so the diagram teaches
the same distinction as the deep dive.

### Step 6: Reconciliation Against the PSP

This moved from conceptual to operational. The break lifecycle, owners,
approval path, correcting ledger transaction, and alert thresholds are good
senior-level material. Add a `statement_files` data-model row if you want the
schema to fully match the deep dive.

### Step 7: Payouts & Balance Read Model

The previous safety issue is fixed. The flow now correctly treats the read
model as a preflight hint, then reserves funds strongly in the ledger before the
bank transfer and finalizes or reverses based on the result.

Consider adding failure/callback metadata to `payouts` so the recovery behavior
is visible in the schema, not only the sequence.

### Step 8: Scaling the Ledger

Sharding by account with clearing accounts is a credible default, and the
single-primary counter-option is a fair comparison. The hot-account,
resharding, shard-local ordering, and all-shards reconciliation deep dive is a
good addition.

Tighten the cross-shard visibility rule so pending half-transactions cannot
pollute available balances.

### Step 8a: Where Money Demands Strong Consistency

This remains a valuable sub-step. The security/compliance and observability
deep dives now make the case feel much more production-realistic. This step
should stay near the end because it lets the candidate classify the design
choices they have already made.

## Final Design Review

The final design is coherent and much stronger than the previous review
described. It includes the major components introduced in the steps and the
description now explicitly names:

- balanced transaction headers,
- `capture_unknown`,
- persisted `psp_events`,
- reconciliation break lifecycle,
- rebuildable balance read model,
- payout reservation before bank transfer,
- lifecycle state in `payment_events`, `refunds`, `payouts`, and
  `reconciliation_breaks`.

The final diagram itself stays clean, which is the right choice. The only
change I would make is to split the capture/event-worker ownership. Optionally
update the final diagram caption to mention "reserve before bank transfer" so
the payout ordering remains visible even when someone only scans the diagram.

## Concept Introduction and Learning Flow

The learning flow is excellent:

- Synchronous charge exposes external uncertainty.
- Idempotency handles safe retries.
- Double-entry ledger establishes the source of truth.
- Outbox and async capture handle long-running PSP workflows.
- In-doubt recovery handles ambiguous external outcomes.
- Webhooks handle external asynchronous truth.
- Reconciliation handles drift and finance-ops repair.
- Balance read model and payouts handle scalable reads without giving up money
  correctness.
- Sharding and consistency choices handle scale and correctness budgets.

The concepts are introduced just in time. The recent additions make the case
more realistic without bloating the early steps.

## Step-to-Final-Design Coherence

Most step components appear cleanly in the final design:

- `Idem` from Step 2 appears in final design.
- `Ledger` evolves into `LedgerA` and `LedgerB`.
- `Outbox`, `Queue`, and `Capture` from Step 4 appear in final design.
- `WebhookSvc` from Step 5 appears in final design.
- `Recon` and `Statement` from Step 6 appear in final design.
- `Balance`, `Payout`, and `Bank` from Step 7 appear in final design.
- `Router`, `LedgerA`, and `LedgerB` from Step 8 appear in final design.

The one weak transition is `Capture`: it represents outbound capture in Step 4
and inbound event application in Step 5. Split that role and the coherence issue
goes away.

## Realism Compared With Production Systems

This now compares well with production payment architecture at the interview
level. The dataset covers the high-value realities: PSP boundaries are
ambiguous, retries are normal, ledger writes must be idempotent, webhooks are
untrusted and duplicated, reconciliation is required, payouts are guarded by
available funds, and operational signals matter.

The remaining realism gaps are small and specific:

- The API should expose asynchronous or in-doubt states honestly.
- A settlement-file import table should back the reconciliation workflow.
- PSP event and payout rows should carry retry/error/callback state.
- Cross-shard pending visibility should be explicit.
- Fraud/risk and KYC/AML are present in security notes, but they remain
  extension points rather than flow participants. That is acceptable if the
  case stays focused on ledger correctness.

## Dataset and Renderer-Facing Observations

- `python3 -c "import json; json.load(...)"` succeeds for
  `data/book/payment-system/interview.json`.
- Checked step `view.nodes`, step `view.links`, final-design `view.nodes`,
  final-design `view.links`, and `satisfies[*].steps[*]`; references resolve.
- The prior missing `Snapshot` node issue is fixed. `Snapshot` is now a
  canonical high-level node with type `database`.
- The prior `technologyChoices` issue is fixed. The dataset now has seven
  payment-specific technology choice concerns.
- `satisfies.functional` and `satisfies.nonFunctional` now each have six rows,
  matching the six functional and six non-functional requirements.
- The high-level architecture still includes sequence-friendly alias nodes
  (`C`, `X`, `K`, `L`) alongside full nodes (`Client`, `PSP`, `Bank`,
  `Ledger`). This does not break rendering, but keeping aliases sequence-local
  would make the canonical node catalog cleaner.
- Technology choices currently render as bare strings. That is schema-valid; if
  visual polish is desired, run the tech-icon assignment workflow separately.
- Do not rebuild `docs/` for this review-only file; `REVIEW.md` is repo-only.

## Recommended Edits, Prioritized

### P1: Align API semantics with async capture

Update `POST /v1/payments` so it can return `authorized`, `capturing`,
`processing`, or `capture_unknown`, or add a separate capture endpoint. Make
the API example reflect the Step 4 state machine.

### P1: Split capture worker from PSP event worker

Add a distinct inbound event worker/dispatcher node and route webhook events to
it in Step 5 and the final design. Keep `Capture` for outbound capture work.

### P2: Add operational schema fields

Add `statement_files`, currency on reconciliation breaks, retry/error/deferred
metadata on `psp_events`, callback/failure metadata on `payouts`, and
order/source correlation on `payments` or explicitly scope it elsewhere.

### P2: Tighten cross-shard pending visibility

Explain how cross-shard ledger writes remain pending/non-available until both
sides are posted and observed, and how aged half-transactions are retried and
alerted.

### P2: Refresh script and level variants

Update interviewer script and level expectations to call out `capture_unknown`,
webhook inbox/event dispatch, payout reservation, reconciliation break
workflow, and money-movement observability.

### P3: Renderer and presentation polish

Consider sequence-local aliases instead of global alias nodes, add tech icons
for the new technology choices, and optionally add AI visuals if this dataset
is meant to match image-rich flagship cases.

## What Not To Change

- Keep the correctness-first framing.
- Keep the step order. It now builds naturally from naive charge to safe
  retries, ledger, outbox, webhooks, reconciliation, payouts, sharding, and
  consistency budgeting.
- Keep double-entry ledger as the source of truth.
- Keep transactional outbox and webhook dedupe as explicit steps.
- Keep the in-doubt PSP recovery flow.
- Keep reconciliation as a first-class step.
- Keep Step 8a as a sub-step under ledger scaling; it is a good senior/staff
  discussion without bloating the main spine.

## Bottom Line

The recent changes addressed the main correctness and production-realism gaps.
This is now a strong payment-system interview with a credible money-movement
story. The next improvements are targeted: make the API honest about async
capture, split inbound event processing from capture execution in diagrams, and
add a few operational fields that make recovery and finance-ops workflows fully
auditable.
