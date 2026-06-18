Today's Spec-Driven System Design Interview: Distributed Lock Service — System Design.

A lock service looks tiny: acquire, renew, release.

It gets hard when holders pause, leaders fail, partitions split the fleet, or 1M leases renew frequently.

The walkthrough starts with a single database row, then evolves toward a fault-tolerant service: consensus-backed state, leases with TTL, ordered expiry, fencing tokens, idempotent retries, leader election, sharding, and controls for hot keys and renewal storms.

The core lesson: distributed locking is a three-part contract.

Consensus linearizes grants, so two replicas do not hand out the same key. Leases restore liveness when a holder dies. Fencing tokens make the protected action safe when an old holder wakes up late. If the resource does not reject stale epochs with an atomic compare-and-set, the lock is only advisory.

That makes it a strong interview case because it separates mutual exclusion, failure recovery, and safe side effects instead of treating "we have a lock" as the end of the design.

Modern technology choices make build-vs-buy concrete. etcd, Consul, ZooKeeper, Raft/Paxos groups, DynamoDB, Spanner, Redis/Valkey, managed queues, API gateways, KMS, and Kubernetes-style placement can remove pieces of infrastructure. They do not remove the fundamentals: quorum, expiry ordering, retry deduplication, shard migration, hot-key serialization, and resource-side fencing.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#lock-service

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #DistributedSystems #Infrastructure
