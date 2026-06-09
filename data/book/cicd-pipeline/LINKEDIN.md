Today's Spec-Driven System Design Interview: CI/CD Pipeline for Microservices + Web + Mobile - System Design.

A good CI/CD design is not "run some YAML after every push." It is a distributed system for deciding what changed, running the minimum safe work, proving what was built, and promoting the exact same bytes through production.

It starts with the naive build box: one script, one queue, everything rebuilt, secrets in the wrong place, and no real rollback. Then it evolves into a DAG-based pipeline on ephemeral runners, affected-only builds, content-keyed caches, immutable signed artifacts, GitOps promotion, progressive delivery, observability gates, and a separate mobile release path.

The useful lesson is that each "modern" practice solves a specific failure mode:

Affected builds protect feedback time.
Hermetic runners protect reproducibility.
Artifact signing and provenance protect trust.
Canary and blue-green rollout protect users.
Crash gates and feature flags protect mobile releases, where instant rollback is not really available.

The technology choices make the trade-offs concrete: self-hosted Jenkins, Tekton, Argo, GitLab, or GitHub runners versus managed CodeBuild, Cloud Build, or Azure Pipelines; Kubernetes runner pools versus managed workers; Bazel or Gradle caches; Harbor or managed registries; Argo CD/Rollouts, Flux/Flagger, or Spinnaker; and Prometheus/Grafana or cloud observability.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#cicd-pipeline

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #DevOps #PlatformEngineering
