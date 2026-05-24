Design A Chat System
In this chapter we explore the design of a chat system. Almost everyone uses a chat app. Figure 1 shows some of the most popular apps in the marketplace.

Image represents a collection of five popular messaging application logos, each displayed with its corresponding name.  The logos are arranged in two rows, with three in the top row and two in the bottom row.  The top row features, from left to right: a green speech bubble containing a white telephone icon labeled 'Whatsapp,' a blue speech bubble with a white lightning bolt icon labeled 'Facebook messenger,' and a green circle with two white speech bubble icons labeled 'Wechat.' The bottom row shows, from left to right: a green square with a white speech bubble containing the text 'LINE' labeled 'Line,' and a light purple circle with a white stylized face icon labeled 'Discord.'  There are no connections or information flow depicted between the logos; they are simply presented as individual entities.  The arrangement suggests a comparison or overview of different messaging platforms.
Figure 1
A chat app performs different functions for different people. It is extremely important to nail down the exact requirements. For example, you do not want to design a system that focuses on group chat when the interviewer has one-on-one chat in mind. It is important to explore the feature requirements.

Step 1 - Understand the problem and establish design scope
It is vital to agree on the type of chat app to design. In the marketplace, there are one-on-one chat apps like Facebook Messenger, WeChat, and WhatsApp, office chat apps that focus on group chat like Slack, or game chat apps, like Discord, that focus on large group interaction and low voice chat latency.

The first set of clarification questions should nail down what the interviewer has in mind exactly when she asks you to design a chat system. At the very least, figure out if you should focus on a one-on-one chat or group chat app. Some questions you might ask are as follows:

Candidate: What kind of chat app shall we design? 1 on 1 or group based?
Interviewer: It should support both 1 on 1 and group chat.

Candidate: Is this a mobile app? Or a web app? Or both?
Interviewer: Both.

Candidate: What is the scale of this app? A startup app or massive scale?
Interviewer: It should support 50 million daily active users (DAU).

Candidate: For group chat, what is the group member limit?
Interviewer: A maximum of 100 people

Candidate: What features are important for the chat app? Can it support attachment?
Interviewer: 1 on 1 chat, group chat, online indicator. The system only supports text messages.

Candidate: Is there a message size limit?
Interviewer: Yes, text length should be less than 100,000 characters long.

Candidate: Is end-to-end encryption required?
Interviewer: Not required for now but we will discuss that if time allows.

Candidate: How long shall we store the chat history?
Interviewer: Forever.

In the chapter, we focus on designing a chat app like Facebook messenger, with an emphasis on the following features:

A one-on-one chat with low delivery latency

Small group chat (max of 100 people)

Online presence

Multiple device support. The same account can be logged in to multiple accounts at the same time.

Push notifications

It is also important to agree on the design scale. We will design a system that supports 50 million DAU.

Step 2 - Propose high-level design and get buy-in
To develop a high-quality design, we should have a basic knowledge of how clients and servers communicate. In a chat system, clients can be either mobile applications or web applications. Clients do not communicate directly with each other. Instead, each client connects to a chat service, which supports all the features mentioned above. Let us focus on fundamental operations. The chat service must support the following functions:

Receive messages from other clients.

Find the right recipients for each message and relay the message to the recipients.

If a recipient is not online, hold the messages for that recipient on the server until she is online.

Figure 2 shows the relationships between clients (sender and receiver) and the chat service.

Image represents a simplified model of a chat application's architecture.  The diagram shows three main components: a 'sender' represented by a laptop icon within a light-blue rounded square, a 'Chat service' represented by a light-blue rounded rectangle, and a 'receiver' represented by a smartphone icon within a light-blue rounded square.  The sender sends a 'message' (labeled as such) via a directed arrow to the Chat service. The Chat service, which is described as having two functions: '1. store message' and '2. relay message', then sends the same 'message' via another directed arrow to the receiver.  The arrows indicate the unidirectional flow of the message from sender to Chat service and then from Chat service to receiver.  The entire system focuses on the transmission and storage of a message between two users.
Figure 2
When a client intends to start a chat, it connects the chats service using one or more network protocols. For a chat service, the choice of network protocols is important. Let us discuss this with the interviewer.

