Today's Spec-Driven System Design Interview: Order Management System (OMS).

The hard part of OMS is preserving invariants while inventory, payment, fulfillment, carriers, and notifications fail independently.

This walkthrough starts with the tempting baseline: one synchronous transaction. It breaks once payment, inventory, and warehouse systems have separate stores. The design then builds the real backbone: a durable lifecycle state machine with line-level state, inventory reservations, saga compensation, provider idempotency keys, and reconciliation for ambiguous payment or WMS steps.

The useful lesson: reliability comes from explicit state. "Never charge without stock" becomes reserve first, authorize with a stable idempotency key, capture when the package is packed but before carrier handoff, then publish committed transitions through a transactional outbox. Cancellations and returns are line-level compensation flows.

The technology choices stay practical: PostgreSQL, Aurora, DynamoDB, Spanner, or distributed SQL for order state; Temporal, Step Functions, queues, or managed schedulers for orchestration; Kafka, RabbitMQ, SQS, EventBridge, Pub/Sub, or Event Hubs once the outbox boundary is clear.

The interview is good practice because it forces the trade-offs interviewers care about: consistency without distributed transactions, idempotency, async fulfillment, partial shipment, refund safety, auditability, and operational repair.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#order-management

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #Ecommerce
