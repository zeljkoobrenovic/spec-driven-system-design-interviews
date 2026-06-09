# Review: Recommendation System - System Design

Reviewed file: `data/book/recommendation/interview.json`
Review date: 2026-06-09

## Executive Summary

This review has been updated after the recent recommendation-dataset changes. The previous major gaps were largely addressed: the case now has concrete capacity numbers, a per-item exposure log, richer API/event fields, privacy and governance requirements, more traps, and detailed serving failure drills. The interview is now a strong, production-realistic walkthrough of the recall -> rank -> filter -> feedback funnel.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.6/5 | The architecture and capacity model are credible; one feature-read arithmetic mismatch should be fixed. |
| Production realism | 4.4/5 | Exposure logging, governance, version compatibility, and fallbacks are much stronger; event-ingest and metric/runbook detail can still improve. |
| Pedagogical flow | 4.6/5 | Steps build naturally and traps are useful; staff-level deep dives are still missing. |
| Dataset/rendering fit | 5/5 | JSON parses and structural references resolve across views, options, flows, patterns, probe links, and satisfies mappings. |
| Overall | 4.6/5 | Ready as a high-quality book case, with remaining work mostly in precision and advanced teaching artifacts. |

## What Works Well

- The walkthrough teaches the right spine: simple recall first, ANN as one recall source, bounded ranking, post-ranking filters, feedback, then resilient serving.
- Capacity is now concrete: DAU, peak RPS, recall fan-out, feature-read pressure, latency budget, ANN memory, event volume, and refresh cadence are all named.
- The data model now includes `recommendation_exposure` with rank, score, candidate sources, model/feature/experiment/policy metadata, and propensity.
- Privacy and governance are no longer bolted on. Requirements, user profile fields, item policy fields, filtering, feedback, and `satisfies` all refer to consent, retention, deletion, sensitive categories, and regional policy.
- The traps added to ANN, ranking, features, filters, feedback, and serving are concrete and useful in interviews.
- Step 7 now includes realistic failure drills for ranker outage, feature-store timeout, stale ANN, event-stream lag, and bad model rollout.
- Renderer-facing structure is clean: structured architecture views and structured sequences are used consistently.

## Highest-Impact Issues

### 1. Feature-read capacity math is inconsistent

The capacity section says `~500 candidates x ~50 features` produces `~10k feature values/request`, but that multiplication is 25k feature values/request. The peak value estimate then says `~200M values/sec at peak`, which matches 10k x 20k RPS rather than 25k x 20k RPS.

Concrete fix: either change the premise to something like `~200 candidates x ~50 features -> ~10k feature values/request`, or keep `~500 candidates` and update the derived estimate to `~25k/request` and `~500M values/sec at 20k RPS`. This matters because the feature-store load is one of the key design constraints.

### 2. Event ingest and exposure semantics need one more level of precision

The dataset now models exposure logging well, but the diagrams and API sequences still blur three different facts: the API served a ranked list, the client actually rendered visible impressions, and the client later emitted interactions. The `POST /v1/events` sequence also sends the client directly to `EventLog`, which can read as a public durable stream rather than an authenticated ingest endpoint.

Concrete fix: clarify whether `recommendation_exposure` means server-side "served exposure" or client-confirmed "rendered impression." If both are needed, model them separately or add `rendered_at` / `viewport_visible` style fields. Consider adding an `Event Ingest API` node or making clear that `EventLog` includes validation, auth, schema enforcement, deduplication, and retry handling.

### 3. Staff-level deep dives are still absent

The case now has good traps, but every step still has `deepDives: 0`. For a recommendation-system chapter, the best advanced material is too dense to leave only in descriptions and traps.

Concrete fix: add two or three deep dives:

- Exposure logging for unbiased training and off-policy evaluation.
- Latency budget and overload shedding across cache, recall, feature fetch, scoring, filters, and async logging.
- Version-compatible rollout across model, feature-set, embedding, ANN index, and experiment arm.

### 4. Technology choices now cover the main platform decisions

The dataset now has 11 technology-choice concerns spanning ANN retrieval, profile/catalog stores, feature store, event streaming, lakehouse storage, model serving/registry, refresh orchestration, experimentation, cache fallback, policy rules, and monitoring.

