Today's Spec-Driven System Design Interview: Authentication & Authorization — System Design.

Auth is where "simple login" becomes system design.

This walkthrough starts with password login and credential storage, then exposes the decisions that often get waved away: sessions vs JWTs, OAuth/OIDC, refresh rotation, revocation, RBAC/ABAC, MFA, rate limits, abuse defense, audit logs, and key rotation.

The core lesson: auth has two very different paths.

The login path is deliberately expensive. Slow salted password hashes, MFA, IdP redirects, risk checks, and rate limits protect users, but must be isolated from the rest of the platform.

The request path has to be fast. At high volume, API calls cannot depend on a central auth call. Local signed-token checks, cached JWKS keys, short lifetimes, scoped denylists, and fresh enough authorization decisions keep security from becoming a bottleneck.

What makes the case useful is the failure-mode thinking: what if the password database is stolen, a refresh token is replayed, a user's role changes, an IdP is used, an account is attacked, or a signing key must be rotated?

Technology choices are options, not endorsements: Keycloak, Cognito, Microsoft Entra ID, Identity Platform, OPA/OpenFGA, Redis/Valkey, KMS/HSM signing, API gateways, WAFs, audit pipelines, and managed databases can remove plumbing, but not the reasoning around token lifetime, tenant isolation, revocation, policy freshness, and abuse controls.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#auth-system

Project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Security
