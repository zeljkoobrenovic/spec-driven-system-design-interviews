# Review: CI/CD Pipeline for Microservices + Web + Mobile - System Design

Reviewed file: `data/book/cicd-pipeline/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent changes materially improved this interview. The old review's major
recommendations are now mostly implemented: workflow sequences exist for the
final design, deployment approval/admission, rollback, and mobile store state;
fast-feedback now has real options; flaky-test and merge-queue operations are
first-class teaching content; mobile has infrastructure options and signing
material depth; the feature-flag dependency is explicit in prose and
architecture; and data-model fields were normalized.

The dataset is now a strong book-quality system design case. It teaches the
right central invariant - build once, sign, attest, and promote the same bytes -
while also covering CI fan-out, runner trust boundaries, cache poisoning,
progressive delivery, rollback state, mobile store review, and version skew.

The remaining work is narrower and more concrete: fix a few diagram views whose
links reference hidden endpoints, tighten the deployment/environment model so it
can represent many services and web bundles per environment, and decide whether
queue fairness/merge queues should remain a deep dive or become an explicit
control-plane subsystem.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.60/5 | Strong CI/CD control-plane model; deployment state needs a target dimension for a fleet. |
| Production realism | 4.55/5 | Good supply-chain, gates, rollback, mobile, and flaky-test coverage; RBAC/separation-of-duties and queue governance are still light. |
| Pedagogical flow | 4.65/5 | The seven-step spine is coherent and the new options/deep dives teach senior-level trade-offs. |
| Dataset/rendering fit | 4.30/5 | JSON and references parse cleanly, but several views include links whose endpoint nodes are omitted. |
| Overall | 4.55/5 | A credible production CI/CD case with a few specific fixes left. |

## What Works Well

- The interview now exposes one constraint at a time: one-box script, DAG
  orchestration, affected-only feedback, signed artifacts, progressive deploy,
  gates/rollback, then mobile release.
- The control-plane entities are much stronger than before: `runs`,
  `run_stages`, `jobs`, `job_attempts`, `artifacts`, `approvals`,
  `environment_versions`, `deployment_steps`, `mobile_releases`,
  `audit_events`, `test_results`, and `idempotency_keys`.
- The API surface now covers the workflows the design promises: logs, reruns,
  run cancel, deployment admission, approval, pause/resume, rollback,
  environment history, mobile release state, halt/resume/rollback, flaky-test
  lookup, and quarantine.
- The fast-feedback step now compares affected-only caching, remote build
  execution, predictive test selection, and brute-force full rebuild. That is a
  meaningful option set rather than a single preferred path.
- The supply-chain story is credible: short-lived runner credentials, signing
  material isolation, SBOMs, scan state, provenance, immutable artifacts, and
  deploy-time admission.
- The mobile step is now realistic. It models scarce macOS capacity, managed
  mobile CI trade-offs, signing material lifecycle, asynchronous store review,
  staged rollout, crash gates, version skew, and feature-flag kill switches.
- The wrap-up material is useful: `technologyChoices`, `satisfies`,
  `interviewScript`, `levelVariants`, and follow-ups all reinforce the case
  rather than feeling bolted on.

## Highest-Impact Issues

### 1. Environment versioning is too coarse for a fleet

`environment_versions` is described as the source of truth for what is live per
environment, but the table has `env` as the primary key and no `target`,
`service`, `surface`, or `artifact_type` field. In a system with roughly 40
microservices, a web bundle, iOS, and Android artifacts, a single
`live_version` per environment cannot answer "which version of checkout is live
in prod?" versus "which web bundle is active?".

Recommended edits:

- Make the live-version record key `(env, target)` or `(env, surface,
  artifact_name)`, where target maps back to `artifacts.target`.
- Update `GET /environments/{env}/history` to optionally filter by target and
  return per-target live and previous-good versions.
- Clarify whether `POST /deployments` infers the target from
  `artifactVersion` or requires an explicit target; either approach is fine, but
  the invariant should be stated.
- Rename or explain `deployment_steps`: it currently represents one rollout
  state machine, not individual rollout steps. If history matters, add
  `deployment_events` or make clear that `audit_events` stores each transition.

### 2. Some diagram views include links whose endpoint nodes are not visible

The structured views mostly resolve, but several selected links point to nodes
not included in the same `view.nodes` list. Mermaid may render those endpoints
as implicit, unlabeled nodes, which weakens the generated architecture diagrams.

Observed cases:

- `steps/naive`: `git-trigger` omits `Trigger`; `trigger-orch` omits
  `Trigger`; `deployer-k8s` omits `Deployer`.
- `steps/artifacts`: `orch-runner` omits `Orchestrator`.
- `steps/mobile` and all three mobile options: `orch-deployer` omits
  `Orchestrator`.
- `finalDesign`: `deployer-flags` omits `FlagService`.

Recommended edits:

- For each view, either add the missing endpoint node or remove the link.
- In `finalDesign.view.nodes`, add `FlagService` because the final description
  and `deployer-flags` link make feature flags part of the final architecture.
- Re-run a browser visual check after fixing these, because Mermaid can hide
  this issue by creating implicit nodes.

### 3. RBAC and separation-of-duties are implied but not modeled

The design records approval actor, policy, and audit events, but it does not
state who is allowed to approve, deploy, rollback, halt a mobile rollout, or
quarantine a test. In production CI/CD systems this is not a detail: the person
who authored a risky change often must not be the only approver for prod, and
mobile store credentials should be held by a release service identity rather
than broad user accounts.

Recommended edits:

- Add a short security/RBAC deep dive, probably under `deploy` or `artifacts`.
- Mention separation-of-duties for production approval: approver role, protected
  environment, policy id, break-glass path, and audit event.
- Clarify that actor identity comes from auth context on approval, rollback,
  halt, and quarantine APIs rather than user-supplied request fields.
- Consider a small `release_permissions` or `policy_bindings` entity only if
  you want the data model to teach this explicitly.

### 4. Merge queues and runner fairness are strong prose, but not yet concrete

The fast-feedback deep dive now explains stale-green PRs, speculative batches,
flake interaction, and bisection. The orchestrate step also introduces queue
fairness/priority. That is a good teaching improvement, but the control-plane
model still has no merge queue, batch, priority lane, runner-pool quota, or
class-level scheduling state.

This is acceptable if merge queues remain an interview follow-up. If they are
intended to be first-class content, the design should add just enough state to
make the operations real.

Recommended edits:

- Add a `merge_queue_entries` or `merge_batches` record if preserving main
  branch health becomes a core requirement.
- Add runner queue metadata such as job class (`pr`, `main`, `release`,
  `mobile`), priority, deadline, pool, and lease expiry if queue fairness is
  meant to be more than a concept chip.
- Add one sequence for speculative batch success/failure if you want this to
  graduate from deep dive to main-path workflow.

## System Design Soundness

The architecture is sound for the problem. A VCS event enters an idempotent
trigger path, the orchestrator persists a run/stage/job/attempt model, ephemeral
runners execute a DAG, cache and affected-target logic reduce fan-out cost,
artifacts are signed and stored immutably, and the deployment controller
promotes only admitted versions through environments.

The strongest invariant is clear: a version is built once, signed, attested,
scanned, and promoted without rebuilding per environment. That is the right
answer for a modern CI/CD platform.

The capacity section is credible. It sizes daily and peak commit rate, average
and p95 affected targets, Linux vCPU slots, macOS scarcity, cache footprint,
cache egress, retention, latency, and deploy cadence. It also correctly warns
that a wide shared-library change can saturate runners and cache bandwidth at
the same time.

The main system-design gap is the deployment target dimension. The design talks
about a fleet, but `environment_versions` reads as one live version per
environment. Fixing that would align the data model with the stated
microservices/web/mobile scope.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Script on a Build Box

This is a useful baseline. The serial-work example makes the scaling failure
obvious: rebuilding roughly 40 services at about 8 minutes each quickly blows
up at 500 commits/day. The trap against shipping the script as "good enough" is
well placed. The diagram view should be fixed so its links do not imply hidden
trigger/deployer nodes.

### Step 2: Model the Pipeline as a DAG on Ephemeral Runners

This step is strong. It introduces durable state, ephemeral runners,
idempotency, trust boundaries, and queue fairness. The options compare real
deployment models: Kubernetes-native DAG runners, Jenkins-style controllers,
and managed CI. The flow is simple but sufficient for the first control-plane
step.

### Step 3: Fast Feedback: Affected-Only Builds + Caching

This is now one of the strongest steps. The option set covers affected-only
remote cache, remote build execution, predictive test selection, and full
rebuild. The cache correctness deep dive is practical, especially the
untrusted-PR write restriction and egress warning. The merge-queue/flaky-test
deep dive now teaches the reliability consequences of CI concurrency rather
than treating flakes as a throwaway follow-up.

### Step 4: Immutable, Signed Artifacts

This step is production-grade for the interview scope. It connects build-once
promotion to SBOMs, scan results, provenance, vault-backed signing,
short-lived credentials, and deploy-time admission. The remaining issue is
diagram shape: the view includes `orch-runner` but omits `Orchestrator`.

### Step 5: Progressive Delivery for Services + Web

The deploy step now teaches real trade-offs across canary, blue-green, and
rolling update. The GitOps deep dive is balanced: desired state in Git plus an
imperative pause/abort/rollback path for live rollout control. The feature-flag
deep dive correctly explains deploy versus release across server, web, and
mobile.

### Step 6: Automated Gates + Rollback

This step has the right operational depth. Gate policy inputs include windows,
thresholds, and sample size; the migration deep dive correctly warns that
stateful schema changes cannot be rolled back like stateless code. The rollback
sequence makes the state machine visible.

### Step 7: Mobile Release Pipeline

Mobile is no longer hand-waved. The step explains why mobile differs from
server/web deploys, models app-store review as asynchronous external state, and
uses flags and forward-fixes as the practical rollback strategy for installed
binaries. The infrastructure options and signing material deep dive are
particularly useful. The mobile diagrams should add `Orchestrator` or drop the
`orch-deployer` link.

## Final Design Review

The final design integrates the major components introduced in the steps:
developer, Git host, trigger, orchestrator, state store, runner pool, cache,
registry, signing/secrets, deployment controller, Kubernetes runtime, CDN, app
stores, observability gates, and GitOps. The description now also names feature
flags as an external dependency for safe mobile and cross-client releases.

The final sequence is valuable because it shows the whole path from webhook to
gated production. It does not need to show every detail, but it does make the
build-once-promote and gate/rollback story visible.

The final diagram needs one fix: add `FlagService` to `finalDesign.view.nodes`
or remove `deployer-flags`. Since the final text and pattern list both depend
on flags, adding the node is the better fix.

## Concept Introduction and Learning Flow

The concept staging is strong. Hermetic builds, idempotency, runner trust
boundaries, affected target graphs, merge queues, flaky-test quarantine,
provenance, SBOMs, canaries, GitOps, deploy-versus-release, error-budget gates,
expand/contract migration, staged rollout, release tracks, and version skew are
introduced close to where they are used.

The amount of material is high, but the step order keeps it manageable. The
interview script helps the candidate narrate the design in a plausible
30-minute flow.

## Step-to-Final-Design Coherence

The step-to-final mapping is mostly coherent. The final design reflects the
architecture accumulated across the seven steps, and `satisfies` ties each
requirement to relevant steps. The recent additions closed the previous gaps
around workflow sequences, flaky tests, merge queues, feature flags, mobile
signing, and field normalization.

The notable coherence gap is now data-model granularity: the steps discuss
many targets, but the final live-version model is keyed too broadly. The other
gap is visual rather than conceptual: several views select links whose endpoint
nodes are not selected.

## Realism Compared With Production Systems

The dataset is realistic for a senior system design interview. It covers the
operational mechanics that separate a generic pipeline answer from a real
delivery platform: ephemeral runner isolation, content-keyed caches,
untrusted-PR restrictions, immutable artifacts, signed provenance,
deploy-time admission, durable approvals, GitOps, rollout gates, migration
compatibility, mobile store state, crash gates, version skew, and flaky-test
governance.

The remaining production realism areas are RBAC/separation-of-duties, explicit
target-level live-version history, and queue governance under contention. Those
are focused improvements, not signs that the case is incomplete.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Top-level sections are present for requirements, capacity, API, data model,
  high-level architecture, steps, final design, satisfies, technology choices,
  interview script, level variants, and follow-ups.
- The dataset uses structured `view.nodes` and `view.links`; no raw Mermaid
  step/final architecture diagrams were found.
- Step/final `view.nodes` IDs resolve against `highLevelArchitecture.nodes`.
- Step/final `view.links` IDs resolve against `highLevelArchitecture.links`.
- Highlight IDs resolve within their selected view nodes.
- `satisfies[*].steps[*]` resolve to existing step IDs.
- `technologyChoices[*].steps[*]` resolve to existing step IDs.
- Step and final sequence participants resolve to canonical architecture node
  IDs.
- Canonical node types are used: `actor`, `cache`, `database`, `edge`,
  `external`, `gateway`, `object-storage`, `observability`, `orchestrator`,
  `service`, and `worker`.
- Several selected links have endpoints missing from the same view's node list;
  those are listed in Highest-Impact Issue 2.
- The dataset has no `probeLinks`, `aiVisual`, `explainerComic`, or generated
  requirement illustrations. These are optional enrichment, not correctness
  issues.

## Recommended Edits, Prioritized

### P1: Fix view/link endpoint consistency

Add the missing endpoint nodes or remove the selected links in the affected
views. Add `FlagService` to the final design view.

### P1: Add target granularity to live deployment state

Key environment live-version state by environment plus target/surface, and
adjust the deployment/history API wording to match.

### P2: Clarify authorization and separation-of-duties

Add a short RBAC/security deep dive covering production approvers, release
service identity, store credentials, break-glass, and audited privileged
actions.

### P2: Decide whether merge queues are main-path or follow-up

If main-path, add minimal merge-queue/batch and queue-priority state. If
follow-up, the current deep dive and follow-up prompt are enough.

### P3: Add optional enrichment assets

Consider `probeLinks`, AI visuals, requirement illustrations, or an explainer
comic after the content fixes. These would improve presentation but should not
block the dataset.

## What Not To Change

- Keep the seven-step spine; it is the right order for the interview.
- Keep mobile as the final step; the contrast lands best after server/web
  rollback is established.
- Keep build-once-promote-everywhere as the central invariant.
- Keep the affected-only/cache option set and the cache poisoning guidance.
- Keep deploy-time admission and expand/contract migrations as senior-level
  teaching moments.
- Keep feature flags external to the CI/CD platform, but keep naming the
  dependency explicitly.

## Bottom Line

This is now a strong, production-realistic CI/CD system design interview. The
next pass should be precise rather than broad: fix diagram endpoint selection,
make live deployment state target-aware, and add a small amount of
authorization/queue-governance detail if the case needs to feel fully
production hardened.
