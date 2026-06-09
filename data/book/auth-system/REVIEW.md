# Review: Authentication & Authorization - System Design

Reviewed file: `data/book/auth-system/interview.json`
Review date: 2026-06-09

## Executive Summary

This is a strong security-first walkthrough. It teaches the right progression:
password storage, session/token trade-offs, OIDC, refresh and revocation,
authorization, MFA, abuse defense, and key rotation. The step options and traps
are especially useful because they compare real alternatives instead of toy
choices.

| Axis | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4 | Core architecture is credible, but some security-critical state is only described in prose. |
| Production realism | 3 | Good threat framing; needs more explicit lifecycle, tenancy, recovery, and operational data. |
| Pedagogical flow | 4 | The sequence builds cleanly and motivates each next step. |
| Dataset/rendering fit | 4 | JSON and references are clean; duplicate legacy node IDs should be removed. |
| Interview readiness | 4 | Usable as-is, with clear improvements before making it a flagship auth case. |

## What Works Well

- The walkthrough starts with the highest-consequence baseline decision:
  password storage. That is the right anchor for an auth interview.
- The sessions vs stateless tokens step presents a real production trade-off:
  revocation and centralized state versus hot-path verification scale.
- The OIDC step correctly teaches authorization-code flow, PKCE, nonce/state,
  issuer/audience validation, and local identity linking.
- The refresh/revocation step names the right compromise: short access tokens,
  rotating refresh tokens, and a small denylist for logout and sensitive
  operations.
- The traps are concrete and interview-relevant, especially around token
  contents, generic login errors, gateway-only authz, SMS-only MFA, hard
  lockouts, and central introspection.
- Renderer-facing references are mostly healthy: JSON parses, step/final-design
  view nodes and links resolve, `satisfies[*].steps[*]` resolve, and
  `probeLinks` resolve.

## Highest-Impact Issues

### 1. Security-critical state is under-modeled

The data model has `users`, `sessions`, `roles_permissions`, `identity_links`,
and `audit_log`. That supports the broad story, but not the details the case
promises: rotating refresh-token chains, reuse detection, per-device session
management, MFA enrollment, WebAuthn/passkey credentials, revocation by token
ID/session family, OIDC state/nonce/PKCE login attempts, and abuse counters.

Why it matters: these are not implementation trivia for an auth system. They
are the difference between "we say refresh rotation" and "we can detect a
stolen refresh token and revoke the whole family."

Concrete fix:

- Add `refresh_token_families` or expand `sessions` with `family_id`,
  `token_hash`, `rotated_from`, `last_used_at`, `revoked_at`,
  `revocation_reason`, `device_id`, `ip_hash`, and `user_agent_hash`.
- Add `mfa_factors` with factor type, encrypted TOTP seed reference or WebAuthn
  credential ID/public key, enrollment status, last used time, and backup-code
  handling.
- Add `oauth_login_attempts` for `state`, `nonce`, `pkce_challenge`, provider,
  redirect URI, expiry, and consumed time.
- Add `rate_limit_counters` or `login_risk_events` to back the abuse-defense
  step with concrete storage.
- Add policy metadata such as tenant/resource attributes, policy version, and
  decision cache TTL.

### 2. MFA is taught as a gate, but the API returns full tokens immediately

Step 6 correctly warns that full tokens must not be issued before MFA succeeds.
However, the public API section still has `POST /v1/login` returning full
`access_token` and `refresh_token`, with only prose saying it "triggers MFA if
enabled." There is no MFA challenge endpoint, MFA-pending credential, or
challenge state in the API.

Why it matters: this is a direct coherence gap between the strongest MFA trap
and the interface candidates will copy in an interview.

Concrete fix:

- Change `/v1/login` to return either full tokens for non-MFA users or a
  `mfa_required` response with `challenge_id` and a limited `mfa_pending_token`.
- Add `POST /v1/mfa/challenge` and `POST /v1/mfa/verify`.
- Add `POST /v1/mfa/factors` and `DELETE /v1/mfa/factors/{factor_id}` if user
  session/device management is in scope.
- Show in the sequence diagram that full token issuance happens only after MFA
  verification.

### 3. Capacity is too qualitative for the design choices it motivates

The capacity section names the right dimensions, especially `~100k req/s`
verification, but it does not turn them into work units. For this interview,
the crucial math is CPU and storage pressure: password hash cost, login peak,
refresh QPS, signature verification cost, JWKS cache behavior, audit write
volume, denylist lookup QPS, and rate-limit counter cardinality.

Why it matters: the case argues for local JWT verification and against central
introspection, but the candidate needs numbers to defend that trade-off.

Concrete fix:

- Split traffic into verification QPS, login QPS, refresh QPS, MFA challenge
  QPS, and authorization-decision QPS.
- Estimate CPU for Argon2/bcrypt under login bursts and show why login must be
  separately rate-limited and horizontally scaled.
- Estimate audit writes/sec for successes, failures, revocations, policy
  changes, and suspicious events.
- Estimate denylist/cache memory from token TTL and revocation rate.
- Add rate-limit counter cardinality for account, IP, subnet, tenant, and
  device dimensions.

