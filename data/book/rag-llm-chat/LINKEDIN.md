Today's Spec-Driven System Design Interview: RAG / LLM Chat — System Design.

The hard part of RAG chat is not putting a vector database next to an LLM. It is keeping answers fast, grounded, tenant-safe, and affordable when every message can trigger embeddings, retrieval, reranking, prompt assembly, streaming, and token spend.

This walkthrough starts with a thin LLM proxy, then adds production pieces: conversation storage, context windows, streaming, async ingestion, chunking/embeddings, retrieval/reranking, grounded prompts, citations, caches, budgets, guardrails, and eval traces.

The core lesson: RAG quality is a systems problem, not just a model problem.

Chunking controls retrieval quality. Tenant and corpus filters control isolation. Prompt assembly controls context. Streaming controls perceived latency. Caches and token limits control cost. Evals and traces control whether model, embedding, reranker, or prompt changes are safe to ship.

The interview connects those fundamentals to current implementation choices: Bedrock, Vertex AI, and Azure OpenAI for model access; pgvector, Milvus, Qdrant, OpenSearch, and Azure AI Search for retrieval; SQS, Pub/Sub, and Service Bus for ingestion; Redis-style semantic caches and rate limiters; plus guardrails, WAFs, KMS, and secret stores around the hot path.

The tools reduce operational work. They do not design retrieval boundaries, token budgets, citation checks, reindexing flows, or quality gates.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#rag-llm-chat

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #AIEngineering #RAG
