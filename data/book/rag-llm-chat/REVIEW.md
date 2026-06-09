# Review: RAG / LLM Chat - System Design

Reviewed file: `data/book/rag-llm-chat/interview.json`
Review date: 2026-06-08

## Executive Summary

This is now a flagship-quality RAG/LLM chat walkthrough. The recent changes
addressed the previous high-impact gaps: tenant/corpus isolation is carried
through API, data model, retrieval, cache, traces, citations, and final design;
document indexing/deletion lifecycle is explicit; streaming has durable
`chat_runs`, run/message IDs, cancellation, and idempotency; cache/limiter state
is modeled; and capacity now converts chat traffic into tokens, streams,
retrieval/reranker QPS, embedding work, and trace writes.

The case teaches the right AI-era architecture in the right order: stateless LLM
calls, bounded conversation context, token streaming, async ingestion, chunking,
embeddings, vector retrieval, reranking, grounded prompt assembly, citation
validation, semantic caching, per-tenant budgets, model routing, guardrails, and
evaluation traces. The remaining issues are no longer structural omissions.
They are mostly about making the hard operational edges more precise: bursty
ingestion backpressure, stream resume semantics, eval/regression workflows,
privacy/retention policy, and capacity assumptions under cache hits versus
misses.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.7 / 5 | Strong end-to-end architecture with the core RAG, isolation, lifecycle, and run-state surfaces now represented. |
| Production realism | 4.5 / 5 | Much improved; remaining gaps are queue/backpressure detail, eval operations, privacy/retention, and provider-limit posture. |
| Pedagogical flow | 4.7 / 5 | Clear problem-by-problem buildup; concepts arrive just in time and the chunking sub-step adds useful depth. |
| Final design coherence | 4.7 / 5 | Final design now explicitly names the control-plane state that the diagram intentionally does not draw. |
| Dataset/rendering fit | 4.8 / 5 | JSON parses; node/link/parent/pattern/satisfies references checked cleanly. Minor flow and follow-up polish only. |

Recommendation: keep the step order and main architecture. The next edit pass
should add a little more operational specificity around ingestion queues,
stream resumption, eval datasets, retention/redaction, and capacity
degradation.

## What Works Well

- The dataset starts from the right baseline: the model is stateless, slow,
  expensive, and non-deterministic. That framing makes every later addition
  feel motivated.
- Conversation context is introduced before retrieval, so the learner sees that
  history, summary, retrieved chunks, system instructions, and answer budget all
  compete for the same context window.
- Streaming is treated as both UX and operations. The API now returns stable
  run/message identifiers, the data model has `chat_runs`, and cancellation is
  represented instead of hand-waved.
- Ingestion is properly asynchronous, with chunking, embeddings, vector upserts,
  document status, versioning, tombstones, and failure drills.
- Tenant/corpus isolation is no longer a follow-up-only concern. It is threaded
  through conversations, documents, chunks, retrieval filters, cache keys,
  traces, citations, patterns, traps, and final design prose.
- Retrieval quality is taught well: ANN candidate generation, reranking,
  hybrid retrieval for exact identifiers, relevance thresholds, deletion/stale
  filters, and citation validation all appear.
- Cost is concrete. The dataset now names token volume, active streams,
  retrieval/reranker QPS, trace writes, semantic cache keys, corpus-version
  invalidation, and per-tenant budget buckets.
- Safety is RAG-specific. Retrieved document text is treated as untrusted data,
  prompt injection is called out directly, and safety decisions are recorded in
  traces.
- The wrap-up material is strong: `satisfies`, `interviewScript`,
  `levelVariants`, `followUps`, and `toProbeFurther` align with the teaching
  path.

## Highest-Impact Issues

### 1. Ingestion needs a clearer queue and backpressure story

The ingestion step says uploads are asynchronous and rate-limited off the query
path, but the architecture view goes directly from `Ingest` to `Chunker`. That
is acceptable for a compact diagram, but the walkthrough now has enough
production detail elsewhere that the missing job queue/backpressure mechanism
stands out.

Why it matters: document ingestion is bursty and can generate thousands of
chunk-embedding jobs per upload. Without an explicit queue or admission-control
story, it is unclear how the system protects query-time embedding, handles
provider embedding rate limits, retries failed chunks, and exposes indexing
progress without overloading workers.

Concrete fixes:

- Add a short deep-dive bullet or caption that `Ingest` enqueues per-document
  or per-chunk jobs, with retry/backoff and dead-letter handling.
- Consider adding a `queue` node to the ingestion view if diagram complexity is
  acceptable.
- Clarify that query embeddings and ingest embeddings have separate rate limits
  or priority classes.
- Extend the document lifecycle note with progress counters such as
  `chunks_total`, `chunks_indexed`, and `chunks_failed`.
- Add a failure drill for embedding-provider rate limiting during a large
  upload.

This is the main remaining P1 because it affects reliability and capacity under
real upload bursts.

### 2. Stream cancellation is explicit, but resume semantics are still vague

The API includes `POST /v1/runs/{run_id}/cancel`, the stream opens with
`run_id`/`message_id`, and `chat_runs` records `streaming`, `completed`,
`failed`, and `cancelled`. Step 3's failure drill also says partial output is
recoverable or clearly incomplete. What is not yet precise is whether resume is
supported, and if so what the client fetches after reconnect.

Why it matters: streaming contracts become ambiguous during disconnects. Some
systems cancel immediately to avoid token spend; others keep generating and let
the client reconnect; others persist partial assistant messages but do not
resume the upstream model. The dataset currently gestures at both cancellation
and partial recovery.

Concrete fixes:

- Choose one default behavior: disconnect cancels upstream generation, or
  disconnect does not cancel for a short grace period.
- If resume is supported, add a resume endpoint or state that
  `GET /v1/conversations/{id}` returns partial assistant messages with status.
- If resume is not supported, say the partial assistant turn remains
  `cancelled` or `failed` and the client starts a new idempotent run.
- Add `started_at`, `completed_at`, and maybe `last_event_seq` to `chat_runs`
  if replay/resume is part of the intended design.

This can be fixed with prose and a small API/data-model tweak.

### 3. Evaluation is present, but regression workflow is thin

The dataset correctly records traces and distinguishes user feedback from eval
in the Step 8 deep dive. However, the data model only has `traces`; it does not
show evaluation datasets, eval runs, metric snapshots, or release gates for
changes to prompts, chunking, embedding models, rerankers, or LLM routing.

Why it matters: production RAG quality regresses silently. Teams need to know
whether a chunk-size change improved retrieval recall but hurt citation
faithfulness, whether a model-router change saved cost but reduced answer
quality, and whether prompt changes broke common tasks.

Concrete fixes:

- Add optional eval entities such as `eval_sets`, `eval_cases`, `eval_runs`,
  and `eval_results`, or explain them in the Step 8 deep dive.
- Name a small metric set: retrieval recall@k, answer faithfulness, citation
  precision, refusal accuracy, latency, and cost per successful answer.
- Add an interview-script line that prompt/model/index changes are gated by
  replaying sampled traces or curated eval cases.
- Keep user feedback as a signal, not the primary eval dataset.

This is a P2 because the architecture is already valid, but the staff-level
operations story would be stronger with this addition.

### 4. Privacy, retention, and redaction need one visible pass

The design stores prompts, retrieved chunks, citations, safety decisions, cost,
and traces. That is exactly what an operator needs for debugging and eval, but
the dataset does not yet say how long that data is retained, whether prompts or
chunks may contain PII, or how tenant-specific audit and deletion requests
affect traces.

Why it matters: RAG over private documents often involves sensitive business or
personal data. Trace retention can become a compliance issue even when core
retrieval isolation is correct.

Concrete fixes:

- Add a non-functional requirement or Step 8 note for data retention/redaction.
- Add `redaction_status`, `retention_expires_at`, or similar policy metadata to
  traces if the data model should carry it.
- Explain whether deleted documents require trace redaction or whether traces
  keep references only.
- Add a trap: "Logging full prompts and retrieved chunks forever."

This should stay lightweight, but it belongs in a production RAG case.

### 5. Capacity math is much better, but should name miss-path assumptions

The capacity section now translates 5k messages/s into roughly 2M generated
tokens/s, 40k open streams, retrieval/reranker QPS, ingestion throughput, and
trace writes. That is a major improvement. The remaining ambiguity is whether
these are all-message estimates, cache-miss estimates, or worst-case estimates.

Why it matters: cache hit rate, retrieval skip paths, admission control, and
provider rate limits materially change the feasible design. At 5k LLM-backed
messages/s, the system likely needs aggressive quotas, provider sharding,
fallbacks, or deflection.

Concrete fixes:

- State a cache hit-rate assumption and derive miss-path LLM/retrieval QPS.
- Separate query embeddings from ingestion embeddings in the numeric estimates.
- Add a note that provider token limits are enforced before starting a run, not
  discovered after streaming begins.
- Mention load shedding or degraded responses when the model provider is rate
  limited.

This is refinement, not a flaw in the current architecture.

## System Design Soundness

### Requirements and Capacity

The functional requirements are well scoped: multi-turn chat, grounded answers
with citations, token streaming, document ingestion/reindexing, and persisted
history. The non-functional requirements name the AI-specific constraints that
drive the design: time-to-first-token, context-window pressure, hallucination,
cost, safety, prompt injection, and graceful degradation.

Capacity is now concrete enough to guide architecture. The dataset estimates
input/output tokens per request, generated tokens per second, active SSE
connections, retrieval and reranker calls, embedding throughput, corpus size,
retrieval latency, and trace writes. The strongest next improvement is to
separate cache-hit, cache-miss, and degraded-mode math.

### API

The API shape is now credible for production:

- `POST /v1/conversations/{id}/messages` streams a grounded answer, includes an
  idempotency key, and opens with `run_id`/`message_id`.
- `POST /v1/documents` handles async ingest into a `corpus_id` with
  idempotent re-upload.
- `GET /v1/conversations/{id}` returns history, assistant status, and verified
  citations.
- `GET /v1/documents/{id}` exposes indexing lifecycle.
- `DELETE /v1/documents/{id}` tombstones source documents and removes stale
  chunks from derived stores.
- `POST /v1/runs/{run_id}/cancel` gives streaming a real control path.
- `POST /v1/feedback` connects user feedback to trace-based evaluation.

The main API polish is stream reconnection/resume semantics and perhaps a more
explicit document progress response for large uploads.

### Data Model

The data model now carries the promises made by the architecture:
`conversations` include tenant/corpus scope, `messages` include assistant
status and citations, `chat_runs` records durable generation state,
`documents` and `chunks` include indexing/deletion/versioning fields, `traces`
capture model/tokens/cost/safety decisions, `cache_entries` are keyed by
tenant/corpus/version, and `tenant_budgets` supports cost control.

Remaining data-model additions are optional and targeted: ingestion progress
counters, eval-run entities, retention/redaction fields, and stream replay
sequence fields if resume is in scope.

### Architecture

The architecture has the right components and the final design integrates them:
API, streaming gateway, orchestrator, conversation store, summarizer, cache,
limiter, retriever, embedding model, vector index, reranker, document/chunk
store, ingestion pipeline, chunker, safety filter, model router, small/large
models, and eval/trace store.

The final design description is especially useful because it names the
control-plane state the diagram does not draw. That prevents the diagram from
becoming cluttered while still teaching tenant isolation, document lifecycle,
and durable run state.

## Step-by-Step Pedagogical Review

### Step 1: Thin LLM Proxy

This is the right opening. It exposes stateless inference, latency, cost, and
non-determinism before introducing memory or retrieval. The trap about assuming
the model remembers the conversation is valuable.

Suggested improvement: add one sentence that even the baseline should emit a
request/trace ID because model calls are expensive and ambiguous on timeout.

### Step 2: Conversation Store & Context Window

This step is strong. It correctly compares recent-turns-plus-summary against
last-N truncation and explains why retrieved context competes with history in
the same fixed window.

Suggested improvement: tie summary quality to eval or user-visible failure
cases. The step already has a good failure drill for references from 150 turns
ago; it could mention summary drift as a measurable quality issue.

### Step 3: Streaming Responses

The SSE/WebSocket/buffered comparison is practical and the recent run-state
additions make the step much more production-realistic. The cancellation path
is now visible in API and data model.

Suggested improvement: decide and document whether disconnect means immediate
cancel, grace-period resume, or persisted partial answer only.

### Step 4: Document Ingestion: Chunking & Embeddings

This is a good introduction to async RAG ingestion. The document lifecycle deep
dive and failure drill for half-indexed documents address the previously
missing operational state.

Suggested improvement: add an explicit queue/backpressure mechanism between
ingestion and chunk/embed workers, plus progress counters for large documents.

### Step 4a: Chunking Strategy

This sub-step is one of the dataset's strongest teaching moments. It explains
semantic boundaries, overlap, fixed-size chunk trade-offs, parent-child
retrieval, and the need to tune chunking against retrieval evals.

Suggested improvement: name one or two concrete metrics in the step itself:
recall@k, citation precision, answer faithfulness, and context-token waste.

### Step 5: Retrieval & Reranking

This step is now production-aware. It scopes retrieval to the caller's
tenant/corpus namespace before ranking, drops deleted/stale chunks, includes
reranking, and offers hybrid retrieval for exact terms.

Suggested improvement: call out where metadata filters are applied in the
vector system: per-tenant namespace, index filter, or post-ANN eligibility
filter. The safest teaching point is to filter inside the index query or
namespace, not after sending candidates onward.

### Step 6: RAG Assembly, Grounding & Citations

The grounding and citation-validation advice is sound. The prompt-construction
deep dive correctly treats retrieved content as data rather than instructions.

Suggested improvement: add a short note about answer abstention thresholds:
when retrieved context is weak, the answer should say it cannot find support in
the corpus rather than overusing generic LLM knowledge.

### Step 7: Caching & Cost / Rate Control

This step is much stronger now that `cache_entries` and `tenant_budgets` are in
the data model. Corpus-version cache invalidation and tenant-scoped cache keys
avoid the two most dangerous semantic-cache mistakes.

Suggested improvement: mention cache hit-rate assumptions in capacity, and make
clear that limiter checks happen before expensive retrieval/LLM work whenever
possible.

### Step 8: Scaling, Safety & Evaluation

The step covers the right advanced concerns: model routing, guardrails, prompt
injection, traces, and evaluation. The deep dive that separates routing,
safety, and eval is useful because those concerns share traces but have
different failure modes.

Suggested improvement: add a more concrete regression-testing workflow. A
staff-level candidate should be able to explain how a prompt, chunking,
embedding model, reranker, or routing change is evaluated before rollout.

## Final Design Review

The final design is coherent and matches the step sequence. It includes the
components introduced during the walkthrough and now explicitly describes the
stateful guarantees that are easy to miss in a compact architecture diagram:
tenant/corpus-scoped retrieval, document indexing lifecycle, tombstoned stale
vectors, durable `chat_run` state, idempotent retries, cancellation, semantic
cache invalidation, budgets, and traces.

The final design should not add many more boxes. The remaining improvements are
better handled as captions, deep-dive bullets, and data fields:

- ingestion queue/backpressure;
- stream reconnect or resume policy;
- eval datasets/runs/results;
- trace retention/redaction;
- cache-hit and degraded-mode capacity assumptions.

## Concept Introduction and Learning Flow

The learning flow is one of the dataset's best attributes:

1. The LLM is stateless, expensive, and non-deterministic.
2. Conversation history must be assembled into a bounded prompt.
3. Slow generation needs streaming and durable run state.
4. Private knowledge requires async ingestion, chunking, embeddings, and
   indexing.
5. Retrieval quality requires tenant-scoped filtering, ANN, reranking, and
   sometimes hybrid search.
6. Grounding and citation validation turn retrieved chunks into a trustworthy
   answer.
7. Cost controls are required because every call spends real money.
8. Safety, routing, and evaluation make the system operable.

Concepts are introduced just in time. The earlier problem that tenant/corpus
authorization arrived too late has been fixed; it now appears in requirements,
API, data model, patterns, retrieval, caching, and final design.

## Step-to-Final-Design Coherence

Each step contributes directly to the final design:

- Step 1 introduces the API/orchestrator/LLM baseline.
- Step 2 adds conversation storage and summary construction.
- Step 3 adds the streaming gateway and durable generation state.
- Step 4 adds ingestion, chunking, embeddings, vector index, document store,
  and lifecycle state.
- Step 4a deepens the chunking choice without disrupting the main path.
- Step 5 adds scoped retrieval and reranking.
- Step 6 adds grounded prompt assembly and citation validation.
- Step 7 adds semantic cache and per-tenant budget enforcement.
- Step 8 adds safety, model routing, and traces/evaluation.

The final design now reflects both the visible components and the hidden state
needed to make them reliable.

## Realism Compared With Production Systems

The dataset now covers the production concerns that most RAG interviews miss:
private-corpus isolation, stale-vector cleanup, run-state reconciliation,
idempotency, semantic-cache scoping, corpus-version invalidation, cost budgets,
prompt injection, and trace-based evaluation.

The remaining realism gaps are narrower:

- embedding-worker queues, retries, dead letters, and provider rate limits;
- clear stream reconnect/resume/cancel behavior;
- eval set management and regression gates;
- prompt/chunk/trace retention and redaction policy;
- cache hit-rate assumptions and degraded-mode capacity;
- explicit handling of PII and tenant audit requirements.

These should be lightweight additions, not a new architecture.

## Dataset and Renderer-Facing Observations

- JSON parsing succeeded.
- `steps[].view.nodes` resolve to `highLevelArchitecture.nodes`.
- `steps[].view.links` resolve to `highLevelArchitecture.links`.
- `steps[].options[].view.nodes` and string link IDs resolve.
- `finalDesign.view.nodes` and string link IDs resolve.
- `satisfies.functional[].steps[]` and `satisfies.nonFunctional[].steps[]`
  resolve to real step IDs.
- The `chunking-strategy` parent reference resolves to `ingestion`.
- Dataset-level `patterns[].name` covers all `step.patterns[]` chips,
  including the recently added `Rate limiting / throttling` and
  `Tenant / corpus isolation`.
- Step highlight IDs resolve to canonical architecture nodes.
- Structured sequences in `steps[].flows[]` and `api[].sequence` use internally
  consistent participant/message IDs. API sequences intentionally use compact
  participant IDs for diagram readability while the architecture views use
  canonical node IDs.
- No generated `docs/` files need to be rebuilt for this review because
  `REVIEW.md` is repo-only.

## Recommended Edits, Prioritized

### P1: Add ingestion queue/backpressure detail

Represent the async queue, retry/backoff, dead-letter behavior, worker
priority, and embedding-provider rate-limit handling either in Step 4 prose or
as a small queue node.

### P1: Clarify stream disconnect and resume behavior

Choose the default behavior for disconnects, cancellation, partial assistant
messages, and stream replay. Reflect it in the API/data model only if resume is
intended.

### P2: Make evaluation workflow concrete

Add eval-set/eval-run language, metric names, and regression gates for prompt,
chunking, embedding, reranker, model, and router changes.

### P2: Add privacy and retention policy for traces

Add a requirement, trap, or trace fields for redaction, retention expiration,
and tenant-scoped audit/deletion handling.

### P2: Separate capacity estimates by path

State cache-hit assumptions, cache-miss LLM/retrieval QPS, provider token-limit
behavior, and degraded-mode/load-shedding choices.

### P3: Update follow-ups after the tenant/corpus upgrade

The follow-up "How would you support multi-tenant corpora with strict
isolation..." is now largely answered by the core case. Reframe it toward
harder extensions such as per-document ACLs, shared corpora with group
permissions, row-level permissions inside documents, or tenant-specific model
and retention policies.

## What Not To Change

- Do not reorder the main steps. The progression is logical and
  interview-friendly.
- Do not remove the chunking sub-step. It gives the RAG case concrete depth.
- Do not collapse retrieval and RAG assembly. Keeping retrieval quality
  separate from answer construction is pedagogically correct.
- Do not weaken citation validation, corpus-version cache invalidation, or
  prompt-injection warnings. These are among the strongest parts of the case.
- Do not overload the final diagram with every operational table. The current
  diagram plus explicit final-design prose is the right balance.

## Bottom Line

The recent changes moved this from a strong RAG primer to a production-credible
system design interview. It now models the control-plane details that make RAG
safe and operable: tenant-scoped retrieval, document lifecycle, streaming run
state, idempotency, cancellation, cache invalidation, budgets, and traces. The
remaining work is focused polish around ingestion backpressure, stream resume
semantics, eval operations, privacy/retention, and capacity assumptions.
