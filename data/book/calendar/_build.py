#!/usr/bin/env python3
"""Builder for the Calendar Scheduling book case."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

NODES = {
    "Client":    ("Calendar Client", "client", "boundary", [], "Creates events, views calendars, responds to invites."),
    "LB":        ("API Gateway", "edge", "traffic", ["stateless"], "Routes event, calendar, and free/busy requests."),
    "EventSvc":  ("Event Service", "service", "compute", ["stateless"], "CRUD for events; expands recurrence; checks conflicts."),
    "EventDB":   ("Event Store", "database", "state", ["stateful"], "Authoritative events + recurrence rules, sharded by calendar."),
    "Expander":  ("Recurrence Expander", "service", "compute", ["stateless"], "Materializes recurring rules into concrete instances for a window."),
    "FreeBusy":  ("Free/Busy Service", "service", "compute", ["stateless"], "Answers availability across calendars over a time range."),
    "BusyIndex": ("Busy-Interval Index", "index", "state", ["stateful", "derived"], "Per-calendar busy intervals for fast availability lookup."),
    "InviteSvc": ("Invite / RSVP Service", "service", "compute", ["stateless"], "Sends invites, tracks attendee responses, fans out updates."),
    "Notify":    ("Reminder / Notification", "service", "async", ["stateless"], "Sends reminders and invite/update notifications."),
    "ReminderQ": ("Reminder Scheduler", "queue", "async", ["stateful"], "Time-ordered queue of due reminders."),
    "SyncSvc":   ("Sync Service", "service", "compute", ["stateless"], "Delta sync to devices/external calendars (CalDAV)."),
}

LINKS = {
    "client-lb":        ("Client", "LB", "HTTPS"),
    "lb-event":         ("LB", "EventSvc", "event CRUD"),
    "event-db":         ("EventSvc", "EventDB", "persist event + RRULE"),
    "event-expander":   ("EventSvc", "Expander", "expand recurrence"),
    "event-freebusy":   ("EventSvc", "FreeBusy", "conflict check"),
    "lb-freebusy":      ("LB", "FreeBusy", "find a time"),
    "freebusy-index":   ("FreeBusy", "BusyIndex", "busy intervals"),
    "expander-index":   ("Expander", "BusyIndex", "materialize busy"),
    "event-invite":     ("EventSvc", "InviteSvc", "invite attendees"),
    "invite-notify":    ("InviteSvc", "Notify", "send invite/update"),
    "notify-client":    ("Notify", "Client", "notification"),
    "event-reminder":   ("EventSvc", "ReminderQ", "schedule reminder"),
    "reminder-notify":  ("ReminderQ", "Notify", "due reminder"),
    "client-sync":      ("Client", "SyncSvc", "delta sync"),
    "sync-eventdb":     ("SyncSvc", "EventDB", "changes since cursor"),
    "invite-event":     ("InviteSvc", "EventSvc", "RSVP updates event"),
}


def view(nodes, links, highlight=None, groups=None):
    v = {"nodes": list(nodes), "links": list(links)}
    if highlight: v["highlight"] = list(highlight)
    if groups: v["groups"] = list(groups)
    return v


def hla():
    nodes = [{"id": n, "label": l, "type": t, "category": c, "traits": tr, "description": d}
             for n, (l, t, c, tr, d) in NODES.items()]
    links = [{"id": i, "from": f, "to": to, "label": lb} for i, (f, to, lb) in LINKS.items()]
    types = [
        {"id": "events", "label": "Events & Recurrence", "nodes": ["EventSvc", "EventDB", "Expander"]},
        {"id": "availability", "label": "Availability", "nodes": ["FreeBusy", "BusyIndex"]},
        {"id": "collab", "label": "Invites, Reminders, Sync", "nodes": ["InviteSvc", "Notify", "ReminderQ", "SyncSvc"]},
    ]
    return {"nodes": nodes, "links": links, "types": types}


def seq(parts, msgs, highlight=None):
    out = {"sequence": {"participants": parts, "messages": msgs}}
    if highlight: out["highlight"] = highlight
    return out


data = {
    "title": "Calendar Scheduling — System Design",
    "description": "Design a calendar system: create one-off and recurring events, find mutually-free times across attendees, send invites/RSVPs, and remind people — correctly across timezones. The themes are recurrence expansion, free/busy availability, the timezone/DST minefield, and invite + reminder fanout.",
    "highLevelArchitecture": hla(),

    "requirementsDiagram": [
        "graph LR",
        "  User[User]",
        "  Create[Create event]",
        "  Recur[Recurring rules]",
        "  Find[Find free time]",
        "  Invite[Invite + RSVP]",
        "  User --> Create",
        "  Create --> Recur",
        "  Create --> Find",
        "  Create --> Invite",
    ],
    "capacityDiagram": [
        "graph LR",
        "  Events[Billions of events]",
        "  Recur[Recurring expand]",
        "  Busy[Free/busy queries]",
        "  Events --> Recur",
        "  Recur --> Busy",
    ],

    "requirements": {
        "functional": [
            "Create, update, delete one-off and recurring events.",
            "Recurring events (daily/weekly/monthly rules) with exceptions and edits to a single instance vs the series.",
            "Find free/busy times across multiple attendees over a range.",
            "Invite attendees, track RSVPs, and propagate updates.",
            "Reminders/notifications before events; sync to devices/external calendars.",
        ],
        "nonFunctional": [
            "Correct across timezones and DST — the hardest hidden requirement.",
            "Fast free/busy and calendar reads (common operations).",
            "Consistent: an RSVP/edit propagates to all attendees' views.",
            "Scale to billions of events across many users.",
            "Reliable reminders (fire on time, once) and delta sync to devices.",
        ],
    },

    "capacity": [
        {"label": "Events", "value": "billions", "note": "Sharded by calendar/user."},
        {"label": "Recurring", "value": "common", "note": "One rule -> many instances; don't store them all."},
        {"label": "Free/busy queries", "value": "frequent", "note": "Scheduling assistants, meeting finders."},
        {"label": "Timezones", "value": "all", "note": "Plus DST transitions — correctness minefield."},
        {"label": "Reminders", "value": "exactly-once-ish", "note": "Fire on time, dedup repeats."},
    ],

    "api": [
        {"method": "POST", "path": "/v1/events",
         "description": "Create an event (one-off or recurring); conflict-checks and invites attendees.",
         "request": "{ \"start\": \"2026-06-01T10:00\", \"tz\": \"America/Los_Angeles\", \"rrule\": \"FREQ=WEEKLY\", \"attendees\": [...] }",
         "response": "{ \"eventId\": \"e_9\" }",
         **seq(
             [{"id": "Client"}, {"id": "EventSvc", "label": "Event Service"}, {"id": "FreeBusy", "label": "Free/Busy"},
              {"id": "EventDB", "label": "Event Store"}, {"id": "InviteSvc", "label": "Invites"}],
             [
                 {"from": "Client", "to": "EventSvc", "arrow": "->>", "label": "create event + rrule"},
                 {"from": "EventSvc", "to": "FreeBusy", "arrow": "->>", "label": "conflict check"},
                 {"from": "EventSvc", "to": "EventDB", "arrow": "->>", "label": "persist rule (not instances)"},
                 {"from": "EventSvc", "to": "InviteSvc", "arrow": "->>", "label": "invite attendees"},
                 {"from": "EventSvc", "to": "Client", "arrow": "-->>", "label": "201 eventId"},
             ])},
        {"method": "GET", "path": "/v1/freebusy",
         "description": "Find busy intervals (or free slots) across attendees over a range.",
         "request": "?attendees=u1,u2,u3&from=...&to=...",
         "response": "{ \"busy\": { \"u1\": [ ... ] }, \"freeSlots\": [ ... ] }",
         **seq(
             [{"id": "Client"}, {"id": "FreeBusy", "label": "Free/Busy"}, {"id": "BusyIndex", "label": "Busy Index"}],
             [
                 {"from": "Client", "to": "FreeBusy", "arrow": "->>", "label": "free/busy(attendees, range)"},
                 {"from": "FreeBusy", "to": "BusyIndex", "arrow": "->>", "label": "busy intervals per calendar"},
                 {"from": "FreeBusy", "to": "Client", "arrow": "-->>", "label": "busy + free slots"},
             ])},
        {"method": "GET", "path": "/v1/events",
         "description": "List events in a window (recurring rules expanded to instances for that window).",
         "request": "?calendar=c_1&from=...&to=...",
         "response": "{ \"events\": [ ... expanded instances ... ] }"},
    ],

    "dataModel": [
        {"name": "events", "note": "Authoritative events; recurring stored as a rule, not expanded instances.",
         "fields": [
             {"name": "event_id", "type": "uuid PK"},
             {"name": "calendar_id", "type": "bigint (shard key)"},
             {"name": "start_utc", "type": "timestamp (UTC) + original tz"},
             {"name": "duration", "type": "interval"},
             {"name": "rrule", "type": "recurrence rule (RFC 5545) | null"},
             {"name": "exdates", "type": "list<date> (cancelled instances)"},
         ]},
        {"name": "event_overrides", "note": "Per-instance edits to a recurring series.",
         "fields": [
             {"name": "event_id", "type": "uuid (series)"},
             {"name": "instance_date", "type": "the occurrence being overridden"},
             {"name": "changes", "type": "json (new time/title or cancellation)"},
         ]},
        {"name": "attendees", "note": "Invite + RSVP state per event.",
         "fields": [
             {"name": "event_id", "type": "uuid"},
             {"name": "user_id", "type": "bigint"},
             {"name": "response", "type": "enum(needs_action, accepted, declined, tentative)"},
         ]},
    ],

    "patterns": [
        {"name": "Store rule, expand on read", "what": "Persist recurring events as a rule; materialize concrete instances only for the queried window.",
         "whenToUse": "Recurring events that could be infinite — never store all instances.", "steps": ["recurrence"]},
        {"name": "UTC storage + tz at edges", "what": "Store times in UTC with the original timezone; convert for display and recurrence.",
         "whenToUse": "Any system spanning timezones / DST.", "steps": ["timezone"]},
        {"name": "Busy-interval index", "what": "Maintain per-calendar busy intervals so free/busy is a fast range query.",
         "whenToUse": "Frequent availability lookups across calendars.", "steps": ["freebusy"]},
        {"name": "Override + exception model", "what": "Represent single-instance edits/cancellations as overrides on the series.",
         "whenToUse": "'This event' vs 'this and following' vs 'all events' edits.", "steps": ["recurrence"]},
        {"name": "Invite fanout + RSVP", "what": "Propagate an event to attendees' calendars and reconcile their responses.",
         "whenToUse": "Multi-attendee events.", "steps": ["invites"]},
        {"name": "Time-ordered reminders + delta sync", "what": "Schedule reminders by fire time; sync changes to devices via a cursor.",
         "whenToUse": "Timely reminders and multi-device consistency.", "steps": ["reminders"]},
    ],

    "steps": [
        {
            "id": "recurrence",
            "title": "1. Recurring Events: Store the Rule, Expand on Read",
            "description": [
                "A 'daily standup forever' has infinite instances — you can't store them all. Store the recurrence as a rule (RFC 5545 RRULE: FREQ/INTERVAL/BYDAY/UNTIL); concrete occurrences are materialized only for the window a query asks about (e.g. this month's view).",
                "Edits are the tricky part: 'this instance' (an override), 'this and following' (split the series), or 'all' (edit the rule). Cancellations of one occurrence are exception dates (EXDATE); single-instance changes are overrides keyed by occurrence date.",
                "So reads expand the rule + apply overrides/exceptions for the window; writes touch the rule or a small override, never a giant instance set.",
            ],
            "view": view(["Client", "EventSvc", "EventDB", "Expander"],
                         ["lb-event", "event-db", "event-expander"],
                         highlight=["EventSvc", "Expander"], groups=["events"]),
            "decisionPrompt": "A meeting recurs weekly with no end date. How do you store and query it?",
            "concepts": [
                {"term": "Rule + expansion", "definition": "Store recurrence as a rule; expand to instances only for a queried window, applying overrides/exceptions.",
                 "whyItMatters": "Avoids storing infinite instances and makes 'edit this vs series' tractable.",
                 "example": "RRULE=FREQ=WEEKLY; EXDATE drops one week; an override moves another."},
            ],
            "patterns": ["Store rule, expand on read", "Override + exception model"],
            "whyNow": ["Recurrence is the defining calendar complexity; rule-storage + on-read expansion + overrides is the foundational model."],
            "recap": {"before": "Nothing.", "after": "Recurring events as rules, expanded per window with overrides.",
                      "newRisk": "Expanding a rule across timezones/DST is where calendars famously break."},
            "traps": [
                {"trap": "Materializing all instances of a recurring event up front.", "why": "No-end rules are infinite; editing the series means rewriting everything.",
                 "instead": "Store the rule; expand on read; represent edits as overrides."},
            ],
        },
        {
            "id": "timezone",
            "title": "2. Timezones and DST Correctness",
            "description": [
                "The most error-prone requirement. Store event times in UTC plus the original timezone, and convert at the edges (display, recurrence expansion). But a recurring 'every day at 9am local' is anchored to wall-clock local time, not a fixed UTC offset — across a DST change, 9am local shifts in UTC.",
                "So recurrence must expand in the event's local timezone (apply the rule on local wall-clock, then convert each instance to UTC), or DST transitions produce wrong instance times. Handle the gnarly DST edge cases: a 2:30am event on a spring-forward day doesn't exist; a fall-back hour repeats.",
                "Keep the original tz on the event (not just UTC) so edits and expansion stay correct, and so '9am' stays 9am after DST.",
            ],
            "view": view(["EventSvc", "Expander", "EventDB"],
                         ["event-expander", "event-db"],
                         highlight=["Expander"], groups=["events"]),
            "decisionPrompt": "A daily 9am meeting in NYC: after the DST change, what time is it in UTC, and how do you keep it 9am local?",
            "concepts": [
                {"term": "UTC + original tz, expand in local time", "definition": "Store UTC plus the event's timezone; expand recurrence on local wall-clock then convert.",
                 "whyItMatters": "Keeps 'every day at 9am local' correct across DST instead of drifting.",
                 "example": "9am NY recurs in America/New_York; each instance -> UTC (offset changes at DST)."},
            ],
            "patterns": ["UTC storage + tz at edges"],
            "whyNow": ["Timezone/DST is the hidden correctness crux; expanding recurrence in local time (not fixed UTC) is exactly the senior insight interviewers probe."],
            "recap": {"before": "Naive UTC times.", "after": "DST-correct recurrence anchored to local wall-clock.",
                      "newRisk": "Finding a free time across attendees requires fast availability lookup."},
            "traps": [
                {"trap": "Storing only UTC and expanding recurrence in UTC.", "why": "A fixed UTC offset breaks 'daily at 9am local' across DST — instances drift by an hour.",
                 "instead": "Keep the original tz; expand the rule in local time, then convert each instance."},
            ],
        },
        {
            "id": "freebusy",
            "title": "3. Free/Busy Availability",
            "description": [
                "Scheduling assistants and meeting-finders need 'when are these N people free?'. Computing that by expanding every attendee's full calendar per query is slow. Maintain a per-calendar busy-interval index: the merged busy time ranges, kept current as events change.",
                "Free/busy then becomes a fast range query: pull each attendee's busy intervals over the window, merge them, and the gaps are the mutually-free slots. The index hides event details (privacy) — it only exposes busy/free, which is also what cross-organization free/busy sharing needs.",
                "The busy index is derived from events (including expanded recurrence) and rebuildable; it's updated when events are created/edited.",
            ],
            "view": view(["Client", "FreeBusy", "BusyIndex", "Expander"],
                         ["lb-freebusy", "freebusy-index", "expander-index"],
                         highlight=["FreeBusy", "BusyIndex"], groups=["availability"]),
            "decisionPrompt": "How do you find a 30-min slot free for 8 people next week without scanning everyone's full calendar?",
            "concepts": [
                {"term": "Busy-interval index", "definition": "Per-calendar merged busy time ranges for fast availability queries.",
                 "whyItMatters": "Turns multi-attendee availability into a range merge, not full-calendar expansion.",
                 "example": "Merge u1..u8 busy intervals over the week; gaps >= 30min are candidate slots."},
            ],
            "patterns": ["Busy-interval index"],
            "whyNow": ["Free/busy is a core, frequent operation; the busy-interval index is the mechanism that makes meeting-finding fast and privacy-preserving."],
            "recap": {"before": "Availability by full expansion per query.", "after": "Fast free/busy via a busy-interval index.",
                      "newRisk": "Multi-attendee events need invites and RSVPs propagated to everyone."},
        },
        {
            "id": "invites",
            "title": "4. Invites and RSVPs",
            "description": [
                "A meeting with attendees lives on multiple calendars. The invite service fans the event out to each attendee's calendar (or external system) and tracks RSVP state (accepted/declined/tentative) per attendee.",
                "RSVPs and organizer edits must propagate: when an attendee responds or the organizer changes the time, all attendees' views update and are notified. There's one organizer-owned source event; attendee copies/references reflect it. Cross-provider invites use the iCalendar/iTIP standard.",
                "Concurrency: organizer edits and attendee RSVPs can race; the organizer's event is authoritative for the event details, attendee rows for responses.",
            ],
            "view": view(["EventSvc", "InviteSvc", "Notify", "Client"],
                         ["event-invite", "invite-notify", "notify-client", "invite-event"],
                         highlight=["InviteSvc"], groups=["collab", "events"]),
            "decisionPrompt": "The organizer moves a meeting an hour later. What happens on all 10 attendees' calendars?",
            "patterns": ["Invite fanout + RSVP"],
            "whyNow": ["Invites/RSVP make calendars collaborative; fanout + propagation + a clear source-of-truth is the multi-attendee correctness model."],
            "concepts": [
                {"term": "Organizer-authoritative invites", "definition": "One organizer-owned event; attendee copies reflect it; RSVPs tracked per attendee.",
                 "whyItMatters": "Keeps event details consistent across many calendars while letting each attendee respond.",
                 "example": "Organizer moves the time -> propagate to attendees -> notify; RSVPs preserved."},
            ],
            "recap": {"before": "Single-calendar events.", "after": "Multi-attendee events with propagated edits + RSVPs.",
                      "newRisk": "People expect reminders on time and the calendar synced across devices."},
        },
        {
            "id": "reminders",
            "title": "5. Reminders and Device Sync",
            "description": [
                "Reminders must fire on time and once. Schedule them by fire time in a time-ordered reminder queue/scheduler (the same due-index idea as a job scheduler); a due reminder triggers a notification. Recurring events generate the next reminder as each instance passes.",
                "Device/external sync uses delta sync: each client tracks a cursor and pulls changes since it last synced (new/edited/cancelled events), reconciling locally — efficient and offline-tolerant. CalDAV/standard sync interoperates with external calendars.",
                "Reminders are deduped (fire once even if the scheduler retries) and respect the user's timezone for 'remind me at 9am'.",
            ],
            "view": view(["EventSvc", "ReminderQ", "Notify", "SyncSvc", "EventDB"],
                         ["event-reminder", "reminder-notify", "notify-client", "client-sync", "sync-eventdb"],
                         highlight=["ReminderQ", "SyncSvc"], groups=["collab", "events"]),
            "decisionPrompt": "How do you fire a reminder exactly once at the right local time, and keep all the user's devices in sync?",
            "concepts": [
                {"term": "Time-ordered reminders + delta sync", "definition": "Reminders scheduled by fire time (deduped); device sync via a change cursor.",
                 "whyItMatters": "Timely, once-only reminders and efficient multi-device consistency.",
                 "example": "Reminder fires 10min before in local tz; device pulls changes since cursor t_77."},
            ],
            "patterns": ["Time-ordered reminders + delta sync"],
            "whyNow": ["Reminders + sync complete the user experience; reusing the scheduler due-index and delta-sync patterns ties it to known mechanisms."],
            "recap": {"before": "No reminders/sync.", "after": "On-time deduped reminders + cursor-based device sync.",
                      "newRisk": "Billions of events and reminder bursts (top-of-hour) need scaling."},
        },
        {
            "id": "scale",
            "title": "6. Scaling and Consistency",
            "description": [
                "Shard events by calendar/user so a calendar's events and busy index live together and reads are local. Free/busy across many attendees fans out per-calendar (each shard answers its own busy intervals) and merges.",
                "Reminder bursts (everyone's 9am meeting) concentrate at round times; the time-ordered scheduler + queue absorbs them with scalable workers, jittering where possible. Caches hold hot calendar views and free/busy results.",
                "Consistency: the event store is authoritative; busy index, expanded instances, and device caches are derived/rebuildable. An RSVP or edit propagates via the invite/sync path; brief propagation lag across attendees' devices is acceptable (eventual), but the organizer's event details are the source of truth.",
            ],
            "view": view(["EventSvc", "EventDB", "BusyIndex", "FreeBusy", "ReminderQ"],
                         ["event-db", "freebusy-index", "lb-freebusy", "event-reminder"],
                         highlight=["EventDB"], groups=["events", "availability"]),
            "decisionPrompt": "Everyone has a 9am meeting reminder. What happens at 8:50am across millions of users?",
            "whyNow": ["Closing on sharding + reminder bursts + derived-state consistency shows the design scales and stays correct at billions of events."],
            "recap": {"before": "Single-store assumptions.", "after": "Calendar-sharded events, burst-tolerant reminders, rebuildable derived state.",
                      "newRisk": "Propagation lag and reminder-burst spikes — bounded by sharding, jitter, and eventual device sync."},
            "bottlenecks": [
                {"issue": "Top-of-hour reminder burst.", "mitigation": "Time-ordered scheduler + queue + autoscaled workers; jitter where allowed."},
                {"issue": "Free/busy across many attendees.", "mitigation": "Per-calendar busy index, parallel fan-out + merge, cached results."},
            ],
            "failureDrills": [
                {"scenario": "The busy index is lost for a calendar.",
                 "expectedBehavior": "Rebuild it from events (expanding recurrence); free/busy briefly falls back to direct expansion.",
                 "mitigation": "Treat the busy index as rebuildable derived state."},
            ],
        },
    ],

    "finalDesign": {
        "title": "Final Design — Calendar System",
        "description": "Events persist authoritatively (recurring ones as RRULE rules, never expanded instances), with single-instance edits/cancellations as overrides/exceptions. Reads expand rules for the queried window in the event's local timezone (DST-correct) and apply overrides. A per-calendar busy-interval index makes multi-attendee free/busy a fast range-merge. Invites fan out to attendees with organizer-authoritative details and tracked RSVPs; reminders are scheduled by fire time (deduped, local-tz) and devices stay current via cursor-based delta sync. Events shard by calendar; busy index, expanded instances, and device caches are derived/rebuildable; reminder bursts are absorbed by the scheduler queue.",
        "view": view(
            ["Client", "LB", "EventSvc", "EventDB", "Expander", "FreeBusy", "BusyIndex",
             "InviteSvc", "Notify", "ReminderQ", "SyncSvc"],
            ["client-lb", "lb-event", "event-db", "event-expander", "event-freebusy", "lb-freebusy",
             "freebusy-index", "expander-index", "event-invite", "invite-notify", "notify-client",
             "event-reminder", "reminder-notify", "client-sync", "sync-eventdb", "invite-event"],
            groups=["events", "availability", "collab"]),
    },

    "satisfies": {
        "functional": [
            {"requirement": "One-off + recurring events", "how": "Rule storage + on-read expansion + overrides.", "steps": ["recurrence"]},
            {"requirement": "Single-instance vs series edits", "how": "Override/exception model.", "steps": ["recurrence"]},
            {"requirement": "Free/busy across attendees", "how": "Per-calendar busy-interval index + merge.", "steps": ["freebusy"]},
            {"requirement": "Invites + RSVP", "how": "Organizer-authoritative invite fanout + responses.", "steps": ["invites"]},
            {"requirement": "Reminders + device sync", "how": "Time-ordered reminders + cursor delta sync.", "steps": ["reminders"]},
        ],
        "nonFunctional": [
            {"requirement": "Timezone/DST correctness", "how": "UTC + original tz; expand recurrence in local time.", "steps": ["timezone"]},
            {"requirement": "Fast availability/reads", "how": "Busy-interval index + caching.", "steps": ["freebusy", "scale"]},
            {"requirement": "Consistent propagation", "how": "Organizer-authoritative events + invite/sync paths.", "steps": ["invites"]},
            {"requirement": "Scale to billions", "how": "Calendar sharding + rebuildable derived state.", "steps": ["scale"]},
            {"requirement": "Reliable reminders", "how": "Time-ordered scheduler, deduped, burst-tolerant.", "steps": ["reminders", "scale"]},
        ],
    },

    "interviewScript": [
        {"phase": "Scope & requirements", "time": "first 5 min",
         "say": ["Confirm recurring events, free/busy, invites, reminders, sync.",
                 "Flag timezone/DST correctness as the hidden hard requirement.",
                 "Note recurring events can't be stored as instances."]},
        {"phase": "High-level design", "time": "next 10 min",
         "say": ["Store recurrence as rules; expand on read with overrides.",
                 "UTC + original tz; expand in local time for DST.",
                 "Busy-interval index for free/busy."]},
        {"phase": "Deep dive", "time": "next 15 min",
         "say": ["DST edge cases and local-time expansion.",
                 "Invite fanout + RSVP propagation.",
                 "Reminders (time-ordered, deduped) + delta sync; sharding + bursts."]},
        {"phase": "Wrap-up", "time": "final 5 min",
         "say": ["Map requirements to mechanisms.",
                 "Tradeoffs: expand-on-read vs cache, override complexity, reminder bursts.",
                 "Mention scheduling assistants and cross-provider interop as extensions."]},
    ],

    "levelVariants": [
        {"level": "Junior", "expectations": ["Stores events and expands recurrence.", "Sends reminders/invites.", "May mishandle DST and free/busy at scale."]},
        {"level": "Senior", "expectations": ["Rule storage + on-read expansion + overrides.", "UTC + local-time DST-correct expansion.", "Busy-interval index + invite propagation."]},
        {"level": "Staff", "expectations": ["Reasons about DST edge cases precisely.", "Designs busy-index rebuildability and reminder-burst handling.", "Handles edit-this-vs-series and cross-provider interop."]},
    ],

    "followUps": [
        "How do you handle the spring-forward gap (a 2:30am recurring event that doesn't exist that day)?",
        "How do you model 'this and following events' edits to a recurring series?",
        "How do you share free/busy across organizations without leaking event details?",
        "How do you fire millions of 9am reminders without a thundering herd?",
        "How would you interoperate with external calendars (CalDAV/iCalendar)?",
    ],
}

if __name__ == "__main__":
    out = os.path.join(HERE, "interview.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"WROTE {out}: {os.path.getsize(out)} bytes, {len(data['steps'])} steps")
