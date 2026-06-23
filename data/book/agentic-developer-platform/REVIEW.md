# Review: Agentic Developer Platform - System Design

Reviewed file: `data/book/agentic-developer-platform/interview.json`
Review date: 2026-06-23

## Executive Summary

This is a strong, focused dataset for the agentic-platform vertical. It has a
clear thesis - a fleet of coding agents is safe only when code changes stop at a
draft PR and merge/deploy remains a separate human-owned gate - and the step
sequence builds that thesis cleanly from baseline, to repo grounding, to fleet
isolation, to verification, to prompt-injection defense, to operations.

The biggest gap is that several production-control planes are still compressed
into prose. Capacity has no real sizing numbers, task scheduling lacks conflict
and lease/idempotency detail, the repo index is modeled without freshness or
authorization metadata, and merge/deploy governance is described but not carried
by explicit entities. There are also three small diagram-view endpoint issues
that can create implicit Mermaid nodes.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.20/5 | Strong architecture spine; needs concrete capacity, task state, index freshness, and merge/deploy governance. |
| Production realism | 4.05/5 | Good sandboxing, scoped credentials, prompt-injection framing, and gates; conflict handling, secret/egress policy, and provider workflows need more state. |
| Pedagogical flow | 4.45/5 | The seven-step journey is coherent and interview-friendly; a few steps would benefit from more options or sequence flows. |
| Dataset/rendering fit | 4.30/5 | JSON parses and most references resolve; three view links omit endpoint nodes. |
| Overall | 4.25/5 | Strong book-quality case with specific production-depth edits left. |

## What Works Well

- The scope is sharp: it distinguishes an org-scale cloud fleet from a local AI
  coding CLI and explicitly depends on the shared Agentic Platform Foundations
  substrate instead of re-teaching it.
- The two-stage gate is the right central invariant. The dataset repeatedly
  reinforces that a draft PR is reversible, while merge/deploy can trigger
  external effects that code revert does not undo.
- The architecture contains the right major nodes: gateway, supervisor, queue,
  coding agent, sandbox, inference, repo index, VCS, CI, guardrail, identity,
  durable log, and observability.
- The step recaps work well. Each step exposes the next risk, so the walkthrough
  feels like an interview answer being assembled rather than a component dump.
- The security step is appropriately specific for coding agents: repo text,
  issue text, PR comments, dependency docs, and CI logs are attacker-reachable
  input, not trusted internal context.
- The wrap-up material is concise and aligned. `satisfies`, `interviewScript`,
  `levelVariants`, and follow-ups reinforce the main teaching points.

## Highest-Impact Issues

### 1. Capacity is qualitative, so the fleet cannot be sized

The capacity section has only three qualitative rows: "fleet-scale",
"ephemeral, per task", and "async". Those statements are directionally right,
but they do not force the candidate to size the hard bottlenecks: concurrent
sandboxes, task duration, queue depth, repo checkout/cache pressure, CI minutes,
index update load, token spend, and trajectory storage.

Why it matters: without numbers, admission control stays a slogan. A production
agentic developer platform is dominated by expensive, stateful resources:
microVMs, working copies, CI runners, LLM calls, and code-index storage. The
design should make candidates translate task arrival rate and p95 task duration
into concurrency and backpressure.

Concrete fix: add capacity rows such as tasks/day, peak task submissions/min,
average and p95 task duration, concurrent sandbox target, warm-pool size, repo
checkout/cache footprint, index size per MLOC, incremental re-index events/day,
CI runner minutes, trajectory/event storage, and per-tenant queue limits. Update
`capacityDiagram` to show at least two bottleneck branches: sandbox/CI capacity
and index/inference/trajectory capacity.

### 2. The task lifecycle is under-modeled for exactly-once resume

`tasks` has only `queued,running,pr_open,merged,failed`, and `run_events.kind`
only includes `plan,edit,test,push,pr_open`. The prose promises async,
resumable, exactly-once execution, but the data model has no lease, attempt,
heartbeat, idempotency key, dedup key, cancellation state, retry policy, branch
name, commit SHA, PR id, lock ownership, timeout, or resume cursor.

Why it matters: long-running coding tasks fail in messy ways. A worker can die
after pushing a branch but before recording the PR, a webhook can submit the
same task twice, CI can finish after the task is marked failed, or two attempts
can race on the same branch. Those are the cases where "exactly-once resume"
needs real state.

Concrete fix: expand `tasks` with `tenant_id`, `repo_id`, `request_id` or
`idempotency_key`, `attempt`, `lease_owner`, `lease_expires_at`,
`branch_name`, `head_sha`, `pr_id`, `last_event_seq`, `retry_policy`,
`cancel_requested_at`, and terminal reason. Expand `run_events.kind` to cover
checkout, retrieve, tool_call, patch, test_start, test_result, push_branch,
ci_status, pr_opened, review_event, lease_renewed, and cancellation.

### 3. Parallel-agent conflict handling is a follow-up, but it should be in the mainline

The requirements say many agents run in parallel across repos, and the follow-up
asks how to stop two parallel agents from producing conflicting PRs on the same
files. That is an important question, but it is not only a follow-up: it is a
core operating problem for the fleet.

Why it matters: without a conflict policy, the platform can be safe at the
merge gate but still waste reviewer time by producing incompatible draft PRs,
rebasing forever, or repeatedly touching the same hotspot files. This directly
affects fairness, throughput, and merge rate quality.

Concrete fix: add a short mainline treatment in `fleet` or `async-obs`: repo or
path-level work-intent locks, branch naming and base-SHA capture, optimistic
rebase before PR, duplicate task detection, stale-base refresh, and a policy for
conflict cancellation versus retry. A small `work_intents` or `repo_locks` data
model item would make this teachable without overloading the diagram.

### 4. Repo indexing lacks freshness, authorization, and invalidation state

`repo_index` stores chunk id, repo, path, symbol, embedding, and graph edges.
That is enough to describe retrieval shape, but not enough to operate a
multi-repo, multi-tenant code corpus.

Why it matters: code retrieval is the vertical-specific substrate in this case.
If the index is stale or crosses authorization boundaries, the agent can edit
against the wrong code or leak private repo context across tenants. Incremental
re-index on push is mentioned, but the data model does not show commits,
versions, visibility, language/parser versions, tombstones, or rebuild status.

Concrete fix: add fields such as `repo_id`, `tenant_id`, `commit_sha`,
`indexed_at`, `chunk_hash`, `language`, `parser_version`, `visibility_scope`,
`deleted_at`, and `index_job_id`. Consider a separate `index_jobs` entity for
webhook-triggered indexing state, retry, lag, and backfill.

### 5. Merge/deploy governance is described but not represented as state

The gate step correctly names branch protection, required CI, code owners,
migration policy, progressive delivery, rollback, and constrained auto-merge.
However, the data model has no approval record, policy snapshot, code-owner
decision, deployment gate, rollout status, or audit event tied to the task.

Why it matters: the central lesson is that draft PR and merge/deploy are
different gates. If the model only stores `merged` on `tasks`, the strongest
concept in the interview has no durable representation. Candidates may leave
with a prose rule rather than a control-plane design.

Concrete fix: add `pr_reviews` or `gate_decisions` with actor, role, decision,
policy version, required checks, code-owner set, risk class, and timestamp. If
deploy is in scope, add `deployment_gates` or explicitly state that deployment
state belongs to the downstream CI/CD platform and this platform only links to
its evidence.

## System Design Soundness

The requirements are well scoped. Functional requirements cover async task
ingest, parallel agents, repo-context retrieval, draft PRs, and human-owned
merge/deploy. Non-functional requirements cover isolation, verification,
resumability, prompt-injection defense, and multi-tenant fairness.

The architecture is coherent and minimal. It avoids inventing a new CI/CD
system, source control system, or model-serving tier; those are correctly shown
as dependencies or inherited substrate. The main design path is sound: triggers
enter through an API, the supervisor queues and admits work, agents run in
isolated sandboxes with brokered credentials, retrieve repo context, verify
changes, open a draft PR, and emit trajectories.

The main soundness gap is that several promises do not yet have enough state:
exactly-once resume, admission control, repo-index freshness, and the second
gate. These do not require many more components, but they do require a few more
fields and one or two operational flows.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Agent, Direct Commit

This is a useful baseline. It makes the transition from local tool to platform
visible: one user, one task, full credentials, no isolation, no async trigger,
and no review gate. The trap is well chosen.

Improvement: the pattern tag points to orchestrator-workers even though the
baseline does not yet have an orchestrator or worker fleet. Consider leaving
step 1 untagged or using a "baseline/anti-pattern" pattern if the project ever
adds one.

### Step 2: Ground the Agent in the Codebase

This step correctly identifies repo context as the vertical-specific corpus.
The hybrid Tree-sitter plus code-graph option is the right recommended answer,
and the no-index option is useful as a realistic trade-off for small repos or
freshness-sensitive work.

Improvement: make index freshness and authorization visible here. A sequence
flow could show VCS webhook, index job, chunk/graph update, retrieval query,
and commit-SHA binding so the agent knows which version of the repo it used.

### Step 3: Run a Fleet: Supervisor + Ephemeral Sandboxes

This is the control-plane step and it mostly lands. Supervisor, queue, sandbox,
identity broker, and durable log are the right components. The trap against
shared sandboxes or shared tokens is production-relevant.

Improvement: add leases and conflict handling. This is the best place to teach
worker lease renewal, attempt numbering, queue fairness, per-tenant quotas,
work-intent locks, branch/base-SHA capture, and cancellation. Without those,
the fleet is safe in principle but not yet operable under retries and parallel
edits.

### Step 4: The Gate: Draft PR, Then Merge/Deploy

This is the strongest step. It names the central invariant and the reason it
exists: reverting source code is not the same as reversing deployed or data
effects. The sequence flow is concise and useful.

Improvement: represent the gate as durable state. The step would be stronger if
it added gate decisions, policy snapshots, reviewer identity, required checks,
code-owner review, risk class, and deploy evidence. If the actual deploy gate
belongs to a CI/CD platform, say that explicitly and store only the link/evidence
that proves the downstream gate passed.

### Step 5: Verify Before Proposing

The distinction between fast in-sandbox verification and PR CI as the source of
truth is correct. This prevents the common mistake of treating local checks as
the merge gate.

Improvement: make the verifier result more explicit. Add fields or events for
test command, exit code, log artifact, retry count, changed files, and final
commit SHA. That gives reviewers evidence and makes failed verification
observable instead of just a loop inside the sandbox.

### Step 6: Untrusted Repo Text

This is appropriately sharp. It names the exact injection surfaces and explains
why scoped credentials and egress controls matter. The deep dive on blast radius
is a good fit for the domain.

Improvement: split policy from enforcement if this grows. `Guardrail / Policy`
currently screens text and gates tool calls, while `Identity` mints tokens and
`Sandbox` constrains execution. A tiny flow for untrusted text -> tainted plan
-> allowed tool call -> brokered credential would make the boundary easier to
teach.

### Step 7: Async at Scale

The step closes the interview well by shifting from components to operations:
triggers, admission, trajectories, costs, and quality signals. The warning that
merge rate alone is a weak quality metric is valuable.

Improvement: this step is doing a lot with little structure. Consider adding a
sequence flow for trigger ingestion, queue admission, sandbox allocation,
trajectory emission, and reviewer audit. It is also the natural place for
SLOs, queue depth, tenant fairness, dead-letter handling, and quality dashboards.

## Final Design Review

The final design integrates the introduced components cleanly. It includes all
major nodes from the steps and keeps the two gates visible in prose. It also
correctly states that runtime, durability, identity, and observability come from
Agentic Platform Foundations.

The final design would become more production-grade if it named the task
state-machine and gate evidence explicitly. Right now, the final diagram has
`DurableLog` and `Observability`, but not the specific evidence records that
support exactly-once resume, reviewer audit, or deployment-gate proof.

## Concept Introduction and Learning Flow

The concept staging is strong: code-graph retrieval arrives when grounding is
introduced, "reverting code != reversing effects" arrives at the gate, and
untrusted repo text arrives once the agent has meaningful tool authority. That
is the right order.

The dataset could use one or two more concept chips: idempotency/lease for the
fleet, and index freshness/commit binding for repo grounding. Those concepts
are already implied; naming them would make the later operational story easier
to defend.

## Step-to-Final-Design Coherence

The final design includes the components introduced by the steps:

- `context` introduces `RepoIndex`, which appears in the final view.
- `fleet` introduces `Supervisor`, `TaskQueue`, `Sandbox`, `Identity`, and
  `DurableLog`, all present in the final view.
- `gate` and `verify` introduce `VCS`, `CI`, and reviewer ownership, all present
  in the final view.
