Today's Spec-Driven System Design Interview: Reusable Design Patterns - Catalog.

Basics are not beginner material. They are the vocabulary that lets a system design conversation move from "add a database and a queue" to precise trade-offs: where state lives, how writes are ordered, what gets cached, how failures are retried, and which guarantees the design can actually defend.

This catalog collects 57 patterns used across the book's case studies, grouped by the problem they solve: scaling and data distribution, messaging and asynchrony, reliability and correctness, read/write optimization, specialized indexing, protection and fairness, identity, and edge integration.

That matters in interviews because patterns are not decorations. A work queue changes failure handling. A transactional outbox changes consistency boundaries. Idempotency keys change retry safety. Leases and fencing tokens change correctness. CDN caching, read models, sharding, search indexes, and sagas each solve a real pressure point while adding an operational cost.

The modern choices are just as important. You can self-host PostgreSQL, Kafka, Redis, Elasticsearch, Temporal, Keycloak, or Ceph. You can also reach for DynamoDB, Spanner, Cosmos DB, Pub/Sub, SQS, CloudFront, managed search, workflow services, and managed identity. The useful answer is not "which tool is best"; it is knowing which pattern you need, what the service removes, and which trade-off remains yours.

Try the interactive catalog:
https://system-design-interviews.com/book/interview.html#patterns

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #DistributedSystems
