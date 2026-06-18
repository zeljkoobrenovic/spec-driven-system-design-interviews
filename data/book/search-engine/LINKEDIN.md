Today's Spec-Driven System Design Interview: Web Search Engine - System Design.

Search is a reminder that "contains these words" is not the same problem as "answer 100K queries per second over 100B+ documents."

This walkthrough starts with the naive baseline: scan every document for the query terms. That is easy to explain and completely impossible at web scale. From there it moves one pressure point at a time: polite crawling, URL/content deduplication, inverted indexing, document partitioning, scatter-gather over replicas, top-k merging, ranking, caching, and continuous segment publishing.

The main lesson: web search is not one clever data structure. It is a chain of bounded decisions:

- move work from query time into indexing
- use posting lists instead of corpus scans
- make multi-term queries local inside each document shard
- keep scatter-gather inside deadlines
- publish fresh segments with rollback

The technology choices make this concrete. Lucene, OpenSearch, or Solr can give you mature postings, analyzers, skip data, and segment merges. Kafka, Kinesis, or Pub/Sub can carry crawl and freshness events. Spark, Flink, Dataflow, or EMR can build segments and compute link-graph scores. Redis, Valkey, Memcached, CloudFront, or Cloud CDN can absorb repeated queries and hot snippets.

Those tools help, but they do not remove the design work around shard count, top-k limits, cache hit-rate collapse, robots.txt politeness, and query p99.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#search-engine

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #Search
