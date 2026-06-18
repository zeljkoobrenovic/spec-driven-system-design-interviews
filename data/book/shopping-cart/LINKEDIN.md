Today's Spec-Driven System Design Interview: Shopping Cart & Order Management — System Design.

The hard part of a shopping cart is not adding an item. It is turning mutable cart intent into a correct order while pricing, inventory, payment, and fulfillment fail independently.

The walkthrough starts with the tempting baseline: an in-memory cart and one "buy" request. It works for one shopper, then breaks: carts vanish on restart, retries double-order, hot SKUs oversell, and money or stock can move with no durable record.

The design then separates the workloads. Carts move to a fast, sharded, TTL-backed store and favor availability. Checkout becomes the correctness boundary: freeze price, reserve inventory with TTL holds, write PENDING_PAYMENT before charging, use the order id as the payment idempotency key, compensate, reconcile webhooks, and publish through a transactional outbox.

Lesson: "fast cart" and "correct order" are different systems. Cart state can be disposable. Inventory must preserve available + reserved + sold = stock_on_hand. Payment and order state need idempotency, durable webhooks, legal transitions, and replayable events.

Practical choices: Redis, Valkey, Cassandra, ScyllaDB, or DynamoDB-style stores for carts; PostgreSQL, Aurora, or Spanner-style stores for order truth; Temporal or Step Functions for sagas; Kafka, SQS, Pub/Sub, or Service Bus for outbox delivery. Managed services reduce plumbing, not invariants.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#shopping-cart

Explore the catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #Ecommerce
