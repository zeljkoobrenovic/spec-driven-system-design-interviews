# Review: AI Coding Agent CLI (Claude Code / Codex) - System Design

Reviewed file: `data/book/ai-coding-cli/interview.json`
Review date: 2026-06-12

## Executive Summary

The recent `interview.json` changes address most of the previous review's
highest-impact findings. The case now has a much stronger operational spine:
task idempotency, leases, task events, permission-rule metadata, session
compaction metadata, richer capacity rows, and structured flows for compaction,
verification, extensibility, and cloud delegation.

This is now one of the strongest book datasets. It teaches the system as a
harness around an untrusted but capable model, not as a thin wrapper over an LLM
API. The remaining work is mostly about making a few implicit product/control
planes visible: local session and permission APIs, verification/eval execution,
enterprise retention and redaction, and a capacity diagram that reflects the
new non-model infrastructure sizing.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 5/5 | State machines, capacity, API, and architecture now line up well. |
| Production realism | 5/5 | Strong treatment of sandboxing, injection, leases, idempotency, caching, evals, and extension trust; privacy/retention can be made more concrete. |
| Pedagogical flow | 5/5 | The step sequence is coherent and the new flows remove most hand-waving. |
| Dataset/rendering fit | 5/5 | JSON parses; node/link/highlight/sequence references resolve cleanly. |
| Overall | 5/5 | Flagship-quality with targeted polish left. |

## Recent Change Assessment

The prior review asked for several concrete improvements. The current dataset
has implemented the important ones:

- API and data model state is much richer: `/v1/tasks` is idempotent,
  task status includes attempt/heartbeat/PR metadata, `/v1/tasks/{taskId}/events`
  exposes an append-only log, and the data model now includes `task_events`,
  lease fields, compaction metadata, usage linkage, and extension provenance.
- The capacity section now includes concurrent interactive sessions, cloud task
  and sandbox fleet sizing, transcript storage, task/event volume, and prefix
  cache footprint.
- `compaction`, `verify`, and `cloud` now have structured sequence flows.
  `extensibility` also has a useful MCP discovery/call flow.
- Project memory trust precedence is explicit: checked-in memory is guidance,
  not authority, and cannot expand permissions or egress.
- Idempotency is now a named concept before the cloud step depends on it.
- Option captions were added where the diagram difference was subtle.

The old review should not keep saying these items are missing. The remaining
findings below are narrower follow-ups on the updated design.

## What Works Well

- The narrative is excellent: one-shot baseline, tool loop, context engineering,
  compaction, safety, extensibility, inference economics, verification, then
  cloud delegation.
- The harness/model split is consistently taught. The model proposes actions;
  the harness owns transcript shape, tool execution, budgets, permissions,
  retries, streaming, and rendering.
- Safety is unusually production-aware: policy vs. sandbox, prompt injection,
  repo content as untrusted input, egress control, full-auto risk, and
  headless isolation all appear in the mainline.
- The extension section is a real system-design topic, not a feature aside. It
  connects commands, skills, and MCP servers to token budget, provenance,
  credential scope, and tool poisoning.
- The inference step has the right workload insight: append-only agent
  transcripts make prefix caching and cache-aware routing central design
  requirements.
- The new flows materially improve teachability. Compaction, verification, MCP
  calls, streaming, and cloud leasing are much harder to hand-wave now.

## Highest-Impact Issues

### 1. Local harness contracts are still less explicit than provider/cloud contracts

The top-level API section now describes `/v1/messages`, cloud tasks, task event
streaming, and usage. That is enough for the provider side, but the local CLI
control plane remains mostly implied by prose and data structures.

Why it matters: many core product behaviors are local-first: listing/resuming
sessions, appending session events, saving permission rules, showing approval
history, installing/revoking skills or MCP servers, and rendering a live tool
event stream. The data model has the nouns, but the contract a candidate would
implement is still fuzzier than the cloud task contract.

Concrete fix: either label the API section as "provider-facing API" and keep
local contracts out of scope, or add a small "local harness contracts" group:
session resume/list, append-only session events, permission-rule CRUD, approval
decision records, extension install/review/revoke, and tool-call event IDs.

### 2. Verification and eval execution are still visually compressed

Step 7 now has a strong sequence flow for baseline checks, edits, bounded
retries, git checkpoints, and final diff. Step 8 discusses eval gating. In the
final architecture, though, both are still mostly inside `Sandbox` and
`Telemetry & Evals`.

Why it matters: "verified code changes" is one of the product's central
promises. If the final diagram does not show a check runner or eval runner
path, candidates may treat verification as a command the agent happens to run,
rather than a first-class quality-control subsystem with budgets, outputs,
policy, and release gates.

Concrete fix: add a visible `Verifier / Check Runner` node, or add explicit
links from `Sandbox` to a verification/eval path. For cloud, make eval
execution and rollout gating a concrete operational path instead of only a
responsibility of `Telemetry`.

### 3. Enterprise privacy, retention, and secret handling need one mainline model

The requirements now mention enterprise trust, audit trails, retention controls,
and constrained or disabled prompt caching. The satisfies section correctly
states that zero-retention modes trade away server-side transcripts and prompt
cache. What is still missing is a compact data/control model for those choices.

Why it matters: AI coding agents touch source code, credentials, local files,
dependency registries, issue trackers, and sometimes production-like logs. For
enterprise adoption, "audit and retention" is not just a follow-up; it affects
which transcripts persist, whether prompt-cache KV may be retained, what gets
redacted from logs, and which credentials can enter model context.

Concrete fix: add a short `tenant_policies` or `privacy_policy` data model item
covering transcript retention, telemetry opt-in, prompt-cache eligibility,
secret redaction, allowed egress, and per-extension credential scopes. Tie it to
the safety, inference, extensibility, and cloud steps.

### 4. Capacity improvements are not reflected in the capacity diagram

The capacity rows are now much better than before, but `capacityDiagram` still
shows only the old model-call/token/prefix-cache chain. It does not show the
newly added sizing dimensions: concurrent sessions, cloud sandbox fleet,
queue depth, transcript storage, task events, or prefix-cache memory.

Why it matters: the prose now correctly teaches that this is not just an LLM
throughput problem. The diagram should reinforce that the candidate must size
multiple bottlenecks: GPU serving, cache residency, local/cloud state, task
queueing, sandbox concurrency, and event/audit storage.

Concrete fix: update `capacityDiagram` with a second branch for operational
capacity, or split it into "Model path" and "Agent platform path" subgraphs.
Add rough assumptions where the newer rows depend on them, especially average
session length, task duration, event count per task, and cache TTL.

## System Design Soundness

Requirements are well scoped for a terminal AI coding agent. The functional
requirements cover the local tool loop, context over large repos, streaming,
resume, background PR delivery, and extension mechanisms. The non-functional
requirements now include enterprise trust, which is important for this domain.

Capacity is now useful beyond the model API. The original core numbers still
work: about 1M daily active developers, 80M model calls/day, 4T input
tokens/day, and a 90%+ prefix-cache target. The new rows add the consequences:
150K peak interactive sessions, 10K concurrent cloud sandboxes, 4 TB/day of
cloud-task transcript storage, 200M task/usage events per day, and a large
prefix-cache residency requirement. The only gap is that these rows should feed
the diagram and be tied to explicit assumptions.

The API section is now credible for provider and cloud work. `/v1/tasks`
handles idempotency, repo authorization, base branch, policy selection, and
branch output. Task polling and task events expose progress and retries. Usage
now links spend to request/session/task. The remaining contract gap is local:
permission, extension, and session lifecycle operations are represented in
data but not in an API or CLI contract.

The data model is much stronger. `sessions` now distinguishes full transcript
from in-window digest. `permission_rules` has scope, command pattern, path
scope, source, owner, expiry, and precedence semantics. `extensions` adds
provenance, pinned version, credential scope, review status, and enabled state.
`tasks` and `task_events` support the cloud reliability story. `usage_events`
now supports cost attribution. Add retention/redaction policy as the next
state-model improvement.

The architecture is coherent and uses the canonical node types well. The final
design includes all important components introduced during the walkthrough:
CLI, agent loop, policy, sandbox, repo, session store, optional code index,
subagents, gateway, router, LLM fleet, prefix cache, usage, telemetry/evals,
cloud orchestrator, task queue, cloud sandbox fleet, git host, skills, and MCP.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One-Shot Prompt to Patch

Strong baseline. It now explicitly says one-shot can survive as a scoped,
diff-only mode for tiny edits, which makes the critique more realistic. The
step exposes sight, feedback, and safety as the roadmap.

### Step 2: The Agent Loop: Tool Use

This remains one of the best sections. The harness/model split, small
orthogonal tool catalog, patch-style edits, tool-result truncation, and
termination budget are the right teaching points. A small future improvement
would be to show tool-call IDs in the flow so stream retries cannot accidentally
re-execute a mutation.