Requests are initiated by the client for most client/server applications. This is also true for the sender side of a chat application. In Figure 2, when the sender sends a message to the receiver via the chat service, it uses the time-tested HTTP protocol, which is the most common web protocol. In this scenario, the client opens a HTTP connection with the chat service and sends the message, informing the service to send the message to the receiver. The keep-alive is efficient for this because the keep-alive header allows a client to maintain a persistent connection with the chat service. It also reduces the number of TCP handshakes. HTTP is a fine option on the sender side, and many popular chat applications such as Facebook [1] used HTTP initially to send messages.

However, the receiver side is a bit more complicated. Since HTTP is client-initiated, it is not trivial to send messages from the server. Over the years, many techniques are used to simulate a server-initiated connection: polling, long polling, and WebSocket. Those are important techniques widely used in system design interviews so let us examine each of them.

Polling
As shown in Figure 3, polling is a technique that the client periodically asks the server if there are messages available. Depending on polling frequency, polling could be costly. It could consume precious server resources to answer a question that offers no as an answer most of the time.

Image represents a sequence diagram illustrating the interaction between a Client and a Server regarding message retrieval.  The diagram shows four iterative cycles. In each cycle, the Client initiates a request to the Server by asking 'New messages?'.  Three out of four times, the Server responds with 'NO' and sends a red arrow back to the Client, indicating no new messages.  After each negative response, a dashed line labeled 'connection closed' signifies the termination of that communication cycle.  However, in the third cycle, the Server responds with 'Yes. Return new...', represented by a green arrow directed towards the Client, indicating that new messages are available and are being sent.  Following this positive response, a dashed line labeled 'connection closed' again shows the closure of the connection for that cycle.  The ellipsis (...) suggests that this pattern of client requests and server responses continues.  The overall diagram depicts a polling mechanism where the client repeatedly checks for new messages from the server.
Figure 3
Long polling
Because polling could be inefficient, the next progression is long polling (Figure 4).

Image represents a sequence diagram illustrating client-server communication for retrieving new messages.  Two vertical lines represent the Client and Server, respectively, with horizontal arrows indicating message exchanges. The Client initiates the interaction by sending 'New messages?' requests (thick black arrows) to the Server. The Server responds with 'Yes. Return new messages' (green arrow) when new messages are available, sending the messages back to the client, and closing the connection.  If no new messages are available, the server waits until a timeout occurs (indicated by the text 'Wait for new messages' on the server side).  After a timeout, the server closes the connection (red arrow).  Dashed lines between the arrows indicate the connection closure. The process repeats with subsequent 'New messages?' requests from the client.  The diagram visually depicts the polling mechanism used by the client to check for new messages, showing both successful message retrieval and handling of timeouts.
Figure 4
In long polling, a client holds the connection open until there are actually new messages available or a timeout threshold has been reached. Once the client receives new messages, it immediately sends another request to the server, restarting the process. Long polling has a few drawbacks:

Sender and receiver may not connect to the same chat server. HTTP based servers are usually stateless. If you use round robin for load balancing, the server that receives the message might not have a long-polling connection with the client who receives the message.

A server has no good way to tell if a client is disconnected.

It is inefficient. If a user does not chat much, long polling still makes periodic connections after timeouts.

WebSocket
WebSocket is the most common solution for sending asynchronous updates from server to client. Figure 5 shows how it works.

Image represents a sequence diagram illustrating the WebSocket handshake and communication between a Client and a Server.  The diagram shows two rectangular boxes labeled 'Client' and 'Server' connected by vertical lines representing their persistent connection.  A small rectangular box next to the Client box displays 'GET /ws,' indicating the client's initial request to establish a WebSocket connection. A thick black arrow labeled 'HTTP Handshake' extends from the Client to the Server, depicting the initial connection request.  A green arrow labeled 'Acknowledgement' then goes from the Server back to the Client, signifying the server's acceptance of the connection. Finally, a dashed black bidirectional arrow labeled 'Bidirectional messages' shows the ongoing exchange of messages between the Client and Server after the successful handshake, representing the two-way communication characteristic of WebSockets.
Figure 5
WebSocket connection is initiated by the client. It is bi-directional and persistent. It starts its life as a HTTP connection and could be “upgraded” via some well-defined handshake to a WebSocket connection. Through this persistent connection, a server could send updates to a client. WebSocket connections generally work even if a firewall is in place. This is because they use port 80 or 443 which are also used by HTTP/HTTPS connections.

Earlier we said that on the sender side HTTP is a fine protocol to use, but since WebSocket is bidirectional, there is no strong technical reason not to use it also for sending. Figure 6 shows how WebSockets (ws) is used for both sender and receiver sides.

Image represents a simplified architecture of a chat application.  Two rectangular boxes, outlined in light blue, represent the 'sender' and 'receiver' clients. The sender is depicted as a laptop computer, while the receiver is shown as a smartphone.  A larger, centrally located, light-blue rectangular box labeled 'Chat service' represents the server-side component of the application.  Arrows indicate the flow of information, labeled 'ws' (likely representing WebSockets), showing that both the sender and receiver communicate with the 'Chat service' using this protocol.  The arrows point towards the 'Chat service' to indicate messages sent from clients to the server, and away from the 'Chat service' to indicate messages sent from the server to the clients, enabling bidirectional communication between the clients and the central chat service.
Figure 6
By using WebSocket for both sending and receiving, it simplifies the design and makes implementation on both client and server more straightforward. Since WebSocket connections are persistent, efficient connection management is critical on the server-side.

High-level design
Just now we mentioned that WebSocket was chosen as the main communication protocol between the client and server for its bidirectional communication, it is important to note that everything else does not have to be WebSocket. In fact, most features (sign up, login, user profile, etc) of a chat application could use the traditional request/response method over HTTP. Let us drill in a bit and look at the high-level components of the system.

As shown in Figure 7, the chat system is broken down into three major categories: stateless services, stateful services, and third-party integration.

Image represents a system architecture diagram divided into two main sections: 'Stateless' and 'Stateful'.  The 'Stateless' section shows a user (represented by laptop and mobile phone icons) making HTTP requests to a load balancer. The load balancer distributes requests to four services: Service discovery, Authentication service, Group management, and User profile.  These services are depicted as rectangular boxes, and arrows indicate the flow of requests from the load balancer to each service. The entire 'Stateless' section is enclosed in a dashed-line box. The 'Stateful' section depicts two users (User 1 with a laptop and User 2 with a mobile phone) communicating with a 'Chat service' via WebSockets (labeled 'ws').  Arrows show the bidirectional communication between users and the chat service.  This 'Stateful' section is also enclosed in a dashed-line box. Finally, a separate dashed-line box labeled 'Third party' contains a 'Push notification' service, suggesting that the chat service interacts with a third-party service for push notifications.  The overall diagram illustrates a client-server architecture with a load balancer for distributing requests and a separation between stateless and stateful components.
Figure 7
Stateless Services
Stateless services are traditional public-facing request/response services, used to manage the login, signup, user profile, etc. These are common features among many websites and apps.

Stateless services sit behind a load balancer whose job is to route requests to the correct services based on the request paths. These services can be monolithic or individual microservices. We do not need to build many of these stateless services by ourselves as there are services in the market that can be integrated easily. The one service that we will discuss more in deep dive is the service discovery. Its primary job is to give the client a list of DNS host names of chat servers that the client could connect to.

Stateful Service
The only stateful service is the chat service. The service is stateful because each client maintains a persistent network connection to a chat server. In this service, a client normally does not switch to another chat server as long as the server is still available. The service discovery coordinates closely with the chat service to avoid server overloading. We will go into detail in deep dive.

Third-party integration
For a chat app, push notification is the most important third-party integration. It is a way to inform users when new messages have arrived, even when the app is not running. Proper integration of push notification is crucial. Refer to "Design a notification system" chapter for more information.

Scalability
On a small scale, all services listed above could fit in one server. Even at the scale we design for, it is in theory possible to fit all user connections in one modern cloud server. The number of concurrent connections that a server can handle will most likely be the limiting factor. In our scenario, at 1M concurrent users, assuming each user connection needs 10K of memory on the server (this is a very rough figure and very dependent on the language choice), it only needs about 10GB of memory to hold all the connections on one box.

