Today's Spec-Driven System Design Interview: Google Maps Routing — System Design.

Maps routing looks like shortest path until the graph is continental, answers need milliseconds, tiles load globally, and traffic changes every few minutes.

This walkthrough starts with Dijkstra or A* over the road graph per request. That works for a city, but breaks for cross-country routes because each query re-explores too much of the graph.

The design then adds the production pieces: a directed weighted road graph, contraction-hierarchy preprocessing, shortcut unpacking back into real road geometry, immutable map tiles through a CDN, GPS probe aggregation into edge speeds, region partitioning, and versioned graph/index publishing.

The core lesson is cadence separation. The base graph changes slowly, traffic changes in short windows, closures need fast overlays, and tiles are mostly static. A good design pins compatible graph/index versions, layers live weights and restrictions at route time, and falls back to historical speeds when probes are stale.

Modern choices make the trade-offs concrete: OSRM, Valhalla, GraphHopper, or managed Routes APIs for routing; S3 or Cloud Storage plus CloudFront, Cloud CDN, or Azure CDN for tiles; Kafka, Kinesis, Pub/Sub, Flink, or Dataflow for probes; Redis, Valkey, DynamoDB, Bigtable, or Cassandra-style stores for edge speeds; and workflow/batch systems for route regression, canarying, and rollback.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#maps-routing

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #GeoSystems
