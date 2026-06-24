# Review: Agentic Public Benefits Platform

Reviewed file: `data/book/agentic-public-benefits-platform/interview.json`
Review date: 2026-06-24

## Executive Summary

This is a strong vertical in the agentic-platform series because it gives the domain a clear gate: due process. The interview consistently teaches that the model may extract and explain, but a deterministic rule engine decides eligibility and a caseworker owns every adverse outcome. The final design is coherent and the key project-specific idea, "audit-for-appeal", is memorable.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | The core safety boundary is right; capacity, state transitions, and data model details are too thin. |
| Production realism | 3/5 | Due process is well framed, but operational workflows, renewals, notices, appeal deadlines, and caseworker queues need more substance. |
| Pedagogical flow | 4/5 | The sequence builds cleanly from naive agent to contestable determination. More option trade-offs would make it interview-stronger. |
| Dataset/rendering fit | 3/5 | Schema references mostly resolve, but several step diagrams reference links whose endpoints are not in the step view, so the renderer drops those links. |
| Overall | 4/5 | Keep the concept; deepen the mechanics. |

## What Works Well

- The interview has a crisp domain thesis: benefits decisions are rights-affecting, so contestability is not a compliance afterthought.
- The model boundary is clear. The LLM extracts evidence and drafts explanations; the deterministic rule engine produces determinations; a human decides adverse outcomes.
- The steps build in a sensible order: naive automation, rule grounding, deterministic rules, human gate, appeal record, fairness monitoring, then evaluation.
- The final design integrates the shared Agentic Platform Foundations substrate without losing the public-benefits-specific gate.
- The `satisfies` section maps requirements to real steps and all referenced step IDs resolve.

## Highest-Impact Issues

### 1. Several step diagrams silently drop intended links

The renderer only emits a `view.links` edge when both endpoints are present in the same `view.nodes` list. This dataset references valid global links but omits an endpoint in multiple steps, so those edges disappear from the generated Mermaid.

Affected examples:

- `naive`: `pipe-decision` needs `Pipeline`, but the view has only `Applicant`, `IntakeAgent`, `Inference`, `DecisionStore`.
- `grounding`: `rules-index` needs `RuleEngine`; `pipe-case` and `pipe-guard` need `Pipeline`.
- `gate`: `pipe-gate` needs `Pipeline`.
- `audit-appeal`: `pipe-log` needs `Pipeline`.
- `fairness`: `pipe-decision` needs `Pipeline`.
- `compliance-eval`: `decision-appeal` and `appeal-reviewer` need `AppealPath`.

Concrete fix: either add the missing endpoint nodes to each step view, or replace those global link refs with local object links whose endpoints are already in the view. For teaching clarity, adding the missing node is usually better when the edge is meant to show pipeline handoff.

### 2. Capacity and renewal operations are under-modeled

The description promises intake, evidence gathering, determinations, and renewals, and the patterns include "Queue-based load leveling; admission control". The actual `capacity` section has qualitative invariants only: human-decided adverse outcomes, deterministic determinations, and built-in appeals.

That misses the hard production questions for this domain:

- seasonal enrollment or renewal surges
- backlog and SLA targets for caseworker review
- appeal-window deadlines and statutory notice timing
- re-determination load when rule thresholds change
- failure behavior when rule lookup, document extraction, or reviewer assignment is delayed

Concrete fix: add capacity bullets with rough work units, such as applications/day, evidence pages/application, adverse percentage, caseworker decisions/day, appeal rate, and renewal batch size. Then make the queue/admission-control pattern visible in the architecture or remove it from the pattern list.

### 3. The data model is too small for a contestable decision

The `dataModel` has `determinations`, `explanations`, and `audit_record`, but the record promised by the interview needs more than a blob of `rules_applied` plus explanation refs. A reviewer needs to reconstruct why a decision was made, under which authority, with which evidence, and whether appeal rights were preserved.

Concrete fix: add fields or tables for:

- applicant jurisdiction, benefit program, effective date, and rule package/version ID
- structured evidence items with source, confidence, extracted value, human corrections, and retention class
- status history: submitted, evidence_needed, determination_ready, adverse_pending, finalized, noticed, appealed, reviewer_decided
- caseworker decision fields: decision time, rationale, overrides, supervisor escalation, and accountable principal
- notice and appeal metadata: notice delivered at, appeal deadline, language/accessibility needs, reviewer assignment, reviewer outcome

Also resolve the small outcome mismatch: `/v1/determinations/{id}/decide` accepts `approve|deny`, while `determinations.outcome` lists `eligible|adverse_pending|denied|appealed`. If approval of an adverse-pending case is possible, the enum should make that terminal state explicit.

### 4. The API hides the rights-affecting state machine

The API surface is compact, but too compact for this case. A real benefits flow is not one POST plus a caseworker decision plus appeal. It needs idempotent submission, evidence updates, status reads, notice delivery, reviewer action, and record export.