If we propose a design where everything fits in one server, this may raise a big red flag in the interviewer’s mind. No technologist would design such a scale in a single server. Single server design is a deal breaker due to many factors. The single point of failure is the biggest among them.

However, it is perfectly fine to start with a single server design. Just make sure the interviewer knows this is a starting point. Putting everything we mentioned together, Figure 8 shows the adjusted high-level design.

Image represents a system architecture diagram for a real-time communication application.  At the top, a 'User' component, depicted as a laptop and a mobile phone, connects to a 'Load balancer' via 'http' and 'ws' protocols. The load balancer distributes requests to 'API servers,' which are depicted as a cluster of green boxes.  The API servers interact with 'Notification servers' (green boxes) and communicate with a 'Real time service' component. This 'Real time service' comprises 'Chat servers' and 'Presence servers,' both represented as clusters of purple boxes.  The 'Real time service' and the 'API servers' are connected to three separate 'KV store' databases (blue boxes with database icons), suggesting data persistence for each service.  The arrows indicate the direction of information flow, showing how user requests are processed, data is stored, and notifications are handled within the system.  The dashed lines around the 'Real time service' and the 'KV store' databases suggest these are separate logical groupings within the overall architecture.
Figure 8
In Figure 8, the client maintains a persistent WebSocket connection to a chat server for real-time messaging.

Chat servers facilitate message sending/receiving.

Presence servers manage online/offline status.

API servers handle everything including user login, signup, change profile, etc.

Notification servers send push notifications.

Finally, the key-value store is used to store chat history. When an offline user comes online, she will see all her previous chat history.

Storage
At this point, we have servers ready, services up running and third-party integrations complete. Deep down the technical stack is the data layer. Data layer usually requires some effort to get it correct. An important decision we must make is to decide on the right type of database to use: relational databases or NoSQL databases? To make an informed decision, we will examine the data types and read/write patterns.

Two types of data exist in a typical chat system. The first is generic data, such as user profile, setting, user friends list. These data are stored in robust and reliable relational databases. Replication and sharding are common techniques to satisfy availability and scalability requirements.

The second is unique to chat systems: chat history data. It is important to understand the read/write pattern.

The amount of data is enormous for chat systems. A previous study [2] reveals that Facebook messenger and Whatsapp process 60 billion messages a day.

Only recent chats are accessed frequently. Users do not usually look up for old chats.

Although very recent chat history is viewed in most cases, users might use features that require random access of data, such as search, view your mentions, jump to specific messages, etc. These cases should be supported by the data access layer.

The read to write ratio is about 1:1 for 1 on 1 chat apps.

Selecting the correct storage system that supports all of our use cases is crucial. We recommend key-value stores for the following reasons:

Key-value stores allow easy horizontal scaling.

Key-value stores provide very low latency to access data.

Relational databases do not handle long tail [3] of data well. When the indexes grow large, random access is expensive.

Key-value stores are adopted by other proven reliable chat applications. For example, both Facebook messenger and Discord use key-value stores. Facebook messenger uses HBase [4], and Discord uses Cassandra [5].

Data models
Just now, we talked about using key-value stores as our storage layer. The most important data is message data. Let us take a close look.

Message table for 1 on 1 chat
Figure 9 shows the message table for 1 on 1 chat. The primary key is message_id, which helps to decide message sequence. We cannot rely on created_at to decide the message sequence because two messages can be created at the same time.

Image represents a table schema for a database table named 'message'.  The table has five columns: `message_id` (a bigint data type, likely serving as the primary key), `message_from` (a bigint, potentially representing a user ID), `message_to` (a bitint, possibly indicating a single recipient or a group ID), `content` (a text field storing the message body), and `created_at` (a timestamp recording the message creation time).  The schema is presented in a tabular format with the column names on the left and their corresponding data types on the right, all within a box with a header indicating the table name 'message' in a darker blue color.  No connections or information flow is depicted; it simply defines the structure of the 'message' table.
Figure 9
Message table for group chat
Figure 10 shows the message table for group chat. The composite primary key is (channel_id, message_id). Channel and group represent the same meaning here. channel_id is the partition key because all queries in a group chat operate in a channel.

