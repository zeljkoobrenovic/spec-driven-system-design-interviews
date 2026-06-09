# Review: Recommendation System - System Design

Reviewed file: `data/book/recommendation/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong recommendation-system walkthrough. It teaches the canonical recall -> rank -> filter -> feedback funnel in a clear order, uses structured diagrams correctly, and does a good job introducing train/serve parity, ANN recall, impression logging, cold start, experimentation, and fallback serving.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | The core architecture is credible, but capacity math and privacy/safety coverage need more specificity. |
| Production realism | 3.5/5 | Good ML-platform shape; weaker on exposure logging, bias correction metadata, operational runbooks, and data governance. |
| Pedagogical flow | 4.5/5 | The steps build naturally and the trade-off options are useful. More traps and drills would make it interview-ready at staff level. |
| Dataset/rendering fit | 5/5 | JSON parses cleanly and node, link, highlight, flow, pattern, probe-link, and satisfies references resolve. |
| Overall | 4.2/5 | Very usable as a book case with a few high-leverage production details to add. |

## What Works Well

- The walkthrough starts with simple candidate generation before ANN, which prevents the common "vector search solves everything" answer.
- The two-stage funnel is explicit: bounded recall, expensive ranking, post-ranking eligibility/diversity, then feedback.
- The feature-store step correctly centers train/serve parity rather than treating the store as only a low-latency cache.
- The feedback step calls out impressions, not just clicks, which is an important senior-level distinction.
- The final design integrates the serving path, model registry, ANN refresh, event stream, data lake, online features, offline pipeline, and monitoring into one coherent diagram.
- Renderer-facing structure is clean: shared architecture nodes and links are reused consistently, sequence participants match canonical node IDs, and wrap-up references resolve.

## Highest-Impact Issues

### 1. Capacity is qualitative instead of sizing the real work units

The capacity section lists catalog size, candidate fan-out, latency, feature freshness, and feedback volume, but it never turns product scale into concrete request, storage, event, feature-read, training, or ANN-index budgets. For a recommender, the key capacity question is not just "millions of items"; it is how many recommendation requests per second, how many candidate-source calls per request, how many feature lookups per ranked candidate, how many impression rows per response, and how often embeddings/indexes are rebuilt.

Concrete fix: add a sample sizing model such as DAU, requests/user/day, peak RPS, `K` candidates per source, total candidates after dedup, features per candidate, event writes per served list, training-data retention, embedding dimensionality, ANN memory estimate, and model/index refresh cadence. Tie those numbers back to the p99 100-200 ms target.

### 2. Counterfactual evaluation is mentioned, but exposure logging is under-modeled

The feedback step says impression logging enables counterfactual evaluation, and the probe links include off-policy evaluation references. The API/data model, however, only keeps `request_id`, `model_arm`, `served_item_ids`, interaction `position`, and event type. That is not enough for serious learning from logged recommendations because it loses per-item exposure metadata: rank, score, candidate source, filter reason, model version, policy id, exploration probability, and propensity.

Concrete fix: add a `recommendation_exposure` or `served_item` entity keyed by request and item, with `rank`, `score`, `candidate_sources`, `model_id/version`, `feature_set`, `experiment_id`, `policy_id`, `propensity`, and `shown_at`. Mention that propensities are required when contextual-bandit or counterfactual/off-policy evaluation is in scope.

### 3. Privacy, consent, retention, and sensitive-signal controls are mostly absent

The design stores user history, context, dwell time, hides, blocks, and profile summaries. That is realistic, but the requirements and steps do not address data minimization, consent, deletion, retention windows, sensitive categories, regional policy, or user controls. For recommendation systems, these are not edge concerns; they directly affect feature eligibility, logging, training data, and model behavior.

Concrete fix: add one non-functional requirement for privacy/governance and extend the filters or feedback step with data-retention, consent-aware feature generation, right-to-delete propagation, and sensitive-category suppression. The item catalog already has `policy_status`, so the design has a natural place to connect policy constraints to both serving and training.

### 4. Serving resilience is compressed into one step without enough operational mechanics

Step 7 correctly mentions cache, deadlines, cold start, and graceful fallback, but it stays high-level. Production serving needs more explicit mechanics: per-stage timeouts, partial recall if one source is slow, fallback ordering, stale feature handling, cache key invalidation by model arm/feature freshness, backpressure, dependency isolation, and model/index version compatibility.

Concrete fix: turn step 7 into an option-driven section. Useful options: "full online funnel with deadlines", "precomputed/homepage recommendations", and "hybrid online plus cached fallback". Add a failure drill for stale feature store values, ANN refresh lag, and model-registry rollback.

### 5. Staff-level teaching artifacts are thinner than the architecture

The dataset has strong step descriptions and options, but only one trap and no deep dives. For an interview book case, recommender systems are rich in traps: offline metric overfit, position bias, popularity feedback loops, stale embeddings, ANN recall tuning, train/serve skew, exploration hurting short-term metrics, and over-personalization/filter bubbles.

Concrete fix: add traps to at least the ANN, ranking, feedback, and serving steps. Add one or two deep dives, especially "logging schema for unbiased training" and "latency budget per stage". These would make the case more useful for senior/staff interview preparation.

## System Design Soundness

The core design is sound. The high-level architecture has the right components for a large-scale recommender: recommendation API, experiment/model router, candidate generator, ANN index, popularity/user/catalog recall sources, ranker, feature store, eligibility/diversity re-ranker, result cache, event stream, realtime features, data lake, offline features, trainer, model registry, and observability.

The main weakness is the lack of hard capacity math. The p99 latency target is stated, but the design should explain how the budget is split: cache lookup, experiment routing, parallel recall, feature batch fetch, model scoring, filters, event append, and response serialization. It should also state whether events are logged synchronously or asynchronously, because waiting on the event stream can hurt tail latency.

The API is intentionally simple and readable. It would be more production-realistic if `GET /v1/recommendations` included `surface`, `locale/region`, `device`, `sessionId`, and optional `debug`/`explain` controls, while `POST /v1/events` included idempotency or client event ids, event timestamp, dwell duration, and exposure rank. The response currently returns `modelArm` and item scores, but the logged data model should preserve the exact per-item exposure details used for later evaluation.

The data model covers the basics, but it is missing a first-class exposure table, model/feature lineage, and retention/deletion metadata. `recommendation_request.served_item_ids` as an array is convenient but too lossy for training and analysis.

## Step-by-Step Pedagogical Review

### Step 1: Start with Simple Candidate Generation

This is the right opening. It teaches bounded, explainable recall before ML complexity and gives cold-start/fallback behavior early. Consider adding one trap: "building only personalized recall and forgetting anonymous/cold traffic."

### Step 2: Refine Recall with Embeddings and ANN

The HNSW, IVF-PQ, and LSH options are well chosen and explain the recall-latency-memory trade-off. The step would be stronger if it described ANN evaluation metrics: recall@K, latency, index memory, rebuild time, and fresh-item insertion behavior.

### Step 3: Ranking the Candidates

The tree, neural, and linear-model options are useful and realistic. The missing piece is evaluation: offline AUC/NDCG is not enough, and the step should warn that rankers can overfit historical exposure bias. Add a trap or deep dive that connects ranker training labels to the exposure log from step 6.

### Step 4: Features and the Feature Store

This is one of the strongest sections. It explains online/offline parity clearly and gives practical trade-offs among full feature store, request-time computation, and precompute-only features. Add point-in-time correctness and feature backfill as explicit concerns.

### Step 5: Post-Ranking Filters and Diversity

The step correctly separates raw model scores from the final product list. MMR, category caps, and DPP are good option choices. This step is also the natural place to add policy, privacy, regional compliance, and sensitive-category controls.

### Step 6: The Feedback Loop: Events, Training, Models

The section has the right shape and calls out impression logging. To match the counterfactual-evaluation promise, it needs exposure propensities and policy metadata in the data model. The contextual-bandit option is good, but should explicitly state that exploration decisions must be logged with propensities.

### Step 7: Serving: Latency, Cold Start, and Resilience

This step lands the production concerns, but it is currently less developed than the earlier option-driven steps. Add explicit latency budget numbers and failure-mode mechanics. The existing failure drill for ranker outage is useful; add drills for feature-store timeout, ANN stale index, event-stream outage, and bad model rollout.

## Final Design Review

The final design coherently integrates every major step. The diagram includes both online serving and offline feedback, and the two final flows - online serving and feedback to model refresh - are a good wrap-up.

The final design should make one dependency clearer: model versions, feature-set versions, ANN embedding versions, and experiment arms must be compatible. Without that, a model can be rolled out against stale or mismatched features/embeddings. Add this to the model registry or experiment router description.

## Concept Introduction and Learning Flow

The concept order is excellent: start with recall, add ANN, add ranking, then features, filters, feedback, and serving hardening. The learner sees one new problem at a time. The concept cards are useful, but the dataset would benefit from more "common trap" cards because recommenders have many plausible but wrong simplifications.

## Step-to-Final-Design Coherence

Each step contributes visible components to the final design. The final diagram includes the nodes introduced along the way, and the `satisfies` section maps requirements to steps correctly.

The weakest transition is from "feedback loop" to "serving resilience." The recap says feedback creates cold-start and serving risks, but cold start actually appears throughout the design: simple recall, content features, exploration, ANN refresh, and filters. Consider making cold start a thread that appears in steps 1, 5, 6, and 7 rather than mostly landing at the end.

## Realism Compared With Production Systems

The design resembles real production recommender architecture, especially in its separation of recall and ranking, its feature-store emphasis, and its feedback loop. The reading list is strong and well grouped.

The largest realism gaps are operational and governance details:

- No concrete SLO budget per serving stage.
- No event idempotency, deduplication, schema evolution, late-event handling, or replay/backfill plan.
- No first-class exposure/proxy-propensity log for biased feedback correction.
- No model/feature/embedding lineage compatibility rule.
- No privacy, deletion, consent, or retention workflow.
- Limited discussion of observability beyond metrics: data drift, feature freshness, model quality, guardrail metrics, fallback rates, and per-surface experiment health should be named.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Step view nodes and option view nodes all reference canonical `highLevelArchitecture.nodes`.
- Step, option, and final-design view links all resolve to `highLevelArchitecture.links`.
- Step highlights resolve to known node IDs.
- Flow participants and messages resolve to canonical node IDs.
- `patterns[*].steps`, `steps[*].patterns`, `steps[*].probeLinks`, and `satisfies[*].steps` references resolve.
- The dataset uses structured `view` and structured `sequence` objects rather than raw Mermaid for architecture and flow diagrams, which matches repo conventions.
- No generated `docs/` rebuild is needed for this review file alone.

## Recommended Edits, Prioritized

### P1: Add quantitative capacity and latency budget

Add request scale, candidate fan-out, feature read count, event write volume, embedding/index memory estimate, and per-stage latency budget.

### P1: Add exposure logging schema

Introduce per-item exposure rows with rank, score, candidate source, policy/model/feature versions, experiment id, and propensity. Connect it to counterfactual evaluation and contextual bandits.

### P1: Add privacy and data-governance requirement

Add consent, retention, deletion propagation, sensitive-category controls, and regional/policy constraints to requirements, data model, and filters/feedback.

### P2: Expand serving resilience

Add options or deep dives for online/cached/hybrid serving, stage deadlines, partial recall, stale features, cache invalidation, dependency isolation, and rollback mechanics.

### P2: Add traps and drills

Add traps for stale embeddings, ANN recall tuning, offline metric overfit, position bias, feedback loops, train/serve skew, and personalized-cache staleness.

### P3: Enrich API examples

Include `surface`, `sessionId`, `locale`, `requestTimestamp`, `idempotencyKey` or `eventId`, dwell duration, and client event time. Clarify whether event logging is synchronous or asynchronous.

## What Not To Change

- Keep the simple-recall-first teaching order.
- Keep ANN framed as one recall source, not the entire recommender.
- Keep feature-store parity as a central correctness concept.
- Keep post-ranking filters separate from model ranking.
- Keep the final design's online/offline split; it is the right mental model for this case.

## Bottom Line

This is already a high-quality recommendation-system interview case. The next improvements should not change the architecture's spine; they should make the case more production-grade by quantifying capacity, modeling exposure logs correctly, adding privacy/governance, and expanding operational failure handling.
