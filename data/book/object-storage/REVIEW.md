# Review: S3-like Object Storage - System Design

Reviewed file: `data/book/object-storage/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a coherent object-storage walkthrough with the right conceptual spine:
single-server baseline, metadata/data-plane split, replication versus erasure
coding, commit-metadata-last consistency, multipart upload, repair/GC, and
prefix listing at scale. The step order is easy to teach and the structured
diagrams resolve cleanly.

The main gap is that the dataset reads more like a strong conceptual overview
than a production-grade S3-style design. Capacity is qualitative, the API only
shows three endpoints despite requirements for delete/list/versioning/multipart,
and the data model omits several records and invariants that make durability,
versioning, listing, lifecycle, and tenant isolation safe. The design should
also choose more precise semantics for listing consistency and for the hybrid
replication/erasure-coding policy it recommends in prose.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 3.9/5 | Correct architecture and durability concepts; needs sharper API, schema, consistency, repair, and capacity contracts. |
| Production realism | 3.55/5 | Repair and GC are present, but auth, quotas, encryption, lifecycle, observability, idempotency, and exact state transitions are thin. |
| Pedagogical flow | 4.15/5 | Clear progression and useful trade-off options; some production mechanisms are compressed into prose instead of concrete flows. |
| Dataset/rendering fit | 4.65/5 | JSON parses; step/final views, option views, highlights, pattern refs, probe refs, and `satisfies` step refs resolve cleanly. |
| Overall | 3.95/5 | A solid book case foundation that needs a hardening pass before it feels production-complete. |

## What Works Well

- The metadata/data-plane split is exactly the right organizing idea for this
  interview. Step 2 explains why the key-to-placement mapping and bulk bytes
  scale differently.
- The durability section teaches the right first principles: full replicas are
  simple and fast; erasure coding controls storage overhead; placement across
  independent failure domains is what makes either scheme meaningful.
- Step `replication-vs-ec` is a useful sub-step. It gives the reader a compact
  explanation of why real stores often use both schemes.
- The commit-metadata-last step is the strongest correctness mechanism in the
  dataset. It explains read-after-write visibility and orphan-data GC without
  overcomplicating the first pass.
- Multipart upload is introduced at the right time, after the write protocol is
  clear and before maintenance.
- Repair, scrubbing, and GC are not left as footnotes. The dataset correctly
  says durability is maintained over time, not just achieved at initial write.
- The final design integrates every component introduced in the steps.
- Renderer-facing checks are clean: source JSON parses, node IDs and link IDs
  resolve for step views, option views, and final design; `satisfies` step refs,
  pattern refs, probe links, and the sub-step parent all resolve.

## Highest-Impact Issues

### 1. Capacity is qualitative, so the design cannot be sized or stress-tested

The capacity section has useful labels - trillions of objects, exabytes, 11
nines, bytes-to-TBs object sizes, racks/zones - but no request rates, object
size distribution, metadata footprint, write/read bandwidth, listing volume, or
repair budget. That makes several later decisions hard to evaluate:

- how many metadata shards are needed;
- whether the bucket index can keep up with writes and listings;
- how much cross-zone or intra-cluster bandwidth repair needs;
- how much write amplification replication or erasure coding creates;
- whether small-object metadata dominates storage or request cost.

Concrete fix:

- Add numeric rows for peak PUT/s, GET/s, LIST/s, DELETE/s, average and p95
  object size, small-object percentage, object metadata bytes, total metadata
  footprint, and expected hot-bucket skew.
- Add durability-specific sizing: chosen replication or EC policy, raw-storage
  multiplier, write amplification, repair bandwidth budget, and target time to
  restore redundancy after a node/rack loss.
- Include one back-of-the-envelope example, such as:
  `10T objects * ~1 KB metadata ~= 10 PB logical metadata before indexes and replicas`.
- Tie the capacity numbers back to Step 7's metadata sharding and Step 6's
  repair prioritization.

### 2. The API does not cover the stated object-store contract

The requirements include PUT, GET, DELETE, prefix list, multipart upload,
optional versioning, and read-after-write. The API section currently shows only:

- `PUT /{bucket}/{key}`;
- `GET /{bucket}/{key}`;
- `POST /{bucket}/{key}?uploads` to initiate multipart upload.

That leaves core behavior implied but not specified. A candidate reading this
does not see how to delete an object, list a bucket by prefix, complete or abort
a multipart upload, upload individual parts, request a specific version, or use
conditional/idempotent writes.

Concrete fix:

- Add endpoints for `DELETE /{bucket}/{key}`, `GET /{bucket}?prefix=&delimiter=&cursor=`,
  `PUT /{bucket}/{key}?partNumber=&uploadId=`, `POST ...?uploadId=complete`,
  `DELETE ...?uploadId=abort`, and optionally `HEAD /{bucket}/{key}`.
- Show version semantics explicitly: `GET ?versionId=`, delete markers, latest
  pointer behavior, and whether non-versioned buckets overwrite in place or
  create hidden generations.
- Add request headers that drive correctness: content checksum, idempotency key,
  conditional write headers, storage class, encryption key reference, and
  expected object size for admission/quota checks.
- Add at least one sequence for multipart complete, because "parts then atomic
  complete" is a central correctness boundary.

### 3. The data model is too small for the promised semantics

The current data model has `objects (metadata)`, `data shards`, and
`multipart_uploads`. That is enough to explain the first diagram, but it does
not yet support several promises made elsewhere in the dataset.

Missing or under-modeled surfaces:

- bucket/account identity, tenant ownership, bucket policy, and quota state;
- object version table versus a latest pointer;
- delete markers and lifecycle state for versioned and non-versioned buckets;
- per-object checksum, encryption/KMS key reference, storage class, retention
  or legal-hold state, and created/updated timestamps;
- multipart part records with part number, size, checksum/etag, placement, and
  TTL;
- bucket index records with ordered key, version/delete-marker visibility, and
  pagination cursor support;
- placement generation/epoch so repair and reads know which placement map they
  are using;
- idempotency records for retried PUT/complete/delete calls.

Concrete fix:

- Split metadata into explicit tables or records:
  `buckets`, `object_versions`, `object_latest`, `multipart_uploads`,
  `multipart_parts`, `bucket_index`, `shard_placements`, and `idempotency_keys`.
- Add a compact state machine:
  `pending_data -> data_durable -> metadata_committed -> deleting/delete_marker -> gc_eligible -> reclaimed`.
- State which updates are transactionally coupled in `MetaDB`, and which are
  asynchronous but recoverable from logs.

### 4. Write, read, and repair flows need sharper failure boundaries

The step-level consistency flow says data is acknowledged durable before
metadata commits, which is good. The top-level API PUT sequence, however, jumps
from "write shards" to "200 versionId" without showing how the metadata service
learns that the data write is durable. This compresses the most important
failure boundary in the design.

The same issue appears in reads and repair. The dataset says any replica or
enough fragments can serve a read, and that repair rebuilds missing
replicas/fragments, but it does not show:

- who coordinates a PUT and owns retries after client timeout;
- how duplicate PUT or complete requests are deduplicated;
- how a GET falls back from a missing/corrupt shard to another replica or EC
  reconstruction;
- how corrupt shards are quarantined before replacement;
- how repair is prioritized when a whole rack is lost;
- how GC proves a shard is not live before deleting it.

Concrete fix:

- Amend the PUT flow so `EC/DataNodes -> MetaSvc` or a write coordinator returns
  a durable placement receipt before metadata commit.
- Add one read-degraded flow: metadata resolves placement, one shard fails
  checksum, client/service reads alternate fragments, object is reconstructed,
  and repair is queued.
- Add one GC safety invariant: GC only deletes data whose metadata version is
  deleted/expired and whose retention window has passed, preferably after a
  mark/sweep or generation check.
- Add failure drills for client retry after timeout, metadata commit failure
  after data write, and repair backlog after rack loss.

### 5. Listing consistency conflicts with the stated S3-like expectations

Step 7 chooses a derived ordered bucket index for prefix listing. That is a good
shape, but the option explicitly says sync lag can make a just-written key
temporarily missing from listings. The requirements say "read-after-write
visibility for new objects" and the title frames the case as S3-like. Modern
S3-style expectations often include strong list visibility, or at least require
the design to state where list consistency is weaker than GET consistency.

Concrete fix:

- Decide whether `LIST` must be strongly consistent with successful PUT/DELETE.
- If yes, make the bucket index update part of the metadata commit path, or
  commit through a log/transaction that makes the index read path observe the
  same version before acknowledging the write.
- If no, explicitly scope the guarantee to `GET/HEAD` and call out that listing
  is eventually consistent. Then reflect that weaker guarantee in
  `requirements`, `satisfies`, and the interview script.
- Define pagination cursor semantics under concurrent writes and deletes.

### 6. Security, tenancy, and compliance are mostly absent

The front-end/API node says it authenticates, routes, and rate-limits, but the
walkthrough and data model do not carry those concerns forward. For an
S3-like object store, these are central production requirements rather than
optional finishing touches.

Concrete fix:

- Add tenant/account/bucket identity to API paths or required request context.
- Mention bucket policies/IAM-style authorization on every metadata operation.
- Add per-tenant quotas and admission control for bytes, object count, request
  rate, and multipart orphan bytes.
- Include encryption at rest with KMS/envelope key metadata, and TLS/signed
  URLs or scoped tokens for direct data-node/object transfer.
- Add retention/legal hold/lifecycle policies as explicit extensions if they
  are out of core scope.
- Add audit logs for administrative and object-level access where appropriate.

## System Design Soundness

The core architecture is directionally sound. The dataset correctly separates
the metadata plane from the data plane, uses placement across failure domains,
keeps data invisible until metadata commits, and recognizes that repair and GC
are part of the durability story.

The strongest system-design idea is commit-metadata-last. It gives a clean
answer to the common "what if the service crashes mid-write?" question: failed
writes leave orphan data, not visible metadata pointing to missing bytes. This
should become the explicit state machine for PUT, multipart complete, delete,
and GC.

Durability is presented correctly at the conceptual level, but it needs math.
Replication versus EC cannot be evaluated without object-size mix, storage
overhead, write/read amplification, degraded-read latency, and repair bandwidth.
The dataset says 11 nines but does not show how repair speed and failure-domain
placement maintain that target after failures.

The consistency story is good for `GET` after `PUT`, but less clear for
`LIST`, overwrite, delete, and versioning. Object storage interviews often turn
on these edge cases. The dataset should define whether the metadata store
serializes updates per `(bucket, key)`, how latest-version pointers are updated,
and what readers see during overwrite/delete races.

Availability is present but thin. "Any copy/enough fragments serve reads" is
right, but the design should explain degraded reads, request hedging, timeouts,
and how repair traffic is isolated from serving traffic.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Store the Blob on One Fileserver

This is a clean baseline. It exposes both durability and scale failure with no
unnecessary machinery. Keep it.

Suggested improvement: connect the failure to a numeric capacity example once
the capacity section is hardened. For example, show why metadata count, disk
capacity, and network throughput each fail independently.

### Step 2: Split Metadata from Data

This step introduces the right abstraction. The distinction between queryable
metadata and opaque bytes is clear and sets up placement, versioning, listing,
and multipart upload.

Suggested improvement: introduce the authoritative metadata invariants here:
metadata is the source of visibility, data nodes are not authoritative for
object existence, and readers should never trust data without metadata.

### Step 3: Durability: Replication vs Erasure Coding

The options teach meaningful trade-offs. The default option is erasure coding,
while the sub-step later says real stores use both replication and EC. That is
not wrong, but the selected architecture should be more explicit.

Suggested improvement: make the chosen policy "tiered: replicate small/hot,
erasure-code large/cold" unless the intended answer is deliberately pure EC.
Then update the default option, final design wording, and decision-tree path to
match.

### Step 3a: Replication vs Erasure Coding

This sub-step is useful and concise. It explains read latency, repair
amplification, storage overhead, and why object class matters.

Suggested improvement: add one concrete rule of thumb, such as "replicate
objects below X MB or recently written objects; EC larger/colder objects after
a background transition." It can be illustrative rather than prescriptive.

### Step 4: Read-After-Write via Commit Ordering

This is the best teaching step in the dataset. It explains the correctness
lever and the failure outcome.

Suggested improvement: add a write coordinator or durable placement receipt to
the flow. The candidate should be able to answer, "who knows the data write
succeeded before committing metadata?"

### Step 5: Multipart Upload for Large Objects

The conceptual flow is right: initiate, upload parts independently, then
complete atomically. The prose also correctly says abandoned parts need GC.

Suggested improvement: model part records and completion semantics more
explicitly. Multipart complete should validate the submitted part list,
checksums, sizes, and upload state, then commit the final object exactly once.
Abort and timeout cleanup should be first-class.

### Step 6: Scrubbing, Repair, and Garbage Collection

This step prevents the common mistake of treating durability as a write-time
property. The rack-loss failure drill is a good start.

Suggested improvement: add more operational details: scrub cadence, checksum
scope, repair queue priority, repair bandwidth throttling, corrupted-shard
quarantine, and GC proof of non-reachability.

### Step 7: Listing, Sharding, and Availability at Scale

This step covers the right pressure point: metadata becomes the scale bottleneck
and prefix listing does not fit a pure hash-sharded point lookup store.

Suggested improvement: decide on list consistency and pagination. The derived
index option is strong, but the current "sync lag" caveat needs to be aligned
with the requirements.

## Final Design Review

The final design includes the introduced components: client/API, metadata
service/store, placement service, replication/erasure coder, data nodes,
multipart coordinator, repair/scrubber, GC, and bucket index. It is coherent as
a teaching diagram.

The final design should carry a few production commitments that are currently
only implied:

- selected redundancy policy: pure EC, pure replication, or hybrid by object
  class/lifecycle;
- exact write state machine and durable acknowledgement path;
- version/delete/list semantics;
- tenant/bucket authorization and quota enforcement;
- repair and GC safety invariants;
- observability and operational SLOs.

It also lacks a `technologyChoices` section, which many book datasets use to
compare self-hosted and managed options. Object storage is a good fit for that
section: metadata store, storage engine/data nodes, queue/log for repair and
index updates, CDN, KMS, observability, and managed cloud object-store choices.

## Concept Introduction and Learning Flow

The concepts are introduced just in time. Metadata/data-plane split appears
before durability, durability appears before consistency, and consistency
appears before multipart. That order is effective.

The learning flow would be stronger if a few concepts were named explicitly:

- write state machine;
- idempotency key;
- delete marker;
- lifecycle transition;
- repair amplification;
- degraded read;
- bucket index consistency;
- envelope encryption/KMS;
- per-tenant quota and rate limiting.

These do not all need full steps. Most can appear as concepts, traps, failure
drills, or data-model fields.

## Step-to-Final-Design Coherence

Most step mechanisms appear in the final design. The final diagram contains the
metadata service/store from Step 2, placement and EC/data nodes from Step 3,
commit-last components from Step 4, the upload coordinator from Step 5,
repair/GC from Step 6, and the bucket index from Step 7.

The main coherence gaps are:

- Step 3a recommends a hybrid replication/EC system, while the default option
  path favors EC and the final design says "replicas or erasure-coded
  fragments" without choosing the policy.
- Step 4's detailed consistency flow is stronger than the API PUT sequence; the
  top-level API flow should not hide the durable acknowledgement boundary.
- Step 7's listing option permits index lag, while the high-level requirements
  imply immediate visibility for new objects unless listing is explicitly
  weaker than GET.

## Realism Compared With Production Systems

The dataset captures the distinctive parts of object storage better than a
generic blob-store answer would: placement, EC, metadata/data split, multipart,
repair, and listing are all present.

The missing realism is mostly in operational contracts:

- authentication and authorization per account/bucket/key;
- bucket policies, signed URLs, and scoped direct-transfer credentials;
- encryption and KMS key metadata;
- quota enforcement and abuse controls;
- request idempotency and retry behavior under timeouts;
- lifecycle policies, retention, legal hold, and object lock;
- cross-region replication and disaster recovery as extensions;
- observability for durability risk, repair lag, orphan bytes, hot buckets,
  data-node errors, checksum failures, and index lag;
- admission control and backpressure when repair or listing competes with
  foreground traffic.

These additions would make the case feel like an operated service rather than a
clean architecture sketch.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level dataset structure is valid for the project: requirements, capacity,
  API, data model, patterns, steps, final design, satisfies, interview script,
  level variants, follow-ups, and probe links are present.
- Step view nodes all exist in `highLevelArchitecture.nodes`.
- Step view string links all exist in `highLevelArchitecture.links`.
- Option view nodes and string links resolve.
- Final-design view nodes and links resolve.
- Step highlights resolve to nodes in the displayed step views.
- `satisfies.functional[*].steps` and `satisfies.nonFunctional[*].steps`
  resolve to real step IDs.
- `step.parent` for `replication-vs-ec` resolves to `durability`.
- Pattern references and probe links resolve.
- No generated `docs/` changes are needed for this review file alone.

Potential dataset polish:

- Several options and flows use `name` rather than `title`, which is consistent
  with this repo's option shape, but ad hoc jq summaries that look for `title`
  report them as null. No renderer issue was observed from static checks.
- The dataset has no `technologyChoices`; that is optional, but adding it would
  match the stronger book cases.
- The API `POST /{bucket}/{key}?uploads` has no sequence while the two simpler
  endpoints do. Multipart is important enough to deserve a sequence.

## Recommended Edits, Prioritized

### P1: Add capacity numbers and use them in the design

Add PUT/GET/LIST/DELETE rates, object-size distribution, metadata footprint,
storage overhead, bandwidth, repair budget, and hot-bucket assumptions. Tie
those numbers to metadata sharding, EC/replication choice, bucket index design,
and repair scheduling.

### P1: Expand the API and metadata model to cover requirements

Add delete, list, multipart part/complete/abort, version-specific reads,
conditional/idempotent writes, checksum headers, and range/head reads. Add data
model records for buckets, object versions, latest pointers, delete markers,
multipart parts, bucket index entries, placements, and idempotency.

### P1: Decide and document consistency semantics

Define whether read-after-write includes `LIST`, overwrites, deletes, and
versioned reads. Align requirements, Step 7 option text, `satisfies`, and the
API/data model with that decision.

### P2: Make write, read, repair, and GC failure boundaries explicit

Add compact flows or failure drills for durable placement receipt before
metadata commit, degraded reads/reconstruction, retry idempotency after timeout,
metadata commit failure after data write, and GC proof of non-reachability.

### P2: Add security, tenancy, lifecycle, and observability

Thread authz, bucket policies, quotas, encryption/KMS, lifecycle/retention,
audit, metrics, alerts, and operational dashboards through the main design or
add a late production-hardening step.

### P3: Clarify the chosen redundancy policy

Make the default path either hybrid replication/EC or pure EC, then update Step
3 options, Step 3a, final design, and the wrap-up script to say the same thing.

### P3: Add `technologyChoices`

Compare metadata stores, data-node storage engines, repair/index queues,
managed object stores, CDN/front-door options, KMS, and observability tooling.

## What Not To Change

- Keep the metadata/data-plane split as the central organizing mechanism.
- Keep commit-metadata-last as the consistency teaching moment.
- Keep repair/GC in the main walkthrough; it is one of the case's strongest
  differentiators from shallow object-store answers.
- Keep the sub-step comparing replication and EC.
- Keep the diagrams structured rather than adding raw Mermaid to architecture
  steps.

## Bottom Line

This is a strong conceptual S3-like object-storage case with clean renderer
structure and a good interview progression. The next hardening pass should make
the public API, metadata records, capacity math, consistency contract, and
operational safeguards concrete enough that the design can survive production
failure scenarios, not just explain the main architecture.
