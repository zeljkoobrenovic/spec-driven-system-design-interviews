Today's Spec-Driven System Design Interview: Calendar Scheduling - System Design.

A calendar looks like CRUD until recurrence, timezones, and fanout meet real users.

This walkthrough starts with the tempting naive model: store every occurrence as a row with local-string times. It fails quickly. Infinite recurring events cannot be pre-created, "this instance" edits need stable recurrence IDs, and a daily 9am meeting must stay 9am local when DST changes.

The design then moves toward the production shape: store RRULEs and exceptions authoritatively, expand only the queried window in the event timezone, keep a per-calendar busy-interval index for free/busy, and commit event changes with an outbox so projectors can rebuild busy state, reminders, invite fanout, cache invalidation, and device sync.

It is a good interview because the trade-offs are not cosmetic. You have to explain what is source of truth, what is derived and replayable, where eventual consistency is acceptable, and how privacy checks happen before free/busy intervals leave the system.

Modern implementation choices make the discussion sharper: managed databases for calendar-sharded event rows and conditional writes, streams or queues for the outbox/projectors, delayed queues or workflow engines for reminders, Redis-like caches for hot views, and gateways/identity services for auth and rate limits. They reduce infrastructure work, but they do not remove the domain semantics.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#calendar

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability
