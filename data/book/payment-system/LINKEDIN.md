Today's Spec-Driven System Design Interview: Payment System.

The hardest part of designing payments is not calling a PSP. It is making every retry, timeout, webhook, refund, ledger entry, reconciliation break, and payout converge on the same money truth.

This walkthrough starts with the naive synchronous charge path, then deliberately adds the pieces that real payment systems need: idempotency keys, an immutable double-entry ledger, async capture, webhook dedupe, reconciliation against PSP settlement files, payout state machines, balance read models, and finally ledger sharding.

The lesson is that "exactly once" in payments is not a magic queue setting. It is an end-to-end discipline:

- claim idempotency before doing work
- store immutable financial facts
- treat PSP timeouts as in-doubt states
- make inbound events replayable
- reconcile against an external source of truth
- reserve funds in the ledger before moving money out

The interview also connects those fundamentals to modern implementation choices: managed API edges and WAFs, durable workflow engines such as Step Functions or Temporal, strongly consistent SQL or distributed SQL for the ledger, queues and transactional outboxes for capture, durable webhook inboxes, batch workflows for reconciliation, and stream-backed read models for high-volume balance reads.

The tools can change. The invariants do not.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#payment-system

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #FinTech
