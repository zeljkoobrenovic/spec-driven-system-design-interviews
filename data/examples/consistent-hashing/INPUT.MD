06
Design Consistent Hashing
To achieve horizontal scaling, it is important to distribute requests/data efficiently and evenly across servers. Consistent hashing is a commonly used technique to achieve this goal. But first, let us take an in-depth look at the problem.

The rehashing problem
If you have n cache servers, a common way to balance the load is to use the following hash method:

serverIndex = hash(key) % N, where N is the size of the server pool.

Let us use an example to illustrate how it works. As shown in Table 1, we have 4 servers and 8 string keys with their hashes.

key	hash	hash % 4
key0	18358617	1
key1	26143584	0
key2	18131146	2
key3	35863496	0
key4	34085809	1
key5	27581703	3
key6	38164978	2
key7	22530351	3
Table 1

To fetch the server where a key is stored, we perform the modular operation f(key) % 4. For instance, hash(key0) % 4 = 1 means a client must contact server 1 to fetch the cached data. Figure 1 shows the distribution of keys based on Table 1.

Image represents a simple consistent hashing scheme for distributing keys across four servers.  The top line shows the formula `serverIndex = hash % 4`, indicating that a key's hash value (presumably a numerical representation generated from the key itself) is modulo-4'd to determine which server (indexed 0-3) it's assigned to. Below, four servers (`server 0`, `server 1`, `server 2`, `server 3`) are depicted as colored boxes, each associated with a server index (0, 1, 2, 3 respectively).  Underneath the servers, a list of keys (`key1`, `key0`, `key2`, `key5`, `key6`, `key7`) is shown, with some keys (e.g., `key1`, `key0`) visually associated with specific servers based on their implied hash value and the modulo operation.  The text 'keover does not luppo full SVG ikey6' appears to be a corrupted or incomplete label associated with `key6`, suggesting a potential issue with the image's OCR.  The overall diagram illustrates a basic load balancing strategy where keys are distributed across servers using a consistent hashing algorithm to ensure even distribution and minimize data movement during rebalancing.
Figure 1
This approach works well when the size of the server pool is fixed, and the data distribution is even. However, problems arise when new servers are added, or existing servers are removed. For example, if server 1 goes offline, the size of the server pool becomes 3. Using the same hash function, we get the same hash value for a key. But applying modular operation gives us different server indexes because the number of servers is reduced by 1. We get the results as shown in Table 2 by applying hash % 3:

key	hash	hash % 3
key0	18358617	0
key1	26143584	0
key2	18131146	1
key3	35863496	2
key4	34085809	1
key5	27581703	0
key6	38164978	1
key7	22530351	0
Table 2

Figure 2 shows the new distribution of keys based on Table 2.

Image represents a simple consistent hashing scheme for distributing keys across three servers.  The top line shows the formula `serverIndex = hash % 3`, indicating that a key's hash value (modulo 3) determines its assigned server.  Below, 'Server Index' labels columns representing server indices 0, 1, and 2.  Corresponding to each index is a labeled server box ('server 0', 'server 1', 'server 2', and 'server 3' although only three are used in the hashing scheme).  The 'Keys' section lists example keys ('key0', 'key1', 'key2', 'key3', 'key4', 'key5', 'key6') which would be distributed across the servers based on their hash values.  For instance, `hash('key0') % 3` would likely result in 0, assigning `key0` to `server 0`, and similarly for other keys.  The visual arrangement shows a conceptual mapping of keys to servers using the modulo operation.  The presence of 'server 3' suggests potential future expansion beyond the current three-server setup.
Figure 2
As shown in Figure 2, most keys are redistributed, not just the ones originally stored in the offline server (server 1). This means that when server 1 goes offline, most cache clients will connect to the wrong servers to fetch data. This causes a storm of cache misses. Consistent hashing is an effective technique to mitigate this problem.

Consistent hashing
Quoted from Wikipedia: "Consistent hashing is a special kind of hashing such that when a hash table is re-sized and consistent hashing is used, only k/n keys need to be remapped on average, where k is the number of keys, and n is the number of slots. In contrast, in most traditional hash tables, a change in the number of array slots causes nearly all keys to be remapped [1]”.

Hash space and hash ring
Now we understand the definition of consistent hashing, let us find out how it works. Assume SHA-1 is used as the hash function f, and the output range of the hash function is: x0, x1, x2, x3, …, xn. In cryptography, SHA-1’s hash space goes from 0 to 2^160 - 1. That means x0 corresponds to 0, xn corresponds to 2^160 – 1, and all the other hash values in the middle fall between 0 and 2^160 - 1. Figure 3 shows the hash space.

Image represents a simplified diagram illustrating data processing or transformation.  A long, rectangular box, representing a system or process, is shown horizontally.  On the left, an arrow labeled 'x0' points downwards into the top of the box, indicating input data labeled 'x0' entering the system. On the right, an arrow labeled 'xn' points downwards into the top of the box from above, indicating output data labeled 'xn' exiting the system. The box itself contains the text 'Viewer does not support full SVG 1.1,' indicating that the original diagram was likely an SVG image that cannot be fully rendered by the current viewer.  The overall structure suggests a linear transformation where input 'x0' is processed within the system to produce output 'xn.'  No internal details of the processing within the box are visible.
Figure 3
By collecting both ends, we get a hash ring as shown in Figure 4:

Image represents a simplified diagram illustrating a circular buffer or ring buffer data structure.  The circle depicts the buffer itself, a fixed-size memory region used for storing data.  A short vertical line segment inside the circle represents the current write pointer, indicating the location where the next data element will be written.  Two arrows point to the top of this vertical line, labeled 'x0' and 'xn'.  'x0' likely indicates the starting address or index of the buffer, while 'xn' represents the current write index, showing the location where the next data element will be written.  The data flows into the buffer at 'xn', and as the buffer fills, 'xn' moves around the circle.  Once 'xn' reaches the end, it wraps around to the beginning, overwriting older data if the buffer is full.  The absence of a read pointer suggests a simplified representation focusing solely on the write operation. The text 'Viewer does not support full SVG 1.1' at the bottom is a browser-related message indicating the image rendering limitations and is not part of the data structure itself.
Figure 4
Hash servers
Using the same hash function f, we map servers based on server IP or name onto the ring. Figure 5 shows that 4 servers are mapped on the hash ring.

Image represents a conceptual diagram illustrating a system of four servers (server 0, server 1, server 2, and server 3), each represented by a colored square on the left, and their arrangement in a ring topology.  The servers are also represented as nodes (s0, s1, s2, s3) in a circular gray line forming the ring.  Each node is color-coded to match its corresponding server label on the left.  A dark gray arrow points from the top to node s0, labeled 'f (server 0),' indicating a function or operation 'f' is performed on server 0.  The text 's0 = server 0...' to the right of the ring suggests that node s0 represents server 0 and potentially additional information associated with it.  The nodes are connected by the circular line, implying communication or data flow between them within the ring structure.  The bottom of the image contains a message indicating that the viewer does not support full SVG 1.1, which is likely a rendering issue unrelated to the core system representation.
Figure 5
Hash keys
One thing worth mentioning is that hash function used here is different from the one in “the rehashing problem,” and there is no modular operation. As shown in Figure 6, 4 cache keys (key0, key1, key2, and key3) are hashed onto the hash ring

Image represents a circular arrangement of components depicting a system architecture.  A gray circle forms the backbone, upon which four colored nodes (s0, s1, s2, s3) are placed equidistantly. These nodes, labeled s0, s1, s2, and s3, represent servers, with their corresponding server numbers (server 0, server 1, server 2, server 3) listed in colored boxes to the left.  The colors of the server boxes match the colors of the corresponding nodes on the circle. Four black nodes (k0, k1, k2, k3) are also placed on the circle, interspersed between the colored server nodes.  These black nodes likely represent keys or other control points within the system.  A text annotation 's0 = server 0s1...' to the right indicates that the s0 node's label is shorthand for a more complex identifier potentially including other server instances.  The gray circle connecting all nodes suggests a ring topology or a cyclical dependency between the components. No explicit information flow is shown, but the arrangement implies interaction or communication between adjacent nodes along the circle.
Figure 6
Server lookup
To determine which server a key is stored on, we go clockwise from the key position on the ring until a server is found. Figure 7 explains this process. Going clockwise, key0 is stored on server 0; key1 is stored on server 1; key2 is stored on server 2 and key3 is stored on server 3.

Image represents a circular arrangement of nodes representing servers and keys, connected by a gray circular path.  Four colored nodes labeled `s0`, `s1`, `s2`, and `s3` represent servers, with `s0` (light purple) being explicitly identified as 'server 0s1...' suggesting it represents a composite of servers.  These server nodes are positioned along the outer edge of the circle. Four black nodes labeled `k0`, `k1`, `k2`, and `k3` represent keys and are located on the same circular path, but slightly inward from the server nodes.  Black arrows indicate the direction of information flow or connections.  `k0` connects to `s0`, `k3` connects to `s3`, `k2` connects to `s2`, and `k1` connects to `s1`.  A separate box on the left lists 'Servers' and shows four colored rectangles labeled 'server 0,' 'server 1,' 'server 2,' and 'server 3,' mirroring the colors of the corresponding server nodes in the circular diagram.  The overall structure suggests a ring topology with keys associated with each server, implying a system where keys control access to or interaction with the servers.
Figure 7
Add a server
Using the logic described above, adding a new server will only require redistribution of a fraction of keys.

In Figure 8, after a new server 4 is added, only key0 needs to be redistributed. k1, k2, and k3 remain on the same servers. Let us take a close look at the logic. Before server 4 is added, key0 is stored on server 0. Now, key0 will be stored on server 4 because server 4 is the first server it encounters by going clockwise from key0’s position on the ring. The other keys are not redistributed based on consistent hashing algorithm.

Image represents a circular arrangement of nodes representing servers and keys.  Five colored nodes labeled `s0`, `s1`, `s2`, `s3`, and `s4` represent servers 0 through 4 respectively, with their corresponding colors matching a legend on the left showing server labels and colors (purple, light blue, pink, orange, and green).  Five black nodes labeled `k0`, `k1`, `k2`, `k3`, and implicitly `k4` (though not explicitly labeled) represent keys.  A thick gray arc connects the server nodes in a circular fashion.  Solid arrows indicate a directed connection from `k0` to `s4` labeled 'keyo' and a dashed arrow shows a connection from `k0` to `s0`.  A text annotation states that `s0` represents server 0, server 1, and so on.  The keys are positioned between the servers, and the image suggests a relationship between keys and servers, possibly indicating ownership or access control.  The bottom of the image shows 'key2' indicating the label for key `k2`.  The text 'Viewer does not support full SVG 1.1' indicates a rendering issue.
Figure 8
Remove a server
When a server is removed, only a small fraction of keys require redistribution with consistent hashing. In Figure 9, when server 1 is removed, only key1 must be remapped to server 2. The rest of the keys are unaffected.

Image represents a circular arrangement of nodes connected by a gray arc, representing a ring topology.  Four colored nodes labeled `s0`, `s1`, `s2`, and `s3` are positioned along the outer arc, representing servers.  These server nodes are color-coded and correspond to a list of servers on the left: `s0` (light purple) corresponds to `server 0` (light purple box), `s1` (light blue) to `server 1` (light blue box), `s2` (pink) to `server 2` (pink box), and `s3` (light orange) to `server 3` (light orange box). Four black nodes labeled `k0`, `k1`, `k2`, and `k3` are interspersed between the server nodes along the same arc, likely representing keys or control points. A thick black curved arrow points from `k2` to `s2`, suggesting a unidirectional data flow or control mechanism.  The text 's0 = server 0s1...' indicates that the `s0` node's label is an abbreviation representing a sequence of servers. The bottom of the image contains a message indicating that the viewer does not fully support the SVG format used to create the diagram.
Figure 9
Two issues in the basic approach
The consistent hashing algorithm was introduced by Karger et al. at MIT [1]. The basic steps are:

Map servers and keys on to the ring using a uniformly distributed hash function.

To find out which server a key is mapped to, go clockwise from the key position until the first server on the ring is found.

Two problems are identified with this approach. First, it is impossible to keep the same size of partitions on the ring for all servers considering a server can be added or removed. A partition is the hash space between adjacent servers. It is possible that the size of the partitions on the ring assigned to each server is very small or fairly large. In Figure 10, if s1 is removed, s2’s partition (highlighted with the bidirectional arrows) is twice as large as s0 and s3’s partition.

Image represents a circular arrangement of four servers (s0, s1, s2, s3) depicted as colored circles, labeled with 's' followed by a number.  These servers are positioned along a grey circular path.  To the left, a vertical stack of colored rectangular boxes labeled 'Servers' lists 'server 0,' 'server 1,' 'server 2,' and 'server 3,' seemingly corresponding to the colored circles on the ring.  A bright pink curved arrow indicates data flow, starting from server s1, proceeding to server s2, and then continuing to server s0.  The text 's0 = server 0s1...' suggests that server s0's identity incorporates information from servers 0 and 1.  At the bottom, a message 'Viewer does not support full SVG 1.1' indicates a limitation in rendering the diagram's full visual detail.
Figure 10
Second, it is possible to have a non-uniform key distribution on the ring. For instance, if servers are mapped to positions listed in Figure 11, most of the keys are stored on server 2. However, server 1 and server 3 have no data.

