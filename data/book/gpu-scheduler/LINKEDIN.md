Today's Spec-Driven System Design Interview: GPU Job Scheduler — System Design.

The hard part of GPU scheduling is not finding a free card. It is keeping accelerators busy while teams, priorities, distributed jobs, failures, and preemption share a scarce pool.

This walkthrough starts with the tempting FIFO queue, then shows why it breaks in a shared cluster: teams can starve, production work can wait behind best-effort jobs, hardware constraints matter, and a 64-GPU training job cannot start one replica at a time.

The design builds the control plane step by step: idempotent submission, durable pending state, priority queues, topology-aware bin-packing, gang scheduling, reservations, backfill, fair-share quotas, preemption, and reconciliation over job, attempt, and allocation records.

The core lesson is that metrics are not the source of truth. GPU utilization helps operators, but capacity is freed by authoritative agent status and leased allocations. Fair-share usage comes from allocation intervals, not sampled telemetry. Without that boundary, stale signals can double-run work or bill the wrong team.

Trade-offs are concrete: Kubernetes with Volcano or Kueue, Slurm, Ray, or managed training platforms for scheduling; PostgreSQL, etcd, or distributed SQL for durable state; indexed free lists for placement; object storage or parallel filesystems for checkpoints; and DCGM-style GPU signals for observability, not authority.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#gpu-scheduler

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AIInfrastructure #DistributedSystems
