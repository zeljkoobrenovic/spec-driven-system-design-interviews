# Review: Internal Developer Platform (IDP) - System Design

Reviewed file: `data/book/internal-developer-platform/interview.json`
Review date: 2026-06-26

## Executive Summary

This is now a flagship-quality IDP case. The recent revision materially
improves the core production story: the platform orchestrator is no longer a
magic synchronous box, progressive delivery is separated from basic GitOps
rollback, governance tables are first class, and capacity assumptions now map
to component bottlenecks.

The strongest teaching move is still the workload spec plus platform
orchestrator: developers declare what a service needs, platform engineers
declare how each environment fulfills those needs, and the orchestrator
computes the concrete state. The dataset now supports that move with durable
jobs, idempotency, a deploy/reconcile queue, an orchestrator state store,
resource bindings, policy decisions, audit events, generated desired-state
handoff, rollout control, and migration guidance.

The remaining issues are no longer "missing the core design." They are mostly
coherence and operational-contract issues: a few API examples and option
diagrams still teach the older direct orchestrator-to-CD handoff, rollout state
is described better than it is modeled, and the control-plane degraded-mode
contract needs sharper SLO/RTO/RPO language.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.55/5 | Strong architecture with durable control-plane mechanics; needs tighter API/status and rollout-state contracts. |
| Production realism | 4.45/5 | Much stronger on reliability, policy, audit, migration, and sizing; remaining gaps are degraded-mode boundaries and operational APIs. |
| Pedagogical flow | 4.55/5 | Excellent maturity arc; new deep dives add real staff-level depth without losing the main story. |
| Dataset/rendering fit | 4.60/5 | JSON parses and structural references resolve; some semantic drift remains in API flows, option views, and technology-choice columns. |
| Overall | 4.55/5 | Publishable, coherent, and close to flagship depth. |

## What Works Well

- The case has a crisp thesis: an IDP is not a portal; it is a developer-facing
  contract backed by a real provisioning/configuration engine.
- The maturity arc is strong: tickets and runbooks -> CI/CD and Helm -> portal
  -> workload spec and orchestrator -> IaC engine -> resource plane ->
  ephemeral environments -> observability, security, and platform metrics.
- Step 4 now carries the right production weight. Durable jobs, idempotency,
  queue/outbox, provisioning locks, generated desired-state handoff, driver
  ambiguity, HA state, DR, and degraded mode are all explicitly covered.
- Progressive delivery is now correctly distinguished from "GitOps revert" and
  tied to a rollout controller plus observability health gates.
- The data model was expanded in the right direction: `teams`,
  `resource_bindings`, `deployment_jobs`, `policy_decisions`, `audit_events`,
  `migrations`, and `platform_metrics` make governance and operations concrete.
- Capacity moved beyond organizational anecdotes. The derived notes now explain
  worker concurrency, queue age, catalog sync, provider limits, GitOps scale,
  preview environment quotas, and platform-team on-call.
- The traps remain practical and memorable: bigger wiki, relabeled ops team,
  golden cage, leaky abstraction, PR-close cleanup only, vanity metrics,
  mandated adoption, and ivory-tower platform team.
- The review-time reference checks pass: step nodes, step links, final-design
  nodes/links, parents, `satisfies`, `patterns`, and `technologyChoices` all
  resolve.

## Highest-Impact Issues

### 1. The deploy API and API sequences lag behind the new durable handoff

The architecture now says the orchestrator persists a job, commits generated
desired state to a repo/artifact store, and lets GitOps reconcile from that
durable handoff. The main `/workloads/{id}/deploy` API example still returns a
simple `{ deploymentId, status, resources }`, and its sequence goes directly
from `Orchestrator` to `CD` with "generated desired state."

Why it matters: the API is where the candidate proves the control plane is not
just a diagram. If the API hides idempotency, queue state, policy decisions, and
generated commit identity, the strongest new production mechanics are easy to
miss.

Concrete fix:

