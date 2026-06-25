# Review: Agentic HR Platform - System Design

Reviewed file: `data/book/agentic-hr-platform/interview.json`
Review date: 2026-06-24

## Executive Summary

The recent revision materially strengthens this interview. The old gaps around
qualitative capacity, missing policy/onboarding APIs, thin data modeling, absent
options, missing technology choices, and broken local diagram endpoints are now
mostly addressed. The case now reads like a credible HR-specific extension of
the Agentic Platform Foundations dataset: effective-dated policy grounding,
PII-scoped retrieval, human hiring decisions, adverse-impact monitoring, audit
evidence, and idempotent HRIS workflows are all present.

The remaining issues are narrower and more production-shaped. The dataset says
onboarding/offboarding run through a durable workflow, but the architecture and
data model still do not make that workflow first-class. The human review queue
is conceptually strong, but API/data fields for assignment, SLA, idempotent
decision recording, appeal/escalation, and queue state are still light. Tenant,
residency, and retention metadata are also inconsistent across policy,
protected-attribute, HRIS-operation, and audit records.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Strong HR risk framing and much better contracts; workflow and tenancy details need one more pass. |
| Production realism | 4/5 | Good treatment of fairness, PII, HRIS retries, and audit evidence; review operations and provider reconciliation remain under-modeled. |
| Pedagogical flow | 4/5 | Clear step spine with useful options; more sequence flows would make policy Q&A, PII scoping, and onboarding easier to teach. |
| Dataset/rendering fit | 4/5 | JSON and references validate; previous endpoint mismatches are fixed. Capacity diagram is still not really a capacity diagram. |
| Overall | 4/5 | Strong and usable, with a few concrete edits needed to reach flagship-book quality. |

## What Changed Since The Previous Review

- Numeric capacity assumptions were added for screenings, helpdesk QPS,
  onboarding/offboarding workflows, reviewer load, policy corpus size, audit
  retention, and adverse-impact batches.
- API coverage now includes policy answers, workflow start/status, and pending
  hiring reviews in addition to screening and adverse-impact endpoints.
- The data model now includes job rubrics, feature evidence, review decisions,
  protected-attribute audit data, policy documents/chunks, HRIS operations,
  identity scopes, audit runs, and an append-only audit record.
- Options were added for policy indexing, PII enforcement, human review gate
  semantics, and HRIS workflow execution.
- The previous step-view link endpoint mismatches are fixed.
- `technologyChoices` now covers retrieval, workflow engines, identity/PDP,
  audit storage, fairness/eval tooling, and HRIS integration.

## What Works Well

- The central thesis is crisp: HR agents may recommend, but humans decide
  legally consequential hiring outcomes.
- Effective-dated, jurisdiction-tagged policy grounding is treated as a policy
  lifecycle problem, not just a vector-search problem.
- PII scope is tied to identity and data-boundary enforcement rather than prompt
  instructions.
- The hiring gate now carries feature evidence, rubric versioning, rationale,
  recusal, override, adverse-impact metrics, and protected-attribute separation.
- Capacity now has useful orders of magnitude and distinguishes LLM calls,
  reviewer throughput, HRIS write limits, vector-index size, and audit retention.
- The technology choices are domain-appropriate and mostly compare real
  operational trade-offs instead of generic product lists.

## Highest-Impact Issues

### 1. Durable Workflow Is Described But Not First-Class In The Design

Step `service-eval`, `POST /v1/workflows`, and the final design all say
onboarding/offboarding use an idempotent durable workflow with reconciliation.
That is the right production answer, but the architecture has no workflow queue
or workflow-state component, and the data model has only `hris_operations` with
a `workflow_id` field. There is no parent workflow record, task table,
provider-callback/reconciliation record, compensation/rollback model, or state
transition history.

Why it matters: onboarding and offboarding are long-running operational
workflows with partial failure, manual HRIS edits, duplicate callbacks, and
irreversible actions. Without first-class workflow state, the dataset still
teaches the correct slogan but not the system design.

Concrete fix: add a `WorkflowEngine` or `WorkflowQueue` node, plus
`workflow_runs`, `workflow_tasks`, and `workflow_reconciliation_events` tables.
Give Step 5 a sequence flow: start workflow -> enqueue idempotent HRIS task ->
provider write/callback -> reconcile -> audit -> mark complete/needs attention.

### 2. The Review Queue Contract Is Still Too Thin

The hiring gate is the strongest part of the case, but the API/data contract
does not yet fully support the review workflow it describes. `GET /v1/reviews`
returns `slaDueAt` and flags, but `screenings` has no assignee, queue state,
priority, SLA deadline, escalation state, or second-review marker.
`review_decisions` captures a decision, rationale, and recusal flag, but the
decision endpoint does not expose idempotency, reviewer identity binding,
appeal/notice artifacts, or audit correlation in the request/response shape.

Why it matters: "meaningful human review" is an operational process, not only a
human button. The candidate should be able to explain how reviews are assigned,
tracked, retried, escalated, and audited without turning the human into a
rubber stamp.

Concrete fix: add fields or tables for `review_assignments`, `review_state`,
`assigned_to`, `sla_due_at`, `escalation_reason`, `decision_idempotency_key`,
`notice_sent_at`, and `appeal_status`. Update the decision API to make the
human principal and audit correlation explicit.

### 3. Tenant, Residency, And Retention Metadata Are Inconsistent

The dataset correctly calls out tenant isolation, scoped identity, and data
residency, but those properties are not propagated evenly:

- `policy_documents` and `policy_chunks` have jurisdiction/effective dates but
  no tenant, residency region, locale, or source/approval provenance beyond
  `approved_by`.
- `hris_operations` has no tenant, subject, actor, residency region, attempt
  count, or provider response/error fields.
- `protected_attribute_audit_data` has no tenant, retention/legal-basis expiry,
  source, or access-control boundary beyond the note text.
- `audit_runs` has no tenant, jurisdiction/regime scope, generated artifact
  location, or reviewer/publication approval.

Why it matters: HR data is sensitive and often jurisdiction-specific. If the
dataset teaches residency and auditability, the records that move HR data should
carry the metadata needed to enforce and prove it.

Concrete fix: add tenant/residency/legal-basis fields to policy, protected
attribute, HRIS operation, and audit-run tables. Keep the schema small, but make
the enforcement metadata visible.

### 4. Key Non-Hiring Operations Need Sequence Flows

The dataset has one excellent sequence flow for the hiring gate, plus two API
sequences. The walkthrough would teach better if the core non-hiring flows were
shown where they are introduced:

- Policy Q&A: identity scope -> metadata-filtered policy retrieval -> inference
  with citations -> abstain/escalate -> audit answer.
- PII retrieval: token exchange or row-level scope -> HRIS read -> refusal when
  the request crosses identity scope.
- Onboarding/offboarding: workflow run -> HRIS operation -> callback/timeout ->
  reconciliation -> audit event.

Why it matters: these flows are where candidates reveal whether they understand
the difference between an LLM answer, a data-boundary enforcement point, and a
durable enterprise workflow.

Concrete fix: add one flow to `grounding`, one to `privacy`, and one to
`service-eval`. Keep each short; the current hiring-gate flow is a good model.

### 5. The Capacity Diagram Is Still A Constraint Diagram

The capacity table is now useful, but `capacityDiagram` still shows
`Fair -> Scope -> Human`. Those are design invariants, not capacity/load
concepts. It misses the strongest new sizing ideas: bursty screening queue,
open-enrollment helpdesk spike, HRIS write throttles, reviewer staffing, vector
index size, and nightly adverse-impact batch.

Concrete fix: revise `capacityDiagram` into a compact flow such as screening
burst -> queue -> LLM scoring -> review capacity, plus helpdesk QPS -> policy
cache/index, and HRIS workflow -> throttled writes. Keep it high level, but make
the visual match the capacity section.

## System Design Soundness

The requirements are now well selected and mostly enforceable. Screening is tied
to job-related features; policy Q&A is grounded in effective-dated,
jurisdiction-tagged policy; onboarding/offboarding is treated as a workflow;
humans decide adverse outcomes; and adverse-impact monitoring is explicit.

The capacity model is much stronger than before. It gives credible orders of
magnitude and makes reviewer load visible, which is especially important because
human review is the central bottleneck. Add only a little more: p95 latency/SLA
targets for policy answers, review queue age, HRIS operation completion, and
adverse-impact batch freshness.

The API surface is now broad enough for the stated product. The remaining API
work is mostly about operational guarantees: idempotency on screening creation
and decision recording, a policy-answer escalation or case endpoint, workflow
cancel/retry/compensate actions, and explicit auth-derived principal fields.

The data model is substantially improved. The highest-value addition is a real
workflow-state model. The next most valuable is tighter propagation of tenant,
residency, legal basis, retention, and audit artifact metadata.

## Step-by-Step Pedagogical Review

### Step 1: Naive: An Agent That Screens and Rejects

This remains a strong opening because it creates the core failure mode: an agent
auto-rejects and accesses data too broadly. The added distinction between a
recommendation, a decision, and meaningful human review sets up the rest of the
interview well.

Small improvement: the pattern tag mentions queue-based load leveling, but the
baseline step does not show a queue. Either move that pattern to Step 5 or add a
sentence explaining that bursty screening work must later move behind a queue.

### Step 2: Ground in Effective-Dated, Jurisdiction-Tagged Policy

This step is much stronger now. It covers policy lifecycle, effective dates,
supersession, jurisdiction tags, citations, and index invalidation. The options
are useful: metadata-filtered shared index is the right default, segmented
indexes are a plausible isolation trade-off, and a global corpus is clearly the
bad baseline.

Add a short sequence flow or drill for the hard case: a policy flips at
midnight, the cache/index is stale, and an employee asks at 12:05. That would
turn the lifecycle prose into an operational design.

### Step 3: PII-Scoped Retrieval & Identity

The step correctly rejects prompt-only privacy enforcement and moves scope to a
token or retrieval boundary. The role distinction could be sharper: employee
self-service, candidate access, recruiter access, HR admin access, and service
account access should produce different scopes.

Add a flow showing the token or PDP decision travelling to retrieval/HRIS, plus
a refusal path when the requester tries to cross record boundaries.

### Step 4: The Gate: Humans Decide, Adverse-Impact Monitored

This is the best step. It now includes rubric versions, feature evidence,
reviewer rationale, recusal, overrides, protected-attribute separation, rolling
cohorts, and small-sample caveats. The options are credible and teach the
difference between pre-decision review and post-hoc audit.

The remaining gap is review operations. Add assignment, SLA, escalation,
second-review/appeal, and notice artifacts to align the data/API contract with
the step's strong prose.

### Step 5: Service Delivery, Compliance & Evaluation

This step has improved the most but still carries the most pressure. It covers
helpdesk deflection, onboarding/offboarding, HRIS retries, compliance evidence,
quality evaluation, and fairness dashboards. That is a lot for one step.

If it remains one step, give it a concrete workflow sequence and workflow-state
schema. Otherwise split it into two steps: "Durable HRIS Workflows" and
"Compliance, Audit, and Evaluation." A split would make the operational design
easier to teach without burying compliance.

## Final Design Review

The final design now accurately integrates the main components from the
walkthrough and explicitly lists the platform artifacts: policy answers with
citations, screening recommendations with feature evidence, human decisions with
rationale, HRIS operations with idempotency keys, adverse-impact snapshots, and
dated audit runs.

The biggest mismatch is still visibility of the workflow subsystem. The final
design says durable workflow with reconciliation, but the diagram has no queue,
workflow engine, or workflow store. Add that node and tie it to HRIS,
AuditLog, and Observability.

## Concept Introduction and Learning Flow

The concept order is strong: unsafe baseline -> grounded policy -> PII scope ->
human gate/fairness -> service delivery/compliance. The newer options make the
case more interview-like because candidates now compare real choices.

The next teaching layer should be state transitions. Candidates should be able
to describe states for policy versions, screening review, HRIS operations, and
audit runs. That would connect the agentic concepts to the enterprise workflow
systems HR platforms actually rely on.

