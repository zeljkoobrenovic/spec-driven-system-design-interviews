# Review: GPU Job Scheduler - System Design

Reviewed file: `data/book/gpu-scheduler/interview.json`
Review date: 2026-06-08

## Executive Summary

This review has been updated after the recent strengthening pass. The dataset is now materially better than the previous review described: capacity math is concrete, submission is idempotent, cancellation/status/log APIs exist, allocation and reservation state are modeled, checkpoint/event stores are visible, gang scheduling vs backfill is clearly separated, reliability uses leases/fencing, missing requirement mappings were added, and `technologyChoices` is present.

The interview is now a strong book case. Its remaining issues are not about the conceptual spine; they are about making the production contract precise enough for a real multi-tenant scheduler: resource-vector fairness, authoritative usage accounting, tenant/runtime security, reservation/backfill admission state, and explicit lifecycle/observability contracts.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | Core scheduler mechanisms are correct and now backed by durable state. The remaining gap is precision around multi-resource fairness and source-of-truth boundaries. |
| Production realism | 4/5 | Leases, events, checkpointing, and capacity math are strong. Security, image/runtime isolation, and operational SLOs need one more pass. |
| Pedagogical flow | 4.7/5 | Excellent staged progression with meaningful alternatives and realistic traps. |
| Step-to-final coherence | 4.6/5 | Recent edits make the final design line up with the steps much better. A few state-model relationships still need tightening. |
| Dataset/rendering fit | 4.7/5 | JSON and references are clean; no renderer blockers found. |

## What Works Well

- The recent pass resolved the old highest-impact gaps: capacity now translates jobs/day into submit bursts, scheduling-loop work, candidate scoring, heartbeats, pending depth, and checkpoint I/O.
- The API now carries the fields the architecture depends on: `Idempotency-Key`, image/command, gang constraints, retry policy, preemptibility, checkpoint config, and log sink.
- The data model now includes `allocations`, `reservations`, `job_attempts`, `job_events`, and `nodes`, so the final design's durable-state claim is credible.
- Gang scheduling is now taught correctly: all-or-nothing placement holds no partial GPUs, while backfill runs only around a future-start reservation.
- Reliability is much stronger: capacity is freed from authoritative agent status/events, not metrics; allocations carry leases, launch tokens, and scheduler epochs.
- The final design now includes `Checkpoints` and `Events`, which makes preemption, restart, status, and logs visible in the architecture.
- `satisfies` now covers cancellation/status/logs and low scheduling latency, so the wrap-up closes the loop on the stated requirements.
- The `technologyChoices` section is useful and domain-appropriate: Kubernetes plus Volcano/Kueue, Slurm, Ray, managed ML platforms, durable stores, queues, object stores, and leader-election choices are all relevant.

## Highest-Impact Issues

### 1. Dominant-resource fairness is claimed, but the resource vector is still mostly GPU-count based

Step 5 explains dominant-resource fairness and mentions GPU count, GPU memory, CPU/RAM, and scarce GPU type. The persisted quota model is still mostly `guaranteed_gpus`, `max_gpus`, `used_gpus`, `usage_window`, and `weight`; the job request has `gpus`, `gpuType`, and `memGB`, but no CPU, RAM, local storage, network, runtime, or per-GPU-type quota vector.

Why it matters: the interview says fairness is based on the dominant share, but the data model cannot compute a true dominant share across heterogeneous bottlenecks. A team using scarce H100s, large GPU memory slices, or heavy CPU/RAM sidecars should not be compared only by GPU count.

Concrete fix:

- Add a `resources` object to the job spec: GPU count/type/profile, GPU memory, CPU, RAM, ephemeral/local storage, network tier, and maybe accelerator family.
- Extend `quotas` or add `quota_allocations` with guarantees, burst ceilings, and rolling usage per resource class.
- Define scarcity normalization: one A100/H100 may count differently from one T4/L4; MIG slices need their own accounting.
- If that is too much for the case, narrow the text to "GPU-dominant fair-share" instead of full dominant-resource fairness.

### 2. Fair-share accounting still appears to depend on Metrics

The reliability step correctly says metrics must not be authoritative for freeing GPUs. But the fairness step and final diagram still route `Metrics -> Quota` as "usage for fair-share." That is plausible for utilization signals, but risky as the primary accounting source.

Why it matters: quota/fair-share should be computed from durable allocation intervals, attempt records, and agent status events. Raw metrics can lag, drop samples, be spoofed by broken agents, or show low GPU utilization for a job that still owns capacity.

Concrete fix:

- Clarify that billable usage comes from `allocations`, `job_attempts`, and `job_events`, while metrics enrich health/utilization decisions.
- Add a `JobDB/Events -> Quota` link or adjust the existing `Metrics -> Quota` label to "utilization signal, not authority."
- Store allocation start/end times and resource vector on `job_attempts` or a usage ledger.
- Add a failure drill for missing metrics while an allocation lease is still valid.

### 3. Multi-tenant execution security is under-modeled

The scheduler runs arbitrary team images on shared GPU nodes. The API includes `image`, `command`, and `logSink`, and the final design has a registry, checkpoint store, and event/log store, but there is no tenant isolation contract.

Why it matters: in production, the scheduler is also an admission and isolation system. Without explicit rules, a team can request privileged containers, exfiltrate another team's checkpoint/logs, mount secrets incorrectly, or bypass quota through side effects.

Concrete fix:

- Add submit fields or notes for `serviceAccount`, secrets, image-pull identity, namespace/project, and allowed network policy.
- Add image admission controls: signed images, allowed registries, vulnerability policy, and runtime class/security context.
- Make checkpoint/log ACLs tenant-scoped; a `logSink` or checkpoint URI should not be arbitrary write access unless the API validates ownership.
- Mention node-level isolation choices: MIG, exclusive GPU allocation, taints/drains, and whether mixed tenants can share a node.

### 4. Reservation and backfill are conceptually correct but need admission state

The Step 4 rewrite is a major improvement. The remaining gap is that the `reservations` table has `planned_start`, but not enough information to enforce safe backfill or explain what happens when estimates are wrong.

Why it matters: backfill is only safe if the scheduler can prove the smaller job will finish before the large gang's planned start, or can preempt/drain it without violating the reservation. Otherwise the "reservation" becomes only advisory and large gangs can still starve.

Concrete fix:

- Store a reservation expiry/deadline, topology/resource shape, and the reason the planned start was chosen.
- Track the backfill admission predicate: job walltime, remaining time, preemptibility, and latest finish time.
- Add a failure behavior for missed walltime: kill/requeue, checkpoint, or charge a penalty.
- Tighten the default option's con "reserved-but-unused briefly while the full set is assembled" so it does not sound like partial GPU holding.

### 5. Lifecycle state is present, but transitions and operational SLOs are implicit

The dataset now has job states, attempts, events, leases, and cancellation. It still lacks a compact state-transition contract and the operational SLOs that would make reconciliation testable.

Why it matters: retries, cancellation, preemption, lease expiry, node loss, and scheduler restart all mutate overlapping state. Without valid transitions and timing targets, it is hard to reason about idempotent agent updates or stale scheduler writes.

Concrete fix:

- Add a lifecycle table or diagram: pending -> scheduled -> running -> succeeded/failed/cancelled/preempted -> pending retry/resume.
- Tie `allocations` to `job_attempts` with an `attempt_id`; clarify whether `jobs.placement` and `gpus.allocated_to` are authoritative or cached projections from `allocations`.
- Add SLO-style targets: scheduling p95, maximum reconcile lag, lease renewal cadence, node failure detection time, checkpoint drain bound.
- Add observability counters: stale leases, duplicate launch-token rejections, queue wait by team/priority, fragmentation, checkpoint duration, preemption success/failure.

## System Design Soundness

The current design is sound. It covers the right GPU-scheduler problems: scarce expensive hardware, heterogeneous placement, gang scheduling, fair-share, preemption, checkpointing, and crash recovery.

The capacity section is now one of the stronger parts of the dataset. It correctly shows that 10K jobs/day is not an API QPS problem; the harder work is queue depth, placement scoring, heartbeats, and checkpoint I/O. The 1K-10K GPU / 125-1,250 node framing gives the reader enough scale to defend a single scheduler loop before discussing sharding.

