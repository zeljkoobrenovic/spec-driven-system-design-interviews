# Review: Agentic Legal Platform - System Design

Reviewed file: `data/book/agentic-legal-platform/interview.json`
Review date: 2026-06-23

## Executive Summary

This review reflects the current post-revision dataset. The interview is now a strong and production-aware legal-agent case study. The earlier gaps around capacity, workflow-aware APIs, citation-verification evidence, review state, confidentiality placement, probe links, and step diagram omissions have mostly been addressed.

The core teaching move is excellent: legal AI is not "RAG plus drafting"; it is a deterministic, attorney-gated work-product pipeline where every citation is checked for existence, currency, and relevance before a licensed attorney finalizes anything. The remaining improvements are narrower and mostly about internal consistency and operational depth: align the job/review state machine across API and data model, add the domain entities implied by the workflow fields, and make provider/retention/eval controls concrete enough for a staff-level design.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Strong architecture and domain model; a few referenced entities and state transitions are still implicit. |
| Production realism | 4/5 | Much stronger on capacity, provider limits, correction loops, and audit evidence; still needs sharper operational policies. |
| Pedagogical flow | 4/5 | Clear baseline -> grounding -> pipeline -> cite gate -> attorney gate -> trust -> workflows arc. |
| Dataset/rendering fit | 5/5 | JSON parses cleanly; node/link/step references resolve; prior diagram omissions are fixed. |
| Overall | 4/5 | A strong interview dataset, close to flagship quality after a consistency pass. |

## What Works Well

- The revised capacity section now converts legal workflows into concrete work units: matters/day, cites/memo, diligence batch size, token scale, provider calls, queueing, and concurrency caps.
- The API is now asynchronous, workflow-aware, and idempotent. `matterId`, `task`, `jurisdiction`, `sourceCorpus`, `playbookId`, `outputSchemaId`, `reviewAssignee`, and `idempotencyKey` are the right fields.
- Citation verification is no longer a black box. Step 4 now names proposition spans, source spans, KeyCite status, relevance score, verifier version, decision state, correction loop, audit evidence, and provider limits.
- Confidentiality now appears early in Step 2 as a retrieval constraint, not only as later hardening. That is the right legal-platform posture.
- The attorney review step now describes assignment, annotation, request changes, rejection, approval, high-risk second review, license/jurisdiction validation, and audited cite override.
- Workflow-specific outputs are present: redlines, diligence findings, source spans, confidence, and attorney ground-truth eval.
- `toProbeFurther` is now populated with relevant legal hallucination, professional responsibility, confidentiality, citator, and RAG evaluation links.

## Highest-Impact Issues

### 1. The lifecycle state machine is split across API prose and data model

The API says a draft moves through `queued -> drafting -> verifying -> (correcting ->) awaiting_review`, and Step 4 describes repeated verification attempts and correction loops. The `drafts.status` field only lists `awaiting_review, changes_requested, finalized, returned, rejected`.

Why it matters: this is now the main consistency gap. The architecture depends on retryable asynchronous jobs, correction loops, review returns, and finalization, but the persisted state model does not fully represent the pre-review job lifecycle.

Concrete fix:

- Split job state and review state, or expand the draft status enum.
- Add states such as `queued`, `drafting`, `verifying`, `correcting`, `verification_failed`, `awaiting_review`, `changes_requested`, `approved`, `finalized`, `rejected`.
- Make the "request changes" path explicit: attorney event -> correction loop -> reverify -> awaiting review.
- Add terminal failure behavior for repeated cite failures or provider outage, likely `human_exception` or `verification_blocked`.

### 2. Several referenced workflow entities are implied but not modeled

The revised API and deep dives reference `playbookId`, `outputSchemaId`, redline `rule_id`, diligence `batch_id`, extraction schemas, and per-document batch status. The data model includes `redlines` and `diligence_findings`, but it does not define playbooks/rules, diligence batches, extraction schemas, per-document batch attempts, or source corpora as first-class entities.

Why it matters: the interview now promises real contract review and diligence workflows. Without these entities, the schema still cannot fully support the user-facing API or the operational claims around resumability and partial completion.

Concrete fix:

- Add `playbooks` and `playbook_rules` tables referenced by contract-review redlines.
- Add `diligence_batches`, `diligence_documents`, and `extraction_schemas` for per-document status, checkpointing, poison-document DLQ, and partial completion.
- Add `source_corpora` or `corpus_versions` for Westlaw/Practical Law/statute snapshots, freshness, and version pinning.
- Connect these entities to `review_events` and `audit_events` so returned/edited outputs preserve their lineage.

### 3. Provider operations are mentioned but not yet operationalized

The dataset now correctly names KeyCite/Westlaw rate limits, caching, batching, timeouts, retries, circuit breakers, and source-version drift. That is a major improvement, but it remains mostly prose.

Why it matters: legal-source providers and inference providers are external bottlenecks with commercial, latency, freshness, and outage behavior. This is where a staff-level answer should show concrete controls.

Concrete fix:

- Add a short deep dive or data-model row for provider call attempts: provider, operation, request hash, source version, timeout, retry count, response status, cached result, and cost.
- Define stale-cache behavior for citation currency: when cached KeyCite status is acceptable, when it must be refreshed, and what happens during provider outage.
- State explicit retry limits and DLQ behavior for verification and diligence extraction.
- Include spend controls beyond "global token budget": per-matter budget, per-client quota, and priority between interactive memos and offline batches.

### 4. Evaluation needs release-gate semantics

The dataset correctly identifies citation-error rate, unsupported-finding rate, trajectory eval, and attorney ground truth. It stops short of explaining how those metrics gate rollout or regression.

Why it matters: legal AI evaluation is not just observability. If a new verifier, retriever, or model increases off-point citations, the platform must block or stage rollout.

Concrete fix:

- Add thresholds or policy examples: max citation-error rate, max unsupported-finding rate, and required attorney-adjudicated sample size.
- Distinguish offline eval sets, shadow eval on production drafts, and production monitoring.
- Track results by task type (`contract_review`, `diligence`, `memo`) because failure modes differ.
- Add a rollback or holdout story for model/verifier/corpus changes.

## System Design Soundness

The requirements are now coherent and specific. Functional requirements cover contract redlines, diligence extraction, cited memos, citation verification, and attorney approval. Non-functional requirements correctly prioritize hallucination, traceability, confidentiality, authoritative grounding, and deterministic control flow.

The capacity model is now credible. It gives interactive memo volume, citation-verification volume, diligence batch scale, token scale, provider calls, queue behavior, and per-matter/global throttles. The remaining sizing gap is that the caps are directional rather than numerical; that is acceptable for this dataset, but a staff-level interview could ask the candidate to choose specific queue and provider budgets.

The API shape is strong. `/v1/drafts` is async and idempotent, `/v1/drafts/{id}` exposes lifecycle and batch progress, `/v1/drafts/{id}/review` captures review decisions, and `/v1/drafts/{id}/provenance` exposes support evidence. The main fix is to align these lifecycle states with the data model.

The data model is much better than the original review described. Matters, documents, drafts, citations, citation verification attempts, redlines, diligence findings, review events, provenance, and audit events are all present. The missing pieces are the parent entities those rows reference: playbook rules, diligence batches, extraction schemas, source corpora, and provider-call attempts.

The architecture has the right components and link structure: `Gateway`, `Pipeline`, `DraftAgent`, `AuthIndex`, `DMS`, `CiteVerifier`, `DraftStore`, `Provenance`, `Guardrail`, `Identity`, `AuditLog`, `TaskQueue`, and `Observability`. The correction loop from verifier to draft agent is explicit, and the final design integrates the steps.

## Step-by-Step Pedagogical Review

### Step 1: Naive Agent

Strong baseline. It makes the legal failure concrete: fluent output, fake or overruled citations, no provenance, no attorney review, and confidentiality risk. The trap is domain-specific and useful.

Improvement: no major issue. This step does exactly what it needs to do.

### Step 2: Ground in Authoritative Law

This step is materially improved. It now introduces tenant, matter, jurisdiction, document version, ethical walls, guardrail/access-policy checks, untrusted matter documents, and source versioning before retrieval becomes trusted.

Improvement: consider briefly separating "authoritative legal corpus" from "client matter corpus" as two source lifecycle tracks. Westlaw/KeyCite freshness and DMS document versioning fail differently.

### Step 3: Deterministic Pipeline

The recommended deterministic pipeline option is still the right trade-off. The contrast with an autonomous research loop teaches why the verifier must be a mandatory stage.

Improvement: clarify the `DraftStore` write. In the step diagram, `Pipeline -> DraftStore` appears before the citation-verification step has been introduced. The API sequence writes the pending draft after verification. Either wording is defensible if the store holds internal draft artifacts, but the dataset should say whether `DraftStore` contains unverified intermediate drafts, verified drafts awaiting review, or both with different statuses.

### Step 4: Citation Gate

This is now the strongest step. The existence/currency/relevance framing is memorable, the correction loop is explicit, and the deep dives cover relevance scoring, evidence rows, provider limits, outages, and source-version pinning.

Improvement: add one sentence on how attorney override interacts with machine-flagged citations. The data model has `attorney_overridden`; Step 5 mentions policy-permitted overrides. Step 4 can cross-reference that an override never means "machine passed"; it means a licensed attorney accepted the risk with evidence attached.

### Step 5: Attorney-in-the-Loop

The step correctly treats review as a workflow, not a button. It includes assignment, annotation, request changes, approval, rejection, second review, license/jurisdiction source, and audit events.

Improvement: align the review event actions with API response statuses and draft statuses. Today the prose is richer than the `drafts.status` enum.

### Step 6: Confidentiality and Provenance

This step is concise and right. It correctly says confidentiality and provenance sit under everything, and the diagram now includes `Pipeline`, so the intended links render.

Improvement: add operational retention detail if space allows: prompt traces, retrieved snippets, model outputs, eval traces, audit records, and raw matter documents likely have different retention/redaction policies.

### Step 7: Workflows at Scale and Evaluation

The step is much stronger than before. The deep dives distinguish contract review, diligence extraction, and evaluation against attorney ground truth. Diligence now includes checkpointing, per-document errors, DLQ, low-confidence human adjudication, and concurrency caps.

Improvement: this step now references several entities that should exist in the data model: batches, extraction schemas, document-level batch status, and playbook rules.

## Final Design Review

The final design integrates the major components and now reads like a credible production architecture. It covers deterministic control flow, access-scoped retrieval, version-pinned authoritative law, correction loops, reviewable verification evidence, provenance, attorney review, identity binding, confidentiality, immutable audit, evaluation, provider limits, retries, and circuit breakers.

Remaining gaps:

- The final design says work queues and correction loops exist, but the persisted lifecycle states are not fully modeled.
- Workflow-specific parent entities are missing even though the API and deep dives refer to them.
- Provider-call operations are named but not modeled as observable, auditable attempts.
- Evaluation is described as monitoring; it should also be a release gate for retriever, verifier, model, and corpus changes.

## Concept Introduction and Learning Flow

The flow is now strong. Confidentiality appears in Step 2, the deterministic pipeline is motivated before the citation gate, and the attorney gate lands after machine verification. The sequence helps a candidate build the answer incrementally.

The only sequencing ambiguity is the `DraftStore` write in Step 3 before Step 4 verification. A small clarification would avoid suggesting that an unverified draft is ready for attorney review.

