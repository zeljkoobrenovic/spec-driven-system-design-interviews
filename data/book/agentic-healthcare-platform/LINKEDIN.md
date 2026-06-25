Today's Spec-Driven System Design Interview: Agentic Healthcare Platform - System Design.

Healthcare agents should recommend, not act.

In this case, a clinician asks for dosing, differentials, guideline lookups, or chart summaries. A fluent model can sound right while being wrong, so the design wraps the agent in a safety pipeline: PHI-scoped patient-record retrieval, versioned guidelines and formularies, calibrated confidence, abstention when evidence is thin, deterministic allergy, interaction, contraindication, and dose checks, and clinician sign-off before the EHR is touched.

That progression is useful interview practice because every step exposes a trade-off: what belongs in the LLM loop, what must be deterministic, what gets audited, when to fail closed, and how to keep a human review queue from becoming the new bottleneck.

Technology choices stay concrete: FHIR/EHR integration with HAPI FHIR, HealthLake, Cloud Healthcare API, or Azure Health Data Services; hybrid keyword/vector retrieval with OpenSearch, pgvector, Vertex AI Search, or Azure AI Search; BAA/no-train model serving; Temporal or managed workflows; relational recommendation stores; and immutable audit bundles.

The lesson is not to make the model more confident. It is to design a system where the safe default is to abstain, hard clinical rules cannot be overridden by generated text, and a licensed clinician remains the accountable decision-maker.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#agentic-healthcare-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #HealthTech #AIEngineering