- Add an idempotency key to the deploy request or document how one is derived
  from workload, environment, spec version, and image digest.
- Return durable job details: `jobId`, `phase`, `attempt`, `desiredStateRef`,
  `policyDecisionIds`, `resourceBindingIds`, and links to status/errors.
- Add `GET /deployments/{id}` or `GET /deployment-jobs/{id}` for polling the
  queued -> matching -> provisioning -> handed_off -> reconciling -> healthy
  lifecycle.
- Add failure/repair fields such as `resumePoint`, `lastError`,
  `manualRepairRequired`, and `ambiguousProviderOutcome`.
- Update the deploy API sequence to include `JobQueue`, `OrchDB`,
  `DesiredRepo`, and `CD` instead of the old direct `Orchestrator -> CD` path.

### 2. Some option diagrams still simplify away the new reliability model

The default Step 4 view now includes `JobQueue`, `OrchDB`, and `DesiredRepo`,
but the orchestrator option views still use the older, smaller
`Spec -> Orchestrator -> ResDef/Driver -> CD` shape. That is understandable for
compact option comparison, but it can accidentally imply that buying Humanitec,
operating Kratix, or assembling Score controllers removes the need for durable
state and handoff mechanics.

Concrete fix:

- Keep option diagrams compact, but include at least `DesiredRepo` in all three
  orchestrator option views.
- Add one sentence per option about who owns the reliability surface:
  Humanitec vendor SLA and integration boundary, Kratix operational burden,
  or in-house controller ownership.
- If the visual must stay small, say explicitly in each caption that the
  reliability queue/state/repo pattern still applies.

### 3. Rollout safety is described well but under-modeled

The progressive-delivery deep dive is a good correction. It names canary,
blue/green, health gates, automatic rollback, app-vs-infra rollback, rollout
revision, promotion state, and rollback reason. The data model only has
`deployments.strategy`, `deployments.status`, and `deployment_jobs.phase`.

Why it matters: rollout safety is stateful. Without first-class rollout state,
it is hard to answer "where is this canary stuck?", "which metric failed the
promotion?", or "was this rollback automatic or manual?"

Concrete fix:

- Add a `rollout_runs` table or explicit deployment fields for
  `rollout_revision`, `strategy`, `current_step`, `health_policy`,
  `promotion_state`, `rollback_reason`, and `automated_decision`.
- Add a small API or status response for rollout progress and rollback.
- Change the functional requirement wording from "via GitOps" to "via GitOps
  plus a rollout controller" so the top-level requirement matches the design.

### 4. The degraded-mode contract needs sharper boundaries

The deep dive correctly says existing workloads keep running, CI can still
build, GitOps continues reconciling committed desired state, and only new
provisioning is blocked. The non-functional requirement still says an
orchestrator outage blocks every team's deploys.

This tension is useful, but it needs precise wording. In a real interview, the
candidate should distinguish several cases:

- Existing workloads serving traffic.
- App-only redeploys where desired state is already generated or can be
  committed through a bypass.
- New resource provisioning or changed resource definitions.
- Preview environment creation.
- Portal/catalog read paths.
- Policy or secret binding changes.

Concrete fix: add a short degraded-mode matrix with allowed, delayed, and
blocked operations, plus platform-control-plane SLOs, RTO/RPO for `OrchDB`, and
restore procedure from `OrchDB` plus `DesiredRepo`.

### 5. Governance is present, but platform-engineer workflows are still thin

The model now includes teams, policy decisions, audit events, migrations, and
platform metrics. That is a big improvement. The remaining gap is workflow:
how a platform engineer safely changes a resource definition, golden path,
policy version, or tenant quota.

Concrete fix:

- Add a short flow for resource-definition rollout: draft -> validate ->
  canary on volunteer teams -> audit -> promote -> deprecate old version.
- Add policy-version lifecycle: warn-only, enforce, exemption, expiry, and
  review.
- Show how teams discover pending golden-path migrations and request or renew
  exemptions.

