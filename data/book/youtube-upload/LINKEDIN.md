Today's Spec-Driven System Design Interview: YouTube - Upload & Streaming - System Design.

The interesting part of "design YouTube" is not the brand name. It is where the hot path disappears.

A naive design uploads one huge file, stores it, and serves that original file back to every viewer. That is useful only because it breaks in all the right places: flaky multi-GB uploads restart from zero, one file cannot fit every network/device, transcoding blocks user flow, and the origin becomes the bottleneck for every segment request.

This walkthrough builds the system by removing those failure modes one at a time: resumable chunked upload with session and part state; async processing where a queue wakes workers but the task table owns leases, retries, and dead letters; segment-parallel transcoding into multiple renditions; HLS/DASH manifests for adaptive bitrate playback; CDN delivery where playback authorizes once and stays off the segment hot path.

Implementation choices are concrete too. You can compare NGINX/tusd or direct object-store multipart upload, Ceph/MinIO or S3/Cloud Storage/Blob Storage, Kafka/RabbitMQ or SQS/Pub/Sub/Service Bus, FFmpeg on Kubernetes or managed batch/transcoder services, and CDN signed URLs with playback tokens.

Practice lives in those trade-offs: where state belongs, what must be idempotent, which paths need strong correctness, and which counters can be eventually consistent.

Try the interactive walkthrough:
https://system-design-interviews.com/book/interview.html#youtube-upload

Explore the project/book catalog:
https://system-design-interviews.com/book/index.html

Free source code:
https://github.com/zeljkoobrenovic/spec-driven-system-design-interviews

#SystemDesign #SystemDesignInterview #SoftwareArchitecture #Scalability #MediaStreaming
