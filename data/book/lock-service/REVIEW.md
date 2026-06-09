# Review: Distributed Lock Service - System Design

Reviewed file: `data/book/lock-service/interview.json`
Review date: 2026-06-09

## Executive Summary

This dataset has moved from a strong conceptual case to a production-credible
distributed-systems walkthrough. The recent hardening pass addressed the largest
prior gaps: capacity is now design-driving, retries use `requestId`, ownership
uses `leaseId`, expiry is explicitly committed through consensus, fencing has a
resource-side `max_seen_token` contract, and the data model now includes dedup,
shard membership, expiration indexing, and resource fencing state.

The remaining work is mostly about making the polished contract visible in the
teaching surface. The API descriptions are strong, but only acquire has an API
flow. The text mentions wait mode, shard movement, reconfiguration, and
minority-side renewal failure, but those scenarios would benefit from one or two
small diagrams or flows. The design is now sound; the next pass should improve
how clearly candidates can rehearse the operational edge cases.

| Axis | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.6/5 | Correct CP/quorum, lease, fencing, expiry-ordering, retry, and sharding mechanics. |
| Production realism | 4.3/5 | Much stronger API/model/ops contract; remaining gaps are watch/waiter behavior, shard migration details, and auth/tenant policy depth. |
| Pedagogical flow | 4.6/5 | Excellent staged progression from naive row to consensus, leases, fencing, partitions, and scaling. |
| Dataset/rendering fit | 4.4/5 | Structured views validate cleanly; API Flows page has placeholders for endpoints without sequences. |
| Overall | 4.5/5 | A strong book case with a few remaining polish opportunities. |

## What Works Well

- The core teaching spine is excellent: naive lock row -> consensus-backed
  state -> leases -> fencing tokens -> leader election -> partitions -> scaling.
- The previous capacity gap is fixed. The dataset now converts active leases,
  TTL, renewal interval, acquire/release QPS, and per-group throughput into an
  approximate consensus-group count.
- The API contract now includes the critical safety fields: `requestId`,
  `leaseId`, wait/fail-fast mode, server-side TTL clamping, linearizable reads,
  and retryable failover errors.
- Expiry is now modeled correctly as a consensus-ordered operation, not a local
  sweeper mutation. The renew-vs-expire race is explained clearly.
- Fencing is no longer just a token in the lock response. The protected resource
  must persist `max_seen_token` and reject stale tokens.
- The data model now supports the promised behavior: lock state, replicated log,
  request dedup, shard/group membership, expiration index, and external resource
  fencing state.
- Options now have useful titles and tradeoffs, especially for consensus vs
  single-store/Redlock and CP vs AP partition handling.
- Renderer-facing structure is healthy: the dataset uses structured `view` and
  `sequence` objects, and the main node/link references resolve.

## Highest-Impact Issues

### 1. API flows lag behind the now-strong API contract

The API descriptions are much better than before, but only
`POST /v1/locks/{key}/acquire` has a structured sequence. Renew, release, and
read currently render as "No flow diagram defined for this endpoint" in the API
Flows wrap-up.

Why it matters: the most interesting operational behavior is in renew and
release, not just acquire. A candidate should see how renew commits through the
leader, how a timed-out renew becomes uncertain, and how stale release is a
preconditioned no-op.

Concrete fix:

- Add a renew API flow showing `requestId`, `leaseId`, leader/quorum commit, and
  the timeout/uncertain-ownership branch.
- Add a release flow showing the precondition on `leaseId` and the stale-release
  no-op after expiry/regrant.
- Add a read flow or explicitly omit API flow cards for endpoints with no
  sequence; placeholders make the wrap-up look incomplete.
- In the acquire flow, include the replicated log participant. The current flow
  jumps from leader/quorum to `LockState`; adding `Log` would reinforce that
  lock state is derived from committed log entries.

### 2. Waiting/watch semantics are introduced but not fully designed

