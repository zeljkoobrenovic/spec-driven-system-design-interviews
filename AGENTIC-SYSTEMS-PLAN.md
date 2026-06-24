# Agentic Platforms — System Design Interview Mini-Series (Plan)

A planning note for a coherent mini-series of system-design interviews on
**building agentic platforms**, authored as datasets for this explorer (same
schema as `data/book/payment-system` etc.). This file is the spec. It is a
**root-level planning note** (it sits at the repository root, not the `data/book`
group root) and is outside all build inputs — `build.py` copies neither
root-level Markdown nor loose `*.md` at a group root, so it never ships into
`docs/`. In role it parallels `data/book/BOOK-STRUCTURE.md` for this sub-theme.

> **Status:** plan approved (placement + scope + deliverable decided) and
> **revised per `AGENTIC-SYSTEMS-PLAN-REVIEW.md` (2026-06-23)**: protocol claims
> de-risked (no false lineage), the unverifiable "Rule of Two" attribution
> dropped, Foundations trimmed to an 8-step spine, the book verifier added as
> the mandatory gate, Developer merge reframed as a two-stage gate, Finance
> audit artifact changed to a decision record (not a reasoning dump), pattern
> names frozen before the verticals, and volatile claims moved to a source
> backlog (§9). **Second revision (same review file, 2026-06-23):** the prior P1s
are marked resolved; remaining P2/P3 items fixed — step sketches now carry an
exact `step.patterns[]` mapping table (frozen §4 names), the "~50×" token-
amplifier claim is tagged + backlogged, a compliance/legal source-anchor table
was added, and the catalog-sequencing heading was disambiguated ("after dataset
1, before dataset 2"). Build order is in §7.
>
> **Implementation status:** **Phase 1 (§5–§7) and Phase 2 (§8) are DELIVERED** —
> **Phases 1–3 are all DELIVERED: 11 datasets** in the `agentic-platforms`
> category (Foundations + Developer, Marketing, Sales, HR, Finance, Legal,
> Healthcare, Support, Public Benefits, Research) plus the 17 frozen agentic
> patterns in `data/book/patterns` with `usedBy[]` backlinks across every
> vertical; all verifier-clean and built into `docs/book/`. The series spans the
> full irreversibility gradient (revertible → reputation → decision/fairness →
> money → filing → physical harm) plus the **real-time** (Support),
> **contestability** (Public Benefits), and **physical-experiment** (Research)
> axes. Remaining ideas live in §8b (capstone "Choosing the Right Agent Gate")
> and a possible phase 4 (industrial/robotics).

## 1. Decisions taken

- **Placement:** one **new category** `agentic-platforms` ("Agentic Platforms")
  inside the existing **book group** (`data/book/index.json`). Everything stays
  in the existing book site (`docs/book/`). Consistent with `ai-coding-cli`,
  which already lives in `book` under "AI-Era Systems" and is the closest prior
  art.
- **Scope (phase 1):** **Foundations + 3 flagship verticals** —
  1. `agentic-platform-foundations` (the deep anchor: the shared infrastructure)
  2. `agentic-developer-platform`
  3. `agentic-finance-platform`
  4. `agentic-legal-platform`

  Marketing, Sales, HR are **deferred to phase 2** (§8) — the three flagships
  were chosen for maximum contrast on the one axis that makes each vertical
  *vertical* (see §3): the **irreversibility of the action behind the gate**.
- **Deliverable now:** this plan file only. Datasets are scaffolded in a
  follow-up using the `new-interview` skill, in the build order of §7.

## 2. The unifying thesis (what ties the series together)

Two cross-cutting themes run through every interview. State them in the
Foundations interview and *reuse* them in each vertical so the series reads as
one argument, not five disconnected cases.

**Theme A — the control-flow spectrum** (the central design axis):

```
DETERMINISTIC ───────────── HYBRID ───────────── PROBABILISTIC
(authored DAG/pipeline)  (bounded agent + gates)   (autonomous ReAct loop)
```

- **Probabilistic path** — autonomous ReAct loop; the model decides the next
  tool. Max flexibility, but loops/cost/non-determinism. Cite **ReAct
  (Yao et al., 2022, arXiv:2210.03629)**.
- **Deterministic pipeline path** — fixed DAG; code decides the path, the LLM is
  contained inside nodes. Predictable, testable, cheap to bound.
- **Hybrid agent + gate path** — agent reasons autonomously *within fences*;
  deterministic guardrails validate I/O and human-in-the-loop (HITL) interrupts
  pause before high-stakes actions. A common production sweet spot, **but not
  the universal answer.** Cite Anthropic **"Building Effective Agents"
  (Dec 2024)** (workflows vs agents) and LangGraph
  `interrupt()`/`Command(resume=…)` as the reference HITL mechanism.

**Selection rule (state this explicitly; the verticals depend on it).** Choose a
**deterministic workflow** (LLM calls inside bounded nodes) when the action path
is known ahead of time and correctness/audit dominate — this is the right
default for the **Finance** and **Legal** verticals, not an autonomous loop
fenced by a late gate. Choose an **autonomous loop** only where the
search/planning space is genuinely open *and* every dangerous side effect is
guarded before execution. The hybrid agent+gate sits between them: open-ended
planning with deterministic guards at each dangerous boundary.

**Theme B — assume the model layer is compromisable.** Identity, security, and
runtime all converge on *bounding what a compromised agent can do* rather than
preventing compromise. Anchor concepts:
- **The lethal trifecta** (Simon Willison) — the primary, easy-to-verify anchor:
  private data + untrusted content + exfiltration in one session = catastrophic.
  Remove any one leg. (Add the exact post URL/date to `toProbeFurther` —
  `VERIFY BEFORE PUBLISHING`.)
- **The "at-most-two" heuristic** (derived from the trifecta, stated as an
  unattributed internal rule unless a primary source is found): keep any session
  from simultaneously combining private data, untrusted content, and
  unconstrained external communication; when the combination is unavoidable,
  require HITL or partition the session. **Do not attribute this to a named
  "Meta Agents Rule of Two"** unless a precise Meta primary source is located
  first — research could not verify that phrase. `VERIFY BEFORE PUBLISHING`.
- **Credential brokering / least privilege** — the agent *uses* but never *sees*
  secrets; microVM isolation; delegation (not impersonation) for identity.

**The vertical formula** (repeat verbatim per vertical):
> Every vertical = a **generic agent platform** + an **authoritative grounding
> corpus** + a **domain-specific high-stakes gate**. The design tension is
> always *where the deterministic gate sits and what it protects.*

## 3. The irreversibility gradient (why these four, in this order)

The verticals are sequenced by how irreversible the action behind the human gate
is — this is the clean discriminator that justifies different autonomy levels:

| Interview | Action behind the gate | Reversible? | Autonomy posture |
|-----------|------------------------|-------------|------------------|
| Foundations | (builds the gate itself) | — | teaches all three paths |
| Developer | open a draft PR / request review | Code revert yes; *effects* often no | high autonomy up to the PR; second gate at merge/deploy |
| Finance | post a journal / move money | No (money moved) | low autonomy, maker-checker |
| Legal | finalize/file work product | No (privilege, malpractice) | attorney-in-the-loop mandatory |

**Caveat on "reversible" for Developer:** reverting *code* is not the same as
reversing *effects*. A merged PR can trigger deployments, schema migrations,
security-policy changes, customer-visible regressions, or irreversible data
jobs. So the agent's high-autonomy action is **opening a draft PR / requesting
review**, and **merge/deploy is a distinct second gate** protected by branch
protection, CI, code owners, migration policy, and progressive delivery with
rollback (see §6.1). The gradient still holds — the *first* gate is cheap to
reverse — but autonomy is bounded at the PR, not at merge.

Marketing/Sales (phase 2) sit between Developer and Finance: damage is
reputation/deliverability, not money or filings.

## 4. Shared node-type vocabulary

These interviews reuse the canonical types in `_templates/node-types.json`
(`actor`, `client`, `edge`, `gateway`, `service`, `orchestrator`, `worker`,
`queue`, `stream`, `cache`, `database`, `object-storage`, `index`, `model`,
`observability`, `external`). **No new node types are needed** — map agentic
concepts onto existing types so styling stays consistent:

| Agentic concept | Canonical `type` | Notes |
|-----------------|------------------|-------|
| Agent loop / planner-supervisor | `orchestrator` | the reason→act→observe driver |
| Specialist sub-agent / tool worker | `worker` | scatter-gather subagents |
| LLM inference backend | `model` | prefill/decode, prefix cache |
| Sandbox / execution runtime | `service` (trait `stateful`) | Firecracker microVM, gVisor |
| Tool / MCP server | `external` or `service` | MCP = agent↔tool boundary |
| Vector store / memory index | `index` | semantic/episodic memory |
| Memory / session store | `database` | working + long-term memory |
| Task / job queue | `queue` | queue-based load leveling for agents |
| Trace/event stream | `stream` | OTel GenAI spans |
| Guardrail / policy engine | `service` | injection classifier, FGA |
| Trace/eval/cost backend | `observability` | Langfuse/Phoenix-style |
| Human approver | `actor` | the HITL gate |

Keep a consistent set of **shared patterns** (`patterns[]` / `step.patterns[]`)
across the series, ideally aligned with the existing `data/book/patterns`
catalog. Candidate shared agentic patterns (cross-link with `steps[]`):

- **Agentic loop (ReAct)** — reason→act→observe (already in `ai-coding-cli`).
- **Tool use / function calling.**
- **Orchestrator-workers / scatter-gather subagents.**
- **Human-in-the-loop approval (gate).**
- **Bounded autonomy (agent + deterministic gate).**
- **Workflow vs agent (deterministic pipeline vs probabilistic loop).**
- **Context engineering / compaction.**
- **Memory: short-term vs long-term (semantic/episodic/procedural).**
- **Least privilege / sandboxing (microVM isolation).**
- **Credential brokering (agent never sees secrets).**
- **Lethal-trifecta mitigation / session partitioning** (the at-most-two
  heuristic; not attributed to a named "Rule of Two" — see Theme B).
- **Prompt-injection defense (CaMeL / Dual-LLM / Plan-then-Execute).**
- **Delegation not impersonation (OAuth token exchange, `act` claim).**
- **LLM-as-judge / trajectory evaluation.**
- **Durable execution / checkpointing (resume after crash).**
- **Prefix (prompt) caching; model routing (cost vs quality).**
- **Queue-based load leveling; admission control.**

**This list is the frozen canonical name list.** To avoid synonym drift across
the series, every dataset's `patterns[]` / `step.patterns[]` **must** reuse the
exact names above; do not coin a new name for an already-listed pattern. The
catalog work is sequenced so the vocabulary is canonical *before* the verticals
are authored:

1. After **Foundations** is authored (and before the three verticals), add the
   core agentic patterns above to the **Pattern Catalog** (`data/book/patterns`)
   as canonical entries.
2. Author the verticals using those exact names.
3. Backfill `usedBy[]` links once the dataset IDs exist.

If step 1 slips, the frozen list here still governs `step.patterns[]` naming —
the catalog entries can follow, but the names cannot drift.

## 5. Interview 1 — Agentic Platform Foundations (the anchor)

**Dataset id:** `agentic-platform-foundations`
**Framing:** "Design the shared platform that hosts AI agents at enterprise
scale — the layer every vertical agent team builds on." This is the deep one;
verticals reference it.

**Functional requirements (sketch):** run agent sessions safely; give agents
tools (MCP) and memory; let teams deploy agents without reinventing
infra; evaluate agents before/after deploy; authenticate agents and carry user
authority to downstream systems; observe and debug agent trajectories; support
all three control-flow paths.

**Non-functional:** strong isolation of untrusted/agent-authored code; cost
governance (agents can be large token amplifiers — prefer the compounding
formula in the capacity section over a fixed multiplier; the memorable "~50×"
figure is a research note, `VERIFY BEFORE PUBLISHING`, see §9); multi-tenant
fairness; auditable; resumable across crashes (durable execution); the security
model assumes the model is compromisable.

**Capacity talking points.** Prefer **provider-neutral formulas plus one dated
example** over universal percentages (numbers below are research notes, each
`VERIFY BEFORE PUBLISHING` — see the source backlog in §9): session token growth
compounds because each step re-sends the full transcript (state the formula:
cumulative tokens ≈ Σ context-per-step; a long agent session can grow ~10–16×
over a chat turn); prefix-cache reads are much cheaper than fresh prompt tokens
(quote a *dated* provider example, not a flat "~90%"); a batch/async tier
typically trades latency for a large discount; runaway-loop cost incidents are
real (use as a *qualitative* motivation for hard token budgets that
*terminate*, not as precise dollar figures unless a primary source is cited).

**Steps — a sharp 8-step spine, not a 7-pillar survey.** The `new-interview`
skill recommends 5–7 steps and flagship book cases run ~8–9; an 11-step
"one step per pillar" outline would make the decision-tree and final design too
busy and turn the anchor into a survey. So the seven pillars are *folded* into
eight steps, with the long-tail detail (memory variants, eval frameworks,
serving internals, the protocol map, vendor products) pushed into **deep dives**,
`technologyChoices`, and `toProbeFurther` rather than first-class steps.

The `Pattern:` annotations below are **prose reminders only**; the exact
canonical `step.patterns[]` values to author are in the mapping table that
follows the spine (use those verbatim — they are the frozen §4 names).

1. **Naive hosted agent loop.** ReAct loop calling tools; why the naive version
   doesn't scale to an org. (Echoes `ai-coding-cli` step 1–2.)
2. **Runtime isolation & credential brokering.** Sandboxed execution for
   untrusted/agent-authored code: Firecracker microVM (default for untrusted)
   vs gVisor vs container vs WASM (trade-off table); snapshot/restore for cold
   start. Agent *uses* but never *sees* secrets.
3. **Durable sessions, context & memory.** Durable execution (checkpoint vs
   event-sourced replay; "checkpoints alone are not durable execution" —
   exactly-once side effects) **and** the memory model (short-term vs long-term;
   semantic/episodic/procedural; consolidation; context rot). *Deep dives:*
   vector-only vs temporal knowledge graph (Zep/Graphiti); Mem0 extract→update.
4. **Tool/protocol boundary & identity delegation.** The agent↔tool boundary
   (MCP) and how user authority reaches downstream systems: agent's own
   principal + delegation (RFC 8693 token exchange, `act` claim) — delegation,
   not impersonation; credential vault; MCP as an OAuth 2.1 resource server with
   audience binding (no token passthrough). *Deep dive:* the protocol map (see
   note below).
5. **Security guardrails & data-flow partitioning.** Lethal trifecta and the
   at-most-two heuristic; CaMeL / Dual-LLM / Plan-then-Execute; tool + parameter
   allowlisting; neutralize markdown auto-fetch (the indirect-exfiltration
   vector — cite the EchoLeak/CVE class, `VERIFY BEFORE PUBLISHING` the exact
   CVE); MCP supply-chain (tool poisoning).
6. **Capacity, inference economics & admission control.** Inference backend
   (`model`): prefill/decode disaggregation, prefix caching, continuous
   batching; token budgets that *terminate*; admission control + SLO queueing;
   model routing (cost vs quality).
7. **Evaluation & observability.** Offline golden sets from production failures;
   LLM-as-judge (+ bias control, juries); **trajectory** eval
   (EXACT/IN_ORDER/ANY_ORDER); the flywheel; contamination. Plus OTel GenAI
   spans (session→trace→span; span kinds AGENT/LLM/TOOL/RETRIEVER/GUARDRAIL);
   tail-based sampling; cost roll-ups; silent-failure detection.
8. **Control-flow synthesis: workflow, agent, hybrid gate.** Probabilistic vs
   deterministic pipeline vs hybrid agent+gate, **with the §2 selection rule
   made explicit**; Anthropic's five workflow patterns (prompt-chaining,
   routing, parallelization, orchestrator-workers, evaluator-optimizer). Where
   Theme A lands.

