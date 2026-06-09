Today's Spec-Driven System Design Interview: Netflix — Video Streaming System Design.

The hard part of Netflix is not playing a video file. It is starting fast, avoiding rebuffering, and keeping bandwidth cost sane at tens of millions of viewers.

This walkthrough starts with the naive version: upload a file and stream it from origin. The math breaks fast. At ~60M viewers and ~5 Mbps average bitrate, the media path is around 300 Tbps, plus roughly 12-15M segment GETs/sec across the edge fleet.

From there, the design adds the machinery streaming platforms need: async transcoding, bitrate ladders, HLS/DASH packaging, CDN and ISP-edge distribution, adaptive bitrate logic in the player, playback sessions, entitlements, DRM licenses, QoE telemetry, and regional CDN steering.

The useful interview lesson: keep the hot media path separate from the control plane. Segments should flow from edge caches. Playback starts, rights checks, resume state, heartbeats, homepage reads, and recommendations all have different needs.

Technology choices make the trade-offs concrete: Open Connect-style appliances or managed CDNs such as CloudFront, Cloud CDN, Media CDN, and Azure Front Door; S3, Cloud Storage, or Blob Storage for origin; FFmpeg or managed transcoders; Kafka, Pub/Sub, or Event Hubs for QoE; and DynamoDB, Bigtable, Cosmos DB, Cassandra, or Redis for sessions.

Use the products as trade-off prompts, not a checklist.

Try the interactive walkthrough:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/interview.html#netflix

Explore the project/book catalog:
https://zeljkoobrenovic.github.io/spec-driven-system-design-interviews/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #Streaming
