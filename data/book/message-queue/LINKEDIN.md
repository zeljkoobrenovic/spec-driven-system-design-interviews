Today's Spec-Driven System Design Interview: Message Queue — System Design.

A message queue is not a list with push and pop.

The design lesson is where state lives. Durable messaging separates immutable log data, consumer progress, per-message lease state, and failures that redeliver work.

The walkthrough starts with in-memory FIFO, then adds a partitioned append-only log, consumer groups and offsets, delivery semantics, queue-mode visibility timeouts and DLQs, replicated leaders, and scaling across brokers.

Core boundary: log mode and queue mode are related, but not interchangeable.

Log mode tracks a group position for ordered streams, replay, retention, and consumer groups. Queue mode tracks per-message ownership, timeout, retry count, and completion for competing workers and failed-job recovery. Mixing them is how designs mutate the log, lose replayability, or promise exactly-once delivery they cannot provide.

Modern choices make the trade-offs concrete: Kafka, Redpanda, Pulsar, or Kinesis for partitioned logs; RabbitMQ, NATS JetStream, SQS, Pub/Sub, or Service Bus for leases and DLQs; KRaft, ZooKeeper, or etcd for leadership and fencing; broker-native idempotent producers or durable KV stores for dedup windows.

Managed services can remove broker operations. They do not remove the fundamentals: partitioning, offsets, replication, idempotency, backpressure, lag and hot-partition observability, and the scope of ordering.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#message-queue

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #DistributedSystems #Scalability
