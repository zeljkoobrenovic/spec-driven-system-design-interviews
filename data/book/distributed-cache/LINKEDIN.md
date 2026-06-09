Today's Spec-Driven System Design Interview: Distributed Cache — System Design.

A distributed cache is not just "Redis in front of the database."

The hard part is how misses, evictions, hot keys, failover, and rewarming push load back to the source of truth.

The walkthrough moves from an in-process map to cache-aside reads, a shared cache tier, consistent hashing, eviction/admission, write invalidation, hot-key replication, single-flight, warm replicas, failover, and backpressure.

Core lesson: the database remains authoritative, but cache behavior decides whether the database survives.

At 1M+ reads/sec, even a 95% hit rate leaves 50k DB reads/sec. A failed node can turn one warm shard into a cold miss wave. A popular key can overload one cache node even when the hash ring is balanced. A synchronized TTL can make thousands of callers refresh the same value at once.

Technology choices make the trade-offs concrete. Memcached is lean for plain key-value caching. Redis, Valkey, Dragonfly, and KeyDB add richer operations and replication. Caffeine, Ristretto, and short-TTL L1 caches can protect ultra-hot keys but duplicate state. ElastiCache, MemoryDB, Memorystore, and Azure Cache for Redis reduce operational ownership.

Managed services help, but they do not remove the fundamentals: key ownership, eviction, invalidation, TTL jitter, backfill budgets, replica-lag alerts, stale-serve rules, and the response when DB fallback exceeds budget.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#distributed-cache

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #DistributedSystems
