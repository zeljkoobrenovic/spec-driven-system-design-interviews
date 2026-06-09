# Review: Distributed Job Scheduler / Cron - System Design

Reviewed file: `data/book/job-scheduler/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong, focused scheduler walkthrough. It teaches the right core distinction: exactly-once triggering is a scheduler responsibility, while execution is at-least-once and must be made idempotent. The step progression is coherent, the diagrams are renderer-friendly, and the wrap-up maps requirements back to mechanisms clearly.

| Axis | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4/5 | Solid backbone: durable schedule store, due index, per-shard leader, dedup key, queue, workers, retries. Needs sharper atomicity and recurrence semantics. |
| Production realism | 3/5 | Missing time-zone/DST/misfire/overlap policy, API idempotency, explicit outbox/transaction boundary, and richer operations signals. |
| Pedagogical flow | 4/5 | Each step exposes the next problem cleanly. A few diagrams and claims move faster than the supporting model. |
| Dataset/rendering fit | 5/5 | JSON parses; step/final views and step references resolve; no obvious renderer-facing schema problems. |
| Overall | 4/5 | Usable and interview-ready after a few high-impact clarifications. |

## What Works Well

- The dataset separates "exactly-once trigger" from "at-least-once execution" in requirements, steps, concepts, final design, and follow-ups. That is the right senior-level framing for this problem.
- The seven-step story has a clean escalation: naive loop, durable state, due lookup, leader election, trigger dedup, execution idempotency, retries/DLQ.
- The option sets for due lookup, election, and dispatch compare real alternatives instead of strawmen.
- The final design includes the main components introduced in the steps and does not add unrelated services late.
- The structured diagrams are well-formed. Global node/link references resolve, `satisfies` step links resolve, and pattern step links resolve.

## Highest-Impact Issues

### 1. The API and data model do not capture hard scheduler semantics

The API request only includes `name`, `schedule`, and `target`, while the requirements promise recurring cron, update/cancel, retries, and seconds-level accuracy. Production cron semantics depend on fields that are not modeled: `timezone`, schedule type, `start_at`/`end_at`, misfire/catch-up policy, max overlap/concurrency policy, retry policy, timeout, tenant/owner, API idempotency key, and target idempotency key propagation.

This matters because time-zone and DST behavior, missed fires after downtime, and overlapping long-running executions are not edge polish for cron systems. They determine what "run at 02:00" and "exactly one run per scheduled fire" mean.

Concrete fix: expand `POST /v1/jobs` and the `jobs` table with explicit scheduling policy fields. Add `PATCH /v1/jobs/{id}` or `POST /v1/jobs/{id}:pause/resume` examples that recompute `next_fire_at` and update the due index atomically. Add `client_request_id` or `idempotency_key` for create/update operations.

### 2. The default "atomic mark + enqueue" path is too magical for a separate queue

Step 5 says the dispatcher atomically marks a fire and enqueues a run. The default option admits that a separate queue needs an outbox, but the selected/default path and final design still draw `Dispatcher -> JobDB` and `Dispatcher -> RunQ` directly. That leaves the critical crash window unresolved: if the mark succeeds and enqueue fails, the run is lost; if enqueue succeeds and mark fails, it can double-fire.

Concrete fix: make "Transactional outbox" the default production answer unless `RunQ` is explicitly the same transactional store as `JobDB`. Add an `Outbox/Relay` node to the final design or add a `run_outbox` table to the data model. The flow should commit `(job_id, scheduled_fire)` plus an outbox row in one transaction, then publish to `RunQ` at least once.

### 3. Recurring `next_fire_at` ownership is inconsistent

Step 5 correctly says recurring jobs advance `next_fire_at` in the same atomic trigger step. Step 6 and the final architecture link `Workers -> JobDB` says workers compute the next fire for recurring jobs. Those are different semantics.

For cron-style scheduling, the dispatcher should usually advance to the next scheduled occurrence when it claims the current fire, independent of whether the current execution later succeeds. If workers advance the schedule only after execution, long-running or failed jobs can block future scheduled occurrences, which is fixed-delay workflow behavior rather than cron behavior.

Concrete fix: move recurring `next_fire_at` advancement to the dispatcher transaction and update the due index/outbox in that same logical step. Keep workers focused on run status, attempts, result, and target execution. If the desired product is "do not overlap runs", model that as an explicit overlap policy instead of implicit worker-owned recurrence.

### 4. Worker idempotency is worded as stronger than it really is

Step 6 says the worker records/checks `(job_id, scheduled_fire)` before executing so a redelivered run is recognized and not run twice. That can prevent duplicate worker claims, but it does not by itself prevent duplicate external side effects if the worker crashes after performing the target action but before recording success.

Concrete fix: distinguish infrastructure idempotency from target idempotency. Add fields and text for `attempt_id`, claim lease/heartbeat, visibility timeout, target timeout, and propagation of `idempotency_key` to the target. The run state machine should explain what happens to `running` claims whose worker dies.

## System Design Soundness

The core architecture is sound: durable `jobs`, due lookup through `TimeWheel` or indexed `next_fire_at`, leader election with fencing, run queue, workers, run store, retry controller, and DLQ. The design correctly treats the due index as rebuildable rather than authoritative.

The main correctness gaps are at transaction boundaries and time semantics. The design should explicitly define:

- Fire identity: likely `(job_id, scheduled_fire_at, schedule_version)`, not just `(job_id, scheduled_fire)`, so updates/cancels cannot collide with old schedule occurrences.
- Claim/update transaction: dedup marker, `next_fire_at` advance, due-index update/removal, and outbox write.
- Lease/fencing enforcement point: where the fencing token is checked when writing fire markers.
- Misfire/catch-up behavior: skip missed occurrences, run one catch-up, or enqueue all missed occurrences.
- Overlap behavior: allow concurrent runs, skip if previous still running, or queue one pending run.

Capacity is currently qualitative. "Millions" and "spiky" are useful starting labels, but the design choices need numbers: schedules stored, schedule create/update QPS, average and peak due fires/sec, top-of-hour burst size, worker concurrency, average job duration, retry amplification, and run-retention storage. Without those, it is hard to justify time wheel vs DB range scan, shard count, queue throughput, or worker autoscaling.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Cron Process on a Single Box

The text does a good job motivating durability, duplicate triggers, and scan cost. The diagram is less aligned: it already shows `Client`, `API`, and `JobDB`, which looks more like the first production step than a single in-memory cron process. Consider showing a single `Cron Process` plus in-memory schedules, then introduce `API`/`JobDB` in Step 2.

### Step 2: Durable Schedules

This step introduces the right source-of-truth idea. It should also introduce schedule versioning and create/update idempotency because later dedup depends on fire identity. If updates can move a future fire from 02:00 to 03:00, the model needs to explain which pending fire keys remain valid.

### Step 3: Finding Due Jobs Efficiently

The options are good. The missing teaching point is index mutation. The API adds entries, but updates/cancels/fires also need to remove or replace entries. The walkthrough should explain whether `TimeWheel` is a durable sorted set, an in-memory shard-local cache rebuilt from `JobDB`, or an indexed table. Each choice changes failover and burst behavior.

### Step 4: Leader Election to Avoid Duplicate Triggers

This is one of the strongest steps. The lease, TTL, fencing, and per-shard leader framing is exactly the right escalation. Tighten it by saying where the fencing token is enforced: the dispatcher should include it in the conditional fire-marker write, or the store should reject stale tokens.

### Step 5: Exactly-Once Triggering

This is the most important step and needs the clearest atomic boundary. The default option should not imply a normal DB and normal queue can be atomically updated without an outbox or shared transaction. The transactional outbox option is the better production default.

The sequence also says "enqueue run + advance next_fire" as a queue operation. That should be a store transaction followed by a relay publish, or it should be split into "commit fire marker + next_fire + outbox row" and "relay publish".

### Step 6: At-Least-Once Execution with Idempotency

The concept is right, but the claim sequence is too compressed. Add a lease/heartbeat or visibility-timeout story around `running` attempts. Also explain that worker-side dedup cannot make arbitrary targets safe unless the target accepts and honors the idempotency key or the side effect is itself transactional with the run store.

### Step 7: Retries, Backoff, and Dead-Lettering

This closes the lifecycle well. It would be stronger with a retry policy in the job definition, error classification, timeout handling, and alerting ownership for DLQ entries. Right now the DLQ exists, but the operator workflow after dead-lettering is only implied.

## Final Design Review

The final design integrates most step components cleanly. The biggest concern is that it repeats the direct dispatcher-to-queue path and worker-owned recurrence ambiguity. A production final design should either:

- include `Outbox + Relay` between `JobDB` and `RunQ`, or
- state that the queue is implemented inside the same transactional store as the fire marker.

It should also remove or relabel `Workers -> JobDB compute next-fire (recurring)` unless the product intentionally uses fixed-delay scheduling. For cron semantics, the dispatcher should compute/advance future fires during trigger claim.

## Concept Introduction and Learning Flow

The concept staging is strong and just-in-time. The candidate learns why persistence is needed, why due lookup is needed, why one dispatcher is needed, why election is not enough, and why worker execution is a different guarantee.

The main missing concepts are schedule semantics rather than distributed-systems mechanics: time zones, DST, misfires, catch-up, overlap policy, schedule versioning, and update/cancel race handling. Add these before or during Step 2 so the later dedup key has enough meaning.

## Step-to-Final-Design Coherence

Most steps flow into the final architecture:

- `store` introduces `JobDB`.
- `due` introduces `TimeWheel`.
- `election` introduces `Dispatcher` and `Lease`.
- `dispatch` introduces `RunQ` and fire dedup.
- `execute` introduces `Workers` and `RunStore`.
- `retry` introduces `Retry` and `DLQ`.

The weak transitions are the outbox omission and recurrence ownership. Step 5's transactional outbox option does not make it into the final design, even though it is needed for the stated crash safety with a separate queue. Step 6's worker-to-job-store recurrence link contradicts Step 5's atomic next-fire advancement.

## Realism Compared With Production Systems

The dataset covers the classic reliable distributed cron backbone, but production scheduler behavior also needs:

- multi-tenant isolation, quotas, and per-tenant rate limits;
- authz/audit for creating, updating, pausing, and deleting schedules;
- schedule parsing and validation errors;
- misfire/catch-up and DST/time-zone semantics;
- max runtime, timeout, cancellation of active runs, and overlap policy;
- retry policy per job, non-retryable errors, and DLQ remediation workflow;
- observability: schedule lag, fire-to-enqueue latency, queue backlog, run latency, duplicate-suppression count, lease churn, retry rate, DLQ rate, and missed-fire alerts;
- retention and compaction for run history and dedup keys.

These do not all need full steps, but the API/model and final wrap-up should acknowledge the most interview-relevant ones.

## Dataset and Renderer-Facing Observations

The source file is healthy from a renderer perspective:

- `interview.json` parses as JSON.
- Top-level keys cover the expected sections: requirements, capacity, API, data model, patterns, steps, final design, satisfies, script, level variants, follow-ups, and probe links.
- Global architecture links reference existing nodes.
- Step and final-design string node/link references resolve.
- `satisfies[*].steps[*]` and `patterns[*].steps[*]` references resolve.

No generated `docs/` changes are needed for this review because `REVIEW.md` is repo-only.

## Recommended Edits, Prioritized

### P1: Make the dispatch atomicity explicit

Promote transactional outbox to the default path or explicitly collapse `RunQ` into the transactional store. Add outbox schema/diagram/flow if the queue remains separate.

### P1: Fix recurring schedule ownership

Move `next_fire_at` advancement and due-index update to the dispatcher claim transaction. Remove the worker-owned recurring schedule link or turn it into run-status-only writes.

### P1: Add schedule semantics to API and data model

Add timezone, schedule version, misfire/catch-up policy, overlap policy, retry policy, timeout, owner/tenant, create/update idempotency key, and target idempotency key.

### P2: Add concrete capacity math

Replace qualitative capacity labels with example numbers for stored jobs, due fires/sec, top-of-hour burst, schedule-write QPS, worker concurrency, retry amplification, queue throughput, and run retention.

### P2: Clarify worker idempotency and attempt state

Add claim leases, attempt IDs, heartbeats or visibility timeout, and target idempotency-key propagation. Explain the crash-after-side-effect-before-success-record case.

### P2: Add operational signals and remediation workflows

Add metrics/alerts for schedule lag, backlog, lease churn, retries, DLQ, and duplicate suppression. Explain who handles a DLQ item and whether rerun/manual override is supported.

### P3: Align the naive-step diagram with the text

Show the true single-box/in-memory cron design in Step 1, then introduce `API` and `JobDB` in Step 2.

### P3: Consider technology choices

Because this is a `book` dataset, a `technologyChoices` wrap-up could be useful for schedule store, due index, lease store, queue, worker runtime, and observability options.

## What Not To Change

- Keep the narrow focus on distributed cron/scheduler semantics rather than broad DAG orchestration. DAGs are already a good follow-up.
- Keep the exactly-once-trigger vs at-least-once-execution distinction prominent.
- Keep leader election and fire-level dedup as separate steps; merging them would hide an important interview insight.
- Keep the compact seven-step structure. The fixes above can mostly be added as sharper model/API details and one stronger dispatch flow.

## Bottom Line

This is a strong scheduler case with a clean teaching arc. The next revision should make the production guarantees more honest by defining schedule semantics, making outbox/atomicity explicit, and resolving who advances recurring fires. Those edits would move it from a strong interview walkthrough to a production-grade reference case.
