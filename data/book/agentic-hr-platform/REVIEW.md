# Review: Agentic HR Platform - System Design

Reviewed file: `data/book/agentic-hr-platform/interview.json`
Review date: 2026-06-24

## Executive Summary

This is a strong vertical framing: HR is correctly treated as higher risk than normal service automation because hiring decisions, PII access, policy correctness, and fairness monitoring all matter at once. The core teaching spine is clear: start with an unsafe auto-rejecting agent, add grounded policy retrieval, add identity-scoped PII access, then force a human-decision gate and adverse-impact monitoring.

The main gap is that the dataset states a broad production platform but only models a thin slice of it. The API and data model mostly support screening, while policy Q&A, onboarding/offboarding, effective-dated policy ingestion, identity scope, and audit/compliance evidence are described but not represented enough for an interview-grade design. The capacity section is also qualitative rather than quantitative, and several step diagrams reference links whose endpoints are not present in that step's node list.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 3/5 | Correct risk framing, but incomplete API/data model and no real capacity model. |
| Production realism | 3/5 | Human gate and fairness monitor are right; HRIS retries, workflow state, compliance artifacts, retention, and review operations are under-modeled. |
| Pedagogical flow | 4/5 | Clear narrative; would improve with options, trade-offs, and more realistic drills. |
| Dataset/rendering fit | 3/5 | JSON parses and references resolve, but step views include links whose endpoints are absent from the visible node set. |
| Overall | 3/5 | Promising and usable, but thinner than the adjacent agentic finance/legal/sales cases. |

## What Works Well

- The case has a crisp domain-specific center: agents recommend, humans decide adverse hiring outcomes.
- The baseline step is effective. Auto-rejection makes the legal, fairness, and privacy risks concrete.
- Effective-dated, jurisdiction-tagged policy grounding is exactly the right HR helpdesk concern.
- PII-scoped retrieval is introduced before sensitive helpdesk/onboarding actions, which is the right ordering.
- The four-fifths adverse-impact concept is placed where it belongs: next to the hiring gate, not as generic observability.
- The final design integrates the key nodes from the walkthrough and keeps the "Foundations substrate plus HR-specific gate" message clear.

## Highest-Impact Issues

### 1. API and Data Model Do Not Cover the Stated Product Surface

The description and requirements cover candidate screening, employee policy Q&A, onboarding/offboarding, policy grounding, PII scope, compliance evidence, and HRIS actions. The API has only three endpoints: create screening, decide screening, and fetch adverse-impact metrics. The data model has only `screenings`, `selection_metrics`, and `audit_record`.

This leaves major behavior unsupported:

- No policy-answer endpoint, response citation shape, policy version, effective date, jurisdiction, or escalation path.
- No onboarding/offboarding task API or workflow state, despite onboarding/offboarding being a functional requirement.
- No `policy_documents`, `policy_chunks`, `policy_versions`, or jurisdiction/effective-date metadata.
- No identity-scope, tenant, role, consent/notice, data residency, or delegated-action records.
- No candidate/job/rubric model that explains what "job-related skills only" means.
- No review queue or decision event model with timestamps, approver identity, rationale, override, appeal, or audit snapshot.

Concrete fix: expand `api` and `dataModel` with first-class policy Q&A, onboarding/offboarding workflow, policy corpus, review queue, decision events, identity scopes, and audit artifacts. Keep the screening endpoints, but make them part of a larger HR platform rather than the whole contract.

### 2. Capacity Is a Set of Invariants, Not a Sizing Model

The capacity section says decisions are human-decided, adverse impact is monitored, and retrieval is per identity. Those are requirements, not capacity. A system design interview needs at least a rough model for request volume, expensive work units, storage, latency, and human review load.

Concrete fix: add sizing assumptions such as:

- Candidate screenings per day and burst behavior after job postings.
- Policy/helpdesk QPS during normal periods and open enrollment.
- Onboarding/offboarding workflow volume and HRIS write rate limits.
- Human reviewer queue size, SLA, and staffing math for adverse outcomes.
- Vector index size, policy update cadence, audit retention, and trace storage.
- Batch cadence for adverse-impact metrics and minimum cohort thresholds.

### 3. Hiring Fairness Is Directionally Correct but Too Abstract

Step `hiring-gate` says to exclude prohibited signals/proxies and monitor four-fifths selection rates. That is the right headline, but production systems need more detail:

- A versioned job rubric and feature allowlist.
- Feature provenance showing which evidence supported each recommendation.
- Separation between protected-attribute data used for auditing and features available to scoring.
- Cohort windows, small-sample handling, and statistical caveats around adverse-impact flags.
- Review statuses and escalation rules when a metric crosses a threshold.
- Candidate notice and audit-publication workflow where applicable.
- Evidence that the human review is meaningful, not a rubber stamp.

Concrete fix: add a dedicated data-model slice for `job_rubrics`, `feature_evidence`, `protected_attribute_audit_data`, `review_decisions`, and `audit_runs`. Add a flow showing recommendation -> review queue -> human decision -> audit event -> metric aggregation.

### 4. Step Diagrams Have Hidden Endpoint Mismatches

The usual high-level node/link reference checks pass, but several step `view.links` include links whose endpoints are not included in the same step's `view.nodes`. Mermaid can materialize unlabeled or unintended nodes when an edge references a missing endpoint, so these diagrams may render confusingly.

Examples:

- `naive` includes `id-hris` (`Identity -> HRIS`) but the step nodes do not include `Identity`.
- `grounding` includes `screen-infer` (`ScreenAgent -> Inference`) but the step nodes do not include `ScreenAgent`.
- `privacy` includes `orch-pii` and `orch-guard` but the step nodes do not include `Orchestrator`.
- `hiring-gate` includes `orch-gate` and `orch-review` but the step nodes do not include `Orchestrator`.
- `service-eval` includes `id-hris` but the step nodes do not include `Identity`.

Concrete fix: either add the missing endpoints to each step's `view.nodes`, or replace those links with links whose endpoints are intentionally visible in that step.

### 5. The Walkthrough Has Too Few Design Choices

Every step has zero `options`. That keeps the story clean, but it makes the interview less useful as a trade-off exercise. Adjacent book datasets usually teach candidates by comparing choices.

Concrete fix: add options in the highest-value places:

- Policy grounding: one global corpus vs tenant/jurisdiction segmented indexes vs metadata-filtered shared index.
- PII enforcement: prompt-level instruction vs retrieval-filter enforcement vs token-scoped service boundary.
- Hiring gate: post-hoc review vs pre-decision queue vs thresholded escalation.
- Fairness monitoring: online signal logging vs scheduled batch audit vs independent auditor export.
- HRIS integration: synchronous writes vs workflow queue with idempotency and reconciliation.

## System Design Soundness

The requirements are well selected for HR: job-related screening, grounded policy answers, onboarding/offboarding, human adverse-outcome decisions, and adverse-impact monitoring. The non-functional requirements correctly name fairness, human decisioning, PII privacy, policy correctness, compliance, and auditability.

The weak point is enforceability. "Job-related features only" needs a source of truth: job rubric, required qualifications, feature allowlist, evidence snippets, and model input contracts. "Exclude proxies" needs a governance mechanism, not only a guardrail node. "Humans decide" needs workflow state, reviewer identity, rationale, and escalation/appeal support.

The architecture has the right components, but it compresses too much into generic services. `Guardrail` stands for prohibited-signal exclusion, residency, tenant isolation, and untrusted-text screening. `AuditLog` stands for recommendations, decisions, policy answers, provisioning, and metrics. Those are valuable abstractions, but the case would teach better if the data model decomposed them into concrete records.

## Step-by-Step Pedagogical Review

### Step 1: Naive: An Agent That Screens and Rejects

Strong opening. It creates the central failure mode and explains why HR is not just another automation surface. The diagram should not use `id-hris` unless `Identity` is visible, because the baseline is supposed to show unsafe direct action, not a delegated identity path.

Add a short note distinguishing "recommendation" from "decision" and "human review" from a superficial approval click. That distinction matters for the later gate.

### Step 2: Ground in Effective-Dated, Jurisdiction-Tagged Policy

The concept is well introduced and the example is concrete. This step should add a policy lifecycle: ingestion, approval, effective date, expiry/supersession, jurisdiction tags, citation metadata, and cache/index invalidation. Without that, the policy KB looks like a static index even though policy currency is the core point.

The `screen-infer` link also pulls in `ScreenAgent` without listing it in the step nodes. Either show `ScreenAgent` or use a link centered on `Orchestrator -> PolicyKB`.

### Step 3: PII-Scoped Retrieval & Identity

The step correctly binds retrieval scope to authenticated identity rather than query text. It should be sharper about role differences: employee self-service, candidate access, recruiter access, HR admin access, and service-account access are different scopes.

Add tenant/region/residency to the data model and show how scoped tokens or policy enforcement points travel through retrieval and HRIS calls. The current step mentions data residency but does not model it.

### Step 4: The Gate: Humans Decide, Adverse-Impact Monitored

This is the strongest step and should remain the center of the case. It needs more operational detail: pending queue, assignment, decision SLA, rationale capture, reviewer conflict-of-interest/segregation rules, override handling, and metric feedback.

The flow is useful but too short. Add the store and audit log to the sequence: recommendation written, human decision recorded, HRIS updated idempotently, audit event appended, metric aggregation updated. That would align the flow with the final design.

### Step 5: Service Delivery, Compliance & Evaluation

This step has the right ambition but combines too many topics: helpdesk escalation, onboarding/offboarding, LL144, EU AI Act, audit, answer-quality evaluation, and fairness dashboards. It risks becoming a list instead of a design step.

Consider splitting it into two steps: one for HR service workflows and HRIS integration, another for compliance/evaluation/audit evidence. If it stays as one step, add a concrete workflow state machine and explicit evidence artifacts.

## Final Design Review

The final design includes all major nodes and gives a coherent narrative. It is strongest when explaining the hiring gate and identity-scoped retrieval.

The final design overstates completeness because several promised capabilities are not backed by APIs or data tables. "Onboarding orchestrates HRIS actions" appears in prose, but there is no onboarding task model, idempotency key, HRIS operation state, provider callback/reconciliation path, or retry strategy. "Compliance and audit are first-class" appears in prose, but the only audit table is a generic payload record.

Concrete fix: make the final design reflect an explicit set of artifacts: policy answer with citations, screening recommendation with feature evidence, human decision event, HRIS operation, audit run, and adverse-impact metric snapshot.

## Concept Introduction and Learning Flow

The concepts are introduced in a good order: grounding, PII scoping, four-fifths monitoring, and bias-audit compliance. The missing concept is workflow state. HR platforms are not just LLM calls; they are long-running operational systems with queues, approvals, retries, escalations, HRIS reconciliation, and audit retention.

Add concepts for:

- Versioned decision rubric.
- Review queue/state machine.
- Protected-attribute audit separation.
- Idempotent HRIS writes.
- Policy corpus lifecycle.
- Retention and legal hold for audit evidence.

## Step-to-Final-Design Coherence

The steps build toward the final design, but some final-design nodes appear without enough step-level motivation. `ReviewStore`, `AuditLog`, and `Observability` are essential in the final design, yet only lightly developed in the walkthrough. `Gateway` and `Request` appear in the final design but are mostly absent from steps. Conversely, `HRIS` is central in the final design but the integration failure modes are not taught.

To improve coherence, make each step leave behind a concrete artifact:

- Step 1: unsafe baseline and risk inventory.
- Step 2: policy corpus/version model.
- Step 3: identity scope and access-decision record.
- Step 4: recommendation, review queue, human decision, fairness metric.
- Step 5: HRIS operation, audit record, evaluation dashboard, compliance export.

## Realism Compared With Production Systems

Production HR systems would need more than the current case models:

- HRIS/ATS APIs have rate limits, partial failures, duplicated webhooks, manual edits, and eventual consistency.
- Hiring workflows need reviewer assignment, recusal/conflict rules, SLA tracking, and escalation.
- Policy answers need citations, confidence/abstain behavior, escalation to HR, and explicit source/version display.
- Onboarding/offboarding needs idempotent provisioning/deprovisioning, reversible vs irreversible actions, and reconciliation.
- PII handling needs tenant isolation, role-based access, row-level retrieval filters, data residency, retention, deletion, and legal hold.
- Fairness monitoring needs a protected-attribute data boundary and careful treatment of small cohorts.
- Compliance needs dated evidence packets, not just generic logs.

The compliance angle is also date-sensitive. I spot-checked the two official anchors:

- NYC DCWP says LL144 AEDT use requires a bias audit within one year, public audit information, and required notices, with enforcement beginning July 5, 2023: <https://www.nyc.gov/site/dca/about/automated-employment-decision-tools.page>.
- EU Regulation 2024/1689 classifies Annex III employment/recruitment AI uses as high-risk and has staged application dates in Article 113: <https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng>.

The dataset should not need a legal treatise, but it should include a dated source-backed compliance note or avoid date-sensitive wording such as "obligation dates in flux" unless that uncertainty is intentionally part of the lesson.

## Dataset and Renderer-Facing Observations

Validation results:

- `interview.json` parses as JSON.
- Step `view.nodes` all resolve to `highLevelArchitecture.nodes`.
- Step `view.links` all resolve to `highLevelArchitecture.links`.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.
- `satisfies[*].steps[*]` references resolve.

Issues:

- Several step views include links whose endpoints are absent from that same step's nodes, listed above.
- No `technologyChoices` section is present. That is optional, but adjacent book agentic verticals use it to compare managed vs self-hosted choices. HR would benefit from choices around vector search, policy document management, workflow engines, HRIS connectors, identity/PDP enforcement, audit storage, and evaluation tooling.
- There are no `options`, so the generated decision-tree overview will not expose trade-off branches.
- Only one step has a sequence flow. More flows would help for policy answer, PII-scoped retrieval, human decision, and HRIS provisioning.
- `followUps` are good but sparse. Add operational drills for retries, stale policy, conflicting HRIS edits, missing demographic data, small-cohort fairness flags, and candidate appeals.

## Recommended Edits, Prioritized

### P1: Make the Platform Contract Real

Add APIs and data tables for policy Q&A, onboarding/offboarding, policy corpus/versioning, identity scopes, review decisions, and HRIS operations. Add idempotency keys, actor identity, tenant/region, timestamps, rationale, and audit correlation IDs.

### P1: Replace Qualitative Capacity With Sizing

Add numeric assumptions for screening volume, helpdesk QPS, open-enrollment bursts, HRIS write limits, audit retention, vector index size, and reviewer queue throughput.

### P1: Fix Step Diagram Endpoint Mismatches

For every step link, ensure both endpoints are included in `view.nodes`, or change the link. This is the only concrete renderer-facing issue found.

### P2: Deepen the Human Gate and Fairness Model

Add review queue state, feature evidence, job rubric versioning, protected-attribute audit separation, metric windows, small-cohort handling, and escalation behavior.

### P2: Add Options and Trade-Offs

Add options to the steps where candidates should reason: policy indexing, PII enforcement, gate semantics, fairness monitoring cadence, and HRIS integration strategy.

### P2: Split or Enrich Service Delivery

Either split Step 5 into service workflow and compliance/evaluation, or keep it as one step but add concrete HRIS workflow and compliance evidence artifacts.

### P3: Add Technology Choices

Add `technologyChoices` for workflow engine, vector/policy retrieval, identity/PDP, audit log, metrics/evaluation, and HRIS/ATS integration. Then assign tech icons and rebuild generated docs only if the dataset itself changes.

### P3: Add More Drills

Suggested drills:

- A California leave policy changes at midnight but the vector index is stale.
- A recruiter rejects after the agent recommended "advance"; what is audited?
- An HRIS write times out after provisioning completed.
- A candidate asks for the AEDT notice and bias-audit summary.
- A cohort is too small for a stable four-fifths metric.
- An employee asks a policy question that requires manager-only data.

## What Not To Change

- Keep the human-decision gate as the centerpiece.
- Keep effective-dated, jurisdiction-tagged policy as the grounding model.
- Keep PII-scoped retrieval before helpdesk/onboarding actions.
- Keep the explicit rejection of emotion/biometric inference.
- Keep the comparison to finance/legal gates in follow-ups; it places this case well inside the agentic platform series.

## Bottom Line

The case has the right thesis and a clear teaching spine. To reach the quality of the stronger book datasets, it needs more concrete platform contract, real capacity math, stronger HR workflow state, source-backed compliance evidence, and fixed step diagrams. The current version teaches what matters in HR agents; the next revision should teach how to operate it without hand-waving the hard parts.
