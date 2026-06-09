Today's Spec-Driven System Design Interview: Nearby Search (Yelp / Maps) — System Design.

Nearby search looks like "sort by distance" until you have 100M places, dense downtown cells, lunch-time traffic spikes, and updates that must appear within minutes.

This walkthrough starts with lat/lng scans and distance checks. That baseline fails immediately at scale, so the interview moves step by step into geohash/S2/H3-style cell covering, boundary handling, exact-distance trimming, adaptive precision for dense vs. sparse regions, cheap metadata filters, bounded ranking, and cache-backed hydration.

The useful lesson is that a geo index is only the recall layer. The design still has to bound fanout, cap candidates, dedupe mixed-precision cells, filter by exact radius, keep ETA/ML ranking out of the p99 hot path, and make index updates replayable through outbox or CDC events, idempotent versions, dead-letter handling, backfills, and shadow rebuilds.

Modern implementation choices make the trade-offs concrete: S2 or H3 over a KV store for control, PostGIS or OpenSearch for richer geo queries, DynamoDB, Bigtable, or Cosmos DB-style cell-prefix indexes for scale, Kafka, Kinesis, Pub/Sub, or Debezium for change streams, Redis or Valkey for hot place details, and managed routing APIs or OSRM/Valhalla when ETA is useful. The tools help, but they do not remove the need to defend radius caps, freshness lag, and bounded ranking.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#nearby-search

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #GeoSearch
