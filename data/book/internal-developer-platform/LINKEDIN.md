Today's Spec-Driven System Design Interview: Internal Developer Platform (IDP) — System Design.

An IDP is not a portal with a nicer homepage.

The design question: how do you let developers declare intent once, then turn that intent into safe, repeatable environments without recreating ticket-ops behind a UI?

This starts with tickets, shared scripts, and wiki runbooks, then adds CI/CD, Helm, a Backstage-style catalog, and the abstraction: a Score-style workload spec plus a platform orchestrator.

The lesson is separating what a service needs from how each environment fulfills it.

Developers ask for containers, a database, a queue, DNS, or a route. Platform engineers define resource definitions for dev, staging, and prod. The orchestrator matches the request, provisions through Terraform, OpenTofu, Crossplane, or a managed platform, injects bindings/secrets, and hands generated state to GitOps and rollout controllers.

Concrete trade-offs follow: portal vs. platform, GitOps vs. progressive delivery, namespace-per-team vs. vcluster/dedicated isolation, self-hosted Backstage vs. SaaS catalog, managed databases/queues vs. operating your own, and observability/security as defaults.

The final design is a five-plane platform: developer control plane, integration and delivery, resource plane, observability, and security. Useful practice for discussing developer experience without hiding the distributed systems underneath.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#internal-developer-platform

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #PlatformEngineering
