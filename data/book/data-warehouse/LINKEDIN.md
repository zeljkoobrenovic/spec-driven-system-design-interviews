Today's Spec-Driven System Design Interview: Data Warehouse / ETL Ingestion — System Design.

A data warehouse interview is not about naming a favorite database. It is about showing how analytical data stays correct after it leaves operational systems.

The walkthrough starts with a naive nightly script: transform rows, load one database, let analysts query it. That design fails in useful ways. Raw data is lost, retries can duplicate rows, source schema changes break jobs, and analytical scans compete with production traffic.

The design then becomes a platform: CDC, streams, and batch/API extracts land immutably in a raw lake; ELT transforms typed staging data into modeled tables; partitions publish atomically only after validation; schema changes are versioned; and BI queries hit columnar, partitioned marts with rollups and workload isolation.

The central lesson is reprocessability. Retained raw data + idempotent loads + committed snapshots mean fixing history is a controlled backfill, not a data-loss incident.

Modern choices make the trade-offs concrete: S3, Cloud Storage, or Azure Data Lake Storage for raw retention; Iceberg, Delta Lake, or Hudi for snapshots and evolution; dbt, Spark, or Flink for transforms; Redshift, BigQuery, Synapse, Trino, or ClickHouse for serving; Airflow, Dagster, or managed workflows for orchestration.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#data-warehouse

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #DataEngineering #SystemDesignInterview #SoftwareArchitecture #Scalability
