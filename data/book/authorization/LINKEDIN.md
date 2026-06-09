Today's Spec-Driven System Design Interview: Authorization Service (RBAC / ABAC) — System Design.

Authorization is easy to underestimate because the API looks tiny: can subject S perform action A on object O?

The hard part: make that answer fast, explainable, and correct after a revoke.

This walkthrough moves from hardcoded role checks inside each app to a shared Check API where policy is evaluated consistently. RBAC is simple but coarse. ABAC handles attributes. ReBAC handles object sharing, group membership, folder inheritance, and "who can access this exact thing?" questions.

Checks sit on every request path, so the design needs SDK-side caching, a decision cache, and a bounded graph walk to hit sub-10ms p99 at 1M+ checks/sec. But caching creates the security problem: a stale allow after revoke is not a performance bug; it is an access leak. The interview makes consistency tokens, watermarks, and deny-by-default fallbacks explicit.

It also covers the part many candidates miss: listing. "Can user:42 view doc:9?" is one query. "Show me all docs user:42 can view" needs materialized reverse indexes, pagination, caveat filtering, and freshness guarantees.

Modern implementations can use pieces like SpiceDB, OpenFGA, OPA, Cedar, Verified Permissions, Redis/Valkey, Kafka/Kinesis/Pub/Sub, DynamoDB, Spanner, and PostgreSQL. The point is to understand which responsibility each tool removes, and which correctness semantics still belong to the design.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#authorization

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Security
