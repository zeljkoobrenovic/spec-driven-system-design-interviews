# Review: Agentic Support Platform - System Design

Reviewed file: `data/book/agentic-support-platform/interview.json`
Review date: 2026-06-24

## Executive Summary

This is a strong outline for a distinctive agentic vertical. Its central thesis
is clear: support differs from other agentic workflows because the safety gate
runs inside a live conversational loop, while the customer is waiting, and the
agent may take transactional action on the customer's account. The seven-step
story is easy to follow and the final design integrates the main components.

The dataset is not yet at the same depth as the strongest book cases. The
largest gaps are production specificity: capacity is qualitative, the API and
data model are much thinner than the architecture promises, transactional
"exactly-once" and rollback are worded too strongly for external commerce
systems, and the real-time loop lacks a concrete flow for latency control,
timeouts, approval pauses, and channel behavior. There is also one concrete
renderer-facing issue: several step views reference links whose endpoint nodes
are not in that step's `view.nodes`, so those links are silently filtered out
of the generated Mermaid diagrams.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 3.65/5 | The architecture direction is right, but capacity, API contracts, state model, and transaction semantics need more rigor. |
| Production realism | 3.35/5 | Good risk framing; missing channel operations, provider failure handling, approval state, consent, PII, rate limits, and realistic compensation boundaries. |
| Pedagogical flow | 4.05/5 | The step order teaches the central distinction well; it needs richer options/flows to teach trade-offs rather than only a happy path. |
| Dataset/rendering fit | 3.70/5 | JSON parses and IDs resolve, but multiple step diagrams lose links because view links include hidden endpoints; `satisfies` misses one non-functional requirement. |
| Overall | 3.70/5 | A promising book case with a sharp thesis, but it needs concrete operational depth before it is flagship-quality. |

## What Works Well

- The core distinction is memorable: support gates transactional actions inside
  the live conversation, unlike async workflows that can gate before execution.
- The requirements focus on the right domain problem: grounded answers,
  scoped account data, transactional side effects, deflect-vs-act-vs-escalate,
  human handoff, and auditable action decisions.
- The final architecture has the right high-level pieces: live channel,
  support API, conversation agent, inference, policy KB, account record,
  action gate, transaction engine, identity/token broker, escalation router,
  durable state, audit log, and observability/evaluation.
- The action-gate step is the strongest teaching moment. The reversibility
  tiering gives candidates a useful mental model for deciding auto-execute,
  approve, or escalate.
- The data model at least names the central nouns: conversations, actions, and
  audit records. That gives the dataset a starting point for deeper state.
- The final design does not drift away from the walkthrough; it includes the
  components introduced by the steps and keeps the "gate inside the loop" idea
  visible.

## Highest-Impact Issues

### 1. Capacity is qualitative, so the design cannot be sized or stress-tested

The capacity section has only three qualitative rows: "real-time budget",
"reversibility-tiered", and "exactly-once". It does not estimate concurrent
conversations, turns per second, channel split, action rate, approval rate,
retrieval fan-out, inference token volume, account-system calls, provider QPS,
audit-event volume, or storage retention.

Why it matters: this interview is supposed to be about a live loop under a turn
latency budget. Without numbers, a candidate cannot reason about admission
control, LLM serving latency, KB/index caching, account-system backpressure,
queueing for human approval, or audit storage. The architecture reads plausible
but cannot be defended operationally.

Concrete fix: add rows such as:

- Active load: `~50k concurrent conversations, ~2 turns/min active, ~1.7k turns/sec peak`.
- Action mix: `~15% of turns propose actions; ~70% low-risk auto, ~20% human approval, ~10% escalate`.
- Retrieval fan-out: `1 policy search + 1-2 account/order reads per actionable turn`.
- Latency budget: `p95 < 2.5s text turn, stream first token < 800ms; voice uses partial responses and async action status`.
- Audit volume: `turn + retrieval + gate + transaction + handoff events, e.g. 5-10 events/turn with 1-7 year retention depending on tenant policy`.
- Provider limits: commerce/payment/account systems have stricter QPS, retries,
  and circuit breakers than the chat frontend.

Update `capacityDiagram` to show the live-turn bottlenecks instead of only the
conceptual chain from latency to reversibility to rollback.

### 2. The API does not expose the controls needed for safe live action

`POST /v1/conversations/{id}/turn` accepts only `{ "message": "..." }` and
returns `{ "reply": "...", "action": "none|executed|awaiting_approval|escalated" }`.
The approval endpoint accepts only a decision and idempotency key. The handoff
endpoint accepts only a reason.

Why it matters: the platform promises scoped authority, idempotency, risk
tiering, approval, audit, and handoff context, but the external contracts do not
show how those controls are supplied or observed. A production support platform
needs stable turn IDs, action proposal IDs, idempotency keys, delegated scope,
channel metadata, approval actor, policy version, streaming/event output, and
reason codes.

Concrete fix: expand the API examples:

- Turn request: `turnId`, `idempotencyKey`, `channel`, `customerAuthContext`,
  `tenantId`, optional locale, message attachments, and conversation state
  cursor.
- Turn response: `turnId`, `reply`, `decision`, `proposedActionId`,
  `riskTier`, `reversibility`, `approvalRequired`, `escalationReason`,
  `eventStreamUrl`, and `auditEventId`.
- Action proposal/approval: separate `POST /v1/actions` or an explicit
  `proposed_actions` state, approval actor, policy/rule version, expiration,
  and reason codes for approve/reject.
- Handoff: transcript pointer, summary, attempted actions, account snapshot,
  reason, priority, and routing skill/queue.

If the API is meant to be illustrative rather than complete, say that directly
and add the missing fields as comments in the request/response examples.

### 3. The data model is too thin for idempotency, approval, rollback, and audit

The current model has `conversations`, `actions`, and `audit_record`. The
`actions.status` enum is only `executed, awaiting_approval, rejected, rolled_back`.
There is no durable state for proposed actions, approval decisions, attempts,
provider transaction IDs, compensation attempts, external callbacks, policy
versions, human handoff packages, KB source versions, or customer consent.

Why it matters: the design claims idempotent and reversible side effects, but
the state model cannot safely represent a live action lifecycle. In production,
the dangerous cases are not just "executed" or "rolled_back"; they are
`proposed`, `blocked_by_policy`, `awaiting_approval`, `approved`, `executing`,
`provider_timeout`, `unknown_external_state`, `compensating`,
`compensation_failed`, and `escalated_to_human`.

Concrete fix: add or expand entities:

- `conversation_turns`: turn ID, sequence number, channel, message hash,
  model version, latency, and response status.
- `action_proposals`: action kind, target resource, risk tier, reversibility,
  policy version, required authority, proposed payload, expiration.
- `approval_decisions`: approver principal, decision, reason, policy snapshot,
  created_at, and audit event ID.
- `transaction_attempts`: idempotency key scoped to action, provider request ID,
  provider response, retry state, terminal reason, and unknown-state handling.
- `compensations`: compensating action type, attempt state, provider response,
  and manual-repair flag.
- `handoffs`: summary, transcript pointer, attempted actions, customer/account
  snapshot, queue, priority, assigned agent, and SLA.
- `knowledge_sources` or retrieval evidence: KB version, document/source IDs,
  account snapshot version, and access decision.

Keep `audit_record`, but make it append-only with timestamp, actor/principal,
event type, correlation IDs, previous hash or sequence number, and retention
policy.

### 4. "Exactly-once" and rollback are overstated for external side effects

The capacity row says side effects are "exactly-once", and the data model note
says refunds/cancels are idempotent and reversible with compensating rollback.
That is directionally right, but too absolute for payments, order management,
shipping, and rescheduling systems.

Why it matters: external providers rarely give true exactly-once semantics.
They usually provide idempotency per request key plus ambiguous timeout cases,
webhooks, reconciliation, and manual repair. Some actions are not reversible:
a shipment can leave the warehouse, a seat can be lost, a refund can settle, a
coupon can be abused, or a regulatory notification can already have been sent.

Concrete fix: change the teaching language from "exactly-once" to
"effectively-once where provider idempotency exists, with reconciliation and
manual repair for unknown outcomes." Make reversibility a policy attribute, not
a universal guarantee:

- Reversible: resend receipt, update address before cutoff, small in-policy
  goodwill credit.
- Compensatable: refund then recharge, cancel then rebook, apply replacement
  credit.
- Not safely reversible: account closure, high-value refund, shipped order,
  identity change, legal/regulatory notice.

Then tie those categories back to the action gate and handoff rules.

### 5. The real-time loop lacks a concrete latency-control workflow

Step 3 states that each turn fits a conversational latency budget, but there is
no sequence flow for the turn loop and no mechanism for staying inside the
budget when retrieval, model inference, account reads, policy checks, and
actions are all in play.

Why it matters: this is the defining axis of the dataset. A safe but slow
support agent is not a usable live support agent. Candidates need to show how
the platform degrades gracefully: stream partial answers, ask for confirmation,
defer slow actions, time out account reads, cache policy results, circuit-break
commerce systems, and avoid holding a voice caller in silence.

Concrete fix: add a step 3 flow:

1. Channel sends turn with a deadline and sequence number.
2. Gateway authenticates and resolves scope.
3. Conversation agent starts retrieval/account reads in parallel under a
   deadline.
4. Inference streams a response or asks a clarifying question if action data is
   not ready.
5. Action gate either executes a fast low-risk action, returns
   `awaiting_approval`, or escalates.
6. Session store records turn state and timeout/retry metadata.

Add one deep dive for channel differences: text chat can show "working on it",
voice needs partial verbal feedback, and async messaging can tolerate delayed
action completion.

### 6. Authority, consent, and prompt-injection defense are under-modeled

The dataset says customer input is untrusted and actions use scoped delegated
authority, but the mechanism is mostly prose. The trust boundary appears in
step 2 and step 5, while the actual authority handoff is introduced in step 4
through `Identity & Token Broker`.

Why it matters: the riskiest support failures are authority confusion. A
customer message should never be able to expand scope, override policy, change
the beneficiary, or convince the agent to use a human's approval token outside
the approved action. The platform also needs consent and identity verification
before acting on account resources.

Concrete fix: make the authority model explicit:

- Gateway verifies customer identity and account scope before account reads.
- Customer messages are data, not authority. They can request an action but
  cannot approve policy bypasses.
- Action gate requests a scoped action token from Identity only after policy
  check and, when required, human approval.
- Tokens are bound to action ID, resource ID, amount, expiry, approver, and
  policy version.
- Guardrail separates untrusted message text from tool/action authority.
- PII redaction, retention policy, and transcript access are enforced per
  tenant/channel.

This could be a short sequence flow or a deep dive under the action-gate step.

### 7. Evaluation is promising but too vague for an acting agent

Step 7 correctly says CSAT is insufficient and action correctness matters. The
data model and final design do not show how correctness is measured, where
ground truth comes from, how bad actions are sampled/reviewed, or how evals feed
policy changes.

Why it matters: an acting support agent can look successful while issuing
unowed refunds, missing escalations, violating policy, or making customers happy
by doing the wrong thing. The system needs outcome and safety metrics, not just
conversation quality.

Concrete fix: add a small evaluation model:

- Online metrics: p50/p95 turn latency, timeout rate, deflection rate,
  escalation rate, approval wait time, wrong-action rate, duplicate-action
  rate, compensation rate, provider-error rate, and human override rate.
- Offline/QA metrics: policy adherence, groundedness, missed escalation,
  action payload correctness, PII leakage, hallucinated policy, and customer
  sentiment.
- Review workflow: sample actions by risk tier, route incidents to QA, feed
  policy/risk-rule updates, and quarantine a policy/model version if error
  rates cross thresholds.

### 8. Several step diagrams silently drop links because endpoint nodes are omitted

The JSON references valid global links, but `graphViewToMermaid` filters a
link unless both endpoints are present in that step's `view.nodes`. These step
views therefore lose intended edges:

- `live-loop`: `channel-gw` and `gw-conv` require `Gateway`, but `Gateway` is
  not in `view.nodes`.
- `action-gate`: `id-acct` requires `Account`, but `Account` is not in
  `view.nodes`.
- `txn-safety`: `conv-guard` requires `ConvAgent`, but `ConvAgent` is not in
  `view.nodes`.
- `compliance-eval`: `txn-log` requires `TxnEngine`, but `TxnEngine` is not in
  `view.nodes`.

Why it matters: the rendered walkthrough does not show all relationships the
author intended. This is especially harmful in `live-loop`, because the support
API/Gateway is the boundary that resolves customer scope and routes the turn.

Concrete fix: either add the missing endpoint nodes to each local view or
remove the links from those step views. For example, add `Gateway` to
`live-loop`, `Account` to `action-gate`, `ConvAgent` to `txn-safety`, and
`TxnEngine` to `compliance-eval` if those relationships should be visible.

### 9. `satisfies.nonFunctional` omits the scoped-authority requirement

The non-functional requirements include "Act only with scoped, delegated
authority; customer input is untrusted." The `satisfies.nonFunctional` list
covers latency, idempotent reversible side effects, risk-tiered approval, and
audit, but not this scoped-authority/trust-boundary requirement.

Why it matters: this is one of the central safety claims in an agentic support
platform. It should be explicitly tied to the grounding, action-gate, and
transaction-safety steps so the Design vs. Requirements view does not imply it
was forgotten.

Concrete fix: add a non-functional satisfies item:

`{ "requirement": "Scoped delegated authority", "how": "Gateway resolves customer scope; Guardrail treats customer text as untrusted; Identity mints action-bound delegated tokens after policy and approval checks.", "steps": ["grounding", "action-gate", "txn-safety"] }`

## System Design Soundness

The high-level architecture is directionally sound. The component set matches
the problem: a live channel sends turns through a gateway to a conversation
agent; the agent uses inference, policy KB, account records, session state, and
guardrails; the action gate controls transactional side effects; identity
brokers delegated authority; escalation routes humans into the loop; audit and
observability close the operational path.

The weak spots are mostly in the contracts and state. The architecture says
"safe action", but the API and data model do not yet carry enough state to
prove safe action. Idempotency requires scoped keys, external request IDs,
attempt state, and reconciliation. Human approval requires an approval record
bound to the proposed action, resource, amount, policy version, and approver.
Rollback requires compensation state and acknowledgement that some actions
become manual repair.

The requirements are well scoped but should be made more measurable. "Real-time
budget" should become specific p95 goals by channel. "Auditable" should name
event retention and evidence fields. "Scoped delegated authority" should be
reflected in API, data model, and satisfies.

The capacity model is the largest soundness gap. A live support platform has
multiple bottlenecks: frontend connection concurrency, turn throughput,
retrieval QPS, LLM serving, account/order reads, transaction-provider QPS,
human approval queue depth, and audit storage. The current capacity section
does not expose any of them.

## Step-by-Step Pedagogical Review

### Step 1: Naive: A Bot That Answers But Can't Act

This is a good baseline. It creates the right contrast between a deflection-only
bot and a reckless action-taking bot.

Improvement: show the support API/Gateway or channel boundary even in the
baseline, or make explicit that this step is intentionally ignoring auth,
scope, and account state. That sets up why step 2 matters.

### Step 2: Ground in Policy + the Customer's Account

The two-sided grounding idea is strong: policy says what is allowed, while the
customer/order record says what is true for this case. The concept chip is
clear and useful.

Improvements:

- Add source/version evidence for policy documents and account snapshots.
- State what happens when policy and account state disagree or account reads
  time out.
- Move more of the trust-boundary logic here: customer text is untrusted from
  the first turn, not only when a transaction happens.

### Step 3: The Real-Time Loop & Latency Budget

This step introduces the dataset's main differentiator, but it is currently
mostly declarative. It needs a concrete flow that shows deadline propagation,
parallel retrieval/account reads, streaming, timeout behavior, and durable turn
state.

Improvement: add a sequence diagram for one live turn, including `Channel`,
`Gateway`, `ConvAgent`, `KB`, `Account`, `Inference`, and `SessionStore`. Show
how the system responds when account lookup misses the deadline.

### Step 4: The Gate: Take Actions Inside the Loop, by Reversibility

This is the centerpiece and it works pedagogically. Reversibility-tiered
approval is the right abstraction, and the flow makes the approve-vs-auto path
visible.

Improvements:

- Bind approvals to a proposed action ID, policy version, amount/resource, and
  approver identity.
- Add the action token request to `Identity` after the gate decision.
- Clarify that agentic checkout/commerce is optional or make it a first-class
  path. It currently appears abruptly without API/data-model support.
- Add an option comparison: coarse risk tiering, policy-engine rules, and
  learned risk classifier with deterministic guardrails.

### Step 5: Transactional Safety: Idempotency & Rollback

The failure scenario is relevant: refund succeeds, connection drops, customer
retries. The step correctly points to idempotency and durable logs.

Improvements:

- Add a sequence flow for idempotent execution, timeout, provider lookup, retry,
  and compensation.