The patterns are well chosen: deterministic workflow vs agent loop, bounded autonomy, human-in-the-loop gate, memory/grounding, prompt-injection defense, delegation, and queue-based load leveling.

## Step-to-Final-Design Coherence

The step progression maps cleanly to final design:

- Step 1 introduces `DraftAgent`, `Inference`, and `DraftStore`.
- Step 2 adds `AuthIndex`, `DMS`, and `Guardrail`.
- Step 3 adds `Pipeline` and `TaskQueue`.
- Step 4 adds `CiteVerifier`, correction loop, and verification audit evidence.
- Step 5 adds `Attorney`, `Identity`, and review/audit semantics.
- Step 6 adds `Provenance` and confidentiality posture.
- Step 7 adds `Observability` and workflow scale.

`Matter` and `Gateway` appear only in the final design, but that is acceptable because the API section introduces the ingress shape. If desired, a tiny note in Step 2 or Step 3 could make the API ingress less abrupt.

## Realism Compared With Production Systems

The current dataset is realistic on the central domain risks: overruled citations, off-point authorities, attorney supervision, access-scoped retrieval, source spans, version pinning, and no auto-filing.

The remaining realism gaps are operational:

- Citation currency cache freshness and provider outage policy need more explicit behavior.
- Diligence batch state should include document-level attempts, poison documents, retries, and partial completion entities.
- Retention/redaction should differ for prompts, retrieved snippets, model outputs, eval traces, audit events, and finalized work product.
- Legal hold, client export/deletion, and immutable audit retention can conflict; the platform should name the policy boundary.
- Evaluation should gate release, not only report metrics.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- All `view.nodes` references resolve to `highLevelArchitecture.nodes`.
- All `view.links` references resolve to `highLevelArchitecture.links`.
- All visible step/final-design links include both endpoints in the current view; the earlier `confidentiality` and `workflows-eval` rendering issue is fixed.
- All `satisfies[*].steps[*]` references resolve to real step IDs.
- All `patterns[*].steps[*]` references resolve to real step IDs.
- Sequence participant/message references resolve to canonical node IDs or declared participants.
- Node types now follow the project convention; `Matter` is `external`, not `client`.
- `toProbeFurther` and `technologyChoices` are populated. AI visuals and comic assets are absent, which is valid for this dataset.

## Recommended Edits, Prioritized

### P1: Align job, verification, and review states

Make API lifecycle, `drafts.status`, `review_events.action`, correction-loop behavior, and terminal failure states agree.

### P1: Add the workflow parent entities now referenced by API and deep dives

Add playbooks/playbook rules, diligence batches, extraction schemas, document-level batch status, source corpora/corpus versions, and provider-call attempts.

### P2: Clarify `DraftStore` semantics

State whether it stores unverified internal drafts, verified drafts awaiting review, finalized work product, or all of them with separate statuses.

### P2: Operationalize provider limits and cache freshness

Add retry limits, cache TTL/freshness rules for legal authority checks, outage behavior, per-matter spend budget, and DLQ criteria.

### P2: Turn eval metrics into release gates

Define how citation-error and unsupported-finding rates block or stage model, retriever, verifier, prompt, and corpus-version changes.

### P3: Add retention and legal-hold nuance

Differentiate retention/redaction for traces, snippets, drafts, eval samples, immutable audit events, and finalized work product.

## What Not To Change

- Keep the citation-verification gate as the central design move.
- Keep the deterministic pipeline recommendation over an autonomous research loop.
- Keep attorney approval mandatory and identity-bound.
- Keep confidentiality in the grounding step, not only the later trust step.
- Keep workflow-specific deep dives for contract review, diligence, and evaluation.
- Keep the curated probe links; they make this domain-specific and defensible.

## Bottom Line

The recent changes moved this dataset from a strong conceptual walkthrough to a credible production-oriented interview. The next pass should be a consistency pass, not a redesign: align lifecycle states, model the workflow entities already implied by the API, and make provider/eval/retention operations concrete.
