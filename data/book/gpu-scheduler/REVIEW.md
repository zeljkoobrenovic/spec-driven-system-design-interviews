# Review: GPU Job Scheduler - System Design

Reviewed file: `data/book/gpu-scheduler/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a strong system design walkthrough. The step order is coherent: FIFO baseline, durable queueing, bin-packing, gang scheduling, fairness, preemption, then reconciliation. The case teaches the core GPU-cluster ideas in a way that a candidate can build up during an interview.

The main weakness is production specificity. The design names the right mechanisms, but it often stops before the concrete state, API fields, capacity math, and failure-mode contracts needed to make those mechanisms implementable. The highest-impact fixes are to quantify scheduling workload, add allocation/reservation/checkpoint state, clarify gang/backfill semantics, and map every requirement to an explicit API or architecture mechanism.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Correct core scheduler concepts; needs richer operational state and clearer authority boundaries. |
| Production realism | 3.5/5 | Good failures and preemption framing; missing leases, checkpoint storage, topology inventory, logs, and idempotency. |
| Pedagogical flow | 4.5/5 | Excellent staged progression with non-strawman options. |
| Step-to-final coherence | 4/5 | Final design integrates the steps, but claims durable allocation/checkpoint behavior not fully modeled earlier. |
| Dataset/rendering fit | 4.5/5 | JSON and cross-references are clean; no obvious renderer blockers found. |

## What Works Well

- The walkthrough exposes one problem at a time. The naive FIFO step motivates each later addition instead of dumping the final architecture up front.
- The options are meaningful trade-offs: DB-as-source-of-truth vs queue-as-source-of-truth, best-fit vs spread vs topology-aware placement, fair-share borrowing vs hard quotas, checkpoint-and-requeue vs kill-and-restart.
- The gang scheduling section correctly highlights partial-allocation deadlock, which is the central distributed-training scheduling trap.
- Fairness and preemption are connected: bursting is allowed, but reclaiming borrowed capacity requires eviction.
- The final design includes the key components introduced in the steps: API, job store, queues, scheduler, resource manager, quota service, preemption controller, agents, nodes, registry, and telemetry.
- Dataset-level checks are healthy: `satisfies[*].steps[*]` resolve, step and option `view.links` resolve, final-design links resolve, `probeLinks` resolve, and pattern references are consistent.

## Highest-Impact Issues

### 1. Capacity does not become scheduling math

The capacity section gives useful scale hints - thousands of GPUs, 10K+ jobs/day, largest jobs in the hundreds of GPUs - but it does not translate those into design-driving numbers. The scheduler workload is probably not submit QPS-bound: 10K jobs/day is only about 0.12 average submits/sec, while bursts, queue scans, placement scoring, heartbeats, retries, and checkpoint writes dominate.

Why it matters: without this math, the reader cannot tell whether one scheduler loop is fine, when to shard by pool, how often agents heartbeat, how large the pending queue can get, or what telemetry/cardinality load the system creates.

Concrete fix:

- Convert GPUs to approximate nodes: e.g. 1K to 10K GPUs at 8 GPUs/node means about 125 to 1,250 nodes.
- Add expected burst submit rate, pending queue size, and scheduling decisions/sec.
- Estimate placement work: candidates scored per job, topology-aware scoring cost, and whether the scheduler can scan all nodes or needs indexed free lists.
- Estimate heartbeat volume: node or GPU heartbeat cadence times node count.
- Add checkpoint I/O scale: model checkpoints can be tens to hundreds of GB, so preemption is storage-bandwidth constrained, not just scheduler-controlled.

### 2. API and data model do not yet support the behavior the design promises

The API covers submit, get status, and cancel, but the job contract is too thin for the later architecture. It lacks idempotency, command/entrypoint details, retry policy, checkpoint configuration, topology/MIG constraints, node selectors, image pull policy, secrets, log location, and explicit preemptibility. The data model has `jobs`, `gpus`, and `quotas`, but no allocations/reservations, attempts, job events, node inventory, topology domains, checkpoint pointers, preemption counters, or scheduler lease/fencing fields.

Why it matters: the final design promises durable allocation state, lifecycle retry, checkpoint-and-requeue, cancellation, status/logs, and crash-tolerant reconciliation. Those require first-class state, not just a `placement` list on `jobs` and `allocated_to` on `gpus`.

Concrete fix:

- Add `idempotencyKey`, `retryPolicy`, `checkpoint`, `constraints`, `gang`, `maxPreemptions`, and `logSink` fields to `POST /v1/jobs`.
- Add tables such as `allocations`, `reservations`, `job_attempts`, `job_events`, `nodes`, `gpu_inventory`, and `checkpoints`.
- Track `scheduler_epoch` or lease owner on allocations so a restarted or partitioned scheduler cannot double-act.
- Store checkpoint URI, checkpoint status, last successful checkpoint time, and resume parameters.

### 3. Gang scheduling and backfill semantics are blurred

The default gang option says the scheduler acquires all GPUs atomically or holds none. That is correct. But the same section also says to "reserve capacity for the head-of-line gang" and the flow says "reserve for gang; backfill small jobs into gaps." The alternative says smaller jobs can backfill "held capacity until the gang is complete," which is contradictory: if GPUs are held by a partial gang, they are not available for backfill.

Why it matters: this distinction is central in production batch schedulers. Partial allocation wastes GPUs and can deadlock. Backfill works when the scheduler reserves a future start condition or priority position for the large job, then runs smaller jobs that can finish before the large job would be delayed.

Concrete fix:

- Keep the default as all-or-nothing, holding no GPUs until the full gang can start.
- Define backfill as running bounded small jobs around a planned reservation/start time, not on already-held partial GPUs.
- Rename the alternative to "Partial reservation with timeout" and make it clearly a rejected or risky option.
- Add a flow branch for "large gang blocked; run small backfill job only if it does not delay the gang."

### 4. Reconciliation needs leases, fencing, and an authoritative status path

Step 7 correctly introduces reconciliation, but the mechanism is underspecified. The architecture link `metrics-res` labels telemetry as "free-on-completion"; that makes metrics look authoritative for freeing GPUs. Metrics should observe. The resource manager should free capacity from agent status events, durable job/attempt state, and reconciliation guarded by leases/fencing.

Why it matters: freeing GPUs from a metrics signal risks double-running jobs or marking slow/partitioned nodes as free. Reconciliation needs to answer who owns an allocation, which scheduler epoch made the decision, whether the agent accepted the launch, and when a lease expired.

Concrete fix:

- Add an explicit agent status/event path to the resource manager or job store.
- Add allocation leases with expiry, scheduler epoch, node-agent acknowledgement, and idempotent launch tokens.
- Clarify leader election and fencing for the scheduler, not just "hot-standby with leader election" in bottlenecks.
- Add a recovery flow for scheduler restart and node failure.

### 5. The requirements mapping misses visible requirements

The functional requirements include cancellation and status/log reporting, but `satisfies.functional` does not map that requirement. The non-functional requirements include scheduling latency, but `satisfies.nonFunctional` does not map it either.

Why it matters: the wrap-up is where readers check that the design closed the loop. Missing mappings make implemented requirements look accidental or unsupported.

Concrete fix:

- Add a `satisfies.functional` item for cancellation/status/logs, linked to queueing, preemption, and reliability.
- Add a logs/status mechanism: job events, log sink, and an agent-to-store/status path.
- Add a `satisfies.nonFunctional` item for scheduling latency, linked to queueing, placement, and reliability.

## System Design Soundness

The requirements are well-scoped for an interview. They avoid unnecessary product breadth and focus on the scheduler problems that matter: scarce hardware, multi-dimensional constraints, gang placement, tenant fairness, preemption, and recovery.

The weakest design area is the boundary between scheduling decisions and authoritative state. `JobDB` is called authoritative for jobs, `ResManager` tracks capacity, and `Metrics` feeds usage and health. That split is plausible, but the design should state which component is authoritative for allocation lifecycle and completion. Metrics should not be the source of truth for freeing GPUs.

The resource model also needs more GPU-specific detail. `gpu_type` and `mem_gb` are a good start, but real placement needs node topology, GPU interconnect domain, MIG profile or partition, health, driver/runtime compatibility, taints/drains, and possibly local storage/network constraints. Some of this can remain a follow-up, but the data model should at least make room for it.

Fairness is directionally correct but too abstract for "dominant-resource fairness." The design should define the resources that dominate - GPU count, GPU type scarcity, GPU memory, maybe CPU/RAM - and whether fairness is based on live usage, rolling historical usage, or guarantees plus borrowing.

## Step-by-Step Pedagogical Review

### Step 1: Naive FIFO

Strong baseline. It clearly motivates priority, fairness, bin-packing, gang scheduling, and preemption. Keep this step.

Improvement: mention that FIFO can still be acceptable for a tiny single-team lab cluster, which helps frame why the complexity is justified only at shared-cluster scale.

### Step 2: Accept and Queue Jobs by Priority

The DB-as-source-of-truth default is the right teaching choice. The queue-as-source-of-truth option is a useful contrast.

Improvement: add idempotent submission and cancellation semantics here. A production `POST /jobs` should survive client retry without duplicate jobs, and a cancelled queued job should be skipped by the scheduler even if its queue reference remains.

### Step 3: Bin-Packing Placement

The pack/spread/topology trade-off is excellent. Best-fit as the default is defensible for expensive GPUs, and the topology-aware option is a good senior/staff extension.

Improvement: define what the resource manager indexes. For example, free GPUs by type, memory, node, topology domain, and health. This avoids making placement sound like a full cluster scan on every scheduling decision.

### Step 4: Gang Scheduling

This is one of the strongest conceptual steps, but it needs the backfill clarification described above. "All or nothing" and "partial reservation" should remain distinct, because confusing them teaches the wrong failure mode.

Improvement: explain head-of-line blocking and backfill with job runtime estimates or walltime limits. Backfill is only safe when the small job will not delay the reserved gang.

### Step 5: Fairness and Quotas

The reclaimable-bursting model is a good default. It connects directly to preemption in the next step.

Improvement: define fair-share scoring more concretely: priority class, team weight/guarantee, rolling usage window, dominant resource share, age, and starvation boost. Also state what happens when a team lies about walltime or resource size.

### Step 6: Preemption with Checkpointing

The checkpoint-and-requeue default is right, and the kill-and-restart option shows why checkpointing matters.

Improvement: add checkpoint storage and job contract details. Preemption cannot be assumed safe unless the job advertises checkpointability, the controller enforces a grace period, checkpoint I/O is bounded, and repeated preemption is throttled.

### Step 7: Reliability

The reconciliation framing is correct and ties the system together well.

Improvement: add a sequence flow for restart recovery. Show scheduler leader election, loading desired state from `JobDB`, reconciling allocations from `ResManager` and agents, and fencing stale scheduler epochs.

## Final Design Review

The final design is coherent and mostly earns its summary. It includes every major control-plane component and makes the right claim: scheduling state should be durable and re-derived through reconciliation.

The final design currently overclaims in two places:

- "Durable job and allocation state" is not backed by an allocation/reservation data model.
- "Checkpoint + requeue" is not backed by a checkpoint store, checkpoint pointer, or job contract.

Add those components and fields, and the final design will match the earlier steps much more tightly. A small diagram addition for `Checkpoint Store` and `Log/Event Store` would also make cancellation/status/logs visible.

## Concept Introduction and Learning Flow

Concept staging is strong. The concepts appear close to where they are used: bin-packing in placement, gang scheduling/backfill in distributed jobs, fair-share in tenancy, checkpoint-and-requeue in preemption, and reconciliation in recovery.

The main learning-flow improvement is to add one or two concrete formulas or state snippets. For example, a fair-share score example and an allocation lease example would make the abstract mechanisms memorable without bloating the walkthrough.

## Step-to-Final-Design Coherence

Each step introduces a component that appears in the final diagram, which is good. The coherence gaps are mostly missing state:

- Step 2 introduces durable job submission, but not idempotency or event history.
- Step 3 introduces placement, but not allocation leases or topology inventory.
- Step 4 introduces gang scheduling, but not reservation state.
- Step 5 introduces fairness, but not the usage-window state needed to compute it.
- Step 6 introduces checkpointing, but not checkpoint storage.
- Step 7 introduces reconciliation, but not scheduler fencing or authoritative completion events.

Filling those state gaps would make the final design feel production-ready instead of just conceptually correct.

## Realism Compared With Production Systems

The case is realistic in its choice of topics. GPU schedulers really do revolve around fragmentation, gang scheduling, fairness, preemption cost, and reconciliation.

The missing realism is mostly operational:

- Image pulling can dominate startup time. The registry is present, but there is no image cache, pull failure path, or warmup discussion.
- Logs/status are a requirement, but no log/event pipeline is modeled.
- Security and tenant isolation are absent: image trust, secrets, service accounts, network isolation, and quota enforcement abuse cases.
- GPU health and draining need explicit state. A node can be up while one GPU is unhealthy.
- Checkpoint storage and bandwidth should be modeled, since preemption depends on it.
- Autoscaling is listed as a follow-up, which is fine, but the capacity math should still show whether the control plane can handle the static cluster.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Main step `view.nodes` and `view.links` references resolve.
- Option view string links resolve, and inline endpoints for `Topo` and `Reservation` resolve inside their views.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.
- `satisfies[*].steps[*]` references resolve.
- `probeLinks` references resolve to `toProbeFurther.links`.
- Dataset-level `patterns` and `step.patterns` are consistent.
- The `highLevelArchitecture.types` entries `control-plane` and `data-plane` are present and match view group references.
- No generated `docs/` changes are needed for this review file alone.

## Recommended Edits, Prioritized

### P1: Add operational state needed by finalDesign

Add allocation/reservation/attempt/event/checkpoint tables and update final design text to reference them.

### P1: Clarify gang scheduling vs backfill

Rewrite the Step 4 default and alternative so all-or-nothing allocation, future reservation, backfill, and partial holds are not mixed together.

### P1: Map missing requirements

Add `satisfies` entries and visible mechanisms for cancellation, status/logs, and scheduling latency.

### P2: Expand capacity math

Turn the scale labels into scheduling-loop, heartbeat, queue, placement, telemetry, and checkpoint-I/O estimates.

### P2: Make fairness computable

Add a fair-share score sketch and the state needed to compute rolling usage or dominant-resource share.

### P2: Make preemption implementable

Add checkpoint store, checkpoint contract, grace windows, victim selection state, and anti-thrashing rules.

### P3: Add technology choices

This book dataset would benefit from a `technologyChoices` wrap-up comparing Kubernetes plus Volcano/Kueue, Slurm, Ray, Nomad, custom scheduler, and managed cloud ML platforms.

### P3: Add more flows

Add sequence flows for submission idempotency/cancellation and scheduler restart recovery.

## What Not To Change

- Keep the FIFO baseline. It is a useful teaching anchor.
- Keep best-fit as the default placement choice, with topology-aware scoring as an advanced option.
- Keep all-or-nothing gang scheduling as the default.
- Keep reclaimable borrowing for fairness; hard quotas are correctly presented as simpler but wasteful.
- Keep checkpoint-and-requeue as the preemption default.

## Bottom Line

This is a strong interview dataset with the right conceptual spine. It needs a production-state pass: capacity math, allocation/reservation state, checkpoint/log/event plumbing, explicit leases/fencing, and clearer gang/backfill semantics. After those edits, it would be one of the stronger book cases because the pedagogical sequencing is already in good shape.
