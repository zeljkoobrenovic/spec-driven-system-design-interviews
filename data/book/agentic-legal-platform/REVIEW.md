# Review: Agentic Legal Platform - System Design

Reviewed file: `data/book/agentic-legal-platform/interview.json`
Review date: 2026-06-23

## Executive Summary

This is a strong case-study outline with the right central insight: legal AI is not just "RAG plus drafting"; the hard gate is citation correctness, attorney approval, provenance, and confidentiality. The teaching arc is clear and the final design mostly integrates the components introduced in the steps.

The main weakness is that the dataset is still closer to a crisp conceptual walkthrough than a production system design. The capacity model, API, data model, and operational failure modes need more concrete machinery for real legal workflows: batch diligence, contract redlining, citation-verification evidence, provider rate limits, review state transitions, source versioning, and ethical-wall enforcement.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Strong control-plane framing, but verifier semantics, workflow state, and source lifecycle are under-modeled. |
| Production realism | 3/5 | Mentions the right risks, but lacks retries, provider limits, ingestion/versioning, DLQs, and legal-review operations. |
| Pedagogical flow | 4/5 | Baseline -> grounding -> pipeline -> gate -> attorney -> trust -> eval is effective. |
| Dataset/rendering fit | 3/5 | JSON and references parse cleanly, but some step view links will not render because their endpoints are omitted. |
| Overall | 4/5 | Good interview case; needs concrete production details before it feels staff-level. |

## What Works Well

- The domain crux is well chosen: a real-but-overruled citation is treated as a first-class failure, not just a generic hallucination.
- The deterministic retrieve -> draft -> verify -> review pipeline is the right default for legal work products.
- The attorney-in-the-loop step is framed as mandatory professional responsibility, not optional UX.
- Provenance is tied to source spans and versions, which is the right basis for audit-defensible legal output.
- The final design includes the core components introduced earlier: `Pipeline`, `DraftAgent`, `AuthIndex`, `CiteVerifier`, `DraftStore`, `Provenance`, `Guardrail`, `Identity`, `AuditLog`, `TaskQueue`, and `Observability`.
- The dataset uses structured views and sequence flows rather than raw Mermaid for architecture steps, which fits the renderer conventions.

## Highest-Impact Issues

### 1. Citation verification is named correctly but not specified enough

Step 4 correctly makes existence, currency, and relevance the gate. The missing production detail is how the system represents verification evidence and decisions.

Why it matters: existence and currency can be checked against legal-authority metadata, but relevance is a semantic claim about whether a cited authority supports a specific proposition. That needs thresholds, evidence, escalation paths, and reviewable artifacts. Without those, the most important component in the design is still a black box.

Concrete fix:

- Add fields to `citations` or a new `citation_verifications` table: `proposition_text`, `proposition_span`, `source_span`, `jurisdiction`, `authority_type`, `keycite_status`, `verified_at`, `verifier_version`, `relevance_score`, `decision`, `blocking_reason`.
- Distinguish machine-pass, machine-flagged, and attorney-overridden states.
- Add a failure path in the architecture: flagged cite -> correction loop -> reverify, with audit entries for each attempt.
- Add a deep dive explaining that relevance is not purely deterministic and may require model-assisted scoring plus attorney escalation.

### 2. The three promised legal workflows are too compressed

The requirements promise contract review with redlines, due-diligence tabular extraction, and research memos. Step 7 lists them, but the API and data model mostly model one generic `draft`.

Why it matters: these workflows produce different outputs and need different state:

- Contract review needs playbook/rule IDs, clause spans, risk severity, redline diffs, and rationale.
- Due diligence needs batch jobs, extraction schemas, per-document status, table cells, confidence, and source spans.
- Research memos need jurisdiction, question presented, authority hierarchy, citation verification, and memo sections.

Concrete fix:

- Add workflow-specific request fields to `/v1/drafts`: `jurisdiction`, `playbookId`, `outputSchemaId`, `sourceCorpus`, `reviewAssignee`, and `idempotencyKey`.
- Add workflow tables or child entities for redlines, diligence findings/cells, and memo propositions.
- Split Step 7 into sub-steps or deep dives for contract review and diligence at scale so the case does not end with a generic "run workflows" statement.

### 3. Capacity and operations are qualitative only

The capacity section says "every cite", "draft-only", and "thousands of docs", but it does not convert those into work units.

Why it matters: system design interviews need sizing to justify queues, parallelism, provider throttling, and cost controls. Legal platforms are especially sensitive to expensive retrieval, long documents, and third-party legal-database limits.

Concrete fix:

- Add estimates for matters/day, documents/matter, pages/document, tokens/page, citations/draft, verification calls/citation, and peak batch concurrency.
- Add latency targets separately for interactive memo drafting and offline diligence review.
- Add provider constraints: legal-source API rate limits, inference budget, retry policy, timeout budget, circuit breakers, and backpressure.
- Add queue behavior: per-matter concurrency caps, DLQ, checkpointing, resumable batch extraction, and idempotent retry.

### 4. Confidentiality and ethical walls arrive late in the teaching flow

Step 6 is good, but confidentiality affects ingestion and retrieval from Step 2 onward. The current flow introduces DMS access and authoritative grounding before it has fully introduced matter ACLs, ethical walls, provider retention policy, and untrusted-document handling.

Why it matters: in a legal platform, data isolation is not a later hardening layer. It changes which documents can be retrieved, which providers can be called, which traces can be stored, and who can approve.

Concrete fix:

- Pull a short "tenant/matter access boundary" into Step 2 or Step 3.
- Show `Guardrail` or an access-policy service on the early grounding path, not only in the later trust step.
- Add explicit storage-retention and trace-redaction behavior for prompts, retrieved snippets, model outputs, and audit records.
- Model ethical-wall enforcement as a policy check on every retrieval and approval action.

### 5. Some authored diagram links will not render

The JSON references all valid links, but the renderer only emits a link when both endpoints are included in the current `view.nodes`. These step views include links whose endpoints are absent:

- Step `confidentiality`: `pipe-guard`, `pipe-prov`, and `pipe-log` all start at `Pipeline`, but `Pipeline` is not in `view.nodes`.
- Step `workflows-eval`: `draftstore-attorney` starts at `DraftStore`, but `DraftStore` is not in `view.nodes`.

Why it matters: the diagrams will silently omit those links. Step 6 will mostly show `Guardrail -> DMS` while losing the provenance and audit links the caption describes.

Concrete fix:

- Add `Pipeline` to Step 6 `view.nodes`, or replace those links with links whose endpoints are visible.
- Add `DraftStore` to Step 7 `view.nodes`, or remove `draftstore-attorney` from that step view.

## System Design Soundness

Requirements are well scoped around legal work product risk. The functional set is coherent, and the non-functional set correctly prioritizes hallucination, provenance, confidentiality, authoritative grounding, and deterministic control flow.

Capacity needs real numbers. The current values are labels, not a sizing model. The design introduces a `TaskQueue`, but the reader cannot infer why it is sized the way it is, what gets queued, how batches are partitioned, or where the provider bottlenecks sit.

The API is directionally right but too narrow. `/v1/drafts` needs to be asynchronous and workflow-aware. It should expose a job lifecycle, idempotency key, matter/tenant scope, jurisdiction, source-corpus selection, playbook or output schema, and review assignment. `/v1/drafts/{id}/approve` needs richer state transitions: approve, request changes, reject, finalize, file externally, and attorney override of a flagged cite if policy allows.

The data model captures drafts, citations, and provenance, but it is missing the entities that make the system credible: matters, documents, document versions, ingestion jobs, source corpora, playbooks, redline suggestions, diligence extraction rows/cells, review events, verification attempts, and immutable audit records. The `citations` table needs more detail than booleans because the verifier is the core design component.

The architecture has the right components, but the correction loop is not visible enough. A citation gate that flags bad authority should route back to drafting or a human exception queue before producing a review packet. Provider outages, legal-database freshness, and source-version pinning should also be explicit.

## Step-by-Step Pedagogical Review

### Step 1: Naive Agent

Strong baseline. It makes the malpractice-grade failure concrete and creates a reason for the rest of the design. The trap is useful and domain-specific.

Improvement: call out confidentiality and privilege even more directly here as a co-equal failure with hallucinated citations, because it affects provider and storage choices immediately.

### Step 2: Ground in Authoritative Law

