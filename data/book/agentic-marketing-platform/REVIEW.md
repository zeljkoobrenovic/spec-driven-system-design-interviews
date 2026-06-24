# Review: Agentic Marketing Platform - System Design

Reviewed file: `data/book/agentic-marketing-platform/interview.json`
Review date: 2026-06-24

## Executive Summary

This is a coherent and memorable agentic marketing case. The core teaching idea is strong: the dangerous action is not moving money or filing legal work, but publishing under the brand's name. The walkthrough correctly centers brand grounding, a deterministic claim gate, C2PA provenance, risk-tiered approval, channel compliance, and a generate -> serve -> measure -> reallocate loop.

The current dataset is a strong skeleton, but it is not yet production-deep. Capacity is qualitative, the API and data model are too small for the workflow promised by the architecture, the bandit loop is under-specified, and compliance/consent state is mostly named rather than designed. The biggest renderer-facing problem is that several step views reference links whose endpoints are hidden in that step, so Mermaid may create implicit nodes or render confusing diagrams.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 3.5/5 | Correct major components and risk boundary; missing state, workflow, and scaling detail. |
| Production realism | 3/5 | Good instincts around brand safety and compliance; thin on provider callbacks, consent, idempotency, queues, attribution, and operations. |
| Pedagogical flow | 3.5/5 | Clear baseline -> grounding -> gate -> optimization -> compliance -> eval arc, but almost no decision branches. |
| Dataset/rendering fit | 3/5 | JSON and references parse, but several step diagrams include links with hidden endpoint nodes. |
| Overall | 3.5/5 | A good vertical concept that needs production state and richer interview trade-offs to become a flagship book case. |

## What Works Well

- The domain risk is crisp: public brand damage from off-brand, prohibited, or undisclosed synthetic content.
- The naive baseline works because it makes auto-publishing visibly unsafe before adding controls.
- The brand kit / DAM is the right marketing-specific grounding source, and it is scoped per tenant.
- The claim gate is correctly outside the model. The model can draft, but deterministic policy decides what can publish.
- The bandit loop is a good marketing-specific value driver, and the dataset correctly says regenerated variants must re-enter the gate.
- C2PA provenance is introduced as a concrete vertical requirement instead of a generic "audit" phrase.
- The final design integrates grounding, review, approval, activation, personalization, analytics, optimization, audit, and evaluation in a compact way.

## Highest-Impact Issues

### 1. Capacity is qualitative, so it does not drive architecture

The `capacity` section has useful labels, but no numbers. It says asset fan-out is "many per brief", approval is "risk-tiered", and optimization is "live". That does not tell a candidate what must be queued, cached, throttled, or stored.

Why it matters: this system's hard constraints are generated variants per campaign, model/image-generation cost, channel-provider rate limits, approval latency, event volume, attribution delay, and bandit decision cadence. Without sizing, the architecture can mention batch generation and live optimization without proving that it can survive bursts or avoid runaway spend.

Concrete fix: add interview-scale assumptions and derived workloads:

- tenants, campaigns/day, channels/campaign, and variants/channel
- assets generated per brief and regenerated per optimization cycle
- expected LLM/image calls, token/image cost, and max concurrent generation jobs
- approval queue volume and high-risk percentage
- channel delivery rate limits and provider callback volume
- impressions/click/conversion event rate feeding analytics
- bandit decision interval and budget-reallocation frequency
- audit/event retention size and query pattern

### 2. The API and data model cannot support the promised workflow

The API has only create campaign, approve campaign, and get performance. The data model has only `assets`, `variants`, and `audit_record`. That is enough to explain the idea, but not enough to implement risk-tiered approval, compliance, channel delivery, provenance, and optimization.

Missing state includes:

- `campaigns` with tenant, goal, budget, schedule, locale/region, status, and idempotency key
- brand-kit and negative-claim library versions used for generation and review
- generated asset versions with prompt/model provenance, risk tier, reviewer version, and approval snapshot
- claim-check results as first-class evidence, not just `claim_status`
- approval decisions with approver identity, asset version, timestamp, comments, and expiry/revocation behavior
- channel deliveries with provider id, status, retry count, failure reason, template approval, and webhook dedupe key
- consent, suppression, unsubscribe, and preference records by tenant/channel/region
- performance events and attribution windows, not only aggregate counters on `variants`
- bandit decisions with policy constraints, budget allocation, exploration rate, and decision timestamp

Concrete fix: expand `dataModel` so each required behavior has durable state. Then map those entities to steps and `satisfies`.

### 3. The publish lifecycle needs an explicit state machine and idempotency story

The current lifecycle jumps from generated asset to `awaiting_approval` to `live` or `returned`. The asset status enum is `draft,awaiting_approval,live,rejected`. It does not model queued generation, claim review, approval snapshots, scheduled activation, provider submission, partial channel failure, pause, rollback, superseded variants, or expired approvals.

Why it matters: the dangerous bugs are race conditions:

- an asset is approved, then the negative-claim library changes before publish
- a user opts out after approval but before channel activation
- the approve request is retried
- an ad/email/social provider accepts a publish request after timing out
- a callback arrives twice or out of order
- the bandit reallocates budget to an asset that has since been paused or revoked

Concrete fix: add a step, flow, or deep dive for the publish state machine. Use idempotency keys for create/approve/publish, persist immutable asset versions, re-check compliance immediately before activation, and dedupe provider callbacks into append-only events.

### 4. Channel compliance and consent are named but not designed

The requirements mention CAN-SPAM, TCPA, GDPR, template approval, tenant isolation, and untrusted text. Step 5 says compliance rules live at activation. That is directionally correct, but the dataset does not model the data or control points needed to enforce those rules.

Why it matters: marketing compliance is per tenant, region, channel, audience, campaign purpose, and provider. "Compliant" is not a single boolean. A customer may consent to email but not SMS, a region may require different disclosure text, an ad platform may require approved templates, and deletion/DSR workflows may conflict with audit retention.

Concrete fix: add consent/preference/suppression entities, channel-policy versions, regional policy selection, template approval status, and retention/deletion behavior. Make the activation path perform a final policy check using those records before provider submission.

### 5. The bandit loop is under-specified as a safety-critical control loop

The dataset correctly says the bandit reallocates budget and regenerated variants re-enter the gate. It does not define the inputs, constraints, attribution model, or rollback behavior.

Why it matters: a naive bandit can optimize into borderline claims, misleading copy, audience fatigue, unfair treatment of segments, or spend spikes. Brand safety needs to be a hard constraint, not just another metric in the dashboard.

Concrete fix: make the bandit own constrained decisions:

- eligible variants are only those with current cleared status and valid approval
- brand-safety and compliance failures remove arms from allocation
- budget, frequency caps, audience caps, and channel policies bound exploration
- delayed conversions use explicit attribution windows
- decision events are auditable and reversible
- cold-start and low-traffic behavior is named

### 6. The pedagogy lacks real decision branches

All six steps have zero `options`. The story is clean, but candidates are mostly handed the final answer instead of being asked to compare trade-offs.

Good option branches to add:

- brand grounding: raw prompt context vs indexed brand kit vs versioned retrieval with citation/evidence
- claim gate: model-only check vs deterministic rules plus model judge vs external legal review queue
- activation: direct channel publish vs channel-adapter layer with final policy recheck
- optimization: fixed A/B testing vs unconstrained bandit vs policy-constrained contextual bandit
- approval: campaign-level approval vs asset-version approval vs reusable policy approval for low-risk variants
- performance ingestion: synchronous polling vs provider webhooks plus event stream

### 7. Several step diagrams reference links whose endpoints are hidden

The link IDs resolve globally, but the visible step node lists omit one endpoint for several links:

- `naive`: `id-channels` references `Identity -> Channels`, but `Identity` is not in the view.
- `grounding`: `orch-guard` references `Orchestrator -> Guardrail`, but `Orchestrator` is not in the view.
- `brand-gate`: `gen-prov` references `GenAgent -> Provenance`, but `GenAgent` is not in the view.
- `compliance`: `id-channels` references `Identity -> Channels`, but `Identity` is not in the view.
- `eval`: `channels-analytics` references `Channels -> Analytics`, but `Channels` is not in the view.

Why it matters: the renderer may create implicit nodes or show links whose source is not part of the intended incremental reveal. That undermines the teaching walkthrough.

Concrete fix: either add the missing endpoint nodes to each `view.nodes` list or replace those links with step-local links whose endpoints are visible.

## System Design Soundness

The architecture has the right major components: API gateway, orchestrator, content agent, inference backend, brand kit / DAM, claim reviewer, provenance service, asset store, activation channels, CDP, analytics stream, bandit optimizer, compliance guardrail, identity/token broker, audit log, and observability. The central risk boundary is well placed at the claim/compliance gate rather than inside the LLM prompt.

The weak point is durable state. The final design promises approval, provenance, compliance, delivery, audit, and optimization, but the data model only captures a small slice of that. A production answer needs explicit state transitions and immutable evidence for every publish decision.