- Replace "exactly-once" with provider-scoped idempotency plus reconciliation.
- Separate idempotency from reversibility. An action can be idempotent but not
  safely reversible.
- Show where prompt-injection defense sits in the action execution path. Right
  now it is named as a pattern, but not operationalized.

### Step 6: Deflect-vs-Escalate & Human Handoff

This is a necessary step and the handoff context point is good. It correctly
frames escalation as a safe outcome rather than a failure.

Improvements:

- Add handoff package state: transcript summary, attempted actions, account
  snapshot, retrieved policy evidence, customer sentiment, priority, and queue.
- Add routing criteria: low confidence, policy conflict, explicit customer ask,
  repeated failure, high-risk action rejection, suspected fraud, or angry
  customer.
- Show what happens after handoff: does the agent continue assisting the human,
  go read-only, or pause?

### Step 7: Compliance, Audit & Evaluation

The "beyond CSAT" framing is strong. Action correctness is the right headline
metric for this domain.

Improvements:

- Make audit evidence concrete: event sequence, actor, action ID, policy
  version, retrieved source IDs, prompt/model version, and provider IDs.
- Add evaluation workflow: sample, label, compare to policy/account ground
  truth, quarantine bad policy/model versions, and feed rules back into the
  action gate.
- Cover retention and PII redaction, especially because transcripts can contain
  sensitive customer account data.

## Final Design Review

The final design description is coherent and integrates the step sequence. It
mentions the support API, scoped account resolution, real-time loop, KB/account
grounding, action gate, transaction engine, human approval, identity, handoff,
audit, and evaluation. The final design view includes all global links and does
not have the endpoint-missing issue seen in several step views.

The final design still reads more like an architectural summary than an
operational design. It should add the stateful lifecycles that make the design
credible: conversation turn lifecycle, action proposal lifecycle, approval
lifecycle, transaction attempt lifecycle, compensation/reconciliation lifecycle,
and handoff lifecycle.

The optional "agentic checkout" phrase is the one concept that does not fit
cleanly yet. Either make it a follow-up or add explicit commerce/payment
authority details so it does not distract from the core support/refund/cancel
case.

## Concept Introduction and Learning Flow

The concept staging is mostly good:

- Step 1 creates the baseline and failure mode.
- Step 2 introduces policy + account grounding.
- Step 3 introduces turn latency.
- Step 4 introduces the in-loop action gate.
- Step 5 introduces idempotency and compensation.
- Step 6 introduces escalation/handoff.
- Step 7 introduces audit and action correctness.

The main learning-flow issue is that most steps present the chosen design
without alternatives. Book-quality interviews usually teach trade-offs through
options: sync vs async turn handling, rules vs classifier risk tiering,
auto-execute thresholds, provider idempotency strategies, handoff routing
policies, and eval sampling strategies. Adding 2-3 option comparisons would
make the decision-tree wrap-up more useful and would force candidates to defend
design choices.

## Step-to-Final-Design Coherence

The final design includes the same components introduced across the steps, so
the walkthrough does not feel disconnected. The strongest through-line is:
baseline bot -> grounded support agent -> live turn loop -> action gate ->
transaction safety -> handoff -> audit/eval.

The weaker transitions are:

- Step 2 to step 3: grounding is introduced, then latency appears, but the
  retrieval/account-read budget is not operationalized.
- Step 4 to step 5: the action gate chooses execution, but the action state
  machine is not shown before idempotency/rollback are introduced.
- Step 6 to step 7: handoff and evaluation are adjacent, but there is no QA or
  incident workflow connecting human outcomes back to policy/gate tuning.

The `recap.newRisk` fields help the narrative. The final step's `newRisk`
points outside this dataset ("Other phase-3 verticals add contestability and
physical-experiment gates - see the plan"), which is less useful to a reader
inside this interview. Consider replacing it with a support-specific risk such
as "policy, model, and provider changes can silently shift action correctness,
so evals must feed gate-policy rollout and rollback."

## Realism Compared With Production Systems

Production support systems are messy in ways the current dataset only hints at:

- Channels differ. Voice, web chat, SMS/WhatsApp, and email have different
  latency expectations, identity proofing, attachment handling, and handoff
  experiences.
- Account systems are often slow or inconsistent. The design needs timeouts,
  stale-read policy, retries, backpressure, and "I am checking that" responses.
- Commerce/payment systems produce ambiguous outcomes. Timeouts require provider
  lookup, webhook reconciliation, and manual repair queues.
- Approval queues have SLAs. If a human does not approve in time, the agent
  must continue the conversation, escalate, or expire the proposed action.
- PII and retention are central. Support transcripts can include addresses,
  payment hints, account identifiers, and sensitive complaints.
- Fraud/abuse matters. Attackers may social-engineer the agent into refunds,
  address changes, warranty replacements, or account takeover support.
- Tenancy matters. Enterprise tenants need per-tenant policy, retention,
  allowed actions, model choices, and audit export.

The current architecture can support these concerns, but the dataset should
name enough of them to feel production-realistic.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level keys are coherent for this repo: requirements, capacity, API,
  data model, patterns, steps, final design, satisfies, interview script,
  level variants, and follow-ups.
- All `step.view.nodes` references resolve to high-level architecture nodes.
- All `step.view.links` references resolve to high-level architecture links.
- The action-gate sequence participant references and highlights resolve.
- Pattern step references resolve.
- `satisfies[*].steps[*]` references resolve, but the scoped-authority
  non-functional requirement has no `satisfies.nonFunctional` entry.
- Several step views include links whose endpoint nodes are not in the local
  view, so those links are filtered out during rendering. Fix the endpoint
  omissions listed in Highest-Impact Issue 8.
- The dataset has no `options` arrays. That is valid, but it means the
  auto-generated Steps Overview has no meaningful branch alternatives and the
  interview teaches fewer trade-offs than comparable book cases.
- The top-level `capacityDiagram` is valid Mermaid, but it is more conceptual
  than capacity-oriented.

## Recommended Edits, Prioritized

### P1: Make the operational contract credible

Add numeric capacity rows, expand the API examples, and deepen the data model
for turns, action proposals, approval decisions, transaction attempts,
compensations, handoffs, and audit evidence.

### P1: Fix the renderer-facing view link issues

Add the missing endpoint nodes or remove the affected links:

- `Gateway` in `live-loop`
- `Account` in `action-gate`
- `ConvAgent` in `txn-safety`
- `TxnEngine` in `compliance-eval`

### P1: Add scoped authority to `satisfies.nonFunctional`

Tie the scoped delegated authority requirement to `grounding`, `action-gate`,
and `txn-safety`.

### P2: Add three concrete sequence flows

Add flows for:

- Real-time turn under deadline.
- Idempotent transaction execution with timeout/reconciliation.
- Human handoff package and approval expiry.

These would make the dataset much more teachable without changing the overall
architecture.

### P2: Replace absolute rollback/exactly-once wording

Use provider-scoped idempotency, reconciliation, compensation, and manual repair
language. Classify actions as reversible, compensatable, or not safely
reversible.

### P2: Strengthen security, consent, and privacy

Make the identity/token broker, customer consent, untrusted-input partitioning,
PII redaction, transcript retention, and tenant policy more explicit.

### P3: Add option comparisons

Consider options for:

- Risk-tiering approach: static policy rules vs learned classifier plus policy
  guardrails.
- Turn handling: fully synchronous action vs stream response plus async action
  status.
- Handoff policy: threshold-only vs queue-aware routing vs human approval inside
  the same conversation.
- Evaluation: CSAT-heavy vs action-correctness/incident-heavy.

### P3: Move or formalize agentic checkout

Either move agentic checkout to a follow-up or add enough API/state/identity
detail for it to be a real supported action type.

## What Not To Change

- Keep the "gate inside the live loop" thesis. It is the dataset's strongest
  differentiator.
- Keep the bounded-autonomy framing. The agent can converse and propose/execute
  low-risk actions, while policy and human approval fence high-risk actions.
- Keep the policy-plus-account grounding model. It is exactly the right
  support-domain distinction.
- Keep escalation as a first-class success path rather than a failure.
- Keep action correctness above CSAT in the evaluation story.
- Keep reuse of shared Agentic Platform Foundations concepts; this dataset
  should focus on support-specific live action, not rebuild the whole substrate.

## Bottom Line

The dataset has a clear, useful system-design story and a strong final-design
outline. To become book-quality, it needs to move from conceptually correct to
operationally defensible: numeric capacity, richer contracts and state, honest
transaction semantics, concrete latency workflows, explicit authority/privacy
controls, and the small renderer fixes that keep the diagrams faithful to the
authored views.
