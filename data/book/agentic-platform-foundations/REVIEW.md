# Review: Agentic Platform Foundations

Reviewed file: `data/book/agentic-platform-foundations/interview.json`
Review date: 2026-06-23

## Executive Summary

The recent changes substantially improved this dataset. The earlier gaps around audit evidence, control-plane APIs, idempotent side effects, memory governance, quantitative capacity, guarded tool execution, eval promotion, `Subagent` introduction, and diagram endpoint mismatches have largely been addressed. The interview now reads as a credible foundation case for an enterprise agent platform, not just a collection of agent components.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | The core substrate is coherent and agent-specific. The main remaining gap is durable control-plane state for agent/tool/policy/eval configuration. |
| Production realism | 4/5 | Stronger on idempotency, evidence, memory, eval, and cost. Approval workflow, registry state, overload behavior, and retention semantics could be more operational. |
| Pedagogical flow | 4.5/5 | The "one failure at a time" progression remains excellent, and the new deep dives add concrete artifacts at the right steps. |
| Step-to-final coherence | 4.5/5 | `Subagent`, audit evidence, and guarded tool paths now connect to the final design. A little more wording would clarify the early direct MCP edge versus the final guarded path. |
| Dataset/rendering fit | 4.5/5 | JSON parses; node/link/step references resolve; previous view endpoint mismatches are fixed. Browser/Mermaid visual rendering was not exercised in this review. |

## What Works Well

- The dataset has a clear thesis: choose the least-autonomous path that solves the task, and assume the model layer is compromisable.
- The recent additions made the design much more concrete: control-plane endpoints, `action_evidence`, idempotency keys, delegated token shape, memory provenance/trust/TTL, a worked capacity path, and promotion gates.
- Step sequencing is strong. Each step exposes a production failure, fixes that failure, and hands the next risk to the following step.
- Security is still the strongest pillar. The interview teaches prompt injection as an architectural/data-flow problem, not a prompt-writing problem.
- The final design now matches the journey better: `Subagent` is introduced before final design, high-risk tools route through guardrails, and audit evidence is explicitly named.

## Highest-Impact Issues

### 1. Control-plane APIs exist, but their durable state is not modeled

The API now includes representative control-plane endpoints for agents, tools, policies, eval runs, and promotion. That fixes the earlier session-only API concern. The data model, however, still has only `sessions`, `events`, `action_evidence`, and `memories`.

Why it matters: the platform promise is that teams can deploy agents without rebuilding runtime, identity, guardrails, eval, or observability. That promise depends on durable configuration: agent versions, tool manifests, policy versions, eval suites/runs, promotion decisions, tenant quotas, and budget bindings.

Concrete fix: add a compact control-plane data model slice. It does not need to be exhaustive, but should include entities such as `agents`, `agent_versions`, `tool_manifests`, `policy_versions`, `eval_runs`, and `tenant_budget_rules`. Tie those entities to `/v1/agents`, `/v1/tools`, `/v1/policies/{id}`, `/v1/evals/runs`, and `/v1/agents/{id}/promote`.

### 2. Approval and evidence need a clearer state-machine contract

The design now has `action_evidence`, approval fields, and a guarded tool path. The remaining weakness is that the approval API and flow do not show how a human decision is bound to a specific pending action.

Why it matters: high-risk actions need race-safe, replay-safe approval. A production system should prove that the approver saw the action, risk class, policy version, redacted parameters, downstream resource, and consequence before the durable run resumed.

Concrete fix: enrich `POST /v1/sessions/{id}/approve` with an `actionId` or `evidenceId`, expected `policyVersion`, decision idempotency key, and optional expiration. Add a short sequence flow: guardrail creates pending evidence -> human approves/rejects -> evidence is finalized -> durable run resumes or compensates.

### 3. The durable-log/evidence relationship should be explicit

The data model defines a separate `action_evidence` entity, while the final design says the durable log "doubles as the immutable audit/evidence store." That is plausible, but the relationship is underspecified.

Why it matters: audit evidence and execution replay have different access patterns and retention rules. One may be the append-only source of truth and the other a projection, but readers should not have to infer it.

Concrete fix: state one model directly: for example, `events` is the append-only execution stream and `action_evidence` is an immutable evidence record written in the same transaction or projected from evidence events, with its own retention class and query path.

### 4. Admission control is credible but still light on overload behavior

The capacity section now includes a good worked sizing path and weighted fair scheduling. The next production detail is what happens when demand exceeds the budgeted envelope.

Why it matters: agent traffic is bursty, long-running, and sometimes background work. Queue fairness alone does not define cancellation, deadline expiry, priority inversion, dead-lettering, backpressure to callers, or tenant-level throttling.

Concrete fix: add one compact overload policy: interactive sessions get first-step SLO priority, background runs can be delayed or checkpointed, expired queued work returns a retryable status, repeated tool failures go to a dead-letter path, and tenant budget exhaustion produces deterministic termination rather than best-effort throttling.

