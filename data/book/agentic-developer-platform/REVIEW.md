# Review: Agentic Developer Platform - System Design

Reviewed file: `data/book/agentic-developer-platform/interview.json`
Review date: 2026-06-23

## Executive Summary

This review is updated after the recent dataset deepening. The earlier high
impact findings are largely addressed: capacity now has numeric rows, the task
lifecycle has leases/idempotency/attempt state, repo indexing has freshness and
authorization metadata, parallel-agent conflict handling is in the mainline, and
the gate has durable `gate_decisions`. The previous diagram endpoint warnings
also no longer reproduce.

The dataset is now a strong book-quality case. Its central thesis is clear and
distinctive: a cloud fleet of coding agents can be useful only if agent autonomy
stops at a draft PR, while merge and deploy remain a separate guarded gate
because reverting code is not the same as reversing effects. The remaining
issues are narrower: the public API has not caught up to the richer data model,
one capacity calculation is internally inconsistent, gate evidence is modeled
but not visible enough in the sequence flow, and the security/evaluation pieces
would benefit from one more concrete workflow.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.55/5 | Strong requirements, architecture, and state model; API and one capacity number need tightening. |
| Production realism | 4.45/5 | Leases, idempotency, work intents, index jobs, gate decisions, quotas, and retention are now credible; external workflow evidence needs more visibility. |
| Pedagogical flow | 4.50/5 | The seven-step sequence teaches one risk at a time; security and evaluation could use a little more structured flow. |
| Dataset/rendering fit | 4.65/5 | JSON parses; step/final links, endpoint nodes, sequence participants, patterns, and `satisfies` references resolve. |
| Overall | 4.55/5 | A strong flagship vertical with focused polish remaining. |

## What Works Well

- The review-driven changes materially improved the dataset. Capacity is no
  longer qualitative, and the data model now carries the state needed for
  resumable async work, conflict handling, index freshness, and gate evidence.
- The central invariant stays sharp: the agent may open a draft PR, but human
  review, branch protection, CI, code ownership, rollout controls, and deploy
  evidence form the second gate.
- The architecture uses the right boundaries. It reuses Agentic Platform
  Foundations for runtime, durability, identity, inference, and observability
  instead of bloating this vertical with unrelated substrate design.
- The step order is coherent: baseline, repo grounding, fleet isolation, gate,
  verification, prompt-injection defense, and fleet operations.
- The domain-specific problems are not generic "LLM app" points. They are
  coding-agent problems: stale code context, branch/PR side effects, protected
  branches, CI status ambiguity, poisoned repo text, scoped repo credentials,
  and reviewer-owned merge.
- The renderer-facing structure is clean. The earlier implicit-node problems in
  option and step views are fixed.

## Highest-Impact Issues

### 1. The public API is much thinner than the new control-plane model

The data model now includes `tenant_id`, `repo_id`, `idempotency_key`,
`base_sha`, `branch_name`, `head_sha`, `pr_id`, attempts, leases, retry policy,
gate decisions, and trajectory retention. The API examples still expose a small
shape: `POST /v1/tasks` accepts only `repo`, `issue`, and `base`, and
`GET /v1/tasks/{id}` returns only status, PR URL, and checks.

Why it matters: the interview now teaches a production-grade control plane, but
the external contract does not show how callers request idempotency, bind work
to a base commit, declare tenant/repo scope, cancel work, observe lease/retry
state, or read gate evidence. Candidates may design the right internals while
leaving the platform API under-specified.

Concrete fix: expand the API examples to include `tenantId`, `repoId`,
`idempotencyKey`, `baseBranch`, optional `baseSha`, `taskSource`, `requestedPath`
or file-intent hints, priority/risk class, and callback/webhook metadata. Extend
task reads with `attempt`, `leaseState`, `baseSha`, `branchName`, `headSha`,
`prId`, `terminalReason`, `retryAfter`, and a `gateDecisions` or
`gateEvidenceUrl` link. Add a small cancel endpoint if cancellation remains in
the task state model.

### 2. The sandbox concurrency math conflicts with the stated peak load

Capacity now gives useful numbers, but the concurrency row combines the peak
arrival rate and p95 duration while still landing at `~500 concurrent target`.
Task volume says peak `~120 submissions/min` and p95 duration is `~25 min`; at
peak, Little's Law would put p95 occupancy near `120 * 25 = 3000` concurrent
sandboxes. Using the average duration gives `120 * 6 = 720`; using daily
average arrival rate (`50k/day ~= 35/min`) with p95 gives about `870`.

Why it matters: capacity is one of the most interview-relevant parts of this
case. A wrong or ambiguous concurrency target weakens the admission-control
story, because the queue cap, warm pool, CI budget, and tenant quotas depend on
which arrival rate and duration percentile the design is sizing for.

Concrete fix: choose the intended sizing policy and make the row explicit. For
example: "steady-state target ~500-900 concurrent using daily average plus
headroom; overload bursts queue when peak would imply ~3000" or "provision
~3000 for peak p95." Update `capacityDiagram` to match the chosen number.

### 3. Gate evidence is modeled, but the gate flow does not write it

`gate_decisions` is the right data model addition, and the final design
description now says each gate writes durable evidence. The step 4 sequence,
however, still shows CodingAgent -> VCS -> CI -> Reviewer -> merge, without an
explicit write of the gate decision, policy snapshot, head SHA binding, or
downstream deploy evidence.

Why it matters: the strongest lesson in the dataset is the two-gate invariant.
If the data model carries gate decisions but the flow does not show where they
are produced, the invariant still reads partly as prose rather than an
operational workflow.

Concrete fix: update the gate sequence with one of these small additions: VCS or
Supervisor writes `gate_decision(head_sha, policy_version, checks, actor)`;
CI/CD writes or links `deploy_evidence_url`; rejected/changes-requested review
writes a terminal or feedback event. If adding a new node is too much, use
`DurableLog` in the sequence as the evidence sink.

### 4. Prompt-injection defense is conceptually strong but lacks a concrete flow

Step 6 names the right surfaces: issue text, PR comments, CI logs, dependency
docs, and repo content are untrusted. It also correctly points to scoped tokens
and egress constraints. But unlike context, fleet, gate, verify, and async-obs,
the security step has no sequence flow. The deep dive also uses the phrase
"remove a trifecta leg" without defining the trifecta in this dataset.

Why it matters: prompt-injection defense in coding agents is subtle because the
platform must still let the agent read untrusted text and use powerful tools.
The teachable boundary is not "filter text"; it is separation between untrusted
data, plan/tool authority, credential brokering, and network egress.

Concrete fix: add a short security flow: agent retrieves untrusted repo text,
guardrail marks/partitions it, agent requests a tool call, policy checks the
call against task scope, identity mints a scoped token, and sandbox/egress
allows or denies execution. Either define "trifecta" in a concept chip or
replace it with explicit wording: data access, tool authority, and exfiltration
path.

### 5. Fleet quality is present, but evaluation criteria are still too thin

Step 7 adds trajectories, token/cost roll-ups, dead-letter inspection, and a
warning that merge rate alone is weak. That is a good start. The platform still
does not name enough quality signals for a reviewer or operator to judge whether
the fleet is actually improving developer throughput.

Why it matters: org-scale coding agents can look successful while producing PRs
that reviewers heavily rewrite, revert, or avoid merging. A good system design
answer should distinguish activity metrics from outcome and safety metrics.

Concrete fix: add a small evaluation model or deep-dive bullets covering:
reviewer edit distance, comments per PR, time to review, stale PR rate, CI
rerun/flakiness rate, revert/regression rate, escaped incident links, duplicate
task rate, conflict cancellation rate, cost per merged PR, and per-tenant
fairness. Keep "LLM-as-judge" secondary to these externally grounded signals.

## System Design Soundness

The requirements are strong and well scoped. Functional requirements cover
async task ingest, parallel isolated agents, repo-context retrieval, draft PRs,
and human-owned merge/deploy. Non-functional requirements cover sandboxing,
verification-first behavior, resumability, prompt-injection defense, and
multi-tenant fairness.

The high-level architecture is sound. The key components are present:
`Gateway`, `Supervisor`, `TaskQueue`, `CodingAgent`, `Sandbox`, `Inference`,
`RepoIndex`, `VCS`, `CI`, `Guardrail`, `Identity`, `DurableLog`, and
`Observability`. Node types are appropriate: `Dev` is an `actor`, `Trigger` is
a `client`, `RepoIndex` is an `index`, `Inference` is a `model`, and VCS/CI are
external dependencies.

The data model now supports the main promises. `tasks` has leases, attempts,
branch/head/base identifiers, PR identity, cancellation, retry policy, and a
resume cursor. `run_events` covers checkout, retrieval, tool calls, patches,
test results, branch push, PR open, CI status, review events, and lease renewal.
`work_intents` brings conflict handling into the mainline. `gate_decisions`
makes the two-gate story durable. `repo_index` and `index_jobs` address commit
binding, parser version, authorization scope, tombstones, lag, retry, and
backfill.

The main soundness gaps are now alignment issues rather than missing
architecture: API examples should expose the new state, capacity math should be
made internally consistent, and the gate/security/evaluation workflows should
show the exact evidence and policy checks the prose promises.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Agent, Direct Commit