### Step 3: Context Engineering for Large Repos

The update fixes the main trust-boundary gap: project memory is now guidance,
not authority. The agentic-search-first stance is realistic and well defended
against reflexive RAG. The optional index trade-off is balanced across recall,
privacy, freshness, and debuggability.

Improvement: consider adding one context-search flow. It could show memory load,
grep/glob/read, capped tool output, optional index retrieval, and the moment a
file actually enters the window.

### Step 3a: Compaction: Surviving Long Sessions

The new compaction flow is a major improvement. It distinguishes full-fidelity
JSONL from the lossy in-window digest, records replaced ranges and files read,
and emphasizes re-reading stale files after compaction. This is now concrete
enough for an interview answer.

Improvement: if there is room, add the trigger threshold and pinned-content
policy as data fields or flow labels.

### Step 4: Permissions & Sandboxed Execution

Excellent section. The permission engine vs. sandbox boundary is the correct
separation. The option captions make the distinction visible. Prompt injection,
project memory precedence, denial-as-tool-result, and egress control are all
production-relevant.

Improvement: the data model says permission decisions are appended to the
session transcript. A separate approval/audit event example would make the
audit trail easier to implement.

### Step 5: Extensibility: Commands, Skills, and MCP Servers

The section is strong and timely. It distinguishes prompt templates, packaged
expertise, and live third-party capability by power level and trust boundary.
The MCP flow and the `extensions` data model close the previous provenance gap.

Improvement: add revocation behavior to a trap or drill: what happens when an
approved MCP server or skill is later marked malicious?

### Step 6: Streaming & the Inference Backend

The prefix-cache explanation is excellent. The step ties backend economics back
to harness behavior: append-only prompt construction, session-affine routing,
model tiering, retry/backoff, and stream resume. Introducing idempotency here
was the right fix because cloud retries later rely on it.

Improvement: make event IDs/tool-call IDs visible in the sequence flow, not
only in prose. That would make the "never re-execute a tool call it has already
run" invariant explicit.

### Step 7: Verify & Iterate: Tests, Git, and Subagents

The new flow fixes the previous gap. Baseline checks, edits, failed-output
feedback, bounded retries, checkpointing, and final diff are now concrete. The
step also handles reward hacking and worktree isolation.

Improvement: make the check runner visible in the final architecture or add a
link from verification output to telemetry/evals.

### Step 8: Background & Cloud Agents at Scale

The cloud section is now very strong. The flow shows idempotent task creation,
enqueue, lease/heartbeat, scoped git token, headless loop, sandbox death,
re-lease, force-push to the same branch, PR creation, and human review. The
state model supports the story.

Improvement: add cancellation/dead-letter behavior as a drill or data field.
This is the natural next operational question after leases and retries.

## Final Design Review

The final design integrates the walkthrough well. It keeps a clear split
between the developer machine, provider inference path, and cloud task
platform. It also shows that cloud agents reuse the same agent loop rather than
becoming a separate product.

The strongest coherence improvement since the previous review is that the data
model now backs the final design's claims. Sessions, compactions, permission
rules, extensions, tasks, task events, and usage events all support behavior
that the steps teach.

The remaining final-design gap is visibility, not correctness. Verification
and evals are present, but compressed into existing nodes. Enterprise retention
and secret-handling policy is mentioned, but not represented as a first-class
control.

## Concept Introduction and Learning Flow

The concept order is now excellent. Completion vs. agent and context window
come first. Tool use and harness follow. Project memory and token budget arrive
before compaction. Prompt injection and least privilege arrive before
extensibility and cloud autonomy. Progressive disclosure arrives before MCP
tool schemas become a token-cost problem. Prefill/decode and prefix caching
arrive before provider-side routing. Idempotency now appears before cloud
leasing depends on it.

This makes the dataset teachable at multiple levels: a junior candidate can
follow the main boxes, while a senior/staff candidate gets the real design
pressure around context, trust, cost, evals, and autonomy.

## Step-to-Final-Design Coherence

The steps build cleanly into the final diagram:

- Step 1 introduces `CLI`, `Gateway`, `LLM`, and `Repo`.
- Step 2 inserts `AgentCore` and `Sandbox`.
- Step 3 adds `SessionStore` and optional `CodeIndex`.
- Step 3a gives `SessionStore` the compaction/resume semantics the diagram
  needs.
