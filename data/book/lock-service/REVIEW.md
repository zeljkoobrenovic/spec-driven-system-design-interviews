# Review: Distributed Lock Service - System Design

Reviewed file: `data/book/lock-service/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a clear, focused distributed-systems interview. The walkthrough teaches
the right spine: start with a single lock row, add consensus-backed state, add
leases for liveness, add fencing tokens for real protected-resource safety,
then discuss leader election, partitions, and scaling.

The main gap is that the dataset is still more conceptual than production
contract. The hard ideas are named correctly, but the capacity model, API,
data model, lease-expiry semantics, fencing integration, and operational
surface are too thin for a strong senior/staff answer. The review should not
push the case toward feature sprawl; it should make the existing correctness
claims precise enough to defend.

| Axis | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4/5 | Correct CP, lease, fencing, and partition principles; needs sharper lease/time and source-of-truth mechanics. |
| Production realism | 3.4/5 | Strong conceptual coverage, but API/model/ops/contracts are underspecified. |
| Pedagogical flow | 4.2/5 | Excellent staged progression; options and final scaling step need more explicit trade-offs. |
| Dataset/rendering fit | 4.5/5 | JSON and structured diagram references are clean; option labels/tradeoffs are sparse. |
| Overall | 4/5 | A good book case that needs a precision pass before it feels production-grade. |

## What Works Well

- The central teaching choice is right: it does not pretend a lease alone makes
  a distributed lock safe. It names fencing tokens as the real fix for the
  paused-holder problem.
- The baseline step is useful. The single-row design motivates both liveness
  failure and split-brain/failover risk without wasting time.
- The progression is coherent: consensus before leases, leases before fencing,
  fencing before leader election, and partitions before scaling.
- The final design integrates every major component introduced in the steps:
  API, consensus leader/followers, replicated log, derived lock state, sweeper,
  and protected resource.
- The probe links are appropriate: Chubby, ZooKeeper, Raft, Redis locks,
  Spanner, and SRE monitoring are all relevant references for this case.
- Renderer-facing structure is mostly clean. The dataset uses structured
  `view` and `sequence` objects rather than raw Mermaid for architecture and
  flows.

## Highest-Impact Issues

### 1. Capacity is a concept list, not a design-driving model

The capacity section lists "many" keys, "seconds" TTL, a 3/5 consensus group,
and CP semantics. Those are useful reminders, but they do not let a candidate
size the service or defend design decisions.

Why it matters: lock services are often dominated by renewal write load, hot
keys, quorum round trips, and per-shard consensus throughput. Without concrete
assumptions, Step 7 cannot explain when a single consensus group breaks, how
many shards are needed, or what p99 latency target is realistic.

Concrete fix:

- Add assumed active locks, lock keys, acquire QPS, renew QPS, release QPS, and
  read/status QPS.
- Convert TTL and renewal interval into write load. For example: 1M active
  locks renewing every 5 seconds means 200K renew writes/sec before replication.
- Add a per-group throughput budget and derive number of consensus groups.
- Add p50/p99 targets for acquire and renew, plus an availability target for
  majority-side operation.
- Estimate state size: current lock table, log retention before compaction,
  snapshots, dedup/idempotency records, and expiration index.
- Explicitly call out hot-key behavior: a single key cannot be horizontally
  scaled for writes without weakening semantics.

### 2. The API contract lacks the fields that make retries and ownership safe

The API has acquire, renew, and release. That is the right minimal surface, but
the requests only carry `clientId`, `ttlSec`, and sometimes `fencingToken`.
They do not define retry idempotency, holder/session identity, wait semantics,
error codes, TTL bounds, or stale-release behavior.

Why it matters: clients will retry acquire/renew/release across timeouts and
leader failover. If the API does not define operation IDs and ownership
preconditions, a retry can create ambiguous grants, release someone else's
lock, or hide whether a client still owns a lease.

Concrete fix:

- Add an `Idempotency-Key` or `requestId` to acquire and release/renew writes,
  scoped by tenant/client.
- Return a durable `lockId` or `leaseId` in addition to `fencingToken`; renew
  and release should require it.
- Define fail-fast vs wait behavior: `waitMs`, `deadline`, or `mode:
  "fail_fast" | "wait"`.
- Define stale outcomes: `NOT_HOLDER`, `LEASE_EXPIRED`, `STALE_TOKEN`,
  `QUORUM_UNAVAILABLE`, and retryable leader-redirect errors.
- Put TTL policy in the contract: minimum/maximum TTL, server-side clamping,
  and whether clients may request a TTL or only choose from policy.
- Add authn/authz/tenant fields or a note that `clientId` is authenticated
  identity, not a caller-supplied string.

### 3. Lease expiry is shown as a direct state mutation, but it must be committed

The diagrams and text show a `Sweeper` expiring stale leases against
`LockState`. The text also says renew goes through consensus, but expiry is not
shown as an operation proposed to the consensus log.

Why it matters: in a linearizable lock service, expiry changes ownership state.
It cannot be an arbitrary local mutation by a background process. If multiple
replicas independently expire leases based on local clocks, the design can
reintroduce divergence. Expiry must be decided by the leader or proposed as a
log entry and applied deterministically.

Concrete fix:

- Make the sweeper a leader-side task or a stateless worker that proposes
  `expire(key, expectedLeaseId, observedExpiry)` through the leader.
- Add a `sweeper-leader` or `sweeper-log` link instead of implying
  `Sweeper -> LockState` direct mutation.
- State exactly what time source drives expiry: leader monotonic time,
  consensus-applied tick entries, or another bounded-clock model.
- Explain the renew-vs-expire race: renew wins only if committed before the
  expiry operation under the chosen ordering rule.
- Add a small failure flow for "renew timeout near expiry" so candidates can
  discuss uncertainty honestly.

### 4. Fencing is correct conceptually but not yet a complete integration contract

Step 4 correctly says the protected resource must reject stale tokens. The
dataset stops before defining what the resource stores, which operations carry
the token, and what happens when the resource cannot enforce fencing.

Why it matters: the lock service alone cannot protect an external resource
after a holder pause. The real contract is between the lock service, client,
and protected resource. If the resource does not persist the highest accepted
token per lock/resource, fencing is only a number in the response.

Concrete fix:

- Add a protected-resource contract: every guarded write carries
  `(lockKey, fencingToken, holderId)` and the resource atomically checks
  `token >= max_seen_token`.
- Add a small data-model note for the resource-side `max_seen_token` or state
  version, even if it is outside the lock service's storage.
- Make the sequence use distinct old/new holders. The current flow reuses
  `Client` for both, which weakens the paused-holder teaching moment.
- State that locks without fencing are only advisory for resources that cannot
  check tokens.
- Mention token scope: per lock key, per resource, or global; per-key tokens
  are usually enough and cheaper.

### 5. The data model is too small for the behavior promised by the walkthrough

The model has `lock` and `replicated_log`, which covers the happy path but not
retry safety, sessions, sharding, expiration lookup, applied indexes, or
operational recovery.

Why it matters: the final design claims durable, highly available,
linearizable lock state with leases, fencing, leader failover, and sharding.
The data model should show the minimum records that make those behaviors
auditable and recoverable.

Concrete fix:

- Extend `lock` with `tenant`, `lease_id`, `holder_session_id`,
  `last_renewed_at`, `expires_at`, `fencing_token`, `version`, `log_index`,
  and status.
- Extend `replicated_log.op` with operation ID, expected holder/lease, TTL,
  token assigned, term, result, and request identity.
- Add an idempotency/dedup table keyed by client/request ID and retained long
  enough for safe retries.
- Add shard or consensus-group metadata: key-range/ring ownership, leader,
  members, term, health, and reconfiguration status.
- Add an expiration index/timer wheel concept so the sweeper does not scan all
  locks.

## System Design Soundness

The core design is sound. A CP consensus group is the right answer when the
primary guarantee is "never grant two holders." The dataset also correctly
separates liveness from safety: leases prevent permanent deadlock, while
fencing protects the resource from paused or partitioned old holders.

The consistency explanation should become more exact. "Quorum-relative expiry"
is directionally right, but the dataset should say how expiry is ordered with
renewals. A candidate should be able to explain whether expiry is a committed
log operation, whether the leader uses monotonic time, and how a renewal that
arrives near the deadline is accepted or rejected.

The architecture should also clarify the source-of-truth boundary. `LockState`
is derived from the replicated log, but several views show direct API or
sweeper access to it. Reads may be served from applied state, but writes and
expiry transitions should be proposed through the leader/log path.

The fencing section is the strongest conceptual part. It should be preserved,
then made more concrete by defining the resource-side token check and storing
distinct old/new-holder examples.

## Step-by-Step Pedagogical Review

### Step 1: Naive: A Lock Row in a Single Database

Good baseline. It motivates the next steps without caricaturing the single-row
design. The trap is concrete and worth keeping.

Improvement: add one sentence on where this design is acceptable: a single
process, a tiny internal tool, or non-critical advisory locking. That makes
the rejection feel scoped rather than absolute.

### Step 2: Consensus-Backed Lock State

This is the right first real mechanism. The step clearly teaches leader,
quorum, log, and applied lock state. The option contrasting a single atomic
store and independent SET NX stores is useful.

Improvements:

- Give the options labels and tradeoff text. Currently the option records have
  descriptions but no titles/labels/tradeoffs, so the choice is less teachable
  in the UI.
- Make acquire, release, renew, and expire all log operations in the text.
- Add a note about read behavior: linearizable reads through leader/read-index
  vs stale follower reads for non-authoritative inspection.

### Step 3: Leases with TTL (No Permanent Deadlock)

The step correctly introduces bounded ownership and renewal. The TTL trade-off
is also framed well: short TTL recovers faster but increases false expiry and
renewal load.

Improvements:

- Show expiry as a consensus-ordered transition, not a direct sweeper write.
- Discuss renewal cadence in relation to TTL and p99 latency.
- Add the operational load implication: renewals can dominate writes.
- Define what a client must do after a renewal timeout. It may not know whether
  the renewal committed; it should stop acting unless it can confirm ownership.

### Step 4: Fencing Tokens (The Fundamental Gap)

This is the most important step, and it is mostly correct. It teaches that the
protected resource must reject stale tokens, not just that the lock service
hands out tokens.

Improvements:

- Use separate participants for old holder and new holder in the sequence.
- Add the protected resource's `max_seen_token` check to the model or text.
- State that fencing requires cooperation from the guarded system; otherwise
  the lock is advisory.
- Clarify token scope and monotonicity per key/resource.

### Step 5: Leader Election as a Lock

This is a good application of the primitive. The token-as-epoch connection is
the right teaching point.

Improvement: separate internal consensus leader election from client-facing
leader election more explicitly. A reader should not confuse the Raft leader
for the lock holder of `scheduler-leader`. Add a line that the service's own
leader is chosen by consensus membership, while clients use lock records as an
application-level election primitive.

### Step 6: Failure, Partitions, and the Worst Cases

The CP partition behavior is correct: only a majority side grants or renews.
The step also names leader failure, committed state, and clock skew.

Improvements:

- Add a minority-side renewal flow: holder cannot reach quorum, renewal fails,
  and it must stop acting even if its local TTL has not obviously elapsed.
- State the behavior for in-flight acquire/renew requests during leader
  failover: retry with idempotency key, redirect to leader, or return retryable
  error.
- Add a note on membership changes, because 3/5-node groups eventually need
  safe reconfiguration.

### Step 7: Scaling and Operating the Lock Service

This is directionally right: shard by key across independent consensus groups,
snapshot/compact logs, and watch long-held locks.

Improvements:

- Add concrete capacity math before this step or inside it.
- Discuss shard-routing metadata and safe movement of key ranges.
- Call out hot-key limits: one contended lock is serialized by design.
- Add backpressure, per-client quotas, and admission controls for renewal
  storms.
- Add specific metrics: acquire/renew p99, quorum commit latency, failed
  renewals, expired leases, stale-token rejects, leader changes, compaction lag,
  per-shard hot keys, and clock-skew warnings.

## Final Design Review

The final design description is concise and accurate at the conceptual level.
It includes the consensus group, committed log, applied state, leases, sweeper,
fencing tokens, protected resource, client-facing leader election, partitions,
and sharding.

The final diagram should be tightened around write paths. `api-lockstate` is
fine for a read or applied-state lookup, but it should not imply that the API
can mutate lock state outside consensus. Likewise, `sweeper-lockstate` should
be relabeled or rerouted so expiry is a proposed/committed operation.

The final design should also include the minimal production control plane:
shard map, group membership, snapshots/compaction, client authentication, and
idempotency/dedup records. These do not need to dominate the diagram, but they
should appear in text or data model so the design is operable.

## Concept Introduction and Learning Flow

The concept order is strong:

- atomic single-store lock
- quorum-backed linearizable state
- leases and renewal
- fencing tokens
- lock-based leader election
- CP partition behavior
- sharding and operations

The biggest learning-flow improvement is to turn implicit contracts into
explicit ones as they appear. When leases arrive, define renewal uncertainty
and expiry ordering. When fencing arrives, define the resource-side check.
When sharding arrives, define shard ownership and hot-key limits.

The option tabs need more teaching metadata. The consensus, lease, and
availability steps include meaningful alternatives, but the options lack
titles, labels, and tradeoff fields. Adding them would improve the decision
tree and make the alternatives scan better in the explorer.

## Step-to-Final-Design Coherence

Most steps land cleanly in the final design:

- Step 1 motivates why single-store locking is not enough.
- Step 2 contributes leader, followers, log, and linearizable state.
- Step 3 contributes leases and sweeper.
- Step 4 contributes fencing token and protected resource.
- Step 5 contributes the leader-election use case.
- Step 6 contributes majority-only progress under partition.
- Step 7 contributes sharding, log compaction, and operational monitoring.

The weaker connections are the production state records. Idempotency, shard
metadata, expiration indexing, and resource-side fencing state are needed by
the story but are not represented in the final model. Add them lightly rather
than expanding the diagram too much.

## Realism Compared With Production Systems

Compared with Chubby/ZooKeeper-style systems, the dataset teaches the core
correctness principles well. It avoids the common bad answer of using a cache
or Redis key and calling it done.

Remaining realism gaps:

- No session model or watch/waiter model for blocking acquire.
- No idempotency or request replay handling across leader failover.
- No clear ownership contract for `clientId`, `leaseId`, and stale renew/release.
- No explicit expiry ordering through the consensus log.
- No resource-side fencing storage model.
- No shard-map, reconfiguration, or hot-key operational story.
- No authn/authz, tenant isolation, TTL caps, or abuse controls.
- Observability is mentioned only briefly.

The case does not need to become a full ZooKeeper clone. It does need enough of
these contracts to show that the candidate understands where the hard edges are.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level keys include expected book fields: `patterns`, `interviewScript`,
  `levelVariants`, `followUps`, `satisfies`, and `toProbeFurther`.
- Main step `view.nodes` and `view.links` references resolve.
- Option view string links resolve; option-local nodes such as `StoreA`,
  `StoreB`, and `StoreC` are inline nodes, not missing high-level nodes.
- Final design `view.nodes`, `view.links`, and `view.groups` references
  resolve.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Dataset-level `patterns[*].steps` references resolve to real step IDs.
- API sequence participants resolve to high-level node IDs.
- There are no generated AI visuals or explainer comic wired for this dataset.
  That is acceptable for this review.
- Option records are sparse: several have no `title`, `label`, or `tradeoff`.
  This is not a schema error, but it weakens the UI and decision-tree teaching
  value.

## Recommended Edits, Prioritized

### P1: Add design-driving capacity math

Add active locks, key count, acquire/renew/release QPS, TTL/renewal-derived
write load, consensus-group throughput, shard count, latency targets, and
state/log storage estimates.

### P1: Harden the API and ownership contract

Add idempotency keys, lease/session IDs, wait/fail-fast semantics, stale error
codes, TTL bounds, authenticated identity, and retry behavior.

### P1: Make expiry a consensus-ordered operation

Reroute or relabel sweeper behavior so expiry is proposed through the leader
and applied from the committed log. Define the renew-vs-expire race.

### P1: Complete the fencing integration contract

Define the protected resource's token check, resource-side highest-token state,
token scope, and the advisory-lock caveat when a resource cannot fence.

### P2: Expand the data model to support retries, sharding, and operations

Add lease/session identity, request dedup, shard/group metadata, applied log
index, expiration index, snapshots, and richer log op fields.

### P2: Add operational controls and metrics

Cover backpressure, renewal storms, per-client quotas, shard health,
leader-change rate, expired leases, stale-token rejects, commit latency, and
compaction lag.

### P2: Improve option metadata

Add `title`, `label`, and `tradeoff` fields to the consensus, lease, and
availability options so the alternatives are more useful in the explorer.

### P3: Add one or two failure flows

Good candidates: renewal timeout near expiry, minority partition renewal
failure, and retry after leader failover with an idempotency key.

## What Not To Change

- Keep the narrow focus on mutual exclusion, leases, fencing, and leader
  election.
- Keep consensus/CP as the chosen design; do not weaken the guarantee to make
  availability easier.
- Keep the single-row baseline and the independent-store alternative as
  rejected options.
- Keep fencing tokens as the central insight.
- Keep the final design compact; add missing contracts mostly through API,
  data model, captions, and short flows.

## Bottom Line

This is a strong conceptual interview for distributed locks. The next pass
should make the contract operational: concrete load assumptions, safe retry
semantics, consensus-ordered expiry, resource-enforced fencing, and enough
state model detail to prove the design survives real failures.
