# Review: Agentic Healthcare Platform - System Design

Reviewed file: `data/book/agentic-healthcare-platform/interview.json`
Review date: 2026-06-25

## Executive Summary

This is a strong high-stakes agentic-system walkthrough. The case has a clear thesis: healthcare decision support must be grounded, calibrated, safety-checked, and clinician-authorized, with abstention as a successful safe output. The step order is coherent and the final design mostly integrates the components introduced along the way.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4 | The safety framing is strong, but API, data model, state transitions, capacity, and operational controls are too thin for the claims. |
| Production realism | 3 | Good HIPAA/BAA, SaMD, no-train, audit, and clinician-gate language; missing concrete EHR integration, idempotency, retry, rate-limit, alert-fatigue, and incident workflows. |
| Pedagogical flow | 4 | The naive-to-safe progression works well, though zero step options reduces trade-off teaching. |
| Dataset/rendering fit | 3 | IDs mostly resolve, but several step diagrams select links whose endpoint nodes are omitted, so important edges are filtered out at render time. |
| Overall | 4 | Usable and compelling, with a few concrete edits needed before it feels production-grade. |

## What Works Well

The dataset is unusually clear about the safety boundary. "Recommend, never act", "abstain over guess", deterministic safety checks, and clinician sign-off are repeated in requirements, steps, final design, and satisfies mappings.

The step progression is easy to teach: naive answer, grounding, calibration/abstention, deterministic safety, clinician gate, PHI/safety case, then eval. Each step exposes the next risk through `recap.newRisk`, which makes the walkthrough feel intentional rather than a list of components.

The final design is compact and readable. It keeps the agent as a bounded node inside a deterministic pipeline instead of implying autonomous clinical action.

The case correctly names healthcare-specific concerns that generic agentic cases often miss: PHI scoping, BAA/no-train terms, SaMD/FDA framing, source traceability, clinician ground truth, and harm-avoidance evaluation.

## Highest-Impact Issues

### 1. The API and data model do not yet support the safety story

The API surface is intentionally small, but it is now too small for the stated requirements. `POST /v1/recommendations` accepts only `patientId` and `query`; it does not carry clinician identity, tenant/organization, encounter/care-team context, intended use case, urgency, idempotency key, required output type, or consent/break-glass context. The sign-off endpoint accepts only `decision` and `note`; it does not model modification, rejection reason, second review, clinician attestation, or the exact EHR action being authorized.

The data model has the same gap. `recommendations`, `safety_checks`, and `audit_record` are a good start, but they cannot reconstruct the safety case promised by the narrative. Add fields/entities for request type, tenant/org, encounter, care-team scope, retrieval snapshot, guideline/formulary version, patient facts used, citation spans, model/prompt/tool versions, abstention reason, calibrated confidence details, safety-rule version, clinician decision metadata, and immutable EHR write outcome.

Concrete fix: expand the API and schema around a first-class `recommendation_case` or `clinical_decision_support_case`, with child records for retrieved evidence, safety checks, calibration result, sign-off decision, and EHR write/audit events.

### 2. Capacity is not actually capacity

The `capacity` section lists qualitative safety invariants: default abstention, recommend-only autonomy, and deterministic override. Those are important requirements, but they do not help a candidate size or operate the system. The dataset also includes a "Queue-based load leveling; admission control" pattern, but there is no queue/admission node, capacity math, or step that teaches load shedding.

Concrete fix: add a real capacity model. Include daily active clinicians, clinical queries/day, peak QPS, average EHR retrieval fanout, guideline index latency, model-token budget, inference concurrency, sign-off queue depth, EHR write rate limits, target p95 latency for interactive recommendations, and async timeout behavior. If queue-based load leveling remains in patterns, add a queue/admission-control step or remove the pattern.

### 3. The clinician workflow is under-modeled

The gate is the core of the case, but it is represented mostly as a single sign-off call. In production, the hard part is the worklist and decision workflow: pending recommendations, abstentions needing review, modified recommendations, rejected recommendations, urgent vs non-urgent triage, alert fatigue, escalation, and timeouts. A clinician may authorize an order, edit a note, request more evidence, or reject the recommendation entirely.

Concrete fix: add a `Clinician Worklist / Review UI` node or make `RecStore` explicitly back that workflow. Add states such as `drafted`, `blocked_by_safety`, `abstained`, `awaiting_signoff`, `modified_by_clinician`, `authorized`, `rejected`, `expired`, and `ehr_write_failed`. Include a sequence flow that shows create -> evidence/safety -> review -> authorize/reject/modify -> EHR write -> audit.

### 4. Calibration and deterministic safety are plausible but underspecified

The calibrator is called "deterministic", but confidence calibration for model output is not inherently deterministic in the same sense as a drug-interaction rule. The current text does not explain what the calibrator measures, how thresholds are set, how task risk changes thresholds, or how drift is detected. The deterministic safety layer names contraindications, interactions, allergies, and dose limits, but not source-of-truth systems, rule versioning, stale chart handling, or what happens when patient data is missing.

Concrete fix: split "calibration" into grounded-evidence sufficiency, model uncertainty/score, and risk-tier policy. Split "safety layer" into rule sources, patient facts, versions, pass/block/warn result, and fail-closed behavior when required facts are absent.

### 5. Several step diagrams silently drop important links

The renderer only emits selected links when both endpoints are present in `view.nodes`. Several step views select links whose endpoint nodes are omitted:

- `naive`: `id-ehr` needs `Identity`, which is absent.
- `grounding`: `phi-ehr` needs `PHIScope`, which is absent.
- `privacy`: `pipe-phi`, `pipe-guard`, and `pipe-log` need `Pipeline`, which is absent.
- `eval`: `gate-clin` needs `AbstainGate`, which is absent.

Those links resolve to real high-level architecture links, but they are filtered out of the generated Mermaid, so the rendered diagrams omit connections that the captions rely on. This is especially damaging in the grounding and privacy steps, where the missing edges are the concept being taught.

Concrete fix: either add the missing endpoint nodes to each step view or change the selected links to connect only visible nodes. Also reconsider the naive diagram: it includes `EHR` and an EHR write link even though the text says the baseline has no patient-chart grounding and no clinician gate.

## System Design Soundness

The requirements are directionally right: grounded clinical support, deterministic checks, abstention, licensed clinician authorization, PHI privacy, auditability, and SaMD framing. The main missing requirement is explicit scope control by clinical task and risk tier. Dosing, differential diagnosis, chart summarization, and guideline lookup have very different risk profiles and should not share one threshold or one approval path.

The architecture has the right components, but some boundaries are vague. `Gateway` says it resolves care-team scope, `PHIScope` performs scoped retrieval, and `Identity` binds the clinician principal, but the flow does not clearly define which component authorizes chart access, which enforces minimum-necessary retrieval, and which emits access audit events.

The data model should capture a reproducible safety case. Today it stores a recommendation, safety checks, and generic audit events. It should also store the exact evidence bundle, guideline/formulary versions, model/tool/prompt versions, confidence/calibration features, safety-rule versions, clinician decision, EHR write result, and retention/access policy.

The final design says "nothing acts on the patient autonomously", which is the right invariant. It should make the authorized action explicit: order, note, recommendation-only message, or chart summary. The sign-off response should not just be `authorized|rejected`; it should identify what action was authorized and whether the EHR write succeeded.

## Step-by-Step Pedagogical Review

### Step 1: Naive: An Agent That Answers Clinical Questions

This is a strong baseline because it makes the harm concrete. The trap is useful and the agent-harness concept connects the case to Foundations.

The diagram should be simplified. Including `EHR` and selecting `id-ehr` confuses the baseline because the text explicitly says there is no chart grounding and no clinician gate. Show clinician -> agent -> inference, then let step 2 introduce chart/guideline grounding.

### Step 2: Ground in Guidelines + the Patient Record

The conceptual point is strong: a guideline-correct answer can still be wrong for this patient. This is one of the strongest teaching moments in the dataset.

The diagram currently drops the `phi-ehr` link because `PHIScope` is not visible. Add `PHIScope` here or create a direct visible retrieval link. Also consider naming guideline versions, formularies, drug-interaction data, and patient-fact snapshots in the description or schema.

### Step 3: Calibration & Abstention

The abstention framing is excellent. Treating "I cannot determine this" as a successful output is the right interview lesson.

The improvement is precision. Explain what "confidence" means here: retrieval sufficiency, contradiction checks, calibrated score, out-of-distribution signal, or task-specific risk threshold. Make clear that a model self-score alone is not sufficient.

### Step 4: The Deterministic Safety Layer

This step lands well because it separates probabilistic reasoning from hard clinical checks. The trap is specific and useful.

The step should show what the safety layer consumes and returns: patient facts, rules/formulary versions, pass/block/warn, missing-data fail-closed behavior, and override policy. For example, a contraindication block and a missing-lab abstention are different operational outcomes.

### Step 5: The Gate: Clinician Sign-off

This is the crux of the case and the sequence flow is a good start. It correctly binds authorization to a clinician principal before an EHR write.

The flow needs more production states. Add reject, modify, request-more-evidence, expired, and EHR-write-failed paths. Also add the review surface or worklist as an explicit component; otherwise the "human in the loop" is architecturally thin.

### Step 6: PHI Scoping, Confidentiality & the Safety Case

The text names the right concerns: care-team scoping, HIPAA/BAA, no-train, untrusted note text, and SaMD/FDA framing.

The diagram does not currently show the pipeline connections because `Pipeline` is omitted from the view. Add it. This step should also distinguish access audit from recommendation audit, because PHI access itself is regulated and auditable even when no recommendation is authorized.

### Step 7: Workflows & Safety Evaluation

The metric direction is correct: confident-wrong rate, abstention precision/recall, calibration, and harm avoidance matter more than average accuracy.

This step should include monitoring and governance loops: drift detection, per-specialty/per-task evaluation slices, incident review, threshold changes, model/version rollout, and post-deployment surveillance. If LLM-as-judge remains a pattern, qualify it as an auxiliary evaluator, not the source of truth for clinical safety.

## Final Design Review

The final design integrates the main components and repeats the right invariant: the system recommends, while the clinician decides. It includes the gateway, pipeline, reasoning agent, inference backend, guidelines, EHR, calibrator, deterministic safety layer, abstain/sign-off gate, recommendation store, PHI scope, guardrail, identity, audit log, and observability.

Two issues remain. First, `Patient` is included in the final view but has no high-level architecture link, so it will render as an isolated node. Either connect it to the clinical context/EHR boundary or omit it from the final diagram. Second, the final design has no explicit queue/worklist/admission-control path despite the pattern list mentioning load leveling.

## Concept Introduction and Learning Flow

The concepts are introduced just in time: agent harness in the baseline, patient-specific grounding, abstain-don't-guess, deterministic safety, decision support, safety case, and harm-avoidance eval. This sequencing works.

The main pedagogical weakness is the absence of options. Every step has a single path, so the candidate is not asked to choose between realistic alternatives. Add options around fail-open vs fail-closed, direct EHR action vs recommend-only, single global threshold vs risk-tiered thresholds, model self-score vs calibrated evaluator, synchronous request vs queued review workflow, and full chart retrieval vs minimum-necessary retrieval.

## Step-to-Final-Design Coherence

Most components in the final design are introduced by the steps. The best transitions are grounding -> calibration -> safety -> gate; each step solves the risk exposed by the previous recap.

The weaker transitions are operations-oriented. `RecStore`, `AuditLog`, `Identity`, and `Observability` appear in the architecture, but the steps do not deeply teach their operational contracts. The final design says they exist, but the interview does not yet make candidates design their schemas, retention rules, failure behavior, or ownership boundaries.

The `satisfies.functional[0]` mapping points to `naive` and `eval` for "Answer decision-support queries". Since `naive` is explicitly the unsafe baseline, it should not be credited as satisfying the requirement. Map that requirement to the safe pipeline steps instead.

## Realism Compared With Production Systems

The production realism is strongest around safety posture and weakest around integration and operations. Real healthcare systems need EHR rate-limit handling, FHIR/HL7 integration boundaries, retry/idempotency around writes, explicit no-autonomous-order enforcement, access audit, minimum-necessary retrieval, data retention policy, and incident/change-control procedures.

The case should also address stale or incomplete patient data. A model may have a grounded answer, but if the medication list or allergy data is stale, the correct action may be abstain or request review. That is a healthcare-specific failure mode worth adding.

The sign-off workflow should account for clinician workload. A safe system can still fail operationally if it creates too many low-value recommendations, alerts, or abstention reviews. Include queue depth, prioritization, and alert-fatigue metrics.

## Dataset and Renderer-Facing Observations

The JSON parses cleanly. Top-level architecture nodes use canonical node types, and step IDs referenced by patterns and `satisfies` resolve.

Several selected links are filtered out because endpoint nodes are absent from the step view, as listed above. Fix these before relying on browser screenshots or generated docs.

`Request` is typed as `client`, but it represents a clinical query rather than a software client surface. If the diagram needs a client node, consider `Clinician Portal`, `EHR App`, or `Clinical UI`; otherwise model the query as a label/edge rather than a node.

The dataset has no `technologyChoices`, `probeLinks`, AI visuals, or explainer comic. Those are optional, but for a flagship healthcare case, technology choices could be valuable: EHR integration, vector/indexing strategy, model hosting under BAA/no-train terms, audit-log storage, policy/rule engine, and observability/eval stack.

## Recommended Edits, Prioritized

### P1: Expand API and data model for a reproducible safety case

Add request context, clinician/tenant/care-team identity, idempotency, evidence snapshots, guideline/rule/model versions, calibrated confidence details, abstention reasons, safety-check details, sign-off decisions, and EHR write outcomes.

### P1: Replace qualitative capacity with real sizing and operational limits

Add traffic estimates, EHR fanout, model latency/cost, queue/worklist depth, p95 targets, rate limits, and backpressure/admission-control behavior.

### P1: Fix step diagram link endpoints

Add missing nodes or remove invalid links in `naive`, `grounding`, `privacy`, and `eval`. Recheck the final design for the isolated `Patient` node.

### P2: Model the clinician review workflow as a state machine

Include pending, abstained, blocked, modified, authorized, rejected, expired, and EHR-write-failed states. Add a worklist/review UI node or clarify that `RecStore` backs it.

### P2: Make calibration and safety checks concrete

Define what the calibrator scores, how thresholds vary by task/risk, how rule sources are versioned, and how missing/stale chart facts fail closed.

### P2: Add options to teach trade-offs

Add at least two or three options across the case. Good candidates are synchronous vs queued review, single global threshold vs risk-tiered thresholds, model self-score vs calibrated evaluator, and recommend-only vs direct EHR write.

### P3: Tune mappings and optional book features

Remove `naive` from the satisfied requirement mapping, either add queue/admission-control architecture or remove that pattern, and consider adding `technologyChoices` for healthcare-specific implementation decisions.

## What Not To Change

Keep the central invariant: nothing acts on a patient autonomously. That is the strongest part of the case.

Keep abstention as a successful safe output. It is the right differentiator from lower-stakes agentic domains.

Keep the deterministic safety layer outside the model. The interview should not imply that prompt instructions or model memory can enforce life-critical rules.

Keep the step order. The progression from naive answer to grounded, calibrated, safety-checked, clinician-authorized recommendation is pedagogically sound.

## Bottom Line

This is a strong healthcare agentic-platform case with a clear safety thesis and a coherent teaching arc. The next revision should make the operational substrate as concrete as the safety language: richer API/schema, real capacity math, explicit clinician workflow states, and corrected step diagrams.
