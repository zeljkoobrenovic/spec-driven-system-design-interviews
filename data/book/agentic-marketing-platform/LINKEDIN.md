Today's Spec-Driven System Design Interview: Agentic Marketing Platform - System Design.

The hard part is not getting an agent to generate campaign assets. The hard part is proving that nothing unsafe reaches a customer just because the automation got faster.

This walkthrough starts with the tempting demo: a brief goes in, copy and images come out, and the agent publishes across channels. Then it turns that demo into a production design: tenant-scoped brand kit grounding, approved DAM assets, deterministic negative-claim checks, model-judged brand voice review, C2PA provenance for synthetic media, and a human approval path for regulated or high-risk assets.

The optimization loop is where the design becomes interesting. A bandit can reallocate budget across live variants, but only across variants that are still approved, compliant, and consent-safe. Regenerated assets must go back through the gate. That one constraint changes the architecture from "AI content generator" into a marketing platform with auditability, policy, and recovery.

The technology choices are practical: managed model APIs or self-hosted inference; object/vector stores for the brand kit; rules engines or managed guardrails for checks; workflow engines and queues for provider throttling; streaming analytics and warehouses for attribution; identity, secrets, and audit storage around the whole thing. The interview keeps those as trade-offs, not magic boxes.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#agentic-marketing-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AgenticAI
