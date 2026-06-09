# Review: Authorization Service (RBAC / ABAC) - System Design

Reviewed file: `data/book/authorization/interview.json`
Review date: 2026-06-09

## Executive Summary

This is now a strong, near-flagship book case for a fine-grained
authorization service. The recent changes materially improved the dataset:
requirements now include policy/schema lifecycle and tenant isolation; capacity
now converts headline scale into cache-hit, slow-path, graph-depth,
partitioning, and audit-volume assumptions; the API now includes idempotent
relationship writes and schema writes; the data model now includes chunked
expanded sets, relationship changes, policy versions, and decision audit logs.

The walkthrough has a coherent senior-level arc: start with scattered inline
checks, choose a ReBAC-centered model, make checks fast, use consistency tokens
to honor revokes, materialize reverse indexes for listing, propagate changes
without unbounded fan-out, and close with availability, audit, tenant isolation,
and multi-region freshness.

The remaining work is no longer about missing fundamentals. It is about
sharpening production contracts and teaching the hardest edge cases: symmetric
list-subjects storage, policy/schema rollout mechanics, multi-region token
semantics, SDK fallback safety, batch/filter APIs, and the exact operational
shape of audit at 1M checks/sec.

| Area | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4.5/5 | ReBAC backbone, consistency tokens, cache watermarks, chunked indexes, lifecycle, and audit are all present; remaining gaps are mostly precision. |
| Production realism | 4.3/5 | Much stronger after the API/data-model hardening; still needs crisper multi-region, audit-volume, and list-subjects contracts. |
| Pedagogical flow | 4.5/5 | Each step exposes the next problem, and Step 6 now has real propagation options; a few advanced concepts could be staged more explicitly. |
| Dataset/rendering fit | 4.7/5 | JSON parses; structured views and sequences are clean; link endpoints, `satisfies` refs, pattern refs, and sequence participants resolve. |
| Overall | 4.5/5 | A high-quality authorization interview with focused polish remaining before it feels fully production-grade. |

## What Works Well

The core teaching choice is exactly right. The interview does not stop at RBAC;
it pushes into relationship tuples, namespace schemas, relation rewrites,
bounded graph reachability, zookie-style tokens, reverse indexes, and
change-log-driven materialization.

The recent API update materially improves correctness. `POST /v1/relationships:write`
now has an `idempotencyKey`, actor/reason/request IDs, conditional tuple
updates, tuple versions, change IDs, and returned tokens. That is the right
shape for a security-sensitive write path that will be retried and audited.

The freshness story is now much clearer. Step 4 explicitly says that cache
entries, index shards, and regions carry applied-version watermarks, and that a
`min_token` check must wait, route, re-evaluate, or fail retryably instead of
serving a stale allow.

The data model is no longer just conceptual. `relation_tuples`,
`policy_versions`, `expanded_set_chunks`, `relationship_changes`, and
`decision_audit_log` give the reader concrete state to map back to the API and
architecture.

The capacity section now teaches design-driving math. The added assumptions for
99% cache hit rate, roughly 10k/s slow-path load, graph-depth/fan-out caps,
p99 latency budget, tuple-store partitioning, and audit volume give candidates
something defensible to reason from.

The Step 6 propagation update is a major pedagogical improvement. Eager fan-out,
lazy versioned revalidation, and hybrid priority-based materialization are real
alternatives and make the fan-out problem teachable rather than just named.

## Highest-Impact Issues

### 1. The list-subjects side is still thinner than the list-objects side

The requirements ask for both "list the objects a subject can access" and "the
subjects who can access an object." The dataset now models chunked
subject-to-object indexes well, but the object-to-subject side is mostly
described as symmetric rather than modeled.

Why it matters: object-to-subject listing is common in sharing UIs, admin
reviews, incident response, access reviews, and compliance exports. Its storage
and fan-out shape is not identical to subject-to-object listing. A document
shared with a large group may have a compact tuple but millions of effective
subjects, and expanding that naively can be prohibitive.