Image represents a circular arrangement of servers, depicted as a gray ring with colored nodes representing individual servers.  Four colored nodes, labeled `s0`, `s1`, `s2`, and `s3`, are positioned along the ring's circumference, each representing a specific server.  `s0` is light purple, `s1` is light blue, `s2` is pink, and `s3` is light orange.  A text annotation next to `s0` clarifies that `s0` corresponds to `server 0s1...`, suggesting a naming convention.  Between the colored nodes are four uncolored, white circles along the ring, indicating potential additional server locations or connection points.  To the left of the circular arrangement, a vertical list displays four rectangular boxes, each labeled `server 0`, `server 1`, `server 2`, and `server 3`, respectively, mirroring the color scheme of the nodes on the ring and providing a key to their identification.  The bottom of the image contains a message indicating that the viewer does not support full SVG 1.1.  The overall diagram suggests a ring topology or a distributed system where servers are interconnected in a circular fashion.
Figure 11
A technique called virtual nodes or replicas is used to solve these problems.

Virtual nodes
A virtual node refers to the real node, and each server is represented by multiple virtual nodes on the ring. In Figure 12, both server 0 and server 1 have 3 virtual nodes. The 3 is arbitrarily chosen; and in real-world systems, the number of virtual nodes is much larger. Instead of using s0, we have s0_0, s0_1, and s0_2 to represent server 0 on the ring. Similarly, s1_0, s1_1, and s1_2 represent server 1 on the ring. With virtual nodes, each server is responsible for multiple partitions. Partitions (edges) with label s0 are managed by server 0. On the other hand, partitions with label s1 are managed by server 1.

Image represents a system architecture diagram illustrating data flow between two servers (labeled 'server 0' and 'server 1') using a ring topology.  The diagram shows a circular arrangement of nodes, with four nodes colored purple (labeled `s0_0`, `s0_1`, `s0_2`, representing server 0's data) and four nodes colored light blue (`s1_0`, `s1_1`, `s1_2`, representing server 1's data).  A thick dark gray line connects these nodes in a circular fashion, representing the main data pathway.  Thinner lines, colored light purple and light blue, depict data transfer between specific nodes.  Light purple lines (labeled `s0`) represent data flow originating from server 0, while light blue lines (labeled `s1`) represent data flow from server 1.  For example, a light purple line connects `s0_2` to `s1_2`, indicating data transfer from server 0's second data point to server 1's second data point.  Similarly, a light blue line connects `s1_0` to `s0_0`, showing data transfer in the opposite direction.  The text 's0 = server 0s1...' suggests that the `s0` labels represent a composite data identifier combining data from both servers.  A note at the bottom indicates that the viewer does not fully support the SVG format used in the diagram.
Figure 12
To find which server a key is stored on, we go clockwise from the key’s location and find the first virtual node encountered on the ring. In Figure 13, to find out which server k0 is stored on, we go clockwise from k0’s location and find virtual node s1_1, which refers to server 1.

Image represents a system architecture diagram showing two servers, labeled 'server 0' (purple) and 'server 1' (cyan), and their interaction with a ring-shaped network.  The ring consists of six nodes:  three labeled `s0_0`, `s0_1`, `s0_2` (purple) representing instances on server 0, and three labeled `s1_0`, `s1_1`, `s1_2` (cyan) representing instances on server 1.  These nodes are arranged around a grey circular line, indicating a ring topology.  A separate black node, labeled `k0`, is connected to the ring and has a self-looping arrow pointing back to itself, suggesting a control or coordination function.  A text annotation near the top right clarifies that `s0` represents server 0 instances (`0s1...`), implying a naming convention.  The bottom of the diagram displays a message indicating that the viewer does not fully support the SVG format used to create the image.
Figure 13
As the number of virtual nodes increases, the distribution of keys becomes more balanced. This is because the standard deviation gets smaller with more virtual nodes, leading to balanced data distribution. Standard deviation measures how data are spread out. The outcome of an experiment carried out by online research [2] shows that with one or two hundred virtual nodes, the standard deviation is between 5% (200 virtual nodes) and 10% (100 virtual nodes) of the mean. The standard deviation will be smaller when we increase the number of virtual nodes. However, more spaces are needed to store data about virtual nodes. This is a tradeoff, and we can tune the number of virtual nodes to fit our system requirements.