Concrete follow-up: keep the section curated rather than expanding into a vendor catalog. Add or remove choices only when the walkthrough introduces a real platform decision, then rerun icon assignment and rebuild generated docs.

### 5. Observability is named but not yet operationalized

The architecture has an `Observability` node and the serving drills mention degraded-mode metrics, but the dataset does not define a compact metric catalog or alert/runbook expectations. For recommenders, model quality failures are often silent even when HTTP health is fine.

Concrete fix: add explicit metrics such as p99 by stage, recall-source timeout rate, candidate count distribution, ANN recall@K benchmark, index age, feature freshness/TTL miss rate, exposure-log lag, event dedup rate, model score distribution, drift, guardrail metrics per experiment, fallback rate, catalog coverage, tail exposure, and deletion backlog.

## System Design Soundness

The design is now sound and realistic. It includes the major production components expected in a large recommender: recommendation API, experiment/model router, candidate-generation service, ANN index, popularity/profile/catalog recall sources, ranker, feature store, eligibility/diversity re-ranker, result cache, event stream, real-time feature updater, data lake, offline feature pipeline, trainer, model registry, and observability.

The capacity section is much improved. It correctly frames peak recommendation RPS, recall fan-out, bounded candidate sets, feature-store pressure, p99 latency budget, ANN memory shape, event volume, and refresh cadence. Fixing the feature-read arithmetic would make this section strong enough to use directly in an interview.

The API is now more credible: `GET /v1/recommendations` includes surface, locale, device, session, limit, and debug controls, while `POST /v1/events` has event idempotency, client timestamp, dwell time, position, and request correlation. The remaining concern is architectural clarity: client event submission should probably pass through an ingest service, even if the diagram keeps that service lightweight.

The data model is strong. Replacing lossy `served_item_ids` with `recommendation_exposure` is the right move, and the lineage/version fields make the counterfactual-evaluation and rollout story much more defensible. User consent, deletion timestamps, region, item sensitivity, and policy status now support the governance claims.

## Step-by-Step Pedagogical Review

### Step 1: Start with Simple Candidate Generation

This remains the right opening. It avoids the common "just use vector search" mistake and gives cold-start and fallback behavior early. The added trap about anonymous/cold traffic is practical.

### Step 2: Refine Recall with Embeddings and ANN

The options for HNSW, IVF-PQ, and LSH are well chosen. The new traps on recall@K, latency-only thinking, stale embeddings, and index refresh make the step substantially stronger. A deep dive on ANN evaluation and index-refresh rollout would be valuable.

### Step 3: Ranking the Candidates

The ranking step now does a better job connecting model choice to exposure bias. The traps correctly warn against trusting offline AUC/NDCG and training only from biased clicks. It could still use a short treatment of objective design: engagement, conversion, long-term retention, creator/business constraints, and guardrails can conflict.

### Step 4: Features and the Feature Store

This is one of the strongest steps. It explains online/offline parity, real-time features, batch features, point-in-time correctness, and backfill. The feature-store load in the capacity section should be made arithmetically consistent with the candidate count used here.

### Step 5: Post-Ranking Filters and Diversity

The step now cleanly includes policy, privacy, regional eligibility, sensitive-category suppression, user blocks/opt-outs, freshness, diversity, and exploration. This is the right place for these concerns because the model cannot be trusted as the final policy gate.

### Step 6: The Feedback Loop: Events, Training, Models

This step is now materially stronger than the earlier version. It names impressions, exposure rows, rank, score, source, versions, propensities, consent-gated training, retention, and right-to-delete propagation. Clarifying served exposure versus rendered impression would make it production-grade.

### Step 7: Serving: Latency, Cold Start, and Resilience

The serving step now has useful mechanics: per-stage deadlines, partial recall, feature fallback, ranker fallback, dependency isolation, backpressure, cache-key correctness, async logging, version compatibility, and five failure drills. The remaining pedagogical gap is that it has no options, no pattern tag, and no deep dive. A comparison among full online serving, precomputed lists, and hybrid online-plus-cache fallback would fit this step well.

## Final Design Review

The final design coherently integrates the steps. The online path and offline feedback path are both visible, and the description now mentions compatible model, feature-set, embedding, and ANN versions. The final flows are a good wrap-up: one for online serving and one for feedback-driven model refresh.