**Exact `step.patterns[]` mapping** (copy these verbatim — frozen §4 names):

| Step | `step.patterns[]` (exact frozen names) |
|------|----------------------------------------|
| 1 | `Agentic loop (ReAct)`, `Tool use / function calling` |
| 2 | `Least privilege / sandboxing (microVM isolation)`, `Credential brokering (agent never sees secrets)` |
| 3 | `Durable execution / checkpointing (resume after crash)`, `Memory: short-term vs long-term (semantic/episodic/procedural)`, `Context engineering / compaction` |
| 4 | `Delegation not impersonation (OAuth token exchange, act claim)`, `Tool use / function calling` |
| 5 | `Prompt-injection defense (CaMeL / Dual-LLM / Plan-then-Execute)`, `Lethal-trifecta mitigation / session partitioning` |
| 6 | `Prefix (prompt) caching; model routing (cost vs quality)`, `Queue-based load leveling; admission control` |
| 7 | `LLM-as-judge / trajectory evaluation` |
| 8 | `Workflow vs agent (deterministic pipeline vs probabilistic loop)`, `Bounded autonomy (agent + deterministic gate)`, `Human-in-the-loop approval (gate)` |

**The protocol map (a deep dive in step 4, not a lineage claim).** Present
protocols as a *boundary map*, not a governance history: **MCP** = agent →
tools/data it consumes; **A2A** = agent ↔ peer agents (interoperability);
**AGNTCY** = ecosystem components around the "Internet of Agents" idea; **ACP**
only if a case is specifically about commerce/payment checkout (OpenAI's public
ACP is the *Agentic Commerce Protocol*, not a general agent-to-agent protocol).
**Do not claim a standards lineage** — in particular do **not** state "ACP
merged into A2A" (research could not confirm it, and "ACP" is ambiguous). Cite
each protocol's own primary spec/announcement; `VERIFY BEFORE PUBLISHING` any
governance/"under Linux Foundation" wording against the primary source.

**Final design:** the full reference platform = control plane (orchestrator) +
sandbox runtime + memory/index + inference backend + identity/vault + guardrails
+ eval harness + observability, with the three paths shown as routing through
the same substrate.

**Wrap-up:** `technologyChoices` (microVM: Firecracker/E2B/AgentCore vs
gVisor/Daytona; memory: Mem0/Zep/Letta/AgentCore Memory; durable: Temporal vs
LangGraph; eval: LangSmith/Braintrust/Phoenix; observability:
Langfuse/OpenLLMetry; serving: vLLM/SGLang/Dynamic). `levelVariants`,
`interviewScript`, `toProbeFurther` (the papers cited above), `patterns`.

## 6. Vertical interviews (each ≈ Foundations + corpus + gate)

Each vertical interview is deliberately *thinner on shared infra* (it references
Foundations) and *thick on the domain gate + grounding corpus*. Use a parallel
step skeleton so the series feels consistent:

> A) domain workflows & requirements → B) grounding corpus / retrieval →
> C) the control plane / orchestration for this domain → D) **the
> domain-specific gate** (the crux) → E) integration with systems of record →
> F) domain compliance / audit → G) eval for this domain.

**How verticals reference Foundations (decide before authoring).** The schema
has **no dedicated cross-dataset reference field** for normal case studies:
`toProbeFurther` links must be HTTP(S), and `patternCatalog.usedBy[]` links are
for *catalog* datasets only. So the reuse must be made visible one of three
ways, chosen here so it is consistent across all three verticals:
1. **Prose** in the dataset `description` / step text ("builds on the shared
   platform in *Agentic Platform Foundations*") — always do this.
2. An **absolute published URL** in `toProbeFurther` once the site is live, e.g.
   `https://system-design-interviews.com/book/interview.html#agentic-platform-foundations`
   (`VERIFY BEFORE PUBLISHING` the real deployed base URL).
3. **Shared `step.patterns[]` names** (the frozen §4 list) plus catalog
   `usedBy[]` backlinks after the catalog is updated — the structural link.

Default: do (1) + (3) in every vertical; add (2) once the canonical base URL is
confirmed.

### 6.1 Agentic Developer Platform — `agentic-developer-platform`
- **Corpus:** repo context — vector RAG over Tree-sitter chunks **vs code-graph
  retrieval** vs agentic grep/read. Hybrid wins.
- **Gate (two-stage — the crux of this vertical's gradient claim):**
  - **Gate 1 (the agent's autonomy ceiling):** *open a draft PR / request review
    on a branch* — never direct-push to a protected branch. Cheap to reverse.
  - **Gate 2 (merge/deploy):** a *distinct* gate protected by branch protection,
    CI, code owners, migration policy, and progressive delivery with rollback —
    because reverting code ≠ reversing effects (deploys, schema migrations,
    data jobs). Auto-merge is an *option* only for low-risk changes under
    progressive delivery + rollback checks.
  - Verification-first throughout (tests/lint run in-sandbox before proposing);
    treat merge-rate as a *vendor-reported* signal, not a benchmark.
- **Distinctive:** fleets of parallel cloud agents (ephemeral sandbox per task,
  scoped creds, configurable egress); async/remote (webhook/cron-triggered,
  pushes to draft PR). Prompt-injection from issue/PR/comment/CI text is the
  live threat.
- **Cite:** Devin/Cognition, GitHub Copilot coding agent, OpenAI Codex cloud,
  Google Jules, Cursor background agents, Factory, Sourcegraph Amp. (Contrast
  with the single-CLI `ai-coding-cli` already in the book — this is the *fleet*
  version.)
- **Reuses from Foundations:** runtime, durable execution, observability.

### 6.2 Agentic Finance Platform — `agentic-finance-platform`
- **Corpus:** the **ledger/GL is ground truth**; sub-ledgers, bank feeds,
  invoices, contracts.
- **Gate:** **money movement + journal posting** behind **maker-checker**
  (segregation of duties enforced architecturally); deterministic thresholds
  decide auto-execute vs escalate; idempotency on every posting/payment.
- **Distinctive:** correctness/auditability **over** availability ("glass box,
  not black box"); control plane separated from probabilistic reasoning
  (BlackLine Studio360/Verity pattern); agents *propose* journals, never freely
  mutate the ledger. **Audit artifact = an immutable decision record, NOT a
  reasoning/chain-of-thought dump.** Log the *auditable evidence and decision*:
  retrieved records and their source versions, tool calls, deterministic
  calculations, policy checks, maker/checker approvals, model-output summaries,
  exception reasons, and immutable event IDs. Keep any raw prompt/model traces
  behind stricter retention, redaction, and access controls — hidden model
  reasoning is not a stable audit log and can leak secrets, private data, or
  prompt-injection artifacts. Workflows: AP (invoice→pay, three-way match),
  AR (cash application), close/reconciliation, FP&A variance, fraud
  (vendor-bank-change/BEC).
- **Control-flow posture (per the §2 selection rule):** prefer **deterministic
  workflows with LLM calls inside bounded nodes** (extract → match → propose →
  maker/checker), *not* an autonomous ReAct loop fenced by a late gate — the
  action path is known and correctness/audit dominate.
- **Compliance:** SOX/ICFR continuous controls; immutable audit trails as
  first-class artifacts.
- **Cite:** BlackLine Verity, HighRadius, Ramp Agents, Vic.ai, Oracle Fusion
  finance agents.
- **Reuses from Foundations:** identity/delegation (money-movement authority),
  guardrails, durable execution. This is the **strongest contrast to Developer**
  — the gate protects an irreversible action.

### 6.3 Agentic Legal Platform — `agentic-legal-platform`
- **Corpus:** grounding over **authoritative legal sources** (Westlaw/Practical
  Law/KeyCite — KeyCite flags overruled/bad law), client matter docs in the DMS.
- **Gate:** **attorney-in-the-loop mandatory** before any work product is
  finalized/filed (UPL; ABA Model Rules 5.3/5.5); a **citation-verification
  gate** that checks existence, currency, and relevance (a real-but-overruled
  citation is worse than a fake).
- **Control-flow posture (per the §2 selection rule):** like Finance, lean
  **deterministic** — retrieve from authoritative sources → draft → verify every
  citation → attorney review — rather than an open autonomous loop, because a
  wrong/overruled citation is a malpractice-grade side effect that must be
  guarded *before* the work product is surfaced.
- **Distinctive:** hallucination is uniquely dangerous and *measured* (Stanford
  study, ~17–33% even on grounded tools — cite as a **dated** finding tied to
  the model versions tested, not a timeless benchmark) → verification is a
  first-class component;
  document provenance (trace every finding to a source span, "audit-defensible");
  confidentiality/isolation (zero-data-retention, no-train, tenant segregation,
  SOC 2). Market shifted RAG → agent tool-calling loops (Harvey; CoCounsel on
  Claude Agent SDK).
- **Workflows:** contract review vs a playbook + redline; due-diligence review
  at scale (tabular extract over 10⁴ docs); research memo with cited sources.
- **Cite:** Harvey, Thomson Reuters CoCounsel, Legora, Hebbia, Ironclad.
  (Robin AI — cite only as a 2025 consolidation case, not a live product.)
- **Reuses from Foundations:** retrieval/grounding, eval (citation correctness),
  security/confidentiality.

## 7. Build order (phase 1)

Author with the `new-interview` skill, one dataset at a time, validating and
building after each:

1. **`agentic-platform-foundations`** — first; it defines the shared vocabulary,
   patterns, and `toProbeFurther` links the verticals reuse. Largest effort.
2. **`agentic-developer-platform`** — closest to the existing `ai-coding-cli`
   prior art; fastest to author; validates the "vertical = Foundations + corpus
   + gate" skeleton.
3. **`agentic-finance-platform`** — strongest contrast (irreversible gate,
   maker-checker, correctness-over-availability).
4. **`agentic-legal-platform`** — citation/hallucination gate, grounding-heavy.

**After dataset 1 (Foundations) and before dataset 2 (Developer):** add the
frozen §4 agentic patterns to `data/book/patterns` as canonical catalog entries
*before* authoring the verticals (so `step.patterns[]` names cannot drift). Backfill `usedBy[]` links
after each dataset ID exists. Consider AI visuals/comics last (separate
generation scripts, then `downsize-images.py`).

**Per-dataset checklist** (from CLAUDE.md and the `new-interview` skill):
- Create `data/book/<id>/interview.json`; register in a new `agentic-platforms`
  category in `data/book/index.json` (`{ id, name, path }`).
- Reuse canonical node types (§4); structured `view`/`sequence` only (no raw
  Mermaid in steps/flows). Use only frozen §4 pattern names.
- **Run the book verifier first — it is the mandatory automated gate.** It
  catches what `json.load` cannot: broken `view.nodes`/`view.links`/`highlight`,
  unresolved `satisfies.steps`/`patterns.steps`, unknown `parent`, missing
  structured `sequence` objects, and rejected raw `diagram` fields:
  ```bash
  node data/book/_verify.mjs
  python3 -c "import json; json.load(open('data/book/<id>/interview.json'))"
  python3 build.py book
  ```
- Keep the manual cross-check (`view.highlight`/`view.links`/
  `satisfies[].steps[]` resolve) as a secondary pass.
- Commit the regenerated `docs/book/`. Optional `data/book/<id>/icon.png`.

## 8. Phase 2 — three enterprise-function verticals (DELIVERED)

The remaining enterprise functions, built once phase 1 validated the skeleton.
All three follow the §6 A–G skeleton, reuse the frozen §4 patterns, and extend
the irreversibility gradient *between* Developer and Finance — the damage behind
each gate is reputation/compliance or a legally-consequential decision, not
money or a filing.
- **`agentic-marketing-platform`** — gate: brand-claim/negative-claim review +
  C2PA provenance; corpus: brand kit/DAM; bandit optimization loop. Cite Jasper,
  HubSpot Breeze, Agentforce Marketing, Adobe GenStudio.
- **`agentic-sales-platform`** — gate: deliverability/reputation + opt-out
  suppression + approval-before-send; corpus: CRM + waterfall enrichment. Cite
  Agentforce SDR, 11x, Clay, Gong.
- **`agentic-hr-platform`** — gate: human review on hiring + adverse-impact
  (four-fifths) monitoring; corpus: policy KB (effective-dated, jurisdiction);
  PII-scoped retrieval. Cite Workday Illuminate, ServiceNow HRSD/Moveworks,
  Eightfold, Paradox. Compliance: NYC LL144, EU AI Act high-risk (date in flux).

## 8b. Phase 3 — four verticals that teach a *new* gate (DELIVERED)

> Selection rule for any further vertical: it earns a slot only if its **gate
> type or dominant constraint is not already taught** by the existing seven
> (Developer = two-stage / revert≠reverse; Marketing = optimization-inside-a-gate
> + provenance; Sales = deliverability + global suppression; HR =
> adverse-impact fairness; Finance = maker-checker + idempotency + correctness
> over availability; Legal = citation verification + hallucination-as-first-class).
> A domain that only re-skins one of those is better as a level-variant or a
> deep dive, not a new dataset.

Phase 3 picks **one flagship per domain family**, each adding a genuinely new
axis. Together they extend the series from the enterprise-function set to the
full gradient: *revertible → reputation → decision/fairness → money → filing →
**physical harm***, plus the **real-time** and **contestability** axes the
function set never reaches.

- **`agentic-healthcare-platform`** — Clinical decision support. **New on the
  gradient: the irreversible action is harm to a person**, strictly above Legal.
  - *Gate:* clinician sign-off; **abstain-don't-guess** as the safe default
    (the platform declines rather than answers when confidence/grounding is low).
  - *Corpus:* clinical guidelines + the patient record; **PHI-scoped retrieval**.
  - *Distinctive:* a **safety case** and fail-safe defaults; HIPAA/PHI scoping;
    SaMD/FDA regulatory framing; grounding-or-abstain rather than hallucinate.
  - *Cite (VERIFY BEFORE PUBLISHING):* clinical-LLM offerings and SaMD guidance;
    treat any accuracy figure as a dated claim, like the Legal hallucination note.
  - *Reuses from Foundations:* grounding, eval (calibration/abstention),
    security/confidentiality.

- **`agentic-support-platform`** — Customer support / CX agent. **New axis:
  real-time, in-conversation, transactional.** Everything in phases 1–2 gates
  *before* an async action; this gates *inside* a live loop.
  - *Gate:* the agent takes transactional actions (refund, cancel, reschedule)
    **mid-conversation, on the customer's behalf**, with in-conversation
    escalation/handoff to a human at the boundary.
  - *Corpus:* product/policy KB + the customer's account/order record (scoped).
  - *Distinctive:* a **real-time turn-taking latency budget**; transactional
    side effects with rollback; the gate moves into the live loop; deflect-vs-
    escalate routing. Natural home for **agentic-commerce / checkout** as an
    option, where the *ACP (Agentic Commerce Protocol)* deliberately scoped out
    of Foundations §5 becomes the subject (delegated payment authority + cart
    idempotency).
  - *Cite (VERIFY BEFORE PUBLISHING):* support-agent and CX offerings.
  - *Reuses from Foundations:* identity/delegation (act-on-behalf-of), durable
    execution (transactional rollback), guardrails.

- **`agentic-public-benefits-platform`** — Government benefits / eligibility.
  **New gate dimension: contestability / due process.** The audit record must be
  legible to the affected person and a reviewer, not just to a compliance team.
  - *Gate:* a caseworker decision affecting a citizen's rights, with an
    **appeal path** and **explainability-for-appeal** built in.
  - *Corpus:* statute/eligibility rules (effective-dated, jurisdiction-tagged) +
    the applicant record.
  - *Distinctive:* contestability (the decision can be challenged and reviewed),
    audit-for-appeal (a record the applicant can understand), bias-at-population-
    scale monitoring, and a deterministic eligibility engine the LLM can't
    override. (Content moderation / trust & safety is the close sibling —
    population-scale takedown decisions with appeal queues and reviewer
    calibration — and is the better second pick in this family if a second is
    wanted; keep it as a candidate, not a commitment.)
  - *Cite (VERIFY BEFORE PUBLISHING):* gov-tech / eligibility-automation
    references; note due-process and algorithmic-accountability constraints.
  - *Reuses from Foundations:* identity/PII scoping, eval/fairness,
    observability/audit.

- **`agentic-research-platform`** — Scientific research agent. **New gate: a
  physical-experiment boundary** plus reproducibility.
  - *Gate:* the agent proposes experiments; a human authorizes anything that
    **consumes reagents, drives a lab robot, or has biosafety implications**.
  - *Corpus:* primary scientific literature + experimental data, with
    **provenance for every claim** (traceable hypotheses/findings).
  - *Distinctive:* reproducibility as a first-class property; gating **physical
    lab automation** (the wet-lab boundary is what separates it from Legal's
    research grounding); a deterministic protocol/safety check before execution.
  - *Cite (VERIFY BEFORE PUBLISHING):* lab-automation and research-agent work;
    biosafety/dual-use framing.
  - *Reuses from Foundations:* retrieval/grounding, durable execution, eval.

**Build order (when phase 3 is greenlit):** Healthcare first (clearest gradient
extension and the strongest single addition), then Support (the real-time axis),
then Public Benefits (contestability), then Research (physical-experiment
boundary). Same per-dataset checklist as §7; backfill catalog `usedBy[]` after
each. If all four land, consider the **capstone synthesis interview**
("Choosing the Right Agent Gate") — a Pattern-Catalog-style comparison of every
gate across the series — as the navigational spine; it gets materially more
valuable at 10+ verticals.

**Explicitly deferred / fold-in, not standalone** (they re-skin an existing
gate): personal/consumer assistant (≈ Support); autonomous-vehicle & drone fleet
ops (≈ an industrial-robotics option); data-science/analytics agent (≈ Finance
pipeline + eval); education/grading (≈ a Public-Benefits contestability option).
Industrial / robotics / physical-ops is a strong *fifth* candidate (operator-
authorized actuation with a hardware kill-switch + real-time safety envelope) —
hold it as the lead of a possible phase 4 rather than crowding phase 3.

## 9. Sourcing: caveats and the source backlog

All vendor metrics (merge rates, accuracy %, time savings) are **vendor
marketing** — present as claims, not benchmarks. Provider names, prices, rate
limits, and spec revisions move monthly — re-verify before publishing. Anything
tagged `VERIFY BEFORE PUBLISHING` above is a research note, not a publishable
fact; resolve it against a primary source (or drop/soften it) before it lands in
`requirements`, `capacity`, or `toProbeFurther`.

**Source backlog** — every volatile claim, its intended use, and whether it is
safe to publish yet. Fill the *Primary source* / *Date checked* columns before
authoring the dataset that uses the claim.

| Claim (as researched) | Intended use | Primary source | Date checked | Safe? |
|---|---|---|---|---|
| Lethal trifecta (Willison) | Theme B anchor | *(add post URL)* | — | after source |
| "At-most-two" heuristic | Theme B | none found — state unattributed; **do not** call it "Meta Agents Rule of Two" | — | only unattributed |
| Session token growth ~10–16× | Foundations capacity | prefer a formula + dated provider example | — | formula only |
| "~50×" agent token multiplier | Foundations non-functional | none found — prefer the compounding formula | — | formula only |
| Prefix-cache read discount | Foundations capacity | dated provider pricing | — | dated example |
| Batch/async tier discount | Foundations capacity | dated provider pricing | — | dated example |
| Runaway-loop $ incidents | Foundations capacity | use qualitatively | — | qualitative |
| EchoLeak / CVE class (markdown auto-fetch) | Security step | NVD CVE id | — | verify CVE# |
| Stanford legal hallucination ~17–33% | Legal distinctive | the Stanford study (dated, model-version-bound) | — | as dated finding |
| EU AI Act high-risk deadline | Phase-2 HR compliance | EU AI Act text (2 Aug 2026 vs proposed deferral) | — | hedge date |
| OpenAI Evals deprecation | eval `technologyChoices` | OpenAI docs | — | verify |
| Langfuse ← ClickHouse (Jan 2026) | observability `technologyChoices` | primary announcement | — | verify |
| Patronus **not** acquired by Datadog | eval `technologyChoices` | — | — | state the negative |
| Protocol governance ("under Linux Foundation"; **no** "ACP merged into A2A") | protocol map (step 4) | each protocol's own primary spec | — | verify per §5 note |

**Compliance / legal / regulatory anchors to attach before publishing.** These
are high-stakes domain references that must cite a **primary source**, not a
vendor summary or memory, before they enter a dataset's prose or
`toProbeFurther`. Stable, but verify the exact citation/edition at authoring
time.

| Anchor | Used by | Primary source to attach | Date checked | Note |
|---|---|---|---|---|
| UPL; ABA Model Rules 5.3 & 5.5 | Legal gate | ABA Model Rules text | — | the unauthorized-practice / supervision basis for attorney-in-the-loop |
| Westlaw / Practical Law / KeyCite | Legal corpus | Thomson Reuters product docs | — | KeyCite = the "bad law" flagging mechanism; vendor source acceptable as product fact |
| SOX / ICFR continuous controls | Finance compliance | SOX §404 / SEC/PCAOB guidance | — | basis for maker-checker + immutable audit trail |
| C2PA content provenance | Phase-2 Marketing gate | C2PA specification | — | synthetic-media disclosure |
| NYC Local Law 144 (AEDT) | Phase-2 HR compliance | NYC LL144 text / DCWP rules | — | bias-audit + candidate-notice obligations |
| EU AI Act high-risk (hiring) | Phase-2 HR compliance | EU AI Act, Annex III | — | hedge the deadline — see backlog row above |

Stable primary sources worth citing across the series (for `toProbeFurther`):
ReAct (arXiv:2210.03629); Anthropic "Building Effective Agents" (2024);
Firecracker (NSDI '20); MemGPT (arXiv:2310.08560) / Mem0 (arXiv:2504.19413) /
Zep (arXiv:2501.13956); RouteLLM (arXiv:2406.18665); CaMeL (arXiv:2503.18813);
"Design Patterns for Securing LLM Agents" (arXiv:2506.08837); τ-bench
(arXiv:2406.12045); "SWE-Bench Illusion" (arXiv:2506.12286); RFC 8693 (token
exchange); MCP / A2A primary specs; OTel GenAI semantic conventions; OWASP Top
10 for LLM Apps 2025. (Note: the "Agents Rule of Two" item was **removed** from
this list — research could not verify it; see Theme B and the backlog.)