Concrete fix:

- Add a `subject_set_chunks` or `object_access_chunks` record shape for
  `(tenant, object, relation, subject_type, shard) -> subject ids/set refs`.
- Clarify whether object-to-subject answers return direct grants, effective
  subjects, or both.
- Add pagination and `servedAtToken`/`min_token` semantics for list-subjects.
- State that large group grants may return set references plus optional
  expansion, instead of always materializing every effective user.
- Add a `POST /v1/list-subjects` API example to match the requirement.

### 2. Multi-region consistency is good conceptually but needs a sharper contract

Step 7 correctly says each region has applied-version watermarks and that a
lagging region waits, routes, or fails retryably for `min_token` checks. That is
the right principle, but the production contract is still compressed.

Why it matters: global authorization services fail in the gaps between local
latency, global ordering, replicated tuple stores, cache watermarks, and SDK
fallback. The dataset should prevent readers from thinking that "replicated
regionally" automatically implies revoke-safe global behavior.

Concrete fix:

- Name the token source: a globally ordered change log, per-tenant ordered log,
  or region-primary log with replication.
- State whether writes are pinned to a home region/tenant shard or accepted in
  multiple regions with conflict resolution.
- Define the `min_token` timeout behavior: wait budget, route-to-home-region,
  retryable error, or deny/step-up for sensitive actions.
- Distinguish default stale reads from sensitive reads during SDK-cache fallback.
  A fail-closed miss is safe, but a cached allow during an outage needs a
  sensitivity class, TTL, and watermark/expiration rule.
- Add one sequence or deep-dive note for "check lands in a lagging region with
  `min_token`."

### 3. Policy/schema lifecycle is present but could become more operational

The requirements, API, data model, Step 7, and final design now mention staged
policy/schema versions. That resolves the prior gap. What remains is the exact
rollout workflow.

Why it matters: policy rollout bugs are central-authz incidents. A bad rewrite
can accidentally over-grant or deny many applications. A senior answer should
show how a new schema is validated before activation and how decisions are
compared during shadow mode.

Concrete fix:

- Add validation constraints for schema writes: no invalid relations, recursion
  budget, cycle handling, and migration compatibility.
- Define shadow evaluation: evaluate old and candidate policy versions, compare
  allow/deny deltas, emit metrics, then promote.
- Add rollback semantics: what happens to decisions cached under the rolled
  back policy version.
- Include policy version in the cache key and in every decision audit record
  consistently.
- Consider a small "Policy control plane" node or rename `RoleStore` to
  `Policy/Schema Store` so the diagram matches the stronger data model.

### 4. The API should include batch/filter and explain/debug paths

The four API examples are much stronger than before. They cover single check,
relationship write, list-objects, and schema write. The remaining missing API
surface is what production callers usually need after the first integration.

Why it matters: apps rarely authorize only one object at a time. They filter
search results, render pages of candidate objects, debug surprising decisions,
and run access reviews. Without batch/filter and explain paths, the interview
still leaves some of the hardest caller workflows implicit.

Concrete fix:

- Add `POST /v1/check:batch` or `POST /v1/filter-objects` for a bounded
  candidate set.
- Add `POST /v1/list-subjects` as noted above.
- Expand the `explain` flag into a response shape: matched path, policy
  version, tuple versions, reason code, caveats evaluated, and redaction rules.
- State that explain/debug may be privileged and rate-limited because it can
  reveal relationship structure.

### 5. Audit at 1M checks/sec needs a cost and retention policy

The data model now includes `decision_audit_log`, and the capacity section
explicitly notes that logging every decision at 1M records/sec drives tiered
retention. That is the right warning. It should become a concrete operating
choice.

Why it matters: full decision logging can dominate storage and ingest cost.
Some environments need every decision durably logged; others need sampled
allows, full denies, full admin changes, and reconstructable provenance. The
right answer depends on compliance and product risk.

Concrete fix:

- Add a retention split: hot searchable log, cold object storage, and deletion
  policy.