Good introduction of Westlaw/Practical Law/KeyCite and DMS grounding. This is the right point to distinguish authoritative law, matter documents, and open web sources.

Improvement: add source-ingestion/versioning and access-policy detail. Retrieval should be constrained by tenant, matter, jurisdiction, document version, and ethical wall. The current view includes `Guardrail -> DMS`, but the prose should make the access boundary more operational.

### Step 3: Deterministic Pipeline

The recommended deterministic pipeline option is well chosen. The contrast with an autonomous research loop teaches the right trade-off.

Improvement: make the job model explicit. The pipeline should show asynchronous job creation, per-matter queueing, checkpointing, and idempotent retries. The current `pipe-draftstore` link can also be read as writing a draft before verification; clarify whether this is an internal draft artifact or a review-ready draft.

### Step 4: Citation Gate

This is the strongest step and the right centerpiece. The existence/currency/relevance framing is memorable and defensible.

Improvement: deepen relevance checking and failure handling. Show the correction loop, verifier evidence, disputed/uncertain states, and legal-source provider constraints. The sequence flow should include audit logging of verification results because the final architecture has `verify-log`.

### Step 5: Attorney-in-the-Loop

The gate is framed correctly: verification does not replace attorney responsibility. Binding finalization to a licensed attorney principal is a strong detail.

Improvement: add review workflow state. A real platform needs request-changes, annotate, assign reviewer, delegation/supervision, second review for high-risk work, and a durable approval event. "Licensed attorney" also implies a license/jurisdiction verification source or firm-admin attestation.

### Step 6: Confidentiality and Provenance

The concepts are right and the deep dive is useful. Treating matter documents as untrusted input is important.

Improvement: move some of this earlier and fix the diagram view. The step references `pipe-guard`, `pipe-prov`, and `pipe-log`, but `Pipeline` is not visible, so those links will not render. Add `Pipeline` or author local links that match the visible nodes.

### Step 7: Workflows at Scale and Evaluation

The step correctly names the production workflows and quality metrics. Evaluating against attorney ground truth and citation-error rate is the right direction.

Improvement: it is too compressed for a final step. Contract review, diligence extraction, and memos deserve distinct output models or at least a structured deep dive. Also add `DraftStore` to the view if the `draftstore-attorney` link is meant to appear.

## Final Design Review

The final design integrates the major components and has a clear narrative. It successfully explains why the platform is deterministic and why the irreversible action is attorney-finalized work product.

Missing details:

- A visible correction loop from `CiteVerifier` back to `DraftAgent` or an exception queue.
- Source lifecycle for authoritative law: update cadence, version pinning, and legal-source freshness.
- Matter-document ingestion and indexing lifecycle.
- Review-state transitions and attorney override/return handling.
- Provider outage and rate-limit behavior for legal databases and inference.
- Retention/redaction policy for prompts, traces, retrieved snippets, drafts, and audit logs.

## Concept Introduction and Learning Flow

The order is mostly effective. The case starts with a dangerous baseline, adds authoritative grounding, then builds a deterministic pipeline and gates it with citation verification and attorney review.

The main sequencing issue is confidentiality. It is introduced as Step 6, but it constrains every earlier step. A short access-boundary concept should appear in Step 2 before retrieval from DMS or matter corpora is allowed.

The final workflow/eval step could teach more if it were split into smaller sub-steps or deep dives. Right now it acts as a summary of three product lines rather than a design decision.

## Step-to-Final-Design Coherence

Most step components appear in `finalDesign`, which is good. The progression is coherent:

- Step 1 introduces `DraftAgent` and `Inference`.
- Step 2 adds `AuthIndex`, `DMS`, and `Guardrail`.
- Step 3 adds `Pipeline`, `TaskQueue`, and `DraftStore`.
- Step 4 adds `CiteVerifier`.
- Step 5 adds `Attorney`, `Identity`, and `AuditLog`.
- Step 6 adds `Provenance`.
- Step 7 adds `Observability`.

Gaps:

- Step 6 and Step 7 diagrams omit some intended links because endpoints are missing from `view.nodes`.
- `Matter` and `Gateway` appear only in final design, not in the step sequence. That is acceptable, but a small API-ingress step or intro note would make the final diagram feel less abrupt.
- The final design says flagged citations return for correction, but no link models that loop.

## Realism Compared With Production Systems

The review, approval, provenance, and hallucination themes are realistic. The remaining realism gaps are mostly operational:

- Legal-source providers have rate limits, latency, freshness windows, commercial constraints, and outage modes.
- Long matter documents require chunking, OCR/format handling, versioning, deduplication, and source-span stability.
- Diligence batches need resumability, partial completion, per-document errors, and human adjudication for low-confidence findings.
- Citation relevance has false positives and false negatives; it should produce reviewable evidence rather than a bare boolean.
- Attorney review is a workflow with assignment, annotations, returns, approvals, and durable signatures.
- Audit logs need immutability, retention, access controls, and trace redaction.
- Confidentiality needs provider routing and policy enforcement, not just a ZDR/no-train statement.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- All `view.nodes` references resolve to `highLevelArchitecture.nodes`.
- All `view.links` references resolve to `highLevelArchitecture.links`.
- All `satisfies[*].steps[*]` references resolve to real step IDs.
- All `patterns[*].steps[*]` references resolve to real step IDs.
- Sequence participant and message IDs resolve to canonical architecture node IDs.
- Renderer issue: some step links will be filtered out because the step does not include both link endpoints in `view.nodes` (`confidentiality` and `workflows-eval`).
- Node-type issue: `Matter` has type `client` but is labeled "Matter Documents". Per repo convention, `client` should represent software outside the backend boundary. Consider renaming it to a client app/portal or changing the node type to a data/source-like type such as `external` or `object-storage`.
- Optional enrichment fields such as `technologyChoices`, `toProbeFurther`, AI visuals, and comics are absent. That is fine for validity, but `toProbeFurther` would help this domain because legal-source verification, privilege, and attorney supervision are nuanced.

## Recommended Edits, Prioritized

### P1: Fix diagram rendering omissions

Add missing endpoints to the affected step views:

- Step `confidentiality`: add `Pipeline` to `view.nodes`, or remove/replace `pipe-guard`, `pipe-prov`, and `pipe-log`.
- Step `workflows-eval`: add `DraftStore` to `view.nodes`, or remove/replace `draftstore-attorney`.

### P1: Specify citation-verification evidence and state

Expand the citation model and Step 4 to include proposition span, source span, authority status, jurisdiction, relevance score, verifier version, decision state, blocking reason, and correction loop.

### P1: Add a real capacity model

Convert qualitative capacity into numbers: matters/day, docs/matter, pages/doc, citations/draft, extraction cells/batch, verification calls/citation, peak concurrency, latency targets, and provider limits.

### P2: Make APIs workflow-aware and idempotent

Add request fields for task-specific inputs and lifecycle control: `idempotencyKey`, `jurisdiction`, `playbookId`, `outputSchemaId`, `sourceCorpus`, `reviewAssignee`, and asynchronous job/status endpoints.

### P2: Expand the data model

Add matters, documents/document versions, ingestion jobs, source corpora, playbooks, review events, redlines, diligence findings/cells, verification attempts, and audit events.

### P2: Move access-control constraints earlier

Introduce tenant/matter ACLs, ethical walls, provider retention policy, and prompt/document untrusted-input handling in Step 2 or Step 3.

### P3: Add operational deep dives

Add deep dives for legal-source provider outages/rate limits, batch retry/DLQ, source-version pinning, prompt trace retention, and eval sampling against attorney ground truth.

### P3: Add probe links or further reading

This domain would benefit from curated links on legal citation verification, professional responsibility around AI assistance, privilege/confidentiality, and RAG evaluation for legal research.

## What Not To Change

- Keep the citation-verification gate as the central design move.
- Keep the deterministic pipeline recommendation over an autonomous research loop.
- Keep attorney approval as mandatory and identity-bound.
- Keep provenance tied to source spans and versions.
- Keep the naive baseline because it teaches the domain risk quickly.

## Bottom Line

This is a strong legal-agent case study with a clear pedagogical spine. The next improvement pass should make the core gate and production workflow concrete: richer citation-verification evidence, workflow-specific APIs/data, real capacity numbers, operational failure handling, and a small diagram fix so the rendered visuals match the authored intent.
