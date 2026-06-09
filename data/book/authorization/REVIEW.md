# Review: Authorization Service (RBAC / ABAC) - System Design

Reviewed file: `data/book/authorization/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong book-quality foundation for a fine-grained authorization
interview. The arc is coherent: start with scattered inline checks, choose a
central ReBAC/RBAC/ABAC model, make checks fast, add consistency tokens for
revokes, add reverse indexes for listing, propagate changes, and close with
availability and audit concerns.

The biggest improvement opportunity is turning the Zanzibar-style concepts into
more precise production contracts. The dataset currently explains the right
ideas, but several high-risk mechanisms are still compressed: write
idempotency, policy/schema versioning, cache freshness watermarks, reverse-index
storage shape, multi-region behavior, and audit records. Those are exactly the
details that distinguish a senior authorization-system answer from a conceptual
one.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.1/5 | Correct ReBAC-centered architecture with caching, tokens, materialization, and deny-by-default; needs sharper write, listing, schema, and audit mechanics. |
| Production realism | 3.7/5 | Good core hazards are named, especially stale allows after revoke, but operational contracts and data ownership are still thin. |
| Pedagogical flow | 4.3/5 | Clear step progression and useful options; Step 6 and Step 7 pack several hard choices into prose rather than teachable trade-offs. |
| Dataset/rendering fit | 4.0/5 | JSON parses and most references resolve; two views reference links whose endpoints are missing from the view node list. |
| Overall | 4.0/5 | Strong and usable, with a focused hardening pass needed before it feels like a flagship case. |

## What Works Well

The central teaching choice is right. The interview does not stop at RBAC; it
pushes toward relationship tuples, graph reachability, consistency tokens, and
expanded-set indexes, which are the relevant primitives for modern
fine-grained authorization.

The step sequence has a good cause-and-effect shape. Each step exposes the next
problem: hardcoded checks motivate centralization, ReBAC introduces graph-walk
latency, caching introduces stale revoke risk, consistency tokens expose
listing cost, listing creates derived-state propagation, and propagation raises
availability and multi-region questions.

The options are mostly real trade-offs rather than strawmen. RBAC, ABAC, and
ReBAC are compared honestly; cache versus materialization versus live graph walk
shows the hot-path tension; TTL, token, and async invalidation explain the
freshness spectrum; fail-closed, fail-open, and multi-region options frame the
security/availability trade-off.

The final design integrates the main components introduced in the walkthrough:
SDK, Check API, Policy Engine, relationship store, role/policy store, decision
cache, change log, materializer, and expanded-set index.

## Highest-Impact Issues

### 1. The write/API contract is too thin for a correctness-critical service

The dataset has three API examples: `POST /v1/check`, `POST /v1/relationships`,
and `POST /v1/list-objects`. That is enough to explain the shape of the system,
but not enough to make the correctness story operational.

Why it matters: authorization writes are security-sensitive and often retried.
A grant or revoke endpoint needs idempotency, preconditions, versioning, audit
identity, and clear delete semantics. Without those details, it is unclear how
the system handles duplicate revoke requests, concurrent policy edits, schema
changes, conditional grants, or "revoke if tuple still exists at version X".

Concrete fix: expand the write contract slightly:

- Add `idempotencyKey`, `operation` (`create` / `delete`), `expectedVersion` or
  `precondition`, `actor`, `reason`, `tenant`, and `requestId` to relationship
  writes.
- Return `token`, `tupleVersion`, and a stable `changeId`.
- Add a small policy/schema write example or note: namespace definitions,
  relation rewrites, policy versions, rollout state, and rollback.
- Add `decisionId`, `checkedAtToken`, and optional `explain` / `debugTrace` to
  check responses for audit and support.

### 2. Consistency tokens are introduced correctly, but the freshness mechanics need precision

Step 4 has the right concept: writes return a token, and checks can require
freshness at least as recent as that token. The prose also correctly avoids
globally strong checks for every request.

The weak spot is the mechanism behind the guarantee. Some option language says
cache entries are invalidated "the moment" tuples change, but Step 6 also says
invalidation is asynchronous. Both cannot be the default guarantee. The precise
guarantee should be: a check with `min_token` must use a serving path whose
watermark is at or beyond that token, or bypass/wait/fail explicitly.

Why it matters: this is the most important security property in the interview.
If the system claims revokes are honored but does not define cache watermarks,
regional lag, fallback behavior, and timeout policy, the answer can sound safer
than it is.

Concrete fix: add a compact freshness model:

- Each cache/index/region has an applied version watermark.
- Default checks may use cached decisions up to a bounded staleness window.
- A `min_token` check can use cache only if the cache entry and region watermark
  are fresh enough.
- If the local region is behind, the service waits briefly, routes to a fresher
  region/source, or returns a retryable consistency error rather than serving a
  stale allow.
- The Step 4 sequence should show the fresh-evaluation path through Policy
  Engine / Tuple Store, not only "bypass" followed by "deny".

### 3. Capacity numbers are not yet converted into design-driving sizing

The capacity section gives useful headline targets: 1M+ checks/sec, sub-10ms
p99, billions of tuples, reads much greater than writes, and tunable
consistency. It does not yet turn those assumptions into concrete constraints
for cache hit rate, tuple-store reads, graph depth, partitioning, or change-log
throughput.

Why it matters: a candidate can name 1M checks/sec without showing whether the
design can meet it. Authorization systems often fail in the read amplification:
one check may require multiple tuple lookups, group expansions, cache probes,
and policy loads. Listing can create huge result sets, and group changes can
create large invalidation fan-out.

Concrete fix: add a few derived assumptions:

- Target cache hit rate, slow-path QPS, and max graph depth/fan-out.
- A p99 latency budget across SDK cache, network, Check API, decision cache,
  policy evaluation, and tuple-store reads.
- Tuple-store partitioning by object namespace/object id and secondary access
  patterns for subject membership.
- Change-log partition count or consumer parallelism based on write/update
  volume.
- Audit log storage rate and retention tiers if every decision is logged.

### 4. The reverse-index/listing design needs a more realistic storage and consistency shape

Step 5 identifies the right problem: "list what this subject can access" cannot
be implemented as millions of per-object checks. The expanded-set index is the
right interview answer.

The current data model stores `object_ids` as a `set<string>` under
`expanded_sets`. That is too abstract for the scale the dataset claims. A
single subject may have millions of objects; a large group change may touch many
subjects; ABAC predicates may not be enumerable; and pagination/filtering need a
stable index shape.

Why it matters: listing is often the hardest part of authorization systems. It
is easy to promise a reverse index and accidentally hide the storage,
pagination, freshness, and recomputation complexity.

Concrete fix: model expanded access as chunked/indexed records, not one giant
set. For example: `(tenant, subject, relation, objectType, shard/pageToken) ->
objectIds`, plus reverse `object -> subjects` records when needed. Add notes on:

- list consistency with `min_token`;
- pagination and stable ordering;
- partial indexes for common object types/relations;
- fallback to candidate-set filtering when the caller already has a small set;
- ABAC/caveated rules that cannot be fully materialized.

### 5. Audit, policy lifecycle, and multi-tenancy are named but not first-class

The final design says the service is auditable and regionally replicated, and
Step 7 mentions logging who-can-do-what-and-why. But there is no audit-log
table, decision record, policy/schema version table, tenant boundary, or policy
rollout workflow in the API/data model.

Why it matters: central authorization is a control plane as much as a data
plane. Operators need to test a policy, roll it out safely, explain a decision,
rollback a bad schema, prove who changed access, and isolate tenants. Those are
common senior follow-up areas.

Concrete fix: add one small "control plane" slice:

- `policy_versions` / `namespace_schema_versions` with status
  (`draft`, `shadow`, `active`, `rolled_back`).
- `decision_audit_log` with `decisionId`, subject, object, relation/action,
  policy version, tuple version, result, reason code, request ID, caller, and
  latency.
- `relationship_changes` or an explicit change-log record model with actor,
  reason, operation, old/new tuple, token, and timestamp.
- Tenant IDs in tuples, policies, cache keys, and list indexes.

## System Design Soundness

The requirements are well scoped for a central authorization service. They cover
permission checks, RBAC/ABAC/ReBAC, grant/revoke, list objects/list subjects,
central policy, low latency, high throughput, deny-by-default, freshness knobs,
and availability.

The main missing requirement-level concern is policy lifecycle. The dataset
does not explicitly ask for testing, shadow evaluation, rollout, rollback, or
explainability, even though these are central to operating a shared
authorization service. It also treats tenancy as implied. For a book interview,
that is worth making explicit.

The architecture is directionally sound. A stateless Check API plus SDK cache is
the right hot path, and an ordered change log plus materializer is the right
spine for cache invalidation and list indexes. The design correctly avoids
doing list authorization through N checks over a large corpus.

The data model is the thinnest part. `relation_tuples`, `roles_policies`, and
`expanded_sets` explain the concept, but not enough production state. It should
represent tuple lifecycle, policy/schema versions, caveats/conditions, change
records, audit decisions, tenancy, and index chunking.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Hardcode Permission Checks in Each Service

This is a good baseline. It makes the failure mode obvious: inconsistent logic,
poor auditability, redeploys for policy changes, and inability to express
per-object sharing.

Small improvement: mention that this baseline also lacks a decision log. That
would set up auditability as a recurring design goal rather than something that
appears mostly at the end.

### Step 2: Choose the Authorization Model

This is one of the strongest steps. RBAC, ABAC, and ReBAC are framed clearly,
and the selected answer is credible: relationship tuples as the source of truth,
with RBAC and ABAC layered where appropriate.

The next improvement is schema precision. ReBAC systems need namespace/object
type definitions and relation rewrites, not just tuples. A short example such
as `document#viewer includes group#member` or `folder#editor implies
document#editor` would make "graph reachability" concrete and prepare the
reader for cycle/depth limits.

### Step 3: The Low-Latency Check Path

The step correctly focuses on cached, bounded graph walks and SDK-side caching.
The options teach the right tension among decision cache, precomputed index, and
live graph traversal.

The step needs more hot-path mechanics. Add cache key shape
(`tenant, subject, relation/action, object, policyVersion, minToken`), negative
caching rules, graph depth/fan-out limits, and what gets cached besides final
decisions: tuple pages, group membership, relation rewrites, and compiled
policies.

### Step 4: Consistency: Honor Revokes Safely

This is the critical step, and the dataset chooses the right teaching primitive:
consistency tokens. The trade-off among token freshness, TTL, and async
invalidation is useful.

The step should be stricter about what happens when a fresh check cannot be
served locally. A stale deny is usually safe but painful; a stale allow after
revoke is the security failure. The check path should return deny, wait, route,
or fail based on a clearly stated safety policy, not imply the cache can always
decide.

Renderer note: the Step 4 view references the high-level `indexer-cache` link,
whose source is `Indexer`, but `Indexer` is not in that view's `nodes` list. Add
`Indexer` to the view or replace the link with an inline Check API/cache version
comparison.

### Step 5: Listing Accessible Objects (Reverse Index)

The problem and selected direction are correct. The step clearly explains why
per-object checks do not scale and why a materialized subject-to-objects index
is needed.

