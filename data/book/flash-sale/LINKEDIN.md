Today's Spec-Driven System Design Interview: Flash Sale — System Design.

A flash sale is not a "make the database faster" problem.

The important lesson is admission. If 10M buyers arrive for 10K units, the purchase core should never see 10M attempts. Most demand must be absorbed by static edge delivery, bot filtering, rate limits, and a virtual waiting room before it can touch scarce inventory.

The walkthrough starts with the naive stock-row decrement, shows why it melts under a synchronized spike, then adds CDN offload, edge admission, signed time-boxed tokens, an oversell-proof reservation counter, async order/payment workers, and reconciliation against a durable ledger.

The core trade-off is blunt: availability of the buy path is negotiable; the no-oversell guarantee is not. When the counter epoch is uncertain, Redis fails over, or reconciliation detects drift, the safe behavior is to pause admission or fail closed instead of selling inventory twice.

The technology choices make the fundamentals concrete. A managed CDN/WAF or waiting-room product can absorb the first wave. Redis Lua, DynamoDB conditional writes, Spanner, or Cosmos DB can implement decrement-if-positive. SQS, Pub/Sub, Service Bus, Kafka, or RabbitMQ can decouple reservation from order creation. Observability matters here: operators need token issue rate, queue depth, reservation success, payment failures, hold expiry, counter-vs-ledger drift, and kill switches before T0.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#flash-sale

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability
