Today's Spec-Driven System Design Interview: Live Comments / Presence — System Design.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#live-comments

The hard part of live comments is not writing comments. It is deciding what not to deliver.

A naive design starts with everyone polling a comments table. At 5M viewers polling every 2 seconds, that is roughly 2.5M reads/sec before writes, moderation, reactions, or fanout. And if 5K comments/sec were sent to every viewer, the system would face an impossible 25B deliveries/sec.

This walkthrough turns that failure into the design lesson.

It moves from polling to a moderated ingest path, a per-room broadcast bus, WebSocket gateways, hierarchical fanout, sampling, approximate presence, reaction aggregation, and explicit backpressure. The key trade-off is practical: live feeds are best-effort. Users need a lively, safe, readable stream, not every single message.

Modern implementations can map this pattern to a managed stream or pub/sub bus, horizontally scaled gateway fleets, moderation services, quarantine queues, bounded client buffers, room registries with TTLs, and approximate counting techniques for presence. The interview keeps those choices tied to fundamentals: isolate the hot path, reduce fanout cost, cap unreadable volume, and degrade deliberately under load.

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #RealTimeSystems
