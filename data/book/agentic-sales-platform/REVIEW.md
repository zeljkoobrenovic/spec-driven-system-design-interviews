# Review: Agentic Sales Platform - System Design

Reviewed file: `data/book/agentic-sales-platform/interview.json`
Review date: 2026-06-24

## Executive Summary

This is a coherent, sales-specific agentic-system case. The central teaching arc is clear: a naive SDR agent destroys sender reputation, then the design adds CRM and waterfall enrichment, a deterministic send gate, deliverability infrastructure, and human handoff. The framing around the "reputation tier" of irreversible action is strong and fits the surrounding agentic vertical series.

The main gap is depth. The interview states the right components but does not yet make enough design-driving choices around scale, state, retries, channel scope, approval races, identity resolution, and deliverability operations. It also has renderer-facing diagram issues: several step views include links whose endpoints are not included in that step's node list, so Mermaid may create implicit nodes or produce confusing diagrams.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 3.5/5 | Correct conceptual architecture, but capacity, state model, and multi-channel semantics are thin. |
| Production realism | 3/5 | Good reputation/compliance instincts; missing send-attempt lifecycle, provider failure handling, idempotency, consent provenance, and operational runbooks. |
| Pedagogical flow | 3.5/5 | Nice baseline-to-gate progression, but no option branches and limited flows make it read more like a reference answer than an interview journey. |
| Dataset/rendering fit | 3/5 | JSON is valid and references mostly resolve, but step diagrams contain links with hidden endpoints. |
| Overall | 3.5/5 | Strong skeleton; needs production state and decision points to become a flagship book case. |

## What Works Well

- The case has a crisp domain risk: sender reputation and compliance, not money movement or legal work product.
- The naive baseline is effective because it immediately exposes the scarce resource: deliverability.
- The CRM plus waterfall enrichment step introduces the right grounding source for sales, and it ties personalization to authoritative prospect data instead of model memory.
- The deterministic send gate is the right control boundary for agentic sales: suppression, compliance, approval, and reputation-aware rate limiting belong outside the model.
- The final design integrates enrichment, approval, suppression, deliverability, audit, and handoff in a compact way.
- The top-level pattern set is relevant to the broader agentic-platform series: bounded autonomy, delegation not impersonation, prompt-injection defense, queue-based load leveling, and trajectory evaluation.

## Highest-Impact Issues

### 1. Capacity is qualitative, so it does not drive architecture

The `capacity` section has useful labels, but it never converts workload into design pressure. There are no assumptions for prospects/day, enrichment provider calls/prospect, send volume, inbox warmup ramp, queue depth, provider latency, bounce/complaint thresholds, or CRM write volume.

Why it matters: the core sales-platform trade-off is not "can we call an API" but "how fast can we safely enrich and send without exhausting provider budgets or sender reputation." Without numbers, the queueing, worker pools, deliverability manager, data retention, and observability thresholds are not justified.

Concrete fix: add a capacity model with example interview math:

- tenant count and campaigns per tenant
- prospects/day and messages/prospect
- waterfall fan-out and cache hit assumptions
- enrichment provider QPS/cost limits
- per-inbox daily caps, warmup ramp, and cap reductions on bad signals
- bounce/spam thresholds that trigger automatic pause
- audit and event volume

### 2. The data model cannot support the promised behavior

The current model has only `prospects`, `sequences`, and `suppression`. That is enough to describe the idea but not enough to implement the final design.

Missing state includes:

- campaign or sequence step definitions
- sequence messages and generated drafts
- approval records with approver, decision, timestamp, and version approved
- send attempts with idempotency key, provider message id, selected inbox/domain, status, retry count, and failure reason
- inboxes/domains with warmup state, SPF/DKIM/DMARC status, daily cap, current usage, and health
- deliverability events for bounces, complaints, unsubscribes, replies, and provider webhooks
- enrichment results per provider/field with provenance, confidence, cost, and freshness
- CRM sync state, external object version, and conflict metadata
- audit events as a first-class append-only table or stream, not only a diagram node

Concrete fix: expand `dataModel` with these objects, then map each to steps and final design. This would make the "auditable", "deliverability", "bidirectional CRM", and "global suppression" claims verifiable.

### 3. The send gate needs an explicit state machine and idempotency story

The gate is described as deterministic, but the lifecycle is underspecified. The API returns `sending|rejected`, while the sequence status enum has `awaiting_approval,sending,replied,stopped`. It does not model `approved`, `queued`, `blocked`, `sent`, `bounced`, `complained`, `unsubscribed`, `failed`, or `paused_for_reputation`.

Why it matters: the hard bugs in this system are races and retries:

- a prospect opts out after a rep approves but before the queued send fires
- the same approval request is retried
- an email provider times out after accepting a message
- a webhook arrives twice or out of order
- reputation drops while messages are already queued
- a campaign is stopped while send attempts are in flight

Concrete fix: add a step or deep dive for the sequence/send-attempt state machine. Make the gate re-check suppression and cap availability at send time, use idempotency keys for approve/send requests, persist immutable approval snapshots, and treat provider callbacks as deduplicated events.

### 4. The requirements say multi-channel, but the design is effectively email-only

The functional requirement says "multi-channel outreach" and the compliance requirement mentions TCPA for phone/SMS, but the architecture only has `Email` as the delivery surface, the deliverability section is email-specific, and the API example is `channel: "email"`.

This creates an ambiguity: either the interview is really about outbound email, or it must support channel-specific consent, throttling, approval, handoff, provider callbacks, and compliance for SMS/phone/social.

Concrete fix: choose one:

- Scope the case explicitly to email-first sales outreach and remove or defer the multi-channel/TCPA language.
- Or add a `ChannelRouter` and channel adapters, with separate consent/suppression rules for email, SMS, and calls.

### 5. The pedagogy lacks real decision branches

Every step has zero `options`. The story is clear, but candidates do not get many places to compare designs. Neighboring book cases such as finance and legal use options to teach important architecture forks; this case would benefit from the same treatment.

Good option branches to add:

- enrichment strategy: synchronous waterfall vs async enrichment queue vs cached profile refresh
- suppression identity: exact email key vs identity graph with confidence thresholds
- send gate placement: approval before queue vs approval plus final pre-send recheck
- delivery scheduler: provider API limit scheduler vs reputation-aware per-inbox scheduler
- CRM sync: CRM as synchronous source of truth vs local projection with conflict resolution

### 6. Several step diagrams reference links whose endpoints are not in the step view

The link IDs resolve globally, but the endpoints are absent from the individual step's `view.nodes`:

- `naive`: `sendgate-email` references `SendGate -> Email`, but `SendGate` is not in the view.
- `enrichment`: `orch-guard` references `Orchestrator -> Guardrail`, but `Orchestrator` is not in the view.
- `send-gate`: `draft-rep` references `DraftStore -> Rep`, but `DraftStore` is not in the view.
- `deliverability`: `orch-obs` references `Orchestrator -> Observability`, but `Orchestrator` is not in the view.
- `handoff`: `orch-crm`, `orch-log`, and `orch-obs` reference `Orchestrator`, but `Orchestrator` is not in the view.

Why it matters: Mermaid can implicitly create missing nodes or the renderer can produce diagrams whose visible components do not match the authored intent. This is especially confusing in a teaching walkthrough where each step is supposed to reveal a controlled subset of the final architecture.

Concrete fix: either add the missing endpoint nodes to each `view.nodes` list or replace those links with links whose endpoints are intentionally visible in that step.

## System Design Soundness

The architecture has the right major components: trigger/API, orchestrator, research worker, inference, enrichment, CRM, suppression, send gate, deliverability manager, draft store, identity/token broker, audit, and observability. The risk boundary is also correctly placed at the send gate, not inside the LLM.

The weak point is state. The final design depends on durable state transitions, deduped callbacks, approval snapshots, suppression updates, and provider-specific delivery events, but most of these are only described in prose. The design should make the queue and stateful send-attempt store explicit because those are what make "approved but not yet sent" safe.

The compliance story names CAN-SPAM, GDPR, and TCPA, but it should define the data the system stores to prove compliance: consent or lawful-basis metadata, unsubscribe source, address/footer template version, DSR/deletion handling, retention policy, and tenant-level isolation boundaries.

The deliverability manager is the best domain-specific component. It would be stronger if it owned explicit inputs and outputs: inbox health events in, cap decisions out, pause/resume commands, and scheduler leases for send attempts.

## Step-by-Step Pedagogical Review

### Step 1: Naive: An Agent That Blasts Outreach

The baseline is effective: it frames deliverability as the scarce resource and makes the rest of the interview necessary. The diagram should not use `sendgate-email` unless `SendGate` is shown; at this stage the point is probably `ResearchAgent -> Email` or `Orchestrator -> Email` as an unsafe direct send.

### Step 2: Ground in the CRM + Waterfall Enrichment

This step introduces the right sales-specific corpus. It should add one practical tension: waterfall enrichment is costly and latency-prone, so the system needs cache/freshness rules, provider fallbacks by field, confidence/provenance, and async refresh for lower-priority prospects. This is also the best place to explain prompt-injection isolation in concrete terms: untrusted web/enrichment text can inform a draft but cannot carry tool instructions or bypass the send gate.

### Step 3: The Gate: Suppression, Compliance & Approve-Before-Send

This is the core step, and the concept is correct. It needs more precision about ordering. Approval should not be treated as equivalent to delivery; it should create an approved immutable draft/version, then the send path should perform a final suppression and reputation check immediately before provider submission.

The flow currently sends from `Rep` to `Email` in the success branch. That hides the actual gate/scheduler/provider path. A better sequence is `Rep -> Orchestrator` approval, `Orchestrator -> SendGate`, `SendGate -> Suppression`, `SendGate -> Deliverability`, `SendGate -> Email`.

### Step 4: Deliverability as First-Class Infrastructure

This is a strong domain step. It correctly separates reputation limits from API limits. To make it production-realistic, add the control loop: ingest bounces/complaints/replies, compute health and caps, assign messages to warmed inboxes, pause bad domains, and emit alerts. Also show where queued work waits when caps are exhausted.

### Step 5: Qualified Handoff, Audit & Evaluation

The closing step is directionally right but too compressed. It combines reply classification, human handoff, CRM writeback, audit, and evaluation. It would benefit from one flow showing an inbound reply webhook becoming a qualification decision, CRM update, rep task, and audit event. Add failure cases such as ambiguous intent, out-of-office, unsubscribe, angry reply, and account-owner mismatch.

## Final Design Review

The final design integrates the steps cleanly and includes all major nodes. It is a good overview diagram. Its main weakness is that it looks more complete than the underlying data model and flows. The final design promises audit, CRM sync, delegated identity, suppression, deliverability, and evaluation, but only a subset has supporting API/data-model detail.

The final design should also clarify where queues live. The description says sequences queue for approval, and deliverability paces sends, but the diagram has `DraftStore` and no send queue or scheduler-owned durable queue. For this domain, the distinction matters: approval queue, send queue, provider retry queue, and webhook/event stream have different safety properties.

## Concept Introduction and Learning Flow

Concepts are introduced in the right order:

- deliverability risk first
- CRM/waterfall grounding second
- deterministic send gate third
- reputation-aware pacing fourth
- handoff/audit/eval last

The missing concept is "send attempt lifecycle." It should be introduced before or during the gate step because it connects approval, suppression, idempotency, provider callbacks, and audit.

The current concepts are concise and useful, but some patterns are only tagged rather than taught. "Delegation not impersonation" needs at least a sentence about scoped OAuth tokens and an `act`/approved-by claim. "Prompt-injection defense" needs an example of enriched web text being treated as untrusted content rather than executable instructions.

## Step-to-Final-Design Coherence

The final design contains all step-introduced components, but the step diagrams sometimes use final-design links before their endpoint nodes have been introduced. That weakens the incremental reveal. The clearest fix is to make each step view self-contained and make each newly introduced node/link visibly motivated by the `recap.newRisk` from the previous step.

The strongest transition is from naive sending to enrichment and gate. The weakest transition is from deliverability to handoff: the handoff step introduces several operational concerns at once without a prior problem statement or sequence flow.

## Realism Compared With Production Systems

A production sales platform would have more explicit handling for:

- provider outages, partial enrichment, stale enrichment, and cost budgets
- CRM sync conflicts, field-level permissions, and ownership/account routing
- unsubscribe and complaint webhooks that immediately update global suppression
- idempotent sends and provider callback deduplication
- tenant-specific suppression and global suppression interaction
- data retention, deletion, and PII access controls
- manual override workflows and emergency pause/kill switch
- deliverability runbooks for warming, pausing, quarantining, and rotating domains
- user-facing explanations for why a prospect was blocked, delayed, or handed off

These are not all required in the first version, but the interview should name which are in scope and which are deliberately deferred.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Top-level keys are conventional for this repo: requirements, capacity, API, data model, patterns, steps, final design, satisfies, script, level variants, and follow-ups.
- High-level architecture link endpoints resolve to declared nodes.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Pattern `steps[]` references resolve to real step IDs.
- Final design links are endpoint-complete.
- Every step has zero options. This is valid, but weaker pedagogically for a book case.
- Only one step has a sequence flow, and only one step has a deep dive. That is sparse for a domain with rich state and failure modes.
- Several step views include links whose endpoints are not included in the step's visible node list; fix these before relying on the generated diagrams.

## Recommended Edits, Prioritized

### P1: Fix step diagram endpoint completeness

Update each step `view.nodes` or `view.links` so every displayed link has both endpoints visible. This is the only clear renderer-facing defect.

### P1: Add production state for the send lifecycle

Expand the data model and at least one flow around approval, queued send, final gate check, provider submission, webhook callback, reply, stop, bounce, complaint, and unsubscribe.

### P1: Make capacity design-driving

Add concrete numbers and derived workloads. Use them to justify async enrichment, queue depth, send scheduler behavior, provider/cost limits, and deliverability thresholds.

### P2: Resolve the multi-channel ambiguity

Either make the case explicitly email-first, or add channel adapters and channel-specific consent/suppression/compliance.

### P2: Add option branches

Add options to the enrichment, send gate, deliverability scheduler, and CRM sync steps so candidates compare real trade-offs instead of receiving a single path.

### P2: Strengthen compliance and tenant-isolation details

Add consent/lawful-basis fields, retention/deletion behavior, tenant partitioning, access control, and audit query examples.

### P3: Add more traps and deep dives

Good additions would be: per-inbox suppression trap, approval snapshot trap, "API limit is not reputation limit", CRM overwrite trap, provider timeout/idempotency trap, and warmup emergency pause runbook.

## What Not To Change

- Keep deliverability as the central scarce resource; that is the strongest teaching idea in the case.
- Keep the deterministic gate outside the model. The agent may draft, but it should not decide whether sending is legally and reputationally safe.
- Keep CRM as the system of record and enrichment as a grounded, provenance-bearing input rather than model memory.
- Keep the connection to Agentic Platform Foundations, but make sales-specific state explicit enough that the case stands alone.

## Bottom Line

This is a strong outline for an agentic sales interview, with the right domain risk and control boundary. To make it production-grade and book-ready, add quantitative capacity, durable send-state modeling, explicit idempotency/retry behavior, channel-scope clarity, option branches, and self-contained step diagrams.
