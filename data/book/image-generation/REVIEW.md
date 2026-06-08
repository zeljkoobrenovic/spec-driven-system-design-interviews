# Review: Image Generation Platform - System Design

Reviewed file: `data/book/image-generation/interview.json`
Review date: 2026-06-08

## Executive Summary

This revision is a strong book-group interview case. The recent changes close
the biggest gaps from the previous review: capacity is now numeric, the API has
idempotency and webhook registration, the data model includes attempts,
dedupe, generated-image metadata, safety audit state, webhook delivery state,
and richer quotas, and `technologyChoices` now covers the edge/quota layer,
job state and outbox, dispatch queues, GPU serving and orchestration, model
rollout, result delivery, safety, notifications, and observability.

The learning spine is coherent: synchronous generation fails, so the candidate
moves to async intake, input/output safety, tier-aware scheduling, batched GPU
inference, CDN-backed result delivery, and retryable GPU jobs. The final
design now includes a concrete worked example, which makes the case much more
defensible in an interview.

The remaining issues are no longer about missing major components. They are
about sharpening production invariants: aligning peak capacity math with
admission/backlog policy, making the DB-to-queue/outbox boundary explicit,
promoting model-version lifecycle from follow-up to first-class state, and
making Step 7 easier to teach without compressing too many operations topics
into one closing step.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.5 / 5 | Strong architecture, numeric workload, and richer state; peak handling and model lifecycle need tighter contracts. |
| Production realism | 4.3 / 5 | Attempts, leases, safety audit, signed URLs, and webhooks are now present; outbox and rollout semantics remain under-specified. |
| Pedagogical flow | 4.6 / 5 | Clear step sequence and good option sets; Step 7 is dense and could use a more explicit operational checklist. |
| Final design coherence | 4.6 / 5 | Final design integrates the steps and includes a worked example; a few source-of-truth boundaries should be made visible. |
| Dataset/rendering fit | 4.8 / 5 | JSON parses; step, option, final-design, satisfies, probe-link, pattern, and technology-choice references are clean. |

Recommendation: keep the architecture and step order. The next pass should
focus on the remaining production edges, not another broad rewrite.

## What Works Well

- The capacity section now gives a concrete workload: about 2M images/day,
  1M requests/day, average `n` near 2, tier mix, peak submit QPS, seconds per
  image, batched images/sec/GPU, queue waits by tier, storage, and CDN egress.
- The API now exposes the right contracts for this domain: `Idempotency-Key`,
  request fingerprint dedupe, optional `callbackUrl`, owner-authorized status
  fetches, status reason, timestamps, model version, per-image metadata, and
  short-lived signed CDN URLs.
- The data model is much stronger. `jobs`, `job_attempts`,
  `idempotency_keys`, `generated_images`, `safety_decisions`,
  `webhook_deliveries`, and `quotas` support the lifecycle promised by the
  prose.
- Scheduling is no longer just a conceptual box. Step 4 names inputs,
  GPU-seconds/normalized-cost accounting, per-tier weights, per-user caps,
  leases, heartbeats, visibility timeouts, and fencing tokens.
- Step 5 teaches the core GPU-economics lever well: dynamic batching with a
  fill window, compatibility keys, memory caps, OOM splitting, warm model
  caches, and output safety after inference.
- Safety is correctly bookended and now includes blocked input/output states,
  classifier/policy versions, audit records, uncertain/manual-review outcomes,
  abuse telemetry, and fail-closed behavior.
- Delivery is realistic: push/stream is treated as a hint backed by durable
  status replay, webhooks have signing/retry/idempotency, and CDN URLs are
  scoped and expiring.
- `technologyChoices` is now present and useful for this case. It covers ten
  areas that materially affect cost and operability for GPU platforms.

## Highest-Impact Issues

### 1. Peak capacity math needs an explicit admission/backlog policy

The capacity section says the average is about 24 images/sec and a batched GPU
does about 1.6 images/sec, which supports the stated steady-state estimate of
about 21 GPUs at 70% utilization. It also says peak submit QPS is about
200 submits/sec and traffic can burst 5-10x the mean. With `n` near 2, that
peak could imply hundreds of images/sec, far above the 21-GPU steady fleet and
also above the "100+ for peaks" shorthand unless much of that work queues.

Why it matters: this is the central trade-off for the interview. The candidate
must know whether the system is provisioned for peak, queues non-realtime work,
sheds free-tier work, or enforces admission limits.

Concrete fix:

- Reconcile `peak submit QPS` and `images/sec` in one line, including `n`.
- State the intended provisioning policy: steady-state fleet plus burst pool,
  reserved realtime/paid slice, and free-tier backlog.
- Add a short example: "At 200 submits/sec with `n=2`, incoming work is about
  400 images/sec; with 1.6 images/sec/GPU and 70% utilization, serving all of
  it immediately would require about 357 GPUs. We instead reserve X GPUs for
  realtime/paid and let free-tier queue or shed."
- Tie p95 wait targets to admission control: realtime under 2s, paid under
  30s, free best-effort with ETA or throttling.

### 2. DB-to-queue durability is mentioned, but not visible as a design invariant

Step 2 has a good trap about publishing to the queue outside the DB
transaction, and the prose mentions transactional outbox or a re-enqueue
sweeper. The API sequence and data model still make the source-of-truth
boundary a little implicit: `jobs` is authoritative, `Queues` is operational,
and the bridge between them is the failure-prone part.

Why it matters: duplicate or missing queue messages are a common failure mode
for async job systems. This platform cannot lose a paid GPU job after returning
`202`, and it cannot accidentally run duplicate expensive generations.

Concrete fix:

- Add `outbox_events` or `queue_dispatches` to the data model, or explicitly
  state that `jobs(status=queued)` is periodically reconciled into the queue.
- In Step 2, name the invariant: every accepted job has exactly one durable job
  record and at least one recoverable path into scheduling.
- Clarify retry behavior when the API writes `jobs` but crashes before queue
  publish.
- Clarify whether the queue message contains only `job_id` or a denormalized
  payload. Prefer `job_id` plus fetch from JobDB for source-of-truth semantics.

### 3. Model lifecycle is still mostly a follow-up despite being central to batching

The dataset now stores `model_version`, compatibility keys include model and
version, and workers load weights from `ModelStore`. That is good. But model
catalog, rollout, canarying, rollback, and worker-pool pinning are still mostly
deferred to follow-ups.

Why it matters: image-generation platforms are not just one static model.
Serving cost, safety behavior, prompt compatibility, batch compatibility, and
result reproducibility all depend on model versioning.

Concrete fix:

- Add a compact `model_versions` entity with version, model family, status
  (`active`, `canary`, `deprecated`), safety policy compatibility, artifact
  path, and default rollout percentage.
- Mention worker pools pinned by hot model/version/size combinations.
- Clarify when `model_version` is pinned: at submit, at scheduling, or at first
  execution. Pinning at submit is simpler for reproducibility.
- Add a failure drill: canary model increases blocked-output rate or OOM rate;
  rollback should stop new scheduling while preserving existing job semantics.

### 4. Step 7 carries too many operational concerns at once

Step 7 covers leases, idempotent retry, dead-lettering, autoscaling, warm
pools, spot/preemptible capacity, queue age, batch fill, OOMs, model cache hit
rate, retries, blocked outputs, and cost attribution. These are all relevant,
but the step is dense compared with the earlier steps.

Why it matters: the case is pedagogically strong because each prior step
introduces one problem at a time. The final operations step risks becoming a
list of correct facts rather than a guided decision.

Concrete fix:

- Split Step 7 into two subsections in the prose: "Crash-safe execution" and
  "Fleet utilization/cost".
- Add a small operations checklist or table with signal, action, and owner:
  queue age by tier -> scale/preempt free; OOM rate -> lower batch cap; model
  cache miss -> pre-warm; blocked-output spike -> safety incident.
- Tie each metric to a concrete response, not just observation.

### 5. Product lifecycle APIs are intentionally small, but cancellation/deletion are missing

The minimal API is fine for a focused 45-minute case. However, the dataset now
talks about retention, user-requested deletion, tombstoning generated images,
webhook retries, and ownership-scoped signed URLs. Those behaviors imply a few
product lifecycle endpoints or at least explicit non-goals.

Why it matters: generated images and prompts are user data. A production
system usually needs deletion, cancellation, and maybe webhook management
semantics.

Concrete fix:

- Decide whether to add `DELETE /v1/generations/{id}` or keep it as a
  follow-up/non-goal.
- Consider `POST /v1/generations/{id}:cancel` for queued/running jobs, with
  clear behavior once inference has started.
- If callbacks remain first-class, mention event schema and whether webhook
  endpoints can be registered separately from submit.

## System Design Soundness

### Requirements and Capacity

The requirements are well scoped. They focus on prompt submission, async
generation, input/output safety, job status, tiering, quotas, GPU scarcity,
fairness, and failure resilience. This is the right boundary for the case; it
does not drift into social sharing, editing, or model-training features.

Capacity is now useful rather than qualitative. The steady-state calculation
is defensible, and the storage/egress estimates make result delivery concrete.
The main improvement is to make burst handling explicit. A platform can
provision for paid/realtime SLOs while allowing free backlog to grow, but the
reviewed file should say that directly so candidates do not infer that the
fleet handles all peak work synchronously.

### API

