# Review: Stripe-like Payment Gateway - System Design

Reviewed file: `data/book/payment-gateway/interview.json`
Review date: 2026-06-08

## Executive Summary

The recent updates materially improved this dataset. The review is no longer
"missing refunds, payouts, capacity, and Step 7 depth"; those areas now have
concrete API endpoints, capacity assumptions, money-model tables, refund/payout
flows, PSP ambiguity handling, and an option-driven scaling step. The interview
is now a strong payment-gateway walkthrough that teaches the right correctness
themes: PCI containment, durable idempotency, persisted charge orchestration,
ambiguous PSP reconciliation, reliable webhooks, double-entry accounting, and
safe failover.

The remaining work is mostly about tightening precision. Some capacity numbers
do not quite line up with the stated write amplification, Step 7 combines
storage scaling with PSP failover instead of comparing failover strategies as
options, and the richer ledger/payout model still needs explicit invariants,
reconciliation line items, and operational runbooks.

| Axis | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.4 / 5 | The core gateway is credible and now covers refunds, payouts, reconciliation, and failover; ledger invariants and async payment extensions need more precision. |
| Production realism | 4.2 / 5 | Strong on PCI, idempotency, PSP ambiguity, outbox webhooks, and money flow; thinner on merchant operations, security operations, admin tooling, and incident runbooks. |
| Pedagogical flow | 4.4 / 5 | The progression is clear and the recent flows help a lot; Step 6 and Step 7 are dense enough that they need one more teaching pass. |
| Dataset/rendering fit | 4.7 / 5 | JSON is valid, references resolve, and the old view endpoint omissions are fixed; only minor API sequence and documentation polish remain. |
| Overall | 4.4 / 5 | Interview-ready, with a short list of high-value refinements before calling it production-grade. |

## What Works Well

- Capacity is now quantified: average/peak charge volume, sync latency,
  webhook fanout, ledger write amplification, payout cadence, and retention are
  all present.
- The API surface now supports the operational story: charge, refund, status
  reads, event listing, replay, webhook endpoint setup, and tokenization.
- The data model now backs the architecture claims with `payment_attempts`,
  `idempotency_keys`, `refunds`, ledger accounts/entries, payouts,
  reconciliation runs, merchants, webhook endpoints, events, and delivery
  attempts.
- PSP ambiguity is handled with explicit sent/unknown states, PSP request IDs,
  PSP idempotency keys, reconciliation state, and a failover flow that avoids
  double-authorizing an ambiguous charge.
- Step 6 is much stronger than before: it compares ledger designs and includes
  refund and payout sequence flows.
- Step 7 is no longer just prose. It has options, concepts, traps, a failure
  flow, bottlenecks, and recap material.
- Renderer-facing integrity is healthy: step-level view nodes and links resolve,
  link endpoints are present in their views, option views resolve, highlights
  resolve, sequence participants are declared, and `satisfies[*].steps[*]`
  references point to real steps.

## Highest-Impact Issues

### 1. Capacity arithmetic needs one consistency pass

The capacity section now has useful numbers, but the derived work units are not
fully consistent. `~2k charges/sec avg` implies about 173M charges/day, while
the text says `~150M charges/day`. That is close enough for an interview, but
the ledger line says `~150-600M entries/day` while the note says one charge can
create `2-6 ledger entries` plus additional rows. At 150M charges/day, that
would be 300M-900M ledger entries/day before counting webhook, delivery
attempt, attempt, idempotency, and reconciliation rows.

Concrete fix:

- Pick one baseline, e.g. 150M/day or 173M/day, and derive all downstream
  counts from it.
- Separate "ledger entries/day" from "total persisted rows/day"; the current
  note mixes them.
- Add peak write math: at 10k charges/sec and 5-10 persisted rows per charge,
  the store must absorb roughly 50k-100k writes/sec before retries.
- State whether webhook retry multiplier applies to events, delivery attempts,
  or outbound HTTP calls.

### 2. Step 7 still teaches storage scaling more than PSP resilience

Step 7 is titled "Resilience, PSP Failures, and Scale", but its three options
are all charge-store topology choices: merchant-sharded primary, single
regional primary, and active/passive region. PSP failover is covered in the
concepts, traps, and sequence flow, but candidates do not get the same
option-comparison treatment for acquirer routing that they get for storage.

Concrete fix:

- Either split Step 7 into two steps, "Scale the payment store" and "PSP
  resilience / multi-acquirer routing", or add a second option set if the
  renderer supports it.
- Compare PSP strategies directly: single acquirer, active/passive fallback,
  rule-based multi-acquirer routing, and network-token/PSP-token constraints.
- Name the safe routing contract in the options themselves: fail over only
  before an authorize is sent, after confirmed failure, or with a provider or
  network idempotency guarantee.
- Keep the current flow; it is good. Promote its trade-offs into the decision
  options so the step title and selected decision line up.

### 3. Ledger and reconciliation are credible but still not invariant-heavy

The money model is now much better, but a ledger in a payment gateway is only
safe if the invariants are explicit. The current schema names the right tables,
but it does not yet show enough constraints around balanced posting, immutable
entries, idempotent transaction groups, settlement-line matching, available vs
pending balance derivation, and payout eligibility.

Concrete fix:

- Add ledger invariants to Step 6 or the data model: each transaction group must
  balance to zero per currency, entries are append-only, reversals are new
  entries, and payout reads only settled available balance minus reserve.
- Add fields such as `currency` on `ledger_entries`, `created_at`,
  `effective_at`, `posting_state`, `idempotency_key` or unique `ref_type/ref_id`
  constraints, and possibly `balance_version` for materialized balances.
- Add `reconciliation_items` or `settlement_report_lines`, not just
  `reconciliation_runs`, so mismatches can be traced to individual PSP rows.
- Add one trap to Step 6 for mutable balances or unbalanced ledger posting; that
  step currently has no traps despite being one of the riskiest parts of the
  design.

### 4. Merchant and security operations need more concrete treatment

The API and data model now mention merchant API keys, webhook signing secrets,
endpoint configuration, per-merchant rate limits, and vault controls. That is
the right direction, but production operation still feels implicit. A payment
gateway needs lifecycle and incident workflows: rotate keys, rotate webhook
secrets, disable compromised merchants, replay events safely, redact logs,
audit detokenization, and investigate stuck or unknown charges.

Concrete fix:

- Add merchant operations fields or endpoints for API-key rotation, webhook
  endpoint update/delete, webhook secret rotation, endpoint disablement, and
  per-merchant delivery throttling.
- Add operational security details: key version on encrypted PANs, vault access
  audit log, detokenization reason codes, support-tool redaction, log/trace PAN
  scrubbers, and least-privilege service identities.
- Add admin/runbook notes for `authorize_unknown`, reconciliation mismatches,
  payout returns, webhook DLQ replay, and ledger imbalance alerts.
- Tie observability to these operations: unknown payment count, stale unknown
  age, reconciliation mismatch count, ledger imbalance, payout failure count,
  webhook backlog age, and per-merchant throttle/drop rates.

### 5. Async payment extensions are only scoped in follow-ups

The follow-ups correctly call out 3DS/SCA, disputes/chargebacks, multi-currency,
FX, KYC, and bank-account verification as extensions. That is acceptable for a
focused interview, but the main walkthrough should explicitly say these are out
of the core path so readers do not mistake their absence for an oversight.

Concrete fix:

- Add a short "Scoped out" note near requirements or follow-ups.
- Mention where 3DS/SCA would extend the state machine, e.g.
  `requires_action`, `authentication_pending`, `authentication_failed`.
- Mention where disputes and chargebacks would touch the ledger: reserves,
  evidence workflow, dispute holds, chargeback debits, and reversals.
- Mention that payouts require merchant onboarding/KYC and verified payout
  destinations before funds move.

## System Design Soundness

The requirements are appropriate and now word the "exactly-once" claim
carefully: exactly-once external effect through idempotency, durable state, and
reconciliation, not generic exactly-once distributed execution. That distinction
is important and should stay.

The API surface now supports the design much better than before. It covers the
core charge/refund/status/event/replay/tokenization workflows. Remaining API
polish is mostly consistency: several request examples omit `Authorization`,
the tokenization endpoint should clearly be a vault/hosted-fields endpoint using
a publishable client key rather than a merchant secret, and replay/update/delete
operations should describe idempotency and authorization scope.

The data model has caught up with the final design. It now includes the right
families of tables for attempts, idempotency, refunds, ledger, payouts,
webhooks, merchants, and reconciliation. The next improvement is to encode
invariants rather than adding more nouns: balanced ledger postings, unique
external references, immutable entries, reconciliation item records, timestamped
attempt histories, and payout eligibility rules.

The high-level architecture is coherent. The PCI vault, gateway API, charge
orchestrator, charge/payment store, fraud service, acquirer, ledger, webhook
delivery, queue, and payout worker are the right components for this case. The
final design accurately integrates the chosen path.

## Step-by-Step Pedagogical Review

### Step 1: Naive baseline

This remains a good opener. It exposes PCI blast radius and retry double-charge
risk before introducing the gateway mechanisms. The previous review's diagram
endpoint problem is fixed: `ChargeSvc` is now present when `charge-psp` is
shown.

One optional improvement: make the baseline explicitly "intentionally wrong" in
the prose so candidates do not treat direct bank charging as a serious option.

### Step 2: The PCI Boundary: Tokenize Card Data

The options are realistic: hosted fields, server-side tokenization, and
PSP/network tokenization. The default is correct for shrinking PCI scope. The
added vault-security concept is useful and should stay.

The next improvement is to connect PCI controls to operations. Add key versions,
audit logs, detokenization reason codes, support-tool redaction, and log/trace
scrubbing either as concept details or a trap.

### Step 3: Idempotent Charges

This is strong. It includes request fingerprinting, durable idempotency,
retention, conflict semantics, and traps for body mismatch and cache-only
deduplication. The options teach the trade-off between a dedicated idempotency
record, a unique charge constraint, and distributed locks.

Minor polish: say what happens for an in-progress duplicate request. Returning
`409/in_progress`, blocking until the first request completes, or replaying the
last known response are all valid choices, but the contract should be explicit.

### Step 4: Charge Orchestration: Risk -> Network

This is still the strongest conceptual step. It introduces the persisted state
machine, risk gate, detokenization, PSP call, and ambiguous timeout handling in
the right sequence. The `authorize_unknown` and `capture_unknown` states and
PSP IDs are now reflected in the model.

The sequence flow is useful but compressed. It would be stronger if the flow
showed storing `psp_request_id` before the network call, not only persisting the
initial `created` state and final resolution.

### Step 5: Reliable Webhooks

The outbox/default option is correct, and the event/delivery-attempt split in
the data model fixes the earlier gap. The traps are good: do not promise
exactly-once delivery, and do not dual-write DB then HTTP inline.

Add one operational rule: replay should create a new delivery attempt for the
same event ID, not a new business event. That reinforces merchant deduplication.

### Step 6: Ledger and Payouts

This step improved the most. It now compares double-entry ledger, mutable
balance, and event-sourced ledger options, and it has concrete refund and payout
flows. The available-vs-pending concept is important and well placed.

The next improvement is depth. Add traps and invariants for unbalanced entries,
mutable balance edits, payout before settlement, and stale materialized balance
reads. The data model should also show reconciliation at the individual
settlement-line level, not only as aggregate run counts.

### Step 7: Resilience, PSP Failures, and Scale

This step is now useful, but it is doing two jobs. The options teach charge
store topology; the flow teaches PSP failover. Both are valuable, but the
decision prompt asks about the primary acquirer going down, while the selected
option is merchant-sharded storage. That mismatch is the main pedagogical issue
left in the walkthrough.

Split the storage and PSP-routing decisions, or add explicit PSP-routing
options. Keep the current traps; they are exactly the traps a strong candidate
should name.

## Final Design Review

The final design is coherent and no longer overclaims relative to the dataset.
The components in the final diagram are introduced in prior steps, and the
caption accurately describes tokenization, idempotent orchestration, fraud,
acquirer authorize/capture, ledger posting, payouts, and queued webhooks.

The final design would be stronger if it named the operational plane somewhere:
merchant configuration, admin/reconciliation tools, alerting, audit logs, and
runbooks for stuck/unknown money states. These do not need to clutter the main
diagram, but they should exist in prose, concepts, or follow-ups.

## Concept Introduction and Learning Flow

The learning order is good: PCI first, idempotency second, orchestration third,
webhooks after state changes, ledger/payouts after money movement, and
resilience/scale last. Concepts are introduced close to where they are used.

The recent additions to patterns and concepts make the wrap-up much better:
transactional outbox, PSP reconciliation, payout state machine, merchant
webhook dedup, and circuit breaker/failover are now represented. The remaining
concept gap is not naming more concepts; it is giving Step 6 and Step 7 enough
invariants and alternatives to make those concepts interview-operational.

## Step-to-Final-Design Coherence

Every final-design component now has a credible step-level introduction. The
main transition weakness is Step 7: the final design claims resilience to PSP
failure, and the dataset has a good failover flow, but the option tabs primarily
decide storage topology. Aligning the decision prompt, default option, and flow
would make the final step feel earned.

The `satisfies` section is accurate and references real steps. It correctly
maps no-double-charge to idempotency and orchestration, reliable webhooks to the
outbox step, auditable money flow to ledger, and PSP failure resilience to the
scale step.

## Realism Compared With Production Systems

The dataset is now realistic on the core hazards of a payment gateway:
tokenization, idempotent API contracts, external provider ambiguity, state
machines, settlement/reconciliation, at-least-once webhook delivery, and
ledger-backed payouts.

The consciously scoped-out areas are also realistic boundaries for a 45-minute
interview: 3DS/SCA, chargebacks/disputes, KYC, multi-currency, FX, and bank
account verification. The dataset should keep those as follow-ups, but should
make the scope boundary explicit near the requirements.

The most production-like additions would be operational rather than architectural:
merchant secret rotation, webhook endpoint lifecycle, DLQs and replay controls,
admin tools for unknown payments, reconciliation queues, incident runbooks,
PCI audit logs, PAN redaction, and ledger imbalance alerting.

## Dataset and Renderer-Facing Observations

- JSON parse validation passes.
- Top-level schema shape is consistent with the book datasets.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Step-level `view.nodes` references resolve to high-level nodes unless they are
  deliberate inline option-local nodes.
- Step-level and option-level `view.links` references resolve.
- Displayed high-level links have both endpoints present in their step/option
  views; the old `naive` and `scale` omissions are fixed.
- Step-level highlights resolve to visible nodes.
- Sequence participants are declared, including the `PSPA` and `PSPB` aliases
  used in the PSP failover flow.
- `requirementsDiagram` and `capacityDiagram` remain simple raw Mermaid
  diagrams, which is acceptable for overview sketches.
- Minor polish: the `POST /v1/charges` API sequence returns from `ChargeSvc` to
  `Merchant` directly. For strict sequence clarity, return through `API`, or
  explain that the diagram is collapsing the API response path.

## Recommended Edits, Prioritized

### P1: Align capacity math

Recalculate charges/day, ledger entries/day, total persisted rows/day, peak
writes/sec, webhook event count, delivery-attempt count, and retry multiplier
from the same baseline assumptions.

### P1: Split or rebalance Step 7

Make PSP resilience a first-class option comparison, or split the current Step
7 into storage scaling and acquirer failover decisions.

### P1: Add ledger/reconciliation invariants

Add balanced-by-currency posting rules, immutable reversal rules, idempotent
transaction-group constraints, settlement-line matching, and payout eligibility
rules.

### P2: Add merchant/security operations

Cover API-key rotation, webhook secret rotation, endpoint update/delete/disable,
per-merchant throttling, vault audit logs, key versions, support-tool redaction,
and incident runbooks.

### P2: Add Step 6 traps

Add traps for mutable balance edits, unbalanced ledger entries, paying pending
funds, and relying on stale materialized balances for payouts.

### P3: Clarify scoped-out payment features

Add a concise requirements-level or follow-up note for 3DS/SCA, disputes,
chargebacks, KYC, multi-currency, FX, and verified payout destinations.

### P3: Polish API examples and sequences

Make auth headers consistent, clarify tokenization uses the client/vault trust
boundary, and route the charge sequence response through the API for precision.

## What Not To Change

- Keep the naive baseline; it is pedagogically useful.
- Keep client SDK / hosted fields as the default PCI choice.
- Keep durable idempotency as a database-backed correctness mechanism.
- Keep the centralized persisted charge orchestrator as the default.
- Keep PSP ambiguity handling strict: never blindly retry an unknown authorize.
- Keep outbox-backed at-least-once webhooks with merchant deduplication.
- Keep the double-entry ledger as the default money model.
- Keep chargebacks, KYC, multi-currency, and 3DS/SCA as follow-ups unless the
  interview is intentionally expanded beyond the core gateway.

## Bottom Line

This dataset has moved from a good outline to a strong, interview-ready payment
gateway case. The next review pass should focus on precision rather than breadth:
consistent capacity math, a cleaner PSP-failover decision step, explicit ledger
invariants, and concrete merchant/security operations.