Acquire supports `mode: "wait"` and `waitMs`, and the requirements say clients
can block or fail fast. The dataset does not yet explain how waiting is
implemented: polling, long-poll, server-side waiter queues, watches, or a
notification stream.

Why it matters: distributed lock services are often coordination services, not
just conditional-write APIs. Waiters, watches, and leader-election clients can
create herd effects, stuck listeners, and subtle ordering expectations.

Concrete fix:

- State whether `waitMs` is a bounded long-poll, polling wrapper, or real
  server-side wait queue.
- If using wait queues, describe the ordering guarantee: best-effort FIFO,
  priority, or no fairness guarantee.
- Add backpressure for waiters separately from write QPS.
- Mention watch/session behavior for leader-election users: how clients learn
  they lost leadership and how followers learn a leader lock became free.
- Scope fairness explicitly. It is acceptable to say the service provides
  safety and bounded waiting, not strict fair locking.

### 3. Shard movement and membership reconfiguration need one concrete path

Step 7 and the data model now mention `shard_map / group_membership`, controlled
reconfiguration, and safe range movement. That is the right content, but it is
still abstract compared with the clarity of the lease and fencing sections.

Why it matters: key-space sharding is the scalability answer, and unsafe range
movement can create exactly the duplicate-owner problem the lock service exists
to prevent.

Concrete fix:

- Add a short flow for moving a key range: mark source draining, transfer
  snapshot/log tail, install destination owner, update shard map with version,
  and stop serving the source.
- Explain how API routers handle stale shard-map versions: redirect, refresh,
  or reject with retryable error.
- Clarify whether membership changes use joint consensus, one-node-at-a-time
  replacement, or another safe reconfiguration rule.
- Consider adding a small `ShardMap` node in the final diagram, or at least
  mention in the caption that routing uses versioned shard metadata.

### 4. The environment assumptions behind the capacity numbers should be named

The capacity section is now useful and concrete. The remaining weakness is that
the per-group throughput and latency figures depend heavily on deployment
topology, storage durability, and whether the consensus group is single-region
or cross-region.

Why it matters: 10-20K committed ops/sec and p99 20-30ms can be plausible in a
well-tuned single-region setup, but not as a universal promise. A senior answer
should make the assumptions explicit.

Concrete fix:

- State "single-region / one availability-zone set" or "regional quorum" if
  those latency numbers assume local quorum round trips.
- Add a note that cross-region consensus trades much higher p99 latency for
  regional-failure tolerance.
- Say whether writes require fsync per op, group commit, or durable batching.
- Treat the group count as an illustrative sizing pass, then add headroom for
  tail latency, noisy neighbors, and shard imbalance.

## System Design Soundness

The design is fundamentally sound. A CP consensus group is the correct core for
a correctness-critical lock service, and the dataset now avoids the common
mistake of treating lease expiry as a local timer event. State changes,
including expiry, are committed log operations. That makes ownership
linearizable and gives a crisp answer for renew-vs-expire races.

The lease section is especially strong after the update. It covers renewal
cadence, renewal load, false expiry, timeout uncertainty, and the instruction
that a holder must stop acting when it cannot confirm ownership.

The fencing section is also strong. It correctly says the protected resource
must participate by storing the highest accepted token. One useful extension
would be to note that fencing only orders epochs; if guarded writes are retried
or non-idempotent, the resource may still need operation IDs, CAS conditions, or
idempotency at its own boundary.

The scaling story is sound across keys. It correctly says a hot single lock
cannot be horizontally scaled without weakening semantics. The shard-map and
group-membership model are present; the remaining opportunity is to make range
movement and stale-router behavior concrete.

## Step-by-Step Pedagogical Review

### Step 1: Naive: A Lock Row in a Single Database

This is a good baseline. It shows why an atomic row can work in the happy path,
then scopes the rejection to correctness-critical, fleet-wide locks. The added
"this is acceptable for tiny/advisory cases" paragraph prevents the lesson from
sounding absolute.

