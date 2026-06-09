# Review: S3-like Object Storage - System Design

Reviewed file: `data/book/object-storage/interview.json`
Review date: 2026-06-09

## Executive Summary

The latest object-storage revision resolves the major issues from the previous
review. The dataset now has a concrete write-intent/visibility-pointer model,
explicit crash boundaries, strong LIST transaction and cursor semantics, a
consistent data-plane gateway for writes, a degraded-read repair flow,
repair/GC data-model records, technology choices with icons, AI visuals, and an
explainer comic. It now reads as a book-ready S3-like object-storage interview,
not just a conceptual blob-store walkthrough.

The strongest part is the correctness spine: metadata is authoritative for
visibility; data is durable before metadata commit; object version, latest
pointer, bucket index, quota counters, and idempotency result commit together;
LIST is strong by construction; repair and GC preserve durability over time.
The remaining work is mostly precision around the direct GET path, naming
consistency in sequences, and optional visual/book polish.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.85/5 | The main architecture, write state machine, consistency model, durability policy, data model, and capacity framing are now mechanically credible. |
| Production realism | 4.75/5 | Strong coverage of authz, quotas, KMS, idempotency, repair, degraded reads, GC, hot prefixes, and technology choices; the direct read-token boundary could be stated more explicitly. |
| Pedagogical flow | 4.80/5 | The steps now expose one pressure point at a time and build cleanly toward the final design. |
| Dataset/rendering fit | 4.85/5 | JSON parses, option views validate, references resolve, AI assets exist, and review-only changes require no docs rebuild. |
| Overall | 4.80/5 | Strong and ready to use, with a short list of refinement edits rather than structural gaps. |

## What Works Well

- The write-state-machine issue is fixed. `object_versions` now explicitly
  starts as `pending_data`, invisible until `object_latest` and `bucket_index`
  point at it in the commit transaction.
- Step 4 now teaches the key correctness model directly: idempotency reserved,
  write intent created, bytes made durable, then version/latest/index/quota and
  idempotency result committed together.
- Crash outcomes are now concrete: before data durable, after data durable but
  before metadata commit, and after commit but before the client receives the
  response.
- Strong LIST is no longer hand-wavy. The dataset chooses cross-shard
  transactions so hash-distributed object metadata and range-partitioned bucket
  index rows can commit atomically.
- Pagination semantics are explicit: live key-ordered range scans with an
  opaque last `(key, version)` cursor, not a snapshot of a trillion-key bucket.
- The data path is mostly normalized. `EC` is now the "Data-Plane Gateway
  (Replication / Erasure Coder)", and PUT streams bytes through it before the
  metadata commit.
- The maintenance step is now operational. It includes scrub cadence,
  quarantine, prioritized repair, repair throttling, degraded reads, GC
  non-reachability proof, and data-model records for `quarantined_shards`,
  `repair_jobs`, and `gc_marks`.
- The API and data model now support the behavior promised later: multipart
  initiate/upload/complete/abort, range GET, versioned reads, checksums,
  conditional writes, idempotency keys, storage class, KMS key references,
  lifecycle, retention, and legal hold.
- The final design integrates the steps instead of introducing new components
  at the end.
- Presentation has caught up: requirements/capacity/final design visuals,
  step/option visuals, technology-choice icons, and an explainer comic are now
  wired into the source dataset.

## Highest-Impact Issues

### 1. The direct GET path needs an explicit read-token/security boundary

The design intentionally lets the client read bytes directly from `DataNodes`
after metadata resolution. That can be a valid high-throughput shape, but the
dataset should state the control-plane boundary as explicitly as it now states
the PUT commit boundary.

Why it matters: `DataNodes` cannot trust a client merely because it knows shard
locations. A candidate should be able to explain how direct reads preserve
authz, tenant isolation, placement freshness, checksums, and range-read
integrity without routing every byte through the metadata service.

Concrete fix:

- Say that `MetaSvc` returns a short-lived, scoped read plan or signed token
  containing bucket/key/version, allowed byte range, placement epoch, and expiry.
- State that `DataNodes` verify the token before serving shards and reject
  stale placement epochs.
- For degraded reads, clarify whether reconstruction happens in the client SDK
  or a gateway/reconstructor service. The current maintenance sequence uses
  `EC` as `Gateway / Reconstructor`; make that the stated fallback path.
- Mention response integrity: range reads return per-range checksums or are
  validated against object/part checksums from metadata.

### 2. Sequence labels still lag the renamed data-plane gateway

The high-level node label is now "Data-Plane Gateway (Replication / Erasure
Coder)", but some sequence participants still label `EC` as "Erasure Coder".
That is minor, but it reintroduces the old ambiguity about whether `EC` is just
an encoder, a gateway, or a reconstruction service.

Concrete fix:

- Rename sequence participant labels consistently to "Data-Plane Gateway" or
  "Data-Plane Gateway / Reconstructor".
- In the durability step, use "replication/EC pipeline" for the algorithm and
  reserve `EC` as the service/node label.
- Keep the final design caption as the source of truth: client resolves through
  API/metadata, PUT bytes stream to the gateway, GET bytes read from data nodes
  with a signed plan, and degraded GET can route through reconstruction.

### 3. The strong-LIST choice is correct, but the cost should be surfaced in the wrap-up

Step 7 now makes the right choice: cross-shard transactions keep point reads
hash-distributed while the bucket index remains range-partitioned for LIST. The
design is credible, but this is an expensive product decision and deserves a
clear "what this costs us" note in the final design or technology choices.

Concrete fix:

- Add a final-design sentence that strong LIST requires a transaction-capable
  metadata store and makes PUT/DELETE latency depend on both the object shard
  and bucket-index shard.
- In technology choices, call out that stores without cross-shard transactions
  must either co-locate rows, weaken LIST, or build a reconciliation/watermark
  layer.
- Add one metric to the observability concern: cross-shard commit latency and
  abort/retry rate by bucket/index partition.

### 4. Optional book polish remains, not core design work

The dataset now has AI visuals and tech icons, but a few presentation details
can still be improved:

- `satisfies.*` cards do not yet have per-requirement `aiVisual` illustrations.
  This is optional, but those visuals would make the Design vs. Requirements
  wrap-up match newer richly illustrated cases.
- Pattern/concept entries do not have small icons. Again optional, but useful in
  the book group where pattern teaching is a recurring surface.
- Several technology chips still use the generic `tech.png` fallback
  (`FoundationDB`, `MinIO`, `OpenTelemetry`, `KEDA`, and others). Schema-wise
  this is valid; visually, adding mappings in `_media/index.yaml` would make
  the technology table more polished.

## System Design Soundness

The design is now sound for the stated scope: multi-zone durability inside one
region, with cross-region replication and regional disaster recovery explicitly
left as follow-ups.

The core invariants are strong:

- metadata owns visibility;
- data nodes store opaque encrypted bytes/shards;
- data is durably written before metadata points to it;
- uncommitted durable bytes are invisible and reclaimable;
- committed versions, latest pointers, bucket-index entries, quotas, and
  idempotency results are one metadata transaction;
- versioning and delete markers share the same visibility-pointer model;
- LIST is strongly consistent because the bucket index participates in the
  commit;
- multipart upload only becomes visible on validated, idempotent complete;
- scrub, repair, quarantine, and GC preserve the durability contract after the
  initial write.

Capacity is useful and tied to design choices. The dataset now quantifies
object count, logical bytes, object-size distribution, PUT/GET/LIST/DELETE
rates, metadata footprint, storage overhead, repair targets, and failure
domains. The numeric comparison between 3x replication and EC 10+4 is especially
helpful because it explains why the hybrid policy is not cosmetic; it is the
difference between roughly 3 EB and 1.4 EB raw storage for 1 EB of cold logical
data.

The API is also strong. It covers the minimum S3-like operations plus the
details candidates often miss: HEAD, versioned GET, range GET, conditional
writes, checksums, idempotency keys, multipart completion, abort, storage class,
and KMS key references. The main missing API detail is not an endpoint; it is
the signed direct-read plan described above.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Store the Blob on One Fileserver

This remains a clean baseline. It ties single-machine failure to three separate
ceilings: durability, total bytes/object count, and NIC throughput. It does not
overstay its purpose.

