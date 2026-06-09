# Review: CI/CD Pipeline for Microservices + Web + Mobile - System Design

Reviewed file: `data/book/cicd-pipeline/interview.json`
Review date: 2026-06-09

## Update — 2026-06-09 (post-review hardening pass)

This pass implemented the review's P1–P3 recommendations. Summary of what
changed in `interview.json`:

- **Workflow sequences (P1, issue #1).** Added a final-design "commit to gated
  production" flow; a deploy "approval → admission → GitOps → rollout" flow
  (alongside the existing canary ramp); a rollback "gate failure → rollback
  state machine" flow; the mobile store-state flow now has a title. State-machine
  transitions are now visible as sequences.
- **Flaky tests + merge queues (P1, issue #3 / #2).** Promoted from follow-up to
  first-class content: a `test_results` data-model record (test identity, flake
  rate, owner, quarantine state, confidence); `GET /tests/{id}` and
  `POST /tests/{id}/quarantine` APIs; a "Merge queues + flaky tests" deep dive;
  a "rerun until green" trap; flaky-test and merge-queue failure drills; new
  `Merge queue` and `Flaky-test quarantine` patterns/concepts.
- **Fast-feedback option set (P2, issue #2).** Added four options: affected-only +
  remote cache (default), remote build execution, test selection, brute-force
  full rebuild. Capacity now has a p95/burst row and clarifies vCPU-slots ≠
  runners; the cache deep dive notes egress saturation.
- **Mobile option set + signing (P2/P3, issue #5).** Added three mobile-infra
  options (self-hosted macOS+Fastlane, managed mobile CI, hybrid), a
  signing-material deep dive (certs/profiles/store roles/rotation/revocation),
  and an app-store-rejection failure drill.
- **Feature flags made explicit (P2, issue #4).** Added an external `FlagService`
  node + `deployer-flags` link; `required_flags`/`kill_switches` on
  `mobile_releases`; a "deploy vs. release" concept; a cross-client
  flag-coordination deep dive; a flag-misconfiguration failure drill; a
  `Flag-coordinated release` pattern.
- **Data-model normalization (P3, issue #6).** Split all slash-combined field
  labels into individual fields across `job_attempts`, `artifacts`, `approvals`,
  `environment_versions`, `deployment_steps`, `mobile_releases`, `audit_events`,
  `idempotency_keys`; added `repo` to `runs`; added index/partition hints to the
  high-cardinality tables.
- **Minor polish.** Fixed the `/deployments/{id}/pause` "pass action" wording;
  added a queue-fairness concept to the orchestrate step.

References were re-validated (views/options/flows/satisfies/tech/patterns all
resolve) and `docs/book/` was rebuilt. The Mermaid sequence/flowchart rendering
of the new flows still warrants a visual pass in a browser. The rest of this
document is the original review.

---

Reviewed file: `data/book/cicd-pipeline/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent hardening pass materially improved this dataset. The interview is
now much closer to a production-grade CI/CD control-plane design, not just a
high-level delivery-platform story. The earlier major gaps around stage/job
state, approvals, idempotency, environment history, mobile release state,
deploy-time admission, capacity sizing, rollout state, migration safety, and
supply-chain checks are now represented directly in the API, data model, step
prose, deep dives, traps, and final design.

The seven-step spine remains strong: build-box baseline, DAG orchestration,
affected-only feedback, immutable signed artifacts, progressive deployment,
automated gates/rollback, then mobile release. Each step exposes a realistic
new constraint before adding the next component. The dataset is now suitable as
a strong book case.

The remaining work is narrower: add more end-to-end sequences for the stateful
workflows, expand trade-off options beyond orchestration and rollout strategy,
make flaky-test/merge-queue operations first-class, clarify capacity at burst
and p95 cases, and make the external feature-flag dependency concrete enough
for mobile and cross-client releases.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.55/5 | Strong control-plane model, state machines, admission, and rollout safety; remaining gaps are mostly workflow depth and edge cases. |
| Production realism | 4.35/5 | Good treatment of runners, cache trust, artifacts, approvals, mobile stores, gates, audit, and idempotency; flaky-test ops, queue fairness, and flag ownership need more emphasis. |
| Pedagogical flow | 4.45/5 | Clear progression with useful concepts, traps, options, and deep dives; a few more alternatives would make the decision tree more instructive. |
| Dataset/rendering fit | 4.70/5 | JSON parses and references resolve; structured views/options/flows are valid; only minor content-shape polish remains. |
| Overall | 4.50/5 | A strong CI/CD interview dataset with credible production mechanics and a few focused improvements left. |

## What Works Well

- The previous control-plane weakness is largely fixed. The data model now has
  `run_stages`, `jobs`, `job_attempts`, `approvals`,
  `environment_versions`, `deployment_steps`, `mobile_releases`,
  `audit_events`, and `idempotency_keys`.
- The API now exposes realistic operations: log lookup, job rerun, run cancel,
  approval/rejection, pause/resume, rollback, environment history, mobile
  release creation/status, and mobile halt.
- Capacity is much more useful. It sizes peak commit rate, affected targets,
  job count/duration, Linux warm vCPU slots, macOS scarcity, cache footprint,
  artifact/log retention, latency, and deploy cadence.
- The supply-chain story is now end to end: OIDC-style runner identity,
  SBOM/scanning, signed provenance, protected-branch signal, and deploy-time
  admission that fails closed.
- The rollback step now treats rollout as a state machine and adds the right
  deep dives: expand/contract migration and gate policy inputs with thresholds,
  windows, and sample-size concerns.
- Mobile is no longer hand-waved. It models store tracks, review state,
  callback/polling, staged rollout, crash gates, halt/forward-fix, version
  skew, `min_backend_version`, and kill switches.
- Options were added where they matter most: DAG orchestration compares
  Kubernetes-native runners, Jenkins-style controllers, and managed CI; deploy
  compares canary, blue-green, and rolling update.
- Renderer-facing checks are clean: step/final nodes and links resolve,
  option-view nodes and links resolve, sequence participants resolve,
  `satisfies[*].steps[*]` resolve, and `technologyChoices[*].steps[*]`
  resolve.

## Highest-Impact Issues

### 1. The state model is strong, but workflow sequences are still sparse

The data model now captures the right entities, but only three steps have
sequence flows (`orchestrate`, `deploy`, `mobile`), and the final design has no
structured flow. That leaves some of the newly added state machines less
visible than they should be.

Recommended edits:

- Add a final-design flow from webhook to DAG scheduling to artifact creation
  to deploy admission to rollout gate.
- Add a deployment approval flow: `POST /deployments`, policy check,
  pending approval, approval decision, GitOps revision, rollout start.
- Add a rollback flow that includes gate failure, pause/abort,
  `rollback_in_progress`, previous-good traffic shift, and post-rollback
  verification.
- Add a mobile store-state flow that includes upload, review callback/poll,
  staged rollout, crash-gate halt, and forward-fix linkage.

### 2. Fast-feedback scaling is good, but the alternatives are under-taught

The affected-target graph and cache correctness deep dive are strong. The
design also mentions merge queues and speculative pre-merge testing as a
follow-up, but this is a major CI/CD scaling topic and should be closer to the
main path.

Recommended edits:

- Add options under `fast-feedback`: affected-only builds plus cache, remote
  build execution, test selection, and brute-force full rebuild with massive
  parallelism.
- Add a short merge-queue sequence or deep dive covering stale green PRs,
  batching, speculative execution, and how to preserve main-branch health.
- Clarify cache bandwidth and p95 shared-library changes. A 25-target p95 run
  can saturate cache egress and runner slots even if the average PR looks
  small.
- Distinguish "120 warm vCPU-slots" from runner count. Candidates may need to
  translate slots into pod concurrency, per-job CPU/memory, and autoscaler
  headroom.

### 3. Flaky-test operations are still mostly a follow-up

The API supports rerunning a failed/flaky job as a new attempt, and the follow
ups ask about flaky tests. That is a good start, but in real CI/CD systems
flaky tests are a core reliability and trust problem. If the platform lets
reruns turn red into green without audit, the pipeline can become unsafe.

Recommended edits:

- Add a `test_results` or `quality_signals` record with test identity,
  historical flake rate, owner, quarantine state, and confidence.
- Add a trap for "rerun until green" and the safer behavior: record every
  attempt, require bounded reruns, quarantine known flakes, and keep a signal
  visible to owners.
- Add a failure drill for a flaky integration suite that either blocks all PRs
  or lets regressions through.
- Mention how merge queues interact with flakes: one flaky batch can starve the
  queue or hide which PR caused the failure.

### 4. Feature flags are correctly scoped as external, but the dependency is too implicit

The final design says feature flags are external to the CI/CD platform but
required for safe mobile and cross-client releases. That is a reasonable scope
choice, but the design should still define the contract because several safety
claims depend on it.

Recommended edits:

- Add a lightweight `FlagService` external node, or explicitly add flag
  dependencies to `mobile_releases` and `deployment_steps`.
- Record flag ownership, rollout percentage, kill-switch state, audit history,
  and dependency on `min_backend_version`.
- Add a flow for a server/web/mobile feature coordinated by flags: backend
  compatible deploy first, web active-pointer flip, mobile staged rollout,
  flag ramp, and kill switch.
- Add a failure drill for deleting or misconfiguring a flag while old mobile
  clients are still active.

### 5. Mobile is strong, but could teach one more trade-off

The mobile step is now realistic. It would teach better if it included at
least one explicit option, because mobile build and release infrastructure has
real cost and operational trade-offs.

Recommended edits:

- Add options for self-hosted macOS runners plus Fastlane, managed mobile CI,
  and a hybrid approach where Linux builds Android while scarce macOS capacity
  handles iOS signing/builds.
- Add one deep dive for mobile signing material: certificate/profile expiry,
  key rotation, app-store role permissions, and emergency revocation.
- Add a failure drill for app-store rejection or metadata/privacy-form failure,
  not only crash or backend incompatibility.

### 6. Some data-model fields are compressed for readability

Several data model entries combine multiple fields into one label, such as
`queued_at / started_at / ended_at`, `signed / attestation_ref`,
`actor / policy`, and `store_submission_id / review_status`. This renders
readably, but it blurs the schema if a reader treats the data model as a
literal contract.

Recommended edits:

- Split combined field names into separate fields where they represent
  independently queried or indexed values.
- Keep grouped wording only in notes, not in field names.
- Add indexes/partition hints for the high-cardinality tables: run by repo and
  commit, job attempts by job, logs by object-store pointer, audit events by
  target and time, environment history by environment and version.

## System Design Soundness

The design is now sound at the architecture level. A VCS webhook enters a
trigger, the orchestrator persists a run/stage/job/attempt model, ephemeral
runners execute the DAG, cache and affected-target logic reduce work, immutable
signed artifacts land in the registry, and the deployment controller promotes
verified versions through environments. Observability gates close the loop for
server/web rollback, while mobile takes an explicitly asynchronous store path.

The most important invariant, build once and promote the same signed digest,
is now backed by concrete mechanics: SBOM, scan result, provenance, signature,
short-lived runner credentials, and deploy-time admission. That is the right
answer for a modern CI/CD system.

The capacity model is now credible enough for an interview. It gives a
candidate numbers to reason about queueing, affected-target fan-out, warm
capacity, macOS scarcity, cache hit rate, retention, and deploy cadence. The
next precision improvement is p95 and burst analysis: p95 shared-library
changes, cache egress, and macOS saturation can dominate the average case.

The state-machine coverage is also much improved. Deployment states include
approval, ramping, pause, abort, live, rollback, and rolled-back. Mobile
release states include review, rollout percentage, and crash gate. The design
should now add sequences that make those transitions visible.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Script on a Build Box

This remains a good baseline. The added numeric example, 40 services times
roughly 8 minutes leading to multi-hour serial work, gives the reader a real
reason to need parallelism, affected builds, and caching. The trap against
shipping the build-box script as "good enough CI/CD" is useful.

### Step 2: Model the Pipeline as a DAG on Ephemeral Runners

This step is now much stronger. It introduces durable run/stage/job/attempt
state, runner leases, retry policy, queue/start/end timing, and log pointers.
The options are valuable because Jenkins-style, Kubernetes-native, and managed
CI systems really do fail differently. Consider adding a small note on queue
fairness between PR, main, release, and mobile jobs.

### Step 3: Fast Feedback: Affected-Only Builds + Caching

The cache correctness deep dive is one of the best additions. It covers content
keys, untrusted PR write restrictions, correctness fallback, and hit-rate
observability. The remaining gap is strategy comparison: remote execution,
test selection, and merge queues deserve explicit treatment because they are
common senior-level follow-ups.

### Step 4: Immutable, Signed Artifacts

This is now production-grade for the interview scope. The step connects
artifact immutability to provenance, SBOMs, scan results, vault-backed signing,
short-lived credentials, and admission. The traps are practical and
high-signal. Splitting the combined artifact fields in the data model would
make the schema clearer.

### Step 5: Progressive Delivery for Services + Web

The added options make this step teach trade-offs rather than a single
preferred path. Canary, blue-green, and rolling update are compared with
practical pros and cons. The web/CDN compatibility note is important and should
remain. A sequence for approval -> GitOps desired state -> active rollout would
make the control plane easier to visualize.

### Step 6: Automated Gates + Rollback

This step now has the right operational depth. The expand/contract migration
deep dive fixes the previous rollback oversimplification, and gate policy
inputs are specific enough to prevent "metrics healthy" hand-waving. Add a
sequence for rollback states and a drill for insufficient canary traffic or
false-positive gates.

### Step 7: Mobile Release Pipeline

The mobile contrast lands well and is now appropriately stateful. Store tracks,
review state, callback/polling, crash-free sessions, staged rollout, halt, and
version skew are all present. The next teaching improvement is an explicit
mobile infrastructure option set and a deep dive on certificates/profiles/store
permissions.

## Final Design Review

The final design integrates the right components: developer, Git host, trigger,
orchestrator, pipeline state store, runner pool, cache, registry, signing,
deployer, Kubernetes runtime, CDN, app stores, observability gates, and GitOps.
The description now captures the control-plane contracts rather than only the
boxes.

Two refinements would make it stronger. First, add at least one final-design
flow so readers can see how the state store, admission checks, approvals, and
gates interact across the whole system. Second, make the feature-flag
dependency explicit, either as an external node or as a named contract in the
mobile and deployment state models.

## Concept Introduction and Learning Flow

Concept staging is strong. Hermetic builds, idempotency, runner trust
boundaries, affected target graphs, provenance, SBOMs, canaries, error-budget
gates, expand/contract migration, staged rollout, review state, and version
skew are introduced close to where they are used.

The overview concepts page should now be useful because the dataset has enough
per-step concepts to form a coherent glossary. The main additions I would make
are merge queue, flaky-test quarantine, rollout sample size, and feature-flag
ownership.

## Step-to-Final-Design Coherence

The step-to-final-design mapping is coherent. Every final-design node is
introduced in the steps, and the `satisfies` section ties requirements to the
right parts of the walkthrough. The recent additions also close most of the
old promise-versus-model gaps: approvals, logs, policy gates, audit, mobile
store state, idempotency, and deployment state are now represented.

The remaining coherence issue is mostly visual/flow-based. The final diagram
shows the components, but the most important product behavior is in the
stateful transitions. Additional sequence flows would bridge that gap without
adding more boxes.

## Realism Compared With Production Systems

This is now realistic for a senior system design interview. It covers the
operational mechanics that often separate a generic CI/CD answer from a real
delivery platform: ephemeral runner isolation, content-keyed caches,
untrusted-PR restrictions, immutable artifacts, signed provenance, admission,
GitOps, durable approvals, audit, rollout gates, migration compatibility,
mobile store state, and version skew.

The main production areas still underrepresented are flaky-test governance,
merge-queue starvation, quota management across runner pools, and feature-flag
operations. Those are not fatal omissions, but they are common pain points in
large CI/CD systems and would make the case feel even more battle-tested.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- The dataset uses structured `view.nodes` and `view.links`; no raw Mermaid
  architecture diagrams are used in steps or final design.
- Step view nodes and links resolve against `highLevelArchitecture`.
- Option view nodes and links resolve against `highLevelArchitecture`.
- Final-design view nodes and links resolve against `highLevelArchitecture`.
- Sequence participants resolve to canonical node IDs.
- `satisfies.functional[*].steps` and `satisfies.nonFunctional[*].steps`
  resolve to existing steps.
- `technologyChoices[*].steps` resolve to existing steps.
- High-level architecture node types are canonical.
- The dataset now has options on `orchestrate` and `deploy`, and deep dives on
  `fast-feedback`, `artifacts`, `deploy`, and `rollback`.
- The dataset has no `probeLinks`, `aiVisual`, `explainerComic`, or generated
  requirement illustrations. This is optional enrichment, not a correctness
  issue.
- Minor polish: `POST /deployments/{id}/pause` says "pass action"; consider
  rewording to "takes `{ action: 'pause'|'resume' }`" for clarity.

## Recommended Edits, Prioritized

### P1: Add end-to-end workflow sequences

Add final-design and per-step flows for approval, deploy admission, rollback,
and mobile store-state transitions. This will make the newly improved state
model visible to readers.

### P1: Promote flaky-test and merge-queue operations from follow-up to content

Add a small data model/API/deep-dive treatment for flaky tests, bounded reruns,
quarantine, ownership, merge queues, speculative execution, and queue
starvation.

### P2: Add fast-feedback and mobile option sets

Add options for remote execution/test selection/merge queues under
`fast-feedback`, and self-hosted versus managed mobile CI under `mobile`.

### P2: Make feature-flag dependency explicit

Represent flags as an external node or a named state-model dependency with
ownership, audit, rollout percentage, kill-switch state, and version
compatibility.

### P3: Normalize compressed data-model fields

Split slash-combined field labels into individual fields and add index or
partition hints for high-cardinality records.

### P3: Add optional enrichment assets

Consider `probeLinks`, generated AI visuals, requirement illustrations, or an
explainer comic after the content pass. These are presentation enhancements,
not blockers.

## What Not To Change

- Keep the seven-step spine. It is coherent and still the right teaching order.
- Keep mobile as the final step. The contrast works best after server/web
  rollback is already established.
- Keep build-once-promote-everywhere as the central invariant.
- Keep the current control-plane state model; it is the biggest improvement in
  the current version.
- Keep the deploy-time admission deep dive and the expand/contract migration
  deep dive. They are high-value senior-level teaching content.
- Keep feature flags scoped as external if you do not want another platform
  subsystem, but define the dependency clearly.

## Bottom Line

The recent changes successfully moved this CI/CD interview from a good
architecture walkthrough to a credible production control-plane design. The
next pass should not add many more boxes; it should add workflow sequences and
operational depth around flaky tests, merge queues, feature flags, and mobile
infrastructure trade-offs.