Concrete fix: expand the API with endpoints or request fields for:

- idempotency keys and applicant/program/jurisdiction/effective-date inputs
- `GET /v1/determinations/{id}` for status and applicant-facing reasons
- `POST /v1/determinations/{id}/evidence` for supplemental evidence
- `POST /v1/determinations/{id}/notice` or an explicit notice event in the state machine
- `POST /v1/appeals/{id}/decide` for independent reviewer disposition
- record export for the appeal packet

This would make the due-process promise visible at the API boundary instead of only in prose.

### 5. Fairness monitoring needs an operational remediation loop

The fairness step correctly says individual correctness is not enough. But the current design stops at dashboards and flags. A production system needs to define what is measured, how cohorts are handled safely, and what happens when disparity is detected.

Concrete fix: add a deep dive or step detail covering:

- cohort definitions and protected-attribute governance
- comparison against similar applicants, not only raw approval rates
- caseworker-level outlier detection
- remediation workflow: audit sample, policy review, model/extraction review, caseworker retraining, rule correction, or retroactive re-review
- privacy constraints around demographic attributes

Also be careful with the `LLM-as-judge / trajectory evaluation` pattern here. It fits explanation-quality evaluation, but fairness monitoring should not read as if an LLM judges disparate impact. The primary mechanism should be statistical and policy review, with LLM eval only as a supporting tool.

## System Design Soundness

The main architecture boundary is sound: deterministic rule engine plus human adverse-decision gate is the right skeleton. The design would be stronger if it modeled the rule engine as a governed rules lifecycle, not just a runtime component. Public-benefits rules change, have effective dates, and may require legal review before deployment. The interview should show how rule packages are versioned, tested against golden cases, rolled out, and pinned to a determination.

Evidence handling also needs more depth. Extraction confidence, applicant-provided documents, official records, corrections, and missing-evidence requests are all central to benefits eligibility. The current design says "extract evidence" but does not show how disputed or incomplete evidence flows back to the applicant or caseworker.

The human gate is conceptually correct but operationally thin. If every adverse determination waits for a caseworker, the system needs queues, assignment rules, escalation, workload metrics, and deadlines. Without that, the design can satisfy "human in the loop" in prose while failing applicants through delay.

## Step-by-Step Pedagogical Review

### Step 1: Naive Agent That Decides Eligibility

Strong baseline. It makes the due-process failure concrete and gives the rest of the interview a reason to exist. Fix the diagram issue around `pipe-decision`; either show `Pipeline` or use a local link from the agent to the record if the intent is to show the naive shortcut.

### Step 2: Effective-Dated, Jurisdiction-Tagged Rules

This is the right next move. It introduces the legal source-of-truth before the deterministic engine. Add a little more about rule ingestion and governance: who approves rule changes, how effective-date tests are run, and how a determination records the exact rule package. Fix the missing endpoints for the rule, case-record, and guardrail links.

### Step 3: Deterministic Rule Engine

The model/engine split is clear and teachable. To make it more interview-like, add options such as policy-as-code, DMN/decision tables, or a custom rules service, with trade-offs around transparency, versioning, and legal review. The queue/admission-control pattern is attached here but not actually shown; either add a queue node and surge story or drop that pattern from this step.

### Step 4: Caseworker Gate

This is the strongest step. It names the gate and ties accountability to identity. It should also cover caseworker queue mechanics, override rationale, supervisor escalation, and what happens when the caseworker disagrees with the rule-engine output. Fix the dropped `pipe-gate` link by including `Pipeline` or using a local edge.

### Step 5: Audit-for-Appeal and Appeal Path

The "audit-for-appeal" concept is the best teaching asset in the dataset. Deepen it with appeal deadlines, record export, reviewer decision states, independence checks, and notice delivery. Fix the dropped `pipe-log` edge by including `Pipeline` or changing the view link.

### Step 6: Bias-at-Scale

Good progression from individual contestability to population-level consistency. It needs more specificity on metrics and remediation. Add a flow from fairness signal to audit/review action so the monitor is not just a dashboard. Fix the dropped `pipe-decision` edge or show a direct `DecisionStore` to `FairnessMonitor` signal if that is the intended data source.

### Step 7: Due-Process Compliance and Evaluation

The evaluation targets are right: correctness, explanation quality, and contestability. Add examples of eval artifacts: golden determinations, reviewer replay tests, explanation readability checks, multilingual/accessibility checks, and adversarial document-injection tests. Include `AppealPath` in the view if the appeal links are meant to render.

## Final Design Review

The final design is coherent and uses all major nodes. It correctly emphasizes that due process is built into the gate rather than added as logging. The missing pieces are mostly operational:

- no explicit queue/backlog path for caseworker decisions and renewals
- no applicant notice/delivery component
- no state machine for evidence-needed, adverse-pending, appealed, and reviewer-decided states
- limited rule governance and deployment lifecycle
- limited evidence-dispute workflow

Adding those would make the final design feel less like a principle diagram and more like a buildable benefits platform.

## Concept Introduction and Learning Flow

The concept progression works well: due process, effective-dated rules, deterministic decisioning, human adverse-decision gate, audit-for-appeal, fairness, and contestability eval. Each concept appears close to the step that uses it.

The missing teaching opportunities are option trade-offs. Most steps have no `options`, so the candidate is rarely asked to choose between credible designs. Add options where the domain has real trade-offs:

- rules as policy code vs decision tables vs rules service
- synchronous determination vs queued determination with SLA
- applicant-facing explanation generated before vs after caseworker review
- fairness monitor using aggregate rates vs matched-cohort analysis
- appeal record as event log replay vs materialized appeal packet

## Step-to-Final-Design Coherence

The final design includes the main components introduced by the steps. The weaker transitions are around shared substrate components that appear in the final view but are lightly taught here: `Gateway`, `Application`, `Identity`, `AuditLog`, and `Observability`. The steps mention them, but a candidate may not know what design responsibility each owns.

The `satisfies` mapping is mostly accurate. One adjustment: "Intake and extract evidence" maps only to `rules`, but the actual intake responsibility starts earlier and is also part of the naive baseline and grounding step. Consider mapping it to `grounding` and `rules`, or adding a dedicated intake/evidence step if the dataset wants to emphasize evidence handling.

## Realism Compared With Production Systems

The design is realistic in its core safety posture. It avoids the common trap of letting an LLM decide eligibility, and it treats a denial as a contestable public action.

To feel production-grade, it should cover:

- applicant notifications, language/accessibility needs, and record delivery
- missing or conflicting evidence requests
- renewal and recertification batches
- caseworker assignment, load, escalation, and timeout handling
- overpayment or retroactive correction flows
- rule-package governance and rollback
- data retention, consent/authority, and privacy partitioning
- disaster recovery for rule packages and decision records

These do not all need separate steps, but the highest-impact ones should appear in capacity, API, data model, or deep dives.

## Dataset and Renderer-Facing Observations

Clean checks:

- `interview.json` parses as valid JSON.
- `highLevelArchitecture.nodes`, `highLevelArchitecture.links`, and `highLevelArchitecture.types` are present.
- Step `view.nodes` references resolve to high-level architecture nodes.
- Step `view.links` references resolve to high-level architecture links.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Top-level `patterns[].steps[]` references resolve.
- Step pattern tags match top-level pattern names.
- Final design node and link references resolve.
- API sequence participants resolve to known architecture nodes.

Issues:

- Several `view.links` are valid globally but filtered out at render time because their endpoints are not present in the same `view.nodes` list. See the Highest-Impact Issues section for the concrete list.
- The `capacity` section is qualitative. That is allowed by schema, but this topic would benefit from concrete scale and queue/backlog parameters.
- The dataset has no generated AI visuals or `technologyChoices`. Those are optional; do not add them unless the book group wants parity with richer cases.

## Recommended Edits, Prioritized

### P1: Fix dropped step-diagram links

Add missing endpoint nodes or replace the affected link refs with local links. This is the only issue that can make the rendered walkthrough misleading.

### P1: Expand the state machine, data model, and API around contestability

Add statuses, notice/appeal metadata, evidence items, rule package versions, reviewer disposition, and idempotent applicant/caseworker/reviewer operations.

### P2: Add capacity and operational workflow details

Introduce rough scale, renewal surges, caseworker queues, SLAs, appeal deadlines, and failure handling. Show the queue/admission-control pattern if it remains listed.

### P2: Make fairness monitoring actionable

Define metrics, cohort controls, outlier detection, and remediation workflow. Avoid implying that LLM-as-judge is the primary fairness mechanism.

### P3: Add option trade-offs to teach interview decision-making

Use options for rule-engine implementation, queueing model, explanation timing, appeal-record shape, and fairness-analysis approach.

### P3: Add a few domain-specific operational details

Add notices, accessibility/language, missing-evidence loops, retention, and rule-governance rollout details where they naturally fit.

## What Not To Change

- Keep the due-process framing. It is the unique contribution of this vertical.
- Keep the deterministic rule engine as the eligibility authority.
- Keep human ownership of adverse outcomes.
- Keep "audit-for-appeal" as a named concept; it is stronger than generic audit logging.
- Keep the final design tied to Agentic Platform Foundations, but avoid letting the shared substrate crowd out the benefits-specific workflow.

## Bottom Line

This is a compelling and directionally correct public-benefits case. The next pass should make the promised contestability operational: fix the rendered step diagrams, give the determination lifecycle real states and deadlines, model the appeal record explicitly, and turn fairness monitoring into a remediation workflow.