Keep as-is.

### Step 2: Split Metadata from Data

This is now a strong first real architecture step. It introduces the authority
boundary early: data nodes do not decide object visibility, metadata does. The
step also correctly places authz and quota checks in the metadata/control plane.

Suggested improvement: when describing direct GETs, mention that metadata
returns a signed read plan, not just raw locations.

### Step 3: Durability: Replication vs Erasure Coding

This step now has the right default and the right numeric teaching point.
Tiered replication for hot/small objects plus EC for large/cold objects is the
production-realistic answer, and the 3 EB vs 1.4 EB example makes the trade-off
obvious.

Suggested improvement: keep the lifecycle migration caveat visible. Moving
objects from replicated to EC form creates background work and should be
throttled like repair.

### Step 3a: Replication vs Erasure Coding

The sub-step adds useful depth without interrupting the main path. It explains
read/repair amplification and failure-domain placement clearly.

Keep as a sub-step.

### Step 4: Read-After-Write via Commit Ordering

This is now the strongest correctness step in the interview. It explicitly
names the write intent, visibility pointer, state transitions, crash outcomes,
and idempotent retry behavior. It also connects GET/HEAD/LIST consistency to
the same metadata commit.

Suggested improvement: align the `EC` sequence participant label with the newer
data-plane gateway name.

### Step 5: Multipart Upload for Large Objects

This is now credible and detailed. It covers parallel part upload, part
replacement, validation on complete, idempotent complete, abort, TTL cleanup,
and the common ETag trap.

Suggested improvement: none required. The ETag explanation is a strong teaching
detail.

### Step 6: Scrubbing, Repair, and Garbage Collection

This step improved the most. The degraded-read flow, quarantine, repair queue,
repair prioritization, throttling, mark/sweep GC, placement epochs, retention,
legal hold, and pending-intent cleanup are all present.

Suggested improvement: make the reconstructor role match the direct-read model:
client SDK reconstruction for normal cases, gateway reconstruction for
degraded/fallback cases, or one of those consistently.

### Step 7: Listing, Sharding, and Availability at Scale

The listing design is now precise. It explains hash-sharded object metadata,
range-partitioned bucket index, cross-shard transactions, live pagination, hot
prefixes, adaptive splitting, fanout caps, and cache/shielding for hot ranges.

Suggested improvement: add one wrap-up line that strong LIST shifts complexity
and latency into PUT/DELETE commits.

## Final Design Review

The final design is coherent and integrates every major step:

- request boundary: `Client` and `Front-End / API`;
- metadata/control plane: `Metadata Service`, `Metadata Store`, `Placement`;
- data plane: `Data-Plane Gateway (Replication / Erasure Coder)` and `Storage
  Data Nodes`;
- large objects: `Multipart Upload Coordinator`;
- long-term durability: `Repair / Scrubber`;
- cleanup: `Garbage Collector`;
- strong listing: `Bucket Index`.

The final design description now states policy and invariants, not just
components. It covers tiered redundancy, idempotent commit-last writes, strong
GET/HEAD/LIST, the write state machine, multipart completion, repair throttling,
GC safety, KMS encryption, audit, degraded reads, and hot-object caching.

The only final-design addition I would make is the direct-read security
boundary: metadata returns a scoped signed read plan, data nodes verify it, and
degraded reads can route through the gateway/reconstructor.

## Concept Introduction and Learning Flow

The concept staging is strong:

- metadata/data split before placement;
- redundancy before consistency;
- write intent and visibility pointer before multipart completion;
- multipart before GC;
- repair/GC before listing at scale;
- technology choices after the architecture has enough surface to compare.

The dataset now introduces the right senior/staff-level concepts: failure
domains, replication, erasure coding, tiered redundancy, commit metadata last,
idempotency, write intents, version/latest pointer semantics, delete markers,
strong LIST, live pagination, multipart ETag caveats, repair amplification,
degraded reads, quarantine, GC non-reachability proof, envelope encryption,
quota, and observability.

## Step-to-Final-Design Coherence

Coherence is high. The old mismatches are fixed:

- the default durability option now matches the final hybrid policy;
- strong LIST is explicit in requirements, data model, step 7, and final design;
- write-intent semantics are represented in prose and data model;
- degraded read and repair are represented as both prose and a sequence flow;
- technology choices reflect the major architecture concerns;
- presentation assets are wired for most visual surfaces.

Remaining coherence issues are minor:

- `EC` sequence labels should match the gateway terminology;
- the direct GET path should state its signed read plan;
- the cost of strong LIST should be repeated in the final/wrap-up section.

## Realism Compared With Production Systems

The case now compares well with production object-storage systems. It covers
the distinctive hard parts: exabyte capacity, trillions of metadata rows,
durability math, hybrid redundancy, placement, read-after-write consistency,
strongly consistent listing, multipart upload, repair, scrub, GC, lifecycle,
authz, quotas, KMS, audit, observability, and technology tradeoffs.

The remaining realism opportunities are narrow:

- state the short-lived token/read-plan model for direct data-node reads;
- expose cross-shard commit latency and hot-index pressure as first-class
  metrics;
- keep foreground request traffic isolated from repair/index/lifecycle queues;
- make direct-read degraded reconstruction flow through a named gateway or SDK;
- map fallback technology icons for a more polished technology table.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- `_scripts/validate_options.py data/book/object-storage/interview.json`
  returns OK.
- `node --check _templates/interview.js` and
  `node --check _templates/overview.js` pass.
- Step view nodes resolve to `highLevelArchitecture.nodes`.
- Step view links resolve to `highLevelArchitecture.links`.
- Option view nodes and links validate.
- Final-design view nodes and links resolve.
- `satisfies.functional[*].steps` and
  `satisfies.nonFunctional[*].steps` resolve to real step IDs.
- `technologyChoices[*].steps` and `patterns[*].steps` resolve to real step
  IDs.
- `step.parent` for `replication-vs-ec` resolves to `durability`.
- Raw `diagram` fields are not present in structured architecture steps.
- AI visual references exist under `assets/generated/ai-visuals/`, and the
  explainer comic exists under `assets/generated/comic/`.
- The source review file is repo-only; no generated `docs/` rebuild is needed
  for this review update.

Potential dataset polish:

- Per-requirement Design vs. Requirements illustrations are not present.
- Pattern entries do not have icons.
- Several technology choices still use the generic `assets/tech-icons/tech.png`
  fallback. This is valid but less polished than mapped icons.

## Recommended Edits, Prioritized

### P1: Add the direct-read authorization and integrity boundary

Document signed read plans or scoped tokens returned by metadata, token
verification on data nodes, placement epoch checks, and range-read checksum
validation.

### P1: Normalize `EC` labels across sequences

Use "Data-Plane Gateway" consistently, with "Replication / Erasure Coder" as
the function and "Reconstructor" only where degraded reads need it.

### P2: Surface strong-LIST cost in final/wrap-up text

Add the latency/operational cost of cross-shard metadata commits and the
fallback choices if a selected metadata store cannot provide them.

### P2: Add observability metrics for the new precision points

Include cross-shard commit latency, index-partition hotness, read-token
rejection/stale-placement rate, degraded-read count, repair backlog age, scrub
coverage, orphan bytes, and GC sweep skips due to retention/legal hold.

### P3: Complete optional book visuals and icon mapping

Add per-requirement `aiVisual` illustrations, pattern icons, and additional
technology icon mappings for current `tech.png` fallbacks.

## What Not To Change

- Keep the metadata/data-plane split as the central organizing mechanism.
- Keep tiered replication plus erasure coding as the selected durability
  policy.
- Keep commit-metadata-last and the write-intent/visibility-pointer model as
  the main correctness lesson.
- Keep LIST strongly consistent; the dataset now explains the cost clearly
  enough to make it a deliberate product choice.
- Keep repair, scrub, degraded reads, and GC in the main walkthrough rather
  than moving them to follow-ups.
- Keep cross-region replication as a scoped follow-up unless requirements are
  expanded across the whole dataset.

## Bottom Line

The object-storage interview is now one of the stronger book datasets. The
recent changes resolved the previous core correctness gaps; the remaining work
is targeted polish around direct-read security, sequence naming, strong-LIST
cost visibility, and optional visuals/icons.
