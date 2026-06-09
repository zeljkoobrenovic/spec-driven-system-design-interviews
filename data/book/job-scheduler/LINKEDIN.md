Today's Spec-Driven System Design Interview: Distributed Job Scheduler / Cron — System Design.

A scheduler looks simple until you ask what happens at 02:00, after a node pause, or when 200k jobs all want to fire at the top of the hour.

This walkthrough makes one distinction explicit: exactly-once triggering is not the same as exactly-once execution.

The scheduler can create one run per scheduled fire by storing durable schedules, indexing `next_fire_at`, using leader leases with fencing tokens, and writing fire markers plus outbox rows in one transaction. Workers still execute at least once, so the design needs run leases, retries, dead-lettering, and idempotency keys at the target system.

That is the useful interview lesson: the hard part is not "run cron on more machines." It is defining the state transitions and ownership boundaries so crashes, failover, retries, updates, cancellations, and top-of-hour bursts all have predictable behavior.

The case also shows where modern platform choices change the build-vs-buy discussion. EventBridge Scheduler, Cloud Scheduler, Logic Apps, Step Functions, SQS, Pub/Sub, Service Bus, DynamoDB, Spanner, Aurora, Fargate, Lambda, Cloud Run, and Kubernetes can remove pieces of the custom stack. But they do not remove the need to reason about misfire policy, overlap policy, fire-key deduplication, queue visibility, retry limits, and operational recovery.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#job-scheduler

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #DistributedSystems
