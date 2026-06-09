Today's Spec-Driven System Design Interview: Ticketmaster: System Design.

Scarce inventory changes the design problem. When 1M+ users arrive for tens of thousands of seats, average throughput is not the first question. The first question is: how do we avoid selling the same seat twice while still being fair?

This walkthrough builds the system step by step: start with a naive buy-seat flow, separate seat-map reads from authoritative writes, add atomic seat locks and idempotency, model short TTL holds, enforce a virtual waiting room with signed admission tokens, then convert holds to orders through an explicit checkout state machine with payment reconciliation.

The useful lesson is that "no oversell" is not one component. It is an invariant carried through lock acquisition, seat status CAS, hold expiry, payment retries, outbox updates, audit logs, and reconciliation. The read model can be slightly stale. The reservation path cannot be vague.

Modern stacks can implement the same fundamentals in different ways: CDN/WAF/API gateway at the edge, Redis or Valkey-style locks with fencing, DynamoDB, Spanner, Aurora, or PostgreSQL for conditional inventory updates, managed queues or Kafka for waiting-room admission, and Step Functions or Temporal-style workflows for checkout and expiry. The interview keeps these as options because the trade-off matters more than the brand name.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#ticketmaster

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability
