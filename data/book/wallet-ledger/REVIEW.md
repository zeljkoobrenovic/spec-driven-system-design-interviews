# Review: Wallet / Ledger - System Design

Reviewed file: `data/book/wallet-ledger/interview.json`
Review date: 2026-06-08

## Executive Summary

This review updates the prior wallet-ledger review after the recent dataset
revision. The major previous findings were addressed: the design now states the
local ledger-shard transaction boundary, replaces the misleading balance-cache
language with a durable balance table, adds top-up/withdrawal/callback APIs,
expands the data model, adds capacity write-amplification math, and introduces
a cross-shard transfer sub-step.

The interview is now a strong book-quality case. It has a coherent correctness
spine, realistic trade-offs, and a useful Staff-level extension. The remaining
work is no longer about missing core pieces; it is about making the advanced
money-system details precise enough that a reader cannot misinterpret the
cross-shard saga, withdrawal holds, schema constraints, or recovery model.

| Area | Rating | Notes |
| --- | --- | --- |
| System design soundness | 4.5/5 | Core ledger, idempotency, balance, outbox, reconciliation, and external settlement pieces are sound; cross-shard and hold semantics need more precision. |
| Production realism | 4/5 | Much improved with external rails, capacity math, and operations notes; still light on provider-event uniqueness, holds, replay, and compliance controls. |
| Pedagogical flow | 4.5/5 | The step order teaches one correctness problem at a time and the new `cross-shard` sub-step fits naturally under concurrency. |
| Dataset/rendering fit | 4.5/5 | JSON, step links, parent, `satisfies`, and probe links validate; a few pattern tags and diagram details can better reflect the new content. |
| Overall | 4.5/5 | Interview-ready and materially stronger than the prior version, with targeted follow-up edits left. |

## What Works Well

- The core sequence is exactly right for a wallet ledger: reject mutable
  balances, use immutable double-entry postings, make writes idempotent,
  materialize balances transactionally, serialize balance-changing writes, emit
  events through an outbox, then reconcile against the source of truth.
- The latest revision fixed the biggest correctness ambiguity by stating that
  the journal, idempotency table, balance table, and outbox table live in the
  same ledger database or shard for the hot path.
- The data model now includes `transactions`, `journal_entries`,
  `account_balances`, `idempotency_keys`, `outbox_events`, and
  `external_settlements`, which aligns much better with the final design.
- Top-up, withdrawal, and settlement callback APIs are now first-class instead
  of only implied by reconciliation.
- Capacity planning now translates 10k logical movements per second into row
  writes, journal growth, hot-account limits, retention, and per-account
  consistency.
- The new `cross-shard` sub-step is a high-signal addition. It correctly names
  the central choice: local saga plus clearing account versus cross-shard 2PC.
- The final design now explains internal ledger finality versus external rail
  finality, and it explicitly says corrections are compensating entries, not
  edits.

## Highest-Impact Issues

### 1. The cross-shard clearing-account model needs exact mechanics

The new `cross-shard` step is directionally right, but it currently says both
shards use "the same clearing account." A single ledger account normally belongs
to one shard. If both shard-local legs need to balance independently, the design
should define whether there are per-shard clearing accounts, mirror accounts, a
central settlement shard, or a coordinator-owned transfer table that makes the
global in-transit position auditable.

Why it matters: cross-shard transfers are the hardest part of the case. The
current wording teaches the right intuition but can leave readers with a vague
or impossible implementation if they interpret one clearing account as locally
writable on both shards.

Concrete fix:

- Add `cross_shard_transfers` or a coordinator table with
  `transfer_id`, source shard, destination shard, state, leg ids, retry count,
  and terminal reason.
- Reword the clearing model as "per-shard clearing accounts reconciled by a
  coordinator" or choose a central settlement shard explicitly.
- Name the terminal states: `pending_source_posted`,
  `pending_destination_posted`, `posted`, `compensating`, `compensated`,
  `failed`.
- State the client-visible semantics during the pending window: source funds
  unavailable, destination not credited until the second leg posts, or a
  clearly marked pending credit.
- Add one failure drill: source leg committed, coordinator crashes before
  destination leg. Expected behavior should be idempotent resume from the
  coordinator table.

### 2. Withdrawal holds are promised but not represented in the ledger model

The withdrawal API says it "places a hold on the balance," and the audit flow
says failed withdrawals release the hold. The schema, however, only has one
`account_balances.balance` field and no hold/reservation table or available
balance concept.

Why it matters: without explicit holds, a user can initiate a withdrawal and
then spend the same funds before the external rail settles. This is a different
state from a posted debit and deserves its own model.

Concrete fix:

- Add either a `holds` / `authorizations` table or balance fields such as
  `posted_balance`, `available_balance`, and `held_amount`.
- Define hold lifecycle states: `created`, `captured`, `released`, `expired`,
  `reversed`.
- Tie withdrawals to the hold id, settlement movement id, and final ledger
  transaction id.
- Mention expiry and abandoned-provider-call handling.

### 3. Schema constraints and indexes are still mostly prose

The data model is much better than before, but several correctness guarantees
are expressed in notes instead of explicit fields, constraints, or indexes.
Important examples: idempotency scope, idempotency TTL, request-hash mismatch
behavior, provider event uniqueness, outbox retry state, outbox ordering,
transaction state transitions, and account/currency dimensions.

Why it matters: for a ledger interview, the schema is not just storage detail;
it is where many invariants become enforceable.

Concrete fix:

- Scope idempotency keys by tenant/client/account and operation, not just
  `idempotency_key` globally.
- Add a unique provider-event key to settlement ingestion, for example
  `(provider, provider_event_id)`.
- Add outbox relay fields: `status`, `attempt_count`, `next_attempt_at`,
  `locked_by`, `locked_until`, and a pruning/archive strategy.
- Add account metadata or at least an `accounts` table so account status,
  owner/tenant, currency policy, and shard assignment are explicit.
- Make indexes visible for the main queries: statement reads by
  `(account_id, currency, entry_id)`, idempotency lookup by scope and key,
  pending settlement scans, and undelivered outbox scans.

### 4. Reconciliation and disaster recovery need sharper replay semantics

The audit step now includes continuous checks, scheduled reconciliation,
provider report matching, and rebuild from the journal. That is strong. The
remaining gap is the exact replay boundary: how to restore journal,
idempotency, balance, outbox, and settlement tracker state to a mutually
consistent point after partial restore, region failover, or relay replay.

Why it matters: money systems often fail at the edge between "the journal is
authoritative" and "derived systems have been rebuilt incorrectly." The dataset
already asks this as a follow-up; the review recommendation is to promote the
most important part into the audit/final-design text.

Concrete fix:

- Define a recovery checkpoint: journal commit position, outbox event id,
  balance watermark, settlement report watermark.
- Say that balances are rebuilt from journal entries through the checkpoint,
  then tailed forward.
- State that idempotency records must be retained at least as long as client
  retry windows and restored consistently with committed transactions.
- Correct the invariant wording from "balance equals sum of entries past its
  watermark" to "balance equals the sum through its watermark; entries after
  the watermark are unapplied tail work."

### 5. The API examples should make money representation and duplicate behavior explicit

The API examples use decimal strings such as `"10.00"`, while the data model
uses integer minor units. This is acceptable if the API canonicalizes decimal
strings before hashing and posting, but the dataset should say so. The transfer
sequence also shows duplicate-key replay but not the mismatch branch.

Why it matters: idempotency request hashes are only meaningful if equivalent
amount representations canonicalize the same way, and reused keys with changed
payloads must be visibly rejected.

Concrete fix:

- Add `minorUnits` or state that `"10.00"` is parsed into integer minor units
  before validation and request hashing.
- Add the API error behavior for a reused idempotency key with a different
  payload, for example `409 idempotency_key_reused_with_different_request`.
- Add typical money API validation errors: insufficient funds, unsupported
  currency, account frozen, movement not found, provider event already seen.

## System Design Soundness

The core design is now sound. The local write path is properly scoped: one
ledger-shard transaction writes balanced journal entries, the materialized
balance row, idempotency result, and outbox row together. That eliminates the
old ambiguity where those pieces looked like separate infrastructure requiring
2PC.

Double-entry is introduced correctly and now includes per-currency balancing.
The data model uses integer minor units, avoiding floating-point traps. The
remaining improvement is to add explicit transaction constraints and account
metadata so the schema can enforce the invariants that the prose describes.

Idempotency is much stronger than before because it stores a request hash and
commits with the posting. Tighten the scope and lifecycle: global
`idempotency_key` as a primary key is too broad for multi-tenant APIs, and key
retention should match the retry window and dispute/settlement lifecycle.

The balance design is strong. It correctly frames the balance table as durable
derived state, not a cache. The concurrency step also correctly addresses CAS,
row locks, serializable isolation, two-account updates, lock ordering, and
overdraft checks.

Cross-shard transfer handling is the main remaining soundness topic. The saga
plus clearing-account direction is a good default, but the design needs exact
state, idempotent leg writes, and per-shard clearing semantics. Otherwise the
reader may assume atomicity that the design explicitly no longer has.

External rail handling is now real enough to satisfy the requirement. The next
level is modeling holds and available balance, because withdrawals are not just
settlement callbacks; they reserve funds while waiting for an asynchronous
provider.

## Step-by-Step Pedagogical Review

### Step 1: Naive: A Single Mutable Balance Column

This remains an effective baseline. It motivates auditability, lost updates,
and rebuildability without spending too long on a deliberately wrong design.
The caption now calls out the mutable balance table clearly.

### Step 2: Model Money as a Double-Entry Ledger

This is still the strongest conceptual step. The per-currency balancing text is
an important improvement. The step now cleanly leads to the next problem:
summing the journal for reads is too slow.

Recommended improvement: mention that a transaction header gives the postings
business meaning, not just grouping. The data model already has
`transactions`; the teaching step can preview why it exists.

### Step 3: Idempotent Transfers

The step now covers the key nuance: idempotency key plus request hash written in
the same transaction as the posting. That fixes the prior correctness gap.

Recommended improvement: add the mismatch response in the sequence or API
section. A duplicate key with the same hash returns the original result; a
duplicate key with a different hash returns a conflict.

### Step 4: Materialized Balances for Fast Reads

This step is now precise. It avoids the cache metaphor and states that the
balance table is durable, transactional, and rebuildable from the journal.

Recommended improvement: use the same terminology everywhere: "balance table"
or "balance view" is fine, but avoid mixing it with cache-like language in
future edits.

### Step 5: Concurrency Control on Balances

This is a high-value senior step. It explains lost updates, overdraft
invariants, CAS, row locks, serializable isolation, and deterministic lock
ordering for two account rows. It now correctly hands off cross-shard transfers
to the sub-step.

Recommended improvement: add one sentence about retry budgets and backoff under
CAS conflicts, because the capacity section already calls out hot-account
limits.

### Step 5a: Transfers Across Two Shards

This is the most important new step. It raises the right Staff-level issue and
compares saga plus clearing account against 2PC.

Recommended improvement: make the clearing account concrete. Show two shards,
a coordinator, per-shard clearing accounts or a central settlement account, and
the coordinator state machine. The current single `LedgerDB` diagram hides the
reason this step exists.

### Step 6: Reliable Downstream Events (Outbox)

The outbox step is now well grounded: the outbox is explicitly a durable table
written in the ledger transaction, and the relay publishes at least once. It
also mentions relay lag, retries, dedup, and pruning.

Recommended improvement: add "Transactional outbox" to the dataset-level
`patterns` list and set `step.patterns` for this step to that pattern rather
than only `Immutable append-only ledger`.

### Step 7: Reconciliation, Audit, and Settlement

This step is much stronger than before. It includes continuous checks, full
reconciliation, immutable statements, provider settlement matching, and
compensating entries.

Recommended improvement: clarify the watermark invariant and add one recovery
failure drill. For example: restore from backup where outbox delivery is ahead
of balance watermark; expected behavior is replay by journal position and
dedup by event/transaction id.

## Final Design Review

The final design now integrates the walkthrough well. It explicitly names the
same-shard transaction boundary and says there is no distributed commit on the
hot path. It also scopes cross-shard transfers to the `cross-shard` path and
external movements to `pending_external / settled / failed / reversed`.

The main remaining issue is precision. The final design should briefly state
which parts are synchronous invariants and which are asynchronous eventual
workflows:

- Synchronous: journal entries balance, idempotency result commits, balance row
  updates, outbox row exists, overdraft invariant holds.
- Asynchronous: outbox relay delivery, reconciliation scans, statement export,
  provider settlement, cross-shard saga completion.

That split would make the correctness story easier to defend in an interview.

## Concept Introduction and Learning Flow

The learning flow is strong. Each step exposes a new problem created by the
previous step:

- Mutable balances fail audit and concurrency.
- Double-entry fixes auditability but makes reads expensive.
- Materialized balances fix reads but introduce write contention.
- Concurrency control fixes lost updates but reveals cross-shard transfer
  boundaries.
- Outbox fixes dual-write events.
- Reconciliation closes the loop for drift and external settlement.

The main concept gap is that the new content added concepts that are not yet
reflected in the pattern catalog: transactional outbox, clearing account,
settlement state machine, and holds/reservations.

## Step-to-Final-Design Coherence

The steps now map cleanly to the final design:

- `double-entry` contributes the immutable journal and balanced postings.
- `idempotency` contributes request-hash dedup in the ledger transaction.
- `balances` contributes the durable materialized balance table.
- `concurrency` contributes per-account serialization and overdraft checks.
- `cross-shard` contributes the saga/clearing path for non-colocated accounts.
- `events` contributes the transactional outbox and relay.
- `audit` contributes reconciliation, statement export, and settlement
  matching.

The coherence gap is the physical shape of the advanced paths. The final design
names cross-shard and external settlement behavior, but the diagrams and schema
do not yet show the coordinator, hold table, provider-event uniqueness, or
replay watermarks that make those paths operational.

## Realism Compared With Production Systems

Compared with production wallet ledgers, this dataset now covers the essential
mechanisms: immutable journal, transaction header, exact money representation,
idempotency, materialized balances, concurrency control, outbox, settlement
tracking, and reconciliation.

Remaining production realism gaps:

- Holds and available balance for withdrawals and authorizations.
- Provider-event deduplication and signature/secret rotation details.
- Cross-shard coordinator recovery and idempotent leg execution.
- Outbox relay leasing, retry backoff, dead-letter handling, and archive.
- Replay cutoffs across journal, balance table, idempotency table, outbox, and
  settlement tracker.
- Account lifecycle controls: frozen accounts, KYC/AML restrictions, tenant
  ownership, and audit access permissions.
- Hot-account admission control beyond sub-account buckets: throttles, queues,
  or single-writer partitioning for extreme accounts.

These do not all need full walkthrough steps. Several can be short Staff-level
notes, follow-up prompts, or failure drills.

## Dataset and Renderer-Facing Observations

- `interview.json` parses as valid JSON.
- Top-level keys cover the expected book fields: requirements, capacity, API,
  data model, patterns, steps, final design, satisfies, interview script, level
  variants, follow-ups, and probe links.
- Step `view.nodes` string references resolve against
  `highLevelArchitecture.nodes`.
- Step `view.links` string references resolve against
  `highLevelArchitecture.links`.
- The `cross-shard` parent reference resolves to `concurrency`.
- `satisfies.functional[].steps` and `satisfies.nonFunctional[].steps` resolve
  to real step IDs.
- Step `probeLinks` resolve against `toProbeFurther.links`.
- Raw requirements and capacity Mermaid snippets are simple and appropriate for
  overview diagrams.
- No browser visual validation was performed as part of this review.
- The `events` step should probably tag a `Transactional outbox` pattern; the
  current dataset-level patterns do not include it.
- The `cross-shard` diagram uses a single `LedgerDB` node with two repeated
  leg links. It renders structurally, but it does not teach the two-shard
  boundary. A local view with `ShardA`, `ShardB`, `Coordinator`, and
  `Clearing` nodes would communicate the point better.

## Recommended Edits, Prioritized

### P1: Make cross-shard transfer executable

Add a coordinator state table, explicit per-shard or central clearing-account
model, terminal states, idempotent leg ids, and a failure drill for coordinator
crash between legs.

### P1: Model holds and available balance

Add a hold/reservation model for withdrawals and future authorizations. Include
available versus posted balance, hold lifecycle, expiry, capture, release, and
reversal behavior.

### P2: Harden schema constraints and indexes

Add idempotency scope, provider-event uniqueness, outbox relay fields, account
metadata, and explicit indexes for statement reads, pending settlements, and
undelivered outbox events.

### P2: Clarify replay and recovery watermarks

State how journal position, balance watermark, outbox event id, idempotency
records, and settlement reports are restored and replayed consistently after
backup restore or failover.

### P3: Improve pattern tagging and diagrams

Add patterns for `Transactional outbox`, `Clearing account`, and possibly
`Settlement state machine`; update the `events` step pattern tag; make the
cross-shard visual show two shards and a coordinator.

### P3: Tighten API examples

Clarify decimal-string-to-minor-unit canonicalization, request-hash mismatch
responses, and common money API errors such as insufficient funds, frozen
account, unsupported currency, and duplicate provider event.

## What Not To Change

- Keep the compact main spine. It is now strong and interview-friendly.
- Keep correctness over availability as the theme.
- Keep double-entry, idempotency, materialized balances, concurrency, outbox,
  and reconciliation as the non-negotiable sequence.
- Keep `cross-shard` as a sub-step under concurrency; it is the right place for
  that Staff-level detail.
- Keep external settlement in the closing step. It rounds out the money-system
  lifecycle without derailing the core walkthrough.
- Keep corrections as compensating entries, never edits.

## Bottom Line

The wallet-ledger interview is now a strong system design case. The recent
changes resolved the prior major gaps and made the design substantially more
production-realistic. The next improvements should make the advanced paths
precise: cross-shard saga state, withdrawal holds, enforceable schema
constraints, and replay watermarks.