This is still a useful baseline. It makes the contrast with the platform clear:
one developer, one agent, full credentials, direct commits, no isolation, no
queue, and no review gate.

Improvement: this step is intentionally simple, so no major change is needed.
If the renderer feels sparse, add one sentence of step-level overview text that
states the anti-pattern directly.

### Step 2: Ground the Agent in the Codebase

This step is much stronger after the changes. It now teaches hybrid retrieval,
code-graph retrieval, index freshness, commit binding, authorization scope, and
webhook-driven index jobs. The no-index option is a useful counterpoint.

Improvement: add the failure mode for index lag. A single note such as
"if index_jobs lag exceeds the freshness SLO, fall back to direct VCS reads or
delay PR creation" would make the freshness story operational.

### Step 3: Run a Fleet: Supervisor + Ephemeral Sandboxes

This is now one of the strongest steps. It covers queueing, leases,
idempotency, replay from `run_events`, scoped credentials, durable resume,
tenant fairness, and work-intent locks. The new deep dive answers the previous
review's core concern.

Improvement: the flow could show `work_intents` explicitly, either as a model
call before sandbox execution or as part of the lease label. That would make
conflict handling as visible as resume.

### Step 4: The Gate: Draft PR, Then a Distinct Merge/Deploy Gate

This remains the centerpiece of the interview. The concept "reverting code !=
reversing effects" is exactly the right teaching point, and `gate_decisions`
turns the rule into state.

Improvement: make the sequence write gate evidence. Bind approval to `head_sha`,
record the policy version and checks, and show deploy evidence as a link to the
downstream CI/CD platform rather than implying this platform owns deployment.

### Step 5: Verify Before Proposing

The verification step is correctly positioned before the prompt-injection step:
once the agent can run tests and open PRs, the authority boundary matters. The
deep dive now explains why verification evidence should include commands, exit
codes, retry count, log artifact, changed files, and final `head_sha`.

Improvement: consider adding a `verification_results` model or making it clear
that these details live in `run_events.payload`. Right now the deep dive says
what to store, but the schema only implies where it lives.

### Step 6: Untrusted Repo Text: Prompt-Injection Defense

The step has the right domain focus. It does not hand-wave "LLM safety"; it
names the actual attacker-controlled inputs in coding workflows and ties them to
tool authority, credential scope, and egress.

Improvement: add a sequence flow. This is the one major step without one, and
the boundary is important enough to draw: untrusted text in, policy-mediated
tool call out, scoped token from Identity, sandbox/egress enforcement.

### Step 7: Async at Scale

The final step now shows idempotency keys, tenant-aware admission, capacity
limits, trajectories, token/cost roll-ups, retention class, and dead-letter
inspection. It closes the interview in the right operational register.

Improvement: add stronger quality metrics. Merge rate should be explicitly
subordinate to reviewer edit distance, regression/revert rate, stale PR rate,
reviewer time, conflict cancellation, and cost per accepted change.

## Final Design Review

The final design now integrates the steps cleanly. It includes the components
introduced across the walkthrough and describes the missing-but-important state:
leased task state machine, idempotency, work-intent locks, optimistic rebase,
commit-bound repo retrieval, gate decisions, deploy evidence, trajectory
retention, and Foundations substrate reuse.

The final design would become even crisper if the diagram or sequence flows
made the evidence sinks visible. `DurableLog` and `Observability` are present,
but `gate_decisions`, `work_intents`, `index_jobs`, and verification evidence
are currently data-model entities rather than visual control-plane surfaces.
That is acceptable for a compact diagram, but the sequences should pick up the
most important writes.

## Concept Introduction and Learning Flow

The concept staging is strong:

- Code-graph retrieval and index freshness appear exactly when grounding is
  introduced.
- Lease/idempotency and work-intent locks appear when the fleet is introduced.
- The two-gate invariant appears before verification and security.
- Untrusted repo text appears after the agent has meaningful authority.
- Evaluation appears last, once there is a running fleet to measure.

The remaining concept gap is prompt-injection mechanics. The dataset names
CaMeL/Dual-LLM/Plan-then-Execute in a pattern, but the step itself would benefit
from a concrete "data versus authority" concept chip or flow.

## Step-to-Final-Design Coherence

The final design includes the components introduced by the steps:

- `context` introduces `RepoIndex`, commit-bound retrieval, and index jobs.
- `fleet` introduces `Supervisor`, `TaskQueue`, `Sandbox`, `Identity`,
  `DurableLog`, leases, idempotency, quotas, and work intents.