The final design would be even clearer with an explicit event-ingest boundary. Right now `Client -> EventLog` can be interpreted as direct stream access. In production, event submission usually needs auth, schema validation, idempotency, abuse controls, and backpressure before writing to the durable log.

## Concept Introduction and Learning Flow

The concept order is excellent. The learner sees one new problem at a time:

1. Recall must bound the catalog.
2. ANN improves recall without replacing the funnel.
3. Ranking spends more compute on a smaller set.
4. Feature stores prevent train/serve skew.
5. Filters make the ranked list eligible, diverse, and policy-safe.
6. Feedback turns serving into training data.
7. Serving resilience keeps the system usable under dependency failures.

The new traps make the case more interview-ready. The next learning improvement is to move the most advanced material into dedicated deep dives so readers can distinguish the main answer from senior/staff extensions.

## Step-to-Final-Design Coherence

Each step contributes visible nodes and links to the final architecture. The final design includes the same components introduced in the walkthrough, and `satisfies` now maps cold start, privacy/governance, resilient serving, train/serve parity, and fresh models/features back to the right steps.

Cold start is now handled as a cross-cutting thread rather than only at the end: simple recall, filters, feedback/exploration, and serving all mention it. That is a good improvement.

## Realism Compared With Production Systems

The design now resembles a real recommender stack, not just an interview sketch. The major realism upgrades are exposure logging, feature/model/embedding version compatibility, async logging, failure drills, privacy/governance, and explicit latency constraints.

Remaining production caveats:

- Event ingestion should be explicit enough to cover auth, schema validation, idempotency, retries, deduplication, late events, and abuse protection.
- The observability story should list concrete quality, freshness, drift, guardrail, exposure, and fallback metrics.
- Data governance should eventually include operational jobs for retention expiration, deletion tombstones, training-data purge, and audit evidence.
- Technology choices are now present; keep their icon mappings in sync as new terms are added.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Step view nodes and option view nodes reference canonical `highLevelArchitecture.nodes`.
- Step, option, and final-design view links resolve to `highLevelArchitecture.links`.
- Sequence participants use canonical node IDs, and message endpoints resolve to participant IDs or aliases.
- `patterns[*].steps`, `steps[*].patterns`, `steps[*].probeLinks`, and `satisfies[*].steps` references resolve.
- The dataset uses structured `view` and structured `sequence` objects rather than raw Mermaid for architecture and flow diagrams.
- There are no `deepDives`; those are optional, but would still improve this book-group dataset.
- Generated `docs/` should be rebuilt after dataset changes that alter the rendered book site.

## Recommended Edits, Prioritized

### P1: Fix the feature-read capacity math

Make the candidate count, feature count, values/request, and values/sec estimates agree.

### P1: Clarify event ingest and impression semantics

Distinguish served exposure from client-rendered impression, and route client event writes through an explicit ingest boundary or document that `EventLog` includes ingest validation.

### P2: Add staff-level deep dives

Add deep dives for unbiased exposure logging, latency/overload budgets, and version-compatible model/feature/embedding rollout.

### P2: Add serving options and a serving pattern

Compare full online serving, precomputed recommendations, and hybrid online-plus-cache fallback. Add a pattern tag such as "Graceful degradation / fallback serving" to Step 7.

### P2: Keep `technologyChoices` curated

The current section covers 11 implementation concerns. If future architecture steps change, update these choices, assign icons, and rebuild docs.

### P3: Add an observability metric catalog

Name the concrete SLO, model-quality, data-quality, freshness, guardrail, fallback, and governance metrics an interviewer should expect.

## What Not To Change

- Keep simple recall before ANN.
- Keep ANN framed as one recall source, not the whole recommender.
- Keep the feature-store/train-serve-parity emphasis.
- Keep post-ranking filters separate from model ranking.
- Keep the per-item exposure log and propensity fields.
- Keep the final design's online/offline split.

## Bottom Line

The recent changes substantially upgraded the recommendation interview. The dataset is now strong enough to use as a book case; the remaining work is to tighten one capacity calculation, clarify event-ingest semantics, and add advanced deep dives plus an observability metric catalog.
