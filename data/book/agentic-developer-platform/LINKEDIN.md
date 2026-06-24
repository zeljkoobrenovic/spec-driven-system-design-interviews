Today's Spec-Driven System Design Interview: Agentic Developer Platform — System Design.

The hard part of agentic development is not "can an agent edit code?" It is whether a platform can let many agents work on repositories without turning repo access, CI credentials, and untrusted issue text into a blast radius.

This walkthrough treats the coding agent as a distributed systems problem. It starts with the naive single-agent, direct-commit version, then adds repo-context retrieval, a supervisor, leased task execution, ephemeral sandboxes, scoped credentials, draft PR gates, verification before proposing, and prompt-injection defenses.

The core lesson: autonomy needs a ceiling. In this design, the agent can open a draft PR after tests and lint pass in its sandbox. Merge and deploy stay behind a separate gate with branch protection, required CI checks, code owners, rollout policy, and durable evidence.

The technology choices make the trade-offs concrete. You can model the control plane with PostgreSQL, CockroachDB, Aurora, Spanner, or DynamoDB. You can run task history and retries with Temporal, Kafka, SQS, Step Functions, Pub/Sub, or Cloud Tasks. Sandboxes might use Firecracker, gVisor, Kubernetes, Fargate, or Cloud Run. Repo grounding may combine Tree-sitter, Zoekt, OpenSearch, Elasticsearch, pgvector, or managed vector/search services. Guardrails still need task-scoped tokens, allowlisted tools, and egress control.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#agentic-developer-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AgenticAI #DeveloperTools
