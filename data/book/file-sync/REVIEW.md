# Review: Dropbox / File Sync - System Design

Reviewed file: `data/book/file-sync/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent hardening pass materially improved this dataset. The previous major
gaps around sharing, capacity sizing, metadata schema, restore/share APIs,
technology choices, and GC/refcount safety are now mostly addressed. The
walkthrough has a clear book-quality spine: whole-file baseline, client-side
content-defined chunks, dedup, metadata/block split, cursor-based sync, shared
namespaces, notification/conflict handling, and safe garbage collection.

The remaining work is less about adding missing sections and more about making
the strongest claims precise. A few capacity numbers need arithmetic cleanup,
the upload/commit/refcount lifecycle should be stated as an explicit state
machine, the notification path should distinguish durable change logs from
online push delivery, and sharing/security should define their edge-case
boundaries.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.35/5 | Strong core architecture, schema, sharing step, sync flow, and GC repair story; still needs sharper commit/refcount and cursor/fanout invariants. |
| Production realism | 4.15/5 | Much more realistic after capacity, ACLs, technology choices, and observability; quota, abuse, signed URLs, dedup privacy, and revocation behavior need stronger integration. |
| Pedagogical flow | 4.4/5 | Excellent progression from baseline pain to production mechanisms; remaining improvements are mostly failure drills and numeric consistency. |
| Dataset/rendering fit | 4.65/5 | JSON parses; structured views, link IDs, endpoint coverage, sequence participants, `satisfies`, and technology step refs resolve cleanly. |
| Overall | 4.35/5 | A strong file-sync case that is close to book-ready, with a few precision fixes needed before calling it production-grade. |

## What Works Well

- The recent sharing step fixes the biggest previous scope issue. Sharing is now
  represented in requirements, step flow, data model, API, patterns,
  `satisfies`, technology choices, and interview script.
- Capacity is no longer hand-wavy. It sizes users/devices, files, logical and
  physical bytes, chunk checks, chunk writes, metadata commits, notifications,
  CDN hit ratio, chunk-index cardinality, and metadata footprint.
- The data model now supports the narrative: `file_id`, immutable
  `file_versions`, manifest references, tombstones, `namespaces`,
  `namespace_members`, and `shared_links` are all present.
- Client-side content-defined chunking is the right default, and the fixed-size
  option is framed honestly as simpler but weaker under inserts.
- The sync step introduces per-namespace cursors, offline-retention reset, CDN
  downloads, and local chunk reuse. That is the right conceptual package.
- The GC step now states the important invariant: chunks are verified before
  metadata references them, and refcounts are repaired from committed manifests
  rather than trusted blindly.
- Technology choices are concrete and relevant to this domain: metadata DB,
  object store, chunk index, notification/fanout, CDN, and auth/quota/abuse.
- The structured diagram data is clean in the checks run for this review.

## Highest-Impact Issues

### 1. Capacity math has one major inconsistency

The capacity row says `~200k edits/sec` and explains it as `~2 edits/user/day`
for `~100M users`. Those numbers do not match. `100M users * 2 edits/day` is
about `2.3k edits/sec`, not `200k edits/sec`. Conversely, `200k edits/sec` is
about `17.3B edits/day`, or roughly `173 edits/user/day` across 100M users.

The step-1 prose also says whole-file upload would move "petabytes per second."
Using the capacity table's `100 MB` average file and `200k edits/sec`, the
whole-file baseline is about `20 TB/sec`; using the 500 MB example, it is about
`100 TB/sec`. Those are huge, but not petabytes per second.

Concrete fix:

- Decide whether the intended workload is `~2k edits/sec` or `~200k edits/sec`.
- If keeping `200k edits/sec`, change the note to something like
  `~170 edits/user/day across active users` or redefine "active users" as a much
  smaller active-editing cohort.
- Correct the step-1 comparison from "petabytes per second" to a concrete
  `TB/sec` estimate, or express it as `PB/day` if that is the intended scale.
- Re-check dependent rows (`chunk-check QPS`, `chunk-write QPS`, metadata
  commits, notification fanout, CDN egress) after choosing the edit rate.

### 2. The upload, commit, and refcount lifecycle should be an explicit state machine

The dataset now mentions the right invariant, but it still compresses several
dangerous transitions into prose: upload missing chunks, verify hash, mark
available, commit the version, update or derive refcounts, notify devices, and
eventually sweep. This is where production file-sync systems lose data if the
ordering is vague.

Why it matters: failures can happen between every pair of those operations.
A client can retry after a timeout, a metadata commit can succeed while the
refcount update fails, a chunk can be uploaded but never referenced, and a hash
can be claimed before bytes are durably verified.

Concrete fix:

- Add a compact state table or sequence in `gc` or `meta-split`:
  `pending_chunk -> available_chunk -> committed_manifest -> reachable_chunk ->
  gc_candidate -> deleted`.
- Add an idempotency token or `commit_id` to `POST /v1/files/commit`, and an
  upload/session identifier if the client can retry multi-chunk uploads.
- State whether refcount updates are synchronous with the metadata transaction,
  appended to a commit log/outbox, or purely repaired by mark-and-sweep.
- Add a failure drill: "metadata commit succeeds but refcount update fails."
- Mention that notifications are emitted after the committed manifest is
  durable, not after merely receiving chunk bytes.

### 3. Cursor recovery and notification fanout need a stronger model

The sync step correctly introduces a per-namespace cursor and reset snapshot,
but the data model does not include a change-log table, retention window,
cursor compaction rule, or device cursor state. The notification diagram also
shows `NotifyQ -> Client`, which collapses a durable queue and an online
connection manager into one arrow.

Why it matters: for file sync, notifications are only hints. The source of
truth is the metadata change log. Devices miss pushes, reconnect in waves, and
large shared folders can create high-fanout bursts from a single commit.

Concrete fix:

- Add `namespace_changes(namespace_id, seq, file_id/path, version_id, op,
  created_at)` or describe it in the data model note.
- Add a short note for per-device cursor storage and what happens when a cursor
  is older than retention.
- Split the notification path conceptually: durable change event/log,
  notification worker, and WebSocket/long-poll gateway or connection manager.
- Add backpressure behavior for large shared folders: coalesce notifications
  by namespace and make clients pull deltas instead of pushing every file event.

### 4. Sharing is now present, but its scope should be stated more sharply

The new `namespaces` and `namespace_members` model is the right baseline for
shared folders. The remaining ambiguity is whether the case supports only
shared-folder membership or true file/folder-level ACL inheritance. The
requirement says "Share files/folders with other users (read or write)," while
the implementation mostly models a shared folder as a mounted namespace.

Concrete fix:

- If the intended scope is shared folders only, say so in requirements or in
  the sharing step, and treat file-level public links as a separate extension.
- If file/folder ACLs are in scope, add `acl_entries` or define inheritance,
  overrides, and how revocation affects descendants.
- Define the behavior for revocation during pending client commits: commit
  should authorize against current membership at commit time.
- Add one note about role changes and stale clients: old notifications or cached
  manifests must not bypass authorization on chunk URLs or metadata commits.

### 5. Security, quotas, and abuse controls are still mostly wrap-up material

The technology choices mention auth, quotas, malware scanning, signed chunk
URLs, and zero-knowledge encryption trade-offs. That is valuable, but the main
architecture and API do not yet show how those protections attach to the file
sync workflow.

Concrete fix:

- Add `authz`/quota checks to the metadata and block API descriptions, not only
  technology choices.
- Mention signed URLs or scoped download tokens for CDN/object-store access,
  especially for private chunks and shared links.
- Add quota enforcement at metadata commit time and object/chunk upload time.
- Describe async malware/abuse scanning state for shared/public content.
- Tighten the dedup privacy story: global dedup, per-user/per-namespace dedup,
  salted hashes, and client-side encryption are mutually constraining choices.

## System Design Soundness

The architecture is sound for a Dropbox-style sync service. The split between
metadata and bytes is clear, the block plane uses immutable content-addressed
chunks, the metadata plane owns namespace/version state, and the final design
connects client, gateway, metadata service/store, block service/store, chunk
index, notification path, CDN, GC, and observability.

The requirements now align with the design much better than before. Upload,
download, delete, versioning, restore, sharing, resumability, dedup, bandwidth
efficiency, sync latency, and large-scale storage are all represented in the
walkthrough or wrap-up.

The best production mechanism is the repeated separation of "bytes are present"
from "metadata points to them." The dataset should lean even harder into that
with an explicit commit protocol, because candidates can otherwise hand-wave
the one place where correctness is most fragile.

The consistency story is appropriate. Optimistic version checks and conflicted
copies are the right default for arbitrary file content. The dataset correctly
rejects last-writer-wins for user files and treats OT/CRDT merge as a niche
option for structured collaborative documents.

The weakest remaining design surface is the live sync control plane: change-log
retention, cursor repair, notification coalescing, shared-folder fanout, and
reconnect storms. These do not require a new major step, but they deserve a
stronger paragraph and possibly one failure drill.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Upload & Download the Whole File

This remains a strong baseline. It exposes bandwidth, storage duplication, and
resumability problems before introducing machinery.

Fix the numeric phrase about "petabytes per second." The current capacity table
supports a `TB/sec` example, not `PB/sec`.

### Step 2: Split Files into Content-Addressed Chunks

This is one of the strongest steps. It correctly makes client-side
content-defined chunking the default and explains why fixed-size chunks lose
dedup stability after inserts.

Suggested improvement: mention bounded min/max chunk size in the main prose, not
only the option cons, because it is a common production detail.

### Step 3: Deduplicate: Store Each Chunk Once

The check-missing sequence is concrete and useful. The addition of hash
verification before marking a chunk available is the right correction.

Suggested improvement: mention whether `check` responses leak cross-user chunk
existence and whether the chosen design scopes dedup globally, per user, or per
namespace.

### Step 4: Split Metadata from Block Storage

This step now has the data model support it needs. `file_id`, versions,
manifests, tombstones, and metadata-last commit are all aligned.

Suggested improvement: add a one-line idempotency rule for commit retries after
client timeout. Without it, duplicate version rows or duplicated conflicted
copies are an easy failure mode.

### Step 5: Delta Sync Across Devices

The cursor-based pull plus CDN download flow is good. The reset snapshot behavior
for old cursors is an important addition and should stay.

Suggested improvement: add the missing persistence model for the cursor:
where the change log lives, how long it is retained, how it is compacted, and
what per-device cursor state is stored.

### Step 6: Shared Namespaces and ACLs

This step fixes the previous review's largest issue. Shared namespaces mounted
into each member tree is the right model for folder sharing, and authorizing all
metadata mutations through membership is the right principle.

Suggested improvement: state the exact scope. Shared-folder membership is
credible and teachable; arbitrary nested ACL inheritance is a bigger product
surface. Pick one deliberately.

### Step 7: Change Notification and Conflict Handling

The conflict options are strong. Conflicted copies are the right default, and
the alternatives teach real trade-offs.

Suggested improvement: separate "notification" from "conflict handling" in one
extra paragraph. Notifications are best-effort hints plus durable cursor pulls;
conflict handling is a metadata commit rule.

### Step 8: Garbage Collection and Durability

This step is now much stronger. It correctly warns that refcounts drift and says
mark-and-sweep repairs reachability from live manifests.

Suggested improvement: make the lifecycle mechanical with states and a failure
drill. The core idea is right; the next improvement is making the invariant
auditable.

## Final Design Review

The final design integrates the main components introduced by the steps and now
adds an observability plane. The caption is accurate and connects metadata,
block storage, chunk index, CDN, notification queue, and GC.

The final design would be stronger with two small additions:

- A push/connection gateway or explicit note that `NotifyQ` wakes devices only
  as a hint, while clients still pull from the metadata change log.
- A security/quota/authz note near `MetaSvc` and `BlockSvc`, because sharing and
  public links make authorization central rather than optional.

## Concept Introduction and Learning Flow

The concept staging is strong. Content-addressed chunking appears exactly when
whole-file transfer fails. Dedup follows naturally from chunk hashes. Metadata
split follows from needing paths, versions, manifests, restore, and commits.
Delta sync follows from manifests. Sharing then changes namespace semantics.
Notification/conflict handling and GC close the operational loop.

The remaining concepts that deserve one more explicit hook are:

- idempotent commit and upload session lifecycle;
- change-log retention and cursor reset;
- notification coalescing for high-fanout shared folders;
- revocation and stale authorization;
- dedup privacy versus encryption;
- quota and abuse enforcement.

## Step-to-Final-Design Coherence

The step-to-final-design coherence is now good:

- `naive` motivates chunking.
- `chunking` establishes the block unit.
- `dedup` introduces `ChunkIdx`.
- `meta-split` introduces `MetaSvc` and `MetaDB`.
- `sync` introduces cursor pull and CDN download.
- `sharing` adds namespaces and ACL membership.
- `notify` adds fanout and conflict behavior.
- `gc` closes the chunk lifecycle and durability story.

The final design includes the components needed for those steps. The only
coherence gap is that some operational details live in wrap-up text rather than
the step/final-design path: quota, authz, malware scanning, signed URLs, and
change-log persistence.

## Realism Compared With Production Systems

Compared with real file-sync systems, this dataset now covers the important
middle layer well: chunking, dedup, metadata, manifests, sharing, cursors,
notifications, conflicts, and GC. It no longer reads like generic blob storage.

The remaining production realism gaps are mostly edge-case workflows:

- reconnect storms after outage or client rollout;
- a device offline past change-log retention;
- a shared folder with hundreds or thousands of members;
- permission revocation while a client has pending writes;
- signed URL expiry while a chunk download is in progress;
- quota exceeded after chunks are uploaded but before metadata commit;
- malware scan finds a public/shared file after it has synced;
- metadata commit succeeds but refcount update or notification emit fails;
- cross-user dedup leaks existence of private content.

These are good candidates for failure drills rather than new architecture
sections.

## Dataset and Renderer-Facing Observations

- JSON parsing succeeds for `data/book/file-sync/interview.json`.
- Top-level keys include requirements, capacity, API, data model, structured
  architecture, steps, final design, satisfies, technology choices, interview
  script, level variants, follow-ups, assets, and probe links.
- Step view node IDs resolve to `highLevelArchitecture.nodes`.
- Step and final-design link IDs resolve to `highLevelArchitecture.links`.
- Selected link endpoints are present in each step, option, and final-design
  view checked.
- Sequence participants referenced by flow messages resolve, including nested
  `alt` branches.
- `satisfies[*].steps[*]` references resolve to existing step IDs.
- `technologyChoices[*].steps[*]` references resolve to existing step IDs.
- Requirements and capacity diagrams remain raw Mermaid overview diagrams,
  which matches repo conventions.
- There are no AI visuals, which is acceptable; the structured Mermaid diagrams
  are sufficient for this dataset.

## Recommended Edits, Prioritized

### P1: Fix capacity arithmetic and dependent prose

Resolve the `200k edits/sec` versus `2 edits/user/day` mismatch and correct the
step-1 `PB/sec` phrase. Then re-check derived QPS, fanout, and egress rows.

### P1: Add an explicit commit/refcount state machine

Make upload session, chunk availability, metadata commit, refcount/outbox
update, notification emit, and GC candidate states unambiguous. Add one failure
drill around a partial failure between metadata commit and refcount update.

### P2: Model the change log and notification delivery boundary

Add a `namespace_changes` concept/table, retention/reset behavior, per-device
cursor state, and a note that notification delivery is best-effort and
coalesced. Consider adding a push gateway node or explaining that `NotifyQ ->
Client` is shorthand.

### P2: Clarify sharing scope and revocation behavior

Say whether this supports only shared-folder namespaces or arbitrary file/folder
ACL inheritance. Add revocation-at-commit-time behavior and stale-client
authorization notes.

### P2: Pull security/quota/abuse into the main workflow

Keep the technology choices, but add API/architecture notes for signed URLs,
quota checks, malware scanning state, rate limits, and dedup privacy.

### P3: Add two or three failure drills outside GC

Good drills: client retries commit after timeout, device cursor is too old,
shared-folder fanout backlog, permission revoked during pending upload, and
quota exceeded after chunks are uploaded.

## What Not To Change

- Keep the current step order. It is the right teaching sequence for file sync.
- Keep content-defined chunking as the default option.
- Keep metadata/block split as the central architectural lesson.
- Keep conflicted copies as the default conflict policy for arbitrary files.
- Keep shared namespaces as the baseline sharing model.
- Keep refcount plus grace-period sweep as the default GC option, with
  mark-and-sweep repair as the safety backstop.
- Keep technology choices focused on concrete implementation trade-offs rather
  than generic cloud lists.

## Bottom Line

The file-sync interview is now a strong book case. It teaches the right design,
uses the project schema well, and covers the major product requirements. The
remaining fixes are precision work: clean up the arithmetic, make commit and GC
invariants mechanical, and turn sync/sharing/security edge cases into explicit
failure drills.
