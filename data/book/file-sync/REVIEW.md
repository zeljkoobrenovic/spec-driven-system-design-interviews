# Review: Dropbox / File Sync - System Design

Reviewed file: `data/book/file-sync/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a solid core walkthrough for a Dropbox-style file sync interview. The
main teaching arc is clear: start with whole-file upload, introduce
content-addressed chunks, deduplicate through a chunk index, split metadata from
bytes, sync by cursor and chunk manifests, notify devices, and close with GC and
durability. That is the right spine for this problem.

The dataset is not yet as production-complete as the stronger book cases. The
largest gap is scope coherence: sharing is listed as a functional requirement
and appears in the requirements diagram, but the design does not actually model
shared folders, ACLs, permission changes, public links, or the effect of sharing
on namespaces and conflict handling. Capacity is also too qualitative for a
book-level case: it says "billions" and "exabytes" but does not convert that
into chunk counts, metadata writes, block writes, notification fanout, CDN
egress, or database/shard sizing.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 3.8/5 | Strong chunking, dedup, metadata/block split, sync, conflicts, and GC; incomplete sharing, metadata schema, capacity math, and operations/security story. |
| Production realism | 3.45/5 | Good default mechanisms, but missing ACL workflows, quotas, abuse controls, observability, encryption implications, and exact refcount/commit invariants. |
| Pedagogical flow | 4.15/5 | Steps build cleanly and expose the next risk well; more flows/failure drills would make production edges teachable. |
| Dataset/rendering fit | 4.2/5 | JSON parses and most references resolve; one diagram view has a missing endpoint and `satisfies` omits stated requirements. |
| Overall | 3.9/5 | A useful file-sync case with a strong core, but it needs a sharing/capacity/operations hardening pass before it feels book-complete. |

## What Works Well

- The step order is natural and interview-friendly. Each step removes a concrete
  weakness from the previous one: whole-file transfer, redundant storage,
  missing metadata structure, slow sync, conflict ambiguity, and unsafe deletes.
- Content-defined chunking is presented as the default, with a meaningful
  fixed-size alternative. The trade-off is not a strawman: implementation cost
  versus dedup stability is the right comparison.
- The metadata/data split is correctly framed as the architectural backbone.
  "Upload chunks first, commit metadata last" is exactly the kind of correctness
  nuance interviewers expect.
- The dedup flow and delta-sync flow are compact and useful. They show the
  check-missing handshake, chunk index, CDN download path, and local chunk reuse.
- Conflict handling chooses the right default for a general file sync product:
  keep both as a conflicted copy instead of silently overwriting.
- The GC step has real alternatives. Refcount plus grace-period sweep,
  immediate delete-at-zero, and mark-and-sweep tracing teach realistic safety
  and cost trade-offs.
- The follow-ups are relevant: ACLs, zero-knowledge encryption, huge files, and
  safe GC are exactly where a senior interviewer would probe.

## Highest-Impact Issues

### 1. Sharing is a stated requirement but not part of the design

The requirements include "Share files/folders with other users (read or write),"
and the requirements diagram ends at sharing. The main architecture, data model,
API, steps, final design, and `satisfies.functional[]` do not model it. The
interview script says to confirm sharing, but the walkthrough treats it as an
extension rather than a designed requirement.

Why it matters: sharing changes the core metadata contract. A shared folder is
not just a path in one user's namespace. It needs namespace membership, ACLs,
permission inheritance, write authorization, invite/accept flows, revocation,
possibly public links, and clear behavior when two users write the same file.
It also affects dedup privacy and encryption choices.

Concrete fix:

- Either downgrade sharing from a top-level requirement to a follow-up, or add a
  real step after metadata split or after sync: "Shared Namespaces and ACLs."
- Add data model rows such as `namespaces`, `namespace_members`, `shared_links`,
  and possibly `acl_entries`.
- Add API examples for creating a share, accepting/revoking access, and listing
  folder members.
- Add a `satisfies.functional[]` item for sharing that links to the new step.
- In final design, mention that `MetaSvc` authorizes every path operation
  against namespace membership before committing metadata.

### 2. Capacity is qualitative and does not size the real workload

The capacity section currently says billions of files, exabytes of data, about
4 MB chunks, high dedup ratio, and downloads much greater than uploads. That is
a useful start, but it does not turn the problem into work units.

For this system, the important sizing questions are not just total bytes. The
design needs approximate file counts per user, average file size distribution,
chunks per file, check-missing request rate, chunk upload rate, metadata commit
rate, change cursor reads, notification fanout per commit, CDN hit ratio, object
store egress, chunk-index cardinality, metadata footprint, and write
amplification from versions and refcounts.

Concrete fix:

- Add rows for active users/devices, upload edits per second, downloads per
  second, average changed chunks per edit, metadata commits per second, chunk
  checks per second, and notification events per second.
- Estimate chunk-index scale: `logical bytes / average chunk size`, then adjust
  for dedup ratio and version retention.
- Estimate metadata size separately from object-store bytes. This justifies the
  metadata/block split with numbers instead of prose.
- Include egress/CDN assumptions because the non-functional requirement says
  the workload is read-heavy on downloads.
- Add capacity notes about hot namespaces and large shared folders because they
  shape metadata sharding and notification fanout.

### 3. The data model does not fully support the promised behavior

The schema is close, but several fields needed by the narrative are missing or
inconsistent:

- `versions` uses `file_id`, but the current `files` table does not define
  `file_id`.
- Version restore is mentioned, but there is no restore API, no `created_by`,
  no `parent_version` or `base_version`, and no retention policy.
- Conflicted copies are described, but the model has no conflict marker,
  original file reference, conflict owner/device, or conflict naming policy.
- Deletes are represented by `deleted: bool`, but tombstone retention,
  undelete/restore behavior, and when refcounts decrement are not explicit.
- Sharing requires namespace membership and ACL tables, which are absent.
- `chunk_hashes` embedded directly in `files` and `versions` is simple, but for
  huge files it should likely become a manifest table or manifest object with
  ordered ranges.

Concrete fix:

- Add `file_id` to `files`, and define whether `(namespace_id, path)` maps to a
  file record or whether paths are separate directory entries pointing to files.
- Add a `file_versions` or `manifests` table with `version_id`, `file_id`,
  `base_version`, `created_by_device`, `created_at`, `state`, and
  `manifest_ref`.
- Add `namespace_members` / `acl_entries` if sharing remains in scope.
- Add explicit tombstone and retention fields so GC knows when it can decrement
  references safely.

### 4. The refcount/GC correctness story needs one stronger invariant

The GC step correctly warns that immediate delete-at-zero can race with
concurrent uploads, and its default option uses a grace-period sweep. The
remaining gap is the exact invariant connecting metadata commits and refcount
updates. In a content-addressed store, the dangerous states are:

- bytes exist but no metadata references them yet, after an interrupted upload;
- metadata references a chunk whose bytes were not committed durably;
- refcount increments or decrements drift from the actual manifests;
- a client claims a hash but uploads bytes that do not match that hash;
- cross-user dedup leaks existence information for private content.

Concrete fix:

- Add a compact flow to step `gc` or `meta-split`: upload chunks, verify hash,
  mark chunk pending/available, commit metadata, then update or derive
  reachability.
- State whether refcounts are updated transactionally with the version commit,
  asynchronously from a commit log, or periodically repaired from manifests.
- Add a failure drill for "metadata commit succeeds but refcount update fails."
- Mention hash verification and collision handling at `PUT /v1/chunks/{hash}`.
- Discuss dedup privacy: cross-user dedup is storage-efficient but can create
  content-existence side channels unless scoped or encrypted carefully.

### 5. Operations, security, and observability are underrepresented

For a production file-sync system, operations are not generic polish. They are
part of the product contract: users expect no data loss, predictable sync, and
clear recovery when clients are offline or buggy.

Missing operational topics include auth, quotas, abuse/malware scanning,
per-user/device rate limits, sync lag metrics, upload failure metrics, chunk
store durability audits, metadata backups, restore drills, chunk repair, client
version rollout, and alerting on stuck notification queues. Encryption is only a
follow-up even though it directly interacts with dedup.

Concrete fix:

- Add a final step or wrap-up section for "Operations, Security, and Quotas."
- Include an `observability` node or operational notes tied to concrete SLOs:
  commit latency, sync propagation latency, data durability, failed chunk
  verification, CDN hit ratio, refcount drift, and GC deletion rate.
- Add technology choices for metadata DB, object store, CDN, queue, and
  notification channel, following the stronger book datasets.
- Add security notes for authz on namespace operations, encryption at rest, key
  management, signed chunk URLs, and private-vs-global dedup.

### 6. One architecture view has an endpoint mismatch

The top-level `gc` step view includes link `meta-metadb`, whose high-level
definition is `MetaSvc -> MetaDB`, but the view nodes are only `GC`,
`ChunkIdx`, `BlockStore`, and `MetaDB`. `MetaSvc` is not in that view. The
option view for the default GC path uses a custom `GC -> MetaDB` link, which is
closer to the stated caption.

Concrete fix:

- Replace `meta-metadb` in the top-level `gc.view.links` with a custom
  `GC -> MetaDB` link, or include `MetaSvc` if the diagram is intended to show
  the service reading metadata.
- Re-run the structural check after editing to ensure every chosen link has
  both endpoints in the view's `nodes`.

## System Design Soundness

The core architecture is sound for storage-efficient file sync. The block plane
and metadata plane are separated correctly, chunk identities are content hashes,
and the final design integrates `Client`, `MetaSvc`, `MetaDB`, `BlockSvc`,
`ChunkIdx`, `BlockStore`, `NotifySvc`, `NotifyQ`, `CDN`, and `GC`.

The strongest mechanism is the commit ordering: chunks are uploaded before the
metadata version is committed. That prevents readers from resolving a file
version whose bytes do not exist. The dataset should make the related refcount
ordering equally explicit.

The consistency story is reasonable for a Dropbox-like product. Optimistic
version checks plus conflicted copies are the right baseline for general files,
where automatic merging is impossible for many binary formats. The walkthrough
correctly rejects last-writer-wins as unsafe.

The weaker area is namespace semantics. A file-sync service is fundamentally a
metadata system over namespaces, paths, versions, devices, and users. The
dataset currently treats namespace as a shard key but does not model directory
entries, rename/move, shared ownership, folder membership, permission
inheritance, or conflict records. That is acceptable for a narrow "chunked sync"
case, but it conflicts with the stated sharing requirement.

Durability is plausible but brief. Saying the object store provides
cross-zone replication/erasure coding is fine, but a strong system design answer
also mentions metadata backup/restore, chunk repair/audit, version retention,
delete grace periods, and recovery from a bad client or corrupt chunk.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Upload & Download the Whole File

This is a good baseline. The 500 MB one-paragraph edit example makes the cost
obvious, and the trap points directly at dedup and resumability.

Suggested improvement: add one capacity tie-in here, such as "10k such edits per
second would move 5 TB/s before compression/CDN." That would make the later
capacity section less abstract.

### Step 2: Split Files into Content-Addressed Chunks

This is one of the strongest steps. The options compare content-defined and
fixed-size chunking in a concrete way, and the default is appropriate for
delta-friendly sync.

Suggested improvement: clarify client versus server responsibility. The text
says the client splits files, but the option caption says the block service
splits the file. Pick one model. For a sync client, client-side chunking is the
more natural default because it enables check-before-upload and resumability.

### Step 3: Deduplicate: Store Each Chunk Once

The sequence flow is useful and the check-missing API matches it. This is the
right place to teach the chunk index.

Suggested improvement: add the write path after storing `h2`: verify bytes match
`h2`, write chunk metadata, and mark it available. This would make the
idempotency claim stronger and expose hash mismatch/corrupt upload handling.

### Step 4: Split Metadata from Block Storage

The prose is strong and teaches the central architectural split. The "commit
metadata last" trap is valuable.

Suggested improvement: expand the data model introduced here. This step should
establish `file_id`, namespace/path identity, manifest storage, version rows,
and tombstones because later sync, restore, conflict handling, and GC all depend
on those fields.

### Step 5: Delta Sync Across Devices

The cursor-based pull plus CDN chunk download flow is clear. Reusing chunk-hash
comparison on the download side is a good teaching point.

Suggested improvement: define the cursor contract. Is it a per-namespace
monotonic sequence, a change-log offset, or a vector across shards? What happens
when a device is offline longer than the change-log retention window? Add a
fallback: full metadata rescan or snapshot plus delta.

### Step 6: Change Notification and Conflict Handling

This step has strong option quality. Conflicted copies, last-writer-wins, and
OT/CRDT merging are real alternatives with honest trade-offs.

Suggested improvement: separate notification delivery from conflict resolution.
Long-poll/push needs fanout, device presence, missed notification recovery, and
backpressure for large shared folders. Conflict handling needs model support for
base version, conflict file identity, and user/device attribution.

### Step 7: Garbage Collection and Durability

The options and failure drills are good, and this is the right place to close
the dedup lifecycle.

Suggested improvement: add a sequence flow for refcount drift repair or
mark-and-sweep. This is the step where a candidate should prove they understand
that GC cannot trust a single counter forever at exabyte scale.

## Final Design Review

The final design correctly integrates the core storage-sync components and
states the key behaviors: content-addressed chunks, missing-chunk upload,
metadata commit, notification-driven pulls, CDN downloads, conflicted copies,
GC, and object-store durability.

What it does not integrate is equally important:

- no sharing/ACL component or metadata;
- no quota, billing, or abuse-control path;
- no observability/operations component;
- no explicit metadata backup/restore or chunk audit path;
- no client encryption/key-management trade-off;
- no description of high-fanout shared-folder notifications.

The final design would be stronger if it added a sentence about metadata
authorization and a sentence about operational safety. Example direction:
"Every metadata mutation is scoped to a namespace and authorized through
membership/ACL state; operations track sync lag, refcount drift, chunk
verification failures, and restore readiness."

## Concept Introduction and Learning Flow

The concepts are introduced at good moments: content-addressed chunks in step 2,
metadata/data split in step 4, optimistic version checks in step 6, and
reference-counted GC in step 7. The pattern tags also align with those moments.

The gap is that several important concepts are used but not introduced as
first-class teaching objects: change-log cursor retention, namespace membership,
tombstones, chunk manifests, refcount repair, idempotent commit, quota, and
dedup privacy. These do not all need full sections, but the book dataset would
benefit from concept chips or short failure drills for the highest-impact ones.

## Step-to-Final-Design Coherence

The path from steps to final design is mostly coherent:

- `naive` motivates chunking.
- `chunking` introduces the block unit.
- `dedup` adds `ChunkIdx`.
- `meta-split` adds `MetaSvc` and `MetaDB`.
- `sync` adds cursor-based pull and CDN download.
- `notify` adds change fanout and conflict policy.
- `gc` closes the lifecycle of shared chunks.

The two coherence gaps are requirements coverage and data model support.
Sharing appears in the opening scope but never becomes a step. Version restore
appears in requirements and `satisfies`, but no API or flow demonstrates a
restore. The final design says "conflicted copies," but the data model does not
have conflict state.

## Realism Compared With Production Systems

Production file-sync systems live or die on edge cases: offline clients,
reconnect storms, permission changes, very large folders, bad clients, corrupt
chunks, quota enforcement, account compromise, malware/abuse, legal retention,
and user-visible recovery. The dataset covers some data-safety mechanisms but
not the operational workflows around them.

Add realistic caveats without turning the case into a full product spec:

- devices can miss notifications and must always be able to recover from the
  change cursor;
- shared folders create notification fanout and authorization churn;
- deletes need tombstone retention and restore windows;
- GC needs repair/audit because counters drift;
- global dedup can leak content existence unless scoped, salted, or constrained;
- metadata is the control plane and needs backups, restore drills, and shard
  hot-spot handling;
- clients need upload sessions or idempotency tokens for commit retries.

## Dataset and Renderer-Facing Observations

- JSON parsing succeeds for `data/book/file-sync/interview.json`.
- Top-level high-level node IDs and link IDs resolve in the basic checks.
- `satisfies[*].steps[*]` references all point to existing step IDs.
- The `gc` top-level view has one endpoint mismatch: link `meta-metadb`
  requires `MetaSvc`, but `MetaSvc` is absent from `gc.view.nodes`.
- `satisfies.functional[]` omits the sharing requirement even though it is in
  `requirements.functional[]`.
- `satisfies.nonFunctional[]` omits the scale/read-heavy requirement even though
  it is in `requirements.nonFunctional[]`.
- The dataset has no `technologyChoices`. This field is optional, but it is now
  part of the richer book-case surface and would be valuable here.
- There are no AI visuals, which is fine; the structured Mermaid views are
  sufficient for this review.
- Requirements and capacity diagrams are raw Mermaid overview diagrams, which
  matches repo conventions.

## Recommended Edits, Prioritized

### P1: Decide whether sharing is in scope, then make the dataset consistent

Best fix: add a sharing/ACL step and supporting schema/API/satisfies coverage.
Smaller fix: move sharing to follow-ups and remove it from top-level functional
requirements and the requirements diagram.

### P1: Replace qualitative capacity with concrete workload sizing

Add active users/devices, files/user, average file size, chunk count, uploads/s,
downloads/s, chunk-check QPS, chunk-write QPS, metadata commits/s, notification
events/s, CDN egress, metadata footprint, and chunk-index size.

### P1: Strengthen the metadata schema

Add `file_id`, version/manifests fields, tombstone/retention fields, conflict
metadata, and namespace/ACL records if sharing remains in scope.

### P2: Add one production correctness flow

Add a compact sequence for upload/commit/refcount ordering, cursor recovery, or
GC repair. The highest value is upload/commit/refcount because it connects
chunking, metadata, idempotency, and GC.

### P2: Add operations/security/technology choices

Add technology choices for metadata DB, object store, chunk index, queue,
notification channel, CDN, and observability. Include quota/rate limits,
encryption/key management, signed URLs, and dedup privacy caveats.

### P2: Fix the `gc` view endpoint mismatch

Replace `meta-metadb` with a custom `GC -> MetaDB` link or include `MetaSvc` in
the view.

### P3: Improve API completeness

Add restore, delete semantics, upload session/idempotency, share management, and
cursor-recovery examples. Define what happens on `409` conflict and stale
cursor.

### P3: Add failure drills outside GC

Good scenarios: client crashes mid-upload, metadata commit retries after a
timeout, device offline past cursor retention, notification queue backlog,
shared-folder permission revoked while a client has pending writes, and chunk
hash verification failure.

## What Not To Change

- Keep the chunking -> dedup -> metadata split -> sync -> notification -> GC
  sequence. It is the right teaching spine.
- Keep content-defined chunking as the default option, with fixed-size chunking
  as the simpler alternative.
- Keep conflicted copies as the default conflict policy for general files.
- Keep the metadata/block split prominent; it is the central design lesson.
- Keep GC late in the walkthrough, after readers understand shared chunk
  references.

## Bottom Line

The dataset has a strong core and is already useful for teaching the essence of
file sync. To become book-ready, it needs a hardening pass that reconciles the
stated sharing requirement, adds real capacity math, strengthens the metadata
schema, and makes operations/security visible enough for a production interview.
