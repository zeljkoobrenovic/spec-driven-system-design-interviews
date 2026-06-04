# Review: Live Comments / Presence - System Design

Reviewed file: `data/book/live-comments/interview.json`
Review date: 2026-06-04

## Executive Summary

This second pass finds a much stronger dataset. The earlier major gaps around
moderation, API contracts, capacity math, data modeling, partitioning, and
operability have largely been addressed in the source JSON. The case now teaches
the key live-comments shape well: authenticated/comment-idempotent ingest,
moderation before broadcast, a per-room bus, gateway-tier fanout, sampled
delivery, approximate reaction/presence counts, bounded backpressure, and
mega-room slicing.

The remaining issues are narrower and mostly about consistency between the
written design and diagrams. The most important one: the text and final design
correctly say `Bus -> Sampler -> Fanout`, but some high-level and step-4
diagrams still show the older `Fanout -> Sampler` path. A second issue is that
the room partitioner is modeled like it sits on the comment data path after
fanout, even though it is really a control-plane assignment mechanism.

| Axis | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | Core mechanisms are now production-plausible; sampling/partitioner data-path diagrams need cleanup. |
| Production realism | 4/5 | Stronger API, data model, failure drills, and SLOs; still light on regional topology and accepted-comment persistence semantics. |
| Pedagogical flow | 4.5/5 | Clear step progression with better numbers and deep dives; add a couple more flows for sampled delivery and reconnect. |
| Dataset/rendering fit | 4/5 | JSON and references validate; no renderer-breaking issues found. |

## What Improved

- Capacity now gives a concrete hot-room scenario and converts impossible
  delivery work into bounded gateway/sampling work
  (`data/book/live-comments/interview.json:340`).
- The API now includes auth/session, room epoch, resume sequence, idempotent
  `clientMessageId`, moderation outcomes, reaction batching, and throttling
  (`data/book/live-comments/interview.json:382`).
- Moderation is now a real gate before broadcast, with allow, reject,
  quarantine, and timeout behavior in both text and flow
  (`data/book/live-comments/interview.json:719`,
  `data/book/live-comments/interview.json:776`).
- The data model now supports registry leases, room slices, room epochs,
  idempotent comments, moderation status, retention/redaction, and windowed
  reaction tallies (`data/book/live-comments/interview.json:505`).
- Step 7 now teaches mega-room slicing, room epochs, registry TTL, slice-level
  failure isolation, and operational SLOs
  (`data/book/live-comments/interview.json:1541`,
  `data/book/live-comments/interview.json:1579`).

## Highest-Impact Issues

### 1. Sampling path is inconsistent between text and diagrams

The sampling text says the right thing: sampling sits after moderation and
before fanout; the sampler reads the moderated bus and emits rate-capped
batches (`data/book/live-comments/interview.json:1091`). The final design also
uses `bus-sampler` then `sampler-fanout`
(`data/book/live-comments/interview.json:1682`).

But the high-level architecture still keeps a legacy `fanout-sampler` link
(`data/book/live-comments/interview.json:196`), and step 4's main view still
uses `fanout-sampler` plus `fanout-gateway`
(`data/book/live-comments/interview.json:1101`). The random-sampling option
repeats the same path (`data/book/live-comments/interview.json:1132`).

Why it matters: readers may conclude fanout first expands raw comments and then
sampling happens, which undermines the capacity lesson. The point of the design
is that the sampler reduces the stream before gateway fanout multiplies it.

Concrete fix: make step 4's view use `Bus`, `Sampler`, `Fanout`, and `Gateway`
with links `bus-sampler`, `sampler-fanout`, and `fanout-gateway`. Remove
`fanout-sampler` if it is no longer used, or restrict it to an explicitly bad
alternative diagram.

### 2. The room partitioner looks like a data-path component after fanout

Step 7 correctly describes the room partitioner as assigning `(room_id,
slice_id)` ownership and versioning those assignments with a room epoch
(`data/book/live-comments/interview.json:1544`). The deep dive also frames it
as slice assignment and registry mapping (`data/book/live-comments/interview.json:1581`).

The diagram link, however, is `Fanout -> Partitioner` labeled "slice assignment
(mega-room)" (`data/book/live-comments/interview.json:214`), and the final
design includes `sampler-fanout`, `fanout-partitioner`,
`partitioner-roomreg`, and `fanout-roomreg`
(`data/book/live-comments/interview.json:1682`). This can read as if every
comment batch flows from fanout through the partitioner before reaching the
registry.

Why it matters: partitioning should be a control-plane decision that produces
assignments consumed by gateways/fanout workers, not a hot-path hop for every
comment. Putting it on the data path makes the design look more expensive and
adds an artificial bottleneck.

Concrete fix: model partitioning as control plane. Prefer `Partitioner ->
RoomReg` and `Fanout -> RoomReg`, with the caption saying fanout reads current
slice assignments. If a link from fanout to partitioner remains, label it as
"refresh assignment" and treat it as control-plane, not per-message flow.

### 3. Accepted-comment persistence is still slightly ambiguous

The pipeline text says only accepted comments are persisted for VOD if needed
(`data/book/live-comments/interview.json:721`), but the shared architecture link
is still `Ingest -> Store` (`data/book/live-comments/interview.json:261`), and
the pipeline view includes that link next to the moderation gate
(`data/book/live-comments/interview.json:733`).

Why it matters: a public live-comment system usually should not persist
rejected/unsafe raw comments in the same replay store that powers VOD. It may
keep rejected content in quarantine/audit storage, but that is a different
retention and access-control policy.

Concrete fix: either relabel `ingest-store` as "persist accepted comment" and
explain it happens after the allow verdict, or model `Moderation -> Store` /
`Bus -> Store` for accepted comments and keep `ReviewQueue` for rejected ones.

### 4. The richer operations story is not reflected in the interview script or level rubric

The dataset now contains strong operations material: fanout lag, gateway buffer
depth, drop rate, sampling ratio, reconnect rate, registry staleness,
moderation latency, quarantine backlog, and counter freshness
(`data/book/live-comments/interview.json:1591`). But the interview script still
uses the older high-level bullets and does not prompt the candidate to mention
moderation safety, idempotent APIs, leases/epochs, or SLOs
(`data/book/live-comments/interview.json:1795`). The staff rubric also remains
mostly about fanout, partitioning, backpressure, and sampling
(`data/book/live-comments/interview.json:1849`).

Why it matters: the content now supports staff-level production discussion, but
the wrap-up scaffolding underuses it.

Concrete fix: add one sentence in the deep-dive or wrap-up phase that asks for
"operability and safety: moderation fail-closed, idempotent retries,
lease/TTL registry, room epochs, and SLOs." Add one staff expectation about
operating the system under event spikes with explicit shed signals.

## System Design Soundness

The core design is sound. The requirements include the right product and
non-functional constraints, including the newly added safety and operability
requirements (`data/book/live-comments/interview.json:322`). The capacity
section now does the important conversion: 25B naive deliveries/sec becomes
25M upstream gateway pushes/sec with hierarchical fanout, and then about 100K
upstream pushes/sec after a 20 comments/sec room cap
(`data/book/live-comments/interview.json:347`,
`data/book/live-comments/interview.json:362`).

The architecture has all major components: connection gateway, WebSocket
gateway, ingest, moderation, quarantine, bus, sampler, fanout workers,
partitioner, registry, presence, reaction aggregator, and optional store. The
remaining soundness concern is not missing components but the visual data path:
make sampled delivery consistently `Bus -> Sampler -> Fanout -> Gateway`, and
keep partitioning out of the per-comment hot path.

The API and data model now support the behavior the steps promise. The main
contract improvements are auth/session, room epoch, best-effort resume,
idempotent comments, moderation status, reaction batching, registry leases, and
time-windowed reaction tallies.

## Step-by-Step Pedagogical Review

### Step 1: Naive polling

Strong. It now includes the concrete 2.5M reads/sec polling math, which makes
the failure obvious (`data/book/live-comments/interview.json:675`).

### Step 2: Ingest and per-room bus

Strong. This step now teaches moderation as a true gate, idempotent ingest,
rate limits, quarantine, and fail-closed behavior. The sequence flow is a useful
addition. The only remaining issue is the accepted-comment persistence arrow
discussed above.

### Step 3: Gateway fanout

Still the strongest teaching step. The O(gateways) versus O(viewers) comparison
is now backed by the same numbers used in capacity
(`data/book/live-comments/interview.json:846`). The alternatives are credible.

### Step 4: Sampling

Conceptually strong and now connected to capacity math and moderation. The text
is correct about sampling after moderation and before fanout. The diagram and
option views should be updated to match the text.

### Step 5: Presence and reactions

Strong. It now distinguishes concurrent connections from unique viewers,
defines a freshness/error target, and uses time-windowed deltas
(`data/book/live-comments/interview.json:1255`). The HLL option is framed as a
unique-viewer estimate, which avoids a common conceptual mistake.

### Step 6: Backpressure

Much stronger. It now names concrete policies: bounded per-connection buffers,
drop-oldest for comments, count coalescing, a bus retention window, disconnect
thresholds, and shed metrics (`data/book/live-comments/interview.json:1483`).

### Step 7: Scaling rooms and gateways

Much stronger. The room-slicing deep dive and SLO dashboard are exactly the
kind of staff-level detail this case needed. The main cleanup is diagrammatic:
represent the partitioner as assignment/control plane rather than hot-path
message processing.

## Final Design Review

The final design is now production-plausible and integrates nearly all earlier
steps. It covers authenticated/idempotent ingest, moderation gating, quarantine,
sampled fanout, approximate counts, bounded backpressure, room slicing, epochs,
registry rebuild, and reconnect behavior
(`data/book/live-comments/interview.json:1652`).

The final design diagram should be revised only for clarity: remove the legacy
`Fanout -> Sampler` path from the global architecture if the final path is
`Bus -> Sampler -> Fanout`, and avoid placing `Partitioner` after fanout in the
data path.

## Realism Compared With Production Systems

The design now handles most realism concerns that matter for this interview:

- Safe posting: auth, rate limits, idempotency, moderation allow/drop, and
  quarantine.
- Massive fanout: gateway-tier fanout, sampling, and mega-room slicing.
- Bounded loss: drop/coalesce policies and best-effort reconnect semantics.
- State recovery: registry lease/TTL, heartbeats, room epoch, stale assignment
  protection.
- Operations: fanout lag, drop rate, buffer depth, sampling ratio, moderation
  backlog, registry staleness, reconnect rate, and counter freshness.

Remaining realism polish:

- Add regional topology if this case is meant to go beyond one event region:
  where viewers terminate, how room slices are placed by region, and how global
  counts roll up.
- Clarify accepted-comment persistence versus quarantine/audit retention.
- Add one sequence flow for gateway reconnect and registry rebuild.

## Dataset and Renderer-Facing Observations

No renderer-breaking issues found:

- JSON parses successfully.
- Step `view.nodes` string references resolve to high-level architecture nodes.
- Step `view.links` string references resolve to high-level architecture links.
- Final-design node and link references resolve.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- `patterns[*].steps[*]` references resolve to real step IDs.
- `probeLinks` references resolve to `toProbeFurther.links`.
- Step sequence messages reference declared participants.
- View groups resolve to declared architecture groups.

Dataset-facing polish:

- Remove or repurpose the legacy `fanout-sampler` link after updating the
  sampling views.
- Add structured flows for sampled delivery, slow-client backpressure, and
  reconnect/registry rebuild. The new moderation flow is good; the rest would
  make the operational story easier to inspect.
- Consider adding `technologyChoices` later if this case should match the full
  flagship book-dataset format.

## Recommended Edits, Prioritized

### P1: Reconcile sampling diagrams with the final data path

Update step 4 and its default option to show `Bus -> Sampler -> Fanout ->
Gateway`. Remove `fanout-sampler` unless it is intentionally used in a rejected
alternative.

### P1: Separate partitioner control plane from comment data path

Revise the scale/final diagrams so `Partitioner` writes assignments to
`RoomReg`, and `Fanout` reads those assignments. Avoid implying every comment
batch is processed by the partitioner.

### P2: Clarify accepted-comment persistence

Make the persistence arrow and caption say accepted comments only, or move the
store write after moderation/bus. Keep rejected comments in quarantine/audit
storage with separate semantics.

### P2: Update interview script and level variants

Add prompts and expectations for moderation safety, retry idempotency,
lease/TTL registry, room epochs, and SLO-driven operations.

### P3: Add more sequence flows

Add sampled delivery, slow-client backpressure, and gateway reconnect flows.

## What Not To Change

- Keep the narrow focus on live comments/presence, not full video streaming.
- Keep best-effort delivery as an explicit product decision.
- Keep sampling as a first-class architectural mechanism.
- Keep the gateway-tier fanout comparison; it remains the core teaching moment.
- Keep the new capacity math and operations deep dive.

## Bottom Line

This dataset is now strong and close to production-realistic for an interview
walkthrough. The next pass should be cleanup, not a redesign: align the
sampling diagrams with the corrected data path, treat partitioning as control
plane, clarify accepted-comment persistence, and update the script/rubric to
surface the improved safety and operations content.
