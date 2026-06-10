Today's Spec-Driven System Design Interview: URL Shortener — System Design.

A URL shortener is a small product with a large systems lesson: redirects are the product.

The walkthrough starts with a client, one app server, and a database, then keeps asking the interview question that matters: what breaks next?

That progression exposes the core trade-offs behind read-heavy systems: stateless app servers, cache-aside redirects, hot-set protection, dedicated ID generation, shard ownership, edge execution, async analytics, and multi-region failover.

The numbers make the design concrete: 1,000 creates/sec, 100,000 redirects/sec, a 100:1 read/write ratio, and about 75 TB of raw mapping data over five years before indexes, replicas, and backups. At that point, "just add a database" is not enough.

This case also connects fundamentals to modern implementation choices. A managed CDN or programmable edge can remove origin round trips for hot redirects. DynamoDB, Spanner, Cassandra, ScyllaDB, PostgreSQL, or MySQL each imply different shard and consistency work. Kafka, Kinesis, Pub/Sub, SQS, or Event Hubs can move click analytics and purge jobs off the redirect path. Generated short codes can use region-scoped ranges or Snowflake-style IDs, while vanity aliases still need a globally consistent reservation path.

That is why this is a useful interview problem: every shortcut has a boundary, and every boundary forces a product decision.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#url-shortener

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #DistributedSystems
