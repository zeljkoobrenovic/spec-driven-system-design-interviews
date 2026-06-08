# Review: Wallet / Ledger - System Design

Reviewed file: `data/book/wallet-ledger/interview.json`
Review date: 2026-06-08

## Executive Summary

This is a strong, focused ledger walkthrough. It teaches the right core
sequence for money movement: reject mutable balances, introduce double-entry
postings, make writes idempotent, materialize balances, serialize balance
changes, emit events through an outbox, and close with reconciliation. The
case is concise and has a clear "correctness over availability" theme.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4/5 | Correct core mechanisms, but transaction boundaries and cross-shard transfers need sharper treatment. |
| Production realism | 3/5 | Good retry, outbox, and reconciliation coverage; under-specifies external rails, operations, and compliance controls. |
| Pedagogical flow | 4/5 | The step order is natural and teaches one major correctness idea at a time. |
| Dataset/rendering fit | 4/5 | JSON and cross-references are clean; a few diagram labels can mislead about durable stores. |
| Overall | 4/5 | Usable and interview-ready after clarifying the atomicity model and external-money lifecycle. |

## What Works Well

- The main teaching spine is exactly right for a wallet ledger: mutable balance
  baseline, double-entry journal, idempotency, materialized balance, concurrency
  control, outbox, reconciliation.
- The options in steps 3 through 6 compare real alternatives instead of strawmen:
  idempotency key vs natural key, sync balance vs async view vs read-time sum,
  optimistic vs pessimistic vs serializable concurrency, outbox vs direct publish
  vs CDC.
- The traps are specific and useful, especially "single mutable balance",
  "floating-point for money", and "check then decrement separately".
- The final design integrates nearly all introduced components and states the
  most important invariant: corrections are compensating entries, not edits.
- The structured views, sequence flows, `satisfies.steps`, and `probeLinks`
  resolve cleanly.

## Highest-Impact Issues

### 1. The atomic transaction boundary is ambiguous

Several sections say the idempotency key, journal postings, materialized
balance, and outbox event are committed in the same transaction. The diagram,
however, presents `IdemStore`, `LedgerDB`, `BalanceCache`, and `Outbox` as
separate components. If those are physically separate stores, the design needs
distributed transactions; if they are tables in the same ledger database or
same shard transaction, the dataset should say that explicitly.

Why it matters: the correctness claim depends on the boundary. A retry-safe
transfer is only retry-safe if the idempotency record and ledger write commit
together. A strongly consistent balance is only strong if the balance row and
journal append share the same atomic commit. The outbox is only reliable if the
outbox row is written in that same commit.

Concrete fix:

- Reword `IdemStore`, `BalanceCache`, and `Outbox` as durable tables/views in
  the ledger database or per-shard ledger partition, not independent caches or
  queues on the write path.
- Rename `BalanceCache` in the architecture to something like `BalanceView` and
  use a durable-state node type rather than a cache metaphor.
- In step 3, step 4, step 6, and `finalDesign.description`, add one sentence:
  "These rows live in the same transactional ledger store or shard; if separated,
  this would require 2PC."

### 2. Cross-shard transfers are acknowledged but not designed

The capacity section says accounts are sharded by account id, and the
concurrency step lists "transfer spans two shards" as a bottleneck. The final
design still describes a single atomic posting path without declaring the
scope: same-shard only, colocated accounts, 2PC across shards, or a saga/clearing
account model.

Why it matters: a wallet transfer naturally touches two accounts. If those
accounts live on different shards, "append debit + credit in one transaction"
is no longer a local database transaction. This is one of the highest-signal
staff-level issues for a ledger interview.

Concrete fix:

- State the base guarantee: "The main design assumes both affected accounts are
  in one ledger shard/transaction partition."
- Add a sub-step or deep dive for cross-shard transfers: deterministic lock
  ordering with 2PC, or pending/posted states with a transfer coordinator and
  compensating entries.
- Update `finalDesign` and the Staff level expectations to name the chosen
  approach rather than leaving it as a follow-up only.