## System Design Soundness

The requirements are coherent and specific to agent platforms. The architecture covers the right shared substrate: gateway, orchestrator, sub-agents, sandbox, inference, tools, guardrails, identity, vault, memory, durable log, queue, eval, trace stream, and observability.

The biggest improvement is that the dataset no longer overclaims "exactly once" as magic. Step 3 now teaches the correct contract: at-least-once execution plus idempotency keys, deduplication, durable intent/result records, and resume logic. One small wording issue remains: the Step 3 recap says "Runs resume exactly-once," while the body correctly says "exactly-once effect." Aligning that recap would prevent candidates from repeating an overclaim.

Auditability is now materially stronger. `action_evidence` includes actor, agent principal, approval decision, policy version, tool, redacted parameters, downstream resource, idempotency key, result, and retention class. The missing piece is not the fields; it is the state transition that binds approval to evidence and then resumes the run.

Security remains strong. The final design now clearly says there is no direct orchestrator-to-tool bypass for egress or high-risk actions, and the final view omits the direct `cp-tool` link. Early steps still use `cp-tool` to introduce MCP before guardrails exist, which is acceptable, but a short note would help readers understand that this is intentionally pre-security or low-risk/read-only, not the final enforcement path.

## Step-by-Step Pedagogical Review

### Step 1: Naive: A Single Hosted Agent Loop

This remains a strong baseline. It exposes the exact failures that the rest of the interview fixes: full privilege, prompt secrets, crash loss, runaway tokens, missing identity, missing eval, and missing trace. The previous diagram endpoint issue is fixed by including `Gateway`.

### Step 2: Runtime Isolation & Credential Brokering

The Firecracker versus gVisor/container option comparison is useful and realistic. The new sandbox lifecycle deep dive adds the missing operational detail: signed snapshots, default-deny egress, short-lived brokered credentials, cleanup, and warm-pool reset.

Minor improvement: connect this more explicitly to tenant isolation, not just compromised-code isolation. The architecture has the ingredients, but "multi-tenant isolation" appears mostly as quota/fairness later.

### Step 3: Durable Sessions, Context & Memory

This step is much stronger after the idempotency and memory-governance additions. The flow now shows intent, `idempotency_key`, downstream execution, committed result, and resume behavior.

Improvement: change the recap from "Runs resume exactly-once" to "Runs resume with exactly-once-effect semantics" or similar. The detailed explanation is correct; the recap should match it.

### Step 4: Tool / Protocol Boundary & Identity Delegation

The delegated token shape is a good concrete artifact: `sub=agent`, `act=user`, `aud=tool`, scope, tenant, policy version, and expiry. It connects identity to audit evidence and avoids the common "reuse the user's token" mistake.

Improvement: when the control-plane data model is added, make `policy_version` a durable object referenced by tokens and evidence records.

### Step 5: Security Guardrails & Data-Flow Partitioning

This is still the best individual step. It distinguishes statistical classifiers from deterministic enforcement and names the MCP supply-chain/tool-poisoning risk, data-flow partitioning, lethal-trifecta mitigation, and markdown auto-fetch exfiltration.

Improvement: if the CVE-specific example is kept, add a project-consistent external reference or keep the example generic. The authoring note is gone, which was the important cleanup.

### Step 6: Capacity, Inference Economics & Admission Control

The worked sizing path is a major upgrade. It gives candidates a concrete traffic profile, token calculation, concurrency estimate, prefix-cache leverage, hard budget, and queue fairness policy.

Improvement: add one overload/backpressure rule so admission control has behavior under saturation, not just a scheduling strategy.

### Step 7: Evaluation & Observability

The rollout/promotion contract closes the previous loop: promotion is gated, production failures feed golden sets, and observability can demote a bad version. This is now a useful production teaching step rather than a generic "add observability" step.

Improvement: model `eval_runs`, `eval_suites`, or `promotion_decisions` in the data model so the `/v1/evals/runs` and `/v1/agents/{id}/promote` APIs have persistent backing.

### Step 8: Control-Flow Synthesis

This lands the central lesson well: deterministic workflow first, autonomous loop only for genuinely open search, hybrid gate in between. The new orchestrator-workers deep dive introduces `Subagent` before final design and explains bounded context, least privilege, durability, attribution, and observability for fan-out legs.

Improvement: add one sentence that every path still routes dangerous side effects through the guardrail/evidence path. The flow already shows it; the text can make it impossible to miss.

## Final Design Review

The final design is now coherent as a reference architecture. It integrates the platform substrate, states the no-bypass rule for high-risk tools, includes sub-agents, and ties the durable log to evidence and trajectory traces.

