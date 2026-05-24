Video Recommendation System
Recommendation systems play a key role in video and music streaming services. For example, YouTube recommends videos a user may like, Netflix recommends movies a user may enjoy watching, and Spotify recommends music to users.

In this chapter, we design a video recommendation system similar to YouTube's [1]. The system recommends videos on the user's homepage based on their profile, previous interactions, etc.

Image represents a simplified mockup of a webpage interface.  The top section displays standard browser controls: a back arrow, a forward arrow, a refresh button, a file upload icon, and a blank search bar with a magnifying glass icon to its right. Below the search bar, the text 'Recommended for you' precedes a grid of eight square thumbnails. Each thumbnail is a pastel color (light green, light blue, light yellow, light pink, white, light purple, cream, and pale yellow) and contains a black video camera icon, suggesting video content recommendations.  The overall layout is clean and minimalistic, typical of a user interface focused on content display and search functionality.  No URLs or specific parameters are visible.
Figure 6.1: Homepage video recommendation
Recommendation systems are often very complex in design, and a good amount of engineering effort is required to develop an efficient and scalable system. Don't worry, though; no one expects you to build the perfect system in a 45 -minute interview. The interviewer is primarily interested in observing your thought process, communication skills, ability to design ML systems, and ability to discuss trade-offs.

Clarifying Requirements
Here is a typical interaction between a candidate and an interviewer.

Candidate: Can I assume the business objective of building a video recommendation system is to increase user engagement?
Interview: That’s correct.

Candidate: Does the system recommend similar videos to a video a user is watching right now? Or does it show a personalized list of videos on the user’s homepage?
Interviewer: This is a homepage video recommendation system, which recommends personalized videos to users when they load the homepage.

Candidate: Since YouTube is a global service, can I assume users are located worldwide and videos are in different languages?
Interviewer: That’s a fair assumption.

Candidate: Can I assume we can construct the dataset based on user interactions with video content?
Interviewer: Yes, that sounds good.

Candidate: Can a user group videos together by creating playlists? Playlists can be informative for the ML model during the learning phase.
Interviewer: For the sake of simplicity, let’s assume the playlist feature does not exist.

Candidate: How many videos are available on the platform?
Interviewer: We have about 10 billion videos.

Candidate: How fast should the system recommend videos to a user? Can I assume the recommendation should not take more than 200 milliseconds?
Interviewer: That sounds good.

Let’s summarize the problem statement. We are asked to design a homepage video recommendation system. The business objective is to increase user engagement. Each time a user loads the homepage, the system recommends the most engaging videos. Users are located worldwide, and videos can be in different languages. There are approximately 10 billion videos on the platform, and recommendations should be served quickly.

Frame the Problem as an ML Task
Defining the ML objective
The business objective of the system is to increase user engagement. There are several options available for translating business objectives into well-defined ML objectives. We will examine some of them and discuss their trade-offs.

Maximize the number of user clicks. A video recommendation system can be designed to maximize user clicks. However, this objective has one major drawback. The model may recommend videos that are so-called "clickbait", meaning the title and thumbnail image look compelling, but the video's content may be boring, irrelevant, or even misleading. Clickbait videos reduce user satisfaction and engagement over time.

Maximize the number of completed videos. The system could also recommend videos users will likely watch to completion. A major problem with this objective is that the model may recommend shorter videos that are quicker to watch.

Maximize total watch time. This objective produces recommendations that users spend more time watching.

Maximize the number of relevant videos. This objective produces recommendations that are relevant to users. Engineers or product managers can define relevance based on some rules. Such rules can be based on implicit and explicit user reactions. For example, one definition could state a video is relevant if a user explicitly presses the "like" button or watches at least half of it. Once we define relevance, we can construct a dataset and train a model to predict the relevance score between a user and a video.

In this system, we choose the final objective as the ML objective because we have more control over what signals to use. In addition, it does not have the shortcomings of the other options described earlier.

Specifying the system’s input and output
As Figure 6.2 shows, a video recommendation system takes a user as input and outputs a ranked list of videos sorted by their relevance scores.

Image represents a simplified video recommendation system.  A user, depicted as a person icon, provides input to a 'Video recommendation system' block. This system interacts with a database labeled 'Videos,' indicated by a cylinder, to retrieve relevant information.  The system then outputs a list of 'Recommended videos,' shown as four color-coded rectangles (light red, light purple, light green, and light blue), each containing a camera icon representing a video and labeled 'Video 1,' 'Video 2,' 'Video 3,' and 'Video 4' respectively.  Arrows illustrate the flow of information: from the user to the system, from the database to the system, and from the system to the recommended videos.  The entire process shows how user input is processed by the system, using data from the video database, to generate personalized video recommendations.
Figure 6.2: A video recommendation system’s input-output
Choosing the right ML category
In this section, we examine three common types of personalized recommendation systems.

Content-based filtering
Collaborative filtering
Hybrid filtering
Image represents a hierarchical diagram illustrating different types of recommendation systems.  At the top is a box labeled 'Recommendation system,' which branches into two main categories: 'Personalized' and 'Non-personalized.' The 'Personalized' category further subdivides into three types of filtering techniques: 'Content-based filtering,' 'Collaborative filtering,' and 'Hybrid filtering,' each represented by a separate box connected to the 'Personalized' box with a downward-pointing arrow indicating a hierarchical relationship.  Similarly, the 'Non-personalized' category leads to a single box labeled 'Rule-based filtering,' also connected with a downward-pointing arrow.  The arrows visually represent the flow of information or the categorization of recommendation system types, showing how the broader category of recommendation systems is broken down into more specific approaches based on personalization and the underlying filtering methods.
Figure 6.3: Common types of recommendation systems
Let’s examine each type in more detail.

Content-based filtering
This technique uses video features to recommend new videos similar to those a user found relevant in the past. For example, if a user previously engaged with many ski videos, this method will suggest more ski videos. Figure 
6.4
6.4 shows an example.

Image represents a simplified recommendation system.  A user, labeled 'User A,' is depicted as a person icon. A solid black arrow shows User A liking two videos, 'Video X' (light pink rectangle with a video camera icon) and 'Video Y' (light purple rectangle with a video camera icon). These videos are enclosed within a dashed-line box labeled 'User A liked.'  A downward black arrow indicates that these liked videos are used to identify 'Similar video,' which is then used to recommend 'Video Z' (light cyan rectangle with a video camera icon) to User A. This recommendation is represented by a dashed red arrow labeled 'User A may like,' suggesting a probabilistic recommendation based on the similarity of videos X and Y to Video Z.  The overall diagram illustrates a user's interaction with a system that uses their viewing history to suggest similar content.
Figure 6.4: Content-based filtering
Here is an explanation of the diagram.

