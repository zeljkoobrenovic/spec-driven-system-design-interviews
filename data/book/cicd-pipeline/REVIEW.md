# Review: CI/CD Pipeline for Microservices + Web + Mobile - System Design

Reviewed file: `data/book/cicd-pipeline/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong, compact CI/CD delivery-platform walkthrough. The spine is
right for a book interview: naive build box, DAG orchestration, ephemeral
runners, affected-only builds, content-keyed cache, immutable signed artifacts,
progressive delivery, observability-gated rollback, and the separate mobile
release path. The case is easy to teach because every step exposes the next
problem before solving it.

The main issue is that the dataset is still more of a high-level delivery
platform narrative than a production-grade control-plane design. It names the
right components, but the API and data model do not yet encode job/stage
state, approvals, deployment environments, async mobile release state, audit
history, policy gates, or idempotent retry behavior. Capacity also needs enough
math to size runner pools, cache, logs, artifact storage, and especially scarce
macOS capacity.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.05/5 | Correct architecture and release-safety principles; control-plane contracts and state machines need more precision. |
| Production realism | 3.65/5 | Good on runners, artifacts, canaries, rollback, and mobile differences; thin on approvals, retries, migrations, policy, audit, and async store workflows. |
| Pedagogical flow | 4.25/5 | Clear progression and strong "why now" recaps; lack of options/deep dives reduces trade-off teaching. |
| Dataset/rendering fit | 4.55/5 | JSON parses and references resolve; no major renderer issues found. |
| Overall | 4.05/5 | A solid book case that needs a control-plane hardening pass before it feels production-complete. |

## What Works Well

- The step order is natural. Each recap names the new risk that motivates the
  next step, which makes the walkthrough easy to narrate in an interview.
- The initial build-box baseline is useful rather than throwaway. It exposes
  speed, parallelism, heterogeneous targets, secret handling, and unsafe deploys.
- Step `orchestrate` correctly introduces DAG scheduling and ephemeral runners
  before cache or artifact concerns. That is the right foundation.
- Step `fast-feedback` teaches the two biggest monorepo levers: affected-target
  graph computation and content-keyed cache reuse.
- Step `artifacts` has the right invariant: build once, sign, attest, and
  promote the same bytes through every environment.
- Step `deploy` separates build from release and introduces GitOps, canary, and
  blue-green without pretending one rollout strategy fits every case.
- Step `rollback` includes the most important safety loop: compare canary
  golden signals against stable, then abort and shift back.
- Step `mobile` is a strong final contrast. It explains why mobile cannot use
  server-style instant rollback and correctly points to staged rollout,
  forward-fix, and feature flags.
- The final design includes all high-level nodes introduced through the steps.
- Renderer-facing checks are clean: source JSON parses; step and final-design
  node/link references resolve; sequence participants resolve; `patterns`,
  `technologyChoices`, and `satisfies` step references resolve; node types are
  canonical.

## Highest-Impact Issues

### 1. The API and data model do not model the control plane deeply enough

The requirements promise run status, logs, version-to-environment history,
approvals, promotion, rollback, and mobile release. The current API has useful
starting endpoints, but it compresses the platform into `runs`, `artifacts`,
and `deployments`. That is not enough state for a realistic delivery platform.

Missing or under-specified surfaces:

- stages/jobs inside a run, including dependencies, attempts, runner type,
  cache keys, queue time, start/end time, exit reason, and log pointers;
- approval records with actor, policy, environment, expiry, override reason,
  and audit trail;
- environment state, including current live version, previous known-good
  version, desired GitOps revision, rollout strategy, and active traffic split;
- deployment step state, such as `pending_approval`, `ramping`, `paused`,
  `aborted`, `live`, `rollback_in_progress`, and `rolled_back`;
- mobile release records with platform, track, store submission id, review
  status, staged rollout percentage, crash gate status, and halt/forward-fix
  linkage;
- log/artifact retention, audit events, and idempotency keys for retried
  webhooks, run starts, deploy requests, and rollback calls.

Concrete fix:

- Add `run_stages`, `jobs`, `job_attempts`, `approvals`,
  `environment_versions`, `deployment_steps`, `mobile_releases`,
  `audit_events`, and `idempotency_keys` to the data model.
- Expand the API with endpoints for approving/rejecting a promotion, listing
  environment history, fetching logs by stage/job, cancelling/rerunning a job,
  pausing/resuming a rollout, and querying mobile release status.
- Put idempotency keys on `POST /webhooks/vcs`, `POST /deployments`, rollback,
  and mobile release creation so retries do not create duplicate runs or
  duplicate submissions.

### 2. Capacity is useful but too small to size the platform

The capacity section states 500 commits/day, 40 services, two mobile apps, p50
pipeline under 15 minutes, and tens to hundreds of deploys/day. Those are good
headline constraints, but they do not let a candidate estimate the actual
bottlenecks.

The design needs numbers for:

- peak commit/webhook rate, not just daily volume;
- average and p95 affected targets per change;
- average jobs per target and average job duration;
- concurrent PR runs and maximum queue delay;
- Linux runner count, autoscaling warm-pool size, and cold-start penalty;
- macOS runner availability, because iOS capacity is often the scarce resource;
- cache size, hit rate, eviction window, and remote-cache bandwidth;
- artifact size and retention for images, web bundles, `.ipa`, `.aab`, SBOMs,
  attestations, logs, and test reports;
- observability volume from deploy markers, logs, metrics, and traces.

Concrete fix:

- Add a small sizing paragraph, for example: 500 commits/day with a 4x work-hour
  peak, 6 affected targets per PR on average, 8 jobs per target, 3-8 minute job
  duration, and a target queue wait under 2 minutes.
- Derive an approximate runner pool from those numbers, then call out separate
  Linux and macOS pools.
- Add retention assumptions such as 90 days of logs, one year of audit, and N
  retained artifact versions per service/environment.

### 3. Rollout safety is correct conceptually but missing stateful edge cases

The canary/rollback story is directionally right, especially the stable-versus
canary comparison. The dataset should make the boundaries clearer for the cases
that often decide whether a CI/CD design is production-safe.

Gaps to address:

- database migrations are mentioned only as a trap, not integrated into the
  rollout flow;
- feature flag state is mentioned for mobile but not represented as a platform
  dependency for server/web compatibility;
- rollback is modeled as a traffic shift, but not as a state machine with
  pause, abort, retry, manual override, and post-rollback verification;
- web bundle activation on a CDN needs versioned assets, an active pointer,
  cache invalidation strategy, and compatibility with backend APIs;
- gates need explicit inputs, windows, and thresholds, otherwise "metrics
  healthy" can hide noisy or slow signals.

Concrete fix:

- Add an expand/contract migration sequence or deep dive under `rollback`:
  deploy backward-compatible schema, deploy app, migrate data, remove old
  fields later.
- Add rollout states and gate result records to the data model.
- Add one failure drill for a canary with a bad migration and one for a web
  bundle that calls a backend API not yet available to all users.
- Name the gate policy inputs: error rate, latency, saturation, crash-free
  sessions for mobile, synthetic checks, business guardrails, and minimum
  sample size.

### 4. Mobile is well explained but under-modeled operationally

Step `mobile` is one of the strongest teaching steps, but the final system still
treats app stores as a single external box. Real mobile release management is
asynchronous and stateful. A candidate should see how the pipeline tracks that
state without pretending it can control the stores like Kubernetes.

Missing details:

- TestFlight/internal track, Play internal/closed/open tracks, production
  staged rollout, halt, resume, and reject states;
- store callbacks or polling for review status;
- mobile crash and adoption metrics feeding release gates;
- phased rollout differences between iOS and Android;
- feature flag and server compatibility as first-class release dependencies;
- version skew policy for clients that cannot or will not update.

Concrete fix:

- Add a `MobileRelease` data model with `platform`, `artifact_version`,
  `track`, `store_submission_id`, `review_status`, `rollout_pct`,
  `crash_gate_status`, `min_backend_version`, and `kill_switches`.
- Add a short sequence from upload to store review to staged rollout to halt or
  ramp.
- Add one follow-up or failure drill for a backend change that must support old
  mobile clients for weeks.

### 5. Supply-chain security is introduced but not end-to-end

The dataset correctly mentions signing, secrets, provenance, and vault-backed
credentials. To feel production-grade, it should connect those mechanisms from
source to deploy admission.

Missing security checks:

- runner identity and short-lived credentials, for example OIDC from the CI
  system to the cloud account or vault;
- dependency and container scanning;
- SBOM generation and retention;
- signed commits or trusted branch protection as an input signal;
- policy checks before promotion, such as "only signed artifacts with passing
  tests and no critical vulnerabilities can deploy";
- verification at deploy time that the digest and attestation match the
  approved run.

Concrete fix:

- Add a policy/admission gate between registry and deployer, or make it part of
  the deployment controller.
- Include SBOM and vulnerability scan records in the artifact model.
- Add a failure drill: "attestation missing or signing key rotated during a
  release" and expected behavior.

### 6. The walkthrough has few explicit trade-off options

The prose and prompts teach trade-offs, but all seven steps have a single path
and there are no `options` or `deepDives`. That makes the generated decision
tree a straight line and gives the reader fewer chances to compare plausible
alternatives.

Concrete fix:

- Add options to two or three high-leverage steps:
  - `orchestrate`: Jenkins-style central controller vs Kubernetes-native DAG
    runner vs managed CI.
  - `fast-feedback`: affected-only builds vs full rebuild with brute-force
    parallelism vs remote execution/test selection.
  - `deploy`: canary vs blue-green vs rolling update, with when each fails.
  - `mobile`: self-hosted macOS runners vs managed mobile CI.
- Add one deep dive for "hermetic builds and remote cache correctness" and one
  for "GitOps versus imperative deploy APIs".

## System Design Soundness

The architecture is directionally sound. A VCS webhook enters a trigger, the
orchestrator persists run state and schedules a DAG onto ephemeral runners, the
cache accelerates repeat work, the registry stores immutable signed artifacts,
and a separate deployment controller promotes versions into runtime
environments. That is the right split between CI and CD.

The strongest invariant is build-once-promote-everywhere. It prevents staging
and production drift and gives the deployer a concrete digest to verify. The
dataset should make the verification path explicit: the deployment controller
should check the artifact signature, provenance, policy status, and approved
run before changing desired state.

The rollback design is sound for stateless services and web assets if old
versions are kept warm and compatible. The dataset should be more explicit that
rollback is not sufficient for stateful schema changes, incompatible APIs, or
mobile clients that have already updated.

The API and data model are the main soundness gap. A production CI/CD platform
is mostly a state machine and audit log. Without stage/job attempts, approvals,
environment state, rollout steps, idempotency, and mobile release records, the
candidate cannot reason precisely about retries, duplicate webhooks, paused
rollouts, partial failures, audit requirements, or who approved what.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Script on a Build Box

This is a good baseline. It names the exact failures: serial execution, rebuild
everything, no iOS build capacity, secrets in script, no canary, and no
rollback. The improvement would be to add one concrete failure number, such as
"40 services * 8 minutes each means the queue exceeds the workday under peak
commit load."

### Step 2: Model the Pipeline as a DAG on Ephemeral Runners

This step introduces the right abstractions and the sequence flow is clear. It
should add a small amount of control-plane state: stages, jobs, attempts,
runner leases, retry policy, and log pointers. "A crashed run resumes or fails
cleanly" is a good claim, but the schema does not yet show how.

### Step 3: Fast Feedback: Affected-Only Builds + Caching

The target-graph and cache discussion is strong. To make it production-ready,
add remote cache correctness details: cache namespace, key inputs, poisoning
prevention, write policy for untrusted PRs, fallback on cache miss, and
observability for hit rate. This step is also a natural place to mention merge
queues or speculative pre-merge testing as a follow-up.

### Step 4: Immutable, Signed Artifacts

This step has the right contract and the best security content in the dataset.
It should connect signing and attestation to deploy-time admission. A registry
entry should not be enough to deploy; the controller should require a valid
signature, provenance for the expected commit, passing checks, and policy
approval.

### Step 5: Progressive Delivery for Services + Web

The separation between promotion and build is clear. GitOps is a good default
because it gives auditability and revertability. The step would teach more if
it compared canary, blue-green, and rolling update as options. It should also
make web/CDN release semantics concrete: versioned assets, active pointer,
cache TTL/invalidation, and backend compatibility.

### Step 6: Automated Gates + Rollback

This step closes the safety loop correctly. The failure drill is useful but too
narrow. Add drills for false-positive metrics, insufficient canary traffic,
stateful schema migration, and a rollback that fails because the old version
was not kept warm or compatible.

### Step 7: Mobile Release Pipeline

The mobile contrast is accurate and important. The next improvement is to model
the async store workflow and long-lived version skew. Mobile needs release
track state, review status, staged rollout percentage, crash gate results,
server compatibility policy, and feature flag ownership.

## Final Design Review

The final design integrates the main components: developer, Git host, trigger,
orchestrator, pipeline state store, runner pool, cache, registry, signing,
deployer, Kubernetes runtime, CDN, app stores, and observability gates. The
description correctly distinguishes server/web deploy-on-demand from mobile
store-gated release.

What is missing is the operational contract between those boxes. The final
design should name policy/admission as part of deployment, approvals as a
durable workflow, and environment state as the source of truth for what is live.
It should also either add a feature-flag service or explicitly state that
feature flags are external to the CI/CD platform but required for safe mobile
and cross-client releases.

## Concept Introduction and Learning Flow

Concepts are introduced just in time: hermetic build before caching, affected
target graph before artifact promotion, provenance before deploy, canary before
gates, and staged rollout after server rollback. That sequence works.

The concept set should be expanded slightly. Useful additions are:

- idempotency for webhook/run/deploy creation;
- runner trust boundary and untrusted PR isolation;
- merge queue;
- rollout state machine;
- expand/contract migration;
- SBOM and admission policy;
- version skew and feature flags.

## Step-to-Final-Design Coherence

The steps build cleanly toward the final diagram. Every final-design node is
introduced before the end, and the `satisfies` mapping ties requirements to the
right steps.

The weakest coherence gap is that several promises are described in prose but
do not appear as nodes, state, or API concepts in the final design:
approvals, logs, policy gates, audit, mobile crash gates, feature flags, and
store-status polling/callbacks. These do not all need separate diagram nodes,
but they should appear in the data model or sequence flows.

## Realism Compared With Production Systems

The dataset has the right production instincts: ephemeral runners, cache
correctness, immutable digests, provenance, vault-backed secrets, GitOps,
progressive delivery, SLO gates, deploy markers, and mobile staged rollout.

The production realism falls short around lifecycle and failure handling. Real
CI/CD systems spend a lot of complexity on duplicate events, retries,
concurrency control, approvals, runner isolation, log retention, partial
rollouts, rollout pause/resume, flaky tests, queue starvation, and audit. The
case mentions some of these indirectly, but it should make the highest-impact
ones visible in the design.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- The dataset uses structured `view.nodes` and `view.links`; no raw Mermaid
  architecture diagrams are used in steps or final design.
- Step view nodes and links resolve against `highLevelArchitecture`.
- Final-design view nodes and links resolve against `highLevelArchitecture`.
- Sequence participants and message endpoints resolve to canonical node IDs.
- `satisfies.functional[*].steps` and `satisfies.nonFunctional[*].steps`
  resolve to existing steps.
- `patterns[*].steps` and `technologyChoices[*].steps` resolve to existing
  steps.
- High-level architecture node types are canonical.
- There are no step options, option diagrams, or deep dives. That is valid, but
  it limits the value of the auto-generated decision tree and reduces
  trade-off coverage.
- The dataset has no `probeLinks`, `aiVisual`, `explainerComic`, or generated
  requirement illustrations. That is not a correctness issue, only an optional
  enrichment opportunity.

## Recommended Edits, Prioritized

### P1: Add the missing control-plane model

Add state records for stages, jobs, attempts, approvals, environment versions,
deployment steps, mobile releases, audit events, and idempotency keys. Expand
the API to expose approvals, logs, reruns/cancels, rollout pause/resume, and
environment history.

### P1: Add capacity math for runner pools and retention

Turn the headline numbers into a rough sizing model: peak commits, affected
targets, jobs per target, job duration, queue SLO, Linux runner pool, macOS
runner pool, cache footprint, artifact/log retention, and observability volume.

### P1: Make rollout and rollback state explicit

Add rollout states, gate records, rollback states, and migration compatibility
guidance. Include failure drills for stateful migration, noisy metrics, and web
bundle/backend incompatibility.

### P2: Model mobile as an async release workflow

Add a mobile-release table and sequence covering store submission, review,
track/staged rollout, crash gating, halt/resume, and forward-fix.

### P2: Connect supply-chain security to deploy admission

Add SBOM/scanning/policy status to artifacts and require deploy-time
verification of signature, provenance, and policy pass before promotion.

### P2: Add trade-off options and deep dives

Introduce options for orchestration, caching/remote execution, rollout
strategy, and mobile runner strategy. Add deep dives for cache correctness and
GitOps versus imperative deployment.

### P3: Add optional enrichment assets

Consider generated AI visuals, requirement illustrations, and `probeLinks` once
the core content pass is complete.

## What Not To Change

- Keep the seven-step spine. It is coherent and teaches the design in the right
  order.
- Keep mobile as the final step. The contrast lands better after server/web
  rollback is already understood.
- Keep build-once-promote-everywhere as the central artifact invariant.
- Keep the concise prompts and recaps. They are useful for interview narration.
- Keep the high-level architecture node set mostly intact; the next pass should
  add state/contracts more than add boxes.

## Bottom Line

This is a strong CI/CD interview foundation with a clear narrative and correct
core architecture. The next improvement pass should make it feel like a real
delivery control plane: explicit job/stage state, approvals, idempotency,
environment history, rollout state machines, mobile release state, and
deploy-time policy verification.