## Step-to-Final-Design Coherence

The steps now build toward the final design much better than before. Most final
nodes are introduced in a step, and the final design no longer feels like it is
claiming capabilities absent from the dataset.

Two transitions could be tighter:

- `Request` and `Gateway` appear only in the final design; if they matter, Step
  1 or Step 2 should mention auth/routing at the API boundary.
- The workflow claim in Step 5 and final design needs a visible workflow node
  and data model, as noted above.

## Realism Compared With Production Systems

The case is now production-plausible for an interview setting. It models HRIS
rate limits, idempotency, human review load, small-cohort caveats, policy
versioning, protected-attribute separation, and dated audit evidence.

Remaining realism gaps:

- HRIS/ATS integrations need provider callbacks, duplicate events, manual HRIS
  edits, reconciliation exceptions, and attempt/error history.
- Hiring reviews need assignment, escalation, conflict/recusal workflow,
  appeals, candidate notice, and evidence packets.
- Policy Q&A needs abstain/escalate behavior tied to a case workflow, not only a
  response field.
- Compliance artifacts need artifact storage, approval/publishing status, legal
  hold, and retention boundaries.
- Tenancy and residency should be carried by the records that enforce them.

## Dataset and Renderer-Facing Observations

Validation results:

- `interview.json` parses as JSON.
- Step `view.nodes` resolve to `highLevelArchitecture.nodes`.
- Step `view.links` resolve to `highLevelArchitecture.links`.
- Step and option links have endpoints present in their local `view.nodes`.
- Sequence participants resolve to canonical architecture node IDs.
- `satisfies[*].steps[*]`, `patterns[*].steps[*]`, and
  `technologyChoices[*].steps[*]` references resolve.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.

Issues and notes:

- `capacityDiagram` should be updated to match the new capacity table.
- `technologyChoices` now uses assigned icon objects and covers twelve
  HR-specific implementation concerns.
- There are no generated AI visuals for this dataset. That is optional.

## Recommended Edits, Prioritized

### P1: Make Durable Workflow First-Class

Add a workflow node, workflow-run/task/reconciliation tables, and a Step 5
sequence covering idempotent HRIS operation execution and recovery.

### P1: Deepen Review Queue State

Add assignment, SLA, escalation, idempotent decision recording, notice/appeal,
and audit-correlation fields to the review API/data model.

### P1: Propagate Tenant, Residency, And Retention Metadata

Add the enforcement metadata to policy, protected-attribute, HRIS-operation, and
audit-run records.

### P2: Add Missing Non-Hiring Flows

Add short sequence flows for policy Q&A, PII-scoped retrieval/refusal, and
onboarding/offboarding reconciliation.

### P2: Replace The Capacity Diagram

Make the diagram show bursts, queues, reviewer throughput, HRIS throttling, and
nightly adverse-impact aggregation instead of fairness/privacy invariants.

### P2: Tighten API Operational Guarantees

Add idempotency keys and auth-derived principal/audit fields to screening and
decision endpoints. Add explicit escalation/case handling for policy answers.

### P3: Improve Satisfies Entries

Make the `satisfies` bullets reflect the richer current design: durable HRIS
workflow, audit runs, policy citations, feature evidence, and low-confidence
fairness flags.

## What Not To Change

- Keep the human-decision gate as the centerpiece.
- Keep the explicit recommendation-vs-decision distinction.
- Keep effective-dated, jurisdiction-tagged policy grounding.
- Keep PII scope enforced at identity/retrieval boundaries, not prompts.
- Keep protected-attribute data separated from scoring features.
- Keep small-cohort caveats for four-fifths adverse-impact metrics.
- Keep the technology-choice trade-offs; they are now useful and domain-specific.

## Bottom Line

The recent revision moves this from a promising but thin case to a strong book
dataset. The next pass should not add broad new product surface; it should make
the existing claims operationally concrete, especially durable HRIS workflows,
review queue state, tenant/residency metadata, and non-hiring sequence flows.