User A engaged with videos 
X
X and 
Y
Y in the past
Video 
Z
Z is similar to video 
X
X and video 
Y
Y
The system recommends video 
Z
Z to user 
A
A
Content-based filtering has pros and cons.

Pros:

Ability to recommend new videos. With this method, we don't need to wait for interaction data from users to build video profiles for new videos. The video profile depends entirely upon its features.
Ability to capture the unique interests of users. This is because we recommend videos based on users' previous engagements.
Cons:

Difficult to discover a user's new interests.
The method requires domain knowledge. We often need to engineer video features manually.
Collaborative filtering (CF)
CF uses user-user similarities (user-based CF) or video-video similarities (item-based CF) to recommend new videos. CF works with the intuitive idea that similar users are interested in similar videos. You can see a user-based CF example in Figure 6.5.

Image represents a recommendation system illustrating user-based collaborative filtering.  Three videos, labeled 'Video X' (light pink), 'Video Y' (pink), and 'Video Z' (light green), are depicted as rectangles containing a video camera icon.  Two users, 'User A' and 'User B,' are represented by black person icons.  Solid arrows indicate 'like' relationships, showing that User B liked Videos X, Y, and Z.  A solid arrow labeled 'Similar user' connects User B to User A, suggesting a similarity in their preferences.  User A liked Videos X and Y, represented by solid arrows. A dashed red arrow from User A points to Video Z, labeled 'user A may like,' indicating a recommendation based on the similarity between User A and User B's viewing habits.  The system infers that because User B liked Video Z, and User A is similar to User B, User A might also like Video Z.
Figure 6.5: User-based collaborative filtering
Let's explain the diagram. The goal is to recommend a new video to user A.

Find a similar user to 
A
A based on their previous interactions; say user 
B
B
Find a video that user B engaged with but which user A has not seen yet; say video 
Z
Z
Recommend video 
Z
Z to user 
A
A
A major difference between content-based filtering and CF filtering is that CF filtering does not use video features and relies exclusively upon users' historical interactions to make recommendations. Let's see the pros and cons of CF filtering.

Pros:

No domain knowledge needed. CF does not rely on video features, which means no domain knowledge is needed to engineer features from videos.
Easy to discover users' new areas of interest. The system can recommend videos about new topics that other similar users engaged with in the past.
Efficient. Models based on CF are usually faster and less compute-intensive than content-based filtering, as they do not rely on video features.
Cons:

Cold-start problem. This refers to a situation when limited data is available for a new video or user, meaning the system cannot make accurate recommendations. CF suffers from a cold-start problem due to the lack of historical interaction data for new users or videos. This lack of interactions prevents CF from finding similar users or videos. We will discuss later in the serving section how our system handles the cold-start problem.
Cannot handle niche interests. It's difficult for CF to handle users with specialized or niche interests. CF relies upon similar users to make recommendations, and it might be difficult to find similar users with niche interests.
Contentbased filtering	Collaborative filtering
Handle new videos	✓	✘
Discover new interest areas	✘	✓
No domain knowledge necessary	✘	✓
Efficiency	✘	✓
Table 6.1: Comparison between content-based filtering and CF


A comparison of the two types of filtering is shown in Table 6.1. As you see, the two methods are complementary.

Hybrid filtering
Hybrid filtering uses both CF and content-based filtering. As Figure 6.6 shows, hybrid filtering combines CF-based and content-based recommenders sequentially, or in parallel. In practice, companies usually use sequential hybrid filtering [2].

Image represents two distinct approaches to hybrid filtering in a recommendation system.  The top section, labeled 'Parallel hybrid filtering,' shows two recommendation methods ('CF-based recommendation' and 'Content-based recommendation') receiving the same 'Inputs' concurrently.  Their outputs are then fed into a 'Combiner' module, which processes both recommendations simultaneously to generate final 'Recommendations.' The bottom section, labeled 'Sequential hybrid filtering,' illustrates a different process. Here, 'Inputs' are first processed by 'CF-based recommendation,' and its output is then fed into 'Content-based recommendation,' which produces the final 'Recommendations' sequentially.  Both diagrams use rectangular boxes to represent processing modules and arrows to indicate the flow of data between them.  The dashed lines delineate the boundaries of each filtering method.
Figure 6.6: Hybrid filtering method
This approach leads to better recommendations because it uses two data sources: the user's historical interactions and video features. Video features allow the system to recommend relevant videos based on videos the user engaged with in the past, and CF-based filtering helps users to discover new areas of interest.

Which method should we choose?
Many companies use hybrid filtering to make better recommendations. For example, a paper published by Google [2] describes how YouTube employs a CF-based model as the first stage (candidate generator), followed by a content-based model as the second stage, to recommend videos. Due to the advantages of hybrid filtering, we choose this option.

Data Preparation
Data engineering
We have the following data available:

Videos
Users
User-video interactions
Videos
Video data contains raw video files and their associated metadata, such as video ID, video length, video title, etc. Some of these attributes are provided explicitly by video uploaders, and others can be implicitly determined by the system, such as the video length.

Video ID	Length	Manual tags	Manual title	Likes	Views	Language
1	28	Dog, Family	Our lovely dog playing!	138	5300	English
2	300	Car, Oil	How to change your car oil?	5	250	Spanish
3	3600	Ouli, Vlog	Honeymoon to Bali	2200	255K	Arabic
Table 6.2: Video metadata

Users
The following simple schema represents user data.

ID	Username	Age	Gender	City	Country	Language	Time zone
Table 6.3: User data schema

User-video interactions
The user-video interaction data consists of various user interactions with the videos, including likes, clicks, impressions, and past searches. Interactions are recorded along with other contextual information, such as location and timestamp. The following table shows how user-video interactions are stored.

User ID	Video ID	Interaction type	Interaction value	Location (lat, long)	Timestamp
4	18	Like	-	38.8951
-77.0364	1658451361
2	18	Impression	8 seconds	38.8951
-77.0364	1658451841
2	6	Watch	46 minutes	41.9241
-89.0389	1658822820
6	9	Click	-	22.7531
47.9642	1658832118
9	-	Search	Basics of clustering	22.7531
47.9642	1659259402
8	6	Comment	Amazing video. Thanks	37.5189
122.6405	1659244197
Table 6.4: User-video interaction data

