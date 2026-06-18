Today's Spec-Driven System Design Interview: Fraud / Abuse Detection — System Design.

Fraud detection reminds us that "add an ML model" is not a system design.

The hard part is the decision loop around the model: a risk API that answers inline in tens of milliseconds, rules that can stop known-bad behavior immediately, fresh velocity features for "this user/device/IP/card recently...", and graph-derived signals that catch coordinated abuse without doing live graph traversal on the checkout path.

This walkthrough builds that design step by step: start with static rules, add rules + ML scoring, stream events into an online feature store, materialize entity-graph features, split decisions into allow/block/challenge/review, then close the loop with labels, retraining, point-in-time feature snapshots, and versioned audit records.

It is a useful interview case because every choice has a business trade-off. Blocking too aggressively creates false positives. Reviewing too much overwhelms analysts. Failing open on a model outage may be fine for a low-value action and unacceptable for a high-value payment. The design has to make those policies explicit.

Modern implementations can use managed gateways, Kafka/Kinesis/Pub/Sub-style streams, Flink/Dataflow-style aggregation, Redis or durable KV feature stores, managed model serving, workflow engines, and object-storage retention tiers. The fundamentals still decide how those pieces fit together.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#fraud-detection

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #MachineLearning
