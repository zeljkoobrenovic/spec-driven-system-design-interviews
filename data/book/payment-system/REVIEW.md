# Review: Payment System - System Design

Reviewed file: `data/book/payment-system/interview.json`  
Review date: 2026-06-08

## Executive Summary

This is a strong correctness-first payment-system walkthrough. The case has the
right spine for a serious interview: naive synchronous charge, idempotency,
double-entry ledger, outbox-driven async capture, signature-verified webhooks,
line-item reconciliation, payout safety, ledger sharding, and consistency
budgeting. The step order is coherent and teaches why each new mechanism exists.

The main gaps are production-depth and traceability issues rather than a broken
architecture. Refunds, disputes, payouts, settlement breaks, and external PSP
ambiguity are mentioned, but the data model and flows do not yet carry enough
state to make those workflows fully operational. The payout sequence also reads
like it can transfer based on the read model before reserving funds in the
authoritative ledger, which conflicts with the later consistency guidance. The
dataset would benefit from a more explicit operational/security layer and a
book-style `technologyChoices` section.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.2 / 5 | Strong core patterns; refund/dispute/payout/recon state needs more concrete modeling. |
| Production realism | 3.8 / 5 | Good failure drills, but PSP ambiguity, finance-ops workflows, PCI/fraud/security, and observability are thin. |
| Pedagogical flow | 4.5 / 5 | Clear problem-by-problem buildup with useful options, traps, and interviewer signals. |
| Final design coherence | 4.1 / 5 | Final diagram integrates the major components, but some important guarantees are still prose-only. |
| Dataset/rendering fit | 4.2 / 5 | JSON parses and most references resolve; one option-only node lacks canonical metadata, and traceability could be tighter. |

Recommendation: keep the step order and core framing. Focus edits on state
shape, external-boundary ambiguity, payout safety, operations/security, and
renderer metadata.

## What Works Well

- The framing is unusually clear for payments: correctness beats availability,
  and "exactly-once effect" is distinguished from impossible exactly-once
  delivery.
- The capacity section ties directly to design choices: ~2k charge tps, ~4k
  ledger writes, ~50k balance reads, and append-only ledger growth motivate the
  ledger, projection, and sharding steps.
- The API section covers the essential boundaries: idempotent payment creation,
  idempotent refunds, status lookup, balance lookup, and inbound PSP webhooks.
- The double-entry ledger step is the strongest part of the case. It teaches the
  zero-sum invariant, immutability, reversing entries, and why mutable balances
  are dangerous.
- The outbox step correctly avoids dual writes and teaches at-least-once relay
  plus idempotent consumers.
- The webhook step handles signature verification, dedupe, fast ack, duplicate
  delivery, and out-of-order events.
- The reconciliation step names line-item matching and compensating entries,
  which is the right production instinct for money systems.
- Step 8a is a useful senior/staff-level addition. It forces candidates to say
  where strong consistency is required and where eventual consistency is fine.

## Highest-Impact Issues

### 1. Refunds, disputes, and chargebacks are under-modeled

The requirements and API promise full and partial refunds, PSP disputes, late
failures, and settlement outcomes. In the dataset, those mostly appear as
phrases:

- `POST /v1/payments/{id}/refunds` exists, but there is no `refunds` entity.
- The `payments.status` enum has only `authorized`, `captured`, `refunded`,
  and `failed`, which is too flat for partial refunds, partial captures,
  chargebacks, dispute reversals, and late settlement failures.
- `GET /v1/payments/{id}` returns an `events` array, but the data model has no
  payment events/status history table.
- Webhooks mention disputes and late failures, but the flow routes everything to
  the capture worker and does not show event-specific handlers or state
  transitions.
- The follow-ups ask about disputes and partial captures, which implies those
  are out of scope, but the functional requirements already include PSP
  asynchronous disputes.

Why it matters: a production payment system is mostly lifecycle edge cases after
the initial charge. Without explicit refund/dispute/capture state, candidates
can explain the happy path but cannot reason about "captured then partially
refunded", "disputed weeks later", or "PSP says settled but our ledger does not".

Concrete fix: add a compact state model rather than a large schema rewrite:

- Add `refunds` with `refund_id`, `payment_id`, `amount`, `status`,
  `idempotency_key`, `psp_reference`, and `ledger_transaction_id`.
- Add `payment_events` or `payment_state_transitions` with event type, source,
  PSP event id, old/new status, and timestamps.
- Expand status vocabulary or document that status is aggregate while detailed
  lifecycle lives in event rows.
- Add one refund/dispute flow showing webhook -> state transition -> reversing
  ledger transaction -> reconciliation.

### 2. The data model is too small for the guarantees it teaches

The current model has `accounts`, `ledger_entries`, `payments`,
`idempotency_keys`, and `outbox`. That is a good starter model, but several
guarantees in the prose need more durable state:

- There is no `ledger_transactions` header row to group entries, store
  idempotency key/event id, source object, reason code, reversal link, and
  balanced/write status.
- `ledger_entries` has no `direction`/entry type, `available_at`,
  `pending/available` bucket, shard key, or external reference.
- `idempotency_keys` lacks request fingerprint/hash, expiry, `locked_until`,
  owner/merchant scope as structured columns, and recovery metadata for
  `in_progress`.
- The outbox table has no unique aggregate sequence, retry/error columns, or
  relay ownership fields.
- There is no `psp_events` or webhook inbox table, even though the webhook step
  says out-of-order events must be persisted and retried.
- There is no reconciliation break/exception table, even though the recon step
  says breaks are surfaced for repair.

Why it matters: the interview teaches the right invariants, but the schema does
not yet show where those invariants are enforced or audited. A candidate could
hand-wave idempotent recovery, ledger dedupe, and finance ops because the model
does not force them to name the records.

Concrete fix: add a few targeted entities, not an exhaustive banking schema:

- `ledger_transactions` for balanced transaction headers.
- `psp_events` / webhook inbox for signed, deduped, out-of-order external
  events.
- `reconciliation_breaks` for unmatched/mismatched settlement lines, owner,
  state, reason, and resolution ledger transaction.
- Optional `payouts` and `refunds` state rows if the case keeps those flows in
  scope.

### 3. PSP ambiguity is acknowledged but not fully carried through the flows

The dataset correctly says the PSP is outside the transaction boundary. Step 2
also has a failure drill for crashing after claiming an idempotency key, and
Step 4 has a drill for crashing after PSP capture but before ledger posting.
Those are the right hazards.

The visuals and API sequences still make the external boundary look cleaner
than it is:

- `POST /payments` shows `authorize + capture` followed by immediate ledger
  posting and `201 captured`.
- The async capture flow says the PSP capture is idempotent, but the request
  labels do not show the PSP idempotency key/correlation id that makes that
  possible.
- The in-doubt state after timeout or unknown PSP response is not represented
  as a payment state.
- Webhook processing uses the capture worker as the generic consumer, which
  blurs capture execution with PSP event application.

Why it matters: payment correctness depends on handling "we do not know whether
the external PSP did the thing" as a first-class state. This is where many real
double-charge or missing-ledger incidents happen.

Concrete fix: add a short deep dive or flow for the in-doubt window:

- Persist intent before the PSP call.
- Send a stable PSP idempotency key/correlation id.
- If the call times out, mark `requires_reconciliation` or `capture_unknown`.
- Recover by querying PSP status, consuming webhook, or reconciling settlement.
- Only post ledger entries once, keyed by PSP reference/event id.

### 4. The payout path conflicts with the "read model is not authority" lesson

Step 7 correctly warns that the balance read model is eventually consistent and
must not be the source of truth for money decisions. The failure drill says
payouts re-check the authoritative ledger transactionally.

The main payout sequence still shows:

1. Payout service reads `Balance`.
2. It transfers to bank rails.
3. It posts ledger entries.

That visual order is risky. It can be read as "transfer first, account later",
and it appears to rely on the read model for available funds. The final design
also links payout to `Balance` and bank transfer, but does not show a reserve or
strong ledger debit before the external bank call.

Why it matters: payout is a double-spend problem. The safe sequence is usually
reserve/debit available funds in the authoritative ledger or payout state first,
then call bank rails idempotently, then finalize based on bank result.

Concrete fix: update the payout flow and view to show:

- `request payout (Idempotency-Key)`.
- Strong ledger transaction or lock that moves funds from merchant available to
  payout pending/reserved.
- Bank transfer with a stable payout reference.
- Bank callback/reconciliation updates payout state.
- Final ledger entries or reversal if the transfer fails.

The read model can still serve dashboards and preflight checks, but the final
guard should be a ledger transaction.

### 5. Reconciliation lacks an operating model

The reconciliation step has the right conceptual advice: line-item matching,
timing breaks, compensating entries, and late/partial file handling. What is
missing is the workflow around the breaks:

- No persisted settlement file/import metadata.
- No `reconciliation_breaks` table or state machine.
- No owner/assignment/escalation path for finance ops.
- No threshold for alerting on break count, unmatched amount, stale files, or
  aging breaks.
- No distinction between automated resolution, timing deferral, and manual
  approval.

Why it matters: reconciliation is not just a nightly comparison job. It is an
operational workflow with SLAs, controls, approvals, and audit evidence.

Concrete fix: add a small "Break lifecycle" deep dive or data model entity with
states such as `detected`, `timing`, `investigating`, `auto_corrected`,
`manual_approved`, `resolved`, and `written_off`, plus metrics for stale and
high-value breaks.

### 6. Security, compliance, and observability are mostly follow-up material

The webhook step covers signature verification, and the ledger is auditable.
That is necessary but not sufficient for a payment-system flagship. The main
walkthrough is light on:

- PCI/tokenization boundaries for card/source data.
- Fraud/risk checks before authorization and payout.
- Merchant onboarding, KYC/AML, payout holds, and sanctions constraints.
- Secret/key rotation for PSP credentials and webhook signatures.
- Operator/admin actions, approval workflows, and audit logs.
- SLOs and alerts for idempotency conflicts, stuck `in_progress` keys, queue
  lag, outbox relay lag, PSP timeout rate, webhook duplicate/out-of-order rate,
  ledger imbalance, projection lag, payout failures, and reconciliation breaks.

Why it matters: the case is aimed at correctness, and production correctness is
not only data structures. It also depends on controls, monitoring, and response
paths when money movement is abnormal.

Concrete fix: add one operations/security wrap-up or Step 8 deep dive. Keep it
small: a table of `signal`, `why it matters`, `page/degrade threshold`, and
`operator action` would be enough.

### 7. Book-specific polish is missing

This dataset has patterns, traps, failure drills, interviewer signals, an
interview script, level variants, and probe links. It does not have
`technologyChoices`, even though newer book datasets use that section to teach
implementation trade-offs.

Good payment-specific concerns would be:

- Ledger store: Postgres/CockroachDB/Spanner/Aurora vs ledger SaaS.
- Idempotency and locks: primary DB unique constraints vs Redis/DynamoDB.
- Queue/outbox relay: Kafka/Debezium/SQS/Pub/Sub/Event Hubs.
- Reconciliation ingestion: object storage + batch engine + workflow queue.
- Balance projection: stream processor plus read-optimized store.
- Secrets and compliance: KMS/HSM, vaults, audit log storage.
- Observability: metrics, tracing, log retention, alerting.

This is not required for rendering, but it would make the payment-system case
feel current with the rest of the book group.

## System Design Soundness

### Requirements and Capacity

The requirements are well scoped and put correctness first. The functional list
covers charge, refund, ledger, payout, status/balance, and async PSP events. The
non-functional list correctly prioritizes no duplicate effects, durability,
strong consistency for money, reconciliation, and idempotent APIs.

The capacity section is useful but could be sharpened:

- `~2,000 tps peak` for charges and `~4,000 tps` for ledger writes assumes the
  minimum two entries per movement. That is fine as a baseline, but fees,
  reserves, refunds, chargebacks, payouts, and reconciliation corrections can
  create more than two entries.
- `~150M entries/day` implies average write volume far below the peak, which is
  plausible. It would help to label it as daily average/retention sizing while
  the tps number is peak path sizing.
- Webhook, payout, and reconciliation volumes are not sized separately. Those
  are the workloads that often stress idempotency, queue lag, and finance ops.

### API

The API covers the necessary starter surface. `Idempotency-Key` on payments and
refunds is the right teaching point, and the webhook endpoint names signature
verification and event-id dedupe.

The API should expose more lifecycle structure if refunds/disputes remain in
scope:

- Include merchant/account scope in idempotency examples.
- Include PSP reference/correlation ids in responses or event history.
- Show partial refund semantics: remaining refundable amount, multiple refunds,
  and failure states.
- Clarify whether `/v1/payments` with `capture: true` returns final captured
  state or accepted/processing when capture is asynchronous.

### Data Model

The model is a strong minimal seed, especially `ledger_entries` and
`idempotency_keys`. It is currently too compressed for the full set of promised
behaviors. Add only the state that carries important invariants: transaction
headers, webhook inbox, refunds/payouts, reconciliation breaks, and status
history.

### Architecture

The architecture components are appropriate: gateway, payment service,
idempotency store, payments DB, outbox, queue, capture worker, webhook receiver,
ledger, reconciliation service, balance model, payout service, bank rails, and
sharded ledgers.

The main architectural gap is that several important ownership boundaries are
not represented:

- Who owns PSP in-doubt recovery?
- Who owns webhook event application versus capture execution?
- Who owns payout state and bank callbacks?
- Who owns finance-ops break resolution?
- Where do observability and audit controls live?

These do not all need new top-level nodes, but they need named responsibilities
in steps or deep dives.

## Step-by-Step Pedagogical Review

### Step 1: Synchronous Charge

This is a good baseline. It exposes the unsafe external call and makes
idempotency feel necessary. Consider making the "crash after PSP charge but
before DB write" hazard visible in the caption or as a failure drill here, since
it is the motivating failure for the whole case.

### Step 2: Idempotency Keys

Strong step. It explains client-supplied keys, atomic claims, concurrent retry
races, in-progress recovery, and replaying stored responses. Improve the data
model with request fingerprint, expiry, and recovery timestamps so the concept
is grounded in schema.

### Step 3: Double-Entry Ledger

This is the best step in the dataset. The default option, mutable-balance
counter-option, traps, and balanced-entry invariant are all concrete. Add a
`ledger_transactions` entity so the invariant has an obvious enforcement and
dedupe point.

### Step 4: Asynchronous Capture & State Machine

The outbox lesson is correct and well motivated. The state machine needs a bit
more surface area: `authorized -> capturing -> captured/failed` is enough for a
diagram, but the dataset should mention `capture_unknown` or similar for PSP
timeouts and in-doubt recovery. The flow should show the PSP idempotency key.

### Step 5: Webhooks

Good coverage of signature verification, dedupe, fast ack, duplicates, and
out-of-order delivery. The main issue is that all events visually flow to the
capture worker. Consider renaming the consumer to `Payment Event Worker` or
adding labels that distinguish capture result, settlement, dispute, and late
failure handlers.

### Step 6: Reconciliation

Conceptually strong but operationally thin. Add persisted file/import metadata,
break state, owner, aging, and resolution path. This can stay as a deep dive if
the main step should remain compact.

### Step 7: Payouts & Balance Read Model

The read model explanation is good, and the traps are exactly right. The payout
sequence needs to be reordered so a strong ledger reservation/debit happens
before the bank transfer. Otherwise the visual contradicts the warning that the
read model is not authority.

### Step 8: Scaling the Ledger

Sharding by account with per-shard clearing accounts is a credible default. The
cross-shard saga caveat is honest. Add a short note on hot merchants/accounts,
resharding, shard-local sequence numbers, and how reconciliation sees all
shards.

### Step 8a: Where Money Demands Strong Consistency

This is a valuable sub-step. It should cross-reference the payout flow once that
flow is fixed: payout guard is the canonical example of a strong money path,
while balance display is the canonical eventual read.

## Final Design Review

The final design integrates the main components and is coherent at the diagram
level. It includes idempotent APIs, DB/outbox/queue, capture worker, PSP,
webhook receiver, sharded ledgers, reconciliation, balance projection, payouts,
and bank rails.

What is still missing is the state-management layer behind some final-design
claims:

- Final design says idempotent payouts, but there is no payout state machine or
  bank callback/reconciliation path.
- It says daily reconciliation, but there is no break workflow.
- It says signature-verified webhooks, but there is no persisted webhook inbox
  in the data model.
- It says sharded ledger, but the data model does not show shard key or
  transaction header metadata.

The final design should not become crowded. Add the missing details in the data
model and step deep dives, then keep the final diagram as the clean overview.

## Concept Introduction and Learning Flow

The learning flow is strong. Each step solves a problem exposed by the previous
step:

- Synchronous charge exposes unsafe retries and external uncertainty.
- Idempotency handles client/network retries.
- Ledger handles auditability and mutable-balance corruption.
- Outbox and async capture handle long-running PSP workflows.
- Webhooks handle external asynchronous truth.
- Reconciliation handles drift between internal and external records.
- Read model and payouts handle scalable reads and merchant withdrawal.
- Sharding and consistency choices handle scale and correctness budgets.

The only conceptual gap is lifecycle breadth. Refunds, disputes, payouts, and
reconciliation breaks are introduced early as requirements, but the core steps
mostly optimize charge/capture. Add one or two small flows so the learner sees
how the same primitives apply after the happy path.

## Step-to-Final-Design Coherence

The step-to-final progression is mostly coherent:

- `Idem` introduced in Step 2 appears in the final design.
- `Ledger` introduced in Step 3 evolves into `LedgerA` and `LedgerB`.
- `Outbox`, `Queue`, and `Capture` introduced in Step 4 appear in final design.
- `WebhookSvc` introduced in Step 5 appears in final design.
- `Recon` and `Statement` introduced in Step 6 appear in final design.
- `Balance`, `Payout`, and `Bank` introduced in Step 7 appear in final design.
- `Router`, `LedgerA`, and `LedgerB` introduced in Step 8 appear in final
  design.

