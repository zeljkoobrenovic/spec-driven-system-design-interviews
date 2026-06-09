# Review: Calendar Scheduling - System Design

Reviewed file: `data/book/calendar/interview.json`
Review date: 2026-06-08

## Executive Summary

The recent calendar revision materially improves the dataset. The earlier gaps
around capacity math, update/delete/RSVP/sync APIs, recurrence identity,
idempotency, reminder jobs, calendar ACLs, change-log driven derived state,
reminder/sync flows, cache invalidation, and probe-link grouping are now
addressed in the JSON. The interview is no longer just a strong conceptual
calendar walkthrough; it now has a credible production spine.

The remaining issues are narrower and mostly about making the new mechanics
precise. The design introduces a durable change log and projectors, but some
API/diagram flows still show direct side effects from `EventSvc` to invites and
reminders. The organizer-authoritative invite model also needs an explicit
attendee-calendar projection model so attendee reads, busy indexes, and delta
sync cursors work without scanning organizer-owned events. Capacity is much
more useful than before, but one event-count assumption is internally
inconsistent and the storage estimate is too broad to teach trade-offs.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.4 / 5 | Strong recurrence, timezone, free/busy, reminders, sync, and derived-state design; needs sharper attendee-calendar projection semantics. |
| Production realism | 4.1 / 5 | Much better idempotency, outbox, scheduler, ACL, and sync modeling; still needs clearer write-side effect boundaries and external-calendar caveats. |
| Pedagogical flow | 4.4 / 5 | The step progression is clean and now has richer reminder/sync material; Step 7 could use explicit trade-off options or a flow. |
| Final design coherence | 4.3 / 5 | Final design includes the improved components, but a few links/flows blur whether projectors or direct service calls own side effects. |
| Dataset/rendering fit | 4.8 / 5 | JSON parses; checked step/final links, `satisfies` references, and sequence participants resolve. Only small polish remains. |

Recommendation: keep the revised structure. The next pass should clarify the
change-log as the source of all derived work, add attendee-calendar projection
state, and tighten the capacity assumptions.

## What Works Well

- Capacity is now quantitative: users/events, read/write QPS, free/busy fanout,
  reminder bursts, storage, and latency targets are present.
- The API now covers the important mutation surfaces: create, update, delete,
  RSVP, free/busy, list, and cursor sync.
- The data model now includes `version`, `recurrence_id`, `calendar_acl`,
  `reminder_jobs`, `calendar_changes`, and `idempotency_keys`.
- The durable `ChangeLog` plus `Projector` components are the right conceptual
  center for busy-index maintenance, reminder materialization, invite fanout,
  sync cursors, and cache invalidation.
- Step 6 is much stronger than before: reminders have a due-index option,
  leasing, dedup, retry/backoff, cancellation/supersession, and delta sync with
  tombstones.
- Recurrence and timezone are still the teaching core. RRULE storage, windowed
  expansion, EXDATEs, stable recurrence ids, "this and following" as a series
  split, and explicit DST gap/overlap policy are all present.
- Probe links are now calendar-specific and grouped well: standards, time and
  recurrence, sync protocols, and notifications/streams.

## Highest-Impact Issues

### 1. The change-log pipeline is present, but side-effect ownership is still mixed

The final design says every event write commits an outbox row, and projectors
feed the busy index, reminder jobs, invite fanout, sync cursors, and cache. That
is the right design. But several flows and links still show direct side effects:
`POST /v1/events` persists an event and then calls `InviteSvc`; the final
diagram includes both `projector-reminder` and the older `event-reminder` link;
and the high-level architecture still contains direct `EventSvc -> InviteSvc`
and `EventSvc -> ReminderQ` paths.

Why it matters: the point of the outbox is to avoid "event write committed, but
invite/reminder/index/cache update was lost." If the walkthrough shows direct
post-commit side effects, candidates may miss the reliability boundary or treat
the projector path as optional.

Concrete fix: make the write transaction authoritative:

- `EventSvc` writes `events`/`attendees` plus `calendar_changes` in one
  transaction.
- Projectors consume `calendar_changes` to update `BusyIndex`, materialize
  `reminder_jobs`, emit invite/update notifications, and invalidate `Cache`.
- If a direct call remains in a sequence, label it as a synchronous validation
  or request path, not the durable side-effect path.
- Remove or relabel `event-reminder` in the final view so reminders are clearly
  sourced from the projector.

### 2. Organizer-authoritative invites need an attendee-calendar projection model

