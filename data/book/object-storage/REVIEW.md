# Review: S3-like Object Storage - System Design

Reviewed file: `data/book/object-storage/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent hardening pass materially improved this dataset. The previous major
gaps around qualitative capacity, missing API endpoints, thin metadata records,
ambiguous LIST consistency, missing security/tenancy, and absent technology
choices are now largely addressed. The interview now reads like a credible
S3-like object-storage case rather than a conceptual blob-store sketch.

The core teaching spine is strong: start with a single-server baseline, split
metadata from data, choose tiered replication/erasure coding, commit metadata
last, support multipart upload, maintain durability with scrub/repair/GC, and
scale listing through a strongly consistent bucket index. The remaining work is
mostly precision: make the write state machine concrete enough to remove row
lifecycle ambiguity, tighten the strong-LIST transaction and pagination story,
choose one data-path shape for client uploads/downloads, and add a few
production flows for degraded reads, repair, and GC.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.55/5 | Correct architecture, capacity framing, API, metadata model, consistency contract, and durability policy; a few transactional and state-machine details still need sharper boundaries. |
| Production realism | 4.35/5 | Authz, quotas, KMS, idempotency, lifecycle, repair, GC, observability, and technology choices are present; degraded-read/repair/GC execution flows could be more explicit. |
| Pedagogical flow | 4.55/5 | The sequence of decisions is clear and interview-friendly; the case now teaches one pressure point at a time without losing the final design. |
| Dataset/rendering fit | 4.75/5 | JSON parses; step, option, and final-design view references resolve; sequence participant references resolve; review-only edits do not require a docs rebuild. |
| Overall | 4.50/5 | A strong book-ready case with a few precision edits left before it is excellent. |

## What Works Well

- Capacity is now useful. It names object count, bytes, object-size mix,
  PUT/GET/LIST/DELETE rates, metadata footprint, storage overhead, repair
  targets, and failure domains.
- The API now matches the requirements: PUT, GET, HEAD, DELETE, LIST, multipart
  initiate/upload/complete/abort, version reads, checksums, conditional writes,
  idempotency keys, auth headers, storage class, and KMS key references.
- The data model now supports the promised behavior: buckets, object versions,
  latest pointers, bucket index, multipart uploads/parts, shard placements, and
  idempotency keys.
- The design makes a clear redundancy choice: replicate hot/small objects and
  erasure-code large/cold objects, with lifecycle transition as objects cool.
- The consistency decision is now explicit: successful PUT/DELETE is visible to
  GET, HEAD, and LIST because version, latest pointer, and bucket index commit
  together.
- Repair and GC are first-class parts of the case. The dataset now discusses
  scrub cadence, checksum quarantine, repair prioritization, repair throttling,
  retention windows, and abandoned multipart upload cleanup.
- Security and tenancy are no longer afterthoughts. Bucket policy, quotas,
  tenant/account ownership, TLS, KMS/envelope encryption, and audit are threaded
  into the requirements, API, model, final design, and wrap-up.
- The final design integrates the components introduced in the steps instead of
  introducing a new architecture at the end.

## Highest-Impact Issues

### 1. The write state machine is strong in prose but still slightly ambiguous in storage

The final design names the right state machine:
`pending_data -> data_durable -> committed -> deleting/delete_marker -> gc_eligible -> reclaimed`.
The `object_versions` table also includes those states, but its note says it is
"one immutable row per (bucket, key, version_id)." That can confuse the most
important correctness boundary: before metadata commit, is there already an
`object_versions` row, a separate write-intent row, or only an idempotency
record plus durable placement receipt?

Why it matters: commit-metadata-last is the central teaching point. If the
candidate cannot state which row exists before visibility and which transaction
flips visibility, retry, GC, and delete-marker behavior become hand-wavy again.

Concrete fix:

- Add a small `write_intents` or `pending_writes` record, or explicitly state
  that uncommitted `object_versions` rows are invisible until `object_latest`
  and `bucket_index` point at them.
- In the PUT and multipart-complete sequences, show the transition:
  idempotency reserved -> data durable receipt -> transaction commits version,
  latest pointer, bucket index, quota/usage counters, and idempotency result.
- State the crash outcomes for each boundary:
  before data durable, after data durable but before metadata commit, and after
  commit but before the client receives the response.

### 2. Strong LIST consistency needs transaction-scope and pagination details

The dataset now correctly chooses strong LIST consistency by committing the
bucket index with the latest pointer. That is the right S3-like semantic. The
remaining gap is implementation precision at the stated scale: 300k PUT/s, 50k
LIST/s, 10T objects, hot buckets, and a key-ordered index.

Why it matters: "same metadata commit" is only credible if the design explains
how the version row, latest pointer, index row, and cursor ordering share a
transaction boundary or a deterministic commit watermark. Otherwise the
candidate gets the right answer without showing how to keep it true under
sharding.

Concrete fix:

- State whether `object_latest` and `bucket_index` are co-located by
  `(bucket, key)` shard or whether the metadata store provides cross-shard
  transactions.
- Define cursor semantics under concurrent writes/deletes. The current
  "last returned key/version" explanation is a good start, but it should say
  whether a page is a snapshot, a monotonic high-watermark scan, or a live range
  scan that may include later commits.
- Add one sentence about hot-bucket mitigation for the ordered index:
  bucket-prefix partitioning, adaptive split points, write fanout limits, or a
  per-bucket sequencer only when necessary.

### 3. The upload/download data path should choose one concrete shape

The architecture intentionally separates metadata and bytes, but the current
diagrams and sequences use three slightly different shapes:

- the high-level link says the client streams data directly to `DataNodes`;
- the PUT API sequence has the client stream to `EC`;
- the final-design caption says the client calls the API and upload coordinator,
  while the replication/erasure coder writes shards to data nodes.

All three are plausible variants, but together they leave the reader unsure
whether `EC` is a gateway, a client library function, an internal service, or a
data-node-side pipeline.

Concrete fix:

- Pick one path and name it consistently. For example: `MetaSvc` returns a
  signed upload plan to the client, the client streams to a data-plane gateway
  that performs replication/EC, and the gateway returns a durable placement
  receipt to `MetaSvc`.
- If clients write directly to data nodes, state how authz tokens, checksums,
  placement epochs, retries, and partial failures are handled.
- If bytes flow through an internal EC service, rename it as a data-plane
  gateway/coordinator and account for backpressure and bandwidth cost.

### 4. Degraded reads, repair, and GC deserve one explicit sequence or mini-flow

The prose and failure drills now cover degraded reads, checksum quarantine,
repair prioritization, and GC safety. That is a big improvement. The dataset
would be stronger if one of those operational paths had the same concrete flow
treatment as PUT and multipart complete.

Concrete fix:

- Add a degraded-read flow: metadata resolves placement, one shard fails
  checksum or times out, the system reads alternate replicas/fragments,
  reconstructs the object, returns correct bytes, quarantines the bad shard, and
  enqueues repair.
- Add a compact GC invariant: only reclaim a placement when no live latest or
  retained version references it, retention/legal hold has passed, and the
  placement generation still matches the metadata row observed during marking.
- Optionally add `repair_jobs`, `quarantined_shards`, or `gc_marks` to the data
  model if you want the operational machinery to be inspectable.

### 5. Cross-region disaster recovery is correctly scoped as an extension, but the scope should be explicit

The design covers racks/zones/failure domains well and includes cross-region
replication in follow-up prompts. It does not promise regional disaster
recovery in the main requirements, which is reasonable for a focused interview.
Because the title says S3-like and the scale is exabytes, make that boundary
explicit.

Concrete fix:

- Add a short non-goal or extension note: "This design covers multi-zone
  durability inside a region; cross-region replication/DR is a follow-up."
- If the intended mainline answer includes multi-region durability, add it to
  requirements, capacity, data model, repair/lifecycle, and final design.

## System Design Soundness

The system design is now strong. The dataset has the important object-storage
mechanisms in the right places:

- metadata is authoritative for visibility;
- data nodes hold opaque bytes/shards;
- placement crosses failure domains;
- redundancy is tiered by object class;
- metadata commits last after durable data write;
- object versions and delete markers preserve overwrite/delete semantics;
- bucket index updates are part of the write contract for strong LIST;
- multipart upload is visible only after validated complete;
- repair and GC maintain the durability and cost properties over time.

The biggest remaining soundness issue is not missing components but exact
transaction boundaries. The design should make it mechanically obvious which
metadata rows exist before and after a crash at each point in PUT, multipart
complete, delete, and GC. This would turn the current strong prose into a fully
defensible correctness story.

Capacity is now good enough for interview use. The numbers are intentionally
round, but they support the later choices: sharded metadata, ordered bucket
index, CDN/cache fronting for hot reads, hybrid redundancy, and repair budget.
One possible addition would be a worked storage-cost example, such as how 1 EB
logical maps to raw storage under 3x replication versus EC 10+4 plus hot-object
replication.

The API shape is much improved. The only API precision I would add is explicit
range GET and versioned GET examples, because range reads are common for object
storage and the response model already mentions version IDs.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Store the Blob on One Fileserver

This remains a clean baseline. It uses the new capacity numbers to show why a
single server fails independently on durability, bytes, object count, and NIC
throughput. Keep it short.

Suggested improvement: none required beyond preserving the baseline as a foil.

### Step 2: Split Metadata from Data

This is the right first architectural move. The step now carries authz/quota
and metadata authority more clearly, and it sets up later versioning and
listing decisions.

Suggested improvement: add one invariant sentence here: data nodes never decide
object visibility; only committed metadata/latest/index rows do.

### Step 3: Durability: Replication vs Erasure Coding

This step now has the right default: tiered replication for hot/small objects
and erasure coding for large/cold objects. The options are realistic rather than
strawmen.

Suggested improvement: add one numeric cost comparison in the step body:
`1 EB logical * 3x = 3 EB raw` versus `1 EB logical * 1.4x = 1.4 EB raw` for
cold data, while acknowledging hot replicated data increases the blended
multiplier.

### Step 3a: Replication vs Erasure Coding

The sub-step is now aligned with Step 3. It teaches the tradeoff compactly:
replication is simple and fast; EC saves storage but increases read/repair
amplification.

Suggested improvement: keep this as a sub-step, not a full top-level step. It
adds depth without interrupting the main architecture progression.

### Step 4: Read-After-Write via Commit Ordering

This remains the strongest correctness step. The option comparison and PUT
sequence now include a durable placement receipt, idempotency, and a single
metadata transaction for version/latest/index.

Suggested improvement: make crash outcomes table-driven:
`client timeout before receipt`, `receipt but no metadata commit`, `commit but
client timeout`, and `duplicate retry with same idempotency key`.

### Step 5: Multipart Upload for Large Objects

The multipart section is now credible: initiate, upload parts, validate etags
and sizes, complete exactly once, abort, and TTL cleanup are all present.

Suggested improvement: explicitly say whether the final ETag is an MD5-style
multipart digest, a content checksum, or an opaque version validator. This is
minor but prevents readers from assuming ETag always equals a full-object hash.

### Step 6: Scrubbing, Repair, and Garbage Collection

This step now feels operational. Scrub cadence, checksum quarantine, repair
priority, bandwidth throttling, and repair targets are all concrete enough for
an interview.

Suggested improvement: add one structured flow or data-model record for repair
jobs/quarantined shards so the operational path is as inspectable as the write
path.

### Step 7: Listing, Sharding, and Availability at Scale

The step now makes the right decision: do not scan every metadata shard for
LIST; maintain a key-ordered bucket index and commit it with the object update.

Suggested improvement: specify whether listing pages are snapshot-consistent,
watermark-consistent, or live scans. Also mention how the ordered index splits a
hot bucket/prefix when one tenant creates a skewed key pattern.

## Final Design Review

The final design is now coherent and high quality. It integrates every major
step:

- `Client` and `Front-End / API` from the request boundary;
- `Metadata Service`, `Metadata Store`, and `Placement Service` from the
  metadata/data split;
- `Replication / Erasure Coder` and `Storage Data Nodes` from durability;
- commit-last write coordination from consistency;
- `Multipart Upload Coordinator` from large-object support;
- `Repair / Scrubber` and `Garbage Collector` from maintenance;
- `Bucket Index` from listing and scale.

The final description is unusually useful because it also states the chosen
policy, not just the components: tiered redundancy, idempotent commit-last
writes, strong GET/HEAD/LIST, repair throttling, GC safety, KMS encryption,
audit, degraded reads, and hot-object caching.

The only final-design polish needed is to resolve data-path naming. Decide
whether `EC` is a client-side/library encoder, a data-plane gateway, or an
internal service that receives streams. Then make the high-level links, API
sequence, step captions, and final caption all say the same thing.

## Concept Introduction and Learning Flow

The concept sequence is strong and just-in-time:

- metadata/data split before placement;
- redundancy before consistency;
- commit ordering before multipart complete;
- multipart before GC;
- repair/GC before listing at scale;
- technology choices after the design has enough surface area to compare.

The dataset now introduces most of the concepts a senior candidate needs:
failure domains, replication, EC, tiered redundancy, commit metadata last,
idempotency, version/latest pointer semantics, delete markers, multipart
completion, repair amplification, degraded reads, bucket index consistency,
envelope encryption, quota, and observability.

The learning flow would benefit from one small addition: make "write intent" or
"visibility pointer" a named concept. It is the mental model that ties
commit-last PUT, multipart complete, delete markers, LIST, retry idempotency,
and GC together.

## Step-to-Final-Design Coherence

Coherence is now high. The previous mismatch between the default EC option and
the hybrid policy is fixed. The previous mismatch between eventual LIST wording
and S3-like expectations is fixed. The previous missing API/data-model surfaces
are fixed.

Remaining coherence gaps:

- data path terminology differs slightly between high-level links, API
  sequences, and captions;
- the write state machine is in final-design prose but not represented as a
  distinct flow/table in the earlier steps;
- repair/GC concepts are present but less diagrammed than PUT and multipart.

These are precision issues, not structural failures.

## Realism Compared With Production Systems

The case now compares well with production object-storage systems. It covers
the distinctive hard parts: exabyte capacity, trillions of metadata rows,
durability math, hybrid redundancy, placement, read-after-write, strongly
consistent listing, multipart upload, repair, scrub, GC, lifecycle cleanup,
authz, quotas, KMS, audit, observability, and technology tradeoffs.

The remaining realism opportunities are operational:

- define how data-plane upload tokens or signed placement plans work;
- isolate repair/index/lifecycle queues from foreground request traffic;
- show degraded-read fallback as a flow, not only as prose;
- state how metadata shard splits preserve ordered LIST semantics;
- clarify whether cross-region replication is a follow-up or part of the
  offered durability product;
- add SLO-oriented metrics: p99 GET/PUT latency, list latency, objects below
  target redundancy, repair backlog age, scrub coverage, orphan bytes, quota
  rejection rate, KMS failures, and hot-prefix pressure.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- Top-level dataset structure is valid for this project: requirements,
  capacity, API, data model, patterns, steps, final design, satisfies,
  technology choices, interview script, level variants, follow-ups, and probe
  links are present.
- Step view nodes resolve to `highLevelArchitecture.nodes`.
- Step view links resolve to `highLevelArchitecture.links`.
- Option view nodes and links resolve.
- Final-design view nodes and links resolve.
- Step highlights resolve to nodes in the displayed step views.
- API sequence and step flow messages reference declared participants.
- `satisfies.functional[*].steps` and `satisfies.nonFunctional[*].steps`
  resolve to real step IDs.
- `technologyChoices[*].steps` and `patterns[*].steps` resolve to real step IDs.
- `step.parent` for `replication-vs-ec` resolves to `durability`.
- The source review file is repo-only; no generated `docs/` rebuild is needed
  for this review update.

Potential dataset polish:

- `technologyChoices` uses bare string chips rather than assigned icon objects.
  That is schema-valid, but running the icon assignment script would make the
  book wrap-up visually match fuller cases.
- The dataset has no AI visuals or explainer comic. Those are optional; the
  structured diagrams are enough for this interview.
- Several sequence/flow objects do not expose a human title in jq summaries.
  This is not a rendering issue, but titles could make future static summaries
  easier to scan.

## Recommended Edits, Prioritized

### P1: Clarify the write-intent / visibility state machine

Add a `write_intents` record or explicitly document invisible pre-commit
`object_versions`. Show when idempotency, durable placement receipt,
object-version creation, latest pointer, bucket index, and quota counters are
reserved or committed.

### P1: Define strong-LIST transaction and cursor semantics

State the transaction/co-location model for `object_latest` plus
`bucket_index`, and specify whether pagination is snapshot, watermark, or live
range scanning under concurrent writes/deletes.

### P1: Normalize the data-path role of `EC`

Choose whether `EC` is a gateway, library, internal service, or data-node-side
pipeline. Align high-level links, API sequences, step captions, and final
caption.

### P2: Add one degraded-read / repair / GC flow

Add a concrete sequence for checksum failure and degraded read, or a compact
maintenance flow showing quarantine, repair job enqueue, rebuild, and GC
non-reachability proof.

### P2: Make regional scope explicit

State that the main design is multi-zone/single-region unless cross-region
replication is promoted from follow-up to a core requirement.

### P3: Add visual/book polish

Optionally assign technology-choice icons and add AI visuals or an explainer
comic later. These are presentation improvements, not design blockers.

## What Not To Change

- Keep the metadata/data-plane split as the central organizing mechanism.
- Keep tiered replication plus erasure coding as the selected durability
  policy.
- Keep commit-metadata-last as the main correctness lesson.
- Keep LIST strongly consistent now that the requirements explicitly promise
  it.
- Keep repair, scrub, and GC in the main walkthrough rather than moving them to
  follow-ups.
- Keep the current step order; it builds naturally from baseline to final
  design.

## Bottom Line

The object-storage interview has moved from "solid conceptual overview" to a
strong production-oriented case. The remaining edits are about removing the last
ambiguities in transaction boundaries, pagination semantics, and data-plane
roles. After those, this should be one of the stronger book datasets.
