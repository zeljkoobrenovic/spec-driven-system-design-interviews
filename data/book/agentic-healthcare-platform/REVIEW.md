# Review: Agentic Healthcare Platform - System Design

Reviewed file: `data/book/agentic-healthcare-platform/interview.json`
Review date: 2026-06-25

## Executive Summary

The recent revision materially improved this case. The earlier gaps around API
context, reproducible safety-case storage, capacity sizing, clinician worklist
states, options, technology choices, and broken step-diagram links have mostly
been addressed. The interview now reads like a credible high-stakes clinical
decision-support platform rather than a generic agentic workflow with healthcare
terms layered on top.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5 | Strong safety boundary, richer API/schema, task/risk-tier thresholds, deterministic checks, and clinician sign-off. Remaining gaps are mostly operational contracts. |
| Production realism | 4 | Much better EHR, PHI, worklist, BAA/no-train, audit, and SaMD framing; still needs sharper concurrency, retry, retention, and incident/change-control detail. |
| Pedagogical flow | 4.5 | The naive-to-safe progression is clear, and the new trade-off options improve the interview. Option labels and a few operations transitions could teach more explicitly. |
| Dataset/rendering fit | 4.5 | Structural references now resolve cleanly. One visible node is isolated in the privacy step, and option tabs would benefit from explicit titles. |
| Overall | 4.5 | Strong and usable. The next pass should refine production edge cases, not rework the core design. |

## What Works Well

The review's biggest former concerns were addressed. `POST /v1/recommendations`
now carries idempotency, tenant, clinician, patient, encounter, care-team,
task-type, risk-tier, urgency, and consent context. The data model now has a
first-class `recommendation_case` plus evidence, model-run, calibration,
safety-check, sign-off, and audit records, which supports the promised safety
case.

Capacity is now concrete enough to discuss. It gives clinician count, daily
queries, peak QPS, EHR fanout, guideline latency, interactive p95 latency,
inference budget, worklist age, EHR write limits, and backpressure. That is a
large improvement over treating safety invariants as "capacity".

The clinician gate is now a real workflow. `RecStore`, `Worklist`, explicit case
states, modify/reject/request-evidence paths, expiry, and `ehr_write_failed`
make the human-in-the-loop design operational instead of a single approval
button.

The safety teaching is strong. The case distinguishes model reasoning from
grounding sufficiency, calibrated uncertainty, risk-tier thresholds, and hard
deterministic checks. It also correctly treats missing or stale chart facts as a
reason to abstain or escalate, not as a pass.

The dataset now includes useful `technologyChoices` for EHR integration,
guideline indexing, model hosting under BAA/no-train terms, deterministic rule
engines, audit storage, and eval/observability. Those choices are practical and
well tied to the relevant steps.

## Highest-Impact Issues

### 1. State transitions and concurrent review semantics need one more level of detail

The current model has the right states, but it mostly stores the current state.
Production review workflows need transition history and concurrency control:
which clinician claimed or opened the case, what version they reviewed, whether
two clinicians raced to decide, whether a case was reassigned or escalated, and
which transition emitted which audit event.

The sign-off endpoint mentions idempotence on `caseVersion`, but the request has
no explicit sign-off idempotency key or transition/correlation id. For EHR
writes, this matters: the platform must distinguish "clinician clicked twice",
"request retried after timeout", "EHR accepted but response was lost", and "EHR
rejected the write".

Concrete fix: add a `case_transition` or `decision_event` record with
`from_status`, `to_status`, `actor_id`, `case_version`, `transition_id`,
`idempotency_key`, `reason`, and timestamp. Add worklist claim/assignment fields
or explain why the product uses optimistic review without claims.

### 2. EHR integration is named well but still underspecified at the failure boundary

The revised capacity and technology choices correctly mention FHIR/HL7, EHR
rate limits, and idempotent retry. The architecture still compresses the hard
part into `Identity -> EHR`. In real integrations, the risky details are write
semantics, partial success, downstream validation, order/note/message schemas,
FHIR resource versions, patient/encounter mismatch, and reconciliation when the
EHR state changes between recommendation and sign-off.

Concrete fix: add a short note in the gate or technology section on EHR write
contracts: compare-and-set or resource-version checks, per-action schemas,
write correlation ids, retry policy, reconciliation after unknown outcome, and
what happens when the chart changed after the recommendation was drafted.

### 3. PHI access policy is directionally strong but not yet fully operational

The privacy step now distinguishes PHI-access audit from recommendation audit,
which is exactly right. The remaining gap is policy detail. `consent.breakGlass`
appears in the API, but the dataset does not explain who may break glass, what
extra audit or attestation it creates, how minimum-necessary fields are selected
per task, how access is revoked when the clinician leaves the care team, or what
retention/deletion policy applies to raw model traces and evidence bundles.

Concrete fix: add a privacy sub-point or deep dive covering care-team
membership freshness, break-glass workflow, minimum-necessary field policy,
retention tiers, and separation of raw PHI traces from derived safety-case
records.

### 4. Option titles are missing, which weakens trade-off teaching in the UI

Steps 3, 4, and 5 now have meaningful two-option trade-offs, but every option's
`title` is `null`. The renderer will fall back to generic option labels, so the
candidate sees "Option 1" and "Option 2" rather than the actual decision being
made.

Concrete fix: title the options, for example:

- Step 3: "Risk-tiered calibrated evaluator" vs "Single model self-score".
- Step 4: "Fail closed on missing facts" vs "Treat missing facts as pass".
- Step 5: "Recommend-only clinician sign-off" vs "Autonomous low-risk writes".

### 5. One privacy-step diagram node is isolated

Structural checks now pass: step nodes resolve, selected links resolve, link
endpoints are visible, `satisfies` steps resolve, and pattern/technology-choice
step references resolve. The remaining rendering issue is smaller: the privacy
step includes `Identity` in `view.nodes`, but none of that step's selected links
touch `Identity`, so it will render as an isolated node while the text discusses
identity-scoped retrieval.

Concrete fix: either remove `Identity` from that view, or add a visible identity
relationship such as clinician-to-identity authorization or identity-to-PHI
scope. If the intent is to show access enforcement, the diagram should connect
`Identity` to `PHIScope` or the clinical API boundary.

## System Design Soundness

The requirements now cover the domain well: decision-support queries, grounding
in guidelines and chart data, deterministic safety checks, abstention, clinician
authorization, and task/risk-tier-specific behavior. The non-functional
requirements keep the safety invariant front and center: abstain by default,
protect PHI, enforce hard rules outside the model, document a safety case, and
audit sources, confidence, safety checks, abstentions, and decisions.

The API is much stronger than the previous version. It carries the context the
architecture later needs, and the worklist and safety-case record endpoints make
the human review and audit surfaces explicit. The main API improvement would be
to make sign-off retries and worklist pagination/claiming more explicit.

The data model now supports reproducibility. Evidence versions, citation spans,
patient facts used, model/prompt/tool versions, calibration scores, safety-rule
versions, sign-off decisions, EHR write status, and separate PHI/recommendation
audit categories all fit the safety-case story. The next refinement is event
history: do not rely only on the current status enum plus append-only generic
audit payloads for the state machine.

The architecture has the right boundary: the agent recommends, deterministic
services gate, and a clinician decides. The final design includes the components
introduced by the steps, including the new Worklist and Patient link. It should
avoid implying that the EHR write path is simple; that path is where many
production failures happen.

## Step-by-Step Pedagogical Review

### Step 1: Naive: An Agent That Answers Clinical Questions

This is now a clean baseline. The diagram correctly shows clinician -> agent ->
inference without chart grounding or EHR writes. The harm framing is specific
and the agent-harness concept ties the case back to Foundations.

Potential improvement: briefly name which tasks are deliberately unsafe in this
baseline, such as dosing and differential diagnosis, because the rest of the
case later uses task/risk tiers.

### Step 2: Ground in Guidelines + the Patient Record

This step is much stronger after adding `PHIScope` and stale/incomplete snapshot
language. It now teaches that the right guideline can still be wrong for this
patient and that missing chart facts should trigger abstention or review.

Potential improvement: mention resource freshness or chart-version checks as an
input to later sign-off. If the chart changes after the recommendation is
drafted, the system should revalidate before write.

### Step 3: Calibration & Abstention

This is one of the strongest steps. It correctly rejects model self-score as
sufficient, separates grounding sufficiency from calibrated uncertainty, and
uses task/risk-tier thresholds. The option trade-off is realistic.

Potential improvement: give the options titles so the UI teaches the decision
without requiring the user to read the pros/cons first.

### Step 4: The Deterministic Safety Layer

The fail-closed framing is strong and practical. The step now distinguishes
`pass`, `block`, `warn`, and `missing_data`, and records rule/formulary versions.
That is exactly the line a high-stakes agentic design should draw.

Potential improvement: name ownership/update workflow for rule content. Clinical
rule updates are not just deployments; they need review, versioning, rollback,
and sometimes urgent release.

### Step 5: The Gate: Clinician Sign-off

The revision fixed the biggest previous weakness. The worklist, state machine,
modify/reject/request-evidence paths, expiry, EHR write failure, and alert
fatigue metrics make the gate credible.

Potential improvement: specify concurrent review and assignment semantics. The
case should say whether clinicians claim work, whether cases are assigned by
care team, and how stale case versions are rejected at sign-off.

### Step 6: PHI Scoping, Confidentiality & the Safety Case

This step now makes a valuable distinction between PHI access audit and
recommendation audit. It also correctly treats notes and records as untrusted
input and names HIPAA/BAA/no-train and SaMD/FDA framing.

Potential improvement: connect `Identity` in the diagram or remove it from this
view. Also add break-glass/minimum-necessary/retention details, because those
are the operational heart of healthcare privacy.

### Step 7: Workflows & Safety Evaluation

The eval step is strong. It prioritizes confident-wrong rate, calibration,
abstention quality, harm avoidance, per-task/per-specialty slices, drift,
incident review, staged rollout, and clinician adjudication over LLM-as-judge.

Potential improvement: add one operational metric for worklist health here, such
as queue-age p95 by urgency/risk tier, override/reject rate, or rubber-stamp
rate, so the eval loop covers the human gate as well as the model.

## Final Design Review

The final design now coherently integrates the full story: clinical query,
gateway, deterministic pipeline, reasoning agent, inference, guideline index,
PHI-scoped EHR retrieval, calibration, deterministic safety, abstain/sign-off
gate, recommendation store, worklist, identity, EHR write, audit, and
observability. The Patient node is now connected to EHR, fixing the previous
isolated-node concern.

The final design's strongest property is that it keeps the model inside a
bounded decision-support pipeline. It does not imply autonomous clinical action,
and it places deterministic safety and clinician authority outside the model.

The remaining final-design gap is operational depth around EHR writes and review
state transitions. That does not require adding many new boxes; a few sharper
contracts in the API/data model/step text would be enough.

## Concept Introduction and Learning Flow

Concept staging is now excellent: unsafe direct answer, patient-specific
grounding, abstain-don't-guess, deterministic safety, decision support rather
than decision, review worklist as state machine, safety case, and harm-avoidance
eval. The concepts are introduced when the candidate needs them.

The new options improve the teaching flow because they compare real choices:
risk-tiered calibration vs one self-score, fail-closed vs treating missing facts
as safe, and recommend-only sign-off vs autonomous low-risk writes. Add option
titles and this will land much better in the rendered explorer.

## Step-to-Final-Design Coherence

Coherence is high. Almost every final-design node is introduced by the steps,
and the transitions solve the previous risk: generic answer -> grounded answer
-> calibrated abstention -> deterministic safety -> clinician gate -> privacy
and audit -> continuous eval.

The only weak transition is from privacy/identity policy to the actual
authorization and EHR write boundary. Identity is discussed in multiple places,
but the operational contract among clinician principal, PHI retrieval scope,
break-glass access, and signed EHR writes is still partly implicit.

## Realism Compared With Production Systems

The case is now much closer to production reality. It names EHR fanout, EHR rate
limits, BAA/no-train model hosting, FHIR/HL7 technology choices, licensed rule
content, WORM audit storage, clinician-labeled ground truth, drift detection,
incident review, and alert fatigue.

The remaining realism gaps are about the edges where production systems fail:
unknown EHR write outcomes, stale chart versions, concurrent clinician actions,
care-team membership changes, break-glass access, raw PHI trace retention,
clinical rule updates, and post-incident threshold/model rollback. These can be
covered with targeted text rather than a major redesign.

## Dataset and Renderer-Facing Observations

JSON parsing succeeds. Step IDs referenced by `satisfies`, `patterns`, and
`technologyChoices` resolve. Step view nodes and links resolve. Selected step
links have visible endpoints, so the former issue where key links disappeared
at render time is fixed.

`highLevelArchitecture.types` defines the groups used by step and final views,
so group references are valid. The final view includes all major components and
no longer leaves `Patient` isolated.

Remaining fit issues are minor:

- `steps[privacy].view.nodes` includes `Identity`, but no selected link touches
  it, so it will render isolated.
- Options in steps 3, 4, and 5 have `title: null`; the UI will use generic
  labels instead of meaningful trade-off names.
- `Request` is typed as `client`, but it represents a clinical query rather
  than an actual software client. This is acceptable if intentional, though a
  `Clinical UI` or `EHR App` client node would be more literal.

## Recommended Edits, Prioritized

### P1: Add explicit review-state transition and sign-off idempotency detail

Add a transition/event record or fields that show case version, actor, from/to
state, assignment/claim, transition id, sign-off idempotency key, and retry
correlation. Clarify how stale case versions and concurrent review are handled.

### P1: Sharpen EHR write contracts

Describe resource-version checks, per-action schemas, retry/unknown-outcome
handling, correlation ids, and revalidation when chart state changes after the
recommendation was drafted.

### P2: Operationalize PHI policy

Add break-glass workflow, minimum-necessary field selection, care-team
membership freshness, revocation behavior, and retention separation for raw PHI
traces vs safety-case records.

### P2: Title the step options

Give each option a short title so the rendered tabs teach the trade-off:
risk-tiered calibrated evaluator, single model self-score, fail closed on
missing facts, treat missing facts as pass, recommend-only clinician sign-off,
and autonomous low-risk writes.

### P3: Fix the privacy diagram's isolated Identity node

Either remove `Identity` from that step view or add a visible relationship that
shows how identity controls PHI-scoped retrieval or clinician authorization.

### P3: Add one human-gate metric to the eval step

Include queue-age p95 by risk tier, reject/modify rate, override rate,
rubber-stamp rate, or time-to-review so the evaluation loop measures clinician
workflow health, not only model safety.

## What Not To Change

Keep the central invariant: nothing acts on a patient autonomously.

Keep abstention as a successful safe output. That is the case's clearest
teaching point and the right differentiator from lower-stakes agentic domains.

Keep deterministic safety outside the model. Contraindications, interactions,
allergies, dose limits, and missing required facts should never rely on prompt
compliance or model memory.

Keep the step order. The sequence from naive answer to grounded, calibrated,
safety-checked, clinician-authorized recommendation is coherent and teaches one
risk at a time.

## Bottom Line

This is now a strong healthcare agentic-platform interview. The major design
deficiencies called out in the previous review have been fixed. The remaining
work is refinement: make the review state machine and EHR write boundary more
explicit, operationalize PHI policy, title the options, and clean up one small
diagram issue.