### Step 2: Consensus-Backed Lock State

This step is now strong. It explicitly says acquire, renew, release, and expire
are all log entries, and it separates authoritative linearizable reads from
stale inspection reads.

The option set is much better after adding titles and tradeoffs. The Redlock
alternative is fairly framed as a timing-dependent design that is unsafe for
critical locks without fencing.

Improvement: align the acquire API sequence with the text by adding the
replicated log participant before applying to lock state.

### Step 3: Leases with TTL (No Permanent Deadlock)

This is one of the strongest steps. It now connects TTL choice to renew load,
latency, false expiry, and dead-holder recovery. The logged-expiry explanation
is precise, and the renew-timeout flow teaches the right operational posture:
ownership is uncertain, so stop acting until confirmed.

Improvement: make the server-side TTL policy visible near the step, not only in
the API description. Min/max TTL and clamping are important because clients
should not be allowed to request pathological TTLs.

### Step 4: Fencing Tokens (The Fundamental Gap)

This is the central insight and it lands well. The sequence now uses distinct
old and new holders, and the text defines the protected resource's
`max_seen_token` state.

Improvement: add one sentence that fencing is not duplicate suppression. It
rejects stale epochs; idempotent resource writes still need operation-level
deduplication or preconditions when side effects are retried.

### Step 5: Leader Election as a Lock

The step cleanly separates the service's internal Raft leader from a
client-facing application leader elected by a lock key. That distinction is
important and worth preserving.

Improvement: describe how leader-election clients observe leadership loss.
Polling, long-poll, watches, or session expiry all have different operational
tradeoffs.

### Step 6: Failure, Partitions, and the Worst Cases

The text now covers leader failure, idempotent retry across failover,
minority-side unavailability, clock skew, and safe membership change. This is a
substantial improvement over the previous review target.

Improvement: add a small flow for a holder stranded on the minority side:
renew cannot reach quorum, client stops acting, majority expires/regrants, and
fencing rejects any late work. That is one of the most interview-worthy failure
stories.

### Step 7: Scaling and Operating the Lock Service

The step now has real sizing math and a realistic operations checklist. The hot
key caveat is stated correctly: sharding scales across keys, not within one
contended key.

Improvements: name the deployment assumptions behind the per-group throughput,
and add a concrete range-migration/reconfiguration path.

## Final Design Review

The final design now integrates the steps coherently. It includes consensus
leader/followers, committed log, applied lock state, leases, logged expiry,
request-id dedup, fencing, protected resource checks, partition behavior,
sharding, compaction, quotas, and CP posture.

The diagram remains intentionally compact. That is fine, but the caption and
view could be slightly richer: a `ShardMap`/routing metadata node would connect
Step 7 to the final architecture, and a `RequestDedup` or "idempotency cache"
node would make retry safety visible. These can stay out of the core diagram if
the text remains explicit, but adding one or two nodes would reduce the gap
between the data model and architecture picture.

## Concept Introduction and Learning Flow

The concept order is excellent:

- atomic single-store lock
- quorum-backed linearizable state
- leases and renewal
- consensus-ordered expiry
- fencing tokens
- lock-based leader election
- CP partition behavior
- key-space sharding and operations

The dataset introduces the hard concepts just in time. It avoids front-loading
Raft detail before the user sees why single-row locking fails, and it waits to
introduce fencing until leases have created the paused-holder gap.

The next teaching improvement is scenario coverage. The text now contains the
right ideas, but more of them should appear as flows: renew timeout, minority
partition, stale release, and shard movement.

## Step-to-Final-Design Coherence

Each step maps cleanly into the final design:

- Step 1 motivates why single-store locking is insufficient.
- Step 2 contributes the leader, followers, log, and applied lock state.
- Step 3 contributes TTL leases, renewal, sweeper, and logged expiry.
- Step 4 contributes fencing tokens and the protected resource contract.
- Step 5 contributes lock-as-leader and token-as-epoch.
- Step 6 contributes majority-only progress, retry behavior, and membership
  change concerns.
