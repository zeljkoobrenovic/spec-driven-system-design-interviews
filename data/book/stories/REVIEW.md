# Review: Stories (Ephemeral Content) System Design

Reviewed file: `data/book/stories/interview.json`
Review date: 2026-06-05

> **Resolution (2026-06-05):** The production pass below was applied.
> Added concrete capacity work-units; modeled `FanoutQueue` (bounded async
> fanout, idempotent tray writes), and the `ViewSvc → ViewLog → ViewAggregator
> → ViewerStore` path with `(viewer, story)` dedup; added `Obs` observability;
> tightened the expiry guarantee around server-assigned `expiresAt`, read-time
> filtering, and capped media-URL/CDN TTL (reaper demoted to a backstop in
> wording and diagrams); scoped a basic audience policy (followers /
> close-friends, blocks) checked at fanout vs. read time; added data-model
> entries (`view_events`, `story_viewers`), a `/view` API sequence and a
> `/viewers` endpoint, a `technologyChoices` section, new traps and Step 7
> operational failure drills, and a media upload/transcode/CDN-lifecycle note.
> Fixed all no-op diagram links. The original review text is preserved below.

## Executive Summary

This is a strong, compact interview case with a clear central thesis: stories are
not normal posts with a delete job bolted on; they are TTL-native content with
precomputed trays, per-viewer seen-state, read-time expiry filtering, and
bounded derived state. The step order works well and the options teach real
trade-offs instead of strawmen.

The main gaps are not in the core idea. They are in production grounding. The
capacity section is qualitative, the view-count/viewer-list path is described
more fully than it is modeled, fanout backpressure is mentioned but not drawn,
visibility/privacy is only a follow-up despite affecting the tray design, and a
few diagram links are currently filtered out by the renderer because their
endpoints are not included in the view.

| Dimension | Rating | Notes |
|---|---:|---|
| System design soundness | 4.0 / 5 | Core TTL, tray fanout, seen-state, and filter-on-read story are sound. Needs stronger capacity math, queueing, view aggregation, and visibility semantics. |
| Production realism | 3.6 / 5 | Good instincts on TTL and celebrity fanout, but thin on media processing, privacy, view dedup, operational metrics, and CDN/object-store expiry caveats. |
| Pedagogical flow | 4.3 / 5 | The naive baseline motivates each next step cleanly. Step 7 is more summary than decision exercise. |
| Final design coherence | 3.9 / 5 | Final design integrates the visible steps, but claims an async viewer-list aggregator and queued fanout without corresponding components/state. |
| Dataset/rendering fit | 4.1 / 5 | JSON and references are mostly clean. A few view links are no-ops, and one API lacks a structured sequence. |

Recommendation: keep the step order and the TTL-centered narrative. Tighten the
case by adding concrete scale numbers, explicit fanout/view aggregation
components, privacy scope, and small renderer fixes.

## What Works Well

- The problem framing is crisp: 24h ephemerality is both a product requirement
  and a scaling advantage.
- The naive baseline is useful because it exposes exactly why scan-delete and
  assemble-on-read fail.
- Steps 2 through 6 introduce one major mechanism at a time: TTL, fanout,
  seen-state, expiry correctness, and async view tracking.
- The option sets are practical. Hybrid fanout, per-viewer seen sets,
  filter-on-read over TTL purge, and async view aggregation are good default
  choices.
- The dataset uses project features well: patterns, concepts, traps, recaps,
  decision prompts, `satisfies`, interview script, level variants, and
  follow-ups are all present.
- `probeLinks`, `satisfies[*].steps[*]`, step patterns, and primary
  high-level architecture references resolve cleanly.

## Highest-Impact Issues

### 1. Capacity is qualitative, so the design never proves its scale choices

The capacity section says "hundreds of millions", "views >> posts", and
"viewer x story", but it does not convert those into work units. That weakens
the case because fanout, seen-state, view events, CDN traffic, and expiry cost
are the core design pressures.

Add one concrete scenario, even if rough:

- Stories/day and average/peak story posts per second.
- Average follower fanout and celebrity fanout outliers.
- Tray opens per second and media views per second.
- View events per second, including celebrity spikes.
- Live story metadata size, tray entry count, seen-state size, and media
  bandwidth over the 24h live window.
- Queue backlog tolerance: how long a normal fanout may lag before the tray UX
  becomes unacceptable.

This does not need perfect math. It needs enough numbers to justify why tray
reads are cached, why celebrity pull exists, why view events need async
aggregation, and why TTL bounds storage.

### 2. Visibility and relationship semantics are scoped too late

The follow-ups ask about close friends and hidden-from lists, but visibility is
not just an extension. It changes who gets fanned out, what can be rebuilt, and
what must be rechecked at read time.

Important cases:

- Private accounts and follower approval.
- Close-friends audiences.
- Blocked users, muted authors, hidden-from lists, and "do not show my stories
  to this viewer" settings.
- Relationship changes after fanout, such as unfollow, block, or removal from
  close friends while a story is still live.

If this case intentionally excludes audience controls, say that explicitly in
requirements or non-goals. If it includes them, add fields such as
`visibility`, `audience_policy_id`, or `audience_snapshot_version`, and explain
which checks happen at fanout time versus tray-read time.

### 3. View tracking is described but not fully modeled

Step 6 says view events feed an async aggregator that builds per-story viewer
lists and counts. The final design repeats that claim. But the architecture only
has `ViewLog` and `SeenStore`; there is no `ViewAggregator`, no viewer-list
store, and no data model entry for view events, per-story viewer lists, count
sketches, or pagination/capping.

The API also leaves this path thinner than the other APIs:

- `POST /v1/stories/{id}/view` has no structured `sequence`.
- The high-level diagram has `Client -> ViewLog` directly, bypassing the API
  gateway and any service that would authenticate, dedupe, check expiry, and
  validate visibility.
- The default option says the stream also drives seen-state, but Step 4 also
  has `Client -> SeenStore` directly. The design should choose whether the view
  API synchronously marks seen, emits an event for async marking, or does both
  with idempotency.

Concrete fix: add a `ViewSvc` or route through `LB`, a `ViewAggregator`, and a
`ViewerListStore`/`ViewCountStore` with TTL. Model idempotency by
`(viewer_id, story_id)` so duplicate client view events do not inflate unique
viewer lists.

### 4. Fanout queueing and backpressure are mentioned but not part of the design

Step 7 says fanout bursts buffer in a queue with scalable workers, but the
high-level architecture has only a `Fanout` worker and no queue node. That makes
the final design understate one of the highest-risk operational paths.

For a story system, the important fanout questions are:

- Does `POST /v1/stories` return after durable story write or after fanout
  completes?
- What happens while a large normal-author fanout is still in progress?
- How are tray writes retried and deduplicated?
- What metrics drive the celebrity threshold?
- How is queue lag surfaced to the product, for example delayed appearance in
  some followers' trays?

Add a `FanoutQueue` node, idempotent tray write semantics, and one failure drill
for fanout lag. That will make the hybrid fanout option feel operational rather
than just conceptual.

### 5. The expiry guarantee should be tied to read authorization, not cleanup

The dataset correctly says TTL purge is approximate and read-time filtering is
the guarantee. Some wording and diagrams still overcredit the reaper, for
example the Step 5 caption says the reaper drops ids "so stale stories never
appear." A reaper is cleanup; it cannot be the correctness boundary.

The correctness rule should be stated precisely:

- `expiresAt` is assigned by the server at create time.
- Tray entries carry the authoritative server `expiresAt`.
- Tray reads filter expired entries before returning them.
- Media fetch uses signed URLs or CDN authorization whose validity is bounded
  by the story expiry.
- Object-store lifecycle and database TTL may lag without violating user-facing
  expiry.

Also clarify backup/log retention. Product ephemerality usually means "not
shown after expiry", not necessarily instant physical erasure from every
replica, CDN cache, backup, and analytics log.

## System Design Soundness

The core architecture is sound for a 45-minute interview. The strongest
decisions are TTL-native stores, tray fanout for read-heavy access, hybrid
celebrity pull, per-viewer seen-state, and filter-on-read as the hard expiry
guard.

The main missing system-design depth is the lack of explicit work-unit math and
state shapes for the two most explosive relationships: follower fanout and
viewer events. The data model has `stories`, `story_tray`, and `seen_state`, but
not the structures implied by Step 6 and Step 7: fanout jobs, view events,
viewer lists/counts, count sketches, or queue lag state.

The API is intentionally small, which is fine, but it should include the fields
that later architecture depends on: idempotency keys for posts/views, upload
session or media reference rather than inline media, server-assigned TTL policy,
pagination for trays and viewer lists, and visibility/audience policy if that is
in scope.

## Step-by-Step Pedagogical Review

### Step 1: Naive: Normal Posts + Nightly Delete + Assemble-on-Read

This is a good baseline. It exposes the two core failures: expensive delete
scans and slow assemble-on-read tray reads. Keep it.

The recap says `before: Nothing`, which is acceptable for the first step. A
small improvement would be to name the three debts more explicitly in the step
summary: stale visibility, read fan-in cost, and unbounded storage.

### Step 2: Ephemeral by Design: TTL Everywhere

This step is the conceptual anchor and works well. The trade-off set is strong:
TTL-native, scheduled sweep, and lazy delete-on-read.

Add one caveat: TTL purge is not precise physical deletion. The product
guarantee comes later from read filtering and media access control. This will
make Step 5 feel like a necessary correctness layer rather than a repeat of
Step 2.

### Step 3: Fanout to Story Trays

This is the best step pedagogically. The celebrity fanout prompt is concrete and
the three options teach the feed trade-off well.

The production gap is queueing. The step should name whether fanout is async
after post acceptance, how fanout lag affects tray freshness, and how tray
writes are idempotent. If visibility controls are in scope, this is also where
the dataset should introduce audience selection or explicitly defer it.

### Step 4: Per-Viewer Seen-State

The per-viewer seen set is a good default, and the alternatives are useful. The
step correctly uses ephemerality to bound an otherwise large relationship.

The main improvement is to connect this to the view API. Right now the
architecture has `Client -> SeenStore` while Step 6 also says view events drive
seen-state. Decide whether the mark-seen operation is synchronous, event-driven,
or a synchronous write plus async aggregation.

### Step 5: Reliable Expiry (Never Show a Stale Story)

The main idea is correct: read-time filtering is the hard guarantee; TTL purge
is cleanup. This is a high-value teaching point.

Tighten wording so the reaper is always described as a backstop. Add media
access details because otherwise a stale story might be hidden from the tray but
still fetchable through an old CDN URL.

### Step 6: View Counts and Viewer Lists

This is currently the biggest coherence gap. The prose describes a stream and
aggregator, but the diagram and data model stop at `ViewLog -> SeenStore`.

Add the missing aggregator/store components and a data model entry. Include
dedup semantics and pagination/capping for viewer lists. For counts, state when
the system needs exact unique viewers versus approximate celebrity-scale
estimates.

### Step 7: Scaling and Cleanup at Volume

This is a good closing theme, but it is more summary than decision step. It has
no options, concepts, or traps, and only one failure drill.

Add one or two concrete operational drills:

- Fanout queue lag spikes after a popular author posts.
- Tray cache rebuild causes read amplification against the story store.
- CDN serves a media object after story expiry unless signed URL TTL is capped.

This would turn the scale step into an interview-quality deep dive instead of a
wrap-up paragraph.

## Final Design Review

The final design description is coherent with the main step narrative. It
correctly states TTL-native media and records, hybrid fanout, tray TTL entries,
per-viewer seen-state, read-time expiry filtering, async view events, sharding,
and rebuildable derived state.

The mismatch is that several final-design claims are not represented as nodes or
state:

- Async viewer-list aggregation has no aggregator or viewer-list store.
- Fanout queueing/backpressure has no queue.
- Visibility and relationship checks are absent.
- Media processing, CDN signed URL expiry, and moderation/safety checks are
  absent.
- Observability is not represented, even though queue lag, TTL lag, view lag,
  and stale-filter drops are essential operating signals.

Do not rewrite the final design. Add the missing few components and keep the
diagram focused.

## Concept Introduction and Learning Flow

The learning flow is strong. Concepts are introduced close to the point where
they matter:

- TTL-native storage in Step 2.
- Tray fanout in Step 3.
- Ephemeral seen-state in Step 4.
- Filter-on-read plus TTL purge in Step 5.
- Async view tracking in Step 6.

The missing concept is operational backpressure. Since Step 7 already mentions
queued fanout and rebuildable trays, add a concept such as "bounded async fanout"
or "derived-state rebuild" to make that final step teach something concrete.

## Step-to-Final-Design Coherence

Most steps map cleanly into the final design:

- `ttl` maps to `MediaStore` and `StoryDB`.
- `fanout` maps to `Fanout`, `Graph`, and `TrayCache`.
- `seen` maps to `SeenStore`.
- `expiry` maps to read filtering plus `Reaper`.
- `views` maps only partially to `ViewLog`.
- `scale` maps partially to sharding/CDN/rebuildable state, but not to a queue
  or operational controls.

The biggest step-to-final gap is Step 6. If the final design promises viewer
lists and counts, the architecture and data model should show where they live.

## Realism Compared With Production Systems

A production story system would need several details that are currently absent
or only implicit:

- Upload flow: pre-signed media upload, media processing/transcoding,
  thumbnails, safety scanning, and object lifecycle rules.
- Privacy: close friends, blocks, hidden-from lists, private accounts, and
  relationship changes during the 24h window.
- Event dedup: retries from mobile clients and at-least-once stream processing
  should not double-count unique views.
- Cache rebuild limits: a lost tray cache should not trigger unbounded fan-in
  queries for every viewer at once.
- Observability: fanout queue lag, tray read p99, stale-filter drops, TTL purge
  lag, CDN 404/expired-media rates, view aggregation lag, and hot-key metrics.
- Abuse and safety: story reporting, takedowns before TTL expiry, account
  enforcement, and media scan failures.

These do not all need full steps. A few can be scoped out. The ones tied to the
current architecture - visibility, queueing, view aggregation, expiry/media
access - should be included.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- The dataset has 7 steps, 3 APIs, 3 data model entries, 6 patterns, 5
  functional requirements, and 5 non-functional requirements.
- `satisfies[*].steps[*]`, `probeLinks`, and `step.patterns` resolve to known
  ids.
- String `view.nodes` and `view.links` references resolve to
  `highLevelArchitecture`.
- `POST /v1/stories/{id}/view` is the only API without a structured sequence.
  Add one because this path is central to seen-state and viewer-list counting.
- Some authored view links are currently no-ops because `graphViewToMermaid`
  renders only links whose endpoints are both present in `view.nodes`:
  - Step `fanout` includes `lb-tray`, but `LB` is not in that view.
  - Step `scale` includes `post-storydb`, but `PostSvc` is not in that view.
  - Step `scale` includes `client-cdn`, but `Client` is not in that view.
  - Step `scale` includes `cdn-media`, but `MediaStore` is not in that view.
- The high-level links `client-seen` and `client-viewlog` bypass `LB`. If this
  is only diagram shorthand, it is acceptable; if not, route these through an
  API/service so auth, expiry, visibility, and dedup are explicit.
- `technologyChoices` is absent. It is optional, but this book dataset would
  benefit from a short section covering TTL stores, cache/tray storage,
  streams, object storage/CDN, and counters/sketches.

No docs rebuild is needed for this review file alone.

## Recommended Edits, Prioritized

### P1: Make the design defensible at scale

- Add concrete capacity numbers and derived work units.
- Add `FanoutQueue` plus retry/idempotent tray-write semantics.
- Add `ViewSvc`, `ViewAggregator`, and viewer-list/count state.
- Tighten the expiry guarantee around server `expiresAt`, read filtering, and
  media URL/CDN validity.

### P2: Close production-realism gaps

- Either scope out visibility/privacy explicitly or add audience policy fields
  and fanout/read-time checks.
- Add a view API sequence.
- Add data model entries for view events and viewer lists/counts.
- Add operational metrics and failure drills for fanout lag, tray rebuild, and
  view aggregation lag.
- Fix the no-op diagram links by adding the missing endpoint nodes or removing
  the unused links from those views.

### P3: Polish the book-specific learning surface

- Add a small `technologyChoices` section.
- Add traps for "TTL equals exact deletion", "client clock decides expiry", and
  "directly increment the story row for every view".
- Add one media-pipeline note for upload/transcode/CDN lifecycle.
- Consider one more external reading link specifically on object-store lifecycle
  or CDN signed URLs if external-link maintenance is in scope.

## What Not To Change

- Keep the naive-to-final step order.
- Keep TTL-native storage as the conceptual center of the case.
- Keep hybrid fanout as the default tray strategy.
- Keep per-viewer seen-state as the main seen UX model.
- Keep filter-on-read over TTL purge as the expiry correctness answer.

## Bottom Line

This is a good interview dataset with a strong teaching spine. It needs a
production pass, not a redesign: quantify the scale, model the missing async
fanout/view aggregation pieces, clarify privacy and media expiry semantics, and
fix the few renderer-facing no-op links.