### 3. Top-up and withdrawal are requirements but not first-class flows

The requirements include top up and withdraw through an external rail. The
architecture has `External` and the audit step mentions settlement, but the API
only exposes transfers and reads. There is no explicit lifecycle for initiated,
pending, settled, failed, reversed, or disputed external movements.

Why it matters: external rails are asynchronous and ambiguous. A bank or PSP can
accept, delay, fail, reverse, or partially settle. A wallet design should model
the difference between internal ledger finality and external settlement finality.

Concrete fix:

- Add `POST /v1/topups`, `POST /v1/withdrawals`, and a webhook/callback endpoint
  or provider event ingestion API.
- Add status fields and states such as `pending_external`, `posted`, `failed`,
  `reversed`, and `settled`.
- Add a sequence flow showing a funding request, an external callback, and a
  compensating entry for a failed withdrawal.

### 4. The data model is too thin for the correctness claims

The data model has `journal_entries`, `account_balances`, and
`idempotency_keys`, which is a good start. It omits several fields and
constraints needed to make the claims precise:

- A transaction header table for transaction status, idempotency/request hash,
  source, reference, created/posted timestamps, and metadata.
- Account and currency dimensions. `account_balances` should likely key by
  `(account_id, currency)`, not just `account_id`.
- Explicit constraints that postings in a transaction balance to zero per
  currency.
- Indexes for statement reads by `(account_id, created_at/entry_id)`.
- A way to distinguish internal transfer postings from external settlement,
  fee, hold, reversal, and adjustment postings.

Why it matters: the walkthrough says "every movement is auditable", but the
schema does not yet show enough information to reconstruct why a transaction
happened or to enforce balance by currency.

Concrete fix: expand the data model to at least `transactions`,
`journal_entries`, `account_balances`, `idempotency_keys`, `outbox_events`, and
`external_settlements`, with key constraints and the primary query indexes.

### 5. Capacity planning does not translate logical traffic into write units

The capacity section gives a useful starting point: about 10,000 balance-changing
transactions per second, reads much greater than writes, hundreds of millions of
accounts, indefinite retention. It does not convert that into real write
amplification or storage.

Why it matters: a ledger transaction is not one write. A transfer usually writes
at least two journal entries, two balance updates, one idempotency row, and one
outbox event. At 10,000 transactions per second, that is tens of thousands of
durable row writes per second before indexes, replication, and reconciliation
scans.

Concrete fix:

- Add a row estimating writes per transfer and total durable write QPS.
- Estimate yearly journal entries and storage, including indexes and replicas.
- Add partitioning notes: account shard, transaction id, currency, and
  statement query index.
- Mention hot-account limits separately from aggregate TPS.

## System Design Soundness

The core model is correct: double-entry postings are the source of truth,
balances are derived, idempotency protects retrying clients, and reconciliation
checks derived state against the journal. Those are the right primitives for a
wallet ledger.

The main soundness gap is the phrase "same transaction". It appears in the
idempotency, balance, outbox, and final design sections, but the visual model
looks like separate stores. For this system, the dataset should make the
transactional boundary part of the architecture: either a single ledger
database/shard owns all write-path rows, or the design must explicitly pay for
distributed commit.

The concurrency section is strong for a single account balance row. It explains
CAS, row locks, serializable isolation, and atomic check-and-decrement. It should
also define how a transfer locks or updates two accounts consistently: lock
ordering, deadlock handling, retry behavior, and cross-shard fallback.

The data model captures the source-of-truth idea but not enough production
metadata. Adding a transaction header and outbox table would align the schema
with the later architecture. Also tighten amount typing: "minor units" usually
implies integer storage; fixed-point decimal is a separate valid choice. Avoid
the ambiguous field type `decimal (minor units, never float)`.

The API is intentionally small, but it should expose the requirement surface.
Internal transfer, top-up, withdrawal, balance, history, and provider callback
or settlement ingestion are distinct contracts. The history endpoint also needs
pagination and stable ordering.

## Step-by-Step Pedagogical Review

### Step 1: Naive: A Single Mutable Balance Column

This is a good baseline. It motivates auditability, race conditions, and
rebuildability without over-explaining. The one improvement is to make the
caption less confusing: "ledger store" is not really a ledger yet in this
baseline. Call it an account table or mutable balance table.

### Step 2: Model Money as a Double-Entry Ledger

This is the strongest conceptual step. It introduces immutable postings,
compensating corrections, and exact amounts. The step should mention balancing
per currency, not just globally, because multi-currency is listed later as a
follow-up and is easy to get wrong.

The flow note says "the materialized balance updates with it" before the
materialized balance step is introduced. That forward reference is minor but can
be tightened: either remove it here or preview it explicitly as the next problem.

### Step 3: Idempotent Transfers

The retry story is clear and important. The default option is right, but it
should specify replay semantics: the same idempotency key with a different
payload must not return success. Store a request hash and reject mismatches.

The step should also tie the idempotency table to the ledger transaction
boundary. If `IdemStore` is separate from `LedgerDB`, the current wording hides
the exact failure mode it is trying to prevent.

### Step 4: Materialized Balances for Fast Reads

This step teaches the right trade-off between read-time summing, synchronous
materialization, and asynchronous views. The default choice fits the stated
strong-consistency requirement.

The name `BalanceCache` weakens the lesson. For money, this is not a disposable
cache. It is durable derived state with a watermark and reconciliation path.
Rename it to `BalanceView` or `BalanceTable`.

### Step 5: Concurrency Control on Balances

This is a high-value step. It directly addresses lost update, overdraft, CAS,
row locks, and serializable isolation. It also has the best interview prompt in
the dataset.

The missing detail is two-account atomicity. A debit and credit touch two balance
rows, so the step should explain lock ordering or transaction shape. The
bottleneck note about cross-shard transfers is useful but deserves either a
sub-step or a final-design decision.

### Step 6: Reliable Downstream Events (Outbox)

The outbox comparison is good and realistic. Direct Kafka publish is correctly
called out as a dual-write risk, and CDC is presented as a plausible alternative.

The default outbox should appear in the data model. Also, avoid calling the
outbox a queue in the canonical architecture unless the text says it is an
outbox table plus relay. A queue-shaped node may make readers think the event is
already outside the database transaction.

### Step 7: Reconciliation, Audit, and Settlement

This is a strong closing step because it covers drift, statement export, and
external settlement. It should go one level deeper on operational cadence:
continuous invariant checks, scheduled full reconciliation, external report
matching, alert thresholds, and replay/rebuild procedures.

This is also the right place to introduce external movement states. A failed
withdrawal or disputed top-up should have a state machine, not only a final
reconciliation correction.

## Final Design Review

The final design integrates the components introduced in the walkthrough and
states the core invariants clearly. It is a good interview wrap-up.

The main change needed is to qualify its atomicity claim. Today it says one
atomic transaction updates postings, materialized balances, and outbox events.
That is correct only if those are in the same transactional store/shard. If the
architecture intends separate infrastructure for idempotency, balance, and
outbox, the final design needs either 2PC or a different guarantee.

The final design should also mention its scope for cross-shard transfers and
external settlements. Without that, it reads as fully general even though two
important cases are only treated as follow-ups.

## Concept Introduction and Learning Flow

The concepts are staged well. Double-entry appears only after the mutable
balance failure is clear. Idempotency appears after the write model exists.
Materialized balance appears after read cost is exposed. Concurrency appears
after the derived balance exists. Outbox appears after the ledger has meaningful
downstream consumers. Reconciliation closes the loop.

The main learning-flow opportunity is to make every step's "new risk" become
the next step's opening problem. This already works for most steps. The weakest
transition is from double-entry to materialized balance because materialized
balance is mentioned inside the double-entry flow before the learner reaches
that step.

## Step-to-Final-Design Coherence

Most steps map cleanly into the final design:

- `double-entry` contributes the immutable journal and balanced postings.
- `idempotency` contributes retry-safe write semantics.
- `balances` contributes the materialized balance view and watermark.
- `concurrency` contributes atomic check-and-decrement and per-account
  serialization.