Image represents a table schema for a database table named `group_message`.  The table has five columns: `channel_id` (of type `bigint`), `message_id` (also `bigint`), `user_id` (`bigint`), `content` (`text`), and `created_at` (`timestamp`).  The table appears to store information about messages within groups, where each row represents a single message.  `channel_id` likely identifies the group chat or channel where the message was sent, `message_id` uniquely identifies the message itself, `user_id` specifies the sender of the message, `content` holds the message text, and `created_at` records the message's timestamp.  There are no connections or information flow depicted beyond the column definitions within the table structure itself.
Figure 10
Message ID
How to generate message_id is an interesting topic worth exploring. Message_id carries the responsibility of ensuring the order of messages. To ascertain the order of messages, message_id must satisfy the following two requirements:

IDs must be unique.

IDs should be sortable by time, meaning new rows have higher IDs than old ones.

How can we achieve those two guarantees? The first idea that comes to mind is the “auto_increment” keyword in MySql. However, NoSQL databases usually do not provide such a feature.

The second approach is to use a global 64-bit sequence number generator like Snowflake [6]. This is discussed in the “Design a unique ID generator in a distributed system” chapter.

The final approach is to use local sequence number generator. Local means IDs are only unique within a group. The reason why local IDs work is that maintaining message sequence within one-on-one channel or a group channel is sufficient. This approach is easier to implement in comparison to the global ID implementation.

Step 3 - Design deep dive
In a system design interview, usually you are expected to dive deep into some of the components in the high-level design. For the chat system, service discovery, messaging flows, and online/offline indicators worth deeper exploration.

Service discovery
The primary role of service discovery is to recommend the best chat server for a client based on the criteria like geographical location, server capacity, etc. Apache Zookeeper [7] is a popular open-source solution for service discovery. It registers all the available chat servers and picks the best chat server for a client based on predefined criteria.

Figure 11 shows how service discovery (Zookeeper) works.

Image represents a system architecture diagram illustrating the flow of a user's login and subsequent connection to a chat service.  User A, represented by a smartphone icon, initiates a login (labeled '1. login') request that is directed to a load balancer. The load balancer (labeled 'Load balancer') then forwards the request to a set of API servers (labeled 'API servers').  These API servers, in turn, interact with a service discovery system, specifically Zookeeper (labeled 'Service discovery (Zookeeper)'), to locate an available chat server.  Zookeeper shows multiple chat servers (represented by vertical rectangles labeled 'Chat server 1,' 'Chat server 2,' and 'Chat server N'). After the API servers find an available chat server via Zookeeper, the user establishes a WebSocket connection (labeled '4. ws') to a specific chat server, indicated by the arrow pointing to 'Chat server 2.'  The numbers 1, 2, 3, and 4 represent the sequential steps in the process.
Figure 11
1. User A tries to log in to the app.

2. The load balancer sends the login request to API servers.

3. After the backend authenticates the user, service discovery finds the best chat server for User A. In this example, server 2 is chosen and the server info is returned back to User A.

4. User A connects to chat server 2 through WebSocket.

Message flows
It is interesting to understand the end-to-end flow of a chat system. In this section, we will explore 1 on 1 chat flow, message synchronization across multiple devices and group chat flow.

1 on 1 chat flow
Figure 12 explains what happens when User A sends a message to User B.

Image represents a simplified chat application architecture.  Two users, User A and User B, represented by smartphone icons, interact with the system. User A (1) sends a message to Chat server 1, a purple database icon.  Chat server 1 (2) requests a unique message ID from the ID generator (green database cluster icon).  After receiving the ID, Chat server 1 (3) pushes the message to a Message sync queue (three envelope icons).  The Message sync queue acts as a buffer, distributing messages to other components.  The queue (4) sends the message to the KV store (blue database cluster icon) for persistent storage.  User B (6) connects to Chat server 2 (another purple database icon). Chat server 2 receives messages from the Message sync queue via two paths: 5.a (online) for immediate delivery and 5.b (offline) for delivery when the user is offline, using PN servers (green database cluster icon) for offline message storage and delivery.  The numbered arrows indicate the flow of information between components.
Figure 12
1. User A sends a chat message to Chat server 1.

2. Chat server 1 obtains a message ID from the ID generator.

3. Chat server 1 sends the message to the message sync queue.

4. The message is stored in a key-value store.

5.a. If User B is online, the message is forwarded to Chat server 2 where User B is connected.

5.b. If User B is offline, a push notification is sent from push notification (PN) servers.

6. Chat server 2 forwards the message to User B. There is a persistent WebSocket connection between User B and Chat server 2.

Message synchronization across multiple devices
Many users have multiple devices. We will explain how to sync messages across multiple devices. Figure 13 shows an example of message synchronization.

Image represents a simplified architecture diagram of a chat application's data flow for a single user (User A).  Two client devices, User A's phone and User A's laptop, are depicted as separate boxes, each displaying its current maximum message ID (653 for the phone and 842 for the laptop).  These devices communicate with a central 'Chat server 1,' represented as a purple rectangle.  Within the Chat server 1 box, 'Session for User A's phone' and 'Session for User A's laptop' indicate separate sessions maintained for each device.  Arrows show the unidirectional data flow from each device to the chat server.  Finally, the chat server interacts with a 'KV store' (likely a key-value database) represented by three stacked blue cylinders, indicating that message data is stored persistently.  The arrows illustrate that both the phone and laptop sessions send data to the KV store via the chat server.
Figure 13
In Figure 13, user A has two devices: a phone and a laptop. When User A logs in to the chat app with her phone, it establishes a WebSocket connection with Chat server 1. Similarly, there is a connection between the laptop and Chat server 1.

Each device maintains a variable called cur_max_message_id, which keeps track of the latest message ID on the device. Messages that satisfy the following two conditions are considered as news messages:

The recipient ID is equal to the currently logged-in user ID.

Message ID in the key-value store is larger than cur_max_message_id.

With distinct cur_max_message_id on each device, message synchronization is easy as each device can get new messages from the KV store.

Small group chat flow
In comparison to the one-on-one chat, the logic of group chat is more complicated. Figures 12-14 and 12-15 explain the flow.

Image represents a simplified chat application architecture.  A user, labeled 'User A,' sends a message to 'Chat server 1,' depicted as a purple rectangle.  This server then pushes the message to two separate 'Message sync queues,' each represented by a cyan rectangle containing three envelope icons.  These queues act as intermediaries, distributing messages to other users.  One queue sends the message to 'User B,' and the other queue sends the message to 'User C,' both represented by smartphone icons.  The entire system illustrates a message-passing architecture where a central server manages message distribution to multiple clients via asynchronous message queues, ensuring that messages reach their intended recipients even if they are not actively connected.
Figure 14
Figure 14 explains what happens when User A sends a message in a group chat. Assume there are 3 members in the group (User A, User B and user C). First, the message from User A is copied to each group member’s message sync queue: one for User B and the second for User C. You can think of the message sync queue as an inbox for a recipient. This design choice is good for small group chat because:

it simplifies message sync flow as each client only needs to check its own inbox to get new messages.

when the group number is small, storing a copy in each recipient’s inbox is not too expensive.

WeChat uses a similar approach, and it limits a group to 500 members [8]. However, for groups with a lot of users, storing a message copy for each member is not acceptable.

On the recipient side, a recipient can receive messages from multiple users. Each recipient has an inbox (message sync queue) which contains messages from different senders. Figure 15 illustrates the design.

Image represents a simplified chat application architecture.  Two users, User A and User B, are represented by smartphone icons, each connected to a separate chat server (Chat server 1 and Chat server 2, respectively, depicted as purple server icons).  These chat servers, in turn, are connected to a central 'Message sync queue' (represented by three envelope icons within a cyan-colored box), which acts as a message broker.  The message queue then forwards messages to User C (another smartphone icon), suggesting a scenario where User C is receiving messages from both User A and User B.  The arrows indicate the direction of message flow, showing that messages from User A and User B are sent to their respective chat servers, then aggregated and forwarded through the message sync queue to User C.  The system uses a distributed architecture with separate chat servers for scalability and potentially to handle different aspects of the chat functionality.
Figure 15
Online presence
An online presence indicator is an essential feature of many chat applications. Usually, you can see a green dot next to a user’s profile picture or username. This section explains what happens behind the scenes.

In the high-level design, presence servers are responsible for managing online status and communicating with clients through WebSocket. There are a few flows that will trigger online status change. Let us examine each of them.

User login
The user login flow is explained in the “Service Discovery” section. After a WebSocket connection is built between the client and the real-time service, user A’s online status and last_active_at timestamp are saved in the KV store. Presence indicator shows the user is online after she logs in.

Image represents a simplified system architecture for tracking user presence.  A mobile device representing 'User A' establishes a 'ws connection' (likely a WebSocket connection) with a set of 'Presence servers'. These servers are responsible for managing and updating user status information.  The presence servers, in turn, store this information in a 'KV store' (a key-value store database), depicted as three database cylinders.  The data stored for User A in the KV store is shown as a JSON-like structure: `{status: online, last_active_at: timestamp}`, indicating the user's online status and the last time they were active, represented by a timestamp.  The arrows illustrate the unidirectional flow of information: from User A to the Presence servers and then to the KV store.
Figure 16
User logout
When a user logs out, it goes through the user logout flow as shown in Figure 17. The online status is changed to offline in the KV store. The presence indicator shows a user is offline.

Image represents a system architecture diagram illustrating a user logout process.  The diagram shows a left-to-right flow. On the far left, a rectangular box labeled 'User A' contains an icon representing a smartphone, indicating a mobile user. A solid blue arrow labeled 'logout' extends from User A to a cluster of three vertically stacked green rectangles enclosed in a dashed blue box labeled 'API servers.' This signifies that the logout request originates from User A's device and is sent to the API servers.  From the API servers, another solid blue arrow leads to a rectangular box labeled 'Presence servers,' representing the component responsible for managing user presence information. Finally, a solid blue arrow connects the 'Presence servers' to a rectangular box labeled 'KV store' containing an icon of three blue cylinders, symbolizing a key-value store database.  The final label, 'User A: {status:offline},' indicates that after the logout process completes, the user's status in the KV store is updated to 'offline.'  The overall flow depicts the sequence of events when User A logs out, updating their presence status in the system's database.
Figure 17
User disconnection
We all wish our internet connection is consistent and reliable. However, that is not always the case; thus, we must address this issue in our design. When a user disconnects from the internet, the persistent connection between the client and server is lost. A naive way to handle user disconnection is to mark the user as offline and change the status to online when the connection re-establishes. However, this approach has a major flaw. It is common for users to disconnect and reconnect to the internet frequently in a short time. For example, network connections can be on and off while a user goes through a tunnel. Updating online status on every disconnect/reconnect would make the presence indicator change too often, resulting in poor user experience.

We introduce a heartbeat mechanism to solve this problem. Periodically, an online client sends a heartbeat event to presence servers. If presence servers receive a heartbeat event within a certain time, say x seconds from the client, a user is considered as online. Otherwise, it is offline.

In Figure 18, the client sends a heartbeat event to the server every 5 seconds. After sending 3 heartbeat events, the client is disconnected and does not reconnect within x = 30 seconds (This number is arbitrarily chosen to demonstrate the logic). The online status is changed to offline.

Image represents a sequence diagram illustrating a client-server heartbeat mechanism.  Two rectangular boxes labeled 'Client' and 'Server' represent the communicating entities.  Solid horizontal arrows depict messages flowing between them, labeled 'heartbeat'.  Three consecutive heartbeats are sent from the Client to the Server at 5-second intervals, indicated by '5s' labels next to the dashed vertical lines representing time.  On the Server side, each heartbeat reception is marked by a green circle and the text 'Heartbeat received. Status is online'. After a period of 'x = 30s', a dashed arrow indicates a time lapse.  The absence of a heartbeat within this 30-second window results in a red circle on the Server side with the text 'No heartbeat after 30 seconds. Change statu...', suggesting a change in the server's status due to the lack of communication from the client.  The diagram visually demonstrates a simple keep-alive mechanism where the client periodically sends heartbeats to maintain the connection and the server monitors these heartbeats to determine the client's online status.
Figure 18
Online status fanout
How do user A’s friends know about the status changes? Figure 19 explains how it works. Presence servers use a publish-subscribe model, in which each friend pair maintains a channel. When User A’s online status changes, it publishes the event to three channels, channel A-B, A-C, and A-D. Those three channels are subscribed by User B, C, and D, respectively. Thus, it is easy for friends to get online status updates. The communication between clients and servers is through real-time WebSocket.

Image represents a system architecture diagram illustrating a presence server setup.  A central component, labeled 'Presence servers,' is depicted as a dashed-line box containing three horizontally arranged sub-components, each representing a communication channel: 'Channel A-B,' 'Channel A-C,' and 'Channel A-D.' Each channel is visually represented by three icons resembling mailboxes, suggesting multiple message queues or similar data structures.  From the left, a device labeled 'User A' connects to each of the three channels via solid lines.  From the right, devices labeled 'User B,' 'User C,' and 'User D' (a smartphone, smartphone, and laptop respectively) each connect to one of the channels.  The connections from the users to the channels are labeled 'subscribe,' indicating a subscription-based communication model where users subscribe to specific channels to receive information.  The overall structure suggests a publish-subscribe system where User A publishes information to the channels, and Users B, C, and D subscribe to receive updates from those channels.
Figure 19
The above design is effective for a small user group. For instance, WeChat uses a similar approach because its user group is capped to 500. For larger groups, informing all members about online status is expensive and time consuming. Assume a group has 100,000 members. Each status change will generate 100,000 events. To solve the performance bottleneck, a possible solution is to fetch online status only when a user enters a group or manually refreshes the friend list.

Step 4 - Wrap up
In this chapter, we presented a chat system architecture that supports both 1-to-1 chat and small group chat. WebSocket is used for real-time communication between the client and server. The chat system contains the following components: chat servers for real-time messaging, presence servers for managing online presence, push notification servers for sending push notifications, key-value stores for chat history persistence and API servers for other functionalities.

If you have extra time at the end of the interview, here are additional talking points:

Extend the chat app to support media files such as photos and videos. Media files are significantly larger than text in size. Compression, cloud storage, and thumbnails are interesting topics to talk about.

End-to-end encryption. Whatsapp supports end-to-end encryption for messages. Only the sender and the recipient can read messages. Interested readers should refer to the article in the reference materials [9].

Caching messages on the client-side is effective to reduce the data transfer between the client and server.

Improve load time. Slack built a geographically distributed network to cache users’ data, channels, etc. for better load time [10].

Error handling.

The chat server error. There might be hundreds of thousands, or even more persistent connections to a chat server. If a chat server goes offline, service discovery (Zookeeper) will provide a new chat server for clients to establish new connections with.

Message resent mechanism. Retry and queueing are common techniques for resending messages.

Congratulations on getting this far! Now give yourself a pat on the back. Good job!

Reference materials
[1] Erlang at Facebook:
https://www.erlang-factory.com/upload/presentations/31/EugeneLetuchy-ErlangatFacebook.pdf

[2] Messenger and WhatsApp process 60 billion messages a day:
https://www.theverge.com/2016/4/12/11415198/facebook-messenger-whatsapp-number-messages-vs-sms-f8-2016

[3] Long tail: https://en.wikipedia.org/wiki/Long_tail

[4] The Underlying Technology of Messages:
https://www.facebook.com/notes/facebook-engineering/the-underlying-technology-of-messages/454991608919/

[5] How Discord Stores Billions of Messages:
https://discord.com/blog/how-discord-stores-billions-of-messages

[6] Announcing Snowflake: https://blog.twitter.com/engineering/en_us/a/2010/announcing-snowflake.html

[7] Apache ZooKeeper: https://zookeeper.apache.org/

[8] From nothing: the evolution of WeChat background system (Article in Chinese):
https://www.infoq.cn/article/the-road-of-the-growth-weixin-background

[9] End-to-end encryption: https://faq.whatsapp.com/en/android/28030015/

[10] Flannel: An Application-Level Edge Cache to Make Slack Scale:
https://slack.engineering/flannel-an-application-level-edge-cache-to-make-slack-scale-b8a6400e2f6b