# Review: AI Coding Agent CLI (Claude Code / Codex)

Reviewed file: `data/book/ai-coding-cli/interview.json`
Review date: 2026-06-12

## Executive Summary

This is a strong, modern system-design walkthrough for a terminal AI coding
agent. The step sequence is coherent: naive prompt-to-patch, agent loop,
context engineering, compaction, permissions/sandboxing, inference economics,
verification, and headless cloud agents. The strongest parts are the harness vs.
model framing, the safety model, the prefix-cache explanation, and the
pedagogical traps/signals around each step.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Strong architecture, but API/state contracts are thinner than the design they support. |
| Production realism | 4/5 | Good treatment of prompt injection, sandboxing, leases, cost, and evals; needs more explicit state, audit, and capacity sizing. |
| Pedagogical flow | 4/5 | The progression is excellent; several complex steps need structured flows to make the mechanics teachable. |
| Dataset/rendering fit | 5/5 | JSON parses; view nodes/links/highlights and sequence references resolve cleanly. |
| Overall | 4/5 | Publishable and compelling, with a few high-leverage edits before it becomes a flagship case. |

## What Works Well

- The topic is timely and differentiated from standard CRUD/platform cases. It
  teaches system design around an untrusted, tool-using model rather than
  treating the model as a black-box API.
- The roadmap is crisp. Each step answers a real failure exposed by the
  previous one, and the `recap.newRisk` fields keep the interview moving.
- The safety section is unusually strong: policy vs. sandbox, prompt injection,
  egress control, autonomy tied to isolation, and denial as a tool result are
  all production-relevant.
- The inference section correctly derives prefix caching and cache-aware routing
  from append-only agent transcripts, which is the core workload insight.
- The wrap-up fields are well populated: `satisfies`, `interviewScript`,
  `levelVariants`, `followUps`, and `technologyChoices` all reinforce the case.

## Highest-Impact Issues

### 1. API and state contracts do not yet carry the design's operational complexity

The prose depends on permissions, resumable sessions, idempotent cloud tasks,
task leases, scoped credentials, auditability, and PR delivery. The current API
and data model are much thinner:

- `POST /v1/tasks` has no idempotency key, repo authorization model,
  target branch, policy/autonomy mode, callback/stream contract, or PR metadata.
- `tasks` lacks lease owner, heartbeat deadline, attempt number, branch name
  lifecycle, PR URL, terminal error fields, timestamps, and a task event log.
- `permission_rules` lacks account/user/project ownership, path scopes,
  command match semantics, precedence, expiry, source of rule, and audit fields.
- `sessions` does not model pinned task constraints, compaction digests,
  full-transcript vs. in-window transcript, or resume checkpoints.
- `usage_events` has no session/request/task linkage, cache-hit metadata beyond
  token counts, latency fields, or error/retry outcome.

Why it matters: later steps teach production mechanisms that are not visible in
the contract. A candidate could repeat the architecture but still not know what
has to be persisted or exposed to operate it.

Concrete fix: expand the API/data model around three state machines: permission
decision, local session, and cloud task. Add a `task_events` entity, explicit
lease/heartbeat/idempotency fields, permission audit fields, and request/session
IDs on usage records.

### 2. Verification and evals are conceptually strong but not first-class in the architecture

Step 6 correctly says that tests, typecheck, lint, build, git checkpoints, and
subagents close the truth loop. Step 7 also introduces evals as release
infrastructure. In the diagram, however, these are mostly implicit inside
`Sandbox` and `Telemetry`.

Why it matters: "verified changes" is one of the non-functional requirements.
If the final architecture does not show the check runner/eval path explicitly,
the most important quality control looks like prose rather than a system
component.

Concrete fix: add either a `Verifier / Check Runner` node or a structured flow
that shows baseline checks, edit, run checks, feed failures back, checkpoint
with git, and report a diff. For cloud, show eval execution and rollout gating
as a real operational path, not just telemetry text.

### 3. Several complex behaviors need structured sequence flows

The dataset has good sequence flows for the agent loop, permission decision,
and inference call. The most operationally subtle steps do not have flows:

- `context`: agentic search vs. optional index retrieval.
- `compaction`: threshold trigger, pinned content, digest creation, resume from
  full transcript, and mandatory re-read of stale files.
- `verify`: baseline test run, edit, failed test feedback, bounded retry,
  checkpoint, and final diff.
- `cloud`: enqueue task, lease/heartbeat, clone with scoped token, headless loop,
  push branch, open PR, and retry on sandbox death.

Why it matters: these are exactly the areas where candidates tend to hand-wave.
The prose is good, but rendered sequence diagrams would force the state
transitions and failure boundaries into the candidate's answer.

Concrete fix: add one structured `flows[]` entry each for `compaction`,
`verify`, and `cloud` first. The cloud flow should be the highest priority
because it ties together task queueing, credentials, idempotency, and PR output.

### 4. Capacity planning stops before the operational bottlenecks

The capacity section is useful on LLM calls and token volume. It clearly states
~1M daily active developers, ~80M model calls/day, ~4T input tokens/day, and a
prefix-cache hit target. What is missing is the next layer of sizing:

- concurrent interactive sessions at peak;
- cloud sandbox concurrency and queue depth;
- transcript/session storage growth;
- task event and telemetry volume;
- prefix-cache memory/TTL/eviction expectations;
- package/git egress and artifact storage;
- GPU capacity rough order of magnitude for cold vs. warm prefixes.

Why it matters: the interview teaches cost and latency as first-class concerns,
but the candidate never has to translate traffic into storage, queue, sandbox,
or cache sizing.

Concrete fix: add 4-6 capacity rows for session storage, active sandboxes,
queue depth, task event volume, and prompt-cache footprint. Keep them rough; the
goal is to force design consequences, not exact fleet procurement.

### 5. Trust boundaries around local project instructions and extensibility need sharper wording

The safety section treats repo content as untrusted input, which is correct.
The context section also promotes project memory files (`CLAUDE.md` /
`AGENTS.md`) as durable instructions loaded every session. That creates a subtle
trust-boundary question: project memory is repo content but also instruction.

Why it matters: this is a central real-world ambiguity for coding agents. A
malicious or compromised repository can place "project instructions" in the same
channel as trusted user intent.

Concrete fix: state the precedence model explicitly. For example: user/session
instructions outrank checked-in project memory; project memory is treated as
repo-scoped guidance, never as authority to expand permissions; commands or
egress requested by project memory still pass policy and sandbox gates. The MCP
or third-party tool follow-up could become a small mainline note in the safety
or API section because extensibility directly affects the permission model.

## System Design Soundness

Requirements are well chosen and map to the steps. The functional list covers
local code changes, tool use, permission approval, large repos, streaming,
resume, and cloud PR delivery. The non-functional list covers UX, safety, cost,
reliability, and quality. Consider adding enterprise privacy/audit and
multi-tenant account isolation as explicit non-functional concerns, because the
technology choices and follow-ups already imply enterprise use.

Capacity is directionally strong for the model path. The best insight is that an
agent session is many model calls, not one user message. The main gap is that
capacity does not yet drive non-model infrastructure: queue depth, sandbox
fleet, session storage, event logs, and prompt-cache footprint.

The API section is currently provider-facing rather than product-complete. It
describes `/v1/messages`, cloud tasks, task status, and usage, but omits the
local harness contracts that the design depends on: permission decisions,
session resume, tool event streaming, diff/artifact metadata, idempotency, and
task event history.

The data model captures the right nouns but not enough lifecycle. `sessions`,
`permission_rules`, `tasks`, and `usage_events` are good anchors. They need
ownership, status transitions, event logs, timestamps, retry/lease fields, and
audit metadata to support the failure drills already described in the steps.

The architecture components are credible and use the canonical node types well.
The final design includes all major components introduced during the walkthrough.
The only architectural visibility gap is that verification/evals and task event
state are too implicit.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One-Shot Prompt to Patch

