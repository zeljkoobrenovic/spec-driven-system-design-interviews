# Review: Image Generation Platform - System Design

Reviewed file: `data/book/image-generation/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a clear, compact image-generation system design case. The main learning
spine is right: synchronous generation fails, so the design moves to async
intake, safety gates, tier-aware scheduling, batched GPU inference, CDN-backed
delivery, and retryable jobs. The diagrams are structured cleanly, the option
sets are useful, and the final design integrates all major components introduced
by the steps.

The case is not yet at the depth of the stronger book datasets. The biggest
gaps are production precision: capacity is qualitative rather than numeric, the
data model is too thin for the lifecycle being taught, scheduling and batching
need more explicit state and metrics, safety lacks audit/appeal/versioning
semantics, and delivery does not fully specify URL ownership, retention, or
webhook/push reliability. The book-specific `technologyChoices` section is also
missing, which matters for a GPU-heavy platform where implementation choices are
central to cost and operability.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.0 / 5 | Strong conceptual architecture; needs numeric capacity, lifecycle state, and clearer failure semantics. |
| Production realism | 3.7 / 5 | Covers the right components but under-models attempts, leases, safety audit, model versions, storage retention, and observability. |
| Pedagogical flow | 4.3 / 5 | The step sequence is coherent and easy to teach; several steps need deeper drills or examples. |
| Final design coherence | 4.1 / 5 | Final diagram matches the steps, but reliability and scheduling state remain mostly prose-only. |
| Dataset/rendering fit | 4.6 / 5 | JSON parses; view, option, finalDesign, pattern, probe-link, and satisfies references checked cleanly. |

Recommendation: preserve the step order and core architecture. The next pass
should add concrete capacity math, expand the state model, and make the GPU
scheduling, safety, and delivery contracts more operational.

## What Works Well

- The case starts with the right baseline. Step 1 shows why synchronous
  generation collapses under multi-second GPU work and naturally motivates the
  async pipeline.
- Requirements identify the central constraints: expensive scarce GPUs, async
  processing, mandatory input/output safety, tier fairness, quotas, and failure
  recovery.
- The architecture nodes are appropriate for the domain: `SafetyIn`,
  `Scheduler`, `Workers`, `ModelStore`, `SafetyOut`, `ResultStore`, `CDN`, and
  `Notify` are all visible.
- The option sets are meaningful rather than strawmen. Scheduling compares
  tiered priority, FIFO, and weighted fair queuing; inference compares dynamic
  batching, no batching, and continuous batching; delivery compares push/poll
  and webhooks.
- Step concepts and pattern tags line up with dataset-level patterns.
- The final design description integrates safety, quota enforcement, durable
  jobs, fair-share scheduling, warm model pools, batched inference, output
  safety, CDN delivery, idempotent retry, and autoscaling.
- Renderer-facing references are healthy: main step view nodes/links, option
  view nodes/links, final design nodes/links, highlights, `satisfies.steps`,
  `probeLinks`, and step pattern tags all resolve.

## Highest-Impact Issues

### 1. Capacity is qualitative, so the GPU sizing story is hard to defend

The capacity section says requests are "high, bursty", GPUs are "scarce /
costly", time per image is "~seconds", and result size is "~MBs". That is a
good framing, but it does not convert demand into GPU fleet size, queue wait,
batch size, storage volume, or CDN egress.

Why it matters: this interview is fundamentally about scarce GPU capacity. A
candidate should be able to explain how request volume, image count, diffusion
steps, batch size, model mix, and tier SLOs translate into GPU-hours and queue
latency.

Concrete fix:

- Add an example workload: requests/day, peak submit QPS, average `n`, image
  size, model/size mix, and realtime vs paid vs free split.
- Translate it into inference work: images/sec, seconds/image unbatched,
  images/sec/GPU batched, target utilization, and required GPU count.
- Show queue math by tier: paid p95 wait target, free backlog tolerance, and
  what happens when burst demand exceeds GPU capacity.
- Add result storage and egress estimates: MB/image, retention window, daily
  writes, object-store footprint, and CDN read fanout.

### 2. The data model cannot support the lifecycle and guarantees promised by the prose

The data model has only `jobs` and `quotas`. The prose depends on more durable
state than that: idempotency, attempts, queue leases, safety decisions, output
metadata, model versions, delivery subscriptions, and retry/dead-letter
behavior.

Why it matters: long GPU jobs fail in ambiguous ways. Without explicit state,
the design cannot cleanly explain duplicate submit handling, worker crash
recovery, output blocking, model rollout, or user-visible status history.

Concrete fix:

- Add `job_attempts` with `attempt_id`, `job_id`, `worker_id`, `model_version`,
  `status`, `started_at`, `heartbeat_at`, `lease_expires_at`, `finished_at`,
  `error_code`, and retry count.
- Add an `idempotency_keys` or submit-dedup record scoped by user/client and
  request fingerprint.
- Expand `jobs` with lifecycle fields such as `priority`, `dedupe_key`,
  `model_version`, `queued_at`, `started_at`, `completed_at`, `blocked_reason`,
  `failure_reason`, and `retention_expires_at`.
- Add `safety_decisions` or safety audit fields for input/output policy
  version, classifier version, decision, reason, and reviewer/appeal state if
  moderation is manual.
- Add `assets` or `generated_images` rows for object key, size, mime type,
  checksum, safety status, CDN URL expiry, and deletion state.

### 3. Scheduling and batching need more precise operational contracts

Step 4 and Step 5 teach the right ideas, but the scheduler remains a conceptual
box. It does not define how fair-share usage is measured, how batch
compatibility is selected, how jobs are leased to workers, or how queue depth
turns into autoscaling.

Why it matters: GPU scheduling bugs are expensive. A production answer needs to
separate priority policy, admission control, batch formation, worker leases,
and usage accounting.

Concrete fix:

- Define the scheduler inputs: tier, user quota, model, size, batchability,
  deadline/SLO, age in queue, and expected runtime.
- Add a small fairness formula or state sketch: per-tier weights, per-user caps,
  deficit counters or token buckets, and whether usage is measured by
  GPU-seconds, images, or normalized model cost.
- Explain batch formation: compatible model/version/size/LoRA/options, maximum
  batch size by GPU memory, fill-window timeout, and fallback when traffic is
  too mixed to batch well.
- Add leasing/fencing language: queue visibility timeout or assignment lease,
  worker heartbeat, scheduler epoch, and duplicate completion rejection.
- Expand observability from "utilization and queue wait" to include queue age by
  tier, batch fill ratio, GPU memory OOMs, worker cold-start time, model cache
  hit rate, retries, blocked outputs, and cost per image.

### 4. Safety is correctly bookended, but policy state and human workflows are missing

The dataset correctly teaches input and output moderation. Step 3 even calls
out audit logging. The design stops short of saying what is logged, how policy
versions are handled, what users see for blocked jobs, and whether appeals or
manual review exist.

Why it matters: safety behavior affects product correctness and compliance, not
just architecture. "Blocked" is a terminal state that needs reason codes,
retention rules, and operator workflows.

Concrete fix:

- Add status distinctions such as `blocked_input`, `blocked_output`,
  `manual_review`, and `failed_policy_check`, or explicitly map them to the
  existing `blocked` state.
- Store policy/classifier version and reason codes for both prompt and image
  checks.
- Mention adversarial prompt handling, repeated violator throttling, and abuse
  telemetry.
- Decide whether unsafe generated images are stored in a restricted review
  bucket, deleted immediately, or retained only as classifier metadata.
- Add a failure drill: output safety service is down, too slow, or returns
  uncertain results. The safest default should be fail closed or route to review
  depending on product policy.

### 5. Delivery semantics need to be tighter

Step 6 has the right shape: object storage, CDN, push/poll/webhook, signed
expiring URLs, and retention by plan. The data/API surfaces do not yet expose
enough contract detail for production use.

Why it matters: generated images are user data and large binary artifacts.
Access control, expiration, retries, and deletion behavior are part of the
system design, not only storage implementation.

Concrete fix:

- Include delivery fields in the API response: `expires_at`, `content_type`,
  `size_bytes`, and maybe `status_reason`.
- For push/SSE/WebSocket, define reconnect behavior and replay from job status
  rather than relying on an in-memory stream.
- For webhooks, add signing, retry schedule, event id, idempotency, and
  dead-letter/escalation behavior.
- Clarify whether CDN URLs are per-user signed URLs, public unguessable links,
  or short-lived tokens minted by the API.
- Add retention/deletion semantics for free vs paid tiers and user-requested
  deletion.

### 6. `technologyChoices` is missing for a book-group case

The dataset has patterns, interview script, level variants, follow-ups, and
probe links, but it lacks `technologyChoices`. For this particular domain,
technology choices are not cosmetic: model serving, GPU scheduling, queues,
object storage, CDN, safety classifiers, and observability strongly affect the
design.

Concrete fix: add a `technologyChoices` section covering at least:

- GPU serving/runtime: Triton, TorchServe, Ray Serve, Kubernetes jobs, managed
  endpoints.
- Scheduling/orchestration: Kubernetes device plugins, Kueue/Volcano, Ray,
  Slurm-like scheduler, managed batch/ML services.
- Queue and job state: SQS/Pub/Sub/Kafka/RabbitMQ plus a relational or document
  job store.
- Object storage/CDN: S3/GCS/Azure Blob plus CloudFront/Cloud CDN/Azure CDN.
- Safety stack: in-house classifiers, moderation services, review queues, and
  audit stores.
- Observability/cost: Prometheus/Grafana, OpenTelemetry, cloud monitoring, GPU
  utilization exporters, billing/cost attribution.

## System Design Soundness

### Requirements and Capacity

The requirements are well scoped for a 45-minute case. They avoid unrelated
image-editing or social-feed features and keep the focus on async generation,
GPU scarcity, safety, priority/fairness, quota, and resilience.

The weak point is capacity. The interview should include a numeric scenario so
the candidate can decide whether one queue and one scheduler are enough, how
many GPUs are needed, what batch size is plausible, and when free-tier work must
be shed or delayed. Without numbers, "maximize utilization" stays correct but
abstract.

### API

The API is intentionally simple and mostly aligned with the architecture:
`POST /v1/generations` returns a job id, and `GET /v1/generations/{id}` returns
status and result URLs. The submit request includes prompt, size, count, model,
and tier, which matches later scheduling and batching choices.

Needed additions:

- Idempotency key in the submit API.
- Optional callback/webhook or subscription preference if Step 6 keeps webhook
  and push as first-class options.
- Status reason and timestamps so blocked/failed/running states are useful.
- Explicit ownership/authorization model for fetching a job and its images.
- Model version in either the request or response if model rollout is a
  follow-up/staff-level concern.

### Data Model

The current `jobs` table is a start, but it is too small for the rest of the
case. `result_keys` as a list also hides per-image status, size, safety decision,
and retention. `quotas` has only `remaining` and `tier`, so it cannot express
rate windows, paid credits, burst limits, model-specific costs, or reset times.

This can be fixed without making the dataset huge. Add a handful of compact
entities: `job_attempts`, `idempotency_keys`, `generated_images`,
`safety_decisions`, and maybe `delivery_events` or `webhook_deliveries`.

### Architecture

The architecture is conceptually sound. The final design includes all expected
components and avoids overfitting to a specific vendor. The main improvement is
to make source-of-truth boundaries visible:

- JobDB is authoritative for job lifecycle.
- Queue assignments are leased and retryable, not permanent ownership.
- Scheduler decides priority and batch formation but should not be the only
  place where lifecycle state lives.
- Workers produce attempts and artifacts; the job is completed only after
  output safety and result persistence.
- Notifications are derived from job completion and must be replayable.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Run the Model Synchronously in the Request

Strong opener. It cleanly demonstrates why multi-second GPU work cannot sit
inside an HTTP request path. Keep this step.

Improvement: mention that a tiny internal demo can start here, but the design
must move on as soon as user-facing burst traffic or safety requirements exist.

### Step 2: Async Intake: Accept, Persist, Enqueue

This is the right first real design step. Persist-before-enqueue and fast `202`
responses are good teaching points.

Improvement: add idempotency and queue ordering details. A retrying client
should not create duplicate GPU jobs, and a crash after DB write but before
queue publish needs a recovery path such as transactional outbox, queue rebuild,
or periodic sweeper.

### Step 3: Safety Gates on Input and Output

The bookended safety concept is correct and important. The trap about only
screening prompts is worth preserving.

Improvement: add safety state. A candidate should explain blocked status,
policy versions, audit logs, abuse signals, and what happens when the safety
service is unavailable.

### Step 4: Priority and Fair Scheduling

The options are useful and realistic. The default choice of per-tier priority
queues with fair-share floors is plausible for a consumer image-generation
service.

Improvement: make fairness measurable. Define whether fairness uses
requests, images, GPU-seconds, normalized model cost, or credits. This matters
because one "request" may ask for multiple images, a larger resolution, or a
more expensive model.

### Step 5: GPU Inference with Batching

This is the strongest domain-specific step. Dynamic batching with a fill window
is a good default, and the alternatives teach the latency/utilization tradeoff.

Improvement: name compatibility constraints and failure cases. Batches usually
need same model/version, size, precision, and maybe LoRA/control settings.
Mention OOM handling, max batch size, partial batch timeout, warm model cache,
and whether output safety runs on GPU workers or a separate classifier fleet.

### Step 6: Result Delivery

The object store plus CDN design is right. The three delivery options cover the
usual clients: interactive UI, simple polling clients, and server-to-server
integrations.

Improvement: add delivery reliability. Push notifications should be hints backed
by polling/status replay. Webhooks need signatures, retries, event ids, and
idempotent consumers. CDN URLs need explicit expiration and authorization.

### Step 7: Reliability, Utilization, and Cost

The step closes the interview in the right place: idempotent attempts,
re-queueing on worker failure, warm pools, autoscaling, spot capacity, and
utilization metrics.

Improvement: it is too compressed for all the work it carries. Split out or
expand reliability state: leases, attempts, heartbeat timeout, duplicate
completion handling, dead-letter thresholds, autoscale lag, spot preemption, and
cost attribution by tier/model.

## Final Design Review

The final design is coherent and should be preserved. It ties together fast
intake, input safety, durable queueing, fair-share priority scheduling, batched
GPU inference, resident model weights, output safety, object storage, CDN
delivery, notification, retry, warm pools, and autoscaling.

The final diagram is clean but optimistic. The final design should be backed by
more explicit lifecycle and operational state: attempts, leases, model versions,
safety decisions, generated image records, and delivery events. Those additions
would make the prose defensible without changing the main diagram much.

## Concept Introduction and Learning Flow

The concept sequence works well:

- Async jobs appear immediately after the sync baseline fails.
- Safety appears before scheduling because unsafe prompts should not consume
  GPUs.
- Scheduling appears before batching because demand must be ordered before
  workers can form batches.
- Delivery appears after inference because generated images are large binary
  artifacts, not API response bodies.
- Reliability closes the loop on worker crashes and GPU cost.

The biggest teaching improvement would be one worked example. For example: a
paid request for 4 images at 1024px, a free backlog of 20K images, a 50ms batch
window, and a 16-image max batch. Walk through how it is admitted, queued,
batched, run, safety-screened, stored, and delivered.

## Step-to-Final-Design Coherence

Step-to-final coherence is good:

- Step 2 maps to `API`, `JobDB`, and `Queues`.
- Step 3 maps to `SafetyIn` and `SafetyOut`.
- Step 4 maps to `Scheduler`.
- Step 5 maps to `Workers`, `ModelStore`, `SafetyOut`, and `ResultStore`.
- Step 6 maps to `ResultStore`, `CDN`, and `Notify`.
- Step 7 maps back to `Queues`, `Scheduler`, `Workers`, and `JobDB`.

The main coherence gap is state, not components. The final design says jobs are
idempotent and retryable, but the data model does not yet show attempts,
leases, dedupe, or replayable notification state.

## Realism Compared With Production Systems

The case captures the right production concerns at a high level. Remaining
realism gaps:

- Model rollout and version pinning are only a follow-up, yet workers load
  weights from `ModelStore`; the job should record the model version actually
  used.
- Quotas should account for model cost, image count, resolution, and failed or
  blocked jobs, not just a simple remaining integer.
- GPU worker startup and model-load latency can dominate autoscale response;
  warm pools and model cache hit rate need more explicit treatment.
- Safety decisions should be auditable and explainable enough for support,
  abuse review, and compliance.
- Result storage needs retention, deletion, and access-control semantics.
- Observability should include safety, delivery, and cost signals, not only GPU
  utilization and queue wait.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level book fields present: `patterns`, `interviewScript`,
  `levelVariants`, `followUps`, `satisfies`, and `toProbeFurther`.
- `technologyChoices` is absent.
- Main step `view.nodes` and `view.links` references resolve.
- Option view string nodes and links resolve; option-local nodes such as `FIFO`,
  `WFQ`, and `Webhook` are inline nodes, not missing canonical nodes.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve.
- Step highlights resolve.
- `satisfies[*].steps[*]` references resolve.
- `probeLinks` resolve to `toProbeFurther.links`.
- Dataset-level `patterns` and `step.patterns` are consistent.
- There are no generated assets besides `icon.png`; no generated `docs/`
  changes are needed for this review file alone.

## Recommended Edits, Prioritized

### P1: Add concrete capacity math

Convert request volume into images/sec, GPU-hours, batch size, queue wait by
tier, storage footprint, and CDN egress.

### P1: Expand lifecycle and artifact state

Add compact tables for attempts, idempotency keys, generated images, safety
decisions, and possibly delivery/webhook events.

### P1: Make scheduling and batching operational

Define fair-share accounting, batch compatibility, assignment leases, worker
heartbeats, autoscale signals, and duplicate completion handling.

### P2: Tighten safety semantics

Represent blocked states, policy/classifier versions, audit logs, uncertain
classifier outcomes, abuse signals, and operator/manual-review workflow.

### P2: Tighten result delivery contracts

Specify signed URL authorization, expiration, retention/deletion, push replay,
webhook signing/retry/idempotency, and result metadata in the API.

### P2: Add `technologyChoices`

Cover GPU serving, schedulers, queues, job stores, object storage/CDN, safety
classifiers, observability, and managed cloud alternatives.

### P3: Add one worked example

Use a single request and burst scenario to show admission, queueing, batching,
safety, storage, notification, and retry behavior end to end.

## What Not To Change

- Do not change the step order; it builds the design in the right sequence.
- Keep the synchronous baseline as the first step.
- Keep input and output safety as one paired concept.
- Keep the three option sets for scheduling, batching, and delivery; they teach
  real tradeoffs.
- Keep the final design compact. Add state and prose depth without turning the
  diagram into a crowded implementation map.

## Bottom Line

This is a strong compact interview case with a clean architectural spine. To
make it flagship-quality for the book group, the next revision should make the
GPU economics and lifecycle state concrete: numeric capacity, attempts and
leases, safety audit, delivery contracts, observability, and technology choices.
