Design YouTube
In this chapter, you are asked to design YouTube. The solution to this question can be applied to other interview questions like designing a video sharing platform such as Netflix and Hulu. Figure 1 shows the YouTube homepage.

Image represents a screenshot of the YouTube website's homepage.  The left side displays a vertical menu bar with options for 'Sports,' 'Gaming,' 'Movies,' 'TV Shows,' 'News,' 'Live,' 'Fashion,' 'Spotlight,' '360° Video,' 'Browse channels,' and further options under 'MORE FROM YOUTUBE,' including 'YouTube Premium,' 'Live,' 'Settings,' 'Report history,' 'Help,' and 'Send feedback.'  The main area shows a grid of video thumbnails, each with a title, creator's name (often with a verified checkmark), view count, and upload date.  Examples include 'I edited a peppa pig episode cause I didn't know what else to post (part 2)' by Steph Inc., '14-year-old Alysa Liu makes history again at 2020 Nationals | NBC Sports' by NBC Sports, 'Building A Large Post Frame Garage Full Time-lapse Construction: NEVER...' by RR Buildings, and '3 Cool Gadgets - You Can Only Pick One.' by Unbox Therapy.  Each thumbnail displays a video duration.  At the top, a search bar is present with a search icon, and the user's profile icon is visible in the upper right corner, along with other settings icons.  The videos are arranged in a grid format, and no explicit connections are shown between them beyond their shared presence on the homepage.  Information flow is implicit; the user interacts with the menu and thumbnails to select and view videos.
Figure 1
YouTube looks simple: content creators upload videos and viewers click play. Is it really that simple? Not really. There are lots of complex technologies underneath the simplicity. Let us look at some impressive statistics, demographics, and fun facts of YouTube in 2020 [1] [2].

Total number of monthly active users: 2 billion.

Number of videos watched per day: 5 billion.

73% of US adults use YouTube.

50 million creators on YouTube

YouTube’s Ad revenue was $15.1 billion for the full year 2019, up 36% from 2018.

YouTube is responsible for 37% of all mobile internet traffic.

YouTube is available in 80 different languages.

From these statistics, we know YouTube is enormous, global and makes a lot of money.

Step 1 - Understand the problem and establish design scope
As revealed in Figure 1, besides watching a video, you can do a lot more on YouTube. For example, comment, share, or like a video, save a video to playlists, subscribe to a channel, etc. It is impossible to design everything within a 45- or 60-minute interview. Thus, it is important to ask questions to narrow down the scope.

Candidate: What features are important?
Interviewer: Ability to upload a video and watch a video.

Candidate: What clients do we need to support?
Interviewer: Mobile apps, web browsers, and smart TV.

Candidate: How many daily active users do we have?
Interviewer: 5 million

Candidate: What is the average daily time spent on the product?
Interviewer: 30 minutes.

Candidate: Do we need to support international users?
Interviewer: Yes, a large percentage of users are international users.

Candidate: What are the supported video resolutions?
Interviewer: The system accepts most of the video resolutions and formats.

Candidate: Is encryption required?
Interviewer: Yes

Candidate: Any file size requirement for videos?
Interviewer: Our platform focuses on small and medium-sized videos. The maximum allowed video size is 1GB.

Candidate: Can we leverage some of the existing cloud infrastructures provided by Amazon, Google, or Microsoft?
Interviewer: That is a great question. Building everything from scratch is unrealistic for most companies, it is recommended to leverage some of the existing cloud services.

In the chapter, we focus on designing a video streaming service with the following features:

Ability to upload videos fast

Smooth video streaming

Ability to change video quality

Low infrastructure cost

High availability, scalability, and reliability requirements

Clients supported: mobile apps, web browser, and smart TV

Back of the envelope estimation
The following estimations are based on many assumptions, so it is important to communicate with the interviewer to make sure she is on the same page.

Assume the product has 5 million daily active users (DAU).

Users watch 5 videos per day.

10% of users upload 1 video per day.

Assume the average video size is 300 MB.

Total daily storage space needed: 5 million * 10% * 300 MB = 150TB

CDN cost.

When cloud CDN serves a video, you are charged for data transferred out of the CDN.

Let us use Amazon’s CDN CloudFront for cost estimation (Figure 2) [3]. Assume 100% of traffic is served from the United States. The average cost per GB is $0.02. For simplicity, we only calculate the cost of video streaming.

5 million * 5 videos * 0.3GB * 
0.02
=
0.02=150,000 per day.

From the rough cost estimation, we know serving videos from the CDN costs lots of money. Even though cloud providers are willing to lower the CDN costs significantly for big customers, the cost is still substantial. We will discuss ways to reduce CDN costs in deep dive.

Image represents a table displaying pricing for cloud storage, differentiated by geographic region and data volume tiers.  The first column, 'Per Month,' indicates the pricing is per month. Subsequent columns represent different geographic regions: 'United States & Canada,' 'Europe & Israel,' 'South Africa, Kenya, & Middle East,' 'South America,' 'Japan,' 'Australia,' 'Singapore, South Korea, Taiwan, Hong Kong, & Philippines,' and 'India.'  Rows represent tiered data storage volumes: 'First 10TB,' 'Next 40TB,' 'Next 100TB,' 'Next 350TB,' 'Next 524TB,' 'Next 4PB,' and 'Over 5PB.' Each cell at the intersection of a region and volume tier shows the price (in USD) for that specific tier in that region.  For example, the price for the 'First 10TB' in 'United States & Canada' is $0.085, while the price for 'Next 4PB' in 'India' is $0.100.  The table clearly shows that pricing varies significantly across regions, with prices generally higher in Asia and lower in the Americas and Europe.
Figure 2
Step 2 - Propose high-level design and get buy-in
As discussed previously, the interviewer recommended leveraging existing cloud services instead of building everything from scratch. CDN and blob storage are the cloud services we will leverage. Some readers might ask why not building everything by ourselves? Reasons are listed below:

System design interviews are not about building everything from scratch. Within the limited time frame, choosing the right technology to do a job right is more important than explaining how the technology works in detail. For instance, mentioning blob storage for storing source videos is enough for the interview. Talking about the detailed design for blob storage could be an overkill.

Building scalable blob storage or CDN is extremely complex and costly. Even large companies like Netflix or Facebook do not build everything themselves. Netflix leverages Amazon’s cloud services [4], and Facebook uses Akamai’s CDN [5].

At the high-level, the system comprises three components (Figure 3).

Image represents a simplified system architecture diagram.  A light-blue rectangular box labeled 'Client' contains icons representing a laptop, a smartphone, and a TV set, indicating various client devices accessing the system.  From this 'Client' box, two arrows extend downwards. The left arrow, labeled 'streaming video,' points to a light-blue cloud icon with a lightning bolt inside, labeled 'CDN' (Content Delivery Network), suggesting that video content is delivered via a CDN. The right arrow, labeled 'everything else,' points to a light-green box containing three stacked server icons, labeled 'API servers,' indicating that all other requests are handled by application programming interfaces hosted on these servers.  The dashed lines around the CDN and API servers suggest these are separate components or clusters within the overall system.  The diagram illustrates a client-server architecture where video streaming is optimized through a CDN, while other functionalities are managed by the API servers.
Figure 3
Client: You can watch YouTube on your computer, mobile phone, and smartTV.

CDN: Videos are stored in CDN. When you press play, a video is streamed from the CDN.

API servers: Everything else except video streaming goes through API servers. This includes feed recommendation, generating video upload URL, updating metadata database and cache, user signup, etc.

In the question/answer session, the interviewer showed interests in two flows:

Video uploading flow

Video streaming flow

We will explore the high-level design for each of them.

Video uploading flow
Figure 4 shows the high-level design for the video uploading.

Image represents a system architecture diagram for video transcoding.  The process begins with a user (represented by icons for TV, laptop, and mobile phone) accessing the system through a load balancer that distributes requests to multiple API servers.  These servers interact with a Metadata Cache (containing three CACHE blocks) and a Metadata DB for video information.  The original video is fetched from an 'Original storage' (depicted as a bucket with shapes inside).  The API servers then direct the transcoding process to 'Transcoding servers' (three server icons). Upon completion of transcoding, signaled by a 'transcoding complete' message, the information is added to a 'Completion queue' (three mail icons). A 'Completion handler' (three document icons) processes this queue, and the transcoded video is stored in 'Transcoded storage' (another bucket icon), finally being delivered to users via a CDN (cloud icon with a lightning bolt).  The entire flow is depicted using boxes and arrows, showing the data flow and interactions between different components.
Figure 4
It consists of the following components:

User: A user watches YouTube on devices such as a computer, mobile phone, or smart TV.

Load balancer: A load balancer evenly distributes requests among API servers.

API servers: All user requests go through API servers except video streaming.

Metadata DB: Video metadata are stored in Metadata DB. It is sharded and replicated to meet performance and high availability requirements.

Metadata cache: For better performance, video metadata and user objects are cached.

Original storage: A blob storage system is used to store original videos. A quotation in Wikipedia regarding blob storage shows that: “A Binary Large Object (BLOB) is a collection of binary data stored as a single entity in a database management system” [6].

Transcoding servers: Video transcoding is also called video encoding. It is the process of converting a video format to other formats (MPEG, HLS, etc), which provide the best video streams possible for different devices and bandwidth capabilities.

Transcoded storage: It is a blob storage that stores transcoded video files.

CDN: Videos are cached in CDN. When you click the play button, a video is streamed from the CDN.

Completion queue: It is a message queue that stores information about video transcoding completion events.

Completion handler: This consists of a list of workers that pull event data from the completion queue and update metadata cache and database.

Now that we understand each component individually, let us examine how the video uploading flow works. The flow is broken down into two processes running in parallel.

a. Upload the actual video.

b. Update video metadata. Metadata contains information about video URL, size, resolution, format, user info, etc.

Flow a: upload the actual video
Image represents a system architecture diagram for video transcoding and delivery.  A user (accessing via TV, laptop, or mobile) initiates a request (1) to retrieve a video from the original storage (represented by a bucket icon). This request goes through a load balancer (4) which distributes the traffic to API servers. The API servers interact with a Metadata Cache and a Metadata DB to retrieve video information. The original video is then fetched (2) and sent to transcoding servers (3) which process the video. Upon completion (3b), a 'transcoding complete' message is sent to a Completion queue.  The Completion handler (3b.1) processes this message, updating the Metadata DB (3b.1.a and 3b.1.b). Finally, the transcoded video (3a) is stored in transcoded storage (another bucket icon) and then pushed to a CDN (3a.1) for efficient content delivery to the user.  The Metadata Cache improves performance by caching frequently accessed metadata.  The numbered arrows indicate the flow of information and requests between components.
Figure 5
Figure 5 shows how to upload the actual video. The explanation is shown below:

1. Videos are uploaded to the original storage.

2. Transcoding servers fetch videos from the original storage and start transcoding.

3. Once transcoding is complete, the following two steps are executed in parallel:

3a. Transcoded videos are sent to transcoded storage.

3b. Transcoding completion events are queued in the completion queue.

3a.1. Transcoded videos are distributed to CDN.

3b.1. Completion handler contains a bunch of workers that continuously pull event data from the queue.

3b.1.a. and 3b.1.b. Completion handler updates the metadata database and cache when video transcoding is complete.

4. API servers inform the client that the video is successfully uploaded and is ready for streaming.

Flow b: update the metadata
While a file is being uploaded to the original storage, the client in parallel sends a request to update the video metadata as shown in Figure 6. The request contains video metadata, including file name, size, format, etc. API servers update the metadata cache and database.

Image represents a system architecture for managing metadata.  Users (represented by icons for TV, laptop, and mobile phone) initiate requests to update metadata. These requests are sent to a load balancer, which distributes the traffic across multiple API servers.  The API servers are responsible for processing the metadata updates.  To improve performance, the system incorporates a Metadata Cache, which stores frequently accessed metadata.  If the API servers cannot find the requested metadata in the cache, they retrieve it from the Metadata DB, a database storing all metadata.  The arrows indicate the flow of information, showing how user requests travel through the load balancer to the API servers, which then interact with the cache and database as needed.  The dashed line around the API servers highlights them as a cluster.
Figure 6
Video streaming flow
Whenever you watch a video on YouTube, it usually starts streaming immediately and you do not wait until the whole video is downloaded. Downloading means the whole video is copied to your device, while streaming means your device continuously receives video streams from remote source videos. When you watch streaming videos, your client loads a little bit of data at a time so you can watch videos immediately and continuously.

Before we discuss video streaming flow, let us look at an important concept: streaming protocol. This is a standardized way to control data transfer for video streaming. Popular streaming protocols are:

MPEG–DASH. MPEG stands for “Moving Picture Experts Group” and DASH stands for "Dynamic Adaptive Streaming over HTTP".

Apple HLS. HLS stands for “HTTP Live Streaming”.

Microsoft Smooth Streaming.

Adobe HTTP Dynamic Streaming (HDS).

You do not need to fully understand or even remember those streaming protocol names as they are low-level details that require specific domain knowledge. The important thing here is to understand that different streaming protocols support different video encodings and playback players. When we design a video streaming service, we have to choose the right streaming protocol to support our use cases. To learn more about streaming protocols, here is an excellent article [7].

Videos are streamed from CDN directly. The edge server closest to you will deliver the video. Thus, there is very little latency. Figure 7 shows a high level of design for video streaming.

Image represents a simple client-server architecture for streaming video.  A light-blue rectangular box labeled 'Client' contains icons representing a laptop, a smartphone, and a smart TV, indicating that these devices can all access the service. A downward-pointing arrow, labeled 'streaming video,' connects the Client box to a dashed-line box representing a Content Delivery Network (CDN). This CDN box is light-blue and depicts a cloud with a lightning bolt inside, symbolizing fast data delivery. The overall diagram illustrates how multiple client devices request and receive streaming video content from a CDN, which is optimized for fast content distribution.
Figure 7
Step 3 - Design deep dive
In the high-level design, the entire system is broken down in two parts: video uploading flow and video streaming flow. In this section, we will refine both flows with important optimizations and introduce error handling mechanisms.

Video transcoding
When you record a video, the device (usually a phone or camera) gives the video file a certain format. If you want the video to be played smoothly on other devices, the video must be encoded into compatible bitrates and formats. Bitrate is the rate at which bits are processed over time. A higher bitrate generally means higher video quality. High bitrate streams need more processing power and fast internet speed.

Video transcoding is important for the following reasons:

Raw video consumes large amounts of storage space. An hour-long high definition video recorded at 60 frames per second can take up a few hundred GB of space.

Many devices and browsers only support certain types of video formats. Thus, it is important to encode a video to different formats for compatibility reasons.

To ensure users watch high-quality videos while maintaining smooth playback, it is a good idea to deliver higher resolution video to users who have high network bandwidth and lower resolution video to users who have low bandwidth.

Network conditions can change, especially on mobile devices. To ensure a video is played continuously, switching video quality automatically or manually based on network conditions is essential for smooth user experience.

Many types of encoding formats are available; however, most of them contain two parts:

Container: This is like a basket that contains the video file, audio, and metadata. You can tell the container format by the file extension, such as .avi, .mov, or .mp4.

Codecs: These are compression and decompression algorithms aim to reduce the video size while preserving the video quality. The most used video codecs are H.264, VP9, and HEVC.

Directed acyclic graph (DAG) model
Transcoding a video is computationally expensive and time-consuming. Besides, different content creators may have different video processing requirements. For instance, some content creators require watermarks on top of their videos, some provide thumbnail images themselves, and some upload high definition videos, whereas others do not.

To support different video processing pipelines and maintain high parallelism, it is important to add some level of abstraction and let client programmers define what tasks to execute. For example, Facebook’s streaming video engine uses a directed acyclic graph (DAG) programming model, which defines tasks in stages so they can be executed sequentially or parallelly [8]. In our design, we adopt a similar DAG model to achieve flexibility and parallelism. Figure 8 represents a DAG for video transcoding.

Image represents a data processing pipeline for video production.  An 'Original video' block feeds into two parallel processing paths. The first path extracts the 'Video' stream, which then feeds into a 'Tasks' group. This group contains several sequential processing steps: 'Inspection', 'Video...' (suggesting further video processing), 'Thumbnail' generation, and finally 'Watermark' addition.  The second path extracts the 'Audio' stream, which undergoes processing in an 'Audio...' block.  The 'Metadata' from the original video is also extracted separately.  Finally, the processed 'Video...' stream from the 'Tasks' group, the processed 'Audio...' stream, and the 'Metadata' are all combined in an 'Assemble' block to create the final output video.  The connections between blocks are represented by arrows indicating the flow of data.  The 'Tasks' group is visually separated by a dashed line.
Figure 8
In Figure 8, the original video is split into video, audio, and metadata. Here are some of the tasks that can be applied on a video file:

Inspection: Make sure videos have good quality and are not malformed.

Video encodings: Videos are converted to support different resolutions, codec, bitrates, etc. Figure 9 shows an example of video encoded files.

Thumbnail. Thumbnails can either be uploaded by a user or automatically generated by the system.

Watermark: An image overlay on top of your video contains identifying information about your video.

Image represents a simplified diagram of a video delivery system.  A central rectangular box labeled 'Video...' acts as the source, representing a video file needing to be delivered in various resolutions.  From this source, five horizontal lines extend to the right, each connecting to a separate rectangular box representing different video quality levels. These boxes are labeled '360p.mp4', '480p.mp4', '720p.mp4', '1080p.mp4', and '4k.mp4', indicating the resolution of each video file.  The arrows on the lines indicate the direction of data flow, showing that the source provides the video file in multiple resolutions.  At the bottom of the diagram, a small text note reads 'Viewer does not support full SVG 1.1', suggesting a limitation of the video player that might affect the display of certain video metadata or formats.
Figure 9
Video transcoding architecture
The proposed video transcoding architecture that leverages the cloud services, is shown in Figure 10.

Image represents a data processing pipeline for video encoding.  The pipeline begins with a 'Preprocessor' component, which feeds data into a 'DAG scheduler'. The scheduler then passes the processed data to a 'Resource manager', which allocates resources for the next stage.  The 'Resource manager' outputs data to 'Task workers', which perform the actual video encoding. The encoded video is then outputted as 'Encoded video'.  Separately, a direct connection exists from the 'Preprocessor' to a 'Temporary...' storage component, suggesting intermediate results or data are stored temporarily. Finally, the 'Task workers' send their output back to the 'Temporary...' storage, implying that the encoded video might be stored there before final delivery.  The arrows indicate the direction of data flow between components.  A note at the bottom indicates that the viewer does not fully support the SVG format of the diagram.
Figure 10
The architecture has six main components: preprocessor, DAG scheduler, resource manager, task workers, temporary storage, and encoded video as the output. Let us take a close look at each component.

Preprocessor
Image represents a data processing pipeline for video encoding.  The pipeline begins with a `Preprocessor` (light blue box) which feeds data into a `DAG scheduler` (light teal box). The scheduler then passes the data to a `Resource manager` (light teal box), which in turn sends tasks to `Task workers` (light teal box).  The `Task workers` process the data and produce an `Encoded video` (light teal box).  Separately, a direct connection exists from the `Preprocessor` to a `Temporary...` storage (light teal box), suggesting intermediate data is stored there. Finally, a vertical connection shows data flowing from the `Task workers` back to the `Temporary...` storage, implying that the results of the task workers are also stored temporarily.  The text 'Viewer does not support full SVG 1.1' is present below the diagram, indicating a limitation of the viewer used to display the image.
Figure 11
The preprocessor has 4 responsibilities:

1. Video splitting. Video stream is split or further split into smaller Group of Pictures (GOP) alignment. GOP is a group/chunk of frames arranged in a specific order. Each chunk is an independently playable unit, usually a few seconds in length.

2. Some old mobile devices or browsers might not support video splitting. Preprocessor split videos by GOP alignment for old clients.

3. DAG generation. The processor generates DAG based on configuration files client programmers write. Figure 12 is a simplified DAG representation which has 2 nodes and 1 edge:

Image represents a simplified data flow diagram showing a two-stage process.  The diagram consists of two rectangular boxes with rounded corners, connected by a directed arrow. The first box is labeled 'Download,' indicating a stage where data is retrieved.  Below this label, smaller text reads 'Viewer does not support full SVG 1.1,' suggesting a constraint or limitation on the input data's format. The second box is labeled 'Transcode,' signifying a subsequent stage where the downloaded data is converted or processed into a different format.  A solid blue arrow points from the 'Download' box to the 'Transcode' box, illustrating the unidirectional flow of data from the download stage to the transcoding stage.  The overall diagram depicts a sequence where data is first downloaded and then undergoes a transcoding process, likely due to compatibility issues as indicated by the text under the 'Download' box.
Figure 12
This DAG representation is generated from the two configuration files below (Figure 13):

Image represents a pair of code snippets, likely depicting two sequential tasks within a workflow, possibly for video processing.  Each snippet defines a 'task' with attributes 'name' and 'type'. The left snippet defines a 'download-input' task of type 'Download', taking a URL from 'config.url' as input and assigning the downloaded file (it.file) to 'context.inputVideo' in the output.  The 'next' attribute specifies 'transcode' as the subsequent task. The right snippet defines a 'transcode' task of type 'Transcode', taking 'context.inputVideo' and 'config.transConfig' as input and assigning the transcoded video (it.outputVideo) to 'context.file' in the output.  Both snippets include a three-color indicator (red, yellow, green) at the top, possibly representing task status (e.g., failed, running, success). The overall structure suggests a data flow where the output of the 'download-input' task feeds into the input of the 'transcode' task, forming a pipeline.
Figure 13 (source: [9])
4. Cache data. The preprocessor is a cache for segmented videos. For better reliability, the preprocessor stores GOPs and metadata in temporary storage. If video encoding fails, the system could use persisted data for retry operations.

DAG scheduler
Image represents a data processing pipeline for video encoding.  The pipeline begins with a 'Preprocessor' component, which feeds data into a 'DAG scheduler'.  The DAG scheduler, depicted in light blue, then passes the scheduled tasks to a 'Resource manager' component.  The resource manager allocates resources and sends the tasks to 'Task workers'.  The task workers perform the video encoding, and the results are sent to an 'Encoded video' component.  Separately, a direct connection exists from the 'Preprocessor' to a 'Temporary...' component, suggesting temporary storage or intermediate processing steps. Finally, the 'Task workers' send their output to the 'Temporary...' component, indicating that the encoded video might be temporarily stored before reaching the final 'Encoded video' destination.  The text 'Viewer does not support full SVG 1.1' is present below the diagram, indicating a limitation of the viewer used to display the image.
Figure 14
The DAG scheduler splits a DAG graph into stages of tasks and puts them in the task queue in the resource manager. Figure 15 shows an example of how the DAG scheduler works.

Image represents a data processing pipeline managed by a DAG (Directed Acyclic Graph) scheduler.  The pipeline is divided into two stages.  The process begins with an 'Original...' input (presumably a raw media file) which is fed into Stage 1.  In Stage 1, the original input is processed into three separate streams: 'Video,' 'Audio,' and 'Metadata.'  These streams are then passed to Stage 2. In Stage 2, the 'Video' stream is further processed into a 'Video...' output (likely a processed or encoded video file).  The 'Audio' stream is processed into an 'Audio...' output (likely a processed or encoded audio file).  Additionally, a 'Thumbnail' is generated from the 'Video' stream in Stage 2.  The dashed vertical lines separate the stages, illustrating the flow of data from one stage to the next.  The entire pipeline is enclosed within a rounded rectangle labeled 'DAG scheduler,' indicating the overall management of the workflow.
Figure 15
As shown in Figure 15, the original video is split into three stages: Stage 1: video, audio, and metadata. The video file is further split into two tasks in stage 2: video encoding and thumbnail. The audio file requires audio encoding as part of the stage 2 tasks.

Resource manager
Image represents a data processing pipeline for video encoding.  The pipeline begins with a `Preprocessor` which feeds data into a `DAG scheduler`. The scheduler, in turn, interacts with a `Resource manager` to allocate resources for the encoding tasks.  The `Resource manager` then sends tasks to `Task workers`, which perform the actual video encoding. The output of the `Task workers` is an `Encoded video`.  A separate connection runs from the `Preprocessor` directly to a `Temporary...` storage (the ellipsis suggests a truncated label, possibly indicating a temporary storage location or file system). Finally, there's a vertical connection from the `Task workers` back to the `Temporary...` storage, implying that intermediate or final results are stored there.  The text 'Viewer does not support full SVG 1.1' at the bottom indicates a limitation of the viewer used to display the diagram, not a component of the pipeline itself.  All connections are represented by arrows indicating the direction of data flow.
Figure 16
The resource manager is responsible for managing the efficiency of resource allocation. It contains 3 queues and a task scheduler as shown in Figure 17.

Task queue: It is a priority queue that contains tasks to be executed.

Worker queue: It is a priority queue that contains worker utilization info.

Running queue: It contains info about the currently running tasks and workers running the tasks.

•Task scheduler: It picks the optimal task/worker, and instructs the chosen task worker to execute the job.

Image represents a system for task scheduling and execution.  The system is composed of three main components: a Resource Manager, a Task Scheduler, and a set of Task Workers.  Three queues—Task queue, Worker queue, and Running queue—are depicted as sources of tasks and worker information. The Resource Manager interacts with these queues, selecting the highest priority task from the Task queue and the optimal worker from the Worker queue.  This information is then passed to the Task Scheduler, which, in turn, sends the selected task to an appropriate Task Worker ('run task'). The Task Scheduler also receives task/worker information from the Running queue. The Task Workers are represented as four distinct units: Watermark, Encoder, Thumbnail, and Merger, suggesting different processing functions.  The dashed lines around the Task Scheduler and Task Workers indicate logical groupings.  The arrows show the flow of information and tasks between components.
Figure 17
The resource manager works as follows:

The task scheduler gets the highest priority task from the task queue.

The task scheduler gets the optimal task worker to run the task from the worker queue.

The task scheduler instructs the chosen task worker to run the task.

The task scheduler binds the task/worker info and puts it in the running queue.

The task scheduler removes the job from the running queue once the job is done.

Task workers
Image represents a data processing pipeline for video encoding.  The pipeline begins with a 'Preprocessor' component, which feeds data into a 'DAG scheduler'. The scheduler then passes the data to a 'Resource manager', which in turn sends it to 'Task workers'.  These workers process the data, and the results are sent to a 'Temporary...' storage location (the exact name is truncated).  Finally, the processed data, representing the 'Encoded video', is output from the 'Task workers'.  The 'Preprocessor' is connected to the 'Temporary...' storage via a separate, direct connection, suggesting a possible bypass or alternative data path.  The entire flow is depicted using rectangular boxes representing components and arrows indicating the direction of data flow.  A note at the bottom indicates that the viewer does not fully support the SVG format of the image.
Figure 18
Task workers run the tasks which are defined in the DAG. Different task workers may run different tasks as shown in Figure 19.

Image represents a simplified architecture diagram of a task worker system, likely within a larger media processing pipeline.  The diagram is enclosed by a dashed-line box labeled 'Task workers'. Inside, four identical-looking green boxes, each representing a specific task worker, are arranged in a 2x2 grid.  Each box contains a stacked icon suggesting multiple processing units within each worker.  The top-left box is labeled 'Watermark', the top-right 'Encoder', the bottom-left 'Thumbnail', and the bottom-right 'Merger'.  An ellipsis ('...') between the top and bottom rows indicates that more task workers of similar design might exist beyond those shown.  The diagram's caption, 'Viewer does not support full SVG 1.1', suggests a limitation in the visualization tool used to create the diagram, not a limitation within the system itself.  No explicit data flow is shown between the workers, implying that the interaction is implicit or handled by a higher-level orchestrator not depicted in this simplified view.
Figure 19
Temporary storage
Image represents a data processing pipeline for video encoding.  The pipeline begins with a 'Preprocessor' component, which feeds data into a 'DAG scheduler'. The scheduler then passes the data to a 'Resource manager', which allocates resources for the next stage.  The 'Resource manager' outputs data to 'Task workers', which perform the actual video encoding. The encoded video is then outputted as 'Encoded video'.  Separately, a line connects the 'Preprocessor' to a 'Temporary...' storage component, suggesting intermediate results or data are stored temporarily before proceeding to the next stages.  Finally, an upward arrow indicates that the 'Task workers' send data back to the 'Temporary...' storage, possibly for aggregation or further processing.  The flow is unidirectional between each component except for the feedback loop between 'Task workers' and 'Temporary...'.
Figure 20
Multiple storage systems are used here. The choice of storage system depends on factors like data type, data size, access frequency, data life span, etc. For instance, metadata is frequently accessed by workers, and the data size is usually small. Thus, caching metadata in memory is a good idea. For video or audio data, we put them in blob storage. Data in temporary storage is freed up once the corresponding video processing is complete.

Encoded video
Image represents a data processing pipeline for video encoding.  The pipeline begins with a 'Preprocessor' component, which processes the raw video data.  The output of the preprocessor feeds into a 'DAG scheduler', responsible for orchestrating the subsequent tasks according to a directed acyclic graph (DAG). The DAG scheduler then passes the scheduled tasks to a 'Resource manager' component, which allocates resources (e.g., computing power) to the tasks.  The resource manager's output is sent to 'Task workers', which perform the actual video encoding operations.  The encoded video segments are then sent to a 'Temporary...' storage (likely a temporary storage location), and finally, the fully encoded video is outputted as 'Encoded video'.  A single line connects the 'Preprocessor' directly to the 'Temporary...' storage, suggesting a possible alternative or parallel processing path.  The text 'Viewer does not support full SVG 1.1' indicates a limitation of the viewer used to display the diagram, not a component of the pipeline itself.
Figure 21
Encoded video is the final output of the encoding pipeline. Here is an example of the output: funny_720p.mp4.

System optimizations
At this point, you ought to have good understanding about the video uploading flow, video streaming flow and video transcoding. Next, we will refine the system with optimizations, including speed, safety, and cost-saving.

Speed optimization: parallelize video uploading
Uploading a video as a whole unit is inefficient. We can split a video into smaller chunks by GOP alignment as shown in Figure 22.

Image represents a process of splitting a video into smaller segments.  A rectangular box labeled 'Original video' containing a blue video camera icon represents the input video. A thin, blue arrow connects this box to another rectangular area divided into multiple smaller, equal-sized rectangles.  Each smaller rectangle is labeled sequentially as 'GOP 1,' 'GOP 2,' ..., 'GOP N,' representing individual Group of Pictures (GOPs). The text 'Split by GOP alignme...' above the arrow indicates that the original video is being split based on GOP alignment. Below the arrow, the text 'Viewer does not support full SVG 1.1' suggests a limitation in the visualization tool.  The overall diagram illustrates the process of segmenting a video stream into manageable GOP units for processing or transmission.
Figure 22
This allows fast resumable uploads when the previous upload failed. The job of splitting a video file by GOP can be implemented by the client to improve the upload speed as shown in Figure 23.

Image represents a system architecture diagram illustrating data distribution from an original storage to multiple clients.  A green bucket icon labeled 'Original storage' contains various geometric shapes, symbolizing data.  Three rectangular boxes labeled 'GOP1,' 'GOP2,' and 'GOP3' represent three separate data distribution points or servers.  Data flows unidirectionally from the 'Original storage' to each of these GOPs, indicated by arrows pointing left.  A light-blue rounded rectangle labeled 'Client' contains icons representing a TV, a laptop, and a smartphone, indicating different client devices.  Data flows unidirectionally from each GOP to the 'Client' block, also shown with arrows pointing left.  The overall structure shows a replication or distribution strategy where the original data is copied to multiple GOPs, which then serve the data to various client devices.
Figure 23
Speed optimization: place upload centers close to users
Another way to improve the upload speed is by setting up multiple upload centers across the globe (Figure 24). People in the United States can upload videos to the North America upload center, and people in China can upload videos to the Asian upload center. To achieve this, we use CDN as upload centers.

Image represents a world map illustrating a distributed upload center architecture.  The map shows four colored regions representing geographical locations: the United States (purple), Brazil (light green), China (red), and a region encompassing most of Europe (dark blue).  Each region contains a black dot indicating the location of an upload center.  Four blue circles, labeled 'North America upload center,' 'Asian upload center,' 'Europe upload center,' and 'South America upload center,' are positioned outside the map's boundaries.  Straight blue lines connect each of these labeled upload centers to the corresponding black dot on the map, visually representing a connection or data flow between the geographical location and its designated upload center.  The overall diagram suggests a system where data from various geographical regions is uploaded to geographically distributed centers for processing or storage, likely to improve latency and availability.
Figure 24
Speed optimization: parallelism everywhere
Achieving low latency requires serious efforts. Another optimization is to build a loosely coupled system and enable high parallelism.

Our design needs some modifications to achieve high parallelism. Let us zoom in to the flow of how a video is transferred from original storage to the CDN. The flow is shown in Figure 25, revealing that the output depends on the input of the previous step. This dependency makes parallelism difficult.

Image represents a video processing and distribution pipeline.  The process begins with an 'Original storage' block (a green bucket icon), representing the initial storage location of original videos.  These videos are downloaded ('download original se...') by a 'Download...' block (depicted as a stack of green files), which then segments the video ('original segmented v...') and sends the segments to an 'Encoding...' block (a stack of blue files). This block processes the video segments, creating encoded versions ('encoded videos'). The encoded videos are then uploaded ('upload...') to an 'Upload...' block (a stack of orange files), which finally uploads them to a 'CDN' (Content Delivery Network) block (a light blue cloud with a lightning bolt), for efficient distribution to viewers.  Separately, a lower path shows encoded videos being uploaded directly to the 'Encoded...' block (a green bucket icon), suggesting an alternative upload method for already encoded videos.  All blocks are outlined with dashed lines except for the 'Original storage' and 'Encoded...' blocks.  The text labels clearly indicate the data flow and the function of each component.
Figure 25
To make the system more loosely coupled, we introduced message queues as shown in Figure 26. Let us use an example to explain how message queues make the system more loosely coupled.

Before the message queue is introduced, the encoding module must wait for the output of the download module.

After the message queue is introduced, the encoding module does not need to wait for the output of the download module anymore. If there are events in the message queue, the encoding module can execute those jobs in parallel.

Image represents a system architecture diagram illustrating a media processing pipeline.  The process begins with 'Original storage,' depicted as a bucket icon, containing the original media files.  These files are then placed into a 'Message queue' (represented by a series of email icons), triggering the 'Download...' process, a block representing a server cluster that retrieves the files.  After downloading, the files are sent to another 'Message queue,' which feeds into the 'Encoding...' process, another server cluster that encodes the media.  Encoded files are then placed into a third 'Message queue,' leading to the 'Encoded...' storage, another bucket icon representing storage for the processed files.  Finally, the 'Encoded...' files are uploaded to a 'CDN' (Content Delivery Network), represented by a cloud icon with a lightning bolt, via an 'upload...' step.  A separate branch shows a similar process, but instead of encoding, the files are directly uploaded to the CDN after being placed in a message queue and processed by the 'Upload...' server cluster.  The entire system relies on message queues to manage the flow of data between different processing stages.
Figure 26
Safety optimization: pre-signed upload URL
Safety is one of the most important aspects of any product. To ensure only authorized users upload videos to the right location, we introduce pre-signed URLs as shown in Figure 27.

Image represents a simplified system architecture for video uploading.  A user, represented by icons for a TV, laptop, and smartphone, initiates a video upload (labeled '3. upload video'). This action sends a request to a set of 'API servers,' depicted as three stacked green rectangles within a dashed-line box.  The API servers respond with a 'pre-signed URL' (labeled '2. <pre-signed URL>') which the user then uses to upload the video directly to the 'Original storage,' represented by a bucket icon labeled 'Original storage' and connected by an arrow labeled '3. upload video'. The initial user request to the API servers is labeled '1. POST /upload,' indicating a POST HTTP request is used to initiate the upload process.  The overall flow shows a two-step process:  first, obtaining a pre-signed URL from the API servers, and second, using that URL to upload the video to the designated storage location.
Figure 27
The upload flow is updated as follows:

1. The client makes a HTTP request to API servers to fetch the pre-signed URL, which gives the access permission to the object identified in the URL. The term pre-signed URL is used by uploading files to Amazon S3. Other cloud service providers might use a different name. For instance, Microsoft Azure blob storage supports the same feature, but call it “Shared Access Signature” [10].

2. API servers respond with a pre-signed URL.

3. Once the client receives the response, it uploads the video using the pre-signed URL.

Safety optimization: protect your videos
Many content makers are reluctant to post videos online because they fear their original videos will be stolen. To protect copyrighted videos, we can adopt one of the following three safety options:

Digital rights management (DRM) systems: Three major DRM systems are Apple FairPlay, Google Widevine, and Microsoft PlayReady.

AES encryption: You can encrypt a video and configure an authorization policy. The encrypted video will be decrypted upon playback. This ensures that only authorized users can watch an encrypted video.

Visual watermarking: This is an image overlay on top of your video that contains identifying information for your video. It can be your company logo or company name.

Cost-saving optimization
CDN is a crucial component of our system. It ensures fast video delivery on a global scale. However, from the back of the envelope calculation, we know CDN is expensive, especially when the data size is large. How can we reduce the cost?

Previous research shows that YouTube video streams follow long-tail distribution [11] [12]. It means a few popular videos are accessed frequently but many others have few or no viewers. Based on this observation, we implement a few optimizations:

1. Only serve the most popular videos from CDN and other videos from our high capacity storage video servers (Figure 28).

Image represents a system architecture for video streaming.  A central 'User' block depicts a user accessing videos through various devices: a TV set-top box, a laptop, and a smartphone.  This User block connects to two other components.  One connection, labeled 'most popular videos,' points to a dashed-line box labeled 'CDN' (Content Delivery Network), represented as a cloud with a lightning bolt, symbolizing fast content delivery. The other connection, labeled 'other videos,' points to another dashed-line box labeled 'Video servers,' depicted as a cluster of three vertically stacked servers, suggesting a more traditional video storage and delivery system.  The architecture implies that highly popular videos are served from the CDN for faster access, while less popular videos are retrieved directly from the video servers.  The arrows indicate the direction of video data flow from the servers and CDN to the user's devices.
Figure 28
2. For less popular content, we may not need to store many encoded video versions. Short videos can be encoded on-demand.

3. Some videos are popular only in certain regions. There is no need to distribute these videos to other regions.

4. Build your own CDN like Netflix and partner with Internet Service Providers (ISPs). Building your CDN is a giant project; however, this could make sense for large streaming companies. An ISP can be Comcast, AT&T, Verizon, or other internet providers. ISPs are located all around the world and are close to users. By partnering with ISPs, you can improve the viewing experience and reduce the bandwidth charges.

All those optimizations are based on content popularity, user access pattern, video size, etc. It is important to analyze historical viewing patterns before doing any optimization. Here are some of the interesting articles on this topic: [12] [13].

Error handling
For a large-scale system, system errors are unavoidable. To build a highly fault-tolerant system, we must handle errors gracefully and recover from them fast. Two types of errors exist:

Recoverable error. For recoverable errors such as video segment fails to transcode, the general idea is to retry the operation a few times. If the task continues to fail and the system believes it is not recoverable, it returns a proper error code to the client.

Non-recoverable error. For non-recoverable errors such as malformed video format, the system stops the running tasks associated with the video and returns the proper error code to the client.

Typical errors for each system component are covered by the following playbook:

Upload error: retry a few times.

Split video error: if older versions of clients cannot split videos by GOP alignment, the entire video is passed to the server. The job of splitting videos is done on the server-side.

Transcoding error: retry.

Preprocessor error: regenerate DAG diagram.

DAG scheduler error: reschedule a task.

Resource manager queue down: use a replica.

Task worker down: retry the task on a new worker.

API server down: API servers are stateless so requests will be directed to a different API server.

Metadata cache server down: data is replicated multiple times. If one node goes down, you can still access other nodes to fetch data. We can bring up a new cache server to replace the dead one.

Metadata DB server down:

Master is down. If the master is down, promote one of the slaves to act as the new master.

Slave is down. If a slave goes down, you can use another slave for reads and bring up another database server to replace the dead one.

Step 4 - Wrap up
In this chapter, we presented the architecture design for video streaming services like YouTube. If there is extra time at the end of the interview, here are a few additional points:

Scale the API tier: Because API servers are stateless, it is easy to scale API tier horizontally.

Scale the database: You can talk about database replication and sharding.

Live streaming: It refers to the process of how a video is recorded and broadcasted in real time. Although our system is not designed specifically for live streaming, live streaming and non-live streaming have some similarities: both require uploading, encoding, and streaming. The notable differences are:

Live streaming has a higher latency requirement, so it might need a different streaming protocol.

Live streaming has a lower requirement for parallelism because small chunks of data are already processed in real-time.

Live streaming requires different sets of error handling. Any error handling that takes too much time is not acceptable.

Video takedowns: Videos that violate copyrights, pornography, or other illegal acts shall be removed. Some can be discovered by the system during the upload process, while others might be discovered through user flagging.

Congratulations on getting this far! Now give yourself a pat on the back. Good job!

Reference materials
[1] YouTube by the numbers:
https://www.omnicoreagency.com/youtube-statistics/

[2] 2019 YouTube Demographics:

https://blog.hubspot.com/marketing/youtube-demographics

[3] Cloudfront Pricing:
https://aws.amazon.com/cloudfront/pricing/

[4] Netflix on AWS: https://aws.amazon.com/solutions/case-studies/netflix/

[5] Akamai homepage: https://www.akamai.com/

[6] Binary large object:
https://en.wikipedia.org/wiki/Binary_large_object

[7] Here’s What You Need to Know About Streaming Protocols:
https://www.dacast.com/blog/streaming-protocols/

[8] SVE: Distributed Video Processing at Facebook Scale:
https://www.cs.princeton.edu/~wlloyd/papers/sve-sosp17.pdf

[9] Weibo video processing architecture (in Chinese):
https://www.upyun.com/opentalk/399.html

[10] Delegate access with a shared access signature:
https://docs.microsoft.com/en-us/rest/api/storageservices/delegate-access-with-shared-access-signature

[11] YouTube scalability talk by early YouTube employee:
https://www.youtube.com/watch?v=w5WVu624fY8

[12] Understanding the characteristics of internet short video sharing: A youtube-based measurement study.
https://arxiv.org/pdf/0707.3670.pdf

[13] Content Popularity for Open Connect:
https://netflixtechblog.com/content-popularity-for-open-connect-b86d56f613b