Feature engineering
The ML system is required to predict videos that are relevant to users. Let's engineer features to help the system make informed predictions.

Video features
Some important video features include:

Video ID
Duration
Language
Titles and tags
Video ID
The IDs are categorical data. To represent them by numerical vectors, we use an embedding layer, and the embedding layer is learned during model training.

Duration
This defines approximately how long the video lasts from start to finish. This information is important since some users may prefer shorter videos, while others prefer longer videos.

Language
The language used in a video is an important feature. This is because users naturally prefer particular languages. Since language is a categorical variable and takes on a finite set of discrete values, we use an embedding layer to represent it.

Titles and tags
Titles and tags are used to describe a video. They are either provided manually by the uploader or are implicitly predicted by standalone ML models. The titles and tags of a video are valuable predictors. For example, a video titled "how to make pizza" indicates the video is related to pizza and cooking.

How to prepare it? For tags, we use a lightweight pre-trained model, such as CBOW [3], to map them into feature vectors.

For the title, we map it into a feature vector using a context-aware word embedding model, such as a pre-trained BERT [4].

Figure 6.7 shows an overview of video feature preparation.

Image represents a hierarchical feature concatenation and aggregation process for a machine learning model.  At the top, 'Concatenated features' acts as the root node, branching down to five distinct feature sources. Two branches lead to 'Embedding' blocks, each further subdivided into a textual feature (e.g., 'English Language' and 'Video ID' respectively) represented by a single value. Another branch connects to 'Pre-trained BERT,' which processes a 'Title' ('our last anniversary') resulting in a vector of three numerical values (0.1, 0.2, 1). A fourth branch connects to 'CBOW,' processing 'Tags' ('Dance, Music') and producing a vector of three numerical values (0.3, 0.8, 0). Finally, a fifth branch directly provides a vector of three numerical values (0.5, 0.9, -0.1).  All these vectors are then aggregated in a final 'Aggregate' node, which combines the numerical values from each branch into two output vectors, each containing three numerical values (0.3, 0.8, 0) and (0.7, 1, -0.2) respectively.  The entire structure illustrates how diverse features are processed and combined to form a unified feature representation for the machine learning model.
Figure 6.7: Video feature preparation
User features
We categorize user features into the following buckets:

User demographics
Contextual information
User historical interactions
User demographics
An overview of user demographic features is shown in Figure 6.8.

Image represents a data preprocessing pipeline for a machine learning model.  The topmost box, 'Concatenated features,' represents the final output of the pipeline, a combined feature vector.  This vector is formed by concatenating the outputs of six separate feature processing branches. Each branch processes a single feature: User ID (embedding resulting in a single value '1'), Age (bucketized and one-hot encoded resulting in the value '28'), Gender (one-hot encoded as 'Female'), Language (embedding resulting in 'English'), City (embedding resulting in 'SF'), and Country (embedding resulting in 'USA').  Each branch initially receives a vector of numerical values (e.g., [0.1, 0.9, 0.2, 0.7, 1] for User ID). These vectors are then processed using different techniques: embedding (for User ID, Language, City, and Country), which transforms categorical data into numerical vectors, and bucketization plus one-hot encoding (for Age), which transforms numerical data into categorical representations. The final output of each branch is then concatenated to form the 'Concatenated features' vector used as input to the machine learning model (not shown).
Figure 6.8: Features based on a user’s demographics
Contextual information
Here are a few important features for capturing contextual information:

Time of day. A user may watch different videos at different times of day. For example, a software engineer may watch more educational videos during the evening.
Device. On mobile devices, users may prefer shorter videos.
Day of the week. Depending on the day of the week, users may have different preferences for videos.
Image represents a data preprocessing pipeline for feature engineering in a machine learning model.  The topmost box, 'Concatenated features,' represents the final output, a combined feature vector.  Three branches feed into this:  The leftmost branch processes 'Day of the week' using an 'Embedding' technique, resulting in a numerical vector (shown as a column of 1 and 0s) representing the day 'Monday'. The middle branch processes 'Time of day' using a combination of 'Bucketize' and 'One-hot' encoding, likely representing 'Morning' as a one-hot encoded vector. The rightmost branch uses 'One-hot' encoding to represent 'Device,' resulting in a vector (shown as a column of 1 and 0s) likely indicating 'Mobile'. Each of these individual feature vectors is then concatenated to form the final 'Concatenated features' vector used as input to the machine learning model.  The diagram visually shows the flow of information from raw categorical features ('Day of the week', 'Time of day', 'Device') through different encoding methods to create a numerical feature vector suitable for machine learning algorithms.
Figure 6.9: Features related to contextual information
User historical interactions
User historical interactions play an important role in understanding user interests. A few features related to historical interactions are:

Search history
Liked videos
Watched videos and impressions
Search history
Why is it important?

Previous searches indicate what the user looked for in the past, and past behavior is often an indicator of future behavior.

How to prepare it?

Use a pre-trained word embedding model, such as BERT, to map each search query into an embedding vector. Note that a user's search history is a variable-sized list of textual queries. To create a fixed-size feature vector summarizing all the search queries, we average the query embeddings.

Liked videos
Why is it important?

The videos a user liked previously can be helpful in determining which type of content they're interested in.

How to prepare it?

Video IDs are mapped into embedding vectors using the embedding layer. Similarly to search history, we average liked embeddings to get a fixed-size vector of liked videos.

Watched videos and impressions
The feature engineering process for “watched videos" and “impressions" is very similar to what we did for liked videos. So, we won’t repeat it.

Figure 6.10 summarizes features related to user-video interactions.

Image represents a machine learning model architecture for feature aggregation and concatenation.  The topmost node is labeled 'Concatenated features,' indicating the final combined feature vector.  Four branches descend from this node, each representing a different feature type. Each branch starts with an 'Aggregate' node, which presumably combines multiple individual features of the same type.  Below each 'Aggregate' node are multiple rectangular boxes representing individual features. For example, one branch shows features labeled 'Video 9,' '...,' and 'Video 5,' grouped under 'impressions.' Another branch shows 'Video 6,' '...,' and 'Video 20,' grouped under 'watched videos.' A third branch shows 'Video 11,' '...,' and 'Video 6,' grouped under 'liked videos.' The final branch uses a 'Pre-trained text model' node, with features 'travel to bali,' '...,' and 'gift ideas' grouped under 'search queries.'  All these individual feature boxes feed into a large rectangular 'Embedding' node, which likely generates a vector representation of the combined features.  The entire structure suggests a system that combines various user interaction data (impressions, watched videos, liked videos, and search queries) to create a comprehensive user embedding for downstream tasks.
Figure 6.10: Features related to user-video interactions
Model Development
In this section, we examine two embedding-based models that are typically employed in CF-based or content-based recommenders:

Matrix factorization
Two-tower neural network
Matrix factorization
To understand the matrix factorization model, it is important to know what a feedback matrix is.

Feedback matrix
Also called a utility matrix, this is a matrix that represents users' opinions about videos. Figure 6.11 shows a binary user-video feedback matrix where each row represents a user, and each column represents a video. The entries in the matrix specify the user's opinion to 1 as "observed" or "positive."

Image represents a matrix visualizing user-video interactions.  At the top, five video sources are labeled 'Video 1' through 'Video 5,' each represented by a video camera icon within a box. Below, three users, 'User 1,' 'User 2,' and 'User 3,' are represented by person icons.  A 3x5 matrix lies between the users and videos.  Each cell in the matrix represents a potential interaction between a user and a video.  The number '1' inside a cell indicates that the corresponding user has viewed the corresponding video; an empty cell signifies no viewing interaction. For example, User 1 watched Videos 1 and 2, User 2 watched Videos 3 and 4, and User 3 watched Videos 3 and 5.  The diagram illustrates a simple record of user viewing behavior across multiple video sources.
Figure 6.11: User-video feedback matrix
How can we determine whether a user finds a recommended video relevant? We have three options:

Explicit feedback
Implicit feedback
Combination of explicit and implicit feedback
Explicit feedback. A feedback matrix is built based on interactions that explicitly indicate a user's opinion about a video, such as likes and shares. Explicit feedback reflects a user's opinion accurately as users explicitly expressed their interest in a video. This option, however, has one major drawback: the matrix is sparse since only a small fraction of users provide explicit feedback. Sparsity makes ML models difficult to train.

Implicit feedback. This option uses interactions that implicitly indicate a user's opinion about a video, such as "clicks" or "watch time". With implicit feedback, more data points are available, resulting in a better model after training. Its main disadvantage is that it does not directly reflect users' opinions and might be noisy.

Combination of explicit and implicit feedback. This option combines explicit and implicit feedback using heuristics.

What is the best option for building our feedback matrix?

Since the model needs to learn the values of the feedback matrix, it's important to build the matrix that aligns well with the ML objective we chose earlier.

In our case, the ML objective is to maximize relevancy, where relevancy is defined as the combination of explicit and implicit feedback. As such, the final option of combining explicit and implicit feedback is the best choice.

Matrix factorization model
Matrix factorization is a simple embedding model. The algorithm decomposes the user-video feedback matrix into the product of two lower-dimensional matrices. One lower-dimensional matrix represents user embeddings, and the other represents video embeddings. In other words, the model learns to map each user into an embedding vector and each video into an embedding vector, such that their distance represents their relevance. Figure 
6.12
6.12 shows how a feedback matrix is decomposed into user and video embeddings.

Image represents a system for recommending videos based on user preferences.  The leftmost section shows a 'Feedback Matrix,' a 3x5 matrix where rows represent three users (User 1, User 2, User 3) and columns represent five videos (Video 1 through Video 5).  Each cell contains a numerical value (1 in this example) indicating the user's feedback on a particular video; a '1' likely signifies a positive rating or preference.  A wavy double arrow separates this matrix from the next section. The middle section displays a 'User embeddings' matrix, also 3x2, showing a numerical representation (e.g., 0.9, -0.7, 0) of each user's preferences in a lower-dimensional space.  This likely represents a learned embedding of user preferences derived from the feedback matrix. A large 'X' symbol separates the user embeddings from the rightmost section. The rightmost section is a 'Video embeddings' matrix, a 2x5 matrix containing numerical values (e.g., 0.6, -0.4, 1) representing the learned embeddings of each video in the same lower-dimensional space as the user embeddings.  The overall diagram illustrates a process where user feedback on videos is transformed into user and video embeddings, which can then be used for recommendation purposes, likely through a dot product or similar similarity calculation represented by the 'X' symbol, indicating a matrix multiplication or comparison between user and video embeddings.  Above each matrix are icons representing the five videos, visually linking the columns of the matrices to the specific videos.
Figure 6.12: Decompose the feedback matrix into two matrices
Matrix factorization training
As part of training, we aim to produce user and video embedding matrices so that their product is a good approximation of the feedback matrix (Figure 6.13.)

Image represents a system for recommending videos to users.  At the top, five video icons labeled 'Video 1' through 'Video 5' are shown. Below them is a 2x5 matrix representing user preferences for these videos, with each cell containing a numerical score (e.g., 0.6, -1, etc.).  Further down, a 3x5 matrix labeled 'Predicted scores' shows predicted scores for three users (User 1, User 2, User 3) for each of the five videos, again with numerical values in each cell (e.g., 0.9, -0.7, 0.54, etc.). A wavy double arrow (~ ~) connects the 'Predicted scores' matrix to a final 3x5 matrix labeled 'Feedback matrix.' This feedback matrix contains only 1s and blanks, suggesting a binary feedback mechanism where a '1' indicates a positive feedback or selection, and a blank indicates no feedback or rejection. The arrangement suggests that the system predicts user preferences based on the initial preference matrix and then compares these predictions to actual user feedback in the final matrix, presumably for training or evaluation purposes.
Figure 6.13: The product of embeddings should approximate the feedback matrix
To learn these embeddings, matrix factorization first randomly initializes two embedding matrices, then iteratively optimizes the embeddings to decrease the loss between the "Predicted scores matrix" and the "Feedback matrix". Loss function selection is an important consideration. Let's explore a few options:

Squared distance over observed 
⟨
⟨ user, video 
⟩
⟩ pairs
A weighted combination of squared distance over observed pairs and unobserved pairs
Squared distance over observed 
⟨
⟨ user, video 
⟩
⟩ pairs
This loss function measures the sum of the squared distances over all pairs of observed (non-zero values) entries in the feedback matrix. This is shown in Figure 6.14.

Image represents a diagram illustrating a loss function calculation in a machine learning context.  The diagram features two matrices: a 'Feedback matrix' on the left, containing several entries with the value '1' and some empty cells, and a 'Predicted scores' matrix on the right, populated with various floating-point numbers (e.g., 0.54, 0.9, -0.9, etc.).  Both matrices appear to be of the same dimension (3x4 in this example). Arrows emanate from the bottom of each matrix, converging at a loss function equation:  `loss = Σ_(i,j)∈obs (Aij - Ui . Vj)²`. This equation represents the sum of squared differences between corresponding elements of the two matrices, where `Aij` represents an element from the 'Feedback matrix', `Ui` and `Vj` are likely components of vectors used in the prediction process, and the summation is over the observed entries (`obs`).  The equation implies that the loss is calculated by comparing the predicted scores to the feedback values, with the goal of minimizing this loss during model training.
Figure 6.14: Squared distance over observed ⟨ user, video ⟩ pairs
A
i
j
A 
ij
​
  refers to the entry with row 
i
i and column 
j
j in the feedback matrix, 
U
i
U 
i
​
  is the embedding of user 
i
,
V
j
i,V 
j
​
  is the embedding of video 
j
j, and the summation is over the observed pairs only.

Only summing over observed pairs leads to poor embeddings because the loss function doesn't penalize the model for bad predictions on unobserved pairs. For example, embedding matrices of all ones would have a zero loss on the training data. However, those embeddings may not work well for unseen 
⟨
⟨ user, video 
⟩
⟩ pairs.

Squared distance over both observed and unobserved 
⟨
⟨ user, video 
⟩
⟩ pairs This loss function treats unobserved pairs as negative data points and assigns a zero to them in the feedback matrix. As Figure 6.15 shows, the loss computes the sum of the squared distances over all entries in the feedback matrix.

Image represents a diagram illustrating a loss function calculation in a machine learning context.  The diagram features two 3x4 matrices positioned side-by-side. The left matrix, labeled 'Feedback matrix,' contains binary values (0s and 1s) representing ground truth or target values. The right matrix, labeled 'Predicted scores,' contains floating-point numbers representing the model's predictions for the corresponding elements in the feedback matrix.  Arrows emanate from the bottom corners of both matrices, converging at a loss function formula:  `loss = ∑(i,j) (Aij – Ui . Vj)²`. This formula calculates the loss by summing the squared differences between the corresponding elements (Aij) of the feedback matrix and the element-wise product (Ui . Vj) of two latent vectors (U and V) derived from the predicted scores matrix.  The formula implies that the predicted scores matrix is factorized or decomposed into latent vectors U and V, and the loss measures the discrepancy between the model's predictions and the actual feedback.
Figure 6.15: Squared distance over all ⟨ user, video ⟩ pairs
This loss function addresses the previous issue by penalizing bad predictions for unobserved entries. However, this loss has a major drawback. The feedback matrix is usually sparse (lots of unobserved pairs), so unobserved pairs dominate observed pairs during training. This results in predictions that are mostly close to zero. This is not desirable and leads to poor generalization performance on unseen 
⟨
⟨ user, video 
⟩
⟩ pairs.

A weighted combination of squared distance over observed and unobserved pairs
To overcome the drawbacks of the loss functions described earlier, we opt for weighted combinations of both.

Image represents a diagram illustrating a loss function calculation in a machine learning context, likely related to matrix factorization.  The diagram features two matrices positioned side-by-side: a 'Feedback matrix' containing binary values (0s and 1s) representing observed data, and a 'Predicted scores' matrix showing corresponding floating-point values.  These matrices are of the same dimensions (3x4 in this example). Arrows emanate from each matrix, converging at a loss function equation. This equation calculates the loss by summing the squared differences between the feedback matrix (A<sub>ij</sub>) and the predicted scores (U<sub>i</sub>.V<sub>j</sub>) for observed entries ((i,j)∈obs), and adding a weighted sum (W) of the squared differences for unobserved entries ((i,j)∉obs).  The equation thus combines observed and unobserved data to compute the overall loss, suggesting a regularization technique is employed.  The weights U<sub>i</sub> and V<sub>j</sub> likely represent latent factors learned during the model training.
Figure 6.16: Combined loss
The first summation in the loss formula calculates the loss on the observed pairs, and the second summation calculates the loss on unobserved pairs. 
W
W is a hyperparameter that weighs the two summations. It ensures one does not dominate the other in the training phase. This loss function with a properly tuned 
W
W works well in practice [5]. We choose this loss function for the system.

Matrix factorization optimization
To train an ML model, an optimization algorithm is required. Two commonly used optimization algorithms in matrix factorization are:

Stochastic Gradient Descent (SGD): This optimization algorithm is used to minimize losses [6].
Weighted Alternating Least Squares (WALS): This optimization algorithm is specific to matrix factorization. The process in WALS is:
Fix one embedding matrix (U), and optimize the other embedding (V)
Fix the other embedding matrix (V), and optimize the embedding matrix (U)

Repeat.
WALS usually converges faster and is parallelizable. To learn more about WALS, read [7]. Here, we use WALS because it converges faster.
Matrix factorization inference
To predict the relevance between an arbitrary user and a candidate video, we calculate the similarity between their embeddings using a similarity measure, such as a dot product. For example, as shown in Figure 6.17, the relevance score between user 2 and video 5 is 
0.32
0.32.

Image represents a simplified illustration of a dot product calculation.  Two data sources are shown: 'User 2,' represented by a person icon, and 'Video 5,' represented by a video camera icon. Each source is associated with a two-element vector; User 2 has the vector [-0.7, 0.1], and Video 5 has the vector [-0.5, -0.3]. Arrows indicate that these vectors are inputs to a 'dot product' calculation. The calculation itself is explicitly shown as  `dot product = (-0.7) * (-0.5) + (0.1) * (-0.3) = 0.32`, demonstrating the element-wise multiplication and summation that defines the dot product. The result, 0.32, is implicitly the output of the dot product operation.  The diagram visually depicts the process of combining data from two different sources (user and video) using a vector dot product to obtain a single scalar value.
Figure 6.17: Relevance score for ⟨ user 2, video 5 ⟩ pair
Figure 6.18 shows the predicted scores for all the 
⟨
⟨ user, video 
⟩
⟩ pairs. The system returns recommended videos based on relevance scores.