- `security` introduces `Guardrail`, present in the final view.
- `async-obs` introduces `Trigger`, `Gateway`, and `Observability`, all present
  in the final view.

The coherence gap is not missing nodes; it is missing state. The final view has
the right boxes, but the supporting data model does not yet carry enough
information for retries, duplicate tasks, conflicting edits, index freshness,
or gate evidence.

## Realism Compared With Production Systems

Production systems in this space need to handle several messy workflows that
are only lightly represented here:

- Duplicate or replayed triggers from issues/webhooks/cron.
- Worker crashes after external side effects such as branch push or PR create.
- Parallel agents modifying the same files or generating incompatible PRs.
- Stale repo context after the base branch changes.
- Long-running sandboxes that need lease renewal, timeout, teardown, and
  artifact retention policy.
- CI provider ambiguity: pending checks, canceled runs, flaky tests, reruns, and
  checks arriving after task state changes.
- Secrets and egress policy per repo, task, tool, and tenant.
- Audit retention for trajectories that may contain source code or secrets.

The dataset does not need to solve every one in depth, but the top few should be
visible in the mainline because they are central to an org-scale coding-agent
platform.

## Dataset and Renderer-Facing Observations

JSON parsing succeeds. Step, pattern, and `satisfies` references resolve. Final
design nodes and links resolve. Canonical node types are used appropriately:
human reviewer is `actor`, trigger source is `client`, model is `model`, queue
is `queue`, index is `index`, and external systems are `external`.

There are three selected view links whose endpoint nodes are omitted:

- `steps/context/options[1]` uses `sandbox-vcs`, whose source is `Sandbox`, but
  the option view includes only `CodingAgent` and `VCS`.
- `steps/async-obs` uses `dev-trigger`, whose source is `Dev`, but the view
  omits `Dev`.
- `steps/async-obs` uses `agent-obs`, whose source is `CodingAgent`, but the
  view omits `CodingAgent`.

Recommended fix: either add the missing endpoint nodes to those view `nodes`
arrays or choose links whose endpoints are already visible. Otherwise Mermaid
can render implicit nodes that do not carry the intended labels/types.

## Recommended Edits, Prioritized

### P1: Add concrete fleet capacity and state-machine details

Add numeric capacity rows and expand `tasks` / `run_events` so async,
resumable, exactly-once execution has leases, attempts, idempotency, branches,
PR IDs, CI status, cancellation, and terminal reasons.

### P1: Model gate evidence for review and deploy

Add a compact `gate_decisions`, `pr_reviews`, or `deployment_evidence` model
that records reviewer identity, policy version, required checks, risk class,
approval state, and downstream deploy-gate proof.

### P2: Make repo-index freshness and authorization explicit

Extend `repo_index` and/or add `index_jobs` so retrieval is tied to tenant,
repo, commit SHA, parser version, index job state, and visibility scope.

### P2: Bring parallel-edit conflict handling into the mainline

Add a step paragraph, deep dive, or data model for work-intent locks,
duplicate-task detection, stale-base refresh, optimistic rebase, and conflict
retry/cancel policy.

### P2: Add one or two operational sequence flows

The most valuable flows would be task execution with lease/resume, index update
and retrieval, and async trigger -> queue -> sandbox -> trajectory emission.

### P3: Fix the three view endpoint omissions

Add `Sandbox` to the no-index option view or use `agent-vcs`; add `Dev` and
`CodingAgent` to the `async-obs` view or remove/replace `dev-trigger` and
`agent-obs`.

### P3: Consider scoped privacy/retention wording

Because trajectories and retrieved context can include source and secrets, add a
sentence or field covering redaction, retention class, and who may view
trajectory spans.

## What Not To Change

- Keep the two-stage gate as the center of the case. It is the strongest and
  most distinctive teaching point.
- Keep CI/CD and model serving as dependencies rather than re-building those
  systems inside this interview.
- Keep the step order. It introduces each risk just in time and makes the final
  design easy to reconstruct.
- Keep the prompt-injection section focused on repo text and tool authority; it
  is sharper than a generic "LLM safety" discussion.

## Bottom Line

This is already a credible and teachable book dataset. The next revision should
not add more boxes for their own sake; it should make the existing promises
operational by adding capacity numbers, task lifecycle state, repo-index
freshness, conflict handling, and durable gate evidence.
