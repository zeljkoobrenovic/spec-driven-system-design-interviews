Today's Spec-Driven System Design Interview: Agentic Sales Platform — System Design.

The hard part of agentic sales is not writing a personalized email. It is deciding when the system is allowed to send one.

This interview starts with the tempting demo: an agent drafts outreach and blasts from one domain. That fails because deliverability is the scarce resource. A burned domain, ignored opt-out, weak enrichment hit, or misrouted reply can damage the whole platform.

The walkthrough turns that failure into a production design: CRM as system of record, waterfall enrichment with provenance, immutable drafts, approve-before-send, a global identity-resolved suppression list, and a deterministic gate that re-checks compliance at send time.

The systems lesson: the send queue is a policy boundary, not just a buffer. Approved drafts wait behind reputation-aware scheduling: warmed inboxes, per-inbox caps, bounce and complaint thresholds, domain rotation, webhook dedupe, retries, and audit events.

The technology choices make the trade-offs concrete: Temporal or managed workflows for orchestration; Redis, DynamoDB, or ElastiCache for hot suppression lookups; SQS, Pub/Sub, or Service Bus for durable queues; Bedrock, Vertex AI, or Azure OpenAI for model routing and guardrails; SES or SendGrid for feedback loops. None of those replace the architecture rule: keep untrusted enrichment and generated text away from privileged send authority.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#agentic-sales-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AIEngineering