- Step 4 adds `Policy` and hardens `Sandbox`.
- Step 5 adds `SkillsLib` and `MCPServer`.
- Step 6 adds `Router`, `PromptCache`, and `Usage`.
- Step 7 adds `Subagents` and gives `Sandbox` the verification role.
- Step 8 adds `CloudOrch`, `TaskQueue`, `CloudSandbox`, `GitHost`, and
  operational telemetry/evals.

This is a good spine. The one weak visual transition is Step 7: verification is
central to the story but does not become a distinct final-design component.

## Realism Compared With Production Systems

The dataset is realistic about the hard parts most AI-agent designs miss:
prompt injection, approval fatigue, sandbox egress, project-memory precedence,
extension/tool poisoning, scoped MCP credentials, append-only prompt caching,
cache-aware routing, model tiering, baseline test failures, reward hacking,
worktree isolation, leases, branch-per-task retries, scoped git credentials,
metering, abuse detection, and eval gating.

The remaining realism gaps are focused rather than structural:

- secret detection/redaction before prompts, logs, telemetry, and task events;
- tenant-level retention and prompt-cache eligibility controls;
- cancellation, dead-letter queues, and support tooling for stuck cloud tasks;
- revocation and rollout handling for compromised skills or MCP servers;
- package-registry/network allowlists that are specific enough for real builds
  without opening broad exfiltration paths.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- The source dataset and generated docs copy currently match for this
  interview.
- All `highLevelArchitecture.links` endpoints resolve to existing nodes.
- All nested `view.nodes` references resolve to `highLevelArchitecture.nodes`.
- All nested `view.links` references resolve to `highLevelArchitecture.links`.
- All nested `view.highlight` IDs are present in their local view.
- Sequence messages, including nested `alt` messages, reference declared
  participants.
- Sequence highlights reference declared participants.
- `satisfies[*].steps[*]`, `technologyChoices[*].steps[*]`, and
  `patterns[*].steps[*]` resolve to real step IDs.
- Node types are canonical: `actor`, `cache`, `client`, `database`, `external`,
  `gateway`, `index`, `model`, `object-storage`, `observability`,
  `orchestrator`, `queue`, `service`, and `worker`.
- The dataset is registered in the `AI-Era Systems` category in both source and
  generated book manifests.

No renderer-facing defects were found during this review.

## Recommended Edits, Prioritized

### P1: Add or scope the local harness contracts

Either mark the API section as provider/cloud-facing, or add local session,
permission, extension, approval, and tool-event contracts so the local product
surface is as concrete as the cloud task surface.

### P1: Make verification/evals first-class in the architecture

Add a `Verifier / Check Runner` node, an eval runner path, or explicit links
showing check outputs and eval gates. Keep the Step 7 flow; it is already good.

### P1: Add enterprise privacy/retention state

Add a compact policy model for transcript retention, telemetry opt-in, prompt
cache eligibility, secret redaction, egress allowlists, and extension
credential scope.

### P2: Update `capacityDiagram`

Reflect the newly added non-model capacity rows: active sessions, task queue,
sandbox fleet, transcript/event storage, and prefix-cache memory. Add rough
assumptions for the derived numbers.

### P2: Add a context-search sequence flow

Show memory load, grep/glob/read, optional index lookup, capped tool results,
and which files actually enter the context window.

### P2: Surface event IDs/tool-call IDs

Use the inference or agent-loop flow to show how stream resume avoids
duplicating text deltas or re-executing already-run mutating tool calls.

### P3: Add operational edge cases

Add cancellation/dead-letter handling for cloud tasks, revocation handling for
malicious extensions, and one support/debugging path for stuck sandboxes.

### P3: Improve technology icon coverage

Several technology choices still use the fallback `tech.png`. This is not a
content defect, but replacing common AI-agent infrastructure icons where
available would make the wrap-up more polished.

## What Not To Change

- Preserve the step order. It is a major strength.
- Keep agentic search as the default and embedding index as the option.
- Keep policy and sandbox as separate mechanisms.
- Keep project memory as guidance, never authority.
- Keep prefix caching as a central backend insight.
- Keep extensions in the mainline; commands, skills, and MCP are core to this
  product class.
- Keep PR review as the human gate for headless agents.
- Keep the traps, drills, and interviewer signals. They make the case useful in
  an actual interview, not just as architecture prose.

## Bottom Line

The recent changes move this dataset from "strong but still abstract in a few
places" to flagship quality. The core architecture, state model, and teaching
sequence are now coherent and production-realistic. The best next edits are
not broad scope additions; they are small visibility upgrades for local control
contracts, verification/evals, enterprise privacy policy, and the capacity
diagram.