The step would benefit from acknowledging that list answers are often scoped:
object type, relation, tenant, collection/folder, search query, or candidate
set. Without that, `list-objects` sounds like a universal full-corpus query.
Add pagination, chunking, freshness tokens, and the caveat that ABAC predicates
may require filtering or partial materialization.

### Step 6: Change Propagation and Materialization

The prose connects the change log, materializer, reverse index, and cache
invalidation well. The failure drill for a widely shared group change is useful.

This step has no options even though the design space is rich. Consider adding
two or three alternatives: eager fan-out invalidation, lazy versioned
revalidation, and hybrid priority-based materialization. That would turn the
fan-out warning into a teachable trade-off.

### Step 7: Availability, Auditing, and Multi-Region

The fail-closed versus fail-open versus multi-region comparison is important
and practical. The default choice should remain conservative: serve bounded
cached decisions where acceptable, deny or step-up on misses, and avoid silent
over-grants for sensitive actions.

This step combines three topics that each deserve a little structure:
availability fallback policy, regional freshness, and audit/control plane. The
view also references `policy-role`, whose source is `PolicyEng`, but
`PolicyEng` is not in the view's `nodes` list. Add `PolicyEng` or replace the
link with an inline Check API -> RoleStore edge.

## Final Design Review

The final design is coherent with the main walkthrough. It includes the hot
path, authoritative stores, derived index, change log, and materializer. The
description does a good job summarizing default cached reads plus opt-in fresh
reads.

The final design overstates a few capabilities relative to the diagram/data
model. It says the service is auditable and regionally replicated, but the final
view has no audit log, no decision record store, no region-local replicas, no
replication/link watermark component, and no policy/schema control plane. Those
do not all need to become separate boxes, but at least audit and policy version
state should appear somewhere because they are central to the service's
operational trust.

## Concept Introduction and Learning Flow

The concepts are introduced in a good order: RBAC/ABAC/ReBAC, cached graph
walks, consistency tokens, reverse indexes, and change-log materialization. The
terms are short and clear enough for a reader to retain.

Two concepts should be added or expanded:

- Namespace/schema and relation rewrites: how object types define valid
  relations and inheritance.
- Decision explainability/audit: how the service explains and records why a
  decision was allow or deny.

The probe links are credible overall, especially Zanzibar, OPA, Cedar, and
SpiceDB. The OAuth RFC is less directly useful for this dataset's object-level
authorization focus and appears on steps where it may confuse delegated OAuth
flows with fine-grained application authorization. Use it only if a step
explicitly discusses OAuth scopes/delegation, or replace it with a more direct
policy/authz-system reference.

## Step-to-Final-Design Coherence

The main step-to-final-design mapping is strong:

- Step 2 introduces `PolicyEng`, `RelStore`, and `RoleStore`.
- Step 3 introduces `SDK`, `CheckAPI`, and `DecisionCache`.
- Step 4 introduces `ChangeLog` and token freshness.
- Step 5 introduces `ExpandIdx`.
- Step 6 introduces `Indexer` as the derived-state maintainer.
- Step 7 closes with regional availability and safe fallback.

The coherence gaps are mostly around things introduced in prose but not carried
into the final design: audit, multi-region replication, policy/schema lifecycle,
and tenant isolation.

The `satisfies` section also misses a couple of direct mappings. It maps most
functional and non-functional requirements, but should explicitly cover
"Centralized policy used by many applications" and "High throughput (1M+
checks/sec)" rather than leaving them implied by the Check API and caches.

## Realism Compared With Production Systems

Compared with production systems such as Zanzibar-inspired services, the design
has the right backbone: relationship tuples, bounded graph evaluation, zookie-
style tokens, cached reads, and change-log-driven materialization.

The realism gaps are in lifecycle and edge cases:

- Relation schema evolution and policy rollout are not modeled.
- Tuple writes are not idempotent or conditional.
- Graph evaluation limits, cycle handling, and recursion budgets are not
  specified.
- Cache freshness watermarks are not explicit.
- Large group/folder fan-out is named but not designed around.
- Audit logs and decision explanations are not represented as state.
- Tenant isolation and per-tenant quotas are absent.
- Privacy/retention for decision logs and relationship tuples is not discussed.

These are not reasons to discard the design. They are the natural next pass for
turning a good conceptual interview into a production-grade one.

## Dataset and Renderer-Facing Observations

The JSON parses successfully. Top-level structure is consistent with the
project's dataset shape, and the file uses structured `view` and structured
`sequence` fields rather than raw Mermaid diagrams for architecture steps and
flows.

Structural checks found no missing high-level node IDs, no missing high-level
link IDs, no unresolved `probeLinks`, no unresolved pattern step references, and
no sequence participants outside the high-level architecture nodes.

Two view-link endpoint issues should be fixed:

- Step `consistency` references link `indexer-cache` (`Indexer` ->
  `DecisionCache`) but omits `Indexer` from `view.nodes`.
- Step `availability` references link `policy-role` (`PolicyEng` ->
  `RoleStore`) but omits `PolicyEng` from `view.nodes`.

Depending on renderer behavior, these links can create an unintended implicit
node or produce a visually confusing edge. The local fix is small: include the
missing endpoint node in the view or use an inline link whose endpoints are both
present.

AI visuals are absent, but those are optional. No docs rebuild is needed for
this review file alone.

## Recommended Edits, Prioritized

### P1: Harden the correctness contract

Add idempotent/conditional relationship writes, check response metadata,
policy/schema versions, and explicit consistency-token serving behavior.

### P1: Fix the two view-link endpoint issues

Update Step `consistency` and Step `availability` so every referenced link has
both endpoint nodes included in that view.

### P2: Make capacity drive concrete sizing

Turn 1M+ checks/sec and sub-10ms p99 into cache hit-rate targets, slow-path QPS,
tuple-store partitioning, graph depth/fan-out limits, change-log throughput,
and audit storage/retention.

### P2: Deepen listing and materialization

Replace the conceptual `object_ids` set with chunked, paginated index records;
add list freshness, candidate filtering, ABAC caveats, and group-change fan-out
strategy.

### P2: Add audit and policy lifecycle state

Add decision audit records, relationship change records, policy/schema version
records, and a short rollout/rollback note.

### P3: Rebalance Step 6 and Step 7

Give Step 6 explicit propagation/materialization options, and separate Step 7's
availability, regional freshness, and audit concerns enough that each becomes
interview-teachable.

### P3: Tune probe links and wrap-up mapping

Use OAuth only where delegated authorization/scopes are actually discussed, and
add explicit `satisfies` mappings for central policy and high throughput.

## What Not To Change

Keep the ReBAC-first framing. It is the right answer for object-level sharing
and gives the interview more depth than a pure RBAC design.

Keep the consistency-token teaching point. This is the strongest senior-level
signal in the dataset and should stay central.

Keep the reverse-index step. Listing accessible objects is a real requirement
that many authorization interviews miss.

Keep the fail-closed default posture. The dataset correctly treats fail-open as
a limited, low-stakes exception rather than the default behavior for sensitive
authorization.

## Bottom Line

This interview is already a solid authorization-system walkthrough. A focused
hardening pass should make the API/data model more operational, sharpen the
freshness guarantee, make capacity drive sizing, fix the two view endpoint
issues, and promote audit/policy lifecycle from prose into first-class design
state.
