Today's Spec-Driven System Design Interview: Stripe-like Payment Gateway.

A payment gateway is a great interview because the hard part is not "call the bank API." The hard part is making every unsafe edge explicit: raw card data, retries, ambiguous PSP responses, webhooks, ledgers, and payouts.

This walkthrough starts with the intentionally naive design: the merchant server collects card data and sends it straight through to the acquirer. That baseline exposes the two failures the rest of the design must remove: broad PCI exposure and double charges on retry.

From there, the design builds the gateway one decision at a time:

tokenize card data in a narrow PCI vault,
persist idempotency keys with charge state,
model charges as a resumable state machine,
deliver signed webhooks at least once,
record every movement in a double-entry ledger,
scale around merchant-sharded consistency,
and handle PSP outages without re-sending ambiguous authorizations.

The technology choices are framed as trade-offs: managed KMS/HSM for vault key custody, durable SQL or distributed SQL for charge and ledger state, workflow engines for resumable orchestration, queues and DLQs for webhook retries, and routing layers for multi-acquirer resilience.

The lesson is demanding: in money systems, correctness beats availability. You can retry a request, replay an event, or reconcile a settlement line, but you cannot casually "eventually fix" a duplicate charge.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#payment-gateway

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #FinTech #Scalability
