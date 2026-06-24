# Review: Agentic Support Platform - System Design

Reviewed file: `data/book/agentic-support-platform/interview.json`
Review date: 2026-06-24

## Executive Summary

This dataset has moved from a promising outline to a strong book-quality
agentic vertical. The central thesis is now explicit and well supported:
support is different because safety gating happens inside a live turn-taking
loop, while the customer is waiting, and the agent may take scoped
transactional action on the customer's account.

Recent changes fixed the previous largest issues. Capacity now has concrete
load and latency numbers. The API exposes turn IDs, idempotency keys, channel
metadata, scoped customer auth context, action proposal IDs, risk tier,
approval state, escalation reason, event stream, and audit IDs. The data model
now covers turns, action proposals, approval decisions, transaction attempts,
compensations, handoffs, retrieval evidence, and append-only audit records.
Transaction language is correctly framed as provider-scoped idempotency with
reconciliation and manual repair, not absolute exactly-once. The scoped
authority requirement is now represented in `satisfies.nonFunctional`, and the
previous step-view link omissions are fixed.

The remaining gaps are mostly integration depth, not missing fundamentals. The
expanded contracts and state model are stronger than the step diagrams and
flows that teach them. The live-loop, action-gate, transaction, and handoff
flows should show more of the state lifecycle, audit writes, timeout branches,
and customer-facing responses. Capacity is numeric but still not tied to
component sizing and bottleneck choices. Only one step has real options, so the
decision tree still teaches fewer trade-offs than the strongest book cases.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.25/5 | Strong architecture, requirements, API, and state model; remaining work is tying numbers and lifecycle state more tightly to component behavior. |
| Production realism | 4.10/5 | Much better transaction, authority, approval, and audit treatment; still needs more channel operations, capacity bottlenecking, abuse/fraud, tenant policy, and incident workflow detail. |
| Pedagogical flow | 4.20/5 | Clear seven-step story with a memorable thesis; more option comparisons and fuller sequence flows would make the trade-offs easier to defend in an interview. |
| Dataset/rendering fit | 4.45/5 | JSON parses and reference checks pass; no current node/link endpoint issues. Main fit gap is optional content depth, not schema breakage. |
| Overall | 4.25/5 | Strong and publishable, with targeted edits needed to reach flagship depth. |

## What Works Well

- The differentiator is crisp: the gate runs inside the live support loop, not
  before a later async workflow.
- The requirements cover the right domain surface: real-time conversation,
  policy plus account grounding, transactional actions, deflect/act/escalate
  decisions, human handoff, delegated authority, audit, and latency.
- The capacity section now gives defendable starting numbers: concurrent
  conversations, turns/sec, action mix, retrieval fan-out, turn latency,
  provider limits, audit volume, and side-effect semantics.
- The API examples now carry the controls a safe live turn needs: turn ID,
  idempotency key, channel, tenant, scoped auth context, action proposal ID,
  risk/reversibility, approval state, escalation reason, stream URL, and audit
  IDs.
- The data model now supports the promised behavior instead of just naming
  conversations/actions/audit. It has durable turn state, proposal state,
  approvals, transaction attempts, compensations, handoffs, evidence, and
  append-only audit.
- The action-gate step is a strong teaching centerpiece. The default option
  compares deterministic policy-rule tiers against a learned risk classifier
  clamped by guardrails, which is the right production trade-off.
- The transaction-safety step now uses honest provider language:
  effectively-once where provider idempotency exists, reconciliation for
  ambiguous outcomes, and manual repair when external state cannot be proven.
- The final design integrates the same components introduced in the steps and
  preserves the support-specific "live loop plus in-loop gate" idea.

## Highest-Impact Issues

### 1. The improved state model is not fully reflected in the step flows

The data model now has the right lifecycle objects, but the sequence flows only
show simplified component calls. For example:

- Step 3 records turn state after inference, but does not show the response
  returning to `Channel`, first-token streaming, or a deadline outcome being
  persisted before the customer sees a fallback.
- Step 4 shows approval and scoped token minting, but does not show durable
  `action_proposals`, `approval_decisions`, proposal expiration, or audit
  events.
- Step 5 shows transaction attempt recording and provider reconciliation, but
  does not show action status transitions such as `executing`,
  `provider_timeout`, `unknown_external_state`, `reconciled`, or
  `manual_repair`.
- Step 6 shows approval expiry and escalation, but does not show a durable
  `handoffs` record or the handoff package being assembled from transcript,
  account snapshot, policy evidence, and attempted actions.

Why it matters: this is now a stateful design, but the diagrams still mostly
teach request/response calls. In an interview, the candidate needs to explain
which durable object owns each transition and how the system resumes after
crash, timeout, or human delay.

Concrete fix: add state-store and audit messages to the existing flows rather
than adding new components. Show:

- `conversation_turns` created before work starts, updated on stream,
  timeout, and completion.
- `action_proposals` created before approval or execution.
- `approval_decisions` written before Identity mints the action-bound token.
- `transaction_attempts` moving through provider response, timeout,
  reconciliation, retry, and manual repair.
- `handoffs` written with queue, priority, SLA, package pointers, and read-only
  agent state.

### 2. Capacity is numeric, but not yet translated into sizing decisions

The capacity section is much improved, but it remains a list of assumptions.
It does not yet say what those assumptions imply for queues, storage,
admission control, inference capacity, provider backpressure, or human approval
staffing.

Why it matters: the live-loop premise depends on capacity choices. `~1.7k`
turns/sec, `~15%` action proposals, `~20%` human approvals for proposed
actions, `~5-10` audit events/turn, and QPS-capped commerce systems should
drive concrete architecture decisions.

Concrete fix: add one sizing note per major bottleneck:

- Gateway/channel: connection fan-out, per-channel deadlines, and admission
  control when turn backlog rises.
- Retrieval/account reads: parallel deadline budget and cache policy for KB
  versus account data.
- Inference: token budget, first-token target, model fallback, and queue depth
  alarm.
- Provider systems: circuit breaker thresholds, per-tenant/action rate limits,
  retry budget, and slow-action deferral.
- Human approval: expected approvals/sec, queue SLA, expiry policy, and
  escalation when no approver is available.
- Audit: events/sec and retention/storage estimate from `~5-10` events/turn.

The `capacityDiagram` should also show approval queue and audit/event volume,
not only the linear turn path.

### 3. Authority and tenant policy are still mostly prose, not modeled objects

The dataset now correctly states that customer text is untrusted and Identity
mints action-bound delegated tokens only after policy and approval checks. The
data model carries `required_authority`, `policy_version`,
`approver_principal`, and `policy_snapshot`, which is a major improvement.

What is still missing is a concrete authority/policy object. There is no
`tenant_action_policy`, `delegated_token_grant`, `customer_consent`, or
`verification_challenge` entity. The API uses `customerAuthContext`, but the
state model does not show how scope, consent, proofing level, token binding,
expiry, and revocation are represented.

Why it matters: support agents fail dangerously when authority is implicit.
The system must know exactly who authorized which action, on which resource,
under which tenant policy, with which proofing level, for how long.

Concrete fix: add a small authority model:

- `tenant_action_policies`: action kind, tenant, limit, reversibility tier,
  required proofing, approval rule, and version.
- `delegated_token_grants`: action ID, resource ID, amount/scope, expiry,
  approver, policy version, token hash, and revocation state.
- `customer_consents` or `verification_challenges`: proofing method, verified
  account/resource, timestamp, and allowed action scope.

Then tie these objects to the action-gate and approval sequence.

### 4. The action taxonomy needs a concrete reversibility matrix

The text names useful categories: reversible, compensatable, and not safely
reversible. The API/data model include `kind` and `reversibility`, and the
follow-up mentions agentic checkout. But the dataset does not yet include a
single matrix that maps support action types to default tier, approval rule,
provider behavior, compensation path, and escalation trigger.

