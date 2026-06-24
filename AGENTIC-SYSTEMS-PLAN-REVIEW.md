# Review: Agentic Platforms System Design Mini-Series Plan

Reviewed file: `AGENTIC-SYSTEMS-PLAN.md`
Review date: 2026-06-23

## Executive Summary

The revised plan closes the major issues from the prior review. The protocol
lineage claim was replaced with a boundary map, the unverifiable "Meta Agents
Rule of Two" attribution was removed, Foundations was trimmed to an 8-step
spine, the book verifier is now mandatory, Developer merge/deploy is treated as
a second gate, Finance auditability no longer depends on chain-of-thought logs,
vertical cross-links are specified, and volatile claims now have a source
backlog.

I do not see remaining P1 blockers before dataset authoring. The remaining
issues are P2/P3 consistency and source-hygiene items that should be fixed
before the plan is used as a generator prompt for the four `interview.json`
datasets.

## Remaining Findings

### 1. P2: Frozen pattern names are contradicted by the step sketches

`AGENTIC-SYSTEMS-PLAN.md:165`-`AGENTIC-SYSTEMS-PLAN.md:178` says every
`patterns[]` / `step.patterns[]` value must reuse the exact frozen names. But
the Foundations step sketches use shortened or lower-case variants at
`AGENTIC-SYSTEMS-PLAN.md:217`-`AGENTIC-SYSTEMS-PLAN.md:259`, for example:

- `agentic loop (ReAct); tool use` instead of `Agentic loop (ReAct)` and
  `Tool use / function calling`
- `least privilege / sandboxing; credential brokering` instead of
  `Least privilege / sandboxing (microVM isolation)` and
  `Credential brokering (agent never sees secrets)`
- `memory short-term vs long-term` instead of
  `Memory: short-term vs long-term (semantic/episodic/procedural)`
- `prefix caching / model routing` instead of
  `Prefix (prompt) caching; model routing (cost vs quality)`
- `HITL gate` instead of `Human-in-the-loop approval (gate)`

Why it matters: future dataset authoring is likely to copy these step sketches
directly into `step.patterns[]`. That would recreate the synonym drift the
freeze is trying to prevent.

Concrete fix: change every `Pattern:` annotation in the 8-step spine to use the
exact frozen names, or label those annotations as prose-only reminders and add a
separate exact `step.patterns[]` mapping table.

### 2. P2: The untagged "~50x token amplifiers" claim escaped the source backlog

`AGENTIC-SYSTEMS-PLAN.md:193`-`AGENTIC-SYSTEMS-PLAN.md:196` still states
`agents are ~50x token amplifiers` as part of the non-functional requirements.
The later capacity section correctly switches to formulas and dated examples at
`AGENTIC-SYSTEMS-PLAN.md:198`-`AGENTIC-SYSTEMS-PLAN.md:207`, and the source
backlog covers session growth at `AGENTIC-SYSTEMS-PLAN.md:460`.

Why it matters: `~50x` is exactly the kind of memorable number that will get
copied into the published dataset. As written, it is neither tagged
`VERIFY BEFORE PUBLISHING` nor represented in the backlog.

Concrete fix: soften the non-functional line to "agents can be large token
amplifiers" or tag the `~50x` number and add a source-backlog row for it. The
dataset should prefer the formula from the capacity section unless a dated
primary source supports the multiplier.

### 3. P2: The source backlog does not yet cover all compliance anchors

The new source backlog at `AGENTIC-SYSTEMS-PLAN.md:452`-`AGENTIC-SYSTEMS-PLAN.md:470`
is a good control, but it omits several high-stakes references that the plan
intends to use:

- Legal: UPL and ABA Model Rules 5.3/5.5 at
  `AGENTIC-SYSTEMS-PLAN.md:367`-`AGENTIC-SYSTEMS-PLAN.md:370`
- Legal corpus: Westlaw / Practical Law / KeyCite at
  `AGENTIC-SYSTEMS-PLAN.md:365`-`AGENTIC-SYSTEMS-PLAN.md:366`
- Finance: SOX/ICFR continuous controls at
  `AGENTIC-SYSTEMS-PLAN.md:356`-`AGENTIC-SYSTEMS-PLAN.md:357`
- Phase 2 marketing/HR: C2PA, NYC LL144, and EU AI Act high-risk timing at
  `AGENTIC-SYSTEMS-PLAN.md:432`-`AGENTIC-SYSTEMS-PLAN.md:441`

Why it matters: these are legal, financial, or regulatory references. Even if
some are stable, the future dataset should cite primary sources rather than
vendor summaries or memory.