The default invite model uses one organizer-owned event row and attendee rows
for responses. That is a good default, but the dataset also promises attendee
calendar reads, attendee free/busy, and per-calendar delta sync. The current
model does not yet show the projection that makes those possible. `attendees`
has `event_id` and `user_id`, but no attendee calendar id, local event
reference, per-attendee reminder/visibility override, or per-attendee change
record.

Why it matters: a user's calendar view and sync cursor should not need to scan
every organizer-owned event in the system where that user appears as an
attendee. Free/busy for an attendee also needs to know whether the attendee's
copy blocks time, especially for declined, tentative, hidden, or private
events.

Concrete fix: add a small projection entity, for example
`calendar_event_refs` or `attendee_event_refs`:

- `calendar_id`, `event_id`, `organizer_calendar_id`, `attendee_user_id`,
  `response`, `blocks_time`, `local_reminder_overrides`, `visibility_override`,
  and `last_seen_event_version`.
- Organizer edits project changes into each affected attendee calendar's
  change log so `GET /v1/sync?calendarId=...` returns the update for attendees,
  not only for the organizer calendar.
- Busy-index projectors update each attendee calendar's busy intervals according
  to RSVP and visibility policy.

### 3. The capacity numbers are useful but internally inconsistent

The capacity section says `~500M users`, `~3 calendars/user`, and `~50 active
events/calendar`, which implies roughly 75B active event references before
attendees are counted. The headline says `~10B events`. That can be reconciled,
but the dataset should say whether `10B` means canonical event series, retained
event rows, active visible calendar entries, or organizer-owned events only.

Why it matters: calendar storage and fanout are sensitive to the difference
between canonical organizer events, attendee projections, recurring rules,
expanded instances, change-log records, busy intervals, and reminder jobs. The
new architecture makes those distinctions important.

Concrete fix:

- Separate `canonical_events`, `calendar_event_refs`, and `expanded_instances`
  in the capacity math.
- Give one attendee fanout assumption, such as average attendees per meeting
  and percentage of solo events.
- Replace `~tens of TB` with a rough row-size calculation for event rows,
  attendee refs, change-log retention, busy intervals, and reminder jobs.
- State retention windows for `calendar_changes`, tombstones, and reminder-job
  history.

### 4. Privacy is modeled, but the API and flows should enforce it

The data model now has `calendar_acl`, and the requirements call out free/busy
privacy. The free/busy API, however, still reads as
`?attendees=u1,u2,u3&from=...&to=...` without showing caller identity,
calendar/principal authorization, or how `private`, `busy`, `public`, and
`freebusy_only` affect the response.

Why it matters: free/busy is one of the main privacy surfaces in a calendar
system. The same event may be fully visible to the owner, busy-only to a
colleague, and invisible to an external user. The design should teach that the
busy index is privacy-preserving only when ACL checks happen before returning
intervals.

Concrete fix: add a short API/flow note:

- `FreeBusy` authorizes the caller against `calendar_acl` before returning
  intervals.
- Response shape distinguishes "busy interval", "unknown/no permission", and
  optional event details when the caller has reader rights.
- Private events contribute busy blocks but do not expose title/location.

## System Design Soundness

### Requirements and Capacity

The requirements are now well scoped: event CRUD, recurrence, availability,
invites/RSVPs, reminders, device sync, DST correctness, retry safety, privacy,
and reliable derived work. The non-functional section is stronger because it
explicitly names at-least-once delivery, versioned edits, idempotent mutations,
and ACL-bound free/busy.

Capacity is the biggest remaining soundness gap. The numbers are directionally
helpful, especially the reminder burst ratio and free/busy attendee fanout, but
the event totals should be made internally consistent. Once attendee projections
are added, capacity should distinguish canonical event rows from per-calendar
event references; otherwise the sharding and storage story is hard to evaluate.

### API

The API surface now supports the main workflows. `PATCH`/`DELETE` include
recurrence scope and `expectedVersion`; RSVP is idempotent and version-stamped;
sync uses a cursor and tombstones; create includes calendar id, organizer,
duration, visibility, attendees, reminders, and idempotency.

Two API improvements would make the case more production-ready:

- Clarify that write APIs commit only authoritative state plus an outbox/change
  record; invite/reminder/cache/index side effects are projector work.
- Add caller/auth context to free/busy and sync examples so privacy and ACLs are
  not only data-model concepts.

### Data Model

The model is much better than the prior version. `events` captures local start,
TZID, duration, RRULE, EXDATEs, visibility, and version. `event_overrides`
uses a stable recurrence id. `reminder_jobs`, `calendar_changes`, and
`idempotency_keys` support the async reliability story.