Find affected keys
When a server is added or removed, a fraction of data needs to be redistributed. How can we find the affected range to redistribute the keys?

In Figure 14, server 4 is added onto the ring. The affected range starts from s4 (newly added node) and moves anticlockwise around the ring until a server is found (s3). Thus, keys located between s3 and s4 need to be redistributed to s4.

Image represents a circular arrangement of nodes representing servers and keys.  Five colored nodes labeled `s0`, `s1`, `s2`, `s3`, and `s4` represent servers 0 through 4 respectively, with their corresponding colors matching a legend of rectangular server boxes on the left.  Five black nodes labeled `k0`, `k1`, `k2`, `k3`, and implicitly `k4` (though not explicitly labeled) represent keys.  A thick gray arc connects the server nodes in a circular fashion.  Solid arrows indicate a directed connection from `k0` to `s4` labeled 'keyo' and a dashed arrow shows a connection from `k0` to `s0`.  Another dashed arrow shows a connection from `s4` to `s0`. The text 's0 = server 0s1...' indicates that `s0` represents a composite or aggregated server.  The keys are positioned between the servers along the gray arc.  The overall structure suggests a ring topology with keys potentially acting as routing or access points between servers.
Figure 14
When a server (s1) is removed as shown in Figure 15, the affected range starts from s1 (removed node) and moves anticlockwise around the ring until a server is found (s0). Thus, keys located between s0 and s1 must be redistributed to s2.

Image represents a circular arrangement of nodes connected by a gray arc, representing a ring topology.  Four colored nodes labeled `s0`, `s1`, `s2`, and `s3` are positioned along the outer arc, representing servers.  `s0` is light purple, `s1` is light blue, `s2` is pink, and `s3` is light orange.  These server nodes are further identified by a text annotation stating `s0 = server 0s1...`, implying a naming convention. Four black-filled nodes labeled `k0`, `k1`, `k2`, and `k3` are placed at the intersections of the gray arc and the imaginary radii connecting the colored server nodes to the center. These `k` nodes likely represent key components or points within the system. A thick black curved arrow points from `k2` to `s2`, suggesting a unidirectional flow or dependency.  To the left, a rectangular box labeled 'Servers' lists four colored rectangles representing servers 0, 1, 2, and 3, mirroring the colors of the `s` nodes in the ring.  The bottom of the image contains a message indicating that the viewer does not fully support the SVG format used to create the diagram.
Figure 15
Wrap up
In this chapter, we had an in-depth discussion about consistent hashing, including why it is needed and how it works. The benefits of consistent hashing include:

Minimized keys are redistributed when servers are added or removed.

It is easy to scale horizontally because data are more evenly distributed.

Mitigate hotspot key problem. Excessive access to a specific shard could cause server overload. Imagine data for Katy Perry, Justin Bieber, and Lady Gaga all end up on the same shard. Consistent hashing helps to mitigate the problem by distributing the data more evenly.

Consistent hashing is widely used in real-world systems, including some notable ones:

Partitioning component of Amazon’s Dynamo database [3]

Data partitioning across the cluster in Apache Cassandra [4]

Discord chat application [5]

Akamai content delivery network [6]

Maglev network load balancer [7]

Congratulations on getting this far! Now give yourself a pat on the back. Good job!

Reference materials
[1] Consistent hashing:
https://en.wikipedia.org/wiki/Consistent_hashing

[2] Consistent Hashing:
https://tom-e-white.com/2007/11/consistent-hashing.html

[3] Dynamo: Amazon’s Highly Available Key-value Store:
https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf

[4] Cassandra - A Decentralized Structured Storage System:
http://www.cs.cornell.edu/Projects/ladis2009/papers/Lakshman-ladis2009.PDF

[5] How Discord Scaled Elixir to 5,000,000 Concurrent Users:
https://discord.com/blog/how-discord-scaled-elixir-to-5-000-000-concurrent-users

[6] CS168: The Modern Algorithmic Toolbox Lecture #1: Introduction and Consistent Hashing:
http://theory.stanford.edu/~tim/s16/l/l1.pdf

[7] Maglev: A Fast and Reliable Software Network Load Balancer:
https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/44824.pdf