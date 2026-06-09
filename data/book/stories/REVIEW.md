# Review: Stories (Ephemeral Content) System Design

Reviewed file: `data/book/stories/interview.json`
Review date: 2026-06-05

## Executive Summary

This dataset is now a strong book-quality story-system interview. The recent
production pass fixed the largest gaps from the prior review: concrete capacity
work units, `FanoutQueue`, idempotent tray fanout, `ViewSvc`, `ViewLog`,
`ViewAggregator`, `ViewerStore`, observability, explicit media expiry wording,
basic audience scope, technology choices, and operational failure drills are now
all present.

The remaining issues are narrower. The design promises audience controls, but
the data model and read/view flows do not yet make audience policy concrete.
Some API sequence diagrams still describe the older simpler architecture,
especially the create and tray-read paths. Capacity is much more useful than
before, but it stops before sizing the derived stores and bandwidth-heavy paths
that drive partitioning. Step 7 is valuable as an operational wrap-up, though it
is still less of a decision exercise than the earlier steps.

| Dimension | Rating | Notes |
|---|---:|---|
| System design soundness | 4.4 / 5 | TTL, fanout, seen-state, expiry filtering, async views, and rebuildable state are coherent. Audience policy and read authorization need firmer modeling. |
| Production realism | 4.1 / 5 | Good queueing, dedup, media-expiry, observability, and technology choices. Still thin on privacy mutations, moderation/takedown, and derived-state sizing. |
| Pedagogical flow | 4.5 / 5 | The naive baseline motivates each mechanism cleanly. Step 7 is useful but more summary than trade-off exploration. |
| Final design coherence | 4.3 / 5 | The final diagram now includes the major components introduced in the steps. A few direct cache/store paths should be routed through explicit services or explained as shorthand. |
| Dataset/rendering fit | 4.3 / 5 | JSON and references are clean. API sequences and the capacity diagram lag behind the newer architecture detail. |

## What Works Well

- The central teaching thesis is crisp: stories are not permanent posts with a
  delete job; they are TTL-native content with read-time expiry guarantees.
- Capacity now has concrete numbers for story posts, fanout, tray opens, view
  events, live data, and fanout lag.
- The architecture now models the two important async paths: queued fanout and
  view-event aggregation.
- Step 5 states the right correctness boundary: server-assigned `expiresAt`,
  filter-on-read, and media URL/CDN authorization capped to story expiry.
- Step 6 is much stronger: the view service marks seen idempotently and emits
  events, while aggregation runs off the hot path and dedups by
  `(viewer_id, story_id)`.
- Step 7 now teaches bounded async fanout, rebuildable derived state, and the
  operating signals that prove the system is healthy.
- `technologyChoices` is practical and tied to the relevant steps.
- Cross-links for `satisfies[*].steps[*]`, pattern steps, technology-choice
  steps, highlights, and structured view nodes/links resolve cleanly.

## Highest-Impact Issues

### 1. Audience policy is a requirement, but it is not yet a modeled contract

The requirements now include followers vs. close friends plus blocks and
hidden-from checks. Step 3 says audience checks happen at fanout time and
`satisfies` says they are rechecked at read time. That is the right direction,
but the dataset does not yet show enough state or flow to make it credible.

Concrete missing pieces:

- `stories` has no `audience`, `visibility`, `audience_policy_id`, or
  `audience_snapshot_version` field.
- The `Graph` node is used for follower lookup, but there is no explicit
  relationship/audience-policy check on tray reads, view recording, or viewer
  list reads.
- Relationship mutations during the 24h window are not specified: unfollow,
  block, close-friends removal, and hidden-from edits can invalidate already
  fanned-out tray entries.
- The author-facing viewer-list endpoint needs to prove the caller owns the
  story or has permission to see the viewer list.

Recommended fix: add a small audience policy paragraph, add the relevant fields
to `stories`, and update tray/read/view sequences to show a fanout-time
eligibility check plus a read-time revalidation for relationship changes. Keep
the scope basic; the point is to make the promised policy mechanically visible.

### 2. API sequences still lag behind the newer architecture

The step flows are current, but the API-level sequences look like the earlier
version of the design:

- `POST /v1/stories` sends directly from `PostSvc` to `Fanout`, while the
  architecture and Step 3 now correctly use `FanoutQueue`.
- `GET /v1/tray` goes directly from `Client` to `TrayCache`, which hides the
  server-side tray-read path that must authenticate, filter expiry, apply
  seen-state, merge celebrity-pull stories, and recheck audience.
- `POST /v1/stories/{id}/view` has a good `ViewSvc` sequence, but it does not
  show how visibility/expiry checks read the story or graph state.
- `GET /v1/stories/{id}/viewers` has no structured sequence even though the
  viewer-list path is now a first-class part of the design.

Recommended fix: refresh the API sequences so they match the final diagram.
Use `FanoutQueue` in the create flow, route tray reads through a service/gateway
instead of the cache directly, and add a short viewers-read sequence through a
service that checks author authorization before reading `ViewerStore`.

### 3. Seen-state ownership is split between two stories

Step 4 and the high-level link `client-seen` imply the client marks/reads
`SeenStore` directly. Step 6 says the `ViewSvc` marks seen idempotently, which
is the better production boundary because it can authenticate, check expiry and
visibility, and own retry semantics.

Recommended fix: choose one ownership model and use it consistently. Prefer
`Client -> LB/ViewSvc -> SeenStore` for writes. For tray reads, prefer a tray
read service or gateway route that reads `TrayCache` and `SeenStore`; the cache
should not appear as a client-addressable API surface unless the text says it is
just diagram shorthand.

### 4. Capacity has useful top-line numbers but not enough derived-state sizing

The current capacity section is a major improvement. It just stops before the
numbers that would justify some of the final design's partitioning choices:

- Tray-entry volume and memory: `stories/day * average fanout`, after excluding
  celebrity pull.
- Seen-state volume: unique `(viewer, story)` entries over the 24h window and
  expected bytes per entry.
- View-event stream throughput and retention: events/sec, bytes/sec, partitions,
  and replay window.
- Viewer-store size: ordinary exact lists vs. celebrity capped lists/HLL.
- Media bandwidth: uploaded media, transcoded renditions, CDN egress, and cache
  hit assumptions.
- Rebuild load: bounded rate for tray rebuilds after cache loss.

Recommended fix: add a short derived table after the current capacity bullets.
It does not need perfect arithmetic; it needs enough estimates to explain why
these stores are sharded by viewer/story, why celebrity paths switch to pull or
sketches, and why rebuilds need throttling.

### 5. Media safety and takedown are mentioned but not represented

Step 2 now mentions pre-signed upload, transcoding, thumbnailing, and safety
scan, which is good. The architecture still treats media as a simple
`PostSvc -> MediaStore -> CDN` path. For a story system, moderation and takedown
matter because a story may need to disappear before TTL expiry.

Recommended fix: keep this lightweight. Add one explicit note or optional node
for media processing/safety, and add one trap or failure drill for "story is
reported or policy-blocked before expiry." This would complement the existing
expired-media drill without turning the interview into a moderation system.

## System Design Soundness

The core design is sound. The strongest choices are TTL-native story/media
storage, hybrid fanout to precomputed trays, per-viewer seen-state, read-time
expiry filtering, capped media URL validity, async view aggregation, and
rebuildable derived stores. These are the right primitives for a read-heavy,
short-lived content product.

The design is also honest about approximate cleanup: TTL purge, object lifecycle
rules, and reapers are cleanup mechanisms, while the read path and media
authorization are the user-visible guarantee. That is an important production
distinction and a strong teaching point.

The weakest area is now policy correctness rather than scale mechanics. If
audience policy remains in scope, it needs a small but concrete contract:
where the story's audience is stored, when the follower/close-friends/block
state is evaluated, and how relationship changes invalidate or suppress already
fanned-out tray entries. Without that, the design can still leak a story to a
viewer who was eligible at fanout time but no longer eligible at read time.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Normal Posts + Nightly Delete + Assemble-on-Read

This remains an effective baseline. It exposes stale visibility, expensive
scan-delete, read fan-in, and unbounded storage without overcomplicating the
opening move. The trap is concrete and useful.

Potential improvement: the requirements/capacity overview diagrams are very
simple, so this first step does more explanatory work than the visuals. That is
fine for now, but a richer capacity visual would help anchor the scale pressure
before the naive design appears.

### Step 2: Ephemeral by Design: TTL Everywhere

This is the conceptual anchor and it is now much more production-aware. The text
correctly separates TTL purge from the user-facing expiry guarantee and includes
the upload/transcode/lifecycle note.

Potential improvement: if media processing remains textual only, say explicitly
that it is outside the main diagram. Otherwise candidates may wonder why safety
scan and transcoding are introduced but never appear again.

### Step 3: Fanout to Story Trays