Strong baseline. It exposes blindness, lack of feedback, and unsafe writes
without inventing premature infrastructure. The traps are useful because they
stop candidates from jumping straight to embeddings or "just paste the repo."

Improvement: add one sentence that the naive path can still be a product mode
for tiny edits, but must be explicitly scoped and diff-only. That preserves the
teaching value without making the baseline sound entirely useless.

### Step 2: The Agent Loop: Tool Use

This is one of the best sections. The harness/model split, small orthogonal tool
catalog, patch-style edits, tool-result truncation, and loop termination are
exactly the right core. The sequence flow is concrete and useful.

Improvement: include tool-call IDs or idempotency in the flow or prose. If a
stream breaks after the model emits a tool call, the harness must know whether
it already executed the mutation before retrying.

### Step 3: Context Engineering for Large Repos

The agentic-search-first stance is well argued and realistic. The option
comparison is balanced: freshness/privacy/debuggability vs. semantic recall and
monorepo scale. The project-memory discussion makes the dataset feel grounded
in actual coding-agent practice.

Improvement: clarify trust and precedence for project memory. It should guide
the agent but not grant authority, especially when loaded from an untrusted repo.

### Step 3a: Compaction: Surviving Long Sessions

Good sub-step. It cleanly separates full-fidelity session storage from the
lossy in-window digest, and the stale-file trap is important.

Improvement: add a structured compaction flow and a data-model field for
compaction digests/pinned content. This would make the "what survives verbatim"
decision visible.

### Step 4: Permissions & Sandboxed Execution

Excellent section. The separation between policy and sandbox is the right
answer, and the failure drills are practical. Denial as a tool result is a
particularly useful teaching point.

Improvement: make permission rules more concrete in the data model. Include
path scopes, command pattern semantics, rule source, precedence, expiry, and
audit records. Approval prompts need these fields to avoid becoming vague UX.

### Step 5: Streaming & the Inference Backend

Strong system insight. The step explains why prefix caching matters, why
append-only transcripts are a harness constraint, and why routing must be
cache-aware. It also covers model tiering, metering, and retry/backoff.

Improvement: add capacity implications for cache memory, cache eviction, and
fallback behavior when affinity cannot be preserved. Also specify stream resume
semantics: event IDs, duplicate deltas, and whether tool calls can be replayed.

### Step 6: Verify & Iterate: Tests, Git, and Subagents

The content is strong: verification by external checks, baseline red tests,
bounded retries, reward hacking, git checkpoints, and worktree isolation are all
production-realistic.

Improvement: make verification a flow or a visible architectural path. This
step is central enough that it should not be inferred from the sandbox node.

### Step 7: Background & Cloud Agents at Scale

The cloud section is credible and well staged. Queue leases, branch-per-task
idempotency, short-lived scoped tokens, egress controls, PR review, metering,
abuse detection, and eval gating are the right concerns.

Improvement: add the cloud sequence flow and harden the task model. The prose
mentions leases and idempotency, but the API/data model should prove that the
system can recover from preemption without duplicate PRs or lost status.

## Final Design Review

The final design integrates the steps well: local CLI, agent loop, policy,
sandbox, repo, sessions, optional index, subagents, model gateway/router/cache,
usage, telemetry, cloud orchestrator, queue, cloud sandbox fleet, and git host.
The final `description` is concise and accurate.

The main gap is not missing components; it is missing lifecycle visibility. A
reader can see the boxes but not the state machines for permissions, sessions,
verification, and cloud task execution. Adding a few flows and data fields would
make the final design feel much more production-grade.

## Concept Introduction and Learning Flow

Concepts are introduced at the right time. "Completion vs. agent" precedes the
loop; "context window" precedes context engineering; prompt injection and blast
radius arrive before cloud autonomy; prefill/decode arrives before prefix
caching; subagents arrive after context and cost are established.

The weakest concept gap is idempotency. It appears in the cloud recap, but it
should be introduced as a named concept before the cloud step relies on it.
Tool-call replay, task retry, branch-per-task output, and queue leases all
depend on idempotency.

## Step-to-Final-Design Coherence

The steps build cleanly into the final diagram:

- Step 1 introduces `CLI`, `Gateway`, `LLM`, and `Repo`.
- Step 2 inserts `AgentCore` and `Sandbox`.
- Step 3 adds `SessionStore` and optional `CodeIndex`.
- Step 4 adds `Policy` and hardens `Sandbox`.
- Step 5 adds `Router`, `PromptCache`, and `Usage`.
- Step 6 adds `Subagents`.
- Step 7 adds `CloudOrch`, `TaskQueue`, `CloudSandbox`, `GitHost`, and
  operational telemetry.

This is a good spine. The only coherence issue is that verification/evals are
important in the narrative but do not become a distinct visible node or flow.

## Realism Compared With Production Systems

The dataset is realistic about the hard parts most AI-agent designs miss:
prompt injection, approval fatigue, sandbox egress, append-only prompt caching,
model tiering, baseline test failures, reward hacking, worktree isolation,
leases, scoped credentials, and eval harnesses.

The remaining realism gaps are mostly around operations:

- audit logs for approvals, denials, tool calls, and cloud task actions;
- secrets handling and redaction in prompts, logs, and telemetry;
- package registry/network allowlists and how they interact with builds;
- enterprise zero-data-retention modes and whether provider prompt caches are
  allowed;
- rollout/canary metrics for model, prompt, and harness changes;
- support/debug tooling for failed sandboxes and stuck sessions.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- All nested `view.nodes` references resolve to `highLevelArchitecture.nodes`.
- All nested `view.links` references resolve to `highLevelArchitecture.links`.
- All nested `view.highlight` IDs are present in their local view.
- Sequence messages reference participants declared in their sequence.
- `satisfies[*].steps[*]` and `technologyChoices[*].steps[*]` resolve to real
  step IDs.
- Node types are canonical: actor, cache, client, database, external, gateway,
  index, model, object-storage, observability, orchestrator, queue, service,
  and worker.
- The dataset is registered in the `AI-Era Systems` category in both source and
  generated book manifests.

No renderer-facing defects were found during this review.

## Recommended Edits, Prioritized

### P1: Expand API and data model state

Add task idempotency, task events, leases/heartbeats, PR metadata, permission
audit fields, session compaction metadata, and usage request/session linkage.

### P1: Add cloud task sequence flow

Show `POST /v1/tasks`, enqueue, lease, clone with scoped token, headless loop,
heartbeat, push branch, open PR, and retry on sandbox death.

### P1: Make verification visible

Add a verification flow or a check-runner/verifier path showing baseline checks,
edit, failed-check feedback, bounded retry, checkpoint, and final diff.

### P2: Add capacity rows for non-model infrastructure

Cover active sessions, active cloud sandboxes, task queue depth, transcript
storage, task event volume, telemetry volume, and prefix-cache footprint.

### P2: Tighten trust-boundary language for project memory and plugins

State precedence and authority explicitly: project memory guides behavior but
does not grant permissions; third-party tools/context sources must be mediated
by the same policy and sandbox model.

### P3: Add idempotency as a named concept

Introduce idempotency before the cloud step, then reuse it for tool-call replay,
task retry, and branch-per-task output.

### P3: Add captions to option views where the diagram difference is subtle

The context and safety options are good, but short `view.caption` fields would
help readers notice what changed in each option.

## What Not To Change

- Preserve the step order. It is one of the dataset's strengths.
- Keep agentic search as the default and embedding index as an option; that is a
  useful, opinionated teaching point.
- Keep the policy/sandbox separation and the prompt-injection framing.
- Keep prefix caching as a central backend insight, not a minor optimization.
- Keep the `interviewerSignals`, `traps`, and `failureDrills`; they make the
  interview practical instead of just architectural.

## Bottom Line

This is a strong case study with a clear narrative and production-aware
trade-offs. The next improvements should not broaden the scope; they should make
the existing scope more concrete by adding state machines, sequence flows, and
capacity rows for the operational mechanisms the prose already describes.