The API is now aligned with the architecture. Submit returns a job id quickly,
dedupes client retries with an idempotency key, records an optional callback,
and status fetch returns model version, timestamps, status reason, and image
metadata. This supports scheduling, retry, safety, and delivery.

Remaining API polish:

- Clarify callback event payloads and retries in the API section, not only in
  Step 6.
- Decide whether cancellation and deletion are in scope.
- Mention authorization on webhook registration if callbacks are accepted from
  arbitrary callers.

### Data Model

The data model now supports the central lifecycle. The biggest improvement is
moving from a thin `jobs`/`quotas` sketch to seven entities that cover
attempts, leases, dedupe, artifacts, safety, webhooks, and quotas.

The remaining gap is not table count; it is lifecycle invariants. The file
should explicitly state what prevents a DB write from being lost before queue
publish and what prevents stale/duplicate worker completions from winning. The
attempt lease/fencing language is present in Step 7, but the DB-to-queue
bridge deserves the same precision.

### Architecture

The high-level architecture is clean and domain-appropriate:

- `API` owns intake, quota checks, prompt safety, and durable job creation.
- `JobDB` is the source of truth for lifecycle.
- `Queues` and `Scheduler` separate backlog from policy.
- `Workers` run compatible GPU batches with resident model weights.
- `SafetyOut`, `ResultStore`, `CDN`, and `Notify` complete the safe delivery
  path.

The final diagram should stay compact. If more state is added, prefer prose or
data-model additions over crowding the architecture with every operational
table.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Run the Model Synchronously in the Request

Strong opener. It shows why multi-second GPU work should not live in the
request path. Keep it as the baseline.

Improvement: add one sentence that this can be acceptable only for a toy demo
or internal prototype, not for bursty user-facing traffic with safety checks.

### Step 2: Async Intake: Accept, Persist, Enqueue

This step is much stronger now because it includes idempotency, persist-before-
enqueue, and the write-to-publish trap. It teaches the right first production
move.

Improvement: make the outbox/reconciliation mechanism first-class enough that
the candidate can answer the crash-after-DB-write scenario without improvising.

### Step 3: Safety Gates on Input and Output

The safety step is now production-realistic. It distinguishes input and output
screening, blocked states, audit fields, policy/classifier versions, uncertain
decisions, abuse telemetry, and fail-closed behavior.

Improvement: decide how much manual review and appeals matter for the product.
If manual review is in scope, add the operator workflow. If not, mark it as a
follow-up so the case remains focused.

### Step 4: Priority and Fair Scheduling

This is a strong scheduling step. It names real inputs, fair-share units,
per-user controls, leases, heartbeats, and fencing. The option set is useful:
tiered priority with fair-share, FIFO with rate limits, and weighted fair
queuing.

Improvement: connect the fairness policy to the capacity numbers. For example,
reserve realtime/paid capacity, define free-tier floors, and show what happens
when incoming work exceeds the available GPU-seconds.

### Step 5: GPU Inference with Batching

This remains the strongest domain-specific step. Dynamic batching with a fill
window, compatibility constraints, memory caps, OOM splitting, resident
weights, and safety separation are exactly the right concepts.

Improvement: add model-version rollout to the batching story. Compatibility is
not just model name and size; it includes version, precision, adapters, and
safety policy compatibility.

### Step 6: Result Delivery

The delivery step is realistic and correctly avoids serving large images from
workers or the API. The push/poll/webhook options cover common client shapes,
and the prose now treats push as a hint backed by durable status replay.

Improvement: if webhooks are first-class, add a concise event schema and
callback registration/update behavior.

### Step 7: Reliability, Utilization, and Cost

The content is right: leases, idempotent attempts, requeue, fencing,
dead-lettering, autoscale, warm pools, spot capacity, observability, and cost
attribution. This is a good closing set of concerns.

Improvement: organize it so a candidate can present it cleanly under interview
pressure. The step can keep the same title but separate execution reliability
from fleet economics.

## Final Design Review

The final design is coherent and now much stronger than the previous review
version. It integrates fast intake, input safety, quota enforcement, durable
jobs, tiered queues, fair-share scheduling, compatible batches, resident model
weights, output safety, object storage, CDN delivery, notification/polling,
idempotent retry, warm pools, and autoscaling.

The worked example is a valuable addition. It gives the candidate a concrete
path through admission, queueing, scheduling, batching, inference, output
safety, storage, notification, signed URL fetch, and worker-crash recovery.

Remaining final-design improvement: explicitly name the queue publication
invariant and model-version lifecycle. Those two topics are the largest
remaining gaps between the strong final prose and a production implementation.

## Concept Introduction and Learning Flow

The sequence remains well staged:

- Async jobs appear immediately after the sync baseline fails.
- Safety appears before scheduling so unsafe prompts do not consume GPUs.
- Scheduling appears before batching because demand must be ordered before
  workers can form batches.
