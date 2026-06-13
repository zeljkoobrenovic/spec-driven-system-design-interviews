Today's Spec-Driven System Design Interview: AI Coding Agent CLI (Claude Code / Codex) — System Design.

Designing an AI coding CLI is not just "wrap a model in a terminal." It is a system for giving an untrusted model useful access to a developer's repo without letting bad guesses or prompt injection own the machine.

This walkthrough moves from one-shot prompt-to-patch to a production loop: search/read/edit/shell tools, context engineering, transcript compaction, permission gates, sandboxed execution, slash commands, skills, MCP, streaming inference, prefix caching, verification, subagents, and cloud agents that open PRs.

The core lesson: the agent is not the authority. The harness is.

The model chooses actions. The harness decides boundaries: context, tools, approvals, edit scope, transcript resume, and verification. That separation is what keeps the product useful when prompt injection, hallucinated commands, runaway loops, or failing tests appear.

The technology choices make the trade-offs concrete: ripgrep versus semantic indexes; JSONL or SQLite versus managed stores; OPA, Cedar, IAM, and Entra for policy; Docker, gVisor, Firecracker, or managed containers for isolation; provider APIs versus self-hosted serving; GitHub Actions, Buildkite, CodeBuild, Cloud Build, or Azure Pipelines for checks.

Managed tools reduce operations. They do not decide permissions, token budgets, cache-aware routing, retries, or human review.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#ai-coding-cli

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AIEngineering #DeveloperTools
