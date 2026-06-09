Today's Spec-Driven System Design Interview: Recommendation System — System Design.

The useful lesson is not "add ML." It is how to keep a recommender bounded, observable, and correct when every request wants personalization from a huge catalog.

The walkthrough builds the system in interview order: start with simple candidate sources, add embeddings and ANN as one recall path, rank only a few hundred candidates, fetch online features with train/serve parity, then apply eligibility, diversity, and policy filters before returning the final list.

That sequence matters. Scoring the whole catalog per request fails immediately. So does a clever ranker fed stale features, biased logs, or mismatched model and embedding versions. The case makes the hidden production work visible: exposure logging, client interaction ingest, feature freshness, compatible rollouts, cold start, fallbacks, and quality/drift monitoring.

It also connects classic architecture choices to modern implementations. You can discuss FAISS/HNSWlib/Milvus/Qdrant versus managed vector search, Feast/Redis/Cassandra versus managed feature stores, Kafka/Pulsar/Redpanda versus cloud streams, and Triton/TensorFlow Serving/MLflow versus managed model endpoints and registries. The point is not to memorize vendors; it is to explain the trade-offs they simplify or push back onto your team.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#recommendation

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #RecommendationSystems #MachineLearning #SoftwareArchitecture #Scalability
