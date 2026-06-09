# Review: Fraud Detection - System Design

Reviewed file: `data/book/fraud-detection/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a coherent and useful fraud-risk walkthrough. The step arc is strong:
start with static rules, add inline rules + ML, introduce fresh velocity
features, add entity graph signals, split decisions into block/challenge/review,
close the label/retraining loop, and finish with latency/failure/adversarial
concerns.

The main gaps are production depth rather than concept choice. The dataset
teaches the right components, but several of the contracts and records needed to
operate those components are still implied: quantitative capacity, idempotent
decision/event identity, review-case state, challenge outcomes, graph storage,
rules/model versioning, privacy controls, and per-action fallback policy.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 3.8/5 | The architecture is directionally right, but capacity, API identity, and data-model backing are too light. |
| Production realism | 3.4/5 | Good fraud concepts; missing key operational state for idempotency, review workflow, model rollout, privacy, and poisoning resistance. |
| Pedagogical flow | 4.2/5 | The sequence of steps is clean and interview-friendly, with good prompts and recaps. |
| Dataset/rendering fit | 3.9/5 | JSON parses and most references resolve; one step view references a link endpoint not included in that view. |
| Overall | 3.8/5 | Strong draft; one focused production-hardening pass would make it book-quality. |

## What Works Well

- The requirements name the core fraud-engine tensions: low-latency inline
  decisions, recall versus false positives, fast adaptation, auditability, and
  graceful degradation.
- The high-level architecture uses the right primitives: risk API, rules
  engine, model serving, online feature store, event stream, streaming
  aggregator, entity graph, review queue, label store, and trainer.
- The pedagogical progression is effective. Each step removes a concrete blind
  spot from the previous step instead of jumping straight to the final design.
- The options in Steps 2, 3, and 5 compare real choices rather than strawmen:
  rules-only, model-only, batch features, on-demand features, binary allow/block,
  and allow-but-flag are all useful interview trade-offs.
- The dataset introduces point-in-time labeling, online/offline feature parity,
  tiered thresholds, and adversarial reason leakage, which are the right
  differentiators for a senior fraud-system answer.
- The final design integrates the main components introduced by the steps and
  clearly states the intended steady-state behavior.

## Highest-Impact Issues

### 1. Capacity is qualitative, not design-driving

The capacity section currently says "very high", "tens of ms", "seconds", and
"small" without any numeric assumptions. That keeps the design plausible, but it
does not force the candidate to size the critical paths.

Why it matters: fraud systems are shaped by derived work units. A design for 500
decisions/sec, 5,000 decisions/sec, and 100,000 decisions/sec makes different
choices for feature-store partitioning, event-stream partitions, graph update
strategy, review sampling, model-serving fleet size, and audit-retention cost.

Concrete fix: add explicit assumptions and derived numbers, for example:
decision QPS by action type, event write amplification per decision, features
read per score, feature update rate, hot-key skew by IP/device/card, graph edge
growth, review queue arrival rate, label lag distribution, audit row size, and
retention period. Tie those numbers to Step 3 feature serving, Step 4 graph
updates, Step 5 analyst capacity, and Step 7 latency budget.

### 2. The API lacks stable identity and idempotency for the records used later

`POST /v1/risk/decision` accepts action fields and returns a decision, score,
and reasons. The data model then has `decisions.action_id`, the events endpoint
emits action/outcome events, and labels refer to `actionId`. The API does not
show who creates `actionId`, how duplicate scoring requests replay, or which
decision record a later event/label joins to.

Why it matters: inline callers retry. Without a stable `actionId` or
idempotency key, the system can double-count attempts, create conflicting
decisions, poison velocity features, and make labels hard to join to the exact
decision and feature snapshot.

Concrete fix: put `actionId`, `idempotencyKey`, `eventTime`, `tenant` or
business context if scoped, `entityIds`, and `policyContext` in the decision
request. Return `decisionId`, `decisionVersion` or `policyVersion`,
`modelVersion`, `fallbackMode`, and a `challengeId` or `reviewCaseId` when
applicable. State replay semantics: same key and payload returns the original
decision; same key with different payload is rejected.

### 3. The data model is too thin for the architecture it teaches

The model lists `decisions`, `features (online)`, and `labels`. Those are useful
but do not back several core mechanisms in the walkthrough: raw event retention,
feature definitions and point-in-time snapshots, entity graph edges, review
cases, challenge attempts, rule versions, model registry/deployments, threshold
policies, and audit access.

Why it matters: the prose says the system is auditable, explainable,
reviewable, retrainable, graph-aware, and fail-safe. Those claims require
durable records. Otherwise the diagrams teach components whose state ownership
is unclear.

Concrete fix: add small data-model sections for:

- `events` or event log schema with event ID, action ID, event time, ingest time,
  entity IDs, and dedupe key.
- `feature_snapshots` or decision-time feature references for training
  correctness.
- `graph_edges` / `entity_links` with entity type, confidence, first/last seen,
  and source event.
- `review_cases` and `challenge_attempts` with state transitions and outcomes.
- `rulesets`, `decision_policies`, and `model_versions` with rollout state.

### 4. Review and challenge are conceptually strong but operationally under-modeled

Step 5 and Step 5a correctly teach block/challenge/review tiers. The API and
data model do not show the lifecycle of a challenge or review case: creation,
assignment, SLA, analyst decision, customer outcome, reversal/refund/hold, label
emission, and appeal/dispute handling.

Why it matters: "send to review" is not a queue alone. A fraud review workflow
has state, priority, evidence snapshots, access control, analyst audit trail,
and label quality concerns. It also determines whether "allow-but-flag" is
acceptable for payments versus logins versus account creation.

Concrete fix: add a short state machine and fields for `review_cases`: `case_id`,
`action_id`, `decision_id`, `state`, `priority`, `assigned_to`, `evidence_ref`,
`due_at`, `resolution`, `resolved_at`, and `label_id`. For challenges, model
`challenge_id`, method, status, expiry, attempts, and final outcome. Mention how
review/challenge outcomes feed labels without leaking analyst-only evidence.

### 5. "Fail open to rules-only" needs per-action policy and clearer language

The non-functional requirement says a scoring outage degrades to a safe default.
The final design says it "fails open to rules-only", and Step 7 says
"rules-only (or a conservative default)". That is a useful instinct, but it is
not universally safe.

Why it matters: for low-risk browsing, fail-open may be fine. For high-value
payments, a model/feature outage may need challenge, lower limits, manual
review, or temporary throttling. Calling all of those "fail open" can teach the
wrong operational policy.

Concrete fix: replace the single fallback with a per-action fallback matrix:
login may challenge, small payment may allow with risk flag, high-value payment
may require step-up or review, account creation may rate-limit. Log the
fallback reason, alert on fallback rate, and keep the audit record explicit
about missing model/features.

### 6. Privacy, abuse, and poisoning controls need first-class treatment

The design uses sensitive identifiers: device, IP, card, user, address, and
fraud labels. It also exposes a scoring API that attackers can probe and an
event/label pipeline that can be poisoned.

Why it matters: fraud detection is both security-sensitive and
privacy-sensitive. A production design needs retention limits, tokenization or
hashing, analyst access controls, audit logs, reason redaction, sampling or
rate-limits against probing, and guardrails around labels/features contributed
by untrusted sources.

Concrete fix: add a security/privacy subsection or late step drill covering PII
minimization, tokenized identifiers, card data handling, retention by record
type, analyst RBAC, reason redaction, event dedupe, label-source trust levels,
and drift/poisoning monitors.

## System Design Soundness

The requirements are well chosen. They avoid a narrow "classify fraud" framing
and correctly cover synchronous decisioning, hybrid rules + ML, velocity
features, graph signals, human review, adaptation, auditability, and graceful
degradation.

Capacity is the weakest foundation. The current labels describe qualitative
pressure but do not create sizing constraints. Fraud systems need even rough
numbers for peak QPS, p99 latency budget breakdown, feature-store read QPS,
stream partitions, per-entity hot-key skew, graph update volume, review backlog,
and audit storage. Without those, the choices in Step 3 and Step 7 are correct
but not quantitatively defended.

The API is directionally right but too small. `POST /v1/risk/decision`,
`POST /v1/events`, and `POST /v1/labels` are the right surface areas. They need
stable identity, idempotency, event time versus ingest time, source trust,
policy/model versions, and outcome references. The decision response should also
separate attacker-facing messaging from internal reason codes.

The data model supports the first layer of the story but not the whole system.
`decisions` is a good audit anchor and already includes reasons plus
`model_version`. The online features and labels tables are also appropriate.
Missing state for event dedupe, graph edges, review cases, challenge attempts,
rulesets, policies, model deployment, and feature snapshots is the biggest
soundness gap.

The architecture is credible. It puts heavy aggregation off the inline path,
keeps the decision API synchronous, and uses a feedback loop for retraining. The
main architecture improvement is to make state ownership explicit: which store
owns events, which owns feature definitions, which owns graph links, which owns
review cases, and which owns model/rules rollout.

## Step-by-Step Pedagogical Review

### Step 1: Naive: A Few Static If-Rules Inline in the App (the baseline)

This is a strong baseline. It makes the limits of static thresholds and
hard-coded rules obvious, and the trap is well targeted.

Improvement: mention idempotency and audit even in the baseline. A naive risk
system can be fast and explainable but still fail by making the same retried
action look like multiple actions.

### Step 2: Inline Decisioning: Rules + ML

The core trade-off is well explained. Rules-only and model-only are useful
alternatives, and the default hybrid option is the right answer for interviews.

Improvement: the sequence already includes a feature store before Step 3
introduces how features are built. That is acceptable if framed as "we will
design this next"; otherwise, it slightly front-loads a component before the
reader understands its ownership. Add a sentence saying the model currently
depends on fresh features and the next step builds the feature path.

Also add policy/version details here: rule version, model version, threshold
policy version, decision ID, and internal versus external reasons.

### Step 3: Streaming Velocity Features

This is one of the strongest steps. It teaches why batch and on-demand feature
computation both miss the inline freshness/latency target.

Improvement: add event schema, dedupe, late/out-of-order handling, and hot-key
strategy. Fraud velocity counters are vulnerable to duplicate events and skewed
entities such as a shared IP, a popular merchant, or an attack device. A short
failure drill for duplicate/replayed events would make the step more
production-real.

Rendering note: this step's main view includes the `rules-features` link but
does not include the `Rules` node in `view.nodes`. The global link is valid, but
locally the endpoint is absent. Add `Rules` to the Step 3 view nodes or remove
that link from this specific view.

### Step 4: Entity Graph for Coordinated Abuse

The motivation is excellent. The examples of shared device, IP, card, and known
fraud cluster make the value of graph features clear.

Improvement: state what is stored online versus computed offline. Entity graphs
can be expensive on the decision path, so the interview should distinguish
precomputed graph features from live traversal. Add a small data-model entry for
graph edges and a note on edge expiry, confidence, privacy, and feature
materialization.

### Step 5: Sync vs Async: Block, Challenge, Review

The tiering trade-off is strong and realistic. The three options are useful
because they expose the false-positive versus fraud-loss business trade-off.

Improvement: model the lifecycle. The review queue needs priority, ownership,
case state, evidence snapshot, SLA, analyst decision, label emission, and audit
trail. Challenge also needs an outcome record. Without those, Step 5 teaches the
right policy but not enough of the system that runs it.

### Step 5a: Decision Tiers and Thresholds

This sub-step is valuable. It keeps threshold policy from being buried inside
Step 5 and correctly ties thresholds to a cost matrix.

Improvement: connect the cost matrix to a versioned `decision_policies` record
and to monitoring. Threshold changes should be auditable, rolled out safely, and
measured by approval rate, challenge completion rate, fraud loss, false-positive
rate, and review load.

### Step 6: The Feedback Loop: Labels and Retraining

This step introduces the most important ML-systems correctness idea:
point-in-time labels. The champion/challenger mention is also good.

Improvement: add a model registry/deployment record and label quality details.
Labels from chargebacks, analysts, and user reports have different lag and
trust. The trainer should publish a versioned model with validation metrics,
rollout state, rollback path, and feature compatibility.

### Step 7: Latency, Failure Modes, and Adversarial Robustness

This is the right closing step. It reinforces that the risk engine is on the
critical path and cannot become a single point of checkout failure.

Improvement: split "fail safe" into concrete modes by action and risk. Add p95
and p99 latency budget slices, fallback-rate alerts, feature-staleness alerts,
and explicit "do not reveal internal reason codes" behavior. Include data
poisoning and probing as failure drills, not only prose.

## Final Design Review

The final design is coherent with the steps. It includes the inline risk API,
rules engine, model, feature store, event stream, aggregator, entity graph,
review queue, label store, and trainer. The description correctly mentions
feature freshness, graph detection, tiered decisions, point-in-time correctness,
latency budgets, rules-only fallback, audit, and obscured attacker-facing
reasons.

The missing pieces are mostly state ownership and operational policy. The final
design should name the durable stores for events, review cases, graph links,
rulesets, decision policies, and model versions. It should also describe
fallback behavior as a policy matrix rather than one universal rule.

## Concept Introduction and Learning Flow

The learning flow is strong. Concepts arrive in an intuitive order:
explainable rules, fuzzy ML scoring, fresh features, graph links, tiered
outcomes, labels/retraining, and operational robustness.

The main flow issue is that features are used in the Step 2 sequence before the
feature path is introduced. This is minor, but the walkthrough would be cleaner
if Step 2 explicitly says "assume features exist for now; Step 3 designs how we
keep them fresh."

The concepts list is useful but could include a few missing production concepts:
decision idempotency, event-time processing, feature snapshot, model registry,
policy versioning, and label-source trust.

## Step-to-Final-Design Coherence

The steps mostly build toward the final design:

- Step 1 motivates why static rules are insufficient.
- Step 2 introduces the Risk API, Rules, and Model.
- Step 3 introduces EventLog, AggSvc, and Features.
- Step 4 introduces Graph.
- Step 5 introduces CaseQ, Analyst, and LabelStore.
- Step 6 introduces Trainer and the model update loop.
- Step 7 reuses RiskAPI, Rules, Features, and Model to discuss latency and
  failure behavior.

The final design includes all of those components. The coherence gaps are in
the data contract: the final design depends on action identity, decision audit
records, review state, graph state, feature snapshots, policy versions, and
model versions more than the data model currently shows.

## Realism Compared With Production Systems

For an interview, the component choices are realistic. The design does not try
to compute graph traversals inline, it does not rely on batch features for
seconds-fresh abuse, and it recognizes that hard-blocking all medium-risk users
is too costly.

Production systems would need more detail on:

- Idempotency and dedupe for risk decisions, events, labels, and review actions.
- Event-time processing, late events, replay, and exactly-once versus
  effectively-once feature updates.
- Feature definitions, feature snapshotting, and offline/online parity tests.
- Review tooling, analyst authorization, evidence snapshots, and audit logs.
- Model registry, champion/challenger rollout, drift monitoring, and rollback.
- Ruleset/policy governance, approvals, and emergency rule pushes.
- Privacy controls, tokenized identifiers, retention windows, and data-subject
  deletion constraints.
- Abuse of the risk API itself: probing, traffic spikes, poisoning, and reason
  leakage.
- Business metrics: fraud loss, false-positive rate, chargeback rate,
  challenge completion, approval rate, review backlog age, and fallback rate.

## Dataset and Renderer-Facing Observations

- JSON parses successfully.
- Top-level structure is valid for this project: requirements, capacity, API,
  data model, high-level architecture, steps, final design, satisfies,
  interview script, level variants, follow-ups, and probe links are present.
- Main step, option, and final-design view node references resolve to
  `highLevelArchitecture.nodes` when they are string references.
- Main step, option, and final-design view link references resolve to
  `highLevelArchitecture.links` when they are string references.
- `satisfies[*].steps[*]` resolves to real step IDs.
- Dataset `patterns[*].steps[*]` resolves to real step IDs.
- No raw `diagram` fields appear under structured areas.
- Canonical node types used by the dataset are valid for the current template
  set: `actor`, `cache`, `client`, `database`, `model`, `queue`, `service`,
  `stream`, and `worker`.
- Local view endpoint check found one issue: Step 3 (`features`) uses
  `rules-features`, whose `Rules` endpoint is not listed in that view's
  `nodes`.
- `REVIEW.md` is repo-only; no docs rebuild is needed for this review.

## Recommended Edits, Prioritized

### P1: Make capacity numeric and tie it to design choices

Add concrete assumptions and derived rates for decision QPS, event throughput,
feature reads/writes, graph updates, review volume, label lag, and audit storage.
Use those numbers in the Step 3, Step 4, Step 5, and Step 7 explanations.

### P1: Add decision identity, idempotency, and audit versions to the API

Update `POST /v1/risk/decision` to include stable action identity and retry
semantics. Return decision IDs and version metadata. Make events and labels join
unambiguously to the original decision and feature snapshot.

### P1: Expand the data model for the mechanisms already claimed

Add concise records for events, feature snapshots, graph edges, review cases,
challenge attempts, rulesets, decision policies, model versions, and model
deployments. Keep each small, but show state ownership.

### P2: Turn review/challenge into a real state machine

Add review-case and challenge lifecycles, including creation, assignment,
expiry/SLA, outcome, label emission, and audit trail. Tie `reviewCaseId` and
`challengeId` back to the decision response.

### P2: Replace universal fail-open wording with a fallback policy matrix

Define fallback behavior by action type and risk tier. Include alerting and
audit fields for model timeout, feature-store timeout, stale features, and
rules-only decisioning.

### P2: Add security, privacy, and poisoning drills

Cover tokenized identifiers, retention, analyst RBAC, internal-only reason
codes, probing protection, label-source trust, duplicate event defense, and
poisoning/drift monitors.

### P3: Fix the Step 3 local view endpoint mismatch

Either add `Rules` to `steps[features].view.nodes` or remove `rules-features`
from that view's links. The global link is valid, but the local view should be
self-contained.

### P3: Retarget and enrich step-level probe links

The global links are useful. Step-level links could be sharper: Step 3 should
emphasize stream processing and feature stores, Step 4 graph/entity resolution,
Step 6 ML lifecycle/model registry, and Step 7 SRE/security monitoring.

## What Not To Change

- Keep the seven-step arc and the Step 5a sub-step.
- Keep the rules + ML hybrid as the default decisioning option.
- Keep streaming velocity features as the default feature strategy.
- Keep the entity graph as a distinct coordinated-abuse step.
- Keep block/challenge/review as the core policy trade-off.
- Keep point-in-time labeling and online/offline parity as senior-level learning
  points.
- Keep the final step focused on latency, graceful degradation, and adversarial
  behavior.

## Bottom Line

This is a strong conceptual fraud-detection interview. It already teaches the
right architecture and trade-offs. To make it production-shaped, add the
quantitative sizing and durable operational state that make retries, reviews,
labels, graph features, model rollout, privacy, and fallback behavior explicit.