Why it matters: the action gate is the centerpiece. A candidate should be able
to point at examples and say why "resend receipt" is auto, why a small refund
can be auto only inside policy, why a shipped-order cancellation is
compensatable at best, and why account closure or payment authority is
escalated.

Concrete fix: add a deep dive or data-model note with rows like:

- `resend_receipt`: reversible, auto, no provider money movement.
- `small_refund`: reversible/compensatable, auto only below tenant threshold,
  provider idempotency required.
- `large_refund`: compensatable but high risk, human approval.
- `cancel_unshipped_order`: compensatable, auto or approve depending on value
  and cutoff.
- `address_change`: reversible only before fulfillment cutoff, proofing
  required.
- `shipped_order_change`: not safely reversible, escalate.
- `agentic_checkout`: delegated payment authority, likely high-risk approval
  or separate follow-up design.

### 5. Option coverage remains narrow

Only `action-gate` has meaningful options. That is valid, and it is the most
important decision point, but the auto-generated Steps Overview still has only
one branch point. The rest of the walkthrough mostly presents the chosen
design.

Why it matters: a system design interview should teach trade-offs, not only a
reference architecture. The case is now strong enough that adding options
would make it more useful for senior/staff-level evaluation.

Concrete fix: add option comparisons to two or three steps:

- Step 3: fully synchronous action inside turn vs streamed response plus async
  action status vs forced human pause.
- Step 5: provider idempotency plus lookup vs local outbox/reconciliation vs
  saga-style compensation.
- Step 6: threshold-only handoff vs queue-aware routing vs human approval
  without full ownership transfer.
- Step 7: random QA sampling vs risk-tiered sampling vs incident-triggered
  review/quarantine.

### 6. Abuse, fraud, and customer identity proofing deserve a sharper path

The review should not turn this into a full fraud platform, but support is a
common abuse surface: refund abuse, social engineering, address-change account
takeover, false entitlement claims, repeated small credits, and prompt
injection against tool use.

Why it matters: the current design has enough ingredients to handle this, but
they are spread across grounding, guardrails, action gate, Identity, and audit.
A candidate should see where abuse signals enter the gate and how risky cases
become proofing or escalation.

Concrete fix: add one deep dive under `action-gate` or `txn-safety`:

- Inputs: account age, recent refund history, device/session risk, address
  mismatch, high-value item, repeated attempts, suspicious prompt content.
- Controls: proofing challenge, lower autonomy tier, human approval, fraud
  queue, and audit/event tagging.
- Failure mode: do not let a confident model response override policy or fraud
  signals.

### 7. Compliance and evaluation are good, but incident response is implicit

Step 7 now has strong metric and audit detail. It mentions quarantine when
error rates cross thresholds, but the actual incident workflow is not shown.

Why it matters: an acting support agent needs an operational kill switch and
rollback path. If wrong-action rate spikes after a policy/model rollout, the
system should degrade autonomy, freeze an action class, route to humans, and
preserve evidence.

Concrete fix: add an operational response path:

- Detect spike in wrong-action, duplicate-action, compensation, provider-error,
  or human-override rate.
- Disable or lower autonomy for affected action kinds/tenants.
- Roll back policy/model version or clamp learned risk classifier output.
- Notify QA/ops, sample affected conversations, and create repair tasks.
- Keep the conversation agent read-only for impacted actions until cleared.

## System Design Soundness

The high-level architecture is sound. The components match the problem:
customer and channel, support API/Gateway, conversation agent, inference,
policy KB, scoped account record, in-loop action gate, transaction engine,
payments/commerce provider, human agent, escalation router, durable session
state, guardrails, Identity/token broker, audit stream, and observability/eval.

The requirements are well scoped and now measurable enough to reason about.
The non-functional side-effect requirement is especially improved: it now says
provider-scoped idempotency, effectively-once with reconciliation, compensation
where possible, and manual repair where not. That is the right level of
honesty for external commerce/payment systems.