- Batching appears before delivery because it is the core GPU utilization
  lever.
- Delivery appears after inference because generated images are large binary
  artifacts.
- Reliability closes the loop on worker crashes, spot capacity, autoscaling,
  and cost.

The latest additions improve the teaching flow because they make abstract
claims concrete. Capacity, data model, safety, delivery, and final example now
give candidates enough material to defend trade-offs rather than recite boxes.

## Step-to-Final-Design Coherence

Step-to-final coherence is strong:

- Step 2 maps to `API`, `JobDB`, and `Queues`.
- Step 3 maps to `SafetyIn` and `SafetyOut`.
- Step 4 maps to `Scheduler` and scheduling policy.
- Step 5 maps to `Workers`, `ModelStore`, `SafetyOut`, and `ResultStore`.
- Step 6 maps to `ResultStore`, `CDN`, and `Notify`.
- Step 7 maps back to `Queues`, `Scheduler`, `Workers`, and `JobDB`.

The remaining coherence gap is the queue bridge. The final design says the API
persists and enqueues jobs; the review should make clear what happens when one
side of that operation succeeds and the other fails.

## Realism Compared With Production Systems

The case now captures most production concerns expected for this domain:

- GPU economics and batching.
- Tiered scheduling and fairness by normalized work, not raw requests.
- Idempotent submissions and retryable attempts.
- Worker leases, heartbeats, dead-lettering, and stale completion fencing.
- Input/output safety with audit and fail-closed behavior.
- Signed URL delivery, retention, deletion, and webhook retries.
- Observability and cost attribution.
- Managed vs self-hosted technology trade-offs.

The remaining realism improvements are targeted:

- Clarify burst admission and free-tier backlog/shedding.
- Add outbox/reconciliation semantics between JobDB and queue.
- Treat model version rollout and worker-pool pinning as first-class enough to
  support batching and reproducibility.
- Decide whether cancellation, deletion, and callback management APIs are in
  scope.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level book fields present: `patterns`, `technologyChoices`,
  `interviewScript`, `levelVariants`, `followUps`, `satisfies`, and
  `toProbeFurther`.
- `capacity` is now numeric and domain-specific.
- `dataModel` contains seven entities: `jobs`, `job_attempts`,
  `idempotency_keys`, `generated_images`, `safety_decisions`,
  `webhook_deliveries`, and `quotas`.
- `technologyChoices` contains ten concerns and has dataset-local tech icons
  under `assets/tech-icons/`.
- Main step `view.nodes` and `view.links` references resolve.
- Option view nodes and links resolve.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.
- `satisfies[*].steps[*]` references resolve.
- `probeLinks` resolve to `toProbeFurther.links`.
- Dataset-level `patterns` and `step.patterns` are consistent.
- There are no generated AI visual or comic fields in this dataset. That is
  acceptable because those assets are optional, but adding them would improve
  the book experience if visual consistency with other flagship cases matters.
- Source data changes should be followed by a `docs/book` rebuild; this review
  file itself remains repo-only.

## Recommended Edits, Prioritized

### P1: Align burst capacity math with admission policy

Reconcile submit QPS, images/sec, batch throughput, GPU count, queue wait, and
free-tier backlog/shedding in one compact capacity note.

### P1: Make DB-to-queue durability explicit

Add outbox/reconciliation semantics or a `queue_dispatches` entity. State the
invariant for accepted jobs and the recovery behavior for API crashes between
JobDB write and queue publish.

### P2: Promote model lifecycle into the main design

Add `model_versions` or equivalent state, define when model version is pinned,
and describe canary/rollback effects on worker pools, batching, and safety.

### P2: Organize Step 7 into reliability vs fleet economics

Keep the content but make it easier to present: crash-safe attempts and
fencing first; utilization, autoscale, spot, warm pools, metrics, and cost
second.

### P2: Decide cancellation/deletion/callback-management scope

Either add small lifecycle APIs or explicitly mark them as follow-ups/non-goals.

### P3: Add optional generated visuals

The dataset is structurally fine without them, but AI visuals or an explainer
comic would make this flagship case match the richer presentation of newer
book datasets.

## What Not To Change

- Keep the step order; it builds the system in the right sequence.
- Keep the synchronous baseline as Step 1.
- Keep input and output safety as one paired concept.
- Keep the option sets for scheduling, batching, and delivery.
- Keep the final design compact and use prose/data-model additions for extra
  state.
- Keep `technologyChoices`; it is especially valuable for a GPU-heavy case.
- Keep the worked example in the final design.

## Bottom Line

This is now a strong, production-aware image-generation interview case. The
recent changes fixed the main structural gaps. The next improvements should be
precise rather than broad: peak admission math, DB-to-queue recovery, model
rollout state, and a clearer operations presentation in the final step.