The weakest link is payout consistency: Step 7 says the read model is not the
source of truth, Step 8a says payout guard needs strong consistency, but the
flow and final diagram do not make the strong ledger guard visible.

## Realism Compared With Production Systems

The dataset has good instincts about external PSPs, reconciliation, and
idempotency. The next layer of realism should focus on operational controls:

- Treat every PSP call as ambiguous until correlated by idempotency key,
  reference lookup, webhook, or settlement file.
- Keep signed raw PSP events for audit and replay.
- Represent payouts as their own state machine, not just a service call.
- Treat reconciliation breaks as work items with owners and SLAs.
- Include PCI/tokenization boundaries so the system does not appear to store raw
  payment source data.
- Include fraud/risk and payout holds, at least as explicit out-of-scope or
  extension points.
- Add metrics and runbook triggers for stuck money movement.

## Dataset and Renderer-Facing Observations

- `python3 -c "import json; json.load(...)"` succeeds for
  `data/book/payment-system/interview.json`.
- Top-level step views, final-design views, `satisfies[*].steps[*]`, pattern
  step links, and parent references resolve.
- The payout option "Periodic balance snapshots + delta" references
  `Snapshot`, but `Snapshot` is not in `highLevelArchitecture.nodes`. Add a
  canonical node with a suitable type, likely `database` or `index`, so the
  option diagram has stable label/type metadata.
- `satisfies.nonFunctional` has five rows while `requirements.nonFunctional`
  has six bullets. The idempotent-API requirement is covered implicitly by the
  exactly-once row, but traceability would be clearer with a dedicated row or
  wording that explicitly includes idempotent APIs.
- The high-level architecture includes short alias nodes such as `C`, `X`, `K`,
  and `L` in addition to fuller nodes such as `Client`, `PSP`, `Bank`, and
  `Ledger`. This does not break current rendering, but it can make the canonical
  architecture catalog harder to scan. Prefer sequence-local aliases unless the
  nodes are needed in architecture views.
- No `technologyChoices` section is present. That is valid, but it is a missed
  book-feature opportunity for a flagship payment case.
- Do not rebuild `docs/` for this review-only file; `REVIEW.md` is repo-only.

## Recommended Edits, Prioritized

### P1: Make payout safety explicit

Update Step 7 and final-design wording so payout reserves/debits available funds
in the authoritative ledger before calling bank rails. Add payout state and
stable bank reference/idempotency.

### P1: Add state for external event and lifecycle correctness

Add `ledger_transactions`, `payment_events` or `payment_state_transitions`,
`psp_events`, and minimal `refunds`/`payouts` entities. These carry the
invariants already taught in prose.

### P1: Add an in-doubt PSP recovery flow

Show timeout/unknown PSP response recovery using PSP idempotency key,
correlation id, webhook, PSP lookup, and reconciliation.

### P2: Operationalize reconciliation

Add settlement import metadata and `reconciliation_breaks` with lifecycle,
owner, state, amount, aging, resolution, and audit trail.

### P2: Add security, compliance, and observability coverage

Add a compact operations/security table: PCI/tokenization, fraud/risk, PSP
credential handling, audit logs, queue/outbox lag, stuck idempotency keys,
ledger imbalance, projection lag, payout failure rate, and reconciliation
break aging.

### P2: Add `technologyChoices`

Cover ledger database options, idempotency store, outbox/queue implementation,
reconciliation batch/workflow stack, balance projection, secrets/KMS, and
observability.

### P3: Fix renderer metadata and traceability polish

Add the missing `Snapshot` node metadata, tighten `satisfies.nonFunctional`,
and consider removing architecture-global alias nodes that are only useful for
sequence diagrams.

## What Not To Change

- Keep the correctness-first framing.
- Keep the step order. It builds naturally from simple charge to ledger,
  asynchrony, external truth, reconciliation, reads/payouts, and scale.
- Keep double-entry ledger as the core source of truth.
- Keep transactional outbox and webhook dedupe as explicit steps.
- Keep Step 8a as a sub-step under ledger scaling; it is a useful senior-level
  discussion without bloating the main path.
- Keep reconciliation as a first-class step, not a footnote.

## Bottom Line

This is already a strong payment-system interview and has the right conceptual
center of gravity. To make it flagship-quality, the dataset should turn the
remaining prose guarantees into explicit state: refund/dispute lifecycle, PSP
in-doubt recovery, payout reservation, reconciliation breaks, and operational
controls. The architecture does not need a rewrite; it needs the data and flows
that make its correctness claims auditable.