### 4. Authorization lacks tenant/resource context and cache invalidation rules

The authorization step correctly contrasts central policy decisions with
permissions embedded in tokens. The API, however, uses
`GET /v1/authorize?sub=usr_1&action=delete&resource=doc_9` and the model uses a
flat `roles_permissions` table. That does not carry tenant, resource owner,
relationship, environment, policy version, or freshness requirements.

Why it matters: RBAC/ABAC is only realistic when the decision has enough context
and a clear invalidation story. Otherwise the dataset teaches "central authz"
without showing what makes it correct.

Concrete fix:

- Make authorization a POST body with `subject`, `action`, `resource`,
  `tenant_id`, `resource_owner`, `attributes`, and `decision_context`.
- Add policy versioning and decision cache TTLs.
- State which decisions can be cached, which require a fresh policy lookup, and
  what happens on role change.
- Add one flow showing gateway and resource-service defense in depth.

### 5. The final design promises "everything security-relevant is audited" but
the architecture has one generic audit log

The final design includes `Audit Log`, and several steps mention auditability.
That is a good signal, but the dataset does not specify event schema,
immutability, retention, privacy treatment, alerting, or investigation
workflows.

Why it matters: auth audit logs often contain sensitive metadata and are used
for account recovery, incident response, compliance, and abuse detection. A
generic log box is not enough for the production story.

Concrete fix:

- Add event types: login success/failure, MFA challenge/verify, refresh rotate,
  refresh reuse, logout, role/policy change, suspicious login, key rotation.
- Include actor, subject, tenant, session/device, IP/user-agent fingerprint,
  correlation ID, result, risk score, and policy version.
- State retention and access controls for audit data.
- Add alert examples for refresh reuse, impossible travel, credential stuffing,
  and signing-key compromise.

## System Design Soundness

The security fundamentals are strong. The dataset avoids common auth design
mistakes: plaintext passwords, fast hashes, implicit OAuth flow, long-lived
tokens without revocation, gateway-only authorization, hard account lockout,
and central token introspection on every request.

The biggest soundness gap is that several critical behaviors remain prose-level:
refresh-token lineage, MFA state, OIDC transient login state, and authz decision
context. These should be represented in API and data-model fields so the final
architecture is implementable, not just plausible.

The key-rotation story is directionally right: local verification through JWKS,
overlapping old/new keys, and short token TTLs. It would be stronger if it named
`kid`, JWKS cache max-age, verifier refresh behavior on unknown `kid`, emergency
key revocation, and blast radius for a leaked private key.

The abuse-defense step is good at explaining why per-IP limits and hard lockouts
are insufficient. It should add operational detail: a shared counter store,
multi-region counter consistency expectations, false-positive handling, CAPTCHA
or step-up abuse, and a path for user recovery after suspicious activity.

## Step-by-Step Pedagogical Review

### Step 1: Naive Baseline: Password Login & Secure Storage

This is a strong opening. It makes password hashing the first irreversible
security decision and explains why login cannot be the per-request verification
path. Add a small note about peppering/HSM-managed secret material only if you
want a deeper senior/staff branch; it is not required for the base step.

### Step 2: Sessions vs Stateless Tokens

The trade-off is well framed. The next improvement is to explicitly state which
credential type the final design chooses for access tokens and refresh tokens:
short JWT access tokens plus stateful/hashed refresh-token records. That wording
prevents readers from thinking refresh tokens are also purely stateless.

### Step 3: Federated Login (OAuth / OIDC)

This is one of the strongest steps. It covers code flow, PKCE, IdP token
validation, and identity mapping. Add callback/state storage to the data model
and API so nonce/state/PKCE are not only mentioned in prose.

### Step 4: Token Refresh & Revocation

The chosen approach is realistic. The missing piece is persistent token-family
state: what exactly is stored, hashed, rotated, retired, and revoked. A flow for
"refresh reuse detected" would make this step much stronger.

### Step 5: Authorization (RBAC / ABAC)

The step teaches the right distinction between authentication and authorization
and correctly warns against stale permissions embedded in tokens. It needs more
resource context and cache invalidation details to be production-realistic.

### Step 6: Multi-Factor Authentication

The options are strong, especially the WebAuthn/passkey alternative and the SMS
caveats. The API needs to match the teaching: full tokens should be issued only
after MFA succeeds, and the model should store enrolled factors, backup codes,
factor recovery, and remembered-device state if those are in scope.

### Step 7: Rate Limiting & Abuse Defense

This step is practical and avoids the common hard-lockout trap. It should add a
concrete rate-limiter state model and state how counters are keyed, expired, and
replicated. It should also distinguish login throttling from account recovery
and MFA-prompt throttling, which have different abuse modes.

### Step 8: Scaling Verification & Key Rotation

The step lands the main scaling lesson: do not put auth introspection on every
request. Add verifier cache behavior, `kid` lookup, emergency rotation, and
observability metrics so key rotation feels operationally complete.

## Final Design Review