- `events` contributes the transactional outbox.
- `audit` contributes reconciliation, statements, and settlement matching.

The coherence gap is that the final design silently upgrades these pieces into
one atomic commit without showing how the pieces are physically colocated. Make
that explicit and the coherence becomes much stronger.

## Realism Compared With Production Systems

The dataset handles several production realities well: retries, lost responses,
lost updates, outbox delivery, drift detection, and external settlement
corrections.

Missing or under-modeled production concerns:

- Request hash validation for idempotency key reuse.
- Outbox relay operations: lag, retries, dedup keys, pruning, and replay.
- Reconciliation operations: invariant alerts, repair playbooks, and rebuild
  from journal.
- External rail state machine and delayed/failed/reversed settlements.
- Access control and audit log controls for financial data.
- Ledger schema evolution and immutable history retention.
- Hot-account write limits and single-account throttling.
- Disaster recovery: point-in-time restore is not enough if replay ordering and
  idempotency records are inconsistent.

These do not all need full steps, but the final design or follow-ups should name
the most important ones.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Step `view.nodes` string references resolve against `highLevelArchitecture.nodes`.
- Step `view.links` string references resolve against `highLevelArchitecture.links`.
- `satisfies.functional[].steps` and `satisfies.nonFunctional[].steps` resolve
  to real step IDs.
- `probeLinks` resolve against `toProbeFurther.links`.
- The raw requirements and capacity Mermaid snippets are simple and appropriate
  for overview diagrams.
- The local option-only nodes `Broker` and `CDC` render, but they do not carry
  canonical node types. Consider adding `type: "stream"` for Kafka and
  `type: "worker"` for the CDC tailer, or adding them to
  `highLevelArchitecture.nodes` if they become part of the final story.
- `BalanceCache` is typed as `cache`, but the text describes durable,
  transactionally updated derived state. This is both a renderer cue and a
  design cue; rename or retype it.
- No browser visual validation was performed as part of this review.

## Recommended Edits, Prioritized

### P1: Clarify atomicity and store colocation

Rename the write-path durable stores and state that idempotency rows, postings,
balance rows, and outbox rows commit in one ledger database/shard transaction.
If that is not the intended design, add the required distributed transaction
mechanism.

### P1: Add a cross-shard transfer decision

Add a sub-step, deep dive, or final-design paragraph that chooses the model for
transfers whose debit and credit accounts live on different shards.

### P1: Expand external rail APIs and lifecycle

Add top-up, withdrawal, and provider callback/settlement ingestion endpoints.
Show pending, settled, failed, and compensating states.

### P2: Strengthen the schema

Add transaction headers, outbox events, external settlements, request hashes,
currency-aware balances, constraints, and indexes.

### P2: Improve capacity math

Convert 10,000 logical transactions per second into journal rows, balance
updates, outbox rows, idempotency rows, index writes, replication load, and
retention storage.

### P2: Add operational checks

Add metrics and alerts for idempotency conflicts, CAS retries, lock waits,
serialization failures, outbox lag, reconciliation drift, external settlement
mismatches, and hot-account throttling.

### P3: Tighten wording and diagrams

Avoid "cache" for the materialized balance, avoid "ledger store" in the naive
mutable-balance baseline, and keep materialized-balance details out of step 2
until the reader reaches step 4.

## What Not To Change

- Keep the seven-step shape. It is compact and has a good interview rhythm.
- Keep double-entry and idempotency as early non-negotiables.
- Keep the option comparisons in steps 3 through 6; they teach real trade-offs.
- Keep reconciliation as the closing step. It is the right ending for a money
  system because it explains how the system detects and repairs drift.
- Keep the "corrections are compensating entries" framing.

## Bottom Line

This is a solid ledger interview case with the right core mechanisms and a
clear teaching arc. The next revision should make the transaction boundary
explicit, choose a cross-shard transfer strategy, and make external rail
movement a first-class lifecycle. Those changes would move it from a strong
conceptual walkthrough to a production-realistic wallet ledger design.