- Decide whether allow decisions are all logged, sampled, or aggregated by
  default; keep full logs for denies/admin/sensitive actions.
- Include asynchronous audit ingestion/backpressure behavior. The Check API
  should not block every permission check on cold audit storage.
- Add privacy controls for subjects, object identifiers, and reason/debug
  traces.

## System Design Soundness

The functional requirements are now strong. They cover permission checks,
RBAC/ABAC/ReBAC, grant/revoke, list objects/list subjects, centralized policy,
policy/schema authoring and rollback, decision audit, and tenant isolation.
Those are the right requirements for a shared authorization service.

The non-functional requirements are also appropriate: sub-10ms p99, 1M+
checks/sec, deny-by-default correctness, bounded staleness with opt-in
freshness, and high availability. The added capacity assumptions make these
requirements actionable instead of decorative.

The architecture is directionally production-realistic. Stateless Check API,
client SDK cache, decision cache, policy engine, tuple store, policy store,
ordered change log, materializer, and expanded-set index are the right
components. The design avoids the common mistake of answering list queries with
N single-object checks.

The data model now supports most promised behavior. It has authoritative
tuples, versioned policies, chunked reverse index shards, relationship change
records, and decision audit records. The main model-level gap is the
object-to-subject listing shape and the precise representation of policy
rollout/shadow metrics.

The consistency model is the strongest part. The dataset correctly separates
default fast checks from `min_token` checks and makes watermarks the safety
mechanism rather than relying on best-effort invalidation.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Hardcode Permission Checks in Each Service

This baseline is effective. It now explicitly names inconsistent logic,
redeploy-heavy policy changes, per-object expressiveness limits, and missing
decision audit. That cleanly motivates centralization.

Small improvement: mention tenancy early. Scattered checks often also scatter
tenant-boundary assumptions, which sets up the later tenant-isolation
requirement.

### Step 2: Choose the Authorization Model

This is a strong step. RBAC, ABAC, and ReBAC are compared honestly, and the
selected hybrid is credible: relationship tuples as the source of truth, with
RBAC and ABAC layered where they fit.

The recent addition of namespace schemas and relation rewrites is important.
The examples make graph reachability concrete and prevent the dataset from
treating ReBAC as just "tuples in a table."

Improvement: add one warning about schema migration. Relation rewrites are not
just evaluation rules; they are versioned contracts used by many applications.

### Step 3: The Low-Latency Check Path

The step now has the right mechanics: bounded graph walk, depth and fan-out
caps, cycle detection, negative caching, policy-versioned cache keys, and
caching of group membership, relation rewrites, and compiled policies.

The options teach a useful trade-off among decision caching, precomputed
reachability, and live graph walks. The default choice is sensible because it
keeps the hot path fast without requiring every check to be fully materialized.

Improvement: add one sentence about hot-key protection. A popular document,
tenant, or group can concentrate traffic even when total QPS is manageable.

### Step 4: Consistency: Honor Revokes Safely

This step is now very strong. It makes the "stale allow after revoke" hazard
explicit and uses consistency tokens plus applied-version watermarks as the
correct guarantee.

The sequence diagram is also stronger than before: it shows the cache watermark
check, fresh evaluation through the policy engine and tuple store, and a deny
when the revoke is honored. That is the right concrete flow.

Improvement: include the exact behavior when the fresh path cannot complete
within the latency budget. A retryable consistency error is mentioned in prose;
the fallback decision matrix could be clearer.

### Step 5: Listing Accessible Objects (Reverse Index)

The listing step improved substantially. It now talks about scoped listing,
chunked index records, pagination, candidate-set filtering, ABAC caveats, and
`min_token` freshness for index shards.

The main remaining issue is symmetry. The requirement includes listing subjects
who can access an object, but the step and data model are centered on
subject-to-objects. Make the object-to-subject answer explicit, including when
the service returns direct grants versus fully expanded subjects.

### Step 6: Change Propagation and Materialization

This is one of the most improved steps. The previous version mostly named
change propagation; the current version provides real options: eager fan-out,
lazy versioned revalidation, and hybrid priority-based materialization.

The options are realistic and interview-teachable. They expose exactly the
trade-off senior candidates should discuss: write amplification and invalidation
storms versus read-path revalidation and freshness complexity.

Improvement: say how materializer lag is monitored and alerted. Watermark lag
per tenant/namespace/relation is a natural SLO for this system.

### Step 7: Availability, Auditing, and Multi-Region

This step now does more than say "run it in multiple regions." It ties regional
serving to watermarks, names policy lifecycle, threads tenant IDs through state,
and introduces decision audit/explainability.

The fail-closed, fail-open, and multi-region options are useful. The default
should remain fail-closed with cached fallback, with fail-open framed only for
low-stakes surfaces.

Improvement: make the SDK-cache fallback policy more explicit for sensitive
actions. A recent cached allow during an authz outage may be acceptable for a
low-risk read but not for admin, delete, payment, or data export actions.

## Final Design Review

The final design now integrates the walkthrough well. It includes the SDK, Check
API, decision cache, policy engine, relationship store, role/policy store,
change log, materializer, expanded-set index, admin writer, tenant isolation,
policy rollout, decision audit, cache/index/region watermarks, and
deny-by-default failure posture.

The final view is still visually compressed. Audit, policy/schema lifecycle,
and multi-region replication are described in prose and data model fields but
do not have first-class visual representation. That is acceptable for a clean
diagram, but the labels should be precise enough that readers see where those
concerns live.

Recommended small diagram polish:

- Rename `Role / Policy Store` to `Policy / Schema Store` or make the caption
  explicit that this includes versioned namespace schemas and rollout state.
- Consider adding an `AuditLog` node only if the diagram remains readable.
- Consider adding a "regional replicas/watermarks" caption note rather than a
  new cluster of boxes.

## Concept Introduction and Learning Flow

The concept order is strong:

- RBAC/ABAC/ReBAC and centralized authorization.
- Namespace schema and relation rewrites.
- Bounded graph-walk checks with versioned caching.
- Consistency tokens and applied-version watermarks.
- Expanded-set indexes for listing.
- Change-log materialization and invalidation.
- Decision audit, policy lifecycle, tenant isolation, and multi-region serving.

The learning flow now works for senior and staff-level discussions. The case
starts simple and introduces each mechanism when the previous step creates the
need for it.

Two concepts could be reinforced:

- Policy shadowing: how old and candidate policy versions are evaluated and
compared before activation.
- Effective access expansion: the difference between direct grants, group/set
references, and fully expanded users/objects.

## Step-to-Final-Design Coherence

The step-to-final mapping is coherent:

- Step 2 introduces `PolicyEng`, `RelStore`, `RoleStore`, and the schema model.
- Step 3 introduces `SDK`, `CheckAPI`, and `DecisionCache`.
- Step 4 introduces `ChangeLog`, tokens, and watermark-gated cache reads.
- Step 5 introduces `ExpandIdx` and chunked list indexes.
- Step 6 introduces `Indexer` and propagation strategies.
- Step 7 ties in HA, regional watermarks, tenant isolation, lifecycle, and audit.

The `satisfies` section now maps the previously implied requirements explicitly,
including centralized policy, policy lifecycle/audit/tenant isolation, and high
throughput. That is a useful improvement for the wrap-up page.

The remaining coherence gap is mostly naming: the final architecture has one
`RoleStore` box for roles, policy, and schema versions, while the data model has
more precise `policy_versions`. Either rename the node or use captions to
bridge the terminology.

## Realism Compared With Production Systems

Compared with Zanzibar-inspired production systems, the design has the right
backbone: relationship tuples, namespace/rewrite logic, bounded graph
evaluation, consistency tokens, cached reads, derived indexes, and
change-log-driven propagation.

