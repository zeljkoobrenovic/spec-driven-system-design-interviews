Today's Spec-Driven System Design Interview: Logging Platform - System Design.

A logging platform looks simple until one boundary gets tested: when is a log accepted?

If that answer is vague, so are burst shedding, sampling, cold retention, and incident replay.

Start naive: every service writes to one store and search scans everything. At tens of TB per day, that fails. The design adds agents, collectors, auth, quotas, edge redaction, and a partitioned buffer that acks only after durable append.

The key contract: drop only before acceptance. After ack, buffer and archive raw; sampling affects hot-index inclusion and aggregation weights, not whether the event exists.

Then the interview builds the platform around that contract: structured parsing, time-bucketed index segments, hot/cold tiers, async cold query jobs, stream-based alerts, lifecycle rules, and signals like consumer lag, index lag, dead-letter volume, cold-query cost, and alert evaluation lag.

Modern choices sharpen the trade-offs: Fluent Bit, OpenTelemetry Collector, Vector, or Filebeat; Kafka, Pulsar, Redpanda, Kinesis, Pub/Sub, or Event Hubs; Flink, Kafka Streams, Spark, or Dataflow; OpenSearch, Elasticsearch, Loki, ClickHouse, CloudWatch, BigQuery, or Azure Data Explorer; and S3, Cloud Storage, Blob Storage, MinIO, or Ceph.

The useful lesson: logs are mostly written and never read, but when they are needed, something is often already broken.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#logging-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #DataEngineering #Observability