The API shape is also much stronger. `POST /v1/jobs` now carries the fields needed later in the design, and `GET /jobs/{id}/events` plus `DELETE /jobs/{id}` make the lifecycle requirement concrete. The next improvement is to group resource fields under a richer `resources` object and to add security/admission fields.

The data model has moved from conceptual to implementable. The important remaining source-of-truth question is how `jobs.placement`, `gpus.allocated_to`, and `allocations.gpu_ids` relate. The review should push the dataset to make `allocations` authoritative and treat the other fields as cached views, or remove the duplicates.

## Step-by-Step Pedagogical Review

### Step 1: Naive FIFO

Good baseline. It is still worth preserving because it exposes why GPU scheduling is harder than "queue plus free node."

Improvement: keep the current trap, and optionally add one sentence that FIFO is acceptable only for a tiny single-team lab cluster. That helps justify the complexity that follows.

### Step 2: Accept and Queue Jobs by Priority

This step is now strong. Idempotent submission, durable-before-enqueue ordering, stale queue references, and cancellation are all covered. The flow is useful and interview-realistic.

Improvement: mention idempotency-key retention and collision scope. For example, a key should be scoped to tenant/client and expire after a retention window, not be globally permanent forever.

### Step 3: Place Jobs: Bin-Packing onto GPUs

The pack/spread/topology trade-off is strong, and the capacity section now supports indexed free-lists instead of full scans.

Improvement: make the resource manager's index shape match the richer resource model: GPU type/profile, memory, topology domain, health, drain state, image/runtime compatibility, and optionally CPU/RAM.

### Step 4: Gang Scheduling for Distributed Jobs

This is now one of the best sections. The all-or-nothing vs partial-hold distinction is clear, and the backfill definition is correct.

Improvement: make backfill enforceability explicit. Tie safe backfill to walltime estimates, preemptibility, and a reservation deadline. Also clean up the small wording that implies GPUs may be reserved while "assembled."

### Step 5: Fairness and Quotas Across Teams

The fair-share score sketch is a useful teaching addition. It makes the section more concrete than most scheduler interview outlines.

Improvement: align the fairness formula, quota table, and metrics path. If fairness is dominant-resource fairness, persist the resource vector and compute usage from allocation/event state rather than raw metrics.

### Step 6: Preemption with Checkpointing

This step is much better after the recent changes. It now covers preemptible eligibility, grace windows, checkpoint I/O cost, victim selection, anti-thrashing, and max preemptions.

Improvement: persist the checkpoint policy, not just the last `checkpoint_uri`. The data model should retain whether checkpointing is enabled, interval, grace target, resume command/args if needed, and the last checkpoint status.

### Step 7: Reliability: Reconciliation and Failure Recovery

This is now production-realistic. It names the key failure-mode controls: authoritative agent status, durable desired state, leases, launch tokens, scheduler epoch fencing, leader election, and failure detection.

Improvement: add a compact transition/state table and a drill for split-brain or missing agent heartbeats with a valid lease. That would make the reliability story testable rather than only descriptive.

## Final Design Review

The final design now earns its claim. It integrates durable submission, priority queues, constrained placement, all-or-nothing gang scheduling, future-start reservations, backfill, fair-share, checkpointing, authoritative agent status, event/log storage, and leased epoch-fenced allocations.

The remaining refinements are precision issues:

- Make `allocations` the clear source of truth for ownership.
- Route quota accounting through allocation/attempt/event state, with metrics as an advisory signal.
- Add tenant security and admission controls around images, credentials, logs, and checkpoints.
- Make reservation/backfill and lifecycle transitions explicit enough to test.

## Concept Introduction and Learning Flow

Concept staging is excellent. The reader gets priority queues before placement, placement before gang scheduling, fairness before preemption, and preemption before reconciliation. The new concepts are introduced close to the moment they are needed.

The best next teaching improvement is one worked example. A compact example could show a 64-GPU gang blocked behind smaller jobs, the future reservation time, two eligible backfill jobs, and a fair-share score shift when another team returns. That would make the fairness/backfill/preemption interactions easier to remember.

