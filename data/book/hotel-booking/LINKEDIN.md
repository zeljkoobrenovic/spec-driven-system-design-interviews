Today's Spec-Driven System Design Interview: Hotel / Airbnb Booking — System Design.

The interesting part of booking is not search. It is the exact moment two guests want the same nights.

This walkthrough starts with the tempting design: read availability, then write a booking. That baseline is useful because it fails in the precise way interviewers care about: a race can let both requests see the room as free. From there, the design becomes sharper: model availability per unit per night, reserve the full date range atomically, use short TTL holds during checkout, then confirm through an idempotent payment-aware state machine.

It also separates the two worlds that get confused in many booking designs. Browse can be fast and slightly stale: search index, availability cache, projector, and durable outbox/CDC stream. Booking must be strongly consistent: conditional writes, affected-row-count checks, hold ownership, expiry reaping, and reconciliation for payment ambiguity.

Modern technology choices are visible, but they do not replace the core invariant. You might use Aurora, Spanner, DynamoDB, or PostgreSQL for the truth store; OpenSearch and Redis/Valkey for browse; Kafka/Kinesis/Pub/Sub for freshness; Temporal or Step Functions for confirm/cancel workflows; and managed observability for conflict rate, projector lag, stale cache age, and stuck sagas. The design still lives or dies on "reserve every night or none."

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#hotel-booking

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #DistributedSystems
