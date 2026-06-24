# Review: Agentic Sales Platform - System Design

Reviewed file: `data/book/agentic-sales-platform/interview.json`
Review date: 2026-06-24

## Executive Summary

The recent revision materially strengthened this case. The old review's biggest gaps - qualitative capacity, thin data model, missing send lifecycle, email-vs-multichannel ambiguity, absent option branches, and broken step-view endpoints - are now mostly addressed. The case now reads as a strong book chapter on the "reputation tier" of agentic risk: the agent can draft and coordinate, but the deterministic send gate, global suppression, approval snapshot, send queue, and deliverability control loop decide whether anything leaves the company.

The remaining issues are narrower but still worth fixing before treating this as flagship-quality. The most important are a capacity arithmetic inconsistency, suppression keying that cannot represent tenant and platform scope correctly, audit claims without a first-class audit-events model, and a handoff diagram/API mismatch where replies bypass the classifier in the architecture even though the flow says they are classified.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Strong core architecture; remaining concerns are state semantics, suppression scope, audit modeling, and a few API gaps. |
| Production realism | 4/5 | Much better: idempotency, provider callbacks, webhook dedupe, warmup, caps, pause/quarantine, and CRM conflicts are now present. |
| Pedagogical flow | 4/5 | Good baseline -> enrichment -> gate -> deliverability -> handoff progression with real options in the middle steps. |
| Dataset/rendering fit | 4.5/5 | JSON is valid; step, option, and final views have endpoint-complete links. A few semantic diagram refinements remain. |
| Overall | 4/5 | Strong and usable; a focused pass on state tables, handoff surfaces, and capacity math would make it book-ready. |

## What Works Well

- The description now scopes the case as email-first outbound and explicitly defers SMS/phone behind channel-specific consent and throttling. That resolves the earlier multichannel ambiguity.
- Capacity is now design-driving: tenant/campaign/prospect volume, provider fan-out, inbox caps, reputation thresholds, suppression lookup latency, and audit/event volume all motivate queues and control loops.
- The data model now includes the important sales-platform state: enrichment provenance, immutable drafts, approvals, send attempts, inbox health, provider events, suppression, and CRM sync.
- The send-gate step now teaches the right race: approval is not delivery; approval snapshots a version, queues work, and the gate re-checks suppression and reputation at send time.
- Option branches were added where they matter most: sync vs async enrichment, check-once vs approval-plus-recheck, and API-quota vs reputation-aware scheduling.
- The deliverability step is now domain-specific rather than generic rate limiting. It correctly separates provider API quota from sender reputation.
- Sequence flows now cover both gated sending and reply handoff, making the risky asynchronous paths easier to discuss.
- The previous renderer defect is fixed: step views and option views no longer reference links whose endpoint nodes are hidden.

## Highest-Impact Issues

### 1. Capacity math has an internal inconsistency

The capacity section says 3M prospects/day, a 60% cache hit rate, and "~3M cache misses/day x 2.5 = 7.5M provider calls/day." With 3M prospects/day and 60% cache hits, cache misses should be about 1.2M/day, which implies roughly 3M provider calls/day at 2.5 calls per miss. If the intent is 7.5M provider calls/day, then either the cache hit rate should be near 0% or the total prospect volume should be higher.

Why it matters: this case uses capacity to justify async enrichment, provider QPS shaping, and cost controls. A visible arithmetic mismatch weakens the teaching value.

Concrete fix: pick one consistent model and propagate it:

- 3M prospects/day, 60% cache hit -> 1.2M misses/day -> 3M provider calls/day -> about 35 QPS average before peak multiplier.
- Or 3M misses/day -> 7.5M provider calls/day -> say the 3M figure is post-cache-miss volume.

Also clarify whether the 3M messages/day send-volume estimate is one first-touch email per prospect or includes follow-up sequence attempts.

### 2. Suppression cannot represent scoped opt-outs correctly

The `suppression` table has `identity_key` as the primary key plus `scope: enum(tenant,global)`, but no `tenant_id`. That cannot distinguish a tenant-scoped suppression from a platform-global suppression for the same identity, nor can it represent different tenant-specific suppressions for the same identity.

Why it matters: the requirements promise "global, identity-resolved suppression" and the final design says tenant-global plus platform-global. The key shape must make the scope enforceable, queryable, and auditable.

Concrete fix: model suppression as something like:

- `scope: enum(tenant,platform)`
- `tenant_id nullable`
- `identity_key`
- composite uniqueness on `(scope, tenant_id, identity_key)`
- provenance fields for source event, source channel, reason, timestamp, and actor/system

Then state the gate lookup rule: block if either a platform-level entry exists or a matching tenant-level entry exists.

### 3. Audit is promised but not modeled as a first-class append-only record

The final design and `satisfies` section claim enrichment sources, immutable approved drafts, suppression checks, approvals, send attempts, and webhooks are recorded append-only with retention. The data model has several source tables, but no `audit_events` or equivalent append-only audit table/stream. The `AuditLog` node exists in the architecture, but the model does not define its schema.

Why it matters: this platform's defensibility depends on reconstructing who approved what, which source data was used, which checks ran, and why a send was allowed or blocked. Operational tables alone are not a durable audit trail.

Concrete fix: add an `audit_events` model with fields such as `event_id`, `tenant_id`, `actor_type`, `actor_id`, `action`, `object_type`, `object_id`, `sequence_id`, `attempt_id`, `draft_version`, `decision`, `source_event_id`, `policy_version`, `metadata`, and `ts`. Keep it append-only and link it to retention/deletion rules.

### 4. Reply handoff is clearer in the sequence flow than in the architecture/API

The handoff flow correctly shows `Email -> Orchestrator -> CRM/Rep/AuditLog`, with an alternate path for unsubscribe or angry replies. The architecture link, however, is `Email -> Rep` (`email-rep`) labelled "qualified reply -> handoff", and there is no API surface for reply webhooks. The only webhook API is `/v1/webhooks/delivery`, whose request enum covers bounce, complaint, unsubscribe, and delivered, but not reply.

Why it matters: a production system should not route raw replies directly to reps before classification, ownership checks, unsubscribe handling, and audit. The diagram and API should reflect the controlled path.

Concrete fix: add architecture links such as `email-orch` ("reply webhook") and `orch-rep` ("qualified handoff"), use those in the handoff/final views, and either extend `/v1/webhooks/delivery` to include `reply` or add `/v1/webhooks/replies`.

### 5. The send-attempt lifecycle is present but not yet explicit as a state machine

The data model now has statuses for sequences and send attempts, and the send-gate flow covers approve, block, lease, and deliver. What is still missing is a compact transition table that states legal transitions and the event that causes each one.

Why it matters: this is where most production bugs live: retries after provider timeouts, duplicate callbacks, late opt-outs, domain quarantine, campaign stop, and out-of-order provider events.

Concrete fix: add a short deep dive under the send-gate or deliverability step:

- `awaiting_approval -> approved -> queued -> sent -> delivered`
- `queued -> blocked` on suppression, cap exhaustion, campaign stop, or domain quarantine
- `sent -> bounced|complained|unsubscribed|replied`
- callback dedupe by provider event id
- provider timeout handling by idempotency key plus provider message id reconciliation

## System Design Soundness

The architecture is now credible. It has the right split between agentic drafting and deterministic authority: the model can research and personalize, while the send gate enforces suppression, compliance, approval, and reputation-aware rate limits. The introduction of `SendQueue` is especially important because it separates approval from delivery and gives deliverability a place to apply leases, pauses, and retries.

The strongest design choice is treating deliverability as the binding constraint. The capacity section, options, traps, and final design all reinforce the idea that provider API quota is not the real limit. The warmed-inbox cap math makes the queue and per-inbox scheduler feel necessary rather than ornamental.

The remaining design gaps are mostly about making promised guarantees mechanically enforceable. Suppression needs a better primary key. Audit needs an explicit append-only schema. Reply routing needs to go through the classifier in both the graph and API. The send-attempt statuses need a state machine so edge cases are not left to prose.

Compliance is improved but could still be made more concrete. The model has `consent_basis` and `footer_template_version`, and the final design mentions retention/deletion. It should also name where deletion requests, lawful-basis provenance, footer/address template versions, and policy-versioned compliance checks are stored.

## Step-by-Step Pedagogical Review

### Step 1: Naive: An Agent That Blasts Outreach

This is an effective baseline. It exposes sender reputation as the scarce asset and explains why the rest of the system exists. The diagram is now self-contained: `ResearchAgent -> Inference` and `ResearchAgent -> Email` clearly show unsafe direct sending without accidentally introducing the later send gate.

### Step 2: Ground in the CRM + Waterfall Enrichment

This step is much stronger than before. It now includes CRM dedupe, provider waterfall, provenance, cost/freshness pressure, and prompt-injection isolation. The sync-vs-async option is a useful interview fork because it connects capacity math to architecture.

One improvement: make the "async enrichment queue" a visible queue node if this step is meant to teach queue-based decoupling before send scheduling. Today the recommended option says queue, but the view only shows `Enrichment`, not a queue. This is not a renderer defect, just a teaching opportunity.

### Step 3: The Gate: Suppression, Compliance & Approve-Before-Send

This is now the best step in the case. The check-once option creates the right contrast, and the recommended option teaches immutable draft versions, idempotency, late opt-out races, and final pre-send checks. The sequence flow is concrete and production-relevant.

The next improvement is to add the state-machine deep dive described above. The step already contains the ingredients; a transition table would make the safety story precise.

### Step 4: Deliverability as First-Class Infrastructure

This step now teaches a sales-specific system design idea rather than generic throttling. The API-limit scheduler option is a good foil, and the recommended reputation scheduler correctly introduces warmup, live bounce/spam signals, leases, and auto-pause/quarantine.

Consider adding one sequence flow for the control loop: provider callback -> dedupe event -> update inbox health -> cap reduction or quarantine -> queued attempts blocked/held -> alert. That would make the operational feedback path as vivid as the send-gate path.

### Step 5: Qualified Handoff, Audit & Evaluation

The added flow improves this step substantially. It handles unsubscribe/angry replies separately from qualified or pricing asks, updates CRM, hands off to the owning rep, and appends audit provenance.

The architecture should be brought into alignment with this flow. Replace the direct `Email -> Rep` handoff link with `Email -> Orchestrator` and `Orchestrator -> Rep`, and expose a reply webhook API. Also add at least one trap here: common failures include routing to the wrong account owner, treating out-of-office as positive intent, missing unsubscribe intent in a reply, and overwriting CRM fields during handoff.

## Final Design Review

The final design now integrates the major steps well. It explicitly includes async provider waterfall, immutable approval snapshots, durable send queue, send-time suppression/reputation recheck, idempotency keys, webhook dedupe, inbox warmup/caps, CRM conflict resolution, audit, and evaluation. That is a meaningful jump from the earlier skeleton.

The diagram is structurally valid and endpoint-complete. Its remaining weakness is semantic: `Email -> Rep` makes reply handoff look direct, while the text and sequence correctly say replies are classified first. The identity broker is also under-connected visually; the final design mentions scoped delegated access, but the graph only shows `Rep -> Identity`. A link from `Identity` into the gate/CRM/send authority path would help candidates see where delegated authority is enforced.

## Concept Introduction and Learning Flow

The concept order works:

- start with reputation failure
- ground in CRM and enrichment
- add the deterministic send gate
- introduce reputation-aware scheduling
- close with handoff, audit, and evaluation

The recent option branches make the interview much more interactive. Candidates can now compare real design alternatives instead of passively receiving the final answer.

The remaining learning gap is that some core state ideas are distributed across API, data model, flow, traps, and final-design prose. A single state-machine deep dive would pull them together and make the case easier to teach.

## Step-to-Final-Design Coherence

The step-to-final-design coherence is now strong. Every major final-design component is introduced before the final design: enrichment and CRM in step 2, send gate and suppression in step 3, send queue and deliverability in step 4, and CRM handoff/audit/eval in step 5.

The previous link-endpoint issue is resolved. Step views and option views are now self-contained, so the incremental diagram reveal should render predictably.

Two coherence nits remain:

- The top-level pattern `LLM-as-judge / trajectory evaluation` lists `deliverability` in `patterns[].steps`, but the step tag appears on `handoff`. Include `handoff` or move the tag so the pattern cross-link matches where it is taught.
- The handoff step's view and final design should show the same controlled reply path as the sequence flow.

## Realism Compared With Production Systems

This is now fairly realistic for an interview case. It covers:

- provider waterfall cost and QPS pressure
- cache/freshness trade-offs
- CRM as system of record with conflict metadata
- immutable approval snapshots
- idempotent approval/send APIs
- provider webhook dedupe
- late opt-out and reputation races
- per-inbox warmup and caps
- bounce/complaint thresholds and quarantine
- global suppression
- tenant isolation and untrusted enrichment text

Production systems would still need more detail in a few areas:

- suppression scope and tenant/global keying
- audit-event schema and retention/deletion behavior
- reply webhook handling and ownership routing
- emergency pause API and operator workflow
- provider-specific message-id reconciliation after ambiguous timeouts
- policy versioning for compliance checks
- DSR/deletion handling for enriched PII while preserving minimal suppression records

These are good follow-up topics rather than fundamental flaws.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Top-level fields are conventional for this repo: requirements, capacity, API, data model, patterns, steps, final design, satisfies, interview script, level variants, and follow-ups.
- High-level architecture link endpoints resolve to declared nodes.
- Step views, option views, and the final design have endpoint-complete links.
- `view.highlight` IDs are visible in their corresponding views.
- Sequence participants and message endpoints resolve to canonical node IDs.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- `patterns[*].steps[*]` references resolve to real step IDs, though the LLM-as-judge pattern is semantically attached to the wrong step.
- Canonical node types are used; no unknown custom node types appear.
- No docs rebuild is needed for `REVIEW.md`, since it is repo-only.

## Recommended Edits, Prioritized

### P1: Fix the capacity arithmetic

Correct the cache-hit/cache-miss/provider-call calculation and clarify whether send volume counts first touches only or all sequence attempts.

### P1: Fix suppression scope modeling

Add `tenant_id` and composite uniqueness for tenant-vs-platform suppression. State the lookup rule the send gate uses.

### P1: Add a first-class audit-events model

Define the append-only audit schema promised by the final design and `satisfies` section.

### P2: Align reply handoff across graph, flow, and API

Route replies through the orchestrator/classifier in the architecture and expose a reply webhook or extend the delivery webhook to include replies.

### P2: Add a send-attempt state-machine deep dive

Make legal transitions, retries, late opt-outs, campaign stops, provider timeouts, and callback dedupe explicit.

### P2: Make delegated identity visible in the graph

Connect `Identity` to the components that consume scoped authority, such as CRM writes, approval, and sending.

### P3: Add handoff traps and one deliverability control-loop flow

Use these to teach wrong-owner routing, out-of-office classification, unsubscribe-in-reply handling, and domain quarantine.

### P3: Add book polish fields if desired

Technology choices would be useful here: CRM provider integration, enrichment providers, email sending providers, queue/scheduler, event stream, cache/index for suppression, warehouse/observability, and audit storage.

## What Not To Change

- Keep the case email-first. The deferred SMS/phone framing is clearer than trying to teach every channel at once.
- Keep the deterministic send gate outside the model. The agent drafts; the gate authorizes.
- Keep approval separate from delivery. That is the key safety lesson.
- Keep deliverability as first-class infrastructure, not a generic rate limiter.
- Keep CRM as the system of record and enrichment as provenance-bearing input, not model memory.

## Bottom Line

The recent changes moved this from a strong outline to a strong interview dataset. It now teaches the core sales-platform risks with concrete state, capacity, options, and flows. Fix the capacity math, suppression keying, audit schema, and reply-handoff surface, then this will be ready to stand alongside the stronger book cases.