The final design integrates the major components introduced in the steps:
limiter, auth service, IdP, MFA, token service, keys/JWKS, revocation list, API
gateway, authorization service, policy store, resource service, and audit log.
That coherence is a strength.

The final design should be more explicit about trust boundaries and hot paths.
For example:

- Login path: limiter -> auth -> credential store/OIDC -> MFA -> token service.
- Refresh path: token service -> hashed refresh-token record -> rotation/reuse
  detection -> signing keys.
- Request path: gateway/resource verifies JWT locally -> optional denylist
  check for sensitive operations -> authz decision.
- Operations path: audit events, risk signals, and key rotation events.

This would make the final design read like the culmination of the steps rather
than a compact summary of them.

## Concept Introduction and Learning Flow

The concepts are staged well. Each step introduces two or three important terms
right when the design needs them. The best examples are "slow KDF" in step 1,
"stateless signed token" in step 2, "OIDC id token" in step 3, "refresh-token
rotation" in step 4, and "JWKS" in step 8.

The learning flow would improve if "state machine" concepts were introduced
explicitly for login, MFA, refresh rotation, and revocation. Auth systems are
less about boxes and more about lifecycle correctness: pending, verified,
active, refreshed, retired, revoked, compromised, recovered.

## Step-to-Final-Design Coherence

Most step outputs appear in the final design. The main coherence issues are:

- Step 6 says MFA must gate token issuance, but the API shows `/v1/login`
  returning tokens directly.
- Step 4 says refresh tokens rotate and reuse detection revokes the chain, but
  the data model does not store enough chain state.
- Step 7 says multi-dimensional limiting and breached-password checks are used,
  but the final design lacks a counter/risk store or breach-check dependency.
- Step 5 says policy decisions are cached and evaluated centrally, but the API
  and data model do not carry tenant/resource attributes or cache-invalidation
  mechanics.

## Realism Compared With Production Systems

Compared with a production identity platform, the dataset is strongest on
threat awareness and weakest on lifecycle data. Real systems spend a lot of
energy on device/session inventory, account recovery, factor enrollment,
support workflows, incident response, tenancy, and audit access controls.

The follow-up list already names WebAuthn, account recovery, SSO/single logout,
service-to-service auth, leaked signing keys, and multi-tenant isolation. Those
are good follow-ups. For a flagship case, pull one or two of them into the main
body: account recovery and tenant isolation are too central to leave entirely
as afterthoughts.

## Dataset and Renderer-Facing Observations

- JSON parse validation passes.
- Step view node references resolve.
- Step view link references resolve.
- Option view node/link references resolve.
- Final-design node/link references resolve.
- `satisfies[*].steps[*]` references resolve.
- `probeLinks` references resolve.
- Requirements and capacity diagrams are raw Mermaid overview diagrams, which is
  allowed by the repo conventions.
- There are duplicate/legacy architecture nodes with overlapping labels:
  `A` and `Auth`, `C` and `Client`, `I` and `IdP`, `T` and `Token`, `U` and
  `UserDB`. They do not break current rendering, but they increase maintenance
  risk and make sequence aliases harder to reason about. Prefer canonical IDs
  throughout and remove unused legacy nodes if no generated diagram needs them.
- Only `/v1/login` has a structured API sequence. Add sequences for refresh,
  logout/revocation, authorization, OIDC callback, and MFA verification if this
  case is intended to match the richer book datasets.

## Recommended Edits, Prioritized

### P1: Make API and data model match MFA and refresh-token lifecycle

Add MFA challenge/verify endpoints and token-family/session fields. This fixes
the most direct correctness gaps.

### P1: Add concrete capacity math

Break down verification, login, refresh, MFA, audit, denylist, and rate-limit
QPS. Use the math to justify local JWT verification and a small replicated
revocation path.

### P1: Expand authorization context

Move `/v1/authorize` to a richer request shape with tenant/resource attributes,
policy version, and cache/freshness semantics.

### P2: Clean up architecture node IDs

Remove duplicate legacy nodes or migrate sequences to canonical IDs without
aliases. Keep `Client`, `Auth`, `UserDB`, `IdP`, and `Token` as the canonical
forms.

### P2: Add operational audit and key-rotation detail

Specify audit event schema, retention/access controls, key `kid` handling, JWKS
cache refresh, and emergency key compromise response.

### P3: Add optional book polish

Consider adding `technologyChoices`, more API sequences, and generated visuals
for parity with newer book datasets. These are presentation improvements, not
core correctness blockers.

## What Not To Change

- Keep the security-first ordering. It is the right teaching structure for auth.
- Keep the explicit bad alternatives in the options; they teach real traps.
- Keep WebAuthn/passkeys as an MFA option and follow-up unless the case is
  intentionally expanded into passwordless auth.
- Keep local JWT verification via JWKS as the scaling answer, with caveats for
  sensitive-operation revocation checks.

## Bottom Line

This is already a credible auth-system interview. The next level is to make the
state machines explicit: MFA gating, refresh-token families, OIDC transient
state, authorization context, revocation semantics, and audit operations. Those
changes would turn a strong conceptual walkthrough into a production-realistic
flagship dataset.