The capacity section should drive queueing and cost decisions. The high-level architecture even has an `orch-queue` link labelled "batch generation", and the pattern list includes "Queue-based load leveling; admission control", but there is no queue node, queue state, or admission policy in the walkthrough. If bursty campaign generation is in scope, add a task queue and worker/admission-control story.

The brand/claim gate is directionally right, but the wording should distinguish deterministic checks from subjective checks. Prohibited claims, required disclosures, blocked phrases, and template rules can be deterministic. Brand-voice conformance is usually heuristic or model-judged and should have thresholds, evidence, false-positive handling, and escalation.

The C2PA story is useful but shallow. The dataset should say what is signed, where the manifest is stored, whether transformed media preserves provenance, and what happens when a channel strips metadata.

## Step-by-Step Pedagogical Review

### Step 1: Naive: An Agent That Generates and Publishes

This is an effective baseline. It immediately exposes the public-brand-risk failure mode and motivates the rest of the interview.

Improvement: the diagram uses `id-channels`, which introduces `Identity` implicitly even though the baseline is supposed to be unsafe direct publishing. Use a direct unsafe publish link, or include `Identity` and explain that credentials exist but no policy gate exists.

### Step 2: Ground in the Brand Kit / DAM

This step introduces the right marketing corpus: voice, style, approved assets, and negative claims. It also correctly mentions tenant scoping.

Improvement: add versioning and retrieval semantics. A candidate should know whether the asset was generated against brand-kit version N, whether approved assets are retrieved by channel/locale/audience, and how a changed negative-claim library affects pending assets.

### Step 3: The Gate: Brand & Claim Review + C2PA Provenance

This is the strongest conceptual step. The gate is the right crux for the case, and the high-risk vs low-risk flow is useful.

Improvements: separate claim review, brand-voice review, provenance stamping, approval, and activation into clearer persisted events. The sequence flow currently has `ClaimGate` or `Marketer` activating directly to `Channels`, which hides the orchestrator/identity/channel-adapter path that should enforce final compliance and idempotency.

### Step 4: The Optimization Loop: Bandits Over Variants

The loop is the distinctive marketing-platform capability. Requiring regenerated variants to pass through the gate is the right safety invariant.

Improvement: add the policy-constrained nature of the bandit. It should allocate only among eligible, currently cleared variants; log each decision; respect budget and frequency caps; and stop or quarantine arms when brand-safety metrics regress.

### Step 5: Channel Compliance, Personalization & Audit

This step brings in the right concerns: opt-out, consent, GDPR, CDP data, untrusted input, and append-only audit.

Improvement: this step is too compressed. Channel compliance, personalization, prompt-injection isolation, and audit could each carry important state. Add a flow showing activation: fetch audience/preferences, evaluate channel policy, re-check approval, submit to provider, receive webhook, write audit event.

### Step 6: Brand-Safety & Performance Evaluation

The step correctly says conversion metrics are insufficient and that claim-violation/off-brand rates must be measured.

Improvement: distinguish monitoring from release gates. A model, prompt, reviewer, retrieval strategy, or brand-kit update should not roll out if offline or shadow eval increases claim-violation or off-brand rates beyond a threshold.

## Final Design Review

The final design description is concise and coherent. It integrates the major components from the walkthrough and makes the central invariant clear: every new variant re-enters the claim gate before publishing.

The final design currently looks more complete than the supporting API and data model. It promises tenant isolation, delegated identity, channel compliance, CDP personalization, provenance, audit, analytics, and optimization, but most of those are not represented as durable entities or flows.

The final diagram includes all endpoint nodes for its links, which is good. The step diagrams need the same endpoint-completeness cleanup.

## Concept Introduction and Learning Flow

The concept sequence is sensible:

- unsafe auto-publish baseline
- brand grounding
- brand/claim/provenance gate
- optimization loop
- channel compliance and audit
- brand-safety and performance evaluation

The missing teaching concept is "publish attempt lifecycle." It should appear before or during the gate step because it connects approval, consent, final compliance recheck, provider submission, callbacks, audit, and rollback.

The patterns are relevant to the broader agentic-platform series, but several are tagged more than taught. "Delegation not impersonation" should include scoped OAuth/token exchange semantics. "Prompt-injection defense" should include an example of untrusted brief or scraped content being isolated from channel authority. "Queue-based load leveling" should be backed by an actual queue/admission-control component.

## Step-to-Final-Design Coherence

The progression mostly builds toward the final design:

- Step 1 exposes the publish risk.
- Step 2 adds brand grounding.
- Step 3 adds review, provenance, approval, and asset state.
- Step 4 adds analytics and the bandit.
- Step 5 adds channel policy, CDP personalization, and audit.
- Step 6 adds eval and observability.

