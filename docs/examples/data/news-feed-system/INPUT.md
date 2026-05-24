Design A News Feed System
In this chapter, you are asked to design a news feed system. What is news feed? According to the Facebook help page, “News feed is the constantly updating list of stories in the middle of your home page. News Feed includes status updates, photos, videos, links, app activity, and likes from people, pages, and groups that you follow on Facebook” [1]. This is a popular interview question. Similar questions commonly asked are to: design Facebook news feed, Instagram feed, Twitter timeline, etc.

Image represents a mobile phone screen displaying a news feed or similar content aggregator.  The screen shows three distinct news items, each vertically stacked and separated by dashed lines. Each item consists of a light-blue square (likely representing an app icon or source logo), a short headline in dark gray text, and a body of text in dark gray.  The second news item uniquely includes a light-green rectangular video player with a central white play button icon, suggesting multimedia content integration.  No URLs or specific parameters are visible; the information flow is implied as a unidirectional presentation of data from the application to the user, with no user interaction depicted in the image itself. The overall layout is clean and simple, suggesting a focus on content readability within a mobile context.
Figure 1
Step 1 - Understand the problem and establish design scope
The first set of clarification questions are to understand what the interviewer has in mind when she asks you to design a news feed system. At the very least, you should figure out what features to support. Here is an example of candidate-interviewer interaction:

Candidate: Is this a mobile app? Or a web app? Or both?
Interviewer: Both

Candidate: What are the important features?
Interview: A user can publish a post and see her friends’ posts on the news feed page.

Candidate: Is the news feed sorted by reverse chronological order or any particular order such as topic scores? For instance, posts from your close friends have higher scores.
Interviewer: To keep things simple, let us assume the feed is sorted by reverse chronological order.

Candidate: How many friends can a user have?
Interviewer: 5000

Candidate: What is the traffic volume?
Interviewer: 10 million DAU

Candidate: Can feed contain images, videos, or just text?
Interviewer: It can contain media files, including both images and videos.

Now you have gathered the requirements, we focus on designing the system.

Step 2 - Propose high-level design and get buy-in
The design is divided into two flows: feed publishing and news feed building.

Feed publishing: when a user publishes a post, corresponding data is written into cache and database. A post is populated to her friends’ news feed.

Newsfeed building: for simplicity, let us assume the news feed is built by aggregating friends’ posts in reverse chronological order.

Newsfeed APIs
The news feed APIs are the primary ways for clients to communicate with servers. Those APIs are HTTP based that allow clients to perform actions, which include posting a status, retrieving news feed, adding friends, etc. We discuss two most important APIs: feed publishing API and news feed retrieval API.

Feed publishing API

To publish a post, a HTTP POST request will be sent to the server. The API is shown below:

POST /v1/me/feed

Params:

content: content is the text of the post.

auth_token: it is used to authenticate API requests.

Newsfeed retrieval API

The API to retrieve news feed is shown below:

GET /v1/me/feed

Params:

auth_token: it is used to authenticate API requests.
Feed publishing
Figure 2 shows the high-level design of the feed publishing flow.

Image represents a system architecture diagram illustrating the flow of a user request for a news feed.  A user, accessing via either a web browser or mobile app, initiates a request that first resolves through a DNS server. This request, containing parameters like `v1/me/feed?content=Hello&auth_token={auth_token}`, is then directed to a load balancer which distributes the traffic across multiple web servers.  These web servers communicate with three distinct services: a Post Service, a Fanout Service, and a Notification Service. The Post Service retrieves data from a Post Cache, which in turn accesses a Post DB if necessary.  The Fanout Service interacts with a News Feed Cache to provide the news feed content.  The Notification Service is shown but its interaction with other components isn't explicitly detailed.  The diagram highlights the use of caching mechanisms (Post Cache and News Feed Cache) to improve performance by storing frequently accessed data closer to the web servers.  The overall architecture demonstrates a client-server model with load balancing and caching strategies for efficient request handling.
Figure 2
User: a user can view news feeds on a browser or mobile app. A user makes a post with content “Hello” through API:

/v1/me/feed?content=Hello&auth_token={auth_token}

Load balancer: distribute traffic to web servers.

Web servers: web servers redirect traffic to different internal services.

Post service: persist post in the database and cache.

Fanout service: push new content to friends’ news feed. Newsfeed data is stored in the cache for fast retrieval.

Notification service: inform friends that new content is available and send out push notifications.

Newsfeed building
In this section, we discuss how news feed is built behind the scenes. Figure 3 shows the high-level design:

Image represents a system architecture diagram for a news feed service.  The diagram starts with a 'User' block containing icons for a web browser and a mobile app, which connects to a DNS server.  From the User block, a request labeled 'v1/me/feed' is sent to a 'Load balancer,' which distributes the request to a cluster of 'Web servers.' These web servers then communicate with a 'News Feed Service,' which in turn accesses a 'News Feed Cache' composed of multiple cache instances (labeled 'CACHE'). The data flow is unidirectional, starting from the user's request and ending at the retrieval of data from the cache.  The web servers are depicted within a dashed-line box, suggesting a cluster or pool of servers. The News Feed Cache is also highlighted with a rounded rectangle, indicating a distinct component.  The overall architecture shows a client-server model with load balancing and caching implemented for improved performance and scalability.
Figure 3
User: a user sends a request to retrieve her news feed. The request looks like this: /v1/me/feed.

Load balancer: load balancer redirects traffic to web servers.

Web servers: web servers route requests to newsfeed service.

Newsfeed service: news feed service fetches news feed from the cache.

Newsfeed cache: store news feed IDs needed to render the news feed.

Step 3 - Design deep dive
The high-level design briefly covered two flows: feed publishing and news feed building. Here, we discuss those topics in more depth.

Feed publishing deep dive
Figure 4 outlines the detailed design for feed publishing. We have discussed most of components in high-level design, and we will focus on two components: web servers and fanout service.

Image represents a system architecture diagram for a social media feed.  A user, accessing via web browser or mobile app (sending a request like `/v1/me/feed?content=Hello&auth_token={auth_token}`), initiates the process. This request is routed through a DNS server to a load balancer, which distributes the traffic to multiple web servers.  The web servers handle authentication and rate limiting before interacting with a Post Service. The Post Service retrieves data from a Post Cache, falling back to a Post DB if necessary.  Concurrently, the Fanout Service, receiving friend IDs (1) from the web servers, queries a Graph DB for friends' data (2). This data is then placed in a Message Queue (3). Fanout Workers (4) process these messages, updating a News Feed Cache (5).  The Notification Service is also triggered by the web servers.  The system utilizes caching extensively: Post Cache for post data, User Cache for user data, and News Feed Cache for the final feed.  Data flows are numbered for clarity, showing the sequence of operations.
Figure 4
Web servers
Besides communicating with clients, web servers enforce authentication and rate-limiting. Only users signed in with valid auth_token are allowed to make posts. The system limits the number of posts a user can make within a certain period, vital to prevent spam and abusive content.

Fanout service
Fanout is the process of delivering a post to all friends. Two types of fanout models are: fanout on write (also called push model) and fanout on read (also called pull model). Both models have pros and cons. We explain their workflows and explore the best approach to support our system.

Fanout on write. With this approach, news feed is pre-computed during write time. A new post is delivered to friends’ cache immediately after it is published.

Pros:

The news feed is generated in real-time and can be pushed to friends immediately.

Fetching news feed is fast because the news feed is pre-computed during write time.

Cons:

If a user has many friends, fetching the friend list and generating news feeds for all of them are slow and time consuming. It is called hotkey problem.

For inactive users or those rarely log in, pre-computing news feeds waste computing resources.

Fanout on read. The news feed is generated during read time. This is an on-demand model. Recent posts are pulled when a user loads her home page.

Pros:

For inactive users or those who rarely log in, fanout on read works better because it will not waste computing resources on them.

Data is not pushed to friends so there is no hotkey problem.

Cons:

Fetching the news feed is slow as the news feed is not pre-computed.
We adopt a hybrid approach to get benefits of both approaches and avoid pitfalls in them. Since fetching the news feed fast is crucial, we use a push model for the majority of users. For celebrities or users who have many friends/followers, we let followers pull news content on-demand to avoid system overload. Consistent hashing is a useful technique to mitigate the hotkey problem as it helps to distribute requests/data more evenly.

Let us take a close look at the fanout service as shown in Figure 5.

Image represents a system architecture diagram for a news feed fanout service.  The process begins with a `Fanout Service` which first retrieves a list of `friend ids` (step 1) from a `Graph DB` (a graph database storing user relationships).  Next, it retrieves the `friends data` (step 2) from a `User Cache`, which in turn pulls data from a `User DB` (a relational database storing user information) if a cache miss occurs.  The `Fanout Service` then places messages (step 3) into a `Message Queue`, which are subsequently processed by `Fanout Workers` (step 4). These workers update the user's `News Feed` (step 5), which also utilizes a cache for performance optimization.  The numbered steps indicate the sequential flow of data and operations within the system.  The diagram clearly shows the interaction between different components, highlighting the use of caching mechanisms to improve efficiency and the use of a message queue for asynchronous processing.
Figure 5
The fanout service works as follows:

1. Fetch friend IDs from the graph database. Graph databases are suited for managing friend relationship and friend recommendations. Interested readers wishing to learn more about this concept should refer to the reference material [2].

2. Get friends info from the user cache. The system then filters out friends based on user settings. For example, if you mute someone, her posts will not show up on your news feed even though you are still friends. Another reason why posts may not show is that a user could selectively share information with specific friends or hide it from other people.

3. Send friends list and new post ID to the message queue.

4. Fanout workers fetch data from the message queue and store news feed data in the news feed cache. You can think of the news feed cache as a <post_id, user_id> mapping table. Whenever a new post is made, it will be appended to the news feed table as shown in Figure 6. The memory consumption can become very large if we store the entire user and post objects in the cache. Thus, only IDs are stored. To keep the memory size small, we set a configurable limit. The chance of a user scrolling through thousands of posts in news feed is slim. Most users are only interested in the latest content, so the cache miss rate is low.

5. Store <post_id, user_id > in news feed cache. Figure 6 shows an example of what the news feed looks like in cache.

post_id	user_id
post_id	user_id
post_id	user_id
post_id	user_id
post_id	user_id
post_id	user_id
post_id	user_id
post_id	user_id
Figure 6

Newsfeed retrieval deep dive
Figure 7 illustrates the detailed design for news feed retrieval.

Image represents a system architecture diagram for a news feed service.  A user, accessing via web browser or mobile app, initiates a request (labeled '/v1/me/feed') which first resolves through a DNS server. This request then hits a load balancer (1), distributing the traffic across multiple web servers (2).  The web servers handle authentication and rate limiting before forwarding the request to the 'News Feed Service' (3). This service then accesses a 'News Feed Cache' (4) for data. If the data is not present in the cache, the service fetches it from the 'User DB' via the 'User Cache' (5) and 'Post DB' via the 'Post Cache' (5).  The responses are cached for future requests.  The entire system is fronted by a CDN (6) for faster content delivery, with the load balancer distributing traffic to the web servers and the mobile app connecting directly to the CDN (6).  Numbered arrows indicate the flow of requests and responses between components.
Figure 7
As shown in Figure 7, media content (images, videos, etc.) are stored in CDN for fast retrieval. Let us look at how a client retrieves news feed.

1. A user sends a request to retrieve her news feed. The request looks like this: /v1/me/feed

2. The load balancer redistributes requests to web servers.

3. Web servers call the news feed service to fetch news feeds.

4. News feed service gets a list post IDs from the news feed cache.

5. A user’s news feed is more than just a list of feed IDs. It contains username, profile picture, post content, post image, etc. Thus, the news feed service fetches the complete user and post objects from caches (user cache and post cache) to construct the fully hydrated news feed.

6. The fully hydrated news feed is returned in JSON format back to the client for rendering.

Cache architecture
Cache is extremely important for a news feed system. We divide the cache tier into 5 layers as shown in Figure 8.

Image represents a system design for a news feed, structured as a table with five rows and three columns.  The first column labels the rows: 'News Feed,' 'Content,' 'Social Graph,' 'Action,' and 'Counters.' The remaining two columns represent data categories. The 'News Feed' row contains a single box labeled 'news feed.' The 'Content' row contains boxes labeled 'hot cache' and 'normal,' suggesting different caching strategies for content. The 'Social Graph' row shows boxes labeled 'follower' and 'following,' representing relationships between users. The 'Action' row displays boxes for 'liked,' 'replied,' and 'others,' indicating different user interactions. Finally, the 'Counters' row shows corresponding counters for each action: 'like counter,' 'reply counter,' and 'other counters.'  The dashed lines delineate logical groupings of related data within the system.  No explicit connections or data flow are shown between the boxes, but the arrangement implies a relationship between the data in each row, suggesting that the system tracks news feed content, user relationships, user actions, and associated counts.
Figure 8
News Feed: It stores IDs of news feeds.

Content: It stores every post data. Popular content is stored in hot cache.

Social Graph: It stores user relationship data.

Action: It stores info about whether a user liked a post, replied a post, or took other actions on a post.

Counters: It stores counters for like, reply, follower, following, etc.

Step 4 - Wrap up
In this chapter, we designed a news feed system. Our design contains two flows: feed publishing and news feed retrieval.

Like any system design interview questions, there is no perfect way to design a system. Every company has its unique constraints, and you must design a system to fit those constraints. Understanding the tradeoffs of your design and technology choices are important. If there are a few minutes left, you can talk about scalability issues. To avoid duplicated discussion, only high-level talking points are listed below.

Scaling the database:

Vertical scaling vs Horizontal scaling

SQL vs NoSQL

Master-slave replication

Read replicas

Consistency models

Database sharding

Other talking points:

Keep web tier stateless

Cache data as much as you can

Support multiple data centers

Loosely coupled components with message queues

Monitor key metrics. For instance, QPS during peak hours and latency while users refreshing their news feed are interesting to monitor.

Congratulations on getting this far! Now give yourself a pat on the back. Good job!

Reference materials
[1] How News Feed Works:
https://www.facebook.com/help/327131014036297/

[2] Friend of Friend recommendations Neo4j and SQL Sever:
http://geekswithblogs.net/brendonpage/archive/2015/10/26/friend-of-friend-recommendations-with-neo4j.aspx