The API is no longer a toy interface. The turn endpoint exposes the state and
control handles needed for a live support turn. The approval endpoint binds
approver, policy version, reason, action ID, transaction ID, and audit. The
escalation endpoint carries context-package fields instead of just a reason.

The data model is the strongest recent improvement. It now supports:

- Live session and per-turn lifecycle.
- Proposed action state before execution.
- Human approval decisions bound to policy snapshots.
- Provider transaction attempts with idempotency and unknown-outcome states.
- Compensation and manual repair.
- Handoff packages and queue/SLA state.
- Retrieval evidence for grounding and audit.
- Append-only, correlated audit records.

The remaining soundness gap is not the component list. It is the relationship
between state, timing, and ownership. The dataset should show which service
creates and mutates each durable record, which state transitions are terminal,
and what happens when a deadline or external provider fails.

## Step-by-Step Pedagogical Review

### Step 1: Naive: A Bot That Answers But Can't Act

This is a good baseline. It now explicitly says the baseline ignores auth,
customer scope, and account state, which sets up the next steps cleanly. The
contrast between "deflect-only" and "free live action" is strong.

Improvement: this step is intentionally simple, so no major change is needed.
If expanded, show the support API/channel boundary lightly so the transition
to scoped live turns feels even more natural.

### Step 2: Ground in Policy + the Customer's Account

This step is much stronger now. It introduces policy evidence, account
snapshot versioning, scoped reads, and the trust boundary early. The deep dive
correctly handles disagreement between policy and account state, account-read
timeout, and untrusted customer text.

Improvement: add a brief note about stale account snapshots and cache policy.
Policy KB can be cached aggressively by version; account/order state usually
needs freshness rules by action type.

### Step 3: The Real-Time Loop & Latency Budget

This step now has the right sequence structure: channel to gateway, scoped
routing, parallel policy/account work, deadline-based inference behavior, and
durable turn persistence. The channel-specific degradation deep dive is good.

Improvements:

- Add the reply path back to `Channel` in the sequence.
- Show first-token streaming or "working on it" as an explicit response.
- Show the `conversation_turns` lifecycle: created, streamed, timed out, or
  completed.
- Tie capacity numbers to the loop: where queue depth is measured, where
  admission control fires, and what happens when provider/account reads are
  slow.

### Step 4: The Gate: Take Actions Inside the Loop, by Reversibility

This remains the strongest step. It explains that approvals bind to action ID,
resource/amount, policy version, and approver identity. It also places scoped
token minting after gate/approval, which is the right authority boundary.

The option comparison is high quality. Deterministic policy-rule tiers versus
learned risk classifier behind guardrails is a real production choice, and the
"classifier can lower autonomy but never raise it past policy" framing is
excellent.

Improvements:

- Show `action_proposals` and `approval_decisions` as durable writes in the
  flow.
- Add a reversibility/action matrix so the gate's tiering is concrete.
- Add fraud/abuse signals as inputs to the gate.
- Consider whether agentic checkout belongs in this core flow or should remain
  a follow-up; it is still high-risk enough to deserve a separate treatment.

### Step 5: Transactional Safety: Idempotency & Rollback

This step is now credible. It separates idempotency from reversibility and
uses provider-scoped language. The timeout/reconciliation branch is exactly
the right failure mode for refunds, cancellations, and order changes.

Improvements:

- Show action status transitions explicitly in the sequence.
- Include audit writes for attempt started, provider response, reconciliation,
  compensation, and manual repair.
- Show where a compensation creates a new action/attempt versus mutating the
  original action.
- Add one option comparison for execution strategy: provider idempotency,
  outbox/reconciliation, or saga compensation.

### Step 6: Deflect-vs-Escalate & Human Handoff

The handoff story is now useful. It includes routing criteria, handoff package
contents, priority/SLA, read-only mode after handoff, approval expiry, and
queue rerouting.

Improvements:

- Show the durable `handoffs` record in the sequence.
- Include the customer-facing response when approval expires or a human takes
  over.
- Clarify whether the conversation agent remains available as an assistant to
  the human, and what permissions it has in read-only mode.
- Add queue-aware routing as an option comparison if the case needs another
  trade-off.

### Step 7: Compliance, Audit & Evaluation

The audit and evaluation section is strong. It names event fields, correlation
IDs, tamper evidence, PII redaction, retention, online metrics, offline/QA
metrics, sampling by risk tier, and quarantine of bad policy/model versions.

Improvements:

- Add an incident response path from eval signal to autonomy reduction,
  rollback, repair, and customer remediation.
- Consider a sequence flow for audit/eval feedback into the action gate.
- Include tenant-specific retention/export requirements if this is meant to
  serve enterprise CX platforms.

## Final Design Review

The final design is coherent and integrates the steps well. It correctly names
the support API, scoped account resolution, real-time loop, KB/account
grounding, action gate, transaction engine, human approval, Identity, handoff,
audit, and evaluation. It also preserves the shared substrate from Agentic
Platform Foundations without rebuilding it inside this case.

The final view includes all 17 architecture nodes and all 20 links, and the
current reference checks show no local endpoint omissions in step or option
views. That is a meaningful fix from the prior review.

The final design could become more operational by naming lifecycle ownership:
Gateway owns authentication/scope and turn admission; Conversation Agent owns
turn orchestration; Action Gate owns proposal/risk/approval transitions;
Identity owns scoped token grants; Transaction Engine owns attempts,
reconciliation, and compensation; Escalation owns handoff package and queue
state; Observability/Eval owns quarantine and policy rollout feedback.

## Concept Introduction and Learning Flow

The concept staging is clear:

- Step 1 establishes the baseline and core danger.
- Step 2 introduces policy plus account grounding and the trust boundary.
- Step 3 introduces the real-time turn loop and latency budget.
- Step 4 introduces the in-loop reversibility-tiered action gate.
- Step 5 introduces provider-scoped idempotency, reconciliation, and
  compensation.
- Step 6 introduces deflect-vs-escalate and human handoff.
- Step 7 introduces audit, action-correctness evaluation, and operational
  feedback.

This is a good teaching order. Each step exposes the next problem instead of
randomly adding components.

The main pedagogical gap is trade-off density. Only the action-gate step
currently gives a real option comparison. Adding a few more option sets would
make the decision-tree wrap-up more valuable and help a candidate practice
defending choices under constraints.

## Step-to-Final-Design Coherence

The step-to-final-design coherence is strong. The final design contains the
components introduced throughout the walkthrough, and the recap fields now
stay support-specific. The strongest through-line is:

baseline support bot -> scoped policy/account grounding -> live turn loop ->
in-loop action gate -> idempotent transaction safety -> human handoff ->
audit/eval feedback.

The transitions that could still be sharpened are:

- Step 3 to step 4: the live loop introduces latency, then the gate introduces
  action, but the design should show how an action proposal can pause without
  breaking the customer turn.
- Step 4 to step 5: the gate decides execution, but the proposal/approval
  state machine should be visible before transaction attempts begin.
- Step 6 to step 7: handoff and eval are adjacent, but the QA/incident workflow
  should explicitly feed back into gate policy and model rollout.

## Realism Compared With Production Systems

The dataset now handles several production realities well:

- External side effects are not modeled as true exactly-once operations.
- Provider timeouts and ambiguous outcomes require lookup, reconciliation, and
  manual repair.
- High-risk actions require human approval bound to policy and identity.
- The agent goes read-only after handoff rather than continuing to act.
- Audit captures more than transcripts: turns, retrieval, decisions,
  approvals, transactions, compensations, and handoffs.
- Evaluation checks action correctness, not only CSAT.

Remaining production realism opportunities:

- Different channels need different behavior. Voice, chat, SMS, WhatsApp, and
  email should have different latency, identity proofing, attachment, and
  handoff treatment.
- Tenant policy is central in enterprise support. Allowed actions, thresholds,
  proofing requirements, retention, model choice, and audit export often vary
  by tenant.
- Fraud and abuse need explicit inputs to the gate.
- Human approval has staffing and queueing constraints, not just correctness
  constraints.
- Incident response should lower autonomy quickly when wrong-action or
  provider-error metrics spike.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level keys are coherent for this repo: requirements, capacity, API,
  data model, patterns, steps, final design, satisfies, interview script,
  level variants, and follow-ups.
- The dataset does not include `technologyChoices`; that is optional, but a
  managed-vs-self-hosted section could help this case because channel gateway,
  contact-center integration, vector search, workflow/orchestration, policy
  engine, and observability choices are realistic design discussion points.
- All `step.view.nodes` and option view nodes resolve to high-level
  architecture nodes.
- All `step.view.links` and option view links resolve to high-level
  architecture links.
- Every local view link has both endpoint nodes present, so the previous
  silently-filtered Mermaid edge issue is fixed.
- `finalDesign.view` node and link references resolve.
- Sequence participants and message references resolve, including nested
  `alt`/`par` messages.
- Pattern `steps[]` references resolve.
- `satisfies[*].steps[*]` references resolve, and the scoped delegated
  authority non-functional requirement is now covered.
- The dataset has one real options section (`action-gate`). Valid, but the
  decision-tree wrap-up will remain lightly branched until other steps add
  options.
- Requirements and capacity diagrams are valid Mermaid arrays. The capacity
  diagram is improved, but still omits approval queue and audit/event volume.

## Recommended Edits, Prioritized

### P1: Thread durable lifecycle state through the flows

Update the Step 3-6 sequence flows so they show turn, proposal, approval,
transaction attempt, compensation, handoff, and audit state transitions. This
is the highest-value next edit because the data model is now strong enough to
teach from.

### P1: Tie capacity numbers to component decisions

Add sizing notes and bottleneck behavior for Gateway/channel connections,
retrieval/account reads, inference queueing, provider QPS limits, approval
queue SLA, and audit storage.

### P1: Add an explicit authority and tenant-policy model

Add `tenant_action_policies`, delegated token grants, and customer
verification/consent records, or equivalent fields, so scoped authority is
stateful rather than only prose plus API context.

### P2: Add a reversibility and action-tier matrix

Make the action gate concrete with rows for receipt resend, small refund, large
refund, cancel, reschedule, address change, shipped-order change, account
closure, and agentic checkout.

### P2: Add more option comparisons

Add options for turn handling, transaction execution/reconciliation, handoff
routing, and evaluation/incident response. Keep them concise; the architecture
does not need to change.

### P2: Add abuse/fraud proofing to the gate

Show how refund abuse, social engineering, account-takeover risk, prompt
injection, repeated attempts, and suspicious account signals lower autonomy or
trigger proofing/escalation.

### P3: Add technology choices

For book completeness, consider a `technologyChoices` section covering contact
center/channel integration, vector search/KB, policy engine, workflow/durable
execution, identity/delegation, observability/eval, and audit storage.

### P3: Expand capacityDiagram

Add approval queue and audit/event volume nodes, and consider showing provider
backpressure as a side bottleneck rather than only a final linear step.

## What Not To Change

- Keep the "gate inside the live loop" thesis. It is the dataset's strongest
  differentiator.
- Keep policy plus account grounding. It is the right support-domain framing.
- Keep deterministic guardrails as the default gate strategy, with learned risk
  scoring only clamped behind policy.
- Keep provider-scoped idempotency and reconciliation language. Do not revert
  to absolute exactly-once claims.
- Keep escalation as a safe success path, not a failure.
- Keep action correctness above CSAT in the evaluation story.
- Keep this dataset focused on support-specific live action; do not duplicate
  all Agentic Platform Foundations material.

## Bottom Line

The current dataset is strong and substantially improved. It now has credible
requirements, capacity, API contracts, data model, transaction semantics,
authority framing, and renderer integrity. The next round should focus on
making the improved state model visible in the teaching flows, tying capacity
assumptions to bottleneck decisions, and adding a few focused trade-off
branches so the case reaches flagship depth.
