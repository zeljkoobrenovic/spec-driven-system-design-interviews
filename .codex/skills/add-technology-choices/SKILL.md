---
name: add-technology-choices
description: Add or update the book-style `technologyChoices` section in Spec-Driven System Design `interview.json` datasets. Use when Codex is asked to add technology options, implementation choices, cloud/self-hosted comparisons, provider choices, tech stacks, or `technologyChoices` to an interview under `data/<group>/<id>/interview.json`, including assigning technology icons and rebuilding generated docs.
---

# Add Technology Choices

## Goal

Add a practical, project-schema-compatible `technologyChoices` section to a
local interview dataset. The section should help readers map architecture
concerns to self-hosted and cloud implementation options without turning the
interview into a vendor catalog.

## Workflow

1. Resolve the target dataset.
   - Edit `data/<group>/<id>/interview.json`, never `docs/<group>/data/...`.
   - If the user gives only an ID, search `data/*/index.json` and
     `data/*/*/interview.json`.
   - Validate JSON before editing:
     `python3 -c "import json; json.load(open('<path>'))"`.

2. Inspect the dataset before choosing technologies.
   - Extract step IDs/titles:
     `jq -r '.steps[] | [.id,.title] | @tsv' <path>`.
   - Review requirements, capacity, data model, high-level nodes, patterns,
     final design, and existing `technologyChoices` if present.
   - Prefer local precedent from similar book datasets:
     `jq '.technologyChoices[0:2]' data/book/notification-system/interview.json`.

3. Add or update `technologyChoices`.
   - If absent, place it after `dataModel` and before `patterns` when practical.
   - If present, preserve useful entries and update stale/missing concerns.
   - Use 8-14 concerns for a full flagship case; use fewer for a narrow case.
   - Tie every entry to real step IDs in `steps`.

4. Assign icons.
   - Run:
     `python3 _scripts/assign_tech_icons.py <path>`.
   - The script rewrites bare strings into `{ "name": ..., "icon": ... }`,
     copies icons under `<dataset>/assets/tech-icons/`, and updates
     `_media/missing.yaml` for fallback `tech.png` terms.
   - Do not hand-edit copied icon paths unless fixing a clear script issue.

5. Validate.
   - JSON parse the source file.
   - Check all `technologyChoices[].steps[]` resolve to actual step IDs.
   - Check every referenced icon path exists.
   - Run `git diff --check` on changed JSON and `_media/missing.yaml`.
   - Rebuild the relevant group with `python3 build.py <group>` because data
     changed.
   - Parse the generated docs copy and check icon paths there too.
   - If a repo-only `REVIEW.md` exists and now contains stale findings such as
     "`technologyChoices` is missing", update those statements.

## JSON Shape

Use this canonical shape:

```json
{
  "concern": "Event bus and async processing pipeline",
  "steps": ["api-ingestion", "async-pipeline", "scale"],
  "selfHosted": ["Apache Kafka", "Redpanda", "RabbitMQ"],
  "cloud": {
    "aws": ["MSK", "Kinesis", "SQS"],
    "gcp": ["Pub/Sub", "Managed Service for Apache Kafka"],
    "azure": ["Event Hubs", "Service Bus"]
  },
  "tradeoff": [
    "A log/stream fits ordered lifecycle events, replay, and multiple consumer groups.",
    "A queue is simpler for discrete retries and DLQs but weaker for long replay."
  ],
  "makesIrrelevant": "A managed stream with retention, lag metrics, and native DLQ support removes much of the hand-built retry and offset bookkeeping."
}
```

Before running icon assignment, chips may be bare strings. After the script,
chips become objects with `name` and `icon`; that is expected.

## Choosing Concerns

Choose concerns from the dataset's architecture, not generic categories. Good
concerns usually map to a decision the interview teaches:

- API gateway, identity, WAF, and rate limiting.
- Event bus / queue / workflow orchestration.
- Source-of-truth database and transactional outbox / CDC.
- Object storage and raw-file/media retention.
- Media processing, malware scanning, image/video transforms.
- Search index and SearchDoc projection.
- Vector / ANN / fuzzy dedup index.
- Fraud feature store, rules engine, model serving, moderation.
- CDN, query cache, detail cache, BFF edge behavior.
- Webhook delivery, retry, DLQ, replay UI.
- Analytics, billing, promotion/ad events, experimentation.
- Observability, tracing, logging, SLO dashboards.

Avoid:

- Listing every possible vendor.
- Adding technologies that do not match any step or final-design component.
- Choosing cloud chips that violate the provider column semantics.
- Using `technologyChoices` to introduce major architecture that the interview
  never explains.

## Icon Rules

`_scripts/assign_tech_icons.py` enforces the provider-family rule:

- AWS column chips may only use icons under `_media/aws-icons/`.
- GCP column chips may only use icons under `_media/gcp-icons/`.
- Azure column chips may only use icons under `_media/azure-icons/`.
- Self-hosted chips may use any family, usually `_media/general-icons/`.
- Unknown or provider-rejected terms fall back to `_media/tech.png` and are
  recorded in `_media/missing.yaml`.

If many important chips fall back, either accept `tech.png` or add mappings to
`_media/index.yaml` and re-run the assignment script. Do not add provider
cross-family mappings just to avoid a fallback.

## Validation Commands

Replace `<path>` and `<group>`:

```bash
python3 -c "import json; json.load(open('<path>'))"
jq -r '.technologyChoices | length, .[].concern' <path>
jq -r '(.steps | map(.id)) as $ids | [.technologyChoices[] | {concern, missing:[(.steps // [])[] | select(($ids | index(.)) | not)]} | select(.missing|length>0)]' <path>
python3 _scripts/assign_tech_icons.py <path>
python3 build.py <group>
git diff --check -- <path> _media/missing.yaml docs/<group>/data/<id>/interview.json
```

Icon existence check:

```bash
python3 -c "import json, pathlib; p=pathlib.Path('<path>'); d=json.load(open(p)); base=p.parent; missing=[]; \
for c in d.get('technologyChoices', []): \
  [missing.append((c['concern'], x.get('name'), x.get('icon'))) for x in c.get('selfHosted', []) if isinstance(x, dict) and not (base / x['icon']).exists()]; \
  [[missing.append((c['concern'], x.get('name'), x.get('icon'))) for x in vals if isinstance(x, dict) and not (base / x['icon']).exists()] for vals in c.get('cloud', {}).values()]; \
print(missing)"
```

Keep the final response short: summarize concern count, icon assignment result,
fallback terms if notable, rebuild status, and any unrelated pre-existing
working-tree changes.
