Today's Spec-Driven System Design Interview: DoorDash — Food Delivery — System Design.

Food delivery looks simple until order state, payment, dispatch, and the live map disagree about what happened.

This walkthrough starts with one order row, first-available dispatch, and no live tracking. That baseline breaks fast: retries can double-create orders, restaurant rejection must unwind payment, courier assignment can race, 100K couriers may ping every few seconds, and tracking sessions can spike.

The design hardens each boundary: explicit order lifecycle, idempotent transitions, GPS ingest into a region-partitioned stream, geo index plus last-known cache, time-boxed courier offers with compare-and-set acceptance, and push tracking with ETA and access control.

The central lesson: the order store is the truth, but the live system is mostly derived state. Dispatch and tracking can be fast because derived stores are rebuildable; correctness comes from state transitions, offer leases, outbox events, and saga compensation for rejects, cancels, drops, and payment ambiguity.

Modern choices make the trade-offs concrete: PostgreSQL, Aurora, Spanner, or DynamoDB for order state; Kafka, Redpanda, Kinesis, or Pub/Sub for streams; Redis, PostGIS, OpenSearch, or DynamoDB for geo lookup; Temporal, Step Functions, or Workflows for timers and compensation; and realtime gateways or WebSocket fleets for fanout.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#food-delivery

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #DistributedSystems
