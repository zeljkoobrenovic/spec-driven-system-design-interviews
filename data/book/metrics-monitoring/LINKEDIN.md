Today's Spec-Driven System Design Interview: Metrics & Monitoring - System Design.

A monitoring platform is not just charts over numbers. It is a write-heavy data system where the hard part is keeping the system useful when every service, label, histogram bucket, dashboard, and alert rule is competing for budget.

This walkthrough starts with the deliberately bad baseline: one row per metric sample in a relational table. At 10M stored samples/sec, that becomes about 0.86T points/day before indexes, replication, and retention. From there, the design moves into an ingestion buffer with explicit acceptance semantics, compressed time-series chunks, hot/cold retention tiers, push vs pull collection, cardinality limits, query admission control, durable alert state, notification retries, and sharding by series.

The practical lesson: cardinality control and alert state are not advanced extras. They are requirements. A single unbounded label can break the index; an alert evaluator that forgets pending/firing state can wake people unnecessarily or miss a real incident.

The technology choices make the trade-offs concrete: Prometheus-compatible TSDBs, Thanos/Mimir/Cortex/M3DB, Kafka/Pulsar/Kinesis/Pub/Sub ingestion buffers, Grafana, managed Prometheus, object storage, caches, and cloud alerting. Managed services can remove shard-ring and compaction operations, but not the need to reason about budgets, query limits, missing data, and paging semantics.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#metrics-monitoring

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Observability