Concrete fix: add backlog rows for the compliance/legal anchors, or create a
separate "stable primary sources to attach before publishing" table. The point
is not to over-research the plan now; it is to prevent high-stakes claims from
entering `toProbeFurther` without source checks.

### 4. P3: "Between step 1 and step 2" is ambiguous

`AGENTIC-SYSTEMS-PLAN.md:405` says "Between step 1 and step 2" when it means
between build-order item 1 (`agentic-platform-foundations`) and build-order
item 2 (`agentic-developer-platform`). Because Section 5 also has numbered
Foundations steps, this can be misread as between Foundations architecture
steps 1 and 2.

Concrete fix: change the heading to "After dataset 1 and before dataset 2" or
"After Foundations and before Developer."

## Resolved Findings

- Protocol lineage: resolved by the protocol boundary map and explicit "do not
  claim ACP merged into A2A" note at `AGENTIC-SYSTEMS-PLAN.md:261`-`AGENTIC-SYSTEMS-PLAN.md:270`.
- Rule of Two attribution: resolved by the unattributed at-most-two heuristic
  and warning not to cite Meta without a primary source at
  `AGENTIC-SYSTEMS-PLAN.md:76`-`AGENTIC-SYSTEMS-PLAN.md:86`.
- Foundations scope: resolved by the 8-step spine and explicit survey-warning
  at `AGENTIC-SYSTEMS-PLAN.md:209`-`AGENTIC-SYSTEMS-PLAN.md:259`.
- Book verifier: resolved by the mandatory `node data/book/_verify.mjs` gate at
  `AGENTIC-SYSTEMS-PLAN.md:411`-`AGENTIC-SYSTEMS-PLAN.md:427`.
- Developer reversibility: resolved by the draft-PR autonomy ceiling and
  merge/deploy second gate at `AGENTIC-SYSTEMS-PLAN.md:100`-`AGENTIC-SYSTEMS-PLAN.md:114`
  and `AGENTIC-SYSTEMS-PLAN.md:313`-`AGENTIC-SYSTEMS-PLAN.md:322`.
- Finance audit artifact: resolved by the immutable decision-record language at
  `AGENTIC-SYSTEMS-PLAN.md:339`-`AGENTIC-SYSTEMS-PLAN.md:355`.
- Pattern sequencing: mostly resolved by the frozen name list and catalog-before-
  verticals sequence at `AGENTIC-SYSTEMS-PLAN.md:165`-`AGENTIC-SYSTEMS-PLAN.md:178`
  and `AGENTIC-SYSTEMS-PLAN.md:405`-`AGENTIC-SYSTEMS-PLAN.md:408`; see remaining
  Finding 1 for the step-sketch mismatch.
- Vertical cross-links: resolved by the explicit prose, absolute-URL, and
  catalog-backlink convention at `AGENTIC-SYSTEMS-PLAN.md:294`-`AGENTIC-SYSTEMS-PLAN.md:308`.
- Hybrid exceptions: resolved by the selection rule at
  `AGENTIC-SYSTEMS-PLAN.md:64`-`AGENTIC-SYSTEMS-PLAN.md:71`.
- Root-level planning note: resolved at `AGENTIC-SYSTEMS-PLAN.md:5`-`AGENTIC-SYSTEMS-PLAN.md:9`.
- Legal gate Markdown typo: resolved at `AGENTIC-SYSTEMS-PLAN.md:367`-`AGENTIC-SYSTEMS-PLAN.md:370`.

## What Works Well

- The plan now has a clear series contract: Foundations teaches the common
  substrate; verticals add corpus + gate + domain evaluation.
- The deterministic/hybrid/probabilistic selection rule is strong and prevents
  the Finance and Legal cases from becoming inappropriate ReAct-loop examples.
- The Developer vertical now has the right product boundary: high autonomy to a
  draft PR, not direct merge/deploy.
- The Finance vertical now teaches auditable evidence and deterministic
  controls rather than raw model reasoning retention.
- The source backlog is a useful authoring control and should make
  `toProbeFurther` quality materially better.
- The plan still fits the local renderer: canonical node types, structured
  `view`/`sequence`, `technologyChoices`, `patterns`, and `toProbeFurther` are
  all aligned with the current schema.

## Suggested Authoring Order

1. Fix the pattern-name mismatches, the untagged `~50x` claim, and the missing
   compliance/source-backlog rows.
2. Author `agentic-platform-foundations`.
3. Add the frozen agentic patterns to `data/book/patterns` immediately after
   Foundations, before any vertical dataset is written.
4. Author Developer, Finance, and Legal one at a time, running
   `node data/book/_verify.mjs`, JSON parsing, and `python3 build.py book` after
   each dataset.
5. Add icons, AI visuals, and comics only after the content and generated docs
   are stable.

