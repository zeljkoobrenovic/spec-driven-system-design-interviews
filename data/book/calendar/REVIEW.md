# Review: Calendar Scheduling - System Design

Reviewed file: `data/book/calendar/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a strong interview spine for a calendar system. It correctly centers the
hard parts of the domain: recurrence rules, "this instance vs the series" edits,
timezone/DST correctness, free/busy indexing, invites/RSVPs, reminders, and
delta sync. The step order is natural and teaches the candidate to move from a
naive event table toward derived indexes and collaboration workflows.

The main weakness is that several production boundaries are still compressed
into prose. Capacity is qualitative rather than calculated, the API/data model
do not expose enough mutation, RSVP, sync, reminder, idempotency, and privacy
contracts, and derived-state propagation is described without a durable change
pipeline. The design is plausible, but the next pass should make the production
mechanics concrete enough that a candidate can reason about correctness under
retry, race, timezone rule changes, external-provider ambiguity, and stale
indexes.

| Dimension | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 3.8 / 5 | Good core architecture for recurrence, free/busy, invites, and reminders; under-specified contracts around mutation, recurrence identity, and derived state. |
| Production realism | 3.2 / 5 | Names the right issues, but needs idempotency, outbox/change-log mechanics, ACL/privacy, sync cursors, reminder dedup, and external-calendar failure handling. |
| Pedagogical flow | 4.1 / 5 | The progression is clean and interview-friendly; later steps need options, flows, and traps at the same depth as recurrence/timezone. |
| Final design coherence | 3.7 / 5 | Final design includes the introduced components, but mentions caches and sync/reminder behavior that the schema/API do not yet support explicitly. |
| Dataset/rendering fit | 4.5 / 5 | JSON parses; step view nodes, links, highlights, and `satisfies` step references resolve. Mostly polish issues in diagrams and probe-link grouping. |

Recommendation: keep the current conceptual spine. Add concrete capacity math,
expand the API/data model for mutation and sync workflows, and add a durable
event/change pipeline that feeds busy indexes, reminders, invite fanout, and
device sync.

## What Works Well

- The opening naive step is effective: pre-created occurrence rows plus
  local-string times exposes both infinite recurrence and DST bugs quickly.
- The recurrence section is strong. It teaches RRULE storage, windowed
  expansion, EXDATEs, overrides, and the "this / following / all" edit split.
- The timezone step correctly frames recurrence as local wall-clock expansion
  followed by UTC conversion, instead of a fixed UTC offset.
- Free/busy is framed around a derived, per-calendar busy-interval index, which
  is the right privacy and performance boundary for availability queries.
- The invite step chooses an organizer-authoritative event as the default and
  contrasts it with per-attendee copies.
- The final design integrates the main components: Event Service, Event Store,
  Expander, Free/Busy Service, Busy Index, Invite Service, Reminder Scheduler,
  Notification Service, and Sync Service.
- The renderer-facing structure is healthy: no raw Mermaid step diagrams,
  structured sequence data where present, and no unresolved step view links or
  `satisfies` references in the checks run during review.

## Highest-Impact Issues

### 1. Capacity is qualitative, so the scaling step has no numbers to build on

The capacity section says "billions", "common", "frequent", and
"exactly-once-ish", but it does not translate the product surface into read QPS,
write QPS, event volume, recurrence expansion work, free/busy fanout, reminder
burst size, sync traffic, or storage. Step 7 then says to shard by calendar/user
and absorb reminder bursts, but the reader cannot evaluate whether those
choices are sufficient.

Why it matters: calendar systems are dominated by skewed workloads. Most reads
are narrow window reads, free/busy fanout multiplies by attendee count, and
reminders spike at round local times. Without estimates, the dataset cannot
teach when to maintain a busy index, how far to precompute, how many reminder
workers are needed, or what a shard must own.

Concrete fix: replace the qualitative capacity bullets with a small calculation
set, for example:

- Active users, calendars per user, events per calendar, and recurring-event
  percentage.
- Calendar view read QPS, event mutation QPS, RSVP QPS, free/busy QPS, and
  typical attendee count.
- Expansion window assumptions such as 30 or 90 days.
- Reminder fanout at local 9am and before-meeting offsets.
- Storage estimate for event rows, attendees, overrides, change-log entries,
  busy intervals, and reminder jobs.
- Target latency for event list, free/busy, create/update, RSVP, and sync.

### 2. The API is too small for the promised behavior

The API section has create, free/busy, and list-events endpoints. It does not
show the contracts for update/delete, edit scope (`this`, `thisAndFollowing`,
`series`), RSVP, reminder preferences, delta sync, idempotency, or external
calendar sync. The create request has `start`, `tz`, `rrule`, and attendees, but
does not expose `calendarId`, `organizerId`, `duration`/`end`, `visibility`,
`conference/resource` metadata, reminders, idempotency key, or write version.

Why it matters: the most interesting correctness problems in this case happen
on mutations, not on simple reads. Recurrence edits need a scope and a stable
occurrence identity. RSVP and organizer edits race. Device sync needs a cursor
and tombstones. Retried create/update/RSVP requests need idempotency keys.

Concrete fix: add representative endpoints:

- `PATCH /v1/events/{eventId}` with `scope`, `recurrenceId`, `expectedVersion`,
  and idempotency.
- `DELETE /v1/events/{eventId}` with the same recurrence scope.
- `POST /v1/events/{eventId}/rsvp` with attendee id, response, version, and
  idempotency key.
- `GET /v1/sync?calendarId=...&cursor=...` returning changed events,
  tombstones, and the next cursor.
- Optional `PUT /v1/events/{eventId}/reminders` or reminder fields on create
  and update.

### 3. The data model does not yet support sync, reminders, privacy, and safe recurrence edits

The current model has `events`, `event_overrides`, and `attendees`. That is a
good start, but it is not enough for the behavior in the requirements and final
design. There is no calendar membership/share table, no ACL/visibility model,
no change-log or sync-cursor table, no reminder job table, no idempotency table,
and no versioning field. The `event_overrides.instance_date` field is also
ambiguous for recurring events across timezone and rule changes.

Why it matters: production calendars need to answer "who may see this?", "what
changed since my cursor?", "did this retry already apply?", "which occurrence
did this override target?", and "has this reminder already fired?" These cannot
be inferred from a minimal event row.

Concrete fix: extend the model with a few focused entities rather than a large
schema dump:

- `calendars` and `calendar_memberships` or `calendar_acl`.
- `event_versions` or `events.version` for optimistic concurrency.
- `event_overrides.recurrence_id`, using the original local occurrence
  timestamp plus TZID, not a vague date.
- A series-splitting representation for "this and following".
- `reminder_jobs` with `fire_at_utc`, `event_id`, `recurrence_id`,
  `dedup_key`, and state.
- `calendar_changes` with monotonically increasing sequence/cursor,
  tombstones, and changed entity ids.
- `idempotency_keys` scoped by actor, operation, and request fingerprint.

### 4. Derived-state propagation is implied instead of designed

The prose says the busy index is updated when events change, reminders are
scheduled by fire time, and device sync pulls changes since a cursor. The final
design also says busy indexes, expanded instances, and device caches are
derived/rebuildable. But there is no durable mutation stream, outbox, projector,
or reconciliation loop in the architecture or data model.

Why it matters: busy indexes, reminder queues, invite fanout, and sync cursors
all depend on not losing change events. If an event update commits but the busy
index update is lost, free/busy lies. If a reminder enqueue fails after the
event write, the user misses the reminder. If sync changes are not durable,
offline devices never converge.

Concrete fix: add a local transaction boundary around event writes and an
outbox/change-log record. Then show projectors/workers consuming that durable
stream:

- Busy-index projector updates per-calendar intervals idempotently.
- Reminder scheduler materializes due jobs for the next horizon.
- Invite fanout worker sends update notifications at least once.
- Sync service reads the same calendar change log for cursor-based pulls.
- Reconciliation jobs rebuild the busy index and reminder jobs from EventDB.

### 5. Reminder and notification semantics need a sharper failure model

The requirements ask for reliable reminders that fire on time and once. The
dataset says "exactly-once-ish" and "deduped", which is honest, but it does not
define the operational contract. There is no state model for scheduled, leased,
sent, failed, cancelled, or superseded reminders, and no explanation of what
happens when notification delivery is retried.

Why it matters: notification systems are usually at-least-once. The calendar
service can dedup job execution, but it cannot guarantee that every external
push/email channel delivers exactly once. The candidate should learn to state
the boundary precisely.

Concrete fix: define reminders as at-least-once processing with idempotent send
attempts and user-visible dedup keys. Add a short sequence flow for due
reminder execution:

- Worker leases due reminder job.
- Checks event/version still valid and reminder not cancelled.
- Sends via notification provider with a stable dedup key.
- Marks sent or retries with backoff.
- Metrics track due-lag, duplicate-suppression count, provider errors, and
  abandoned leases.

## System Design Soundness

### Requirements and Capacity

The requirement list is well scoped for a calendar interview: event CRUD,
recurrence, free/busy, invites, reminders, and sync. The non-functional
requirements correctly highlight timezone/DST correctness and reliable derived
work.

The missing piece is quantitative scale. "Billions of events" is not enough by
itself. A calendar case needs at least rough traffic and fanout numbers because
the architecture choices are workload-sensitive. For example, free/busy for 20
attendees over a 30-day window has a very different cost from listing one
calendar's day view; a reminder wave for millions of users at local 9am has a
different shape from steady event CRUD.

Privacy and access control also deserve explicit non-functional treatment.
Free/busy sharing intentionally hides details, but the dataset does not define
calendar visibility, delegation, shared calendars, resource calendars, or
cross-organization free/busy permissions.

### API

The create and free/busy APIs are good starting points. The create sequence also
usefully shows conflict checking, event persistence, and invite dispatch. One
caveat: calendars generally allow overlapping events unless the organizer or a
resource calendar has a policy that rejects conflicts. The API should word
conflict checking as a policy decision, not as a universal requirement.

The API gaps are mostly mutation and sync contracts. Add update/delete with
recurrence edit scope, RSVP, sync, and reminder preference endpoints. Add
idempotency and versioning to write APIs. Those fields connect directly to the
architecture's consistency, retry, and device-sync claims.

### Data Model

The event model is directionally right: authoritative event rows, RRULEs,
EXDATEs, overrides, and attendees. It should split "UTC plus original timezone"
into precise fields: original local start, original timezone/TZID, duration,
computed UTC for each expanded instance, and possibly timezone database version
or a policy for tzdb updates.

`event_overrides.instance_date` should become a stable recurrence identity. A
date alone is risky for events that recur multiple times per day, cross
timezones, or move after a series split. Use an RFC-style recurrence id: the
original local occurrence timestamp in the event timezone.

The model also needs change tracking and reminder records to support the final
design. Without them, the Sync Service and Reminder Scheduler are components
without a clear source of truth.

### Architecture

The main components are sensible. EventDB is authoritative, Expander is
stateless, BusyIndex is derived, FreeBusy handles availability queries,
InviteSvc handles collaboration, ReminderQ handles time-ordered work, and
SyncSvc handles device/external sync.

The architecture should add one explicit durable-change component: an outbox,
calendar change log, or event stream. That single addition would connect event
mutations to busy-index updates, reminders, invite notifications, and sync
cursors. It would also make "derived/rebuildable" operationally credible.

The final design mentions hot calendar views and free/busy caches in Step 7,
but no cache component appears in the final diagram. Either add a cache node or
remove/cache-soften that claim so the final diagram and prose match.

## Step-by-Step Pedagogical Review

### Step 1: Naive: One Row per Occurrence, Local-String Times

This is a strong opening. It presents a tempting model and shows precisely why
it fails: infinite recurrence, bulk series edits, timezone comparisons, and DST
corruption. The trap is concrete and useful.

Improvement: none required. Keep this as the problem-revealing baseline.

### Step 2: Recurring Events: Store the Rule, Expand on Read

This is one of the strongest sections. The default option is realistic, the
materialize-every-row alternative is a useful foil, and the bounded cache option
adds production nuance without making it the default. The concept and trap are
well aligned.

Improvement: add a small "this and following" model note. The prose names
series splitting, but the data model only has overrides and EXDATEs. A candidate
should see that a split creates a new series from a recurrence boundary and
terminates or modifies the original rule.

### Step 3: Timezones and DST Correctness

This is also strong. It correctly teaches that recurring events are anchored to
local wall-clock time and only then converted to UTC. The option comparison is
clear and avoids the common "store UTC only" mistake for recurring events.

Improvement: state explicit policy choices for nonexistent and ambiguous local
times. For example, decide whether a spring-forward `02:30` occurrence is
skipped, shifted to `03:00`, or rejected at creation time, and how the repeated
fall-back hour is disambiguated.

### Step 4: Free/Busy Availability

The busy-interval index is the right design move and the option comparison is
good. This step also introduces privacy naturally by exposing intervals rather
than event details.

Improvement: add the update path, not just the query path. Show how an event
create/update/cancel produces a busy-index update, what version it carries, and
how the system handles temporarily stale index entries.

### Step 5: Invites and RSVPs

The organizer-authoritative option is a good default for an internal calendar
system, and the per-attendee-copy alternative is a useful contrast for
federated/iCalendar behavior.

Improvement: add an RSVP flow and a race condition trap. Organizer edits and
attendee RSVPs can cross in flight; the system needs event versions, attendee
response timestamps, idempotent RSVP writes, and update notifications that do
not erase responses.

### Step 6: Reminders and Device Sync

This step names the right concepts, but it is thinner than the earlier sections.
There are no options, flows, traps, or data-model fields for either reminders or
sync. That makes it feel like a summary rather than a design step.

Improvement: add at least one sequence flow for due reminders and one sequence
flow for delta sync. Good option comparisons would be delayed queue vs
time-bucketed scheduler vs database polling for reminders, and push-only vs
pull-with-cursor vs hybrid sync for devices.

### Step 7: Scaling and Consistency

The scaling advice is directionally correct: shard by calendar/user, keep
derived state rebuildable, and tolerate brief propagation lag. It should be
more concrete.

Improvement: connect the scale story back to capacity numbers and operational
mechanics. Name shard-key implications for events with many attendees, hot
resource calendars, cross-shard free/busy fanout, outbox/projector lag,
backfills, and disaster recovery for derived indexes.

## Final Design Review

The final design description integrates the major decisions: RRULE storage,
windowed local-time expansion, override/exceptions, busy-interval index,
organizer-authoritative invites, reminders, and cursor-based sync. The final
diagram includes all major components introduced in the steps.

The biggest final-design gap is that it has derived components but no durable
derivation mechanism. Add an outbox/change-log/event-stream component and make
it feed the BusyIndex, ReminderQ, InviteSvc/Notify, and SyncSvc. That would make
the final architecture much more production-realistic without changing the
teaching spine.

Also align Step 7's cache language with the diagram. If hot calendar/free-busy
caches are important, add a cache node and describe invalidation through the
same change stream. If not, keep caches as a follow-up optimization.

## Concept Introduction and Learning Flow

The core concepts are introduced in a good order:

- Rule + expansion follows naturally from the naive infinite-row failure.
- Timezone/DST correctness builds on recurrence rather than being a side note.
- Busy index appears after recurrence and timezone, which is right because it
  depends on correct interval materialization.
- Invites/RSVPs follow event correctness and availability.
- Reminders and sync come after event mutation and collaboration.

Missing concepts to add:

- Idempotency keys for create/update/RSVP/reminder send operations.
- Optimistic concurrency or event versions.
- Durable outbox/change log for derived state.
- Calendar ACLs, visibility, and free/busy privacy boundaries.
- Reminder job leasing, retry, dedup, and cancellation.
- Sync cursors, tombstones, and conflict resolution.
- External calendar/iTIP delivery uncertainty and reconciliation.

## Step-to-Final-Design Coherence

The step-to-final-design mapping is mostly coherent:

- Step 1 motivates replacing occurrence rows and local strings.
- Step 2 introduces EventDB plus Expander.
- Step 3 defines how Expander must handle local time and DST.
- Step 4 introduces FreeBusy and BusyIndex.
- Step 5 introduces InviteSvc and Notify.
- Step 6 introduces ReminderQ and SyncSvc.
- Step 7 frames sharding and rebuildable derived state.

The weak transitions are Step 6 and Step 7. ReminderQ and SyncSvc appear in the
final diagram, but the API and data model do not yet give them durable state.
Step 7 mentions caches and consistency boundaries that are not represented in
the final diagram or schema. Add the missing state and change-log mechanics to
make the final design feel earned rather than asserted.

## Realism Compared With Production Systems

A production-grade calendar design should make these tradeoffs explicit:

- Calendar systems often allow event overlap; conflict checks are policy-bound,
  especially for rooms/resources.
- Recurrence exceptions need stable recurrence ids, not just dates.
- Timezone rules change after future events are created; the design needs a
  recomputation policy.
- Free/busy is a privacy surface. Users may reveal full details, busy-only, or
  nothing depending on ACLs and organization boundaries.
- External calendar invites are eventually consistent and lossy. Email/iTIP and
  CalDAV clients can delay, duplicate, or reject updates.
- Reminder delivery is not exactly once through external push/email providers;
  the internal scheduler can be idempotent, but sends are at-least-once with
  deduplication.
- Device sync needs tombstones and cursor retention policies, or offline
  clients will miss deletions and old changes.
- Derived indexes must be rebuildable from an authoritative event log or event
  store.

The current dataset mentions several of these, but usually in one sentence. The
next pass should turn the most important ones into explicit fields, flows, and
traps.

## Dataset and Renderer-Facing Observations

- `interview.json` parses successfully.
- `steps[].view.nodes` references resolve against high-level architecture nodes
  or option-local inline nodes in the inspected views.
- `steps[].view.links` string references resolve against
  `highLevelArchitecture.links`.
- `satisfies.functional[].steps` and `satisfies.nonFunctional[].steps` resolve
  to real step ids.
- The structured sequence messages inspected during review reference declared
  participants.
- The requirements and capacity Mermaid diagrams are valid-looking but very
  sparse. They omit several important surfaced requirements, especially
  timezone/DST, reminders, sync, and invites.
- The two step flows have no titles, so the UI may render generic flow labels.
  Add short titles such as "Free/busy query" and "Organizer update fanout".
- Option-local nodes such as `OccCache` and `AttendeeDB` do not specify a
  canonical node type. They will render, but adding types would make captions
  and styling clearer.
- `toProbeFurther.links` contains useful links, but several are grouped under
  inherited "Booking and Contention" labels. Calendar-specific grouping such as
  "Calendar Standards", "Time and Recurrence", "Sync Protocols", and
  "Notifications and Streams" would fit this dataset better.
- `postgres-isolation` and `kafka-design` may be useful general references, but
  their `why` text does not connect tightly to this calendar case. Either tie
  them to idempotent updates/outbox/projectors or replace them with more
  calendar-specific material.

## Recommended Edits, Prioritized

### P1: Add concrete capacity math

Turn the capacity section into numbers that drive the architecture. Include
users, events, recurrence rate, event reads, writes, RSVP traffic, free/busy
fanout, reminder bursts, storage estimates, and latency targets.

### P1: Expand API and data model for mutation correctness

Add update/delete with recurrence scope, RSVP, sync, reminders, idempotency,
versions, recurrence ids, change log, reminder jobs, and ACL/visibility.

### P1: Add a durable change pipeline

Add an outbox/change-log/event-stream component and show it feeding BusyIndex,
ReminderQ, InviteSvc/Notify, and SyncSvc. Include idempotent projectors and
rebuild/reconciliation notes.

### P2: Deepen Step 6 and Step 7

Give reminders, sync, and scale the same teaching richness as recurrence and
timezone: options, sequence flows, traps, and concrete operational tradeoffs.

### P2: Make recurrence edge policies explicit

Specify recurrence ids, series splitting for "this and following", and policies
for spring-forward nonexistent times and fall-back ambiguous times.

### P2: Tighten invite/RSVP realism

Add an RSVP endpoint/flow, organizer-edit vs attendee-response race handling,
cross-provider ambiguity, attendee overrides, and notification retry behavior.

### P3: Improve diagrams and probe-link metadata

Expand the requirements/capacity diagrams, title the flows, type option-local
nodes, and regroup external links under calendar-specific categories.

## What Not To Change

- Keep recurrence and timezone as separate steps. That separation is a teaching
  strength.
- Keep "store rule, expand on read" as the default recurrence decision.
- Keep the busy-interval index as the default free/busy mechanism.
- Keep organizer-authoritative events as the default internal invite model, with
  per-attendee copies as the federated/cross-provider alternative.
- Keep derived busy indexes and reminder state rebuildable rather than
  authoritative.

## Bottom Line

The dataset already teaches the right calendar-system instincts. To make it
book-quality, the next revision should turn the implied production mechanics
into explicit API fields, data-model entities, sequence flows, and capacity
calculations. The highest-leverage addition is a durable calendar change log:
it would connect event mutations to free/busy, reminders, invites, sync, cache
invalidation, and rebuildability in one coherent design move.
