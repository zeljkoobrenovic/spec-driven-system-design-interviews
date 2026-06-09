Today's Spec-Driven System Design Interview: Spotify — Audio Streaming — System Design.

The hard part of Spotify is not storing audio. It is fast starts, edge delivery at massive concurrency, rights enforcement, and turning plays into recommendation and royalty data.

This walkthrough starts with the naive version: stream one big file through the app server. It is easy to explain, but it breaks on latency, bandwidth, and adaptation.

Then it adds the pieces real audio platforms need: bitrate ladders, immutable segments, CDN delivery, signed manifests, DRM licenses, catalog/search split, ID-based playlists, offline entitlement revalidation, play-event streams, recommendations, fraud filtering, and an auditable royalty ledger.

Useful lesson: keep the hot media path separate from the control plane and money/data paths. Segments come from CDN caches. Entitlements and manifests are critical-path. Library sync, recs, fraud, and royalties have different correctness and latency needs.

Technology choices become concrete: object storage + CDN, KMS/Vault signing, PostgreSQL/Spanner/DynamoDB/Cassandra/Redis for state, OpenSearch for discovery, Kafka/Kinesis/Pub/Sub/Event Hubs for events, and managed ML or feature stores for recommendations.

The products are prompts, not a checklist. The durable question is: what state is authoritative, what is rebuildable, and what must never depend on avoidable origin work?

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#spotify

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #Streaming
