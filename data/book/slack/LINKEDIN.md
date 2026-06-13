Today's Spec-Driven System Design Interview: Slack / Discord — System Design.

Designing team chat is not just "add WebSockets to chat."

The hard part is making every message permission-correct, durable, ordered, searchable, and still fast enough to feel real time.

This walkthrough starts with the deliberately naive version: one shared channel, polling, no permissions. Then it adds the pieces that make Slack/Discord-style systems interesting: workspaces, channels, membership checks,
WebSocket gateways, durable per-channel history, unread cursors, permission-scoped search, presence, typing, and fanout queues for large channels.

The central lesson: persist first, fan out second.

Once the message is durable and sequenced, live delivery becomes an optimization. Online users get pushed updates through gateways. Offline users catch up from history. Workers can retry safely. Clients can deduplicate.
Search can index asynchronously. Large channels can be chunked, queued, rate-limited, or degraded to pull mode without losing the source of truth.

The scale signals make the trade-offs concrete: ~10M concurrent sockets, ~50K messages/sec, and ~1-2M pushes/sec when channel fanout is included.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#slack

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability
