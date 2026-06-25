Today's Spec-Driven System Design Interview: Agentic HR Platform — System Design.

The hard part of agentic HR is not ranking resumes. It is proving that a model recommendation cannot become an unchecked hiring decision.

The walkthrough starts with the tempting demo: an agent screens candidates, answers employee questions, and executes HRIS actions. Then it rebuilds around HR's real constraints: effective-dated, jurisdiction-tagged policy; retrieval scoped to the requester's identity; durable onboarding/offboarding workflows; and a human gate for every adverse hiring outcome.

The key lesson is simple but easy to miss: agents recommend, humans decide. A screening agent can score job-related evidence against a versioned rubric, while prohibited signals and proxies stay outside the feature allowlist. A reviewer sees the evidence, records a rationale, can override, and owns the decision. Adverse-impact monitoring, notices, appeals, and audit packets are part of the architecture.

Modern choices include API gateways and WAFs for admission control; pgvector, OpenSearch, Bedrock Knowledge Bases, Vertex AI, or Azure AI Search for policy retrieval; OPA, SpiceDB, Cognito, Entra ID, or cloud IAM for scoped authorization; SQS, Pub/Sub, Service Bus, Temporal, or Step Functions for queues and workflows; and WORM/object-lock storage for compliance evidence.

In HR, autonomy needs explainable, auditable, legally defensible boundaries.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#agentic-hr-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AgenticAI #HRTech