The main coherence issue is that some diagrams borrow final-design links before the relevant endpoint nodes are introduced. Fixing those step views will make the incremental reveal cleaner.

The final design also includes `Brief` and `Gateway`, but those appear mostly in the API section rather than the step sequence. That is acceptable, though Step 1 or Step 2 could show ingress explicitly if the dataset wants a more complete start-to-finish journey.

## Realism Compared With Production Systems

A production marketing automation platform would need more explicit handling for:

- provider outages, partial activation, and retry/backoff by channel
- ad/email/social provider rate limits and callback deduplication
- consent, suppression, unsubscribe, and preference propagation
- per-tenant data isolation and deletion/retention policy
- campaign budget pacing, frequency caps, audience exclusions, and ad fatigue
- attribution windows and delayed conversion events
- asset/version approval snapshots and rollback to prior approved versions
- negative-claim library updates that invalidate pending/live assets
- channel metadata stripping C2PA provenance
- emergency pause/kill switch for a bad campaign or broken reviewer
- operator dashboards for approval backlog, blocked assets, spend, and violation rates

Not all of these need full implementation detail, but the interview should deliberately scope the most important ones in or out.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Top-level keys are conventional for this repo: requirements, capacity, API, data model, patterns, steps, final design, satisfies, script, level variants, and follow-ups.
- All `view.nodes` references resolve to declared high-level architecture nodes.
- All `view.links` references resolve to declared high-level architecture links.
- All `satisfies[*].steps[*]` references resolve to real step IDs.
- All `patterns[*].steps[*]` references resolve to real step IDs.
- The final design view includes both endpoints for every displayed link.
- Several step views display links whose endpoint nodes are hidden; fix these before relying on the generated diagrams.
- Sequence flow participants resolve for the Step 3 flow.
- Every step has zero `options`. This is schema-valid but pedagogically thin for a book case.
- Only one step has a sequence flow, and only one step has a deep dive. That is sparse for a workflow with approval, provider callbacks, consent, and optimization loops.
- `technologyChoices`, `toProbeFurther`, AI visuals, and an explainer comic are absent. That is valid, but the neighboring agentic book cases increasingly use those fields for polish and external grounding.

## Recommended Edits, Prioritized

### P1: Fix step diagram endpoint completeness

Update the `view.nodes` or `view.links` for `naive`, `grounding`, `brand-gate`, `compliance`, and `eval` so every displayed link has both endpoint nodes visible.

### P1: Add concrete capacity and workload math

Replace qualitative capacity labels with example assumptions and derived throughput for generation, approval, delivery, event ingestion, optimization decisions, and audit retention.

### P1: Expand the data model around campaign, asset, approval, delivery, consent, event, and bandit state

The current three tables do not support the final design's operational claims. Add durable records for workflow state and evidence.

### P1: Add a publish-attempt state machine

Model idempotent create/approve/publish, immutable asset versions, final policy recheck, provider submission, callback dedupe, retry behavior, pause/rollback, and terminal failures.

### P2: Make channel compliance concrete

Add consent/preference/suppression data, regional/channel policy versions, template approval, and final activation checks. Clarify how GDPR deletion and audit retention coexist.

### P2: Constrain the bandit explicitly

Make brand safety and compliance hard eligibility gates for allocation. Add attribution windows, cold-start handling, budget/frequency caps, and auditable decision events.

### P2: Add option branches

Add at least three options across grounding, gate, activation, and optimization so candidates compare real alternatives instead of reading a single path.

### P3: Add more flows, traps, and deep dives

Good additions: approval race trap, C2PA metadata stripping trap, "brand voice judge is not deterministic" trap, provider timeout/idempotency flow, consent update during queued activation flow, and emergency campaign pause runbook.

### P3: Add external probe links and technology choices

If this case is meant to match the more polished agentic book cases, add `toProbeFurther` and `technologyChoices` for DAM/brand assets, content authenticity, analytics/event streams, activation providers, consent tooling, and model/eval infrastructure.

## What Not To Change

- Keep the brand-reputation gate as the central teaching idea.
- Keep the deterministic prohibited-claim check outside the model.
- Keep regenerated variants re-entering the gate before activation.
- Keep C2PA provenance in the brand-safety story.
- Keep the connection to Agentic Platform Foundations, but make the marketing-specific workflow state stand on its own.

## Bottom Line

This dataset has the right story and the right core architecture. To become a strong book case, it needs concrete capacity, durable workflow state, explicit consent/channel operations, constrained bandit semantics, and corrected step diagrams. The fastest high-value pass is to fix the hidden diagram endpoints, then add the publish lifecycle and expanded data model that make the brand gate credible in production.