Image represents a system demonstrating a recommendation system likely based on user preferences for videos.  At the top, five video sources are represented by video camera icons labeled 'Video 1' through 'Video 5'.  A 2x5 matrix to the right displays ratings for each video, with each cell containing a numerical value representing a score (e.g., 0.6, -1, etc.). Below this, a 3x2 matrix shows user preferences, where each row represents a user (User 1, User 2, User 3) and each column represents a preference score for two unspecified factors.  Finally, a 3x5 matrix displays the calculated results, likely representing a weighted preference score for each user and video combination, derived from the user preference matrix and the video rating matrix.  The values in this final matrix (e.g., 0.54, -0.46, etc.) are presumably calculated by combining the user preferences and video ratings, possibly through a dot product or similar operation.  The overall structure suggests a process of calculating personalized video recommendations based on user preferences and video ratings.
Figure 6.18: Predicted pairwise relevance scores
Reminder
Since matrix factorization uses user-video interactions only, it is commonly used in collaborative filtering.
Before wrapping up matrix factorization, let’s discuss the pros and cons of this model.

Pros:

Training speed: Matrix factorization is efficient during the training phase. This is because there are only two embedding matrices to learn.
Serving speed: Matrix factorization is fast at serving time. The learned embeddings are static, meaning that once we learn them, we can reuse them without having to transform the input at query time.
Cons:

Matrix factorization only relies on user-video interactions. It does not use other features, such as the user's age or language. This limits the predictive capability of the model because features like language are useful to improve the quality of recommendations.
Handling new users is difficult. For new users, there are not enough interactions for the model to produce meaningful embeddings. Therefore, matrix factorization cannot determine whether a video is relevant to a user by computing the dot product between their embeddings.
Let's see how two-tower neural networks address the shortcomings of matrix factorization.

Two-tower neural network
A two-tower neural network comprises two encoder towers: the user tower and the video tower. The user encoder takes user features as input and maps them to an embedding vector (user embedding). The video encoder takes video features as input and maps them into an embedding vector (video embedding). The distance between their embeddings in the shared embedding space represents their relevance.

Figure 6.19 shows the two-tower architecture. In contrast to matrix factorization, twotower architectures are flexible enough to incorporate all kinds of features to better capture the user's specific interests.

Image represents a system for calculating the similarity between users and videos using embeddings.  The system begins with 'User features' and 'Video features,' which are input into separate 'User encoder (DNN)' and 'Video encoder (DNN)' respectively.  These encoders, both described as Deep Neural Networks (DNNs), process the input features and generate 'User embedding (E<sub>u</sub>)' and 'Video embedding (E<sub>v</sub>)' respectively.  These embeddings are vector representations of the users and videos.  A 'Similarity (E<sub>u</sub>, E<sub>v</sub>)' function then compares the user and video embeddings, calculating a similarity score between them.  The arrows indicate the flow of data: from features to encoders, from encoders to embeddings, and finally, the embeddings are compared to produce a similarity score.  The embeddings are depicted as vertical arrays of cells, suggesting a multi-dimensional vector representation.
Figure 6.19: Two-tower neural network
Constructing the dataset
We construct the dataset by extracting features from different 
⟨
⟨ user, video 
⟩
⟩ pairs and labeling them as positive or negative based on the user's feedback. For example, we label a pair as "positive" if the user explicitly liked the video, or watched at least half of it.

To construct negative data points, we can either choose random videos which are not relevant or choose those the user explicitly disliked by pressing the dislike button. Figure 6.20 shows an example of the constructed data points.

Image represents a tabular dataset used for training a machine learning model.  The table is divided into four columns: a serial number column '#' identifying each data instance; a column labeled 'User-related features' containing a vector of seven numerical features for each user; a column labeled 'Video-related features' containing another vector of seven numerical features for each video; and a final column labeled 'Label' indicating the class of each data instance (1 for positive, 0 for negative). Each row represents a single data point, showing the user features, video features, and the corresponding label. For instance, row 1 shows user features [0, 0, 1, 0.7, -0.6, 0, 0], video features [0, 1, 0, 0.9, 0.9, 1], and a positive label (1). Row 2 similarly presents another data point with different feature values and a negative label (0).  The features are likely used as input to a machine learning model to predict the label (positive or negative sentiment, for example).
Figure 6.20: Two constructed data points
Note, users usually only find a small fraction of videos relevant. While constructing training data, this leads to an imbalanced dataset where there are many more negative than positive pairs. Training a model on an imbalanced dataset is problematic. We can use the techniques described in Chapter 1 Introduction and Overview, to address the data imbalance issue.

Choosing the loss function
Since the two-tower neural network is trained to predict binary labels, the problem can be categorized as a classification task. We use a typical classification loss function, such as cross-entropy, to optimize the encoders during training. This process is shown in Figure 6.21

Image represents a system for predicting user-video interaction, likely a recommendation system.  At the bottom, 'User features' and 'Video features' are fed into separate 'User encoder (DNN)' and 'Video encoder (DNN)' respectively, which are deep neural networks that process these features to generate 'User embedding (E<sub>u</sub>)' and 'Video embedding (E<sub>v</sub>)'. These embeddings are then fed into a 'Dot product' calculation, resulting in a numerical score (0.7 in the example). This score represents the similarity between the user and video embeddings.  Finally, this dot product is compared to a 'Label' (1 in the example, likely indicating a positive interaction), and the difference is calculated using 'cross-entropy loss,' a common loss function used to train such systems. The entire system is designed to learn the relationship between user and video features, predicting the likelihood of interaction based on their embeddings and minimizing the cross-entropy loss to improve prediction accuracy.
Figure 6.21: Two-tower neural network training workflow
Two-tower neural network inference
At inference time, the system uses the embeddings to find the most relevant videos for a given user. This is a classic "nearest neighbor" problem. We use approximate nearest neighbor methods to find the top 
k
k most similar video embeddings efficiently.

Two-tower neural networks are used for both content-based filtering and collaborative filtering. When a two-tower architecture is used for collaborative filtering, as shown in Figure 
6.22
6.22, the video encoder is nothing but an embedding layer that converts the video ID into an embedding vector. This way, the model doesn't rely on other video features.

Image represents a system for recommending videos to users based on their features and video embeddings.  The system begins with 'User features', a horizontal array representing user data, which is fed into a 'User encoder'. This encoder processes the user features and generates a 'User embedding' (Eu), a vertical array representing a compressed, vectorized representation of the user.  Separately, a 'Video ID' is input into an 'Embedding layer', which generates a 'Video embedding' (Ev), another vertical array representing the video's features.  The 'User embedding' (Eu) and 'Video embedding' (Ev) are then compared using a 'Similarity (Eu, Ev)' function, which calculates a similarity score between the user and video representations.  The arrows indicate the flow of information, showing how the user and video features are processed to generate embeddings, which are then compared to determine video recommendations.
Figure 6.22: Two-tower neural network used for collaborative filtering
Let’s see the pros and cons of a two-tower neural network model.

Pros:

Utilizes user features. The model accepts user features, such as age and gender, as input. These predictive features help the model make better recommendations.
Handles new users. The model easily handles new users as it relies on user features (e.g., age, gender, etc.).
Cons:

Slower serving. The model needs to compute the user embedding at query time. This makes the model slower to serve requests. In addition, if we use the model for content-based filtering, the model needs to transform video features into video embedding, which increases the inference time.
Training is more expensive. Two-tower neural networks have more learning parameters than matrix factorization. Therefore, the training is more compute-intensive.
Matrix factorization vs. two-tower neural network
Table 6.5 summarizes the differences between matrix factorization and two-tower neural network architecture.

Matrix factorization	Two-tower neural network
Training cost	✓ More efficient to train	✘ More costly to train
Inference speed	✓ Faster as embeddings are static and can be precomputed	✘ User features should be transformed into embeddings at query time
Cold-start problem	✘ Cannot handle new users easily	✓ Handles new users as it relies on user features
Quality of recommendations	✘ Not ideal since the model does not use user/video features	✓ Better recommendations since it relies on more features
Table 6.5: Matrix factorization vs. two-tower neural networks


Evaluation
The system’s performance can be evaluated with offline and online metrics.

Offline metrics
We evaluate the following offline metrics commonly used in recommendation systems.

Precision@k. This metric measures the proportion of relevant videos among the top 
k
k recommended videos. Multiple 
k
k values (e.g., 
1
,
5
,
10
1,5,10 ) can be used.

mAP. This metric measures the ranking quality of recommended videos. It is a good fit because the relevance scores are binary in our system.

Diversity. This metric measures how dissimilar recommended videos are to each other. This metric is important to track, as users are more interested in diversified videos. To measure diversity, we calculate the average pairwise similarity (e.g., cosine similarity or dot product) between videos in the list. A low average pairwise similarity score indicates the list is diverse.

Note that using diversity as the sole measure of quality can result in misleading interpretations. For example, if the recommended videos are diverse but irrelevant to the user, they may not find the recommendations helpful. Therefore, we should use diversity with other offline metrics to ensure both relevance and diversity.

Online metrics
In practice, companies track many metrics during online evaluation. Let's examine some of the most important ones:

Click-through rate (CTR)
The number of completed videos
Total watch time
Explicit user feedback
CTR. The ratio between clicked videos and the total number of recommended videos. The formula is:

C
T
R
=
 number of clicked videos 
 total number of recommended videos 
CTR= 
 total number of recommended videos 
 number of clicked videos 
​
 
CTR is an insightful metric to track user engagement, but the drawback of CTR is that we cannot capture or measure clickbait videos.

The number of completed videos. The total number of recommended videos that users watch until the end. By tracking this metric, we can understand how often the system recommends videos that users watch.

Total watch time. The total time users spent watching the recommended videos. When recommendations interest users, they spend more time watching videos, overall.

Explicit user feedback. The total number of videos that users explicitly liked or disliked. The metric accurately reflects users' opinions of recommended videos.

Serving
At serving time, the system recommends the most relevant videos to a given user by narrowing the selection down from billions of videos. In this section, we will propose a prediction pipeline that's both efficient and accurate at serving requests.

Given we have billions of videos available, the serving speed would be slow if we choose a heavy model which takes lots of features as input. On the other hand, if we choose a lightweight model, it may not produce high-quality recommendations. So, what to do? A natural decision is to use more than one model in a multi-stage design. For example, in a two-stage design, a lightweight model quickly narrows down the videos during the first stage, called candidate generation. The second stage uses a heavier model that accurately scores and ranks the videos, called scoring. Figure 
6.23
6.23 shows how candidate generation and scoring work together to produce relevant videos.

Image represents a video recommendation system architecture.  A 'Query user' initiates the process, leading to 'Feature preparation,' which generates 'User features.' These features are then used to query a 'Video corpus' containing billions of videos.  A 'Candidate generation' stage filters this corpus down to thousands of candidate videos.  These candidates are then scored using a 'Scoring' module, reducing the number to hundreds.  A 'Re-ranking' module further refines the results to dozens of videos. Finally, the system retrieves video features from a 'Video feature store' to present the top *k* videos to the user, visualized as a dashed-line box containing several video icons labeled 'Top k videos.'  The numbers (billions, thousands, hundreds, dozens) indicate the approximate reduction in the number of videos at each stage of the pipeline.  Arrows depict the flow of information between components.
Figure 6.23: Prediction pipeline
Let's take a closer look at the components of the prediction pipeline.

Candidate generation
Scoring
Re-ranking
Candidate generation
The goal of candidate generation is to narrow down the videos from potentially billions, to thousands. We prioritize efficiency over accuracy at this stage and are not concerned about false positives.

To keep candidate generation fast, we choose a model which doesn't rely on video features. In addition, this model should be able to handle new users. A two-tower neural network is a good fit for this stage.

Figure 
6.24
6.24 shows the candidate generation workflow. The candidate generation obtains a user's embedding from the user encoder. Once the computation is complete, it retrieves the most similar videos from the approximate nearest neighbor service. These videos are ranked based on similarity in the embedding space and are returned as the output.

Image represents a system for video recommendation.  A query user initiates the process.  Their query undergoes 'Feature preparation', followed by processing through a 'User encoder'. The output of the user encoder is fed into 'Candidate generation', which receives input from a database of 'Billions of videos'.  The 'Candidate generation' module uses an 'Approximate nearest neighbor service' to search through an 'Indexed video embeddings' database. This service efficiently retrieves a smaller subset of 'Thousands of videos' that are most relevant to the user's query. The entire process is structured as a flow, with data moving sequentially from the user's query through feature preparation, user encoding, candidate generation, the approximate nearest neighbor service, and finally to the output of thousands of recommended videos.  The dashed lines group related components.
Figure 6.24: Candidate generation workflow
In practice, companies may choose to use more than one candidate generation because it could improve the performance of the recommendation. Let's take a look at why.

