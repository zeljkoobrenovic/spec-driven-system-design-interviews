Today's Spec-Driven System Design Interview: Data Warehouse / ETL Ingestion.

The useful lesson: a warehouse is not just a place to run analytical SQL. It is a reliability system for replay, correctness, and controlled change.

The interview starts with the tempting baseline: one nightly script transforms source data and loads a database analysts can query. It works until the first transform bug, late CDC event, schema change, or dashboard scan that competes with production traffic.

Then the design moves through the core trade-offs:

Land immutable raw data and transform later.
Use idempotent partitions, validation, and atomic snapshot commits.
Version schemas and track lineage so source changes become contracts.
Serve modeled tables with partition pruning, columnar storage, compaction, and workload isolation.
Run backfills below fresh-data priority.

That is the interview value: ELT, CDC offsets, watermarks, schema evolution, quality gates, query serving, and backfills are not separate topics. They are one design.

Modern tools can shorten the build, but they do not remove the questions. You might use S3, Cloud Storage, or Azure Data Lake Storage; Debezium, Kafka Connect, DMS, Datastream, or Data Factory; Iceberg, Delta Lake, Hudi, BigQuery, Fabric, or Databricks; Airflow, Dagster, Prefect, or Composer.

The key is choosing where the platform gives you replay, atomic publish, governance, and operable backfills.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#data-warehouse

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #DataEngineering #SoftwareArchitecture #Scalability