The remaining final-design issue is precision rather than missing components. Clarify whether `action_evidence` is a table, log stream, projection, or append-only record family inside the durable log. Also consider adding control-plane state nodes or at least data-model entities for agent/tool/policy/eval configuration, because those are now visible in the API.

## Concept Introduction and Learning Flow

Concept staging is strong and improved by the new concrete artifacts:

- Step 3 introduces the idempotent side-effect protocol before identity and security depend on it.
- Step 4 introduces the delegated token shape before audit evidence and policy versioning matter.
- Step 5 introduces deterministic policy enforcement before capacity makes the platform broad.
- Step 6 makes token economics quantitative instead of hand-wavy.
- Step 7 turns eval into a deploy gate and production feedback loop.
- Step 8 synthesizes workflow, hybrid gate, autonomous loop, and sub-agents.

The learning flow would become even tighter if the remaining control-plane entities were added. That would let candidates see how an agent version, policy version, tool manifest, eval run, and promotion decision travel through the platform.

## Step-to-Final-Design Coherence

The sequence now maps well to final components:

- `naive` introduces the loop, inference, and tools.
- `runtime` introduces `Sandbox`, `Identity`, and `Vault`.
- `durable` introduces `DurableLog`, `MemoryStore`, and `MemoryIndex`.
- `identity` introduces the MCP/tool boundary and delegated authority.
- `security` introduces `Guardrail` and the policy-gated tool path.
- `capacity` introduces `TaskQueue` and inference economics.
- `eval-obs` introduces `EvalHarness`, `TraceStream`, and `Observability`.
- `control-flow` introduces `Subagent`, human gates, and the path-selection rule.

The only coherence caveat is the `cp-tool` direct link. It is useful in early steps, but the final design intentionally omits it. Add wording that direct MCP calls are the pre-guard baseline or only allowed for explicitly low-risk/read-only cases after policy classification.

## Realism Compared With Production Systems

The dataset is now realistic for a foundations interview. It covers the hard parts many agent-platform designs skip: prompt-injection blast radius, delegated identity, idempotent side effects, memory poisoning, token amplification, trajectory eval, eval gates, and sub-agent fan-out.

Production realism would improve most from:

- Control-plane persistence for agents, versions, tool manifests, policy versions, quotas, budgets, eval suites, eval runs, and promotions.
- A race-safe approval/evidence state machine.
- Explicit overload/backpressure behavior for queue saturation and tenant budget exhaustion.
- A clear retention model for traces, memories, durable events, and action evidence.
- A stated relationship between durable execution logs and queryable audit evidence.

## Dataset and Renderer-Facing Observations

- JSON parsing succeeds.
- Step view node IDs and link IDs resolve to canonical high-level architecture IDs.
- Selected links have both endpoints present in their view nodes, including the previously problematic `naive` and `control-flow` views.
- `finalDesign.view.links` endpoints are present in `finalDesign.view.nodes`.
- `patterns[].steps` and `satisfies[*].steps` references resolve to real step IDs.
- The prior reader-facing authoring note has been removed.
- No source-vs-generated docs change is needed for this `REVIEW.md` update.

## Recommended Edits, Prioritized

### P1: Add control-plane data-model entities

Model `agents`, `agent_versions`, `tool_manifests`, `policy_versions`, `eval_runs`, and tenant budget/quota rules. Tie them to the new control-plane API endpoints.

### P1: Add an approval/evidence state-machine flow

Show guardrail-created pending evidence, human decision binding, immutable evidence finalization, and durable run resume/cancel/compensation.

### P2: Clarify durable log versus action evidence

State whether evidence is part of the event log, a separate append-only table, or an immutable projection from evidence events.

### P2: Define overload behavior

Add queue saturation behavior: priority classes, deadline expiry, retryable rejection, background checkpointing, dead-letter handling, and tenant budget exhaustion.

### P3: Align exactly-once wording

Change recap-level wording from "resume exactly-once" to "resume with exactly-once-effect semantics" so the summary matches the correct detailed explanation.

### P3: Clarify the early `cp-tool` edge

Explain that direct control-plane-to-tool calls are the pre-security baseline or low-risk/read-only path, while egress/high-risk calls must route through guardrails and evidence.

## What Not To Change

- Keep the one-failure-at-a-time sequence. It is the strongest teaching feature.
- Keep the compromisable-model assumption. It makes the security design credible.
- Keep the workflow/hybrid/loop selection rule as the final synthesis.
- Keep the concrete deep dives added by the recent changes; they turn abstract platform concerns into defendable interview artifacts.
- Keep `Subagent` in Step 8 rather than introducing it only in final design.

## Bottom Line

This is now a strong foundations interview. The prior blocking issues are mostly resolved; the remaining work is narrower and operational: persist the control plane, make approval/evidence state transitions explicit, define overload behavior, and tighten a few phrases so candidates do not overclaim exactly-once or infer a guarded-tool bypass.
