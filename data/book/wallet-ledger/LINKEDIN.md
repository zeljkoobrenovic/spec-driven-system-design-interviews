Today's Spec-Driven System Design Interview: Wallet / Ledger — System Design.

The hard part of a wallet is not "subtract here, add there." It is proving, after retries, crashes, concurrent debits, provider delays, and shard boundaries, that the system never lost or invented a cent.

This interview walks through that progression deliberately: start with the tempting single balance column, then replace it with an immutable double-entry journal, committed idempotency records, materialized balances, concurrency control, a transactional outbox, reconciliation, and explicit settlement states for external rails.

The useful lesson is that "correctness over availability" changes the architecture. Fast balance reads are allowed, but the journal stays authoritative. Retries are expected, but a reused idempotency key cannot double-post. Events can be delivered asynchronously, but the outbox row is committed with the ledger write. Cross-shard transfers can use a saga, but clients must see a clear pending state instead of spendable money on both sides.

Modern technology helps, but it does not remove the accounting model. PostgreSQL, Aurora, Spanner, DynamoDB, Temporal, Kafka, S3/Cloud Storage, KMS, and managed observability tools all show up as choices around the core invariant: every posting balances, every derived view can be rebuilt, and every external settlement can be reconciled.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#wallet-ledger

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #FinTech #DistributedSystems
