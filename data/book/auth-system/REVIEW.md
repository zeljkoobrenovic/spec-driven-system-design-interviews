# Review: Authentication & Authorization - System Design

Reviewed file: `data/book/auth-system/interview.json`
Review date: 2026-06-09

## Executive Summary

The recent auth-system update materially improved the dataset. The previous
highest-impact gaps around MFA gating, refresh-token lineage, authorization
context, capacity math, duplicate architecture nodes, and audit schema are now
mostly addressed in the source JSON. The interview is a credible security-first
walkthrough that can be used as-is.

| Axis | Score | Notes |
| --- | ---: | --- |
| System design soundness | 4 | Strong auth fundamentals, concrete lifecycle state, and realistic token strategy; a few state machines still need explicit backing records. |
| Production realism | 4 | Much better capacity, audit, revocation, and policy detail; recovery, tenant isolation, and incident operations remain follow-up-heavy. |
| Pedagogical flow | 4 | The step order is coherent and the options teach real trade-offs. |
| Dataset/rendering fit | 4 | JSON and graph references are clean; sequence aliases and sparse API/final flows are the main renderer-facing weaknesses. |
| Interview readiness | 4 | Strong enough for the book group; one more pass would make it a flagship auth case. |

## What Works Well

- The flow starts with secure password storage, then moves to sessions/tokens,
  OIDC, refresh/revocation, authorization, MFA, abuse defense, and JWKS scaling.
  That is the right learning progression for an auth interview.
- Capacity now breaks the design into useful work units: verification QPS,
  login QPS, password-hash CPU, refresh QPS, MFA QPS, authorization decisions,
  audit writes, denylist memory, rate-limit counters, and revocation latency.
- The API now models the key MFA split: `/v1/login` can return a
  `mfa_required` response with `challenge_id` and `mfa_pending_token`, while
  `/v1/mfa/verify` is the point that returns full tokens.
- The data model now carries important production state: refresh-token
  families, MFA factors, OAuth login attempts, tenant-scoped roles/permissions,
  rate-limit counters, identity links, and an audit event schema.
- The authorization API is no longer a toy query string. It accepts subject,
  action, resource, tenant, owner, attributes, and decision context, and it
  returns `policy_version` plus a cache TTL.
- The high-level architecture uses canonical node IDs and no longer contains
  duplicate legacy nodes such as `A`/`Auth` or `C`/`Client`.
- Dataset references validate cleanly: step/final view nodes and links resolve,
  option view nodes and links resolve, and `satisfies[*].steps[*]` references
  resolve.

## Highest-Impact Issues

### 1. MFA challenge state is introduced by the API but not modeled explicitly

The API now returns `challenge_id` and `mfa_pending_token`, and the MFA sequence
correctly gates full token issuance. The data model has `mfa_factors`, but it
does not yet model the short-lived challenge or pending-auth state behind those
API fields.

Why it matters: MFA correctness depends on binding a challenge to the login
attempt, factor, user, device, risk decision, expiry, and attempt counter. If
that state is left implicit, candidates can miss replay protection and
rate-limited verification semantics.

Concrete fix:

- Add `mfa_challenges` or `pending_auth_attempts` with `challenge_id`,
  `user_id`, `factor_id`, `device_id`, `tenant_id`, `risk_score`,
  `expires_at`, `attempt_count`, `consumed_at`, and `status`.
- State whether `mfa_pending_token` is an opaque lookup token or a short-lived
  signed token with a `purpose=mfa_pending` claim.
- Add a short note that MFA challenge verification is rate-limited separately
  from password login.

### 2. API and final-design sequence coverage lags behind the richer model

Only `/v1/login` has a structured API sequence, and the final design has no
flows. The step flows cover login, OIDC, refresh reuse, and MFA, but not the
full set of APIs now present in the dataset.

Why it matters: this interview is about lifecycle correctness. The source now
has enough API/model detail to teach those lifecycles, but the visual/sequence
path still makes several critical operations feel secondary.

Concrete fix:

- Add API sequences for `/v1/mfa/challenge`, `/v1/mfa/verify`,
  `/v1/token/refresh`, `/v1/logout`, and `/v1/authorize`.
- Add at least one final-design flow for the hot request path:
  gateway verifies JWT locally, checks revocation only for sensitive operations,
  calls authorization with resource context, then writes audit events.
- Add a second final-design flow for refresh-token reuse detection and family
  revocation.

### 3. Authorization is much stronger, but still compressed into one table and
one service call

The dataset now includes tenant ID, attributes, policy version, and cache TTLs.
That fixes the previous toy authorization shape. The remaining weakness is that
resource hierarchy, relationship checks, decision cache placement, and role
change invalidation are still described compactly.

Why it matters: real authz bugs usually happen at the boundary between policy,
resource ownership, tenant scope, cached decisions, and service-level
enforcement. A strong auth interview should make that boundary visible.

Concrete fix:

- Split or expand `roles_permissions` into policy bindings, resource
  attributes, and relationship/ownership facts if the dataset wants to teach
  ABAC beyond a small JSONB field.
- Add a decision-cache component or explicitly state where the cache lives
  (gateway, resource service, or authz service).
- Include one sequence where the gateway authorizes broadly but the resource
  service repeats an object-level check before mutation.
- State how `policy_version` invalidates cached decisions after role or tenant
  membership changes.

### 4. Abuse defense has counter storage, but not the full risk workflow

`rate_limit_counters` is a good addition, and the abuse step now discusses
multi-dimensional limits. The design still does not show a counter/risk store
node in the architecture, and the satisfies section mentions breached-password
checks without showing the dependency or data path.

Why it matters: credential-stuffing defense is not just counters. It includes
signals, challenge escalation, false-positive handling, user recovery, and
provider/dependency failure modes.

Concrete fix:

- Add a `Risk / Counter Store` node or make it clear that the Login Rate
  Limiter owns a replicated fast store.
- Add a breached-password-check dependency if that behavior is kept in
  `satisfies`.
- Document what happens when the counter store is degraded: fail open, fail
  closed, local fallback, or challenge-only mode.
- Add one note about support/user recovery for incorrectly challenged users.

### 5. Recovery, device/session management, and tenant isolation are still
mostly follow-ups

The follow-up list correctly names passkeys, account recovery, SSO/logout,
service-to-service auth, leaked signing keys, and multi-tenant isolation. Those
are good follow-ups, but account recovery, session/device inventory, and tenant
isolation are central enough to deserve a little more mainline treatment.

Why it matters: auth systems are often compromised through recovery flows,
stale devices, weak tenant boundaries, or support workflows rather than through
the idealized login path.

Concrete fix:

- Add a compact "out of scope but important" note to requirements or final
  design for recovery, support workflows, and tenant isolation.
- Add a `devices` or `user_sessions` entity if "manage sessions/devices" stays
  in the functional requirements.
- Add tenant ID to token claims and state that verifier/authz checks reject
  cross-tenant access even when the subject is valid.

## System Design Soundness

The security fundamentals are solid. The design avoids common traps: plaintext
or fast-hashed passwords, password verification on every request, implicit OAuth
flow, trusting ID tokens without issuer/audience/nonce validation, long-lived
access tokens without revocation, SMS-only MFA, gateway-only authorization, hard
account lockout, and central introspection on every request.

The strongest recent improvement is that the state model now backs most of the
claims made by the steps. Refresh-token rotation has a family table, OAuth has
transient login attempts, authorization has tenant and policy-version fields,
rate limiting has keyed counters, and audit logging has concrete event fields.

The main remaining soundness gap is pending-state modeling. MFA challenges,
remembered devices, account recovery, and session/device inventory still need
either explicit records or a clear statement that they are outside scope.

Key rotation is directionally right: JWKS, short access-token TTLs, overlapping
keys, local verification, unknown-`kid` refresh behavior, and emergency
revocation are described. It would be stronger if the final design had a
sequence showing verifier cache refresh and what changes during emergency key
compromise.

## Step-by-Step Pedagogical Review

### Step 1: Naive Baseline: Password Login & Secure Storage

