# Review: Agentic Research Platform - System Design

Reviewed file: `data/book/agentic-research-platform/interview.json`
Review date: 2026-06-24

## Executive Summary

This review updates the earlier critique after the recent improvement pass in
`a7590d5` ("Improve agentic-research-platform per REVIEW.md"). The dataset is
now a much stronger system design case. The old highest-impact gaps around
capacity, missing alternatives, durable lab execution, local diagram link
mismatches, and abstract biosafety language have mostly been addressed.

The core teaching arc is now credible and distinctive: an agent can reason,
ground, cite, draft, and simulate, but deterministic validation, scoped human
authorization, and a durable execution controller guard anything that crosses
the wet-lab boundary. The remaining work is less about the central idea and
more about production completeness: execution APIs, state ownership between
protocols and runs, deeper provenance schema, and optional book polish.

| Axis | Rating | Notes |
| --- | ---: | --- |
| System design soundness | 4.3/5 | Strong safety boundary, capacity model, execution controller, and stateful authorization. |
| Production realism | 4.0/5 | Much better on exactly-once actuation; still needs explicit run/callback/reconciliation API contracts. |
| Pedagogical flow | 4.2/5 | Clear step progression, useful recaps, and meaningful options in key decision points. |
| Dataset/rendering fit | 4.4/5 | JSON and view references are clean; optional API-flow and book assets remain sparse. |
| Overall | 4.2/5 | A strong interview case with a few advanced production details left to tighten. |

## What Works Well

- The wet-lab boundary is still the right central hook. It makes this case
  materially different from generic agent platforms and from the other verticals
  in the series.
- Capacity is now concrete: protocol proposals/day, validation peak, dry-runs,
  wet-lab runs/day, instrument slots, run duration, result size, audit events,
  and retention all drive the architecture.
- The new `execution` sub-step closes the biggest production realism gap. It
  names the real failure mode: a retry after an ambiguous timeout must not
  submit the same physical experiment twice.
- The validation, gate, and evaluation steps now include authored options with
  real trade-offs instead of a single chosen path.
- The data model now includes `protocol_versions`, `validation_results`,
  `authorizations`, `instrument_reservations`, `run_attempts`, `findings`, and
  `provenance`, which better supports the claims in the final design.
- The final design paragraph is specific and enforceable: structured protocol
  IR, fail-closed policy evaluation, signed expirable authorization objects,
  idempotent run submission, leases, callbacks, abort support, immutable run
  records, and claim/run provenance are all present.

## Highest-Impact Issues

### 1. Execution lifecycle APIs are still under-modeled

The architecture and final design now describe the execution controller well,
but the public/API-facing contract stops short of that lifecycle. The API has
`POST /v1/protocols`, `POST /v1/protocols/{id}/authorize`, `GET /v1/runs/{id}`,
and provenance lookup. It does not show how an authorized run is scheduled, how
robot callbacks enter the platform, how abort/reconcile operations are invoked,
or how revocation interacts with an already scheduled run.

Why it matters: the highest-blast-radius path in the system is physical
execution. A candidate should be able to explain the command boundary and the
idempotency boundary precisely, not only in prose.

Concrete fix: add API rows or internal contract notes for:

- `POST /v1/runs` or an explicit "authorization accepted -> execution workflow
  starts" event, with authorization ID, reservation constraints, and
  idempotency key.
- Robot callback ingestion, with signed callback payloads and duplicate callback
  handling.
- `POST /v1/runs/{id}/abort` and/or `POST /v1/runs/{id}/reconcile`.
- Authorization revocation semantics before scheduling, during reservation, and
  after run submission.

### 2. Protocol state and run state are still partially conflated

`protocols.status` includes protocol states (`proposed`, `validated`,
`blocked`, `awaiting_authorization`, `authorized`, `rejected`) and run states
(`scheduled`, `running`, `succeeded`, `failed`, `aborted`). The `run_attempts`
table also has its own lifecycle. That ambiguity matters if one protocol
version can be authorized more than once, dry-run and wet-lab paths both exist,
or a finding aggregates several run attempts.

Concrete fix: keep `protocols.status` focused on protocol/authorization
readiness, and let `run_attempts.status` own execution state. If a denormalized
"latest run status" is useful, label it as derived. Also consider a
`protocol_versions.state` or `authorizations.state` if the walkthrough needs to
teach the exact lifecycle.

### 3. Provenance claims are stronger than the schema details

The prose and deep dive correctly say that every claim should map to citation
spans, corpus versions, protocol versions, environmental conditions,
instrument calibration, raw artifacts, derived lineage, and analysis-code
versions. The schema captures part of this, but `provenance.source_ref` is
doing too much work and `run_attempts.result_ref` is only a single pointer.

Concrete fix: either add explicit fields/tables or call out the simplification.
Good additions would be `claim_provenance` with source span and corpus snapshot,
`run_artifacts` with object references/checksums, and run metadata for
conditions, instrument version/calibration, and analysis pipeline version.

### 4. Some important decisions still have no alternatives

The new options on validation, authorization, and evaluation are useful. The
remaining single-path areas are grounding, durable execution, and
reproducibility. Those are also good interview trade-off moments.

Concrete fix: add one option set each for:

- Literature grounding: retrieval-only RAG vs curated corpus snapshots vs hybrid
  with retraction/quality signals.
- Execution: queue/reservation service vs workflow engine vs direct robot API.
- Provenance: post-hoc lineage extraction vs claim/run lineage captured at
  write time.

## System Design Soundness

The core boundary is now sound. LLM-backed reasoning is constrained to bounded
nodes, while deterministic components own safety decisions and physical
actuation. The system has a clear split between:

- Research API and pipeline for orchestration.
- Hypothesis/design agent and inference backend for bounded generation.
- Literature index and experimental data store for grounding.
- Protocol validator and policy/safety layer for deterministic screening.
- Authorization gate for human and biosafety sign-off.
- Execution controller for reservation, idempotency, leases, callbacks, abort,
  and immutable run records.
- Provenance, audit log, identity, and observability for reproducibility and
  operations.

The capacity section now supports the architecture. It identifies wet-lab runs,
instrument slots, run duration, result data volume, and long retention as the
real constraints rather than pretending HTTP QPS is the main issue.

The remaining design question is where lifecycle ownership lives. The final
design says the execution controller owns physical execution, but the schema
still gives `protocols.status` execution-like states. Tightening that split
would make the state model as strong as the prose.

## Step-by-Step Pedagogical Review

### Step 1: Naive: An Agent That Runs Experiments Autonomously

This remains an effective baseline. It exposes the two failures the rest of the
interview fixes: physical irreversibility and scientific irreproducibility. The
direct `HypoAgent -> LabRobot` link is appropriate for the naive path and no
longer has the old missing-node issue.

### Step 2: Ground in Primary Literature + Prior Data

This step is stronger now because it mentions citation spans, corpus versions,
freshness, retraction signals, and untrusted input. It sets up both provenance
and biosafety later.

The next improvement would be to show the ingestion/indexing lifecycle more
explicitly. Research systems are sensitive to corpus snapshots and retractions;
that is a useful production wrinkle for this domain.

### Step 3: Deterministic Protocol Validation

This is now one of the best steps. It uses a structured protocol IR, deterministic
rule evaluation, policy versioning, fail-closed behavior, and a clear option
comparison. The "model-as-judge" rejected option teaches the right safety lesson.

Potential polish: add a concrete validation report shape in the text or API
example, including rule IDs, risk tier, blocked reason, and remediation hints.

### Step 4: The Gate: Human Authorization for Any Physical Run

The gate step is much more production-realistic than before. Authorization is
now a durable object with signer chain, scope, expiry, revocation, and binding to
the protocol version/hash. The dry-run vs wet-lab split is clear.

The most useful next addition is revocation and changes-requested behavior. The
data model includes `changes_requested`, but the step flow mostly shows approve
or dry-run. A short branch for "request changes" or "revoke before scheduling"
would make the workflow more complete.

### Step 4a: Durable Lab Execution

This new sub-step is the most important recent improvement. It directly covers
the ambiguous timeout case, idempotency keys, run leases, reconciliation, robot
callbacks, abort/manual stop, and the rule that only the execution controller can
actuate the lab.

The remaining gap is interface-level detail. The step should either add API rows
or a deep dive for command/callback contracts, because those contracts are how
exactly-once physical actuation becomes enforceable in production.

### Step 5: Reproducibility & Provenance

The step now has the right conceptual content and a useful deep dive on what a
finding must record. It also resolves the old local-view mismatch involving
`LabRobot`.

The schema should catch up to the deep dive. `source_ref` and `result_ref` are
reasonable simplifications, but the review should make clear whether those are
opaque handles to richer records or intentionally compact fields.

### Step 6: Dual-Use & Biosafety Screening

This step is much clearer now. It frames biosafety as an adversarial hardening
pass over validation, explains why untrusted paper text cannot be part of the
safety decision, and distinguishes hard block from biosafety-officer routing.

One possible improvement is to show the policy service failure path directly in
the flow. The concepts say fail-closed; a small sequence branch would make that
operationally explicit.

### Step 7: Workflows & Scientific-Reliability Evaluation

The evaluation step now names concrete metrics: citation support, unsupported
claims, validation blocks, dry-run vs wet-lab conversion, run outcomes,
replication pass rate, time-to-reproduce, callback gaps, and policy-service
failures. The option comparison correctly rejects plausibility as the objective.

This is a strong closing step. The only polish is to show how evaluation data is
joined from provenance, run attempts, and audit events rather than only emitted
as broad observability.

## Final Design Review

The final design now integrates the steps well. The path from goal to grounded
design, structured protocol validation, human authorization, durable execution,
lab callback, data capture, provenance, audit, and evaluation is coherent.

It also now states the strongest guarantee in architectural terms: the execution
controller is the only component allowed to actuate the lab, and the robot
rejects jobs lacking a valid token. That makes "the model cannot override it"
more credible than in the earlier draft.

The final design would be near-complete if it added explicit run command,
callback, abort, reconciliation, and revocation interfaces, plus the state split
between protocol readiness and execution attempts.

## Concept Introduction and Learning Flow

The sequence is now well staged:

1. Baseline autonomous actuation exposes the risk.
2. Grounding and citations make claims traceable.
3. Structured IR and deterministic validation make protocols checkable.
4. Human authorization turns physical action into a scoped, auditable decision.
5. Durable execution turns authorization into exactly-once actuation.
6. Provenance turns outputs into reproducible science.
7. Biosafety and evaluation harden and operate the system.

The best concepts are introduced just in time: structured protocol IR before
validation, authorization object before execution, idempotency/run lease before
retries, and citation-span provenance before reproducibility.

The concept still worth expanding is multi-lab governance. The API includes
`labId` and the gateway routes by lab scope, but the interview could say more
about lab-specific instruments, policies, approvers, reagent inventories, and
retention rules.

## Step-to-Final-Design Coherence

The coherence is much improved. The final design includes the new `ExecCtrl`,
`Simulator`, policy/safety layer, identity broker, audit stream, and
observability node, and the final view references all high-level links cleanly.

The new `execution` sub-step fixes the previous weak transition between
authorization and provenance. The interview now makes clear that "authorized" is
not the same as "safely executed exactly once."

The remaining weak transition is from data/provenance to evaluation. The eval
metrics are good, but the path from provenance records and run attempts into
replication-weighted scoring could be made more explicit.

## Realism Compared With Production Systems

The design now acknowledges the operational realities that matter most:
scarce instruments, long-running physical actions, ambiguous timeouts, missing
callbacks, aborts, idempotency, run leases, biosafety officer routing, and
append-only audit records.

Production systems would also need:

- A signed robot integration contract with callback authentication and replay
  protection.
- Reservation conflict handling and reagent/instrument inventory constraints.
- Revocation and cancellation semantics across authorization, reservation, and
  already-running states.
- Multi-tenant lab boundaries for instruments, approvers, policies, and data
  retention.
- Cost and capacity controls around simulation backends and large result
  artifacts.

Those do not undermine the current interview, but they are good advanced
discussion points.

## Dataset and Renderer-Facing Observations

Validation performed:

- `interview.json` parses as valid JSON.
- Step `view.nodes` IDs all exist in `highLevelArchitecture.nodes`.
- Step `view.links` IDs all exist in `highLevelArchitecture.links`.
- Step local view links connect endpoints included in that local view.
- `finalDesign.view.nodes` and `finalDesign.view.links` resolve, and final
  design local links connect visible endpoints.
- `satisfies[*].steps[*]` references resolve to real step IDs.
- Dataset-level `patterns[*].steps[]` references resolve.
- `data/book/agentic-research-platform/interview.json` and
  `docs/book/data/agentic-research-platform/interview.json` currently have no
  diff, so the built copy matches the source dataset.

Issues and polish:

- Only the first API endpoint has a structured `sequence`; the API Flows wrap-up
  will therefore be sparse. This is optional but worth enriching for the
  authorization, run status, and provenance endpoints.
- `probeLinks` are absent. This is optional, but the case would benefit from
  curated follow-up reading around safe lab automation, durable execution, and
  scientific provenance. The dataset now has `technologyChoices` covering those
  implementation concerns.
- There are no AI visuals or explainer comic. Optional, but this domain is
  visual enough that an execution-boundary image could help.
- The dataset now uses a sub-step (`execution`) appropriately under `gate`.

## Recommended Edits, Prioritized

### P1: Add explicit execution lifecycle interfaces

Document how an authorization object becomes a run, how robot callbacks are
accepted, how abort/reconcile works, and how revocation interacts with
scheduled or running work.

### P1: Separate protocol readiness from run execution state

Keep protocol/version/authorization state distinct from physical run attempt
state. This avoids confusion when one protocol version has multiple dry-runs,
wet-lab runs, failures, or replications.

### P2: Expand provenance schema to match the claims

Make citation spans, corpus versions, run artifacts, checksums, environmental
conditions, instrument calibration/version, and analysis-code version explicit
or clearly define `source_ref` / `result_ref` as handles to those richer
records.

### P2: Add option sets for grounding, execution, and provenance

The existing options are useful. Add similar trade-offs for corpus strategy,
execution controller implementation, and provenance capture strategy.

### P3: Add richer API flows

Add structured sequences for authorization, run lifecycle, robot callback, and
provenance lookup. These would make the Wrap-up API Flows entry more useful.

### P3: Add book polish

Add `probeLinks`, and periodically refine `technologyChoices` as the case
evolves. This case is a good place to compare workflow engines, rules/policy
engines, vector indexes, object storage, event/audit logs, identity/token
brokers, and lab automation adapters.

## What Not To Change

- Keep the wet-lab boundary as the central hook.
- Keep deterministic validation outside the model.
- Keep physical authorization as a scoped object, not a status flag.
- Keep the new durable execution sub-step; it is essential to the case.
- Keep reproducibility and provenance as first-class requirements.
- Keep the compact sequence of steps. The current arc is teachable and does not
  need more breadth unless the added material directly supports the wet-lab
  boundary.

## Bottom Line

The recent changes moved this from a good conceptual draft to a strong,
production-aware interview. The next edit should not rework the story; it should
tighten the contracts around the story's most dangerous path: authorization to
physical execution, callbacks, reconciliation, revocation, and the state split
between protocols and runs.