## System Design Soundness

The architecture is sound. The five-plane decomposition works well for an IDP:
Developer Control, Integration & Delivery, Resource, Observability, and
Security. The final design now integrates the durable control-plane components
introduced in Step 4 and avoids the earlier risk of treating the orchestrator
as a stateless "submit spec, get manifests" box.

The core path is credible:

- Developers author a Score-style workload spec.
- CI submits spec plus image.
- The orchestrator authenticates, evaluates policy, persists job state, and
  resolves abstract resources against environment-specific definitions.
- Drivers provision or reconcile infrastructure.
- Outputs and secret references are bound back to the workload.
- Generated desired state is committed durably.
- GitOps and a rollout controller reconcile the cluster with health-gated
  promotion and rollback.

That is the right shape for a production IDP case. The main soundness issue is
that some public interfaces still look less mature than the architecture:
deploy status, rollout state, repair state, resource-binding lifecycle, and
policy decisions should be visible at API or status-query level.

The data model is now strong enough to support the narrative. It still has a
few places where adding state would improve defensibility:

- `deployments`: add generated commit/artifact reference, rollout revision,
  current rollout step, health-policy reference, and rollback reason.
- `resource_definitions`: add lifecycle, compatibility, canary scope, and owner.
- `policy_decisions`: add target object, request id, severity, and expiry for
  warnings/exemptions.
- `migrations`: consider workload-level state, not only team-level movement
  between golden-path versions.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Tickets, Shared Scripts, and a Wiki Runbook

This is a strong baseline. It starts from a realistic operating model and gives
measurable pain: ticket age, skipped hand-run steps, environment mismatch, and
multi-day onboarding. The traps cleanly separate "renamed ops" from actual
self-service.

No major change needed. Preserve this step's simplicity.

### Step 2: Automate Delivery: CI/CD Pipelines + Helm Charts per Service

This step is now clearer because it explicitly limits what GitOps rollback
means: reverting desired state is useful, but it is not progressive delivery.
The options are realistic, and the drift trap motivates the later workload spec
without jumping too early.

Improvement: add a sentence to the API/sequence or recap that the direct
`Orchestrator -> CD` path in later legacy diagrams is superseded by the
generated desired-state repo once Step 4 is introduced.

### Step 3: A Self-Service Portal over Existing Tooling (Backstage)

This remains one of the best teaching steps. It correctly frames the portal as
an interaction layer, not the platform itself. The build/buy options are
realistic and the traps are useful.

Improvement: catalog freshness could still be more operational. Add a small
note about ownership validation, orphaned services, source-of-truth sync,
scorecard updates, and stale dependency data.

### Step 4: The Workload Spec + Platform Orchestrator

This is the centerpiece and now has the required production depth. The durable
control-plane deep dive is especially strong: idempotency keys, queue/outbox,
binding locks, durable desired-state handoff, driver retry/timeout handling,
ambiguous IaC outcomes, DR, and degraded mode are all the right topics.

The two sequence flows are useful, but the second one should include the
deploy/reconcile queue explicitly. It currently persists to the state store,
then provisions. Because the deep dive says workers lease from a queue and ack
only on success, the sequence should show `JobQueue` as a participant.

### Step 4a: Choose the IaC Engine Under the Orchestrator

Good focused sub-step. The apply-time versus continuous-reconciliation axis is
the right comparison. The option set is credible: Terraform/OpenTofu,
Crossplane, and Pulumi.

Improvement: add how each engine reports drift and ambiguous outcomes back into
the orchestrator's common job model. This would connect Step 4a more tightly to
the new `deployment_jobs` and repair-state story.

### Step 5: Resource Plane and Multi-Tenancy

The isolation options are well framed: namespace-per-team, vcluster, and
cluster-per-tenant. The step correctly treats this as a cost-vs-isolation
choice, not a single best practice.

