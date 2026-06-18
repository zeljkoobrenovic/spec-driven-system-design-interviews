Today's Spec-Driven System Design Interview: ML Feature Store — System Design.

The hard part of a feature store is not storing values. It is making one definition behave consistently in training and serving: multi-TB history on one side, p99 under 10 ms on the other.

This walkthrough starts with ad hoc SQL for training and serving code. It fails when "user_7d_clicks" drifts, point-in-time joins leak future data, and train/serve skew degrades production.

The design adds a versioned registry, dual offline and online stores, point-in-time training jobs, online serving, batch and stream materialization, freshness SLOs, monitoring, lineage, access control, and rebuildable state.

Core lesson: this is a consistency system for ML.

Offline history makes training reproducible; online state is derived for fast multi-gets. Models pin versions. Training jobs publish manifests with watermarks. Serving returns version, freshness, missing, and stale metadata so fallback follows policy instead of guesswork.

Technology trade-offs: Feast, Hopsworks, or custom registry vs managed feature stores; Iceberg, Delta Lake, or warehouses for history; Redis, Cassandra, DynamoDB, Bigtable, or Cosmos DB for online values; Kafka, Flink, Kinesis, or Pub/Sub for freshness; Airflow, Dagster, Temporal, or cloud workflows for backfills.

Managed services reduce control-plane code, but not the need to reason about leakage, skew, versioning, freshness, and governance.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#feature-store

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #MLOps #AIEngineering
