Today's Spec-Driven System Design Interview: Twitter / X Feed - System Design.

The hard part of a social feed is not storing posts. It is deciding where work happens: on write, on read, or in a careful hybrid.

This walkthrough starts with the simple version: assemble a home timeline by reading recent tweets from every followed account and merging them on demand. It is correct, but at hundreds of thousands of reads per second, correctness is not enough.

Then the design flips the cost: fanout-on-write pushes tweet ids into each follower's precomputed timeline, making reads fast enough for a p99 target under 200 ms. That works until one celebrity post becomes tens of millions of cache writes.

The final design uses the pattern real systems need: push for normal accounts, pull for high-follower accounts, merge on read, hydrate from cache, filter deletes, unfollows, mutes, and blocks, then rank with a hard timeout and chronological fallback.

It is a good interview because every step exposes a trade-off: latency vs. freshness, cache speed vs. rebuild complexity, async fanout vs. queue lag, ranking quality vs. p99 reliability.

Modern implementations can map those choices to Redis or Valkey for timelines, Cassandra, ScyllaDB, DynamoDB, or Bigtable for tweets and graph data, Kafka, SQS, Kinesis, or Pub/Sub for fanout, object storage plus CDN for media, and managed model endpoints for ranking. The fundamentals still decide the architecture.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#twitter-feed

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability
