---
name: research-external-links
description: Find, vet, group, and add credible external reading links for system design, architecture, ML systems, or interview walkthroughs. Use when Codex is asked to do web research for "probe further" resources, further reading, company implementation links, production case studies, official docs, papers, repositories, or to populate fields such as toProbeFurther in interview.json-style datasets.
---

# Research External Links

## Goal

Produce a grouped, credible reading list that helps readers probe beyond the local explanation. Prefer sources that show how real systems are built, measured, operated, or implemented.

## Workflow

1. Confirm the target topic from local context or the user request.
2. Browse the web. Do not rely on memory for source selection, URLs, current availability, titles, or company pages.
3. Build a source set before editing files. Prefer primary sources:
   - Company engineering blogs, architecture posts, research pages, and official repositories.
   - Peer-reviewed papers, arXiv papers from the implementing teams, and official research-lab pages.
   - Official documentation for tools, libraries, and platforms.
   - Benchmarks from known project sites or repositories.
4. Include company-implementation links whenever the topic is a recognizable production system. Search for implementation examples from companies that have shipped similar systems.
5. Avoid thin SEO explainers, generic tutorials, marketing pages without technical substance, scraped copies, and unattributed summaries unless no primary source exists.
6. Group links by learning purpose, not by arbitrary source type.
7. Assign each link a stable lowercase ID so local content can reference it without duplicating URLs.
8. Add one short "why this is useful" note per link. The note should connect the source to a design decision, tradeoff, implementation detail, or evaluation concern.
9. Reference link IDs from the relevant steps when the local schema supports step-level reading lists.
10. Validate the resulting artifact and cite the sources used in the final response.

## Search Strategy

Use several targeted searches instead of one broad query. Combine the domain name with implementation-focused terms:

```text
<topic> engineering blog architecture production
<topic> recommendation system company engineering blog
<topic> system design paper production
<topic> official docs benchmark repository
<company> <topic> engineering blog
```

For system-design interviews, usually collect 15-30 links across 4-6 groups. Typical groups:

- Industrial systems and architecture
- Company implementations
- Algorithms and foundations
- Data, storage, and platform tooling
- Evaluation, experimentation, and operations
- Hands-on toolkits, references, and benchmarks

Merge or rename groups to fit the topic. For example, a recommender-system list may use "Candidate Retrieval and Vector Search"; a payments list may use "Ledgers, Idempotency, and Reconciliation".

## Company Implementation Links

When the user asks for implemented systems, include a dedicated group such as "Company Implementations" or fold those links into "Industrial Systems and Architecture". Good candidates include:

- Engineering blog posts that describe a shipped architecture, migration, service, storage engine, model-serving path, or operational lesson.
- Public source repositories for production-adjacent systems.
- Research papers from teams that deployed the system.
- Official product docs only when they expose design-relevant details.

Do not overclaim. If a source is a paper, say it is a paper. If it is an engineering post, say it is a case study. If a source only implies production use, write the note as an inference.

## Output Shape

For JSON datasets that support `toProbeFurther`, use one canonical link list and reference it from steps:

```json
"steps": [
  {
    "id": "candidate-generation",
    "title": "1. Candidate Generation",
    "probeLinks": ["youtube-dnn", "faiss-docs"]
  }
],
"toProbeFurther": {
  "links": [
    {
      "id": "youtube-dnn",
      "group": "Company Implementations",
      "groupDescription": "Real shipped systems and production case studies.",
      "title": "Source title",
      "url": "https://example.com/source",
      "source": "Company or project",
      "type": "Case study",
      "year": "2025",
      "why": "Explains the tradeoff or implementation detail this reader should study."
    }
  ]
}
```

Use only http(s) URLs. Keep `year` when it is clear from the source; omit it rather than guessing. Use concise type labels such as `Case study`, `Paper`, `Docs`, `Repository`, `Benchmark`, `Tutorial`, or `Explainer`.

Prefer `toProbeFurther.links[]` over nested grouped link arrays. Put the group name on each link via `group`; put a short group summary on each link via `groupDescription` when useful. Do not duplicate link objects inside steps; steps should only store link IDs in `probeLinks`.

## Step Link Assignment

Attach links to steps where they deepen that exact design move:

- Candidate generation: retrieval-funnel papers, simple fallback/cold-start case studies, basic retrieval tutorials.
- ANN refinement: vector-search docs, ANN papers, benchmarks, graph-retrieval papers.
- Ranking: ranking-model case studies, large-scale model architecture papers, ranking toolkits.
- Features: feature-store docs, ML-platform posts, train/serve parity references.
- Filters/diversity: product ranking explainers, policy/diversity/reranking case studies, exploration references.
- Feedback: experimentation, counterfactual evaluation, logged bandit feedback, online learning references.
- Serving/resilience: production feed/retrieval engines, model-serving platforms, deployment best practices.

If a link belongs to several steps, reference the same ID from each step.

Legacy grouped shape may appear in older datasets:

```json
"toProbeFurther": [
  {
    "group": "Company Implementations",
    "links": [
      { "id": "youtube-dnn", "title": "Source title", "url": "https://example.com/source" }
    ]
  }
]
```

When editing, migrate legacy grouped data to the canonical `{"links": [...]}` shape unless the user explicitly asks for a minimal patch.

## File Editing

When adding links to this repository:

- Edit `data/<group>/<id>/interview.json`, not `docs/`.
- Preserve existing JSON fields and ordering where practical. Put `toProbeFurther` near other wrap-up fields, usually after `followUps` and before `assets`; put `probeLinks` near the step education fields.
- If adding a new renderer/schema field, update templates and `PLAN.md`; if the field already exists, only edit the dataset.
- Rebuild with `python3 build.py` after data or template changes.

## Validation

Before finalizing:

- Open enough source pages to verify titles, ownership, and relevance.
- Check for duplicate URLs and weak sources.
- Check that every `step.probeLinks[]` value resolves to exactly one `toProbeFurther.links[].id`.
- Validate JSON, for example `python3 -m json.tool data/.../interview.json`.
- Run project checks when applicable, such as `node --check _templates/interview.js`, `python3 build.py`, and `git diff --check`.
- In the final response, summarize the groups/counts added and include or reference the source links used.
