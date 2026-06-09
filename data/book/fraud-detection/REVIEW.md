# Review: Fraud / Abuse Detection - System Design

Reviewed file: `data/book/fraud-detection/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent hardening pass materially improved this interview. The previous
review's biggest issues are now addressed: capacity is numeric, decision
identity and idempotency are explicit, the data model names the operational
state behind the architecture, review/challenge are modeled as workflows, the
fallback story is per-action rather than a universal "fail open", privacy and
poisoning are first-class requirements, and the old Step 3 local-view endpoint
mismatch is fixed.

The dataset is now a strong book-quality fraud-system walkthrough. The core
architecture is credible, the teaching arc is clear, and the final design
integrates the concepts introduced by the steps. Remaining work is mostly a
second-pass polish: align a few stale wrap-up/interviewer phrases with the new
fallback stance, make challenge/review API contracts a bit more explicit, and
turn the new capacity assumptions into a few concrete sizing and operating
decisions.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.5/5 | Strong real-time risk architecture with numeric load, idempotent decisions, feature snapshots, graph state, review state, and versioned policy/model records. |
| Production realism | 4.3/5 | Much more operationally grounded; review/challenge contracts, retention policy, and concrete staffing/sizing could be sharper. |
| Pedagogical flow | 4.6/5 | The progression from static rules to ML, features, graph, review, feedback, and resilience is clean and interview-friendly. |
| Dataset/rendering fit | 4.7/5 | JSON parses, structured views resolve, local link endpoints resolve, and canonical node types are valid. |
| Overall | 4.5/5 | Ready as a strong flagship case after a small consistency/polish pass. |

## What Changed Since The Prior Review

- Capacity now has design-driving assumptions: ~5k peak decisions/sec,
  10-20k events/sec, 50-150k feature reads/sec, hot-key notes, p99 ~50ms,
  graph edge growth, review arrival rate, label lag, and audit storage.
- `POST /v1/risk/decision` now includes `actionId`, `idempotencyKey`,
  `eventTime`, entity IDs, policy context, `decisionId`, policy/model versions,
  fallback mode, and challenge/review references.
- Events and labels now have dedupe/join semantics: event IDs, dedupe keys,
  event time versus ingest time, decision IDs, and label source trust.
- The data model now backs the system's claims with `decisions`, `events`,
  `feature_snapshots`, `graph_edges`, `review_cases`, `challenge_attempts`,
  versioned rules/policies/models, online features, and labels.
- Step 3 now explains dedupe, late/out-of-order events, hot-key strategy, and
  decision-time feature snapshots.
- Step 5 now treats review as a case state machine with evidence snapshots,
  SLA, analyst assignment, resolution, appeals, RBAC, and audit logging.
- Step 7 now gives p95/p99 latency slices, feature-staleness and fallback-rate
  alerting, per-action fallback behavior, reason redaction, probing defense, and
  poisoning/drift controls.
- The Step 3 renderer issue from the previous review is resolved: the view now
  includes `Rules` before using the `rules-features` link.

## What Works Well

The seven-step arc is strong. The interview starts with understandable static
rules, then introduces the exact pressures that force a real fraud platform:
fuzzy ML scoring, fresh velocity features, entity graph signals, tiered
decisions, human review, label lag, retraining, latency budgets, graceful
degradation, and adversarial behavior.

The design avoids common fraud-interview mistakes. It does not put graph
traversal on the inline path, does not rely on batch-only features for
seconds-fresh abuse, does not collapse every score into a binary allow/block
decision, and does not pretend chargeback labels are immediate or clean.

The API and data model now give the candidate concrete hooks for senior-level
discussion: idempotent scoring retries, decision-time feature snapshots,
event-time processing, source-trusted labels, versioned policy/model rollout,
and auditability.

The final design is coherent with the steps. Every major component introduced
in the walkthrough appears in the final architecture, and the final description
now names state ownership instead of leaving stores implied.

## Highest-Impact Issues

### 1. A few wrap-up/interviewer phrases still say "fail-open fallback"

Most of the dataset now correctly says fallback is per-action and risk-aware:
login can challenge, small payment can allow-with-flag, high-value payment can
require step-up/review, and account creation can rate-limit. Two wrap-up areas
still use the older phrasing:

- `interviewScript[2].say[]`: "Latency budget, fail-open fallback, adversarial
  concerns."
- `levelVariants[2].expectations[]`: "Designs entity-graph features and
  fail-open fallback."

Why it matters: this is exactly the teaching point the hardening pass fixed.
"Fail open" is a dangerous shorthand for fraud systems because it can imply
that a risk-engine outage should wave through high-value actions. The main
content says the opposite; the interviewer scaffolding should not reintroduce
the old mental model.

Concrete fix: replace those phrases with "per-action fallback policy" or
"risk-aware fallback matrix". For Staff level, say the candidate should reason
about per-action degradation, feature staleness, fallback-rate alerting, and
audit records for missing model/features.

### 2. Challenge and review are well modeled, but the external contract is still thin

Step 5 and the data model now do a good job describing `review_cases` and
`challenge_attempts`. The API examples expose `challengeId` in the decision
response, and the prose says review/challenge outcomes feed labels. What is not
yet as explicit is how callers and downstream systems observe and complete
those workflows.

Why it matters: in a real platform, "challenge" and "review" are not just
decision labels. A caller must know whether to block the action pending a
challenge, when a challenge expires, how to report challenge completion, how a
review case is opened, and how final outcomes produce labels/reversals/refunds.
Without that contract, the architecture is correct but the integration story is
partly implied.

Concrete fix: add a concise note or endpoint examples for challenge/review
state transitions. Examples: decision response returns either `challengeId` or
`reviewCaseId`; `POST /v1/events` accepts `challenge_passed`,
`challenge_failed`, `review_resolved`, or `payment_reversed` outcome events; or
add a small `GET /v1/risk/cases/{caseId}` / callback note if the product flow
needs async status. Keep it small, but make the lifecycle observable.

### 3. Capacity is now numeric, but only partly converted into concrete sizing

The new capacity section is a major improvement. It gives peak QPS, event
amplification, feature reads/writes, graph edge growth, review arrivals, label
lag, and audit storage. The step prose uses some of those numbers, especially
for feature serving and review rate.

Why it matters: the next level of interview value is showing how those
assumptions drive implementation choices. For example, ~50-150 cases/sec to
review is too high for manual review unless the band is aggressively sampled,
batched, or limited by analyst staffing. ~0.5-1 TB/day of audit data forces
tiered storage and query/index trade-offs. 50-150k feature reads/sec affects
cache replication and shard count.

Concrete fix: add two or three derived decisions, not a full capacity chapter:
approximate stream partitions/consumer parallelism, feature-store shard/replica
reasoning, analyst staffing or review-band throttling, and audit hot/cold
retention tiers. This will make the numeric assumptions visibly shape the
design rather than sit mostly in the overview.

### 4. Privacy controls are present but could be made operational by record type

The dataset now names tokenized identifiers, analyst RBAC, internal-only reason
codes, rate limiting, dedupe, label trust, drift monitors, and poisoning
defense. That is the right set of concerns.

Why it matters: fraud systems hold sensitive linkage data: user-device-IP-card
relationships, review evidence, chargebacks, labels, and reason codes. Those
records often need different retention, access, deletion, and audit rules. A
single privacy sentence is less teachable than a small operational matrix.

Concrete fix: add a short drill or table: decisions retained 12-24 months,
raw events tiered/compacted, graph edges expire by type/confidence, review
evidence restricted to analyst RBAC, labels retained for model audit, card/IP
identifiers tokenized or salted, and attacker-facing reason strings separated
from internal explanations.

## System Design Soundness

The requirements are now well balanced. They cover synchronous scoring,
rules-plus-ML, velocity/reputation features, entity graph detection, review and
learning, latency, false positives, fast adaptation, auditability, fallback
policy, and privacy/abuse resistance.

The API is credible. The decision endpoint now has the retry semantics a risk
engine needs: same idempotency key and same payload returns the original
decision; same key with different payload is rejected. Events are deduped and
carry event time separately from ingest time. Labels join to the exact decision
and include source trust. The main missing API detail is lifecycle visibility
for challenge/review states.

The data model now supports the architecture. It has durable decision records,
raw event identity, feature snapshots for point-in-time training joins, graph
edges, review cases, challenge attempts, versioned policy/model governance,
online features, and labels. This is a large improvement over the previous
three-table model.

The architecture is technically sound. The inline path is bounded to rules,
feature reads, model scoring, and precomputed graph features. Heavy streaming
aggregation, graph maintenance, review, and retraining are outside the critical
path. The final design correctly states that graph traversal is never done
inline.

## Step-by-Step Pedagogical Review

### Step 1: Naive: A Few Static If-Rules Inline in the App

This remains a good baseline. It makes speed and explainability visible while
exposing the limits of static thresholds, hard-coded deployment, false
positives, and coordinated abuse.

Small improvement: briefly mention that even the baseline needs audit and retry
awareness once it becomes a service. That would prepare the reader for why the
decision endpoint later includes identity and idempotency.

### Step 2: Inline Decisioning: Rules + ML

This step is now much cleaner. It explicitly says the model depends on fresh
features and that Step 3 will design how those features stay fresh. It also
adds decision IDs, reasons, and exact rule/model/policy versions for replay and
disputes.

The options are useful: hybrid, rules-only, and ML-only are real alternatives,
and the default hybrid choice is the right interview answer.

### Step 3: Streaming Velocity Features

This is one of the strongest steps. It connects event throughput, hot keys,
dedupe, event time, watermarks, bounded lateness, online/offline parity, and
feature snapshots into one coherent feature-serving story.

Small improvement: add a concrete partitioning example such as "partition by
entity type + entity hash; split known hot IP/device keys". That would turn the
hot-key warning into an implementation decision.

### Step 4: Entity Graph for Coordinated Abuse

The graph step is production-realistic because it avoids live graph traversal on
the decision path. It says links are maintained from events and graph features
are materialized into the feature store. Edge confidence and expiry are also
good details.

Small improvement: mention how graph features are refreshed and invalidated
when edges expire, because stale shared-IP/device edges are a common false
positive source.

### Step 5: Sync vs Async: Block, Challenge, Review

This step improved significantly. It now frames review as a state machine with
evidence snapshots, priority, SLA, analyst ownership, resolution, labels,
appeals, RBAC, and audit logs.

Remaining improvement: make the caller-facing lifecycle explicit, especially
for challenge completion and review resolution. That can be a small contract
note rather than a new full step.

### Step 5a: Decision Tiers and Thresholds

This sub-step is valuable and should stay. It gives candidates a clean way to
talk about cost matrices, per-action thresholds, canary rollout, rollback, and
metrics such as approval rate, challenge completion, fraud loss,
false-positive rate, and review load.

Small improvement: connect the threshold policy version to the decision
response and audit record in one sentence so the cross-step link is obvious.

### Step 6: The Feedback Loop: Labels and Retraining

This is strong. It covers label lag, point-in-time correctness, feature
snapshots, source trust, noisy labels, registry validation metrics, feature-set
compatibility, shadow/canary/champion rollout, rollback, drift, and emergency
rules.

Small improvement: add one explicit "do not train on analyst-only evidence"
reminder here as well as in Step 5, because it is a subtle leakage point.

### Step 7: Latency, Failure Modes, and Adversarial Robustness

The final step is now appropriately operational. It gives p95 and p99 latency
budgets, bounded model/feature work, fallback-rate and feature-staleness
alerts, per-action fallback behavior, audit fields for degraded scoring,
reason redaction, probing defense, dedupe, source-trust weighting, drift
monitors, and fast rules updates.

Main fix: align `interviewScript` and `levelVariants` with this step by
removing stale "fail-open fallback" wording.

## Final Design Review

The final design is coherent and well integrated. It includes the inline risk
API, rules engine, ML model, feature store, event stream, streaming aggregator,
entity graph, review queue, analyst/review tool, label store, and offline
trainer. It also names state ownership explicitly: event log for raw events,
feature store/snapshots for served features, graph for links, `review_cases`
for review state, and versioned rules/policies/models for rollout.

The final description now captures the right fraud-system stance: feature
freshness, online/offline parity, materialized graph features, tiered decisions,
point-in-time labels, source-trust weighting, p99 latency, per-action fallback,
audit, tokenized identifiers, and obscured attacker-facing reasons.

The only remaining integration gap is challenge/review observability for
callers. The final design says the workflows exist; a small API/status note
would make them fully concrete.

## Concept Introduction and Learning Flow

The concept order is excellent:

- Static rules expose the baseline.
- Rules + ML introduces hybrid inline scoring.
- Streaming features explain freshness and online/offline parity.
- Entity graph introduces coordinated-abuse detection.
- Review and challenge introduce false-positive management.
- Feedback loop introduces labels, lag, and model rollout.
- Serving robustness closes with latency, degradation, and adversaries.

The previous flow issue, where Step 2 used features before Step 3 explained
them, is now handled by an explicit "assume they exist for now" sentence. That
keeps the walkthrough natural.

## Step-to-Final-Design Coherence

The steps now map cleanly to the final design:

- Step 1 motivates moving rules into a risk service.
- Step 2 introduces RiskAPI, Rules, Model, decision identity, and versioned
  audit records.
- Step 3 introduces EventLog, AggSvc, Features, dedupe, event time, snapshots,
  and online/offline parity.
- Step 4 introduces Graph and materialized graph features.
- Step 5 introduces CaseQ, Analyst, LabelStore, review case state, and
  challenge/review outcomes.
- Step 5a introduces threshold policy and rollout governance.
- Step 6 introduces Trainer, source-trusted labels, model registry, and
  champion/challenger rollout.
- Step 7 ties the inline path to latency, fallback, observability, and
  adversarial hardening.

The final design includes all major components and now also includes the state
records that make them real.

## Realism Compared With Production Systems

The interview is realistic for an interview-sized design. It captures the key
operational tensions: low latency versus rich signals, recall versus false
positives, inline decisioning versus async review, fresh features versus
expensive computation, graph power versus graph latency, fast rules versus slow
labels, and attacker-facing opacity versus internal explainability.

Production systems would still need more detail on:

- Caller-visible challenge/review state transitions.
- Analyst staffing and queue throttling given the stated 1-3% review rate.
- Feature-store shard/replica strategy for 50-150k reads/sec and hot entities.
- Stream partition count, replay strategy, and backfill behavior.
- Per-record retention/deletion/access rules for events, graph edges, review
  evidence, labels, and audit records.
- Model/rules/policy approval workflow and emergency override controls.
- Metrics dashboards tying fraud loss, approval rate, false positives,
  challenge completion, review backlog age, drift, fallback rate, and feature
  freshness together.

Those are good advanced follow-up directions rather than blockers.

## Dataset and Renderer-Facing Observations

- JSON parses successfully.
- Top-level structure is valid for this project: requirements, capacity, API,
  data model, high-level architecture, steps, final design, satisfies,
  interview script, level variants, follow-ups, and probe links are present.
- `steps[]` contains eight entries, including one valid sub-step:
  `decision-tiers` has parent `review`.
- Main step, option, and final-design view node references resolve to
  `highLevelArchitecture.nodes` when authored as string references.
- Main step, option, and final-design view link references resolve to
  `highLevelArchitecture.links` when authored as string references.
- Local view endpoint checks pass: every referenced link's `from` and `to`
  endpoints are present in that view's node list.
- `satisfies[*].steps[*]` resolves to real step IDs.
- Dataset `patterns[*].steps[*]` resolves to real step IDs.
- No raw `diagram` fields appear under structured step/final/API flow areas.
- Canonical node types used by the dataset are valid for the current template
  set: `actor`, `cache`, `client`, `database`, `model`, `queue`, `service`,
  `stream`, and `worker`.
- API request/response examples are stringified JSON, which matches the current
  renderer's `<pre>` handling.
- `REVIEW.md` is repo-only; no docs rebuild is needed for this review update.

## Recommended Edits, Prioritized

### P1: Remove stale "fail-open fallback" phrasing from wrap-up helpers

Change the `interviewScript` and Staff `levelVariants` language to
"per-action fallback policy" or "risk-aware fallback matrix" so the wrap-up
matches Step 7 and the final design.

### P2: Make challenge/review lifecycle observable in the API contract

Add a short note or endpoint examples showing how `challengeId` and
`reviewCaseId` are created, completed, expired, resolved, and joined back to
events/labels.

### P2: Convert the new capacity numbers into a few sizing decisions

Add concise derived choices for stream partitions, feature-store sharding,
review staffing/backlog limits, and hot/cold audit retention.

### P2: Add a record-type privacy/retention mini-matrix

Show retention, access, tokenization, and expiry rules for decisions, events,
graph edges, review evidence, labels, and internal reason codes.

### P3: Tighten advanced follow-ups around operations

Add or retarget follow-ups for analyst staffing under review spikes, feature
backfill/replay, graph edge expiry, and emergency policy rollback.

## What Not To Change

- Keep the seven-step arc and the Step 5a sub-step.
- Keep the rules + ML hybrid as the default decisioning option.
- Keep streaming velocity features as the default feature strategy.
- Keep graph features materialized outside the inline path.
- Keep block/challenge/review as the core policy trade-off.
- Keep point-in-time labeling, source-trust weighting, and online/offline
  parity as senior-level learning points.
- Keep the final step focused on latency, degradation, observability, and
  adversarial behavior.

## Bottom Line

The fraud-detection interview is now a strong, production-shaped walkthrough.
The recent changes resolved the prior review's major concerns. A small follow-up
pass should remove stale fail-open wording, expose challenge/review lifecycle
semantics a bit more clearly, and connect the new capacity numbers to concrete
operating choices.