- `gate` introduces `VCS`, `CI`, reviewer ownership, branch protection, and
  durable gate decisions.
- `verify` introduces in-sandbox verification and PR CI as source of truth.
- `security` introduces `Guardrail`, scoped credentials, and egress limits.
- `async-obs` introduces `Trigger`, `Gateway`, admission, trajectories, and
  observability/evaluation.

The coherence gap is no longer missing components. It is that some operational
records introduced in data model prose are not surfaced in API or sequence
examples.

## Realism Compared With Production Systems

The dataset now handles many production concerns that were previously implicit:

- Duplicate or replayed triggers through idempotency keys.
- Worker crash and resume through leases, attempts, and `last_event_seq`.
- External side effects through branch/head/PR identifiers in task state.
- Parallel edit conflicts through work-intent locks and optimistic rebase.
- Stale retrieval through commit binding and `index_jobs` lag.
- Gate audit through durable `gate_decisions`.
- Tenant fairness through queue, token, and concurrency quotas.
- Trajectory privacy through retention-class wording.

The remaining realism concerns are about explicit workflows:

- API fields should expose the control-plane state callers actually need.
- Capacity should distinguish steady-state sizing from peak overload behavior.
- CI/CD deploy evidence should be shown as an external proof link, not only as
  prose.
- Security enforcement should show the path from untrusted text to allowed or
  denied tool action.
- Evaluation should emphasize externally grounded quality outcomes over model
  judgment alone.

## Dataset and Renderer-Facing Observations

Validation performed:

- `interview.json` parses as JSON.
- The dataset has 17 top-level keys, 7 steps, 15 architecture nodes, 20
  architecture links, 11 patterns, 6 data model entities, 12 technology-choice
  concerns, 3 APIs, 5 follow-ups, and no `probeLinks`.
- Step view nodes resolve to `highLevelArchitecture.nodes`.
- Step, option, and final design view links resolve to
  `highLevelArchitecture.links`.
- Link endpoints used by step, option, and final views are present in each
  selected view's node list.
- Sequence participants and message endpoints resolve to architecture node IDs.
- `patterns[].steps[]` and `satisfies[*].steps[]` references resolve.

No renderer-facing blockers were found. A browser/Mermaid visual pass would
still be useful after future diagram changes, but there are no obvious schema or
reference issues in the source JSON.

## Recommended Edits, Prioritized

### P1: Align the API with the richer task, gate, and trajectory model

Add request/response fields for idempotency, tenant/repo identity, base commit,
branch/head/PR identifiers, attempt/lease status, cancellation, retry state,
gate evidence, and trajectory retention/redaction metadata.

### P1: Fix the concurrency calculation and capacity diagram

Decide whether the platform provisions for peak p95, average load plus queueing,
or an explicit capped-overload mode. Then make the numeric row and
`capacityDiagram` agree.

### P2: Make gate evidence writes visible in the sequence

Show the policy snapshot, head SHA binding, required checks, reviewer/actor
decision, and deploy evidence URL being written to `gate_decisions` or
`DurableLog`.

### P2: Add a prompt-injection enforcement flow

Draw the boundary between untrusted repo text, guardrail/policy, Identity token
brokering, sandbox execution, and egress denial/allowance. Define or remove the
"trifecta" phrase.

### P2: Strengthen fleet quality evaluation

Add metrics beyond merge rate and model judgment: reviewer edit distance, time
to review, stale PRs, CI flakes/reruns, regressions/reverts, duplicate tasks,
conflict cancellations, cost per accepted PR, and per-tenant fairness.

### P3: Add a little step-level narrative polish

The steps currently rely mostly on recaps, diagrams, concepts, traps, and deep
dives. One concise `overview` or `decision` sentence per step would make the
rendered pages feel less abrupt.

### P3: Consider optional book wrap-up sections

If this case is meant to be as complete as the flagship book interviews, add
curated `probeLinks`. The technology-choice section is now present, and both
sections are optional, so this is not a correctness issue.

## What Not To Change

- Keep the two-gate invariant as the center of the case.
- Keep Agentic Platform Foundations as inherited substrate; do not re-teach the
  generic runtime, identity, inference, and observability platform here.
- Keep the seven-step order. It builds the design naturally.
- Keep work-intent locks and gate decisions in the mainline, not as follow-up
  trivia.
- Keep CI/CD and source control as external systems with clear contracts rather
  than re-implementing them inside the platform.

## Bottom Line

The recent changes moved this dataset from "strong but under-modeled" to a
credible production-oriented vertical. The next pass should focus on alignment:
make the API match the control plane, fix the capacity math, show gate evidence
and security enforcement in flows, and sharpen the fleet-quality metrics.