## Step-to-Final-Design Coherence

Recent edits fixed most old coherence gaps:

- Step 2 now backs the API and queue with idempotent durable state.
- Step 3 now connects to indexed free-list placement.
- Step 4 now connects to explicit `reservations`.
- Step 5 now has a concrete fair-share score and quota usage window.
- Step 6 now connects to `Checkpoints`, `job_attempts`, and anti-thrashing fields.
- Step 7 now connects to `allocations`, leases, events, and fencing.

The remaining coherence work is to connect these state tables to each other more explicitly: `allocations` to `job_attempts`, reservation/backfill admission to `walltime`, and quota usage to allocation intervals.

## Realism Compared With Production Systems

The case now feels close to production. It avoids the common shallow answer of "use Kubernetes and a queue" and instead explains the scheduler mechanics.

Remaining realism gaps:

- Image pulling and startup latency can dominate scheduling latency; the registry is present, but image cache/warmup behavior is not discussed.
- Tenant isolation is mostly absent: signed images, runtime security, secrets, network policy, per-team object-store ACLs, and service accounts.
- Fairness and billing should use durable allocation accounting, not raw metrics.
- Operational observability should include queue wait, scheduler decisions/sec, fragmentation, stale leases, checkpoint drain time, failed launches, preemption outcomes, and reconciliation lag.
- The `toProbeFurther` links are solid, but a Slurm reference would fit the new `technologyChoices` section because Slurm is one of the strongest real-world backfill/fair-share schedulers.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level keys include the expected book fields: `patterns`, `technologyChoices`, `interviewScript`, `levelVariants`, `followUps`, and `satisfies`.
- Main step `view.nodes` and `view.links` references resolve.
- Option view string links resolve. The option-local nodes `Topo` and `Reservation` are inline nodes, not missing high-level nodes.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.
- `satisfies[*].steps[*]` references resolve.
- `probeLinks` resolve to `toProbeFurther.links`.
- Dataset-level `patterns` and `step.patterns` are consistent.
- No generated `docs/` changes are needed for this review file alone.

## Recommended Edits, Prioritized

### P1: Align fairness with a real resource vector

Add persisted resource-vector fields for jobs, quotas, and usage accounting, or narrow the wording to GPU-count/GPU-type fair-share.

### P1: Clarify authoritative usage accounting

Route quota/fair-share usage through allocation/attempt/event state, with metrics only as an advisory utilization and health signal.

### P1: Add tenant security/admission controls

Cover image trust, service accounts, secrets, network isolation, checkpoint/log ACLs, and per-team access boundaries.

### P2: Make lifecycle transitions explicit

Add a compact state-transition table and tie `allocations` to `job_attempts`; clarify which duplicate placement fields are projections.

### P2: Make backfill/reservation enforceable

Add reservation deadlines, backfill latest-finish checks, and behavior for walltime misses.

### P2: Add operational SLOs and dashboards

Define scheduling latency, reconcile lag, lease cadence, node failure detection, checkpoint drain bounds, and key control-plane metrics.

### P3: Add one worked scenario

Use one large-gang/backfill/fair-share example to connect capacity, placement, quotas, and preemption.

### P3: Add a Slurm/backfill reference

The new technology section names Slurm; a probe link for Slurm fair-share/backfill would help readers compare HPC and Kubernetes-native approaches.

## What Not To Change

- Keep the FIFO baseline; it is the right teaching anchor.
- Keep DB-as-source-of-truth queueing as the default option.
- Keep best-fit packing as the default, with topology-aware placement as the senior/staff extension.
- Keep all-or-nothing gang scheduling and the rejected partial-reservation alternative.
- Keep reclaimable borrowing for fairness; hard quotas are correctly framed as simpler but wasteful.
- Keep checkpoint-and-requeue as the preemption default.
- Keep reconciliation plus leases/fencing as the reliability capstone.

## Bottom Line

The recent changes moved this from a good conceptual walkthrough to a strong, mostly production-realistic scheduler case. The remaining work is a precision pass: multi-resource fairness, authoritative accounting, tenant security, explicit lifecycle transitions, and enforceable reservation/backfill state.
