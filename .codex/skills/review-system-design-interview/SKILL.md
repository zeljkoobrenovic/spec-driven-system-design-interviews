---
name: review-system-design-interview
description: Perform an in-depth project-specific review of Spec-Driven System Design interview datasets. Use when Codex is asked to analyze, critique, audit, or review an `interview.json` file under a `data` group and dataset directory, especially for system design soundness, production realism, pedagogical flow, how steps build toward `finalDesign`, concept introduction, schema/rendering fit, or when asked to write a dataset-local `REVIEW.md`.
---

# Review System Design Interview

## Overview

Review one local Spec-Driven System Design interview as both a system design artifact and a teaching walkthrough. Produce a concrete, prioritized `REVIEW.md` in the dataset directory unless the user requests a different output.

## Workflow

1. Resolve the target interview.
   - Prefer source files under `data/<group>/<id>/interview.json`.
   - If the user gives only an ID, search `data/*/index.json` and `data/*/*/interview.json`.
   - Do not review or edit generated `docs/<group>/data/...` copies.
   - If the target is genuinely ambiguous, ask one concise question.

2. Load project context.
   - Read `AGENTS.md` or `CLAUDE.md` for repo conventions if not already in context.
   - Read only the relevant `PLAN.md` sections when schema details are needed.
   - Inspect nearby datasets only when useful for comparison, usually another `data/book/*/interview.json`.

3. Inspect the dataset before judging.
   - Validate the file parses as JSON.
   - Build a compact outline of:
     - top-level keys, title, description
     - requirements and capacity
     - API and data model
     - patterns, concepts, traps, drills, probe links
     - each step ID/title, options, flows, deep dives, view nodes/links
     - `finalDesign`, `satisfies`, `interviewScript`, `levelVariants`, `followUps`
   - Use `jq`, `rg`, `sed`, and `wc` for extraction. Read enough raw JSON slices to catch nuance; do not rely only on summaries.

4. Review along four axes.
   - System design soundness: requirements, capacity math, API shape, data model, architecture, scaling, reliability, consistency, failure modes, security/privacy, compliance, observability, operations, and cost/blast-radius trade-offs.
   - Production realism: third-party dependencies, retries, queues, idempotency, state machines, provider callbacks, rate limits, backpressure, failover ambiguity, tenancy, data retention, consent, and real operational workflows.
   - Pedagogical flow: whether each step solves the previous step's exposed problem, whether concepts are introduced just in time, whether options teach trade-offs, whether traps and drills are realistic, and whether the sequence helps a candidate build a strong interview answer.
   - Dataset/rendering fit: project schema conventions, structured `view`/`sequence` usage, canonical node types, duplicate/missing nodes, `view.links` references, `satisfies[*].steps[*]`, `probeLinks`, and whether source-vs-generated files are handled correctly.

5. Write the review.
   - Create or update `data/<group>/<id>/REVIEW.md`.
   - Keep the review repo-only. Do not rebuild docs for `REVIEW.md` alone.
   - Use concrete findings tied to the dataset, not generic system-design advice.
   - Separate high-impact issues from polish.
   - Recommend edits, but do not modify `interview.json` unless the user explicitly asks.

6. Validate.
   - Run JSON parse validation on the reviewed `interview.json`.
   - Check the created review file exists and is readable.
   - Prefer ASCII unless the repo/file already uses non-ASCII and there is a reason.
   - Check `git status --short` and mention unrelated pre-existing changes without touching them.

## Useful Commands

Use these from the repo root, replacing the path:

```bash
python3 -c "import json; json.load(open('data/book/notification-system/interview.json'))"
wc -l data/book/notification-system/interview.json
jq 'keys' data/book/notification-system/interview.json
jq '.steps[] | {id,title, option_count:(.options // [] | length), flow_count:(.flows // [] | length), concept_count:(.concepts // [] | length)}' data/book/notification-system/interview.json
jq '.finalDesign, .satisfies, .followUps' data/book/notification-system/interview.json
rg -n '"id"|"title"|"requirements"|"capacity"|"api"|"dataModel"|"steps"|"finalDesign"|"satisfies"' data/book/notification-system/interview.json
```

For structural checks:

```bash
jq '[.highLevelArchitecture.nodes[].id] as $nodes | [.steps[] as $s | (($s.view.nodes // [])[]? | select(($nodes | index(.)) | not)) | {step:$s.id, missing_node:.}]' data/book/notification-system/interview.json
jq '[.highLevelArchitecture.links[].id] as $links | [.steps[] as $s | (($s.view.links // [])[]? | select(type=="string") | select(($links | index(.)) | not)) | {step:$s.id, missing_link:.}]' data/book/notification-system/interview.json
```

## Review Structure

Use this shape unless the user requests another format:

```markdown
# Review: <Interview Title>

Reviewed file: `data/<group>/<id>/interview.json`
Review date: <YYYY-MM-DD>

## Executive Summary
<Overall assessment and 4-6 score table.>

## What Works Well
<Specific strengths.>

## Highest-Impact Issues
### 1. <Issue>
<Why it matters and concrete fix.>

## System Design Soundness
<Requirements, capacity, API, data model, architecture.>

## Step-by-Step Pedagogical Review
### Step 1: <title>
<Strengths and improvements.>

## Final Design Review
<Whether final design integrates the steps and what is missing.>

## Concept Introduction and Learning Flow
<How concepts are staged and what is missing.>

## Step-to-Final-Design Coherence
<How each step builds toward finalDesign and where transitions are weak.>

## Realism Compared With Production Systems
<Practical operational gaps and caveats.>

## Dataset and Renderer-Facing Observations
<Schema, node, link, flow, and repo convention issues.>

## Recommended Edits, Prioritized
### P1: <edit>
### P2: <edit>
### P3: <edit>

## What Not To Change
<Preserve strong structure and intentional trade-offs.>

## Bottom Line
<Short conclusion.>
```

## Rubric Details

Use ratings only as a compact summary; the findings matter more than the numbers.

- 5: production-realistic, coherent, and pedagogically excellent with minor polish only.
- 4: strong and usable, with clear improvement opportunities.
- 3: plausible but missing important concerns or has unclear teaching flow.
- 2: materially incomplete or misleading in several core areas.
- 1: not credible as a system design case.

Common high-value checks:

- Does the capacity section convert logical requests into real work units?
- Does the API expose fields later used by the architecture, such as category, priority, tenant, locale, idempotency, target, or schedule?
- Does the data model support the promised behavior, not just the first diagram?
- Are retries, idempotency, dedup, and external-provider ambiguity worded honestly?
- Are state transitions explicit enough for delivery/status-oriented systems?
- Are observability and operations present where they materially affect the design?
- Do steps reveal one problem at a time, or do they jump without motivation?
- Do options compare real trade-offs instead of strawmen?
- Does `finalDesign` include the components introduced in the steps?
- Are missing features intentionally scoped out or accidentally absent?

## Style Rules

- Be direct and specific. Name the exact step, field, or component.
- Prefer actionable findings over compliments.
- Do not browse unless the user asks for external validation, current technology recommendations, or source-backed claims.
- Do not overfit to one previous review; adapt the rubric to the interview domain.
- Do not edit generated `docs/` review outputs. `REVIEW.md` belongs next to source `interview.json`.
- Do not change `interview.json` while reviewing unless explicitly asked.