- Step 7 contributes key-space sharding, compaction, quotas, and monitoring.

The only weak mapping is visual rather than conceptual: shard metadata, request
dedup, and expiration indexing are in the data model and text but not obvious
in the final design diagram.

## Realism Compared With Production Systems

Compared with Chubby/ZooKeeper-style coordination systems, this is now a strong
teaching case. It correctly treats locking as a linearizable coordination
problem, not a cache-key trick, and it handles the real failure modes: crashed
holders, paused holders, leader failover, partitions, and hot keys.

Remaining realism gaps are bounded:

- Watch/waiter/session behavior is not fully specified.
- Shard migration and stale shard-map handling are described but not stepped
  through.
- API authz/tenant policy is present as authenticated `clientId` and tenant in
  the model, but not developed into permissions or audit behavior.
- Resource-side idempotency for retried guarded writes is not discussed.
- Cross-region vs single-region assumptions are not named for the latency and
  throughput numbers.

These are not foundational flaws. They are the next layer of production detail.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level keys include the expected book fields: `patterns`,
  `interviewScript`, `levelVariants`, `followUps`, `satisfies`, and
  `toProbeFurther`.
- Main step `view.nodes` and `view.links` references resolve.
- Final design `view.nodes`, `view.links`, and `view.groups` references
  resolve.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Dataset-level `patterns[*].steps` references resolve to real step IDs.
- Option titles and tradeoffs are now present where they matter.
- API endpoint sequences are optional per the renderer, but missing sequences
  render placeholders in the API Flows wrap-up. This dataset currently has an
  acquire sequence only.
- There are no generated AI visuals or explainer comic wired for this dataset.
  That is acceptable for the review; it is not required for correctness.

## Recommended Edits, Prioritized

### P1: Add missing API flows

Add structured sequences for renew, release, and linearizable read, and include
the replicated log in the acquire sequence. This is the biggest visible polish
gap because the API contract itself is now strong.

### P1: Define wait/watch/session behavior

Clarify how bounded wait works, whether the service has server-side waiters or
watches, what fairness it does or does not guarantee, and how leader-election
clients observe leadership loss.

### P2: Make shard movement concrete

Add a small flow or step note for safe range migration, stale shard-map
versions, router refresh/redirect behavior, and membership reconfiguration.

### P2: Name deployment assumptions behind capacity

State whether the sizing assumes single-region quorum, local durable storage,
batching/group commit, or cross-region replication. Keep the current numbers as
illustrative estimates, not universal promises.

### P2: Add resource-side retry/idempotency caveat

Fencing prevents stale holders; it does not by itself make non-idempotent
resource writes safe to retry. Add a short note about operation IDs or resource
CAS/idempotency for guarded side effects.

### P3: Enrich Design vs. Requirements summaries

The `satisfies` entries are correct but terse. Update them to mention logged
expiry, request-id retry safety, resource `max_seen_token`, and key-space
sharding so the wrap-up reflects the stronger body content.

## What Not To Change

- Keep the narrow focus on mutual exclusion, leases, fencing, and leader
  election.
- Keep consensus/CP as the chosen design; do not weaken the guarantee to make
  availability easier.
- Keep the single-row baseline and independent-store/Redlock alternatives as
  rejected options for correctness-critical locks.
- Keep fencing tokens as the central insight.
- Keep the final diagram compact unless added nodes materially improve the
  teaching path.

## Bottom Line

The recent updates fixed the major correctness and production-contract gaps.
This is now a strong distributed lock service interview. The next pass should
mostly improve the visible walkthrough: API flows for renew/release/read,
explicit wait/watch semantics, a concrete shard-migration story, and a few
deployment-assumption caveats around capacity.