Users may be interested in videos for many reasons. For example, a user may choose to watch a video because it's popular, trending, or relevant to their location. To include those videos in the recommendations, it is common to use more than one candidate generation, as shown in Figure 6.25.

Image represents a video recommendation system architecture.  A query user initiates the process, their query undergoing 'Feature preparation' before being fed into a 'User encoder'. The encoder's output is then used by multiple 'Candidate generation' modules (1, 2, ..., k), each potentially employing different strategies.  These modules receive input from a massive database of 'Billions of videos'.  Each candidate generation module outputs a set of video recommendations (labeled 'Relevant videos', 'Popular videos', and 'Trending videos').  All candidate video recommendations are then processed by an 'Approximate nearest neighbor service', which uses an 'Indexed video embeddings' database to refine the recommendations based on similarity to the user's encoded features.  The final output is a set of recommended videos presented to the user.  The system uses a pipeline architecture, with data flowing sequentially from the user query through feature preparation, encoding, candidate generation, nearest neighbor search, and finally to the recommended videos.
Figure 6.25: Use k candidate generations to diversify recommended videos
As soon as we have narrowed down potential videos from billions to thousands, we can use a scoring component to rank these videos before they are displayed.

Scoring
Also known as ranking, scoring takes the user and candidate videos as input, scores each video, and outputs a ranked list of videos.

At this stage, we prioritize accuracy over efficiency. To do so, we choose content-based filtering filtering and pick a model which relies on video features. A two-tower neural network is a common choice for this stage. Since there are only a handful of videos to rank in the scoring stage, we can employ a heavier model with more parameters. Figure 6.26 shows an overview of the scoring component.

Image represents a video recommendation system architecture.  A query user initiates the process.  Their query is fed into a 'Scoring' module, which receives input from two sources:  thousands of candidate videos (represented by multiple video icons within a dashed box) and a 'Feature preparation' module. The 'Feature preparation' module processes data from a 'Video feature store' (a database icon), preparing video features for the scoring process. The 'Scoring' module utilizes a 'Two-tower neural network model' (cloud shape) to compute a relevance score between the user query and each candidate video.  The highest-scoring videos (dozens, represented by multiple video icons within a dashed box) are then outputted as recommendations to the user.  Arrows indicate the flow of data between components.
Figure 6.26: Overview of the scoring component
Re-ranking
This component re-ranks the videos by adding additional criteria or constraints. For example, we may use standalone ML models to determine if a video is clickbait. Here are a few important things to consider when building the re-ranking component:

Region-restricted videos
Video freshness
Videos spreading misinformation
Duplicate or near-duplicate videos
Fairness and bias
Challenges of video recommendation systems
Before wrapping up this chapter, let’s see how our design addresses typical challenges in video recommendation systems.

Serving speed
It is vital to recommend videos fast. However, as we have billions of videos in this system, recommending them efficiently and accurately is challenging. To address this issue, we used a two-stage design.

Specifically, we use a lightweight model in the first stage to quickly narrow down candidate videos from billions to thousands. YouTube uses a similar approach [2] , and Instagram adopts a multi-stage design [8].

Precision
To ensure precision, we employ a scoring component that ranks videos using a powerful model, which relies on more features, including video features. Using a more powerful model doesn't affect serving speed because only a small subset of videos is selected after the candidate generation phase.

Diversity
Most users prefer to see a diverse selection of videos in their recommendations. To ensure our system produces a diverse set of videos, we adopt multiple candidate generators, as explained in the candidate generation section.

Cold-start problem
How does our system handle the cold-start problem?

For new users: We don't have any interaction data about new users when they begin using our platform.

In this case, predictions are made using two-tower neural networks based on features such as age, gender, language, location, etc. The recommended videos are personalized to some extent, even for new users. As the user interacts with more videos, we are able to make better predictions based on new interactions.

For new videos: When a new video is added to the system, the video metadata and content are available, but no interactions are present. One way to handle this is to use heuristics. We can display videos to random users and collect interaction data. Once we gather enough interactions, we fine-tune the two-tower neural network using the new interactions.

Training scalability
It's challenging to train models on large datasets in a cost-effective manner. In recommendation systems, new interactions are continuously added, and the models need to quickly adapt to make accurate recommendations. To quickly adapt to new data, the models should be able to be fine-tuned.

In our case, the models are based on neural networks and designed to be easily fine-tuned.

Other Talking Points
If there is time left at the end of the interview, here are some additional talking points:

The exploration-exploitation trade-off in recommendation systems [9].
Different types of biases may be present in recommendation systems [10].
Important considerations related to ethics when building recommendation systems [11].
Consider the effect of seasonality - changes in users' behaviors during different seasons - in a recommendation system [12].
Optimize the system for multiple objectives, instead of a single objective [13].
How to benefit from negative feedback such as dislikes [14].
Leverage the sequence of videos in a user's search history or watch history [2].
References
YouTube recommendation system. https://blog.youtube/inside-youtube/on-youtubes-recommendation-system.
DNN for YouTube recommendation. https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/45530.pdf.
CBOW paper. https://arxiv.org/pdf/1301.3781.pdf.
BERT paper. https://arxiv.org/pdf/1810.04805.pdf.
Matrix factorization. https://developers.google.com/machine-learning/recommendation/collaborative/matrix.
Stochastic gradient descent. https://en.wikipedia.org/wiki/Stochastic_gradient_descent.
WALS optimization. https://fairyonice.github.io/Learn-about-collaborative-filtering-and-weighted-alternating-least-square-with-tensorflow.html.
Instagram multi-stage recommendation system. https://ai.facebook.com/blog/powered-by-ai-instagrams-explore-recommender-system/.
Exploration and exploitation trade-offs. https://en.wikipedia.org/wiki/Multi-armed_bandit.
Bias in AI and recommendation systems. https://www.searchenginejournal.com/biases-search-recommender-systems/339319/#close.
Ethical concerns in recommendation systems. https://link.springer.com/article/10.1007/s00146-020-00950-y.
Seasonality in recommendation systems. https://www.computer.org/csdl/proceedings-article/big-data/2019/09005954/1hJsfgT0qL6.
A multitask ranking system. https://daiwk.github.io/assets/youtube-multitask.pdf.
Benefit from a negative feedback. https://arxiv.org/abs/1607.04228?context=cs.