The main missing state is attendee-calendar projection. `attendees` tracks
responses, but it does not give an attendee calendar a local reference for
listing, busy indexing, reminder overrides, sync changes, or visibility
behavior. Add that as a small focused entity rather than expanding the main
`events` table.

For recurrence, the "this and following" series-split model is mentioned in
prose and traps. If this is meant to be teachable from the schema, add one
field-level note that the old series gets an `UNTIL`/bounded rule and the new
series is a new `events` row linked by `split_from_event_id` or equivalent.

### Architecture

The architecture now has the right components: Event Service, Event Store,
Recurrence Expander, Free/Busy, Busy Index, Invite/RSVP, Notification,
Reminder Scheduler, Sync Service, Read Cache, Change Log, and Projectors.

The strongest design move is treating busy intervals, reminder jobs, sync
cursors, and caches as derived/rebuildable state. To make that fully coherent,
the diagrams and flows should consistently route durable side effects through
`ChangeLog -> Projector`. Direct calls can still exist for synchronous reads or
validation, but not for side effects that must survive failures.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Row per Occurrence, Local-String Times

Still a strong baseline. It exposes infinite recurrence, bulk rewrite pain, and
timezone/DST corruption quickly. No major change needed.

### Step 2: Recurring Events: Store the Rule, Expand on Read

This remains one of the best sections. The default, materialize-all, and bounded
cache options teach the real trade-off space. The updated trap about stable
recurrence ids and series splitting is valuable.

Improvement: add a tiny schema note for how a "this and following" split is
represented as two bounded/linked series.

### Step 3: Timezones and DST Correctness

The section correctly anchors recurring events in local wall-clock time plus
IANA TZID. The new nonexistent/ambiguous local-time policy is a good interview
detail.

Improvement: mention the operational policy for tzdb updates: whether future
instances are recomputed lazily at read time, reindexed by a background job, or
both.

### Step 4: Free/Busy Availability

This step is now strong because it includes both the query path and the
busy-index update path through the change log/projector. The staleness note is
appropriately honest.

Improvement: connect the busy index to attendee projection and ACLs. The index
needs to know which attendee calendar blocks time and what the caller is
allowed to see.

### Step 5: Invites and RSVPs

The organizer-authoritative default and per-attendee-copy alternative are the
right contrast. The idempotent, version-stamped RSVP flow and race-condition
trap address an important previous gap.

Improvement: show how organizer event updates become attendee calendar changes
for reads, sync, and busy indexing. Without that projection, the default model
is conceptually right but operationally incomplete.

### Step 6: Reminders and Device Sync

This step improved the most. It now has real options, due-reminder execution,
lease/validate/send/mark semantics, dedup keys, retry/backoff, delta sync,
tombstones, and cursor-retention behavior.

Improvement: add two or three fields to `reminder_jobs`, such as `lease_until`,
`attempt_count`, `channel`, and `recipient_id`, or mention them in the note.
That would make the state machine more concrete without bloating the schema.

### Step 7: Scaling and Consistency

The scaling step now ties back to the capacity numbers, reminder bursts,
sharding, projector lag, cache invalidation, and DR drills. It is much stronger
than before.

Improvement: give Step 7 one explicit trade-off comparison or flow. Good
choices would be calendar-sharded vs user-sharded vs hybrid, or transactional
outbox/projectors vs direct async publish. This would make the closing step
feel like a decision rather than a summary.

## Final Design Review

The final design now integrates the steps well. It includes rule storage,
windowed local-time expansion, overrides/exceptions, recurrence ids, series
splits, busy-index free/busy, organizer-authoritative invites, reliable
reminders, cursor sync with tombstones, read cache, sharding, and bounded
projector lag.

The final-design risk is no longer missing components; it is semantic
precision. Decide whether `ChangeLog -> Projector` is the only durable owner of
derived work. If yes, remove or relabel direct side-effect links from
`EventSvc` to `InviteSvc` and `ReminderQ`. Also add the attendee-calendar
projection path so the final design explains how organizer-owned events appear
in attendee calendar views, free/busy indexes, and sync streams.

## Concept Introduction and Learning Flow

The concept staging is strong:

- The naive model fails first, so RRULE storage feels motivated.
- Timezone/DST correctness follows recurrence at the right time.
- Free/busy appears after correct interval expansion.
- Invites/RSVPs introduce collaboration and races after event correctness.
- Reminders and sync now introduce durable async work rather than appearing as
  a summary.
- Scaling closes with sharding, burst handling, projectors, cache invalidation,
  and DR.

The missing concept is "calendar event projection" or "attendee calendar
reference." It should be introduced in Step 5 and reused in Step 6/7. That one
concept connects invites, attendee calendar reads, busy indexes, reminders, and
sync.

## Step-to-Final-Design Coherence

The step-to-final-design mapping is now mostly coherent:

- Step 1 motivates leaving one-row-per-occurrence behind.
- Step 2 introduces rule storage, overrides, and the expander.
- Step 3 defines the expander's timezone behavior.
- Step 4 introduces FreeBusy, BusyIndex, and projector-driven index updates.
- Step 5 introduces organizer-authoritative invites and RSVP race handling.
- Step 6 introduces ReminderQ and SyncSvc with real flows.
- Step 7 introduces ChangeLog, Projector, Cache, sharding, and DR.

The remaining weak transition is Step 5 into Step 6/7: attendee calendars need
derived projection state before sync and free/busy can be fully explained. The
other weak point is the mixed direct/projector side-effect path in the final
diagram.

## Realism Compared With Production Systems

The design now handles many real-world calendar issues:

- RRULE plus overrides instead of pre-created infinite occurrence rows.
- Local-time recurrence with IANA TZIDs and explicit DST edge policy.
- Stable recurrence ids for instance edits.
- Policy-bound conflict checks rather than assuming all overlaps are rejected.
- Idempotent writes and optimistic concurrency.
- At-least-once reminder delivery with fire-once scheduler execution.
- Tombstones and cursor retention for device sync.
- Durable outbox/change log and idempotent projectors.
- Rebuildable derived indexes and caches.

Residual realism gaps:

- Cross-calendar attendee projections are not explicit enough for reads, sync,
  reminders, and busy indexing.
- External calendar sync is named, but iTIP/CalDAV inbound/outbound failure,
  duplicate, and reconciliation behavior is still mostly out of scope.
- Privacy/ACL semantics are present in the model but not strongly visible in
  free/busy API examples.
- Reminder jobs would benefit from lease, attempt, recipient, and channel
  fields to match the described state machine.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- `steps[].view.nodes` string references resolve against high-level
  architecture nodes.
- `steps[].view.links`, option view link references, and final-design link
  references resolve against `highLevelArchitecture.links`.
- `satisfies.functional[].steps` and `satisfies.nonFunctional[].steps` resolve
  to real step ids.
- Step and API sequence messages reference declared participants.
- Flow and option names are present.
- Option-local nodes `OccCache` and `AttendeeDB` are rendered inline and are
  acceptable, but adding explicit canonical `type` values would make styling
  clearer if they become more prominent.
- Because this review only changes `REVIEW.md`, no `docs/` rebuild is needed.

## Recommended Edits, Prioritized

### P1: Make the change-log/projector path authoritative

Align API sequences, architecture links, and final-design prose so durable side
effects are owned by the outbox/change-log pipeline. Remove or relabel direct
`EventSvc -> InviteSvc` and `EventSvc -> ReminderQ` side-effect paths.

### P1: Add attendee-calendar projection state

Introduce `calendar_event_refs` or an equivalent entity and explain how
organizer event changes fan out into attendee calendar change logs, busy-index
updates, sync cursors, and local reminder state.

### P2: Fix capacity consistency and storage math

Reconcile `500M users * 3 calendars/user * 50 active events/calendar` with the
`10B events` headline. Separate canonical events from attendee refs, expanded
instances, change-log rows, busy intervals, and reminder jobs.

### P2: Surface privacy enforcement in the API/flow

Add caller/authorization context to free/busy and sync examples. Show
busy-only/private/no-permission response behavior.

### P2: Deepen Step 7 with a trade-off or sequence

Add one closing decision: sharding strategy, outbox/projector vs direct async
publish, or cache invalidation strategy. This would give Step 7 the same
decision quality as earlier steps.

### P3: Add small state-machine details

Add `lease_until`, `attempt_count`, `recipient_id`, and `channel` to
`reminder_jobs` or mention them in Step 6. Add an explicit tzdb-update
recompute policy in Step 3.

## What Not To Change

- Keep recurrence and timezone as separate steps.
- Keep "store rule, expand on read" as the default recurrence decision.
- Keep the busy-interval index as the default free/busy mechanism.
- Keep organizer-authoritative events as the default internal invite model.
- Keep reminders and sync in the same step now that the async state machine is
  concrete.
- Keep the durable change log and idempotent projectors as the final
  architecture's central reliability mechanism.

## Bottom Line

The recent changes turned the calendar interview into a strong book-quality
case. The next refinement should not broaden the scope; it should make the new
production spine precise. Clarify that the change log owns derived side effects,
add attendee-calendar projections, and tighten the capacity math. That would
close the main remaining gaps without disturbing the excellent recurrence,
timezone, free/busy, reminders, and sync flow.
