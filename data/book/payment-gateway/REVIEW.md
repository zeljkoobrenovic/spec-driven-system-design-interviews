# Review: Stripe-like Payment Gateway - System Design

Reviewed file: `data/book/payment-gateway/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a strong, compact payment-gateway walkthrough. It teaches the right
core themes for a Stripe-like gateway: shrinking PCI scope with tokenization,
enforcing idempotency at the charge boundary, driving payment state through a
persisted orchestrator, handling ambiguous PSP responses through reconciliation,
delivering at-least-once webhooks, and closing the money loop with a ledger and
payouts.

| Axis | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.0 / 5 | The core charge path is credible; refunds, ledger schema, payout state, and PSP failover need more concrete treatment. |
| Production realism | 3.5 / 5 | Good coverage of PCI, idempotency, webhooks, and reconciliation; thin on merchant configuration, security operations, chargebacks, observability, and runbooks. |
| Pedagogical flow | 4.0 / 5 | The progression from naive baseline to final design is clear; the last scale/resilience step is mostly prose and should become a decision step. |
| Dataset/rendering fit | 4.0 / 5 | JSON is valid and references mostly resolve; two step views include links whose endpoints are not in the view. |
| Overall | 4.0 / 5 | Usable and interview-ready, with several high-leverage edits that would make it production-grade. |

## What Works Well

- The first step is effective: it exposes both PCI blast radius and retry
  double-charge risk before introducing solutions.
- Tokenization is framed correctly as a boundary decision, not just a storage
  trick. The client SDK / hosted fields option is the right default.
- Idempotency is taught in the right place and tied to durable persistence, not
  a best-effort cache or lock.
- The orchestrator step correctly calls out persisted charge states and
  ambiguous PSP responses, which are central to payment correctness.
- Webhook delivery uses the transactional outbox pattern and explicitly accepts
  at-least-once semantics with merchant-side deduplication.
- The final design integrates every major component introduced in the steps and
  maps cleanly to the `satisfies` section.

## Highest-Impact Issues

### 1. Refunds and payouts are promised but under-modeled

The functional requirements include refunds and merchant payouts, and the API
has `POST /v1/refunds`, but the data model only has `charges`, `card_tokens`,
and `webhook_events`. There is no `refunds` table, no ledger entry/account
model, no payout object, no settlement/reconciliation record, and no delivery
attempt table. This makes the final ledger/payout claim feel conceptually right
but underspecified.

Concrete fix:

- Add data-model entries for `refunds`, `ledger_accounts`, `ledger_entries`,
  `payouts`, `settlement_reports` or `reconciliation_runs`, and optionally
  `idempotency_keys`.
- Make refund idempotency explicit. `POST /v1/refunds` should accept an
  idempotency key and should define partial-refund limits against the captured
  amount.
- Add a sequence flow for refund -> PSP reversal/refund -> ledger reversal ->
  webhook event.
- Add a payout flow showing balance cutoff, reserve/available balance,
  payout creation, PSP transfer, reconciliation, and final webhook.

### 2. Capacity is qualitative, so scaling claims are hard to evaluate

The capacity section says "high, spiky", "hundreds of ms", and "daily", but it
does not translate those into work units. Step 7 then claims sharding, queues,
and horizontal scaling without numbers that motivate them.

Concrete fix:

- Add approximate charge QPS, peak multiplier, webhook fanout, retry multiplier,
  daily ledger entries, retention horizon, and expected storage growth.
- Separate synchronous charge latency from asynchronous settlement, webhook
  retries, reconciliation jobs, and payout jobs.
- Add a short capacity note that derives ledger write amplification: a single
  successful charge may create a charge row, idempotency row, multiple ledger
  entries, one or more webhook events, delivery attempts, and reconciliation
  rows.

### 3. PSP ambiguity and failover need a stricter contract

The dataset correctly says "never blindly retry" a timed-out authorize, but the
model does not define the IDs and states required to do that safely. Multi-
acquirer failover is also mentioned in the final design and `satisfies`, but
there is no routing model or rule that prevents accidentally sending the same
authorization to another acquirer while the first request is ambiguous.

Concrete fix:

- Add fields such as `payment_attempt_id`, `psp_request_id`,
  `psp_idempotency_key`, `acquirer_id`, `network_trace_id`,
  `last_psp_status`, and `reconciliation_state`.
- Make the state machine distinguish `authorize_sent`, `authorize_unknown`,
  `authorized`, `capture_sent`, `capture_unknown`, `captured`, `voided`,
  `refunded`, and `failed`.
- In Step 7, add options for single acquirer, active/passive failover, and
  rule-based multi-acquirer routing. Call out that failover is safe only before
  an authorization is sent, after a confirmed failure, or with a provider/network
  idempotency contract.

### 4. Merchant integration surface is incomplete

The API section has create charge, refund, and tokenization, but a production
gateway also needs merchant authentication, endpoint configuration, replay, and
status inspection. Without those, reliable webhooks and auditability are harder
to operate.

Concrete fix:

- Add `GET /v1/charges/{id}`, `GET /v1/refunds/{id}`, `GET /v1/events`,
  `POST /v1/events/{id}/replay`, and webhook endpoint configuration APIs.
- Include merchant API keys, webhook signing secrets, endpoint URLs, retry
  policy, and per-merchant rate limits in the data model.
- Mention that merchant-side dedup is by event id, while gateway-side idempotency
  is by merchant plus idempotency key plus request fingerprint.

### 5. PCI and security are scoped too narrowly

Tokenization is the right architectural move, but the vault is described mostly
as a service with encrypted PAN storage. A gateway interview should name the
controls that keep the PCI boundary credible.

Concrete fix:

- Add vault details: KMS/HSM-backed encryption, key rotation, token lifecycle,
  least-privilege detokenization, audit logs, network segmentation, and
  restricted service-to-vault access.
- Add operational security for webhook signatures, API-key rotation, merchant
  secret storage, and log redaction.
- Consider one trap for "tokenizing but still logging PANs or storing them in
  analytics/search/error traces."

### 6. The resilience/scale step is not yet a real decision step

Step 7 has no options, flows, concepts, traps, or deep dives, even though it
carries important claims about sharding, circuit breakers, queues, and
multi-acquirer failover. It reads like a wrap-up rather than a step that teaches
trade-offs.

Concrete fix:

- Add options for scaling the charge store: single regional primary,
  merchant-sharded store, and multi-region active/passive.
- Add options for PSP resilience: no failover, circuit breaker with
  reconciliation, and multi-acquirer routing.
- Add traps for "retrying PSP calls through a different acquirer while the first
  attempt is ambiguous" and "scaling the ledger with eventual consistency on
  balances that determine payouts."
- Add observability concepts: charge success rate, PSP timeout rate, unknown
  payment count, webhook backlog age, reconciliation mismatch count, payout
  failure count, and ledger imbalance alerts.

## System Design Soundness

The requirements are appropriate for the scope and correctly prioritize
correctness over availability. The phrase "exactly-once" should be handled with
care: the dataset should present this as exactly-once external effect through
idempotency, durable state, and reconciliation, not as a generic distributed
systems guarantee.

The API is intentionally small and easy to teach, but it is missing status,
replay, and configuration endpoints that support the later architecture. The
charge request also lacks fields that would matter in production: merchant id
or authenticated merchant context, payment method token, capture mode,
description/metadata, request fingerprint, and possibly customer id.

The data model is the weakest part relative to the claims. `charges` carries
state and idempotency, but the promised ledger, payout, refund, outbox,
delivery-attempt, and reconciliation mechanisms are not represented as tables.
This makes the final design less auditable than the text says it is.

The high-level architecture has the right major services. The vault, charge
store, orchestrator, fraud service, PSP, ledger, webhook delivery, queue, and
payout worker are enough for a strong interview answer. The missing piece is the
operational layer: admin/reconciliation tools, merchant configuration, alerting,
and runbooks for unknown charges, stuck payouts, and webhook backlogs.

## Step-by-Step Pedagogical Review

### Step 1: Naive baseline

This is a good opener because it motivates both PCI containment and idempotent
charges. The diagram view should be fixed: it includes `charge-psp`, whose
source endpoint is `ChargeSvc`, but `ChargeSvc` is not in this step's
`view.nodes`. Either add `ChargeSvc` to the view or replace the link with a
local `API -> PSP` link.

### Step 2: PCI boundary

The options are useful and realistic: hosted fields, server-side tokenization,
and PSP/network tokenization. The default is correct. This step would be stronger
with one added operational caveat: tokenization is not enough if logs,
analytics, traces, screenshots, or support tools can still capture PAN data.

### Step 3: Idempotent charges

The chosen design is sound. The distributed lock option is a good contrast
because it exposes why locks are unsafe around slow PSP calls. Add request-body
fingerprinting and an idempotency retention policy so repeat keys with different
payloads become a defined conflict rather than ambiguous behavior.

### Step 4: Charge orchestration

This is the strongest step. It introduces the state machine, risk gate, vault
detokenization, and PSP ambiguity in the right order. To make it production
complete, add explicit states for sent/unknown external calls and store PSP
request IDs before the network call is made.

### Step 5: Reliable webhooks

The outbox/default option is correct and the at-least-once framing is good. The
model should separate event records from delivery attempts and should include
merchant endpoint configuration, signing secret version, replay, and a maximum
backoff/DLQ policy.

### Step 6: Ledger and payouts

The step teaches the right accounting principle, but it is too compressed for a
money system. A double-entry ledger needs accounts, immutable entries,
transaction groups, currency, available/pending balances, fees, reserves,
payouts, and reconciliation. This step deserves either a deep dive or a flow.

### Step 7: Resilience, PSP failures, and scale

This is high-value material but currently underdeveloped. It should become an
option-driven step with concrete trade-offs, not just a prose summary. The view
also includes `webhook-q`, whose source endpoint is `WebhookSvc`, but
`WebhookSvc` is not in `view.nodes`.

## Final Design Review

The final design is coherent and accurately summarizes the selected path. It
includes all major nodes and links, and the caption explains the whole flow in
one pass. The main gap is that the final text claims "double-entry ledger",
"reconciled against PSP settlement", "scheduled payouts", and "multi-acquirer
failover", while the dataset does not yet provide enough schema or step detail
to substantiate those claims.

## Concept Introduction and Learning Flow

Concepts are introduced just in time: PCI tokenization before idempotency,
idempotency before orchestration, orchestration before webhooks, and ledger
after charges/refunds are in scope. That order is good.

The concept set is sparse for the later half of the interview. Add concepts for
transactional outbox, PSP reconciliation, double-entry ledger, payout state,
merchant webhook deduplication, and circuit breakers. The existing pattern
chips are useful and should be preserved.

## Step-to-Final-Design Coherence

Every final-design component appears in a prior step, which is a good sign. The
weak transitions are from Step 6 to payout correctness and from Step 7 to
multi-acquirer scale. Those mechanisms appear in the final design but are not
earned through the same level of option comparison as PCI, idempotency, and
webhooks.

## Realism Compared With Production Systems

The dataset is realistic on the core payment hazards: PCI scope, merchant
retries, slow external PSP calls, ambiguous responses, outbox-based webhooks,
and ledger-backed money movement.

The missing production topics are not all required for the main case, but at
least some should be named or explicitly scoped out:

- 3DS/SCA or asynchronous customer authentication states.
- Disputes, chargebacks, evidence submission, and reserves.
- KYC/merchant onboarding, merchant risk, and bank account verification for
  payouts.
- Multi-currency and FX.
- Provider rate limits, brownouts, partial outages, and reconciliation SLAs.
- Admin tooling for manual review, stuck charges, payout failures, and webhook
  replay.
- Observability, alerting, audit logs, and data retention.

## Dataset and Renderer-Facing Observations

- JSON parse validation passes.
- Top-level schema shape is consistent with the book datasets.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Step-level `view.links` references resolve to known high-level links.
- Option-level `view.nodes`, `view.links`, and highlights resolve.
- Sequence flow participant references resolve.
- Two step views include links whose endpoints are omitted from the same view:
  `naive` uses `charge-psp` but omits `ChargeSvc`; `scale` uses `webhook-q` but
  omits `WebhookSvc`. These can create implicit, unlabeled Mermaid nodes or
  confusing diagrams.
- `requirementsDiagram` and `capacityDiagram` are simple raw Mermaid diagrams
  and are acceptable for overview sketches.

## Recommended Edits, Prioritized

### P1: Make the money model match the claims

Add refund, ledger, payout, outbox/delivery-attempt, idempotency, and
reconciliation data-model entries. Add at least one refund or payout sequence
flow.

### P1: Strengthen PSP ambiguity and failover

Add explicit attempt IDs, PSP idempotency keys, unknown states, reconciliation
states, and safe/unsafe failover rules.

### P1: Fix the two view endpoint omissions

Fix `naive.view` and `scale.view` so every link endpoint appears in the view's
node list, or replace those links with local inline links that match the shown
nodes.

### P2: Quantify capacity

Replace qualitative capacity bullets with approximate QPS, retry/fanout,
storage, queue backlog, and latency assumptions.

### P2: Turn Step 7 into an option-driven step

Add options, traps, and at least one sequence/deep dive for PSP failure,
multi-acquirer routing, or store/ledger scaling.

### P2: Expand merchant operations APIs

Add status, event listing/replay, webhook endpoint configuration, and webhook
secret rotation APIs.

### P3: Add security and compliance details around the vault

Mention HSM/KMS, key rotation, audit logs, log redaction, network segmentation,
least-privilege detokenization, and token lifecycle management.

### P3: Add follow-up scope boundaries

Either add or explicitly scope out 3DS/SCA, disputes/chargebacks, merchant KYC,
reserves, multi-currency, and FX.

## What Not To Change

- Keep the naive baseline. It is pedagogically useful and sets up the rest of
  the design.
- Keep client SDK / hosted fields as the default PCI decision.
- Keep durable idempotency as a database-backed correctness mechanism, not a
  cache-only mechanism.
- Keep the centralized persisted orchestrator as the default for the charge
  lifecycle; it is easier to reason about for money movement than choreography.
- Keep at-least-once webhooks with merchant deduplication. Do not imply
  exactly-once webhook delivery.

## Bottom Line

This dataset is already a strong interview walkthrough for the core charge
path. The next improvement should be to make the claimed production mechanisms
concrete: data models for ledger/refunds/payouts/reconciliation, explicit PSP
attempt-state handling, quantified capacity, and a real resilience/scale
decision step.