The dataset now also includes practical production details that many
authorization interviews skip: idempotent writes, conditional revoke semantics,
change IDs, decision IDs, policy versions, tenant IDs, chunked indexes, audit
records, cache watermarks, and materializer fan-out trade-offs.

The remaining realism caveats are narrower:

- Full decision audit at 1M checks/sec needs retention, sampling, and
  backpressure policy.
- Object-to-subject expansion can be much more expensive than the
  subject-to-object path suggests.
- Multi-region writes and `min_token` routing need an explicit global-ordering
  contract.
- Shadow policy evaluation and rollback need cache invalidation semantics.
- Explain/debug APIs need privilege checks and redaction.
- Hot-key, per-tenant quota, and materializer-lag operations could be called
  out more directly.

## Dataset and Renderer-Facing Observations

The JSON parses successfully. The dataset follows the project conventions:
architecture steps use structured `view` objects, flows use structured
`sequence` data, and raw Mermaid is limited to overview diagrams.

Structural checks were clean:

- No missing high-level node IDs in step views.
- No missing high-level link IDs in step views.
- No high-level link endpoint omitted from a step view that references the link.
- No unresolved `satisfies[*].steps[*]` references.
- No unresolved pattern `steps[]` references.
- Sequence participants and nested message `from`/`to` endpoints resolve.

The previous review's two view-link endpoint issues have been fixed. Step
`consistency` now includes the needed inline ChangeLog -> DecisionCache version
edge, and Step `availability` no longer references `policy-role` without
including `PolicyEng`.

The probe links are now well targeted: Zanzibar, OPA, Cedar, SpiceDB, and SRE
monitoring all fit the case. The earlier OAuth confusion is gone.

AI visuals are absent, but those are optional. No docs rebuild is needed for
this review-only update.

## Recommended Edits, Prioritized

### P1: Add the list-subjects contract

Add a `POST /v1/list-subjects` API example and a data-model shape for
object-to-subject results. Clarify direct grants versus effective subjects, set
references versus full expansion, pagination, and `min_token` behavior.

### P1: Tighten multi-region freshness semantics

Name the global/per-tenant ordering source, write routing model, lagging-region
behavior, retry/timeout policy, and SDK fallback safety classes for sensitive
actions.

### P2: Make policy rollout operational

Add shadow-evaluation mechanics, validation constraints, delta metrics,
rollback cache behavior, and rollout/audit fields for schema writes.

### P2: Add batch/filter and explain APIs

Include a bounded candidate-set filter or batch-check endpoint, and expand
`explain` into a privileged response shape with matched path, versions, caveats,
and redaction limits.

### P2: Define audit retention and backpressure

Turn "log every decision" into an explicit policy: full versus sampled logs,
hot/cold retention, async ingestion, failure behavior, and privacy controls.

### P3: Polish final diagram terminology

Rename or caption `RoleStore` so readers understand it includes versioned
policies and namespace schemas. Add an audit node only if it does not clutter
the final design.

### P3: Add operational SLO notes

Mention materializer watermark lag, cache hit rate, slow-path QPS, hot keys,
per-tenant quotas, and explain/debug rate limits as operational signals.

## What Not To Change

Keep the ReBAC-first framing. It is the right answer for object-level sharing
and gives the case more depth than a pure RBAC design.

Keep the consistency-token teaching point central. It is the strongest senior
signal in the dataset.

Keep the reverse-index step. Listing accessible objects is a real requirement
that many authorization interviews miss.

Keep Step 6's propagation options. They now turn a hard production issue into a
clear interview trade-off.

Keep the fail-closed default posture. The dataset correctly treats fail-open as
a narrow, low-stakes exception rather than the default authorization behavior.

## Bottom Line

The recent changes moved this review from "good foundation with missing
production contracts" to "strong, production-aware case with focused polish."
The dataset now teaches the right architecture and most of the right operating
mechanics. The next pass should concentrate on list-subjects symmetry,
multi-region token semantics, policy rollout workflow, batch/explain APIs, and
audit economics.
