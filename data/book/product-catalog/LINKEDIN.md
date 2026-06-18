Today's Spec-Driven System Design Interview: Amazon Product Catalog — System Design.

The hard part of a product catalog is not storing products. It is serving search and facets at huge read volume while price and inventory keep changing underneath.

The walkthrough starts with a normalized products table. It works for a small store, then fails at hundreds of millions of products and read-heavy traffic. SQL LIKE, joins per page, and facet aggregation are the wrong shape for < 200 ms p99.

The design then splits reads from writes. Catalog owns normalized writes; a change stream projects updates into a denormalized read model and a search/facet index. Search ranks and filters in the index, then hydrates result cards from the read model. Product detail becomes one render-ready lookup.

The useful lesson: consistency is not one setting. Catalog descriptions can be seconds stale. Price and availability cannot be trusted from an old projection. Browse can show projected display values; detail, cart, and checkout must refresh live price and stock from the owner services.

Practical choices: PostgreSQL, Aurora, DynamoDB, or Spanner for catalog truth; Elasticsearch, OpenSearch, Solr, Lucene, or Vespa for search; Redis, Valkey, Bigtable, or ScyllaDB for read models; Kafka, Pulsar, Kinesis, Pub/Sub, or Debezium for projections. Managed services help, but the boundary stays: browse is projected, purchase decisions are authoritative.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#product-catalog

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #Ecommerce
