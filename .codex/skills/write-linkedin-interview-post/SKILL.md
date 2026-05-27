---
name: write-linkedin-interview-post
description: Draft engaging weekly LinkedIn posts for the Spec-Driven System Design project from local interview datasets or published interview URLs. Use when Codex is asked to promote a System Design Interview of the week, write a LinkedIn/social post for an interview such as data/<group>/<id>/interview.json, turn a spec-driven system design case into marketing/educational copy, or reuse the project's public links and GitHub source link in a post.
---

# Write LinkedIn Interview Post

## Overview

Create project-specific LinkedIn posts that promote one System Design Interview while teaching one concrete system design lesson. Ground the post in the local dataset, connect the interview's fundamentals to current technology choices, and include the Spec-Driven System Design project links.

## Workflow

1. Identify the interview.
   - If the user gives a published URL like `.../<group>/interview.html#<dataset>/<entry>`, parse `<group>`, `<dataset>`, and optional `<entry>`.
   - If the user gives only a dataset id, search `data/*/index.json` for the group and category.
   - Prefer local source files under `data/<group>/<dataset>/interview.json` over the generated `docs/` copy.

2. Build a compact briefing.
   - Run:

```bash
python3 .codex/skills/write-linkedin-interview-post/scripts/interview_brief.py --group <group> --id <dataset> --entry <entry>
```

   - If starting from a URL, run:

```bash
python3 .codex/skills/write-linkedin-interview-post/scripts/interview_brief.py --url "<published-url>"
```

3. Draft the post from the briefing.
   - Lead with a concrete hook, not a generic announcement.
   - Explain the educational value: what this interview helps people practice, why the basics still matter, and which trade-offs it makes visible.
   - Connect fundamentals to modern implementation choices: managed cloud services, serverless/container platforms, distributed databases, observability, queues, CDNs, identity, infrastructure automation, or other technology choices present in the dataset.
   - Promote the project with the public interview link, the book/examples index, and the GitHub source link.
   - Keep claims grounded in the dataset. Do not invent features, metrics, or publication cadence beyond what the user provides.

4. Polish for LinkedIn.
   - Length target: 1,200-1,900 characters unless the user asks otherwise.
   - Use short paragraphs with white space.
   - Include 3-5 hashtags at the end.
   - Avoid footnotes and citation-style prose inside the post.
   - Avoid emojis unless the user explicitly asks for them.
   - Keep the voice useful and specific: educational, builder-oriented, and lightly promotional.

## Default Link Set

Use the user's links when provided. Otherwise derive links from this base:

- Published interview: `https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/<group>/interview.html#<dataset>/<entry>`
- More examples: `https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/<group>/index.html`
- Source code: `https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews`

When the interview lives in `book`, describe the index link as the project/book catalog. When it lives in `examples`, describe it as worked examples.

## Post Shape

Use this shape unless the user requests a different style:

```text
This week's System Design Interview: <interview title>.

<Hook that names the lesson.>

<Why this case is educational: the fundamental progression, trade-offs, and interview practice value.>

<Bridge to current technologies: examples from technologyChoices, phrased as options rather than endorsements.>

Try the interactive walkthrough:
<published interview link>

Explore more examples:
<index link>

Free source code:
<GitHub link>

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability
```

## Quality Checklist

Before finalizing, verify:

- The title matches `interview.json`.
- The URL hash uses the requested dataset and entry.
- The post mentions both the educational lesson and the project.
- Technology examples come from `technologyChoices` or the step descriptions.
- The GitHub link is included when the user wants to promote the free source.
