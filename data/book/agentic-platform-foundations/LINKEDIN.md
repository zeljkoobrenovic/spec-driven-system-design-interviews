Today's Spec-Driven System Design Interview: Agentic Platform Foundations — System Design.

Designing an agentic platform is not just "let the model call tools." It is deciding where autonomy ends: identity, isolation, memory, budgets, policy, evals, and traces.

This walkthrough starts with a naive ReAct loop, then adds the pieces that make agents usable: sandboxes, credential brokering, durable execution logs, memory, MCP tool boundaries, delegated identity, guardrails, admission queues, hard token budgets, evals, and OTel traces.

The core lesson: the model may choose the next action, but the platform owns authority.

Agents should not read secrets, impersonate users, run untrusted code beside the orchestrator, spend without a terminating budget, or bypass evidence collection. The design keeps those boundaries explicit: delegated identity, idempotency keys, policy checks on every tool call, human review at high-risk edges, and trajectory traces.

The technology choices make the trade-offs concrete: Firecracker, gVisor, Kata, or managed containers for isolation; Vault, Keycloak, SPIFFE, OPA, Cedar, IAM, and KMS for identity and policy; Temporal, Step Functions, queues, Kafka, or Postgres logs for durable runs; Bedrock, Vertex AI, Azure OpenAI, vLLM, and prompt caching for inference economics.

Managed services help. They do not remove act-as tokens, no-bypass guardrails, hard budgets, evidence records, or eval gates.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#agentic-platform-foundations

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AIEngineering #AgenticAI
