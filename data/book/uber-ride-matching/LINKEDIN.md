Today's Spec-Driven System Design Interview: Uber — Ride Matching System Design.

Ride matching looks like a nearest-driver query until you put it under city-scale load.

The walkthrough starts with the simplest design: a rider requests a trip, the service scans drivers, and it picks the closest one. That baseline fails because millions of drivers ping every few seconds, requests spike by city, "nearby" must be fresh, and one driver cannot be claimed by two riders.

The design then hardens one bottleneck at a time: authenticated pings enter a partitioned stream; latest-location storage and the geo-cell index update asynchronously; matching queries neighboring cells; dispatch uses short-lived offers; and acceptance uses idempotency, conditional writes, and a live driver lease. Dense markets can batch assignments for a better global fit, while sparse markets stay effectively greedy.

The central lesson: a geo index makes lookup fast, but correctness comes from offer expiry, atomic driver claims, trip state transitions, freshness TTLs, and observability for lag, latency, acceptance rate, and claim conflicts.

Modern choices make the trade-offs concrete: Kafka, Pulsar, Kinesis, or Pub/Sub for streams; Redis, Cassandra, DynamoDB, or Bigtable for locations and TTL-backed geo cells; Kubernetes, EKS, GKE, or AKS for matching fleets; PostgreSQL, Spanner, DynamoDB, or Cosmos DB for guarded trip and claim state; Flink or Dataflow for surge windows.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#uber

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #DistributedSystems