Improvement: tie the isolation decision directly to the new `teams` table:
compliance tier, cost center, on-call route, quota, NetworkPolicy template, and
approval policy. That would make tenant policy flow from data, not prose.

### Step 6: Ephemeral Environments + Golden-Path Versioning

The preview-environment and golden-path versioning combination works well.
The reaper trap and "guardrail, not railroad" framing are strong.

The added preview-environment sequence is useful. To deepen it further, include
environment lifecycle state: requested, provisioning, ready, idle, expired,
deleting, failed, and orphaned. Also consider mentioning data seeding, DNS, and
secret scope for PR environments.

### Step 7: Bake In Observability & Security - and Measure the Platform

This step is strong and more production-realistic after the new security and
migration deep dives. It now covers policy gates, secret references,
supply-chain checks, break-glass, tenant-derived guardrails, brownfield import,
parallel migration, and product-funnel measurement.

The main risk is density. This step now carries observability, security,
supply chain, platform product metrics, migration, and adoption. It is still
readable, but if more content is added, split the material into clearer buckets
or move migration into a dedicated follow-up answer.

## Final Design Review

The final design is coherent and now reflects the revised production model:
`JobQueue`, `OrchDB`, `DesiredRepo`, and `Rollout` are present alongside the
original IDP planes. The description correctly says the orchestrator runs
durable jobs, persists state, commits generated desired state, and lets GitOps
plus rollout control reconcile progressively.

The final design should keep these nodes. They are not implementation clutter;
they are what makes the orchestrator credible as a shared control plane.

Remaining refinements:

- Consider showing `JobQueue -> Orchestrator` in final design, not only
  `Orchestrator -> JobQueue`, if the visual needs to communicate worker leasing
  and retry.
- Consider a lightweight policy/audit read path from `Sec` or `OrchDB` to the
  portal/catalog so developers can see why a deploy was denied or mutated.
- Keep `Rollout` visible in final design; it is the clearest way to avoid the
  common "GitOps equals progressive delivery" mistake.

## Concept Introduction and Learning Flow

The concept staging is excellent. The walkthrough introduces one abstraction at
a time and gives each one a reason to exist:

- Ticket-ops exposes the self-service need.
- CI/CD exposes drift.
- Portal/catalog exposes discovery but not provisioning.
- Workload spec and orchestrator solve the what-vs-how split.
- IaC engine choice teaches apply-time versus reconciliation.
- Resource plane teaches isolation.
- Ephemeral environments teach lifecycle and cost control.
- Observability/security/product metrics teach platform maturity.

The new "Durable control plane" and "Progressive delivery" patterns are good
additions. They belong in Step 4 because they are not afterthoughts; they define
whether the orchestrator can safely sit in the delivery path.

## Step-to-Final-Design Coherence

Coherence is much improved. Each important final-design node is introduced
before the final design, and the final design no longer over-promises mechanics
that the steps never teach.

The remaining semantic mismatches are specific:

- The deploy API sequence still shows direct `Orchestrator -> CD`, while the
  final design uses `Orchestrator -> DesiredRepo -> CD`.
- Some orchestrator option views still use `orch-cd`, which visually hides the
  durable desired-state handoff.
- The top-level progressive-delivery requirement says "via GitOps", while the
  design now correctly says "GitOps plus rollout controller."
- The reliability requirement says an orchestrator outage blocks every team's
  deploys, while the deep dive says already-committed state can keep deploying.
  This should be reconciled as a degraded-mode matrix rather than left as
  ambiguous wording.

## Realism Compared With Production Systems

The dataset is now realistic in the places many IDP writeups are weak:

- It treats platform adoption as a product outcome, not a mandate.
- It distinguishes a portal from a platform.
- It includes a real control-plane failure story.
- It acknowledges vendor marketing caveats and the DORA platform tradeoff.
- It models policy, audit, migration, and platform metrics.
- It explains that GitOps rollback and progressive delivery are different
  capabilities.

Remaining production questions a strong interviewer could still ask:

- What exact operations continue during orchestrator outage?
- What are the platform control-plane SLO, RTO, and RPO?
- How are timed-out Terraform/OpenTofu applies reconciled without double
  provisioning?
- How does a developer inspect a denied policy decision or failed mutation?
- How are rollout health policies versioned and tested?
- How are preview environment quotas enforced by team and cost center?
- How are golden-path deprecations communicated, exempted, and eventually
  enforced?

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- High-level architecture link endpoints resolve.
- Step view node/link references resolve.
- Final-design node/link references resolve.
- `satisfies[*].steps[*]`, `patterns[*].steps[*]`, `technologyChoices[*].steps[*]`,
  and `step.parent` references resolve.
- No duplicate `view.links` entries were found; the old `envsvc-orch` duplicate
  is gone.
- The legacy `orch-cd` link still exists and is used by API/option flows. It is
  valid structurally, but semantically weaker than the updated
  `orch-desiredrepo` + `desiredrepo-cd` path.
- Several options mark defaults only in the `name` string, e.g. "(default)".
  This is acceptable for the current renderer, but a structured default marker
  would be easier for future tooling.
- The `technologyChoices.cloud` provider columns still include vendor-neutral
  SaaS tools such as Port, Cortex, OpsLevel, Atlassian Compass, and Humanitec.
  If the UI cannot represent SaaS separately, add a note that those entries are
  provider-adjacent choices rather than native AWS/GCP/Azure services.
- Current vendor/tool claims should be source-checked before publication if the
  dataset is meant to make time-sensitive assertions. This review did not
  browse or externally verify vendor status.

## Recommended Edits, Prioritized

### P1: Update deploy API and API sequence for durable jobs

Expose idempotency, job phase, policy decisions, resource binding ids,
generated desired-state reference, retry/repair state, and status polling.
Update the sequence to include `JobQueue`, `OrchDB`, and `DesiredRepo`.

### P1: Reconcile direct-CD diagrams with the desired-state handoff

Where option/API diagrams still use `orch-cd`, either replace it with
`orch-desiredrepo` + `desiredrepo-cd` or make the caption explicitly say the
durable handoff is omitted for compactness.

### P2: Model rollout state explicitly

Add `rollout_runs` or deployment fields for rollout revision, current step,
health policy, promotion state, rollback reason, and automated decision source.

### P2: Add a degraded-mode matrix and platform SLOs

Define what continues, what is delayed, and what is blocked during outages of
the portal, orchestrator API, workers, state store, desired-state repo, GitOps,
rollout controller, and policy/secrets plane.

### P2: Turn governance objects into platform-engineer workflows

Add a flow for resource-definition rollout, policy-version rollout, exemptions,
and golden-path deprecation so the new tables are taught as operations, not only
schema.

### P3: Tighten catalog and migration details

Add catalog freshness/ownership handling and workload-level migration state for
brownfield services.

### P3: Clean up technology-choice presentation

Represent SaaS choices separately from cloud-native provider choices, or add UI
copy explaining why neutral SaaS products appear under provider columns.

## What Not To Change

- Keep the maturity arc. It is the strongest teaching device in the case.
- Keep the workload spec plus orchestrator as the central design move.
- Keep the "Backstage is not your platform" distinction.
- Keep the durable control-plane deep dive in Step 4; it is now one of the
  dataset's strongest sections.
- Keep the GitOps-versus-progressive-delivery distinction.
- Keep the DORA tradeoff and vendor-claim caveats; they make the case more
  credible.
- Keep adoption as a first-class requirement with escape hatches.

## Bottom Line

The recent changes fixed the most important review findings. This dataset now
teaches both the concept and the production reality of an IDP: developer intent,
platform-owned realization, durable orchestration, policy, audit, progressive
delivery, migration, and measurement. The next polish pass should synchronize
the API examples and compact option diagrams with the updated durable handoff
model, then make rollout and degraded-mode state explicit enough for a strong
staff-level interview answer.
