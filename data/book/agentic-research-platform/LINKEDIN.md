Today's Spec-Driven System Design Interview: Agentic Research Platform — System Design.

The hard part of an agentic research platform is not just better reasoning. It is drawing a clean boundary between "the model can propose" and "the system may touch the physical world."

This case walks through that boundary step by step: literature-grounded hypothesis generation, structured protocol drafting, deterministic validation, human authorization for wet-lab work, durable execution with idempotency, and provenance for every claim and result.

The useful interview lesson is that autonomy is not a single switch. It is a set of scoped capabilities, each with an audit trail, policy gate, and failure mode.

The technology trade-offs are deliberately modern. You can discuss hybrid retrieval over primary literature with OpenSearch, Vespa, Qdrant, Weaviate, or managed vector search. You can compare vLLM/SGLang/LiteLLM with Bedrock, Vertex AI, or Azure OpenAI for design passes. You can use OPA, Cedar, schema validators, Temporal, Step Functions, Postgres, DynamoDB, object storage, and append-only audit streams.

But none of those replace the core design rule: the LLM drafts, deterministic systems validate, and accountable humans authorize physical experiments.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#agentic-research-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AIEngineering
