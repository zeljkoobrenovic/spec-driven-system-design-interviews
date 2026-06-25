Today's Spec-Driven System Design Interview: Agentic Support Platform - System Design.

The hard part of AI support is not answering questions. It is deciding when an agent can safely change a customer's money, order, or account live.

This walkthrough turns the familiar dead-end FAQ bot into a production support agent: policy and account grounding, a real-time turn loop, an in-loop action gate, delegated authority, idempotent transactions, human approval for risky actions, context-rich escalation, and audit.

The core lesson: support automation needs authority boundaries, not just better replies.

A customer message is data, not permission. The agent can propose a refund, cancellation, or reschedule, but a deterministic gate decides whether to answer, act, ask for approval, or escalate. Low-risk reversible actions can auto-execute. High-risk or hard-to-reverse actions pause. Provider-scoped idempotency prevents double refunds; ambiguous outcomes go through reconciliation or manual repair.

The technology choices make the trade-offs concrete: contact-center platforms or WebSocket edges; API gateways and WAFs; relational, KV, or wide-column stores; hybrid search; managed model APIs or self-hosted inference; OPA, Cedar, or managed authorization; Temporal, Step Functions, queues, and outboxes.

Managed services help, but they do not replace scoped authority, reversibility rules, idempotency, auditability, or the in-loop gate.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#agentic-support-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AIEngineering #AgenticAI
