Today's Spec-Driven System Design Interview: Ad-Click / Analytics Pipeline - System Design.

An analytics pipeline is easy to underestimate because version one sounds like "increment a counter." At ad-click scale, that counter becomes billing and replay infrastructure.

This walkthrough starts with hot counter rows and duplicate retries, then uses a thin collector that accepts events only after replication to a durable partitioned log. From there the design adds event-time windows, watermarks, bounded dedup, conversion attribution, immutable raw storage, batch recompute, and a query layer that separates provisional from settled windows.

The useful lesson: real-time metrics and correct metrics are different products.

The speed layer gives dashboards fresh clicks, impressions, CTR, and conversion signals within seconds. The batch layer rereads raw events, deduplicates fully, completes attribution windows, and publishes versioned billing-grade rows. The serving API switches by settlement marker, so "fresh" and "final" do not get mixed accidentally.

The technology choices make the trade-offs concrete: Kafka, Redpanda, Pulsar, Kinesis, Pub/Sub, and Event Hubs for ingestion; Flink, Spark, Dataflow, and Databricks for stream processing; Redis, Cassandra, DynamoDB, Bigtable, and Cosmos DB for state; S3, Cloud Storage, Blob Storage, HDFS, and Ceph for the raw lake; ClickHouse, BigQuery, Redshift, Synapse, and OpenSearch for rollups.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#analytics-pipeline

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #DataEngineering #Scalability