This is one of the strongest steps. The current version includes async fanout,
queue lag budget, idempotent tray writes, hybrid celebrity pull, and audience
checks at fanout time. The flow diagram now shows `FanoutQueue`, which fixes the
old conceptual gap.

The main remaining gap is audience precision. If fanout filters close-friends
and blocks, the story must carry an audience policy and the graph lookup must be
clear about what relationship state it returns.

### Step 4: Per-Viewer Seen-State

The insight is excellent: seen-state is a huge relationship, but ephemerality
bounds it. The per-viewer set is the right default and the alternatives teach
useful trade-offs.

The implementation boundary should be tightened. The step currently reads like
the client writes directly to `SeenStore`; later the view service owns the
idempotent mark-seen write. Prefer the latter and adjust the diagram/caption so
seen-state is a service-owned store, not a direct client dependency.

### Step 5: Reliable Expiry (Never Show a Stale Story)

This step is now strong. It clearly states that read-time filtering and bounded
media authorization enforce the promise, while TTL purge and the reaper are
cleanup. The CDN stale-media failure drill in Step 7 reinforces this nicely.

Potential improvement: show the read path through a service/gateway in the
sequence. The current flow's `Client -> TrayCache` shape can imply cache-level
authorization, even though the prose says the server is the correctness
boundary.

### Step 6: View Counts and Viewer Lists

This step is much improved. The `ViewSvc -> ViewLog -> ViewAggregator ->
ViewerStore` path is the right architecture, and the dataset now explains
idempotency, at-least-once delivery, capped/paginated lists, and HLL for
celebrity-scale counts.

Potential improvement: add the `GET /v1/stories/{id}/viewers` sequence so the
author-facing read side is as explicit as the write side. Also state whether
viewer-list ordering is by first view, latest view, or approximate recency.

### Step 7: Scaling and Cleanup at Volume

The step now has real operational content: queue lag, CDN, bounded live data,
rebuildable derived state, throttled rebuilds, and observability. The three
failure drills are concrete and relevant.

It is still closer to a wrap-up than a decision step. That can be acceptable,
but if the book wants every step to contain an interview decision, add one
trade-off prompt such as "How do we choose the celebrity pull threshold?",
"How stale may trays be during queue lag?", or "What do we serve during tray
cache rebuild?"

## Final Design Review

The final design now integrates the major components introduced in the steps:
`FanoutQueue`, `Fanout`, `TrayCache`, `SeenStore`, `ViewSvc`, `ViewLog`,
`ViewAggregator`, `ViewerStore`, `Reaper`, `CDN`, `MediaStore`, and `Obs` all
appear in the final diagram. This is a meaningful improvement over the prior
reviewed state.

The final description is concise and accurate. It covers server-assigned
expiry, queued fanout, hybrid celebrity pull, idempotent view tracking, HLL for
celebrity counts, bounded live data, rebuildable derived state, and operating
signals.

The remaining coherence issues are service boundaries:

- `client-seen` suggests direct client access to `SeenStore`, while the text
  says `ViewSvc` owns idempotent mark-seen.
- `lb-viewerstore` reads `ViewerStore` directly; a service should check author
  authorization and story ownership before returning viewer lists.
- `lb-tray` goes directly to `TrayCache`; the read path needs a clear place for
  expiry filtering, seen-state lookup, celebrity merge, and audience
  revalidation.

These are small diagram/API-boundary edits, not a redesign.

## Concept Introduction and Learning Flow

The concept staging is excellent:

- TTL-native storage in Step 2.
- Tray fanout and hybrid push/pull in Step 3.
- Ephemeral seen-state in Step 4.
- Filter-on-read plus TTL purge in Step 5.
- Async view counting in Step 6.
- Bounded async fanout and rebuildable derived state in Step 7.

The concepts now line up with the dataset-level `patterns` and the
`technologyChoices` section, which makes the case more reusable as a book
chapter. The only concept that needs firmer placement is audience policy:
introduce it either as part of the fanout concept or as a lightweight
cross-cutting correctness note before the fanout/read/view flows.

## Step-to-Final-Design Coherence

Most steps now map cleanly into the final design:

- `ttl` maps to `StoryDB`, `MediaStore`, TTL/lifecycle choices, and expiry
  wording.
- `fanout` maps to `FanoutQueue`, `Fanout`, `Graph`, and `TrayCache`.
- `seen` maps to `SeenStore`, though the owner service should be clarified.
- `expiry` maps to read-time filtering, media authorization, and `Reaper`.
- `views` maps to `ViewSvc`, `ViewLog`, `ViewAggregator`, and `ViewerStore`.
- `scale` maps to CDN, queue lag, rebuildable state, and `Obs`.

The main step-to-final gaps are not missing components anymore. They are missing
edges and contracts around who is allowed to call those components and where
policy checks happen.

## Realism Compared With Production Systems

Compared with a production stories system, the dataset is now realistic enough
for an interview and suitably scoped for a book case. It includes the critical
topics candidates should discuss: fanout spikes, TTL lag, idempotency, dedup,
CDN expiry, exact vs. approximate counts, derived-state rebuilds, and
observability.

The remaining realism gaps are worth stating or scoping:

- Privacy and audience mutation during the live window.
- Author authorization for viewer-list reads.
- Media moderation, takedown before TTL, and safety scan failure.
- Per-tenant or per-user abuse controls on posting/view-event spam.
- Regional replication and data residency, if the product scope grows.
- Backups/logs/analytics retention language for "ephemeral" content.

Not all of these need diagram nodes. The first three are close enough to the
current design that they should be either lightly modeled or explicitly scoped
out.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Current shape: 7 steps, 4 APIs, 5 data-model entries, 17 high-level nodes,
  21 high-level links, 6 functional requirements, 5 non-functional
  requirements, 5 technology-choice concerns, and 5 follow-ups.
- Structured `view.nodes` and `view.links` references resolve against
  `highLevelArchitecture`.
- Highlight IDs resolve against high-level nodes.
- `satisfies[*].steps[*]`, pattern `steps`, and technology-choice `steps`
  resolve to known step IDs.
- Canonical node types are valid for the current node set.
- `GET /v1/stories/{id}/viewers` is the only API without a structured sequence.
- `POST /v1/stories` has a sequence, but it should use `FanoutQueue` rather
  than direct `PostSvc -> Fanout`.
- `GET /v1/tray` and the Step 5 tray-read flow show `Client -> TrayCache`
  directly. If that is shorthand, add a note or a service participant so the
  renderer does not teach direct cache access.
- The raw `capacityDiagram` is valid but too simple relative to the improved
  capacity section. Consider showing posts, fanout writes, tray reads, view
  events, and bounded 24h state.
- No docs rebuild is needed for this review file alone.

## Recommended Edits, Prioritized

### P1: Align the flows with the current architecture

- Update `POST /v1/stories` to enqueue `FanoutQueue`.
- Add a `GET /v1/stories/{id}/viewers` sequence.
- Route tray reads and seen writes through explicit service/gateway boundaries.
- Remove or reframe direct `Client -> SeenStore` and `Client -> TrayCache`
  paths.

### P1: Make audience policy mechanically visible

- Add `audience` / `audience_policy_id` / `audience_snapshot_version` fields to
  `stories`, or state a simpler equivalent.
- Show fanout-time eligibility lookup and read-time revalidation.
- Mention unfollow/block/close-friends removal during the 24h window.
- Check author ownership before serving viewer lists.

### P2: Add derived capacity numbers

- Estimate tray-entry writes and memory.
- Estimate seen-state and viewer-store live entries.
- Estimate view stream bytes/sec and partitioning pressure.
- Estimate media egress and rendition/storage multiplier.
- Add a rebuild-rate budget for cache loss.

### P2: Cover media safety and pre-expiry takedown lightly

- Add one short media-processing/safety node or explicit non-goal.
- Add a failure drill for story report/takedown before TTL expiry.
- Clarify what happens to tray entries, media URLs, viewer lists, and cached
  tray responses after takedown.

### P3: Polish the learning surface

- Make Step 7 a decision step if consistent with the rest of the book cases.
- Upgrade the capacity diagram to match the now-numeric capacity section.
- Add viewer-list ordering semantics.
- Update level variants to mention audience correctness for staff-level answers.

## What Not To Change

- Keep TTL-native storage as the conceptual center.
- Keep the naive baseline; it motivates the whole case.
- Keep hybrid fanout as the default tray strategy.
- Keep per-viewer seen-state as the main seen UX model.
- Keep filter-on-read over TTL purge as the expiry correctness answer.
- Keep async view aggregation and dedup by `(viewer_id, story_id)`.
- Keep Step 7's operational drills; they are now one of the stronger parts of
  the dataset.

## Bottom Line

The dataset has moved from "good with production gaps" to "strong, with a few
boundary and policy details left." The next useful pass should not redesign the
case. It should align the API sequences with the current architecture, make
audience policy concrete, and add just enough derived sizing to justify the
partitioning and cache/stream choices.
