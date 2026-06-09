# Review: Distributed Job Scheduler / Cron - System Design

Reviewed file: `data/book/job-scheduler/interview.json`
Review date: 2026-06-09

## Executive Summary

This is now a strong, production-aware scheduler walkthrough. The recent changes resolved the earlier core gaps: the API and model now include time zone, schedule versioning, misfire/overlap policy, retry policy, timeout, tenant ownership, and idempotent writes; Step 5 makes the transactional outbox the default; the final design includes `Outbox + Relay`; Step 1 now matches the single-box cron baseline; capacity is concrete; and `technologyChoices` is present.

The remaining issues are narrower and more advanced. The design is credible, but it should be more explicit about due-index consistency when the index is not the same transactional store as `JobDB`, how misfire/overlap policies are enforced in the dispatcher, and whether run state lives in `RunStore`, `JobDB`, or both.

| Axis | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4/5 | Strong durable schedule, due index, fenced dispatcher, outbox, worker idempotency, retry/DLQ design. Needs sharper due-index atomicity and overlap/misfire algorithms. |
| Production realism | 4/5 | Much improved: concrete schedule semantics, outbox, target idempotency, claim leases, capacity numbers, technology choices. Remaining gaps are operational edge cases and store boundaries. |
| Pedagogical flow | 4/5 | The seven-step progression is coherent and now introduces the hard concepts earlier. A few later policies need to be tied back to the dispatch algorithm. |
| Dataset/rendering fit | 4/5 | JSON parses and references resolve. Minor clarity issues around `JobDB` vs `RunStore`; several tech chips use generic fallback icons. |
| Overall | 4/5 | Interview-ready and close to reference quality after tightening consistency and policy enforcement details. |

## What Works Well

- The central guarantee is framed correctly: exactly-once triggering per scheduled fire, at-least-once execution with idempotency for the actual work.
- Step 2 now teaches the scheduler semantics that make cron systems hard: time zone/DST, schedule versioning, misfire/catch-up, overlap policy, retry policy, timeout, and client write idempotency.
- Step 5 now uses the right default production answer for a separate queue: commit fire marker, `next_fire_at`, and outbox row in one transaction, then publish at least once.
- Step 6 now distinguishes infrastructure idempotency from target idempotency, including the crash-after-side-effect-before-success-record case.
- Capacity is no longer hand-wavy. The dataset names stored schedules, write QPS, average due fires/sec, top-of-hour burst, worker concurrency, retention, and semantics.
- `technologyChoices` is useful and aligned with the design concerns: schedule store, due index, lease store, run queue, worker runtime, and observability.

## Highest-Impact Issues

### 1. Due-index consistency has the same cross-store problem as the queue

The design correctly fixes the `JobDB` -> `RunQ` atomicity gap with an outbox, but the API and Step 3 still imply that `JobDB` and `TimeWheel` can be updated together when creating, updating, canceling, and firing schedules. That is only true if the due index is implemented inside the same transactional store as `jobs`.

If `TimeWheel` is Redis, an in-memory wheel, or another separate system, a crash after writing `JobDB` but before indexing `next_fire_at` can make a job invisible until rebuild. A crash after changing a schedule but before removing the old due entry can leave stale entries behind. The current text says the index is derived and rebuildable, which is good, but it should define the steady-state repair pattern.

Concrete fix: add one of these explicit answers:

- Same-store due index: an indexed `jobs.next_fire_at` column or DB-backed due table, so create/update/cancel/fire changes are transactional.
- Separate derived index: write schedule changes to `JobDB`, update `TimeWheel` via CDC/outbox/relay, and make dispatcher validation lazy by checking `(job_id, scheduled_fire, schedule_version, next_fire_at, state)` in `JobDB` before firing. Stale index entries become harmless no-ops; missing entries are repaired by periodic reconciliation/rebuild.

### 2. Misfire and overlap policies are modeled but not yet wired into dispatch

The dataset now adds `misfire_policy` and `overlap_policy`, which is the right move. The dispatch step, however, still mostly describes the happy path: mark fire, advance `next_fire_at`, write outbox. It does not say how the dispatcher behaves when there are missed fires after downtime or when the previous run is still active.

For `misfire_policy=run_all_missed`, the dispatcher may need to enumerate many fire keys, not just the next one. For `run_one_catchup`, it should choose a representative missed fire and advance past the rest. For `overlap_policy=skip` or `queue_one`, the dispatcher needs to consult run state before writing the outbox, and it may need to record a skipped run rather than enqueue work.

Concrete fix: add a short "dispatch policy algorithm" to Step 5:

- Load current job row and validate the due index entry against `schedule_version`.
- Compute due fire keys according to `misfire_policy`.
- Check active run state according to `overlap_policy`.
- In one transaction, insert fire/run records as `queued` or `skipped`, advance `next_fire_at`, update/remove the due entry, and write outbox rows for queued runs.

### 3. The burst numbers need a timing-accuracy budget

The capacity section is much stronger, but the numbers create an interview-worthy tension that the design does not resolve. A top-of-hour burst of `~200k in a few sec` can mean tens of thousands of fires/sec. `~10k` worker slots at `~2s` per job process about `5k jobs/sec` before retry amplification. That can absorb the burst through backlog, but not necessarily preserve "seconds" timing accuracy.

Concrete fix: make the smoothing target explicit. For example, if `200k` top-of-hour jobs may be jittered over `60s`, the dispatch target is about `3.3k fires/sec`, which matches the worker pool. If they must all be triggered within `5s`, the system needs about `40k fires/sec` dispatch throughput and much more worker concurrency or a clear acceptance that execution lags while trigger records remain on time.

### 4. `JobDB` and `RunStore` ownership is ambiguous

The high-level architecture says `JobDB` stores "job definitions, schedules, and run state"; `RunStore` separately stores per-run records; the final design includes both `workers-runstore` and `workers-jobdb` with `workers-jobdb` labeled "report run status." The step text says workers only write run status, but it is unclear which store owns that state.

Concrete fix: pick one boundary and make the labels/data model match:

- Unified store: `JobDB` contains `jobs`, `runs`, `run_outbox`, and `leader_lease`; remove or rename `RunStore`.
- Split store: `JobDB` owns job definitions and schedule state; `RunStore` owns runs, attempts, claims, and outcomes; relabel `workers-jobdb` or remove it from final design unless workers really update job summary fields.

## System Design Soundness

The design has the right backbone for distributed cron: durable schedule store, time-ordered due lookup, per-shard leader election with fencing, fire-key dedup, transactional outbox, at-least-once queue, idempotent workers, claim leases, retries, and DLQ.

The most important correctness story is now present: the dispatcher advances recurring `next_fire_at` when claiming the fire, not after worker success. That preserves cron semantics and avoids turning recurring jobs into fixed-delay workflows. The fire identity also improved from `(job_id, scheduled_fire)` to `(job_id, scheduled_fire, schedule_version)`, which protects update/cancel races.

The remaining correctness questions are about coupling:

- If `TimeWheel` is separate from `JobDB`, how are stale and missing due entries detected and repaired?
- If overlap policy depends on run state, does the dispatcher transaction read/write the same store that workers use for active run claims?
- If the target system ignores the idempotency key, is that scoped as caller responsibility or does the scheduler provide a compensating mechanism?
- How long are fire keys, run records, and dedup records retained relative to retry delay, queue redelivery, and operator rerun windows?

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Cron Process on a Single Box

This step is now aligned with the text. The diagram shows `Client -> Cron Process (in-memory schedules)`, which cleanly motivates durability, availability, and scan-cost problems without prematurely showing the production API/store.

### Step 2: Durable Schedules

This is much stronger than before. It introduces the exact scheduler semantics the rest of the design relies on: `timezone`, `schedule_version`, misfire/catch-up, overlap policy, retry, timeout, and idempotent create/update.

The next improvement is to be explicit about cancellation semantics. Does cancel stop only future fires, also remove queued not-yet-started runs, or attempt to cancel an active worker lease? That can be a short note rather than a full step.

### Step 3: Finding Due Jobs Efficiently

The options are good and the text now explains mutable index entries and physical choices. The main issue is consistency across stores. If the default "time wheel" is Redis or in-memory, the design should teach lazy validation and reconciliation; otherwise candidates may believe schedule-store and due-index writes are magically atomic.

### Step 4: Leader Election to Avoid Duplicate Triggers

This is one of the strongest steps. It correctly teaches TTL leases, fencing tokens, stale leader rejection, and per-shard leaders. The text also now says the fencing token must be enforced at the fire-marker write, which is the right precision.

Useful polish: add one metric or operational note here, such as lease churn, fencing-token rejects, or failover gap, so the candidate can explain how to detect leader flapping.

### Step 5: Exactly-Once Triggering

This step has been substantially fixed. The transactional outbox is the default, the CAS shortcut is clearly scoped to a same-store queue, and the sequence now shows `poll due -> dedup tx -> relay enqueue`.

The remaining teaching gap is how policy affects the transaction. This is the right place to show how missed fires and overlap rules change which fire keys are inserted, skipped, or queued.

### Step 6: At-Least-Once Execution with Idempotency

The two-layer idempotency explanation is strong. It correctly states that a run-store claim does not protect external side effects unless the target honors the propagated idempotency key.

The step would be even better with a compact run state machine: `queued -> running(lease) -> succeeded | failed | dead | skipped`, plus `running -> queued` on lease expiry. That would connect claim leases, retries, DLQ, overlap policy, and status APIs.

### Step 7: Retries, Backoff, and Dead-Lettering

This step closes the execution lifecycle well. It now includes per-job retry policy, transient vs non-retryable errors, DLQ owner alerting, operator rerun, and bounded retries.

The useful addition is a little more cancellation/rerun detail: whether a rerun reuses the same fire key, creates a new manual run key, or records an operator action for audit.

## Final Design Review

The final design now matches the step progression much better. It includes `Outbox + Relay` and the caption accurately describes the one-transaction marker/advance/outbox commit followed by relay publish. The previous major final-design issue is resolved.

The final design should still clarify store ownership. Either `JobDB` is the broad durable database containing job and run tables, or `RunStore` is a separate run database. The current diagram has both, which is fine only if the labels make their roles distinct.

The final design could also show due-index reconciliation if `TimeWheel` is a separate derived system. A small `Rebuilder/Reconciler` node is optional, but a caption note may be enough.

## Concept Introduction and Learning Flow

The concept staging is now excellent for an interview walkthrough:

- Step 1 exposes why single-box cron is insufficient.
- Step 2 introduces schedule semantics and identity.
- Step 3 solves due lookup.
- Step 4 solves duplicate leaders.
- Step 5 solves crash-safe triggering.
- Step 6 separates dispatch guarantees from execution guarantees.
- Step 7 completes the failure lifecycle.

The only learning-flow adjustment is to explicitly connect policies introduced in Step 2 back to the Step 5 dispatcher transaction. That will prevent the policies from feeling like API/model fields that never affect the architecture.

## Step-to-Final-Design Coherence

The step-to-final mapping is mostly clean:

- `store` introduces `API` and `JobDB`.
- `due` introduces `TimeWheel`.
- `election` introduces `Dispatcher` and `Lease`.
- `dispatch` introduces `Outbox` and `RunQ`.
- `execute` introduces `Workers` and `RunStore`.
- `retry` introduces `Retry` and `DLQ`.

The main coherence issue is the final `workers-jobdb` link. If workers write run status to `RunStore`, that link should not say "report run status" to `JobDB`. If `JobDB` owns run state, the separate `RunStore` node should be explained as a logical table or removed.

## Realism Compared With Production Systems

The dataset is now realistic enough for senior/staff interview practice. It acknowledges the hard parts: DST, misfires, overlaps, update races, fire identity, outbox, target idempotency, worker leases, retry classes, DLQ remediation, and burst sizing.

Remaining production realism gaps:

- due-index repair/rebuild cadence and stale-entry validation;
- quota/rate-limit behavior per tenant and per target;
- authz/audit for create, update, pause, cancel, rerun, and DLQ operations;
- cancellation semantics for queued and running jobs;
- run history compaction versus dedup retention;
- alert thresholds for schedule lag, fire-to-enqueue latency, queue backlog, lease churn, retries, DLQ growth, and duplicate suppression.

These do not all need full steps. Most can be added as short notes in Step 2, Step 3, Step 5, and the final wrap-up.

## Dataset and Renderer-Facing Observations

The source file is healthy from a renderer perspective:

- `interview.json` parses as JSON.
- Global architecture links reference existing nodes.
- Step and final-design string node/link references resolve.
- `satisfies[*].steps[*]`, `patterns[*].steps[*]`, and `technologyChoices[*].steps[*]` references resolve.
- Top-level sections include requirements, capacity, API, data model, patterns, steps, final design, satisfies, technology choices, script, level variants, follow-ups, and probe links.
- No generated `docs/` changes are needed for this review because `REVIEW.md` is repo-only.

Minor observations:

- The `Target` participant appears in the Step 6 sequence without being a high-level architecture node. That is acceptable for a sequence-only external participant, but adding an `external` node could make the final design's target-idempotency story more visible.
- Several technology chips use the generic `assets/tech-icons/tech.png` fallback. That is not a rendering bug, but mapping the missing terms in `_media/index.yaml` would improve the visual polish of the Technology Choices entry.

## Recommended Edits, Prioritized

### P1: Define due-index consistency

State whether the due index is same-store transactional or a separate derived index. If separate, add lazy validation, CDC/outbox update, and periodic reconciliation/rebuild so stale and missing due entries are handled explicitly.

### P1: Wire misfire and overlap policies into dispatch

Add a compact algorithm in Step 5 showing how `misfire_policy` and `overlap_policy` affect fire-key generation, skipped run records, `next_fire_at` advancement, and outbox writes.

### P2: Reconcile burst capacity with timing accuracy

Explain the jitter/backlog budget for `~200k` top-of-hour jobs. Either size dispatch/workers for the desired seconds-level trigger window or state the accepted lag under bursts.

### P2: Clarify `JobDB` vs `RunStore`

Make the data model, high-level node descriptions, and final-design links agree on where run status, attempts, claims, and outcomes live.

### P2: Add cancellation and rerun semantics

Define what cancel does to future, queued, and active runs. Define whether operator rerun uses the same fire key or a manual rerun key, and how that is audited.

### P3: Improve operational and visual polish

Add a few scheduler-specific metric names to the relevant steps and replace generic `tech.png` fallback icons where better mappings exist.

## What Not To Change

- Keep the compact seven-step structure. It is easy to follow and each step solves a real problem exposed by the previous one.
- Keep transactional outbox as the default for a separate run queue.
- Keep the exact-trigger versus at-least-once-execution distinction prominent.
- Keep schedule versioning and dispatcher-owned `next_fire_at` advancement; those are important correctness upgrades.
- Keep DAGs, priorities, and richer workflow orchestration as follow-ups rather than expanding this into an Airflow-style workflow engine.

## Bottom Line

The recent changes moved this from a good walkthrough with major correctness caveats to a strong scheduler case. The next pass should focus on the remaining production gaps: due-index consistency, policy-aware dispatch, burst timing math, and clear store ownership.
