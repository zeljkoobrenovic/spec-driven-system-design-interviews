Today's Spec-Driven System Design Interview: Agentic Finance Platform — System Design.

The hard part of agentic finance is not extracting invoice fields. It is proving that an AI-assisted workflow cannot mutate the books or move money without controlled authority.

This walkthrough starts with the dangerous version: an agent reads an invoice, posts the journal entry, and pays it. Then it rebuilds around finance invariants: the ledger is ground truth, agents propose instead of mutate, deterministic stages handle intake/extract/match/propose, and maker-checker approval gates every ledger post and payment.

The useful lesson: autonomy needs boundaries. "Auto" can mean matched, recommended, routed, or batched for review. It must not mean authorized. A checker distinct from the maker approves irreversible side effects, with identity enforcing segregation of duties.

The technology choices make the trade-offs concrete: Textract, Document AI, Azure AI Document Intelligence, Tika, and OCR for intake; Temporal, Step Functions, or Workflows for durable execution; PostgreSQL, Aurora, CockroachDB, Spanner, or Azure SQL for proposal and idempotency state; an outbox plus callback dedupe for payments; and immutable WORM-backed audit records instead of hidden model reasoning.

The tools can change. The invariant does not: the model can help prepare the decision, but it must not become the unchecked authority for the ledger or the bank account.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#agentic-finance-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AgenticAI #FinTech