Strong opening. It anchors the interview in the highest-consequence storage
decision and correctly separates slow password verification from the hot request
path. The flow still uses short participant IDs (`C`, `U`) instead of canonical
architecture IDs; this is minor, but canonical IDs would improve highlight
inheritance and consistency.

### Step 2: Sessions vs Stateless Tokens

The trade-off is clear: centralized revocation and lookup state versus local
verification speed. The chosen design should continue to emphasize that access
tokens are short-lived signed tokens while refresh tokens are stateful,
hashed, rotating records.

### Step 3: Federated Login (OAuth / OIDC)

This is one of the best steps. It teaches code flow, PKCE, nonce/state,
server-side exchange, token validation, and identity linking. The added
`oauth_login_attempts` entity makes the flow much more credible. Use canonical
`Client` and `IdP` participant IDs in the sequence for consistency.

### Step 4: Token Refresh & Revocation

The refresh-token family model is now the right production shape. The flow's
reuse-detection branch is especially valuable because it shows why rotation is
not just "issue a new token." Add an API sequence for `/v1/token/refresh` so
this behavior appears in the public interface section too.

### Step 5: Authorization (RBAC / ABAC)

The step now has enough tenant/resource/policy context to be realistic. The
next improvement is to show defense in depth: gateway-level authorization plus
resource-service object-level checks. This would also make the "not only at the
gateway" trap concrete.

### Step 6: Multi-Factor Authentication

The old coherence issue is fixed: the API and sequence no longer issue full
tokens before MFA succeeds. The remaining improvement is to add challenge-state
storage and clarify the lifetime/claims of the `mfa_pending_token`.

### Step 7: Rate Limiting & Abuse Defense

The option set is practical and avoids teaching hard lockouts or single-IP
limits as acceptable answers. The counter model is now present. Add degraded
mode and recovery handling so this step teaches how to defend login without
self-inflicted denial of service.

### Step 8: Scaling Verification & Key Rotation

The core lesson lands: verify locally with JWKS and avoid central introspection
on every request. The deep dive should stay. A visual or sequence for key
rotation would make the operational story easier to explain under interview
pressure.

## Final Design Review

The final design now integrates the major components cleanly: client app,
login rate limiter, auth service, credential store, external IdP, MFA service,
token service, signing keys/JWKS, revocation list, API gateway, authorization
service, policy store, resource service, and audit log.

The final design's main weakness is that it is a static architecture view only.
For an auth system, the dynamic paths matter as much as the boxes. Add final
flows for:

- Login with MFA: password verification -> pending MFA -> factor verify -> full
  token issue.
- Refresh reuse: refresh request -> token hash lookup -> retired-token replay
  -> family revocation -> audit.
- Hot request path: local JWT verify -> sensitive-op revocation check -> authz
  decision/cache -> resource-service object check -> audit.
- Key rotation: publish new JWKS key -> overlapping verification -> retire old
  key -> emergency revoke if compromised.

## Concept Introduction and Learning Flow

Concepts are introduced at the right time. Slow KDFs appear before tokens,
stateless verification appears before revocation, OIDC appears before identity
linking, refresh rotation appears before denylist checks, and JWKS appears only
after the hot-path scaling pressure is established.

The strongest remaining pedagogical improvement is to name the state machines
more directly. Auth systems are lifecycle systems: pending login, MFA pending,
active session, refreshed token, retired refresh token, revoked family,
disabled factor, consumed OAuth state, and rotated signing key. The data model
now contains many of those states; the prose should call them out as deliberate
state transitions.

## Step-to-Final-Design Coherence

Most step outputs now appear in the final design:

- Step 1 maps to `Auth` and `UserDB`.
- Step 2 maps to `API`, `Token`, `Keys`, and `Session`.
- Step 3 maps to `IdP`, `Auth`, and `UserDB`.
- Step 4 maps to `Token`, `Revoke`, `Keys`, and refresh-token family state.
- Step 5 maps to `AuthZ` and `Policy`.
- Step 6 maps to `MFA`, `MFAProvider`, `Auth`, and `Token`.
- Step 7 maps to `Limiter` and `Audit`, with `rate_limit_counters` in the data
  model.
- Step 8 maps to `API`, `Token`, `Keys`, and `Revoke`.

The main coherence gaps are now narrower:

- MFA challenge state is not represented as a data entity.
- Rate-limit/risk storage is present in the data model but not visible as an
  architecture node.
- Authz caching and resource-service object-level enforcement are described but
  not shown in a flow.
- Final design has no dynamic flows to prove the state transitions.

## Realism Compared With Production Systems

Compared with a production identity platform, this dataset is now realistic on
the core login/token/authz path. It handles the main threat model: credential
database theft, stolen refresh tokens, stale permission claims, credential
stuffing, token replay, and signing-key rotation.

The remaining realism gaps are around the messy operational edges:

- account recovery and factor loss,
- support/admin workflows,
- device/session inventory,
- tenant isolation,
- risk-engine false positives,
- degraded counter or MFA-provider dependencies,
- audit access controls and incident investigation workflow,
- passkey/passwordless migration.

Those do not all need to become main steps. A concise "production extensions"
note in final design or follow-ups would be enough for most of them.

## Dataset and Renderer-Facing Observations

- JSON parse validation passes.
- Step view node references resolve.
- Step view link references resolve.
- Option view node/link references resolve.
- Final-design node/link references resolve.
- `satisfies[*].steps[*]` references resolve.
- Requirements and capacity diagrams are raw Mermaid overview diagrams, which is
  allowed by the repo conventions.
- The canonical architecture node set is clean: no duplicate legacy nodes were
  found in `highLevelArchitecture.nodes`.
- Some sequence participants still use short IDs (`C`, `U`, `I`) instead of
  canonical IDs (`Client`, `UserDB`, `IdP`). They render, but canonical IDs
  would make highlight inheritance and maintenance easier.
- Only `/v1/login` has an API sequence. Add sequences for MFA, refresh,
  logout/revocation, authorization, and OIDC callback for parity with the
  richer data model.
- `finalDesign.flows` is absent. This is not a schema error, but it is a missed
  teaching opportunity for a lifecycle-heavy system.
- The dataset does not yet include `technologyChoices`, `aiVisuals`, an
  `explainerComic`, or per-requirement `aiVisual` fields. These are optional
  book features, not correctness blockers.

## Recommended Edits, Prioritized

### P1: Add explicit MFA challenge / pending-auth state

Add a challenge or pending-auth entity and clarify whether the
`mfa_pending_token` is opaque or signed. This is the most direct remaining
correctness gap.

### P1: Add flows for lifecycle-critical operations

Add API or final-design sequences for MFA verification, refresh reuse,
authorization, logout/revocation, and the hot request path.

### P2: Make authorization defense-in-depth visible

Show gateway authorization plus resource-service object checks, and document
where decision caching lives and how `policy_version` invalidates it.

### P2: Surface abuse/risk storage and degraded modes

Represent the counter/risk store in the architecture or state clearly that the
limiter owns it. Add behavior for counter-store and MFA-provider degradation.

### P2: Add device/session and tenant-isolation detail

Back the "manage sessions/devices" requirement with a small entity or final
design note, and state how tenant IDs are carried in tokens and checked in
authz/resource services.

### P3: Add optional book polish

Consider adding `technologyChoices`, generated AI visuals, per-requirement
illustrations, and an explainer comic after the core review findings above are
handled.

## What Not To Change

- Keep the security-first ordering.
- Keep the explicit bad options; they teach real interview traps.
- Keep short access tokens plus rotating, stateful refresh tokens as the
  recommended compromise.
- Keep local JWKS verification as the platform-scale request-path answer.
- Keep WebAuthn/passkeys as a strong MFA option and follow-up unless the case is
  expanded into a passwordless-auth interview.

## Bottom Line

The recent changes moved this from a good conceptual auth walkthrough to a
production-plausible interview dataset. The remaining work is about making the
state machines and operational paths visible: pending MFA, final-design flows,
authz cache invalidation, abuse/risk degraded modes, device/session management,
and tenant isolation.
