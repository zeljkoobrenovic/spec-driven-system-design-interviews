YouTube Video Search
On video-sharing platforms such as YouTube, the number of videos can quickly grow into the billions. In this chapter, we design a video search system that can efficiently handle this volume of content. As shown in Figure 4.1, the user enters text into the search box, and the system displays the most relevant videos for the given text.

Image represents a simplified web browser window simulating a video search.  The top of the window displays three colored circular icons (red, pink, blue) likely representing user accounts or settings, followed by a search bar containing the search query 'Playing guitar at night' and a magnifying glass icon indicating a search action. Below the search bar, the text 'Your search results:' precedes three square boxes arranged horizontally. Each box is a different pastel color (light pink, light green, light red) and contains a black camcorder icon, representing video search results.  There are no explicit URLs or parameters visible; the diagram focuses on the user input and the visual representation of the search output, suggesting a simplified model of a video search engine's user interface.
Figure 4.1: Searching videos with a text query
Clarifying Requirements
Here is a typical interaction between a candidate and an interviewer.

Candidate: Is the input query text-only, or can users search with an image or video?
Interviewer: Text queries only.

Candidate: Is the content on the platform only in video form? How about images or audio files?
Interviewer: The platform only serves videos.

Candidate: The YouTube search system is very complex. Can I assume the relevancy of a video is determined solely by its visual content and the textual data associated with the video, such as the title and description?
Interviewer: Yes, that's a fair assumption.

Candidate: Is there any training data available?
Interviewer: Yes, let's assume we have ten million pairs of 
⟨
⟨ video, text query 
⟩
⟩.

Candidate: Do we need to support other languages in the search system?
Interviewer: For simplicity, let's assume only English is supported.

Candidate: How many videos are available on the platform?
Interviewer: One billion videos.

Candidate: Do we need to personalize the results? Should we rank the results differently for different users, based on their past interactions?
Interviewer: As opposed to recommendation systems where personalization is essential, we do not necessarily have to personalize results in search systems. To simplify the problem, let's assume no personalization is required.

Let's summarize the problem statement. We are asked to design a search system for videos. The input is a text query, and the output is a list of videos that are relevant to the text query. To search for relevant videos, we leverage both the videos' visual content and textual data. We are given a dataset of ten million 
⟨
⟨ video, text query 
⟩
⟩ pairs for model training.

Frame the Problem as an ML Task
Defining the ML objective
Users expect search systems to provide relevant and useful results. One way to translate this into an ML objective is to rank videos based on their relevance to the text query.

Specifying the system's input and output
As shown in Figure 4.2, the search system takes a text query as input and outputs a ranked list of videos sorted by their relevance to the text query.

Image represents a simplified video search system architecture.  The system begins with a text query, 'Dogs playing indoor,' which is input into a 'Video search system' component. This system processes the query and retrieves relevant video results. The output is displayed as a list of video thumbnails, represented by three color-coded rectangles (light peach, light purple, and light green) each containing a black camera icon symbolizing a video clip.  The ellipsis (...) between the middle and bottom rectangles indicates that there may be more results than are shown. The entire output is labeled 'Results,' indicating the final set of videos returned by the system in response to the initial text query.  The arrows show the unidirectional flow of information from the text query to the video search system and then to the displayed results.
Figure 4.2: Video search system’s input-output
Choosing the right ML category
In order to determine the relevance between a video and a text query, we utilize both visual content and the video’s textual data. An overview of the design can be seen in Figure 4.3.

Image represents a video search system architecture.  The system begins with a text query, 'Dogs playing indoor,' which is fed into two parallel processing paths: a 'Text search' and a 'Visual search.'  Each path processes the query independently. The 'Text search' path outputs a set of video results represented by pink rectangles, each containing a camera icon, indicating videos identified based on textual analysis. Similarly, the 'Visual search' path outputs another set of video results, represented by pale yellow rectangles with camera icons, signifying videos identified based on visual content analysis.  Both sets of results are then fed into a 'Fusing' module, which combines the results from the text and visual searches. The fused results, a combined set of videos from both paths, are then output as the final 'Results,' shown as a mix of pink and yellow rectangles with camera icons, suggesting a ranked list of videos based on the combined scores from both search methods. The entire video search system is enclosed within a dashed-line box.
Figure 4.3: High-level overview of the search system
Let's briefly discuss each component.

Visual search
This component takes a text query as input and outputs a list of videos. The videos are ranked based on the similarity between the text query and the videos' visual content.

Representation learning is a commonly used approach to search for videos by processing their visual content. In this approach, text query and video are encoded separately using two encoders. As shown in Figure 4.4, the ML model contains a video encoder that generates an embedding vector from the video, and a text encoder that generates an embedding vector from the text. The similarity score between the video and the text is calculated using the dot product of their representations.

Image represents a machine learning model for video retrieval based on text queries.  The system consists of two main input branches: a video branch and a text branch. The video branch takes a video as input (represented by a video camera icon), which is processed by a 'Video encoder' to generate a 'Video embedding' – a numerical vector represented by a column of four values (0.1, 0.8, -1, -0.7).  Similarly, the text branch takes a text query ('Dogs playing indoor') as input, which is processed by a 'Text encoder' to generate a 'Text embedding' – another numerical vector with four values (0.2, 0.6, -0.9, -0.4). Both video and text embeddings are fed into an 'ML model' (enclosed by a dashed line), which presumably compares these embeddings to determine the relevance of the video to the text query.  Arrows indicate the flow of data from input to processing units and finally to the embeddings.
Figure 4.4: ML model’s input-output
In order to rank videos that are visually and semantically similar to the text query, we compute the dot product between the text and each video in the embedding space, then rank the videos based on their similarity scores.

Text search
Figure 4.5 shows how text search works when a user types in a text query: "dogs playing indoor". Videos with the most similar titles, descriptions, or tags to the text query are shown as the output.

Image represents a simplified video search system.  The process begins with a text query, 'Dogs playing indoor,' which is input into a 'Text search' component. This component accesses a database represented as a cylinder labeled 'Video's textual data,' containing textual information about videos.  The search uses this data to identify relevant videos.  The results are displayed as a table with three columns: 'Video ID,' 'Title,' and 'Tags.'  The 'Video ID' column lists the IDs of the matched videos (1 and 6 in this example).  The 'Title' column provides the video titles, and the 'Tags' column lists keywords associated with each video.  The dashed line indicates a connection between the textual data and the table, suggesting that the search results are derived from the database.  The entire system demonstrates a text-based video search functionality, retrieving videos based on keyword matching in their titles and associated tags.
Figure 4.5: Text search
The inverted index is a common technique for creating the text-based search component, allowing efficient full-text search in databases. Since inverted indexes aren't based on machine learning, there is no training cost. A popular search engine companies often use is Elasticsearch, which is a scalable search engine and document store. For more details and a deeper understanding of Elasticsearch, refer to [1].

Data Preparation
Data engineering
Since we are given an annotated dataset to train and evaluate the model, it's not necessary to perform any data engineering. Table 4.1 shows what the annotated dataset might look like.

Video name	Query	Split type
76134.mp4	Kids swimming in a pool!	Training
92167.mp4	Celebrating graduation	Training
2867.mp4	A group of teenagers playing soccer	Validation
28543.mp4	How Tensorboard works	Validation
70310.mp4	Road trip in winter	Test
Table 4.1: Annotated dataset

Feature engineering
Almost all ML algorithms accept only numeric input values. Unstructured data such as texts and videos need to be converted into a numerical representation during this step. Let's take a look at how to prepare the text and video data for the model.

Preparing text data
As shown in Figure 
4.6
4.6, text is typically represented as a numerical vector using three steps: text normalization, tokenization, and tokens to IDs [2].

Image represents a flowchart illustrating the text preprocessing steps involved in converting a natural language sentence into numerical representations suitable for machine learning models.  The process begins with the input sentence, “A person is walking in Montréal !”. This sentence is then fed into a 'Text normalization' block, which outputs a normalized version: 'a person walk in montreal”.  This normalized text is subsequently passed to a 'Tokenization' block, which splits the sentence into individual tokens: [“a”, “person”, “walk”, “in”, “montreal”]. Finally, these tokens are processed by a 'Tokens to IDs' block, which converts each token into a unique numerical ID, resulting in the output: [33,28,4,16,99].  The entire process is depicted as a sequential flow, with arrows indicating the direction of data movement between each processing stage.
Figure 4.6: Represent a text with a numerical vector
Let's take a look at each step in more detail.

Text normalization
Text normalization - also known as text cleanup - ensures words and sentences are consistent. For example, the same word may be spelled slightly differently; as in "dog", "dogs", and "DOG!" all refer to the same thing but are spelled in different ways. The same is true for sentences. Take these two sentences, for example:

"A person walking with his dog in Montréal !"
"a person walks with his dog, in Montreal."
Both sentences mean the same, but have differing punctuation and verb forms. Here are some typical methods for text normalization:

Lowercasing: make all letters lowercase, as this does not change the meaning of words or sentences
Punctuation removal: remove punctuation from the text. Common punctuation marks are the period, comma, question mark, exclamation point, etc.
Trim whitespaces: trim leading, trailing, and multiple whitespaces
Normalization Form KD (NFKD) [3]: decompose combined graphemes into a combination of simple ones
Strip accents: remove accent marks from words. For example: Màlaga 
→
→ Malaga, Noël 
→
→ Noel
Lemmatization and stemming: identify a canonical representative for a set of related word forms. For example: walking, walks, walked 
→
→ walk
Tokenization
Tokenization is the process of breaking down a piece of text into smaller units called tokens. Generally, there are three types of tokenization:

Word tokenization: split the text into individual words based on specific delimiters. For example, a phrase like "I have an interview tomorrow" becomes [ "I", "have", "an", "interview", "tomorrow"]
Subword tokenization: split text into subwords (or n-gram characters)
Character tokenization: split text into a set of characters The details of different tokenization algorithms are not usually a strong focus in ML system design interviews. If you are interested to learn more, refer to [4].
Tokens to IDs
Once we have the tokens, we need to convert them to numerical values (IDs). The representation of tokens with numerical values can be done in two ways:

Lookup table
Hashing
Lookup table. In this method, each unique token is mapped to an ID. Next, a lookup table is created to store these 
1
:
1
1:1 mappings. Figure 
4.7
4.7 shows what the mapping table might look like.

Image represents a simple table with two columns: 'Word' and 'ID'.  The 'Word' column lists a sample of words (animals, art, car, insurance, travel), with ellipses (...) indicating that this is a partial list of many more words.  The 'ID' column provides a unique numerical identifier corresponding to each word in the 'Word' column.  The table structure implies a one-to-one mapping between each word and its assigned ID, suggesting a vocabulary or lookup table where words are represented by their respective numerical IDs.  No information flows between the columns; the table simply presents a static mapping of words to IDs.
Figure 4.7: A lookup table
Hashing. Hashing, also called "feature hashing" or "hashing trick," is a memory-efficient method that uses a hash function to obtain IDs, without keeping a lookup table. Figure 
4.8
4.8 shows how a hash function is used to convert words to IDs.

Image represents a simplified illustration of a hashing function used for data mapping.  On the left, a table labeled 'Word' contains a list of words ('animals,' 'art,' 'car,' 'insurance,' 'travel'), each representing a data element.  Ellipses (...) indicate additional words not explicitly shown.  A light-green rectangle in the center is labeled 'Hash function,' signifying a process that transforms input data.  Lines connect each word from the 'Word' table to the 'Hash function' rectangle, indicating that each word is fed as input to the function.  On the right, a table labeled 'ID' shows a sequence of numerical IDs (1, 2, 3, 4, ..., 35000), representing the output space of the hash function.  Lines connect the output of the 'Hash function' to specific IDs in the 'ID' table, demonstrating that the hash function maps each input word to a unique (or potentially colliding) numerical ID.  The ellipses in the 'ID' table suggest a large number of possible output IDs.  The diagram visually depicts how a hash function transforms textual data into numerical identifiers, a common technique in data structures and machine learning for efficient data indexing and retrieval.
Figure 4.8: Use hashing to obtain word IDs
Let's compare the lookup table with the hashing method.

Lookup table	Hashing
Speed	✓ Quick to convert tokens to IDs	✘ Need to compute hash function to convert tokens to IDs
ID to token	✓ Easy to convert IDs to tokens using a reverse index table	✘ Not possible to convert IDs to tokens
Memory	
✘ The table is stored in memory. A large number of tokens will result in an increase in memory required

✓ The hash function is sufficient to convert any token to its ID

Unseen tokens	✘ New or unseen words cannot be properly handled	
✓ Easily handles new or unseen words by applying the hash function to any word

Collisions [5]	✓ No collision issue	✘ Collisions are a potential problem
Table 4.2: Lookup table vs. feature hashing

Preparing video data
Figure 4.9 shows a typical workflow for preprocessing a raw video.

Image represents a data preprocessing pipeline for a video of a corgi running.  The process begins with a video file (represented by a YouTube play button overlayed on a video still), which is fed into a 'Decode frames' block. This block outputs a sequence of individual frames from the video.  These frames then follow two parallel paths.  The upper path involves directly 'Sampling frames' from the decoded sequence, resulting in a subset of frames. The lower path first involves 'Resizing' the frames to a smaller size.  These resized frames are then processed by a 'Scaling, normalizing, and correcting color mode' block, which performs image enhancement and standardization.  Finally, the output from both paths is combined and saved as a NumPy array file named 'frames.npy'.  Arrows indicate the flow of data between each processing step.
Figure 4.9: Video preprocessing workflow
Model Development
Model selection
As discussed in the "Framing the problem as an ML task" section, text queries are converted into embeddings by a text encoder, and videos are converted into embeddings by a video encoder. In this section, we examine possible model architectures for each encoder.

A typical text encoder’s input and output are shown in Figure 4.10.

Image represents a simple text encoding process.  The diagram shows a rectangular box labeled 'Dogs playing indoor' which acts as the input, identified below as 'Text query'.  A directed arrow connects this box to another rectangular box labeled 'Text encoder,' indicating that the text query is fed into the text encoder.  The text encoder processes the input text.  A second directed arrow then connects the 'Text encoder' box to a vertical array of five rectangular boxes, each containing a single floating-point number: 0.2, 0.6, -0.9, -0.4, and 0.1. This array represents the output of the text encoder – a numerical vector encoding the input text 'Dogs playing indoor'.  The arrows indicate the unidirectional flow of information from the text query through the encoder to the final numerical vector representation.
Figure 4.10: Text encoder’s input-output
The text encoder converts text into a vector representation [6]. For example, if two sentences have similar meanings, their embeddings are more similar. To build the text encoder, two broad categories are available: statistical methods and ML-based methods. Let's examine each.

Statistical methods
Those methods rely on statistics to convert a sentence into a feature vector. Two popular statistical methods are:

Bag of Words (BoW)
Term Frequency Inverse Document Frequency (TF-IDF)
BoW. This method converts a sentence into a fixed-length vector. It models sentenceword occurrences by creating a matrix with rows representing sentences, and columns representing word indices. An example of BoW is shown in Figure 4.11.

best	holiday	is	nice	person	this	today	trip	very	with
this person is nice very nice	0	0	1	2	1	1	0	0	1	0
today is holiday	0	1	1	0	0	0	1	0	0	0
this trip with best person is best	2	0	1	0	1	1	0	1	0	1
Figure 4.11: BoW representations of different sentences


BoW is a simple method that computes sentence representations fast, but has the following limitations:

It does not consider the order of words in a sentence. For example, "let's watch TV after work" and "let's work after watch TV" would have the same BoW representation.
The obtained representation does not capture the semantic and contextual meaning of the sentence. For example, two sentences with the same meaning but different words have a totally different representation.
The representation vector is sparse. The size of the representation vector is equal to the total number of unique tokens we have. This number is usually very large, so each sentence representation is mostly filled with zeros.
TF-IDF. This is a numerical statistic intended to reflect how important a word is to a document in a collection or corpus. TF-IDF creates the same sentence-word matrix as in BoW, but it normalizes the matrix based on the frequency of words. To learn more about the mathematics behind this, refer to [7].

Since TF-IDF gives less weight to frequent words, its representations are usually better than BoW. However, it has the following limitations:

A normalization step is needed to recompute term frequencies when a new sentence is added.
It does not consider the order of words in a sentence.
The obtained representation does not capture the semantic meaning of the sentence.
The representations are sparse.
In summary, statistical methods are usually fast. However, they do not capture the contextual meaning of sentences, and the representations are sparse. ML-based methods address those issues.

ML-based methods
In these methods, an ML model converts sentences into meaningful word embeddings so that the distance between two embeddings reflects the semantic similarity of the corresponding words. For example, if two words, such as "rich" and "wealth" are semantically similar, their embeddings are close in the embedding space. Figure 
4.12
4.12 shows a simple visualization of word embeddings in the 
2
D
2D embedding space. As you can see, similar words are grouped together.

Image represents a two-dimensional scatter plot visualizing the semantic relationships between different words.  The plot uses color-coded circles to represent word clusters, with each circle labeled with the corresponding word.  The x and y axes are not explicitly labeled but implicitly represent semantic dimensions.  Three distinct color groups are visible: light purple circles represent food items (pizza, sandwich, pepperoni); light pink circles represent bathroom and kitchen items (sink, bathroom, bathtub, toilet, faucet, kitchen); and light green circles represent social media platforms (facebook, instagram, twitter, twitt).  A separate cluster of light red circles represents types of vehicles (vehicle, car, suv, truck). Finally, a cluster of light cyan circles represents actions (walk, jump, run). The spatial arrangement of the circles suggests that semantically similar words are clustered closer together, while dissimilar words are further apart.  No specific numerical values or URLs are present; the visualization focuses solely on the relative proximity of words based on their implied semantic similarity.
Figure 4.12: Words in the 2D embedding space
There are three common ML-based approaches for transforming texts into embeddings:

Embedding (lookup) layer
Word2vec
Transformer-based architectures
Embedding (lookup) layer In this approach, an embedding layer is employed to map each ID to an embedding vector. Figure 4.13 shows an example.

Image represents a schematic of an embedding layer in a machine learning model.  A column vector of input IDs, represented as `[[2],[1],[3],[1]]`, feeds into an 'Embedding layer' box. This layer acts as an interface to a 'Lookup table'. The lookup table is depicted as a database with two columns: 'ID' and 'Embeddings'. Each row in the table corresponds to a unique ID (1 to N) and its associated embedding vector, which is a list of floating-point numbers (e.g., `[0.5, 0.3, ..., -0.5]`). The embedding layer uses the input IDs to look up the corresponding embedding vectors from the table.  A dashed line connects the embedding layer to the lookup table, indicating the data flow for the lookup operation. The output of the embedding layer is a matrix of embedding vectors, shown as `[[0.6, -0.9,... ,0.1], [0.5, 0.3, ..., -0.5], [-0.1, -0.5, ..., 0.6], ... ,[0.5, 0.3, ..., -0.5]]`, where each row corresponds to the embedding of an input ID.  The entire process transforms integer input IDs into their corresponding dense vector representations (embeddings).
Figure 4.13: Embedding lookup method
Employing an embedding layer is a simple and effective solution to convert sparse features, such as IDs, into a fixed-size embedding. We will see more examples of its usage in later chapters.

Word2vec Word2vec [8] is a family of related models used to produce word embeddings. These models use a shallow neural network architecture and utilize the co-occurrences of words in a local context to learn word embeddings. In particular, the model learns to predict a center word from its surrounding words during the training phase. After the training phase, the model is capable of converting words into meaningful embeddings.

There are two main models based on word2vec: Continuous Bag of Words (CBOW) [9] and Skip-gram [10]. Figure 
4.14
4.14 shows how CBOW works at a high level. If you are interested to learn about these models, refer to [8].

Image represents a simplified diagram of a shallow neural network processing a sequence of words.  Four input boxes, labeled 'How' (ω<sub>t-2</sub>), 'to' (ω<sub>t-1</sub>), 'pizza' (ω<sub>t+1</sub>), and 'at' (ω<sub>t+2</sub>), represent individual words in a sequence, with the subscript indicating their position relative to a central word (not explicitly shown but implied).  Arrows point from these input boxes to a larger, light-green box labeled 'Shallow neural network,' indicating that these words are fed as input to the network.  The network processes this input and produces an output, represented by an arrow pointing upwards to a box labeled 'make' (ω<sub>t</sub>). This suggests the network is predicting the word 'make' based on the context provided by the surrounding words 'How,' 'to,' 'pizza,' and 'at.'  The ω<sub>t</sub>, ω<sub>t-1</sub>, ω<sub>t-2</sub>, ω<sub>t+1</sub>, and ω<sub>t+2</sub> labels likely represent the word embeddings or contextual representations of the words at different time steps (t) in the sequence.
Figure 4.14: CBOW approach
Even though word2vec and embedding layers are simple and effective, recent architectures based upon Transformers have shown promising results.

Transformer-based models
These models consider the context of the words in a sentence when converting them into embeddings. As opposed to word2vec models, they produce different embeddings for the same word depending on the context.

Figure 4.15 shows a Transformer-based model which takes a sentence - a set of words as input, and produces an embedding for each word.

Image represents a diagram illustrating the input and output of a transformer-based model.  Six rectangular blocks, each labeled with 'H' followed by a word ('how,' 'to,' 'make,' 'pizza,' 'at,' 'home'), represent the input embeddings. Each block is vertically divided into several smaller, equal-sized rectangles, suggesting a multi-dimensional embedding for each word.  Arrows point from each of these six input blocks towards a central, light-green rectangular block labeled 'Transformer-based model,' indicating that these word embeddings are fed as input to the model.  From this central model block, arrows point to six smaller rectangular output blocks, each containing a single word ('How,' 'to,' 'make,' 'pizza,' 'at,' 'home'), mirroring the input words but potentially in a different order or with altered representation, suggesting the model processes and outputs the words.  The overall structure depicts a many-to-many mapping, where multiple input word embeddings are processed by the transformer model to generate multiple output word representations.
Figure 4.15: Transformer-based model’s input-output
Transformers are very powerful at understanding the context and producing meaningful embeddings. Several models, such as BERT [11], GPT3 [12], and BLOOM [13], have demonstrated Transformers' potential to perform a wide variety of Natural Language Processing (NLP) tasks. In our case, we choose a Transformer-based architecture such as BERT as our text encoder.

In some interviews, the interviewer may want you to dive deeper into the details of the Transformer-based model. To learn more, refer to [14].

Video encoder
We have two architectural options for encoding videos: We have two architectural options for encoding videos:

Video-level models
Frame-level models
Video-level models process a whole video to create an embedding, as shown in Figure 4.16. The model architecture is usually based on 3D convolutions [15] or Transformers. Since the model processes the whole video, it is computationally expensive.

Image represents a simplified pipeline for video processing and embedding generation.  The pipeline begins with an 'Input Video' block, depicted as a pale yellow rectangle containing a video camera icon.  A directed arrow connects this input to a 'Preprocess' block, a simple white rectangle containing the text 'Preprocess'. This suggests that the input video undergoes some form of preprocessing before further processing.  Another directed arrow connects the 'Preprocess' block to a 'Video model' block, another white rectangle labeled 'Video model'. This block presumably contains a machine learning model that processes the preprocessed video. Finally, a directed arrow connects the 'Video model' block to a rectangular array labeled 'Video embedding'. This array displays a numerical vector: 0.8, 0.6, -0.2, 0, and 0.1, representing the output of the video model – a numerical embedding of the input video. The entire diagram illustrates a sequential flow of data from raw video input through preprocessing and model processing to a final numerical representation (embedding).
Figure 4.16: A video-level model
Frame-level models work differently. It is possible to extract the embedding from a video using a frame-level model by breaking it down into three steps:

Preprocess a video and sample frames.
Run the model on the sampled frames to create frame embeddings.
Aggregate (e.g., average) frame embeddings to generate the video embedding.
Image represents a system for generating a video embedding from an input video.  The process begins with an 'Input Video' (represented by a video camera icon in a yellow box) which is fed into a 'Preprocess' block.  The preprocessed video is then broken down into individual frames, exemplified by 'Frame 1', 'Frame 5', and 'Frame N', indicating a sequence of frames. Each frame is individually processed by an 'Image model', resulting in a frame embedding (e.g., 'Frame 1 embedding' shows a vector of values: 0.8, 0.6, -0.2, 0).  These individual frame embeddings (represented by vectors of numerical values) are then passed to an 'Aggregation' block. The aggregation block combines the embeddings from all frames to produce a single 'Video embedding' (another vector: 0.8, 0.6, -0.2, 0, 0.1).  The ellipses (...) indicate that the process repeats for all frames between Frame 1 and Frame N.  The arrows show the direction of data flow between the blocks.
Figure 4.17: A frame-level model
Since this model works at the frame level, it is often faster and computationally less expensive. However, frame-level models are usually not able to understand the temporal aspects of the video, such as actions and motions. In practice, frame-level models are preferred in many cases where a temporal understanding of the video is not crucial. Here, we employ a frame-level model such as ViT [16] for two reasons:

Improve the training and serving speed
Reduce the number of computations
Model training
To train the text encoder and video encoder, we use a contrastive learning approach. If you are interested in learning more about this, see the "Model training" section in Chapter 2, Visual Search System.

An explanation of how to compute the loss during model training is shown in Figure 4.18.

Image represents a machine learning model for video-text retrieval.  A video input (labeled 'Input V,' depicted as a video camera icon) is fed into a 'Video encoder,' which outputs a video embedding vector, 'E<sub>v</sub>'.  Simultaneously, a set of text queries (T<sub>1</sub>: 'Two dogs sitting indoor,' T<sub>2</sub>: 'Road trip with my family,' ..., T<sub>n</sub>: 'Children swimming') are processed by a 'Text encoder,' generating corresponding text embedding vectors (E<sub>1</sub>, E<sub>2</sub>, ..., E<sub>n</sub>).  The model then computes the similarity between the video embedding and each text embedding (E<sub>v</sub> • E<sub>1</sub>, E<sub>v</sub> • E<sub>2</sub>, ..., E<sub>v</sub> • E<sub>n</sub>). These similarities are passed through a 'Softmax' function, producing a probability distribution ('Predictions') representing the likelihood of each text query matching the video.  Finally, these predictions are compared to the 'Ground truth' (a one-hot vector indicating the correct matching text query, shown as '1' for the positive example and '0' for the negative examples), using cross-entropy loss to measure the model's performance.  The entire system is labeled as an 'ML model,' with the text queries described as '1 positive + (n-1) negative text queries.'
Figure 4.18: Loss computation
Evaluation
Offline metrics
Here are some offline metrics that are typically used in search systems. Let's examine which are the most relevant.

Precision@k and mAP

 precision@k 
=
 number of relevant items among the top 
k
 items in the ranked list 
k
 precision@k = 
k
 number of relevant items among the top k items in the ranked list 
​
 
In the evaluation dataset, a given text query is associated with only one video. That means the numerator of the precision@k formula is at most 1. This leads to low precison@k values. For example, for a given text query, even if we rank its associated video at the top of the list, the precision@10 is only 0.1. Due to this limitation, precision metrics, such as precision@k and mAP, are not very helpful.

Recall@k. This measures the ratio between the number of relevant videos in the search results and the total number of relevant videos.

 recall@k 
=
 Number of relevant videos among the top 
k
 videos 
 Total number of relevant videos 
 recall@k = 
 Total number of relevant videos 
 Number of relevant videos among the top k videos 
​
 
As described earlier, the "total number of relevant videos" is always 1 . With that, we can translate the recall@k formula to the following:

recall@ 
k
=
1
k=1 if the relevant video is among the top 
k
k videos, 0 otherwise

What are the pros and cons of this metric?

Pros

It effectively measures a model's ability to find the associated video for a given text query.
Cons

It depends on 
k
k. Choosing the right 
k
k could be challenging.
When the relevant video is not among the 
k
k videos in the output list, recall@k is always 0. For example, consider the case where model A ranks a relevant video at place 15, and model B ranks the same video at place 50. If we use recall@10 to measure the quality of these two models, both would have recall@10=0, even though model A is better than model B.
Mean Reciprocal Rank (MRR). This metric measures the quality of the model by averaging the rank of the first relevant item in each search result. The formula is:

M
R
R
=
1
m
∑
i
=
1
m
1
rank
⁡
i
MRR= 
m
1
​
  
i=1
∑
m
​
  
rank 
i
​
 
1
​
 
This metric addresses the shortcomings of recall@k and can be used as our offline metric.

Online metrics
As part of online evaluation, companies track a wide variety of metrics. Let's take a look at some of the most important ones:

Click-through rate (CTR)
Video completion rate
Total watch time of search results
CTR. This metric shows how often users click on retrieved videos. The main problem with CTR is that it does not track whether the clicked videos are relevant to the user. In spite of this issue, CTR is still a good metric to track because it shows how many people clicked on search results.

Video completion rate. A metric measuring how many videos appear in search results and are watched by users until the end. The problem with this metric is that a user may watch a video only partially, but still find it relevant. The video completion rate alone cannot reflect the relevance of search results.

Total watch time of search results. This metric tracks the total time users spent watching the videos returned by the search results. Users tend to spend more time watching if the search results are relevant. This metric is a good indication of how relevant the search results are.

Serving
At serving time, the system displays a ranked list of videos relevant to a given text query. Figure 
4.19
4.19 shows a simplified ML system design.

Image represents a system architecture diagram for a video search engine.  The diagram is divided into three main pipelines: a video indexing pipeline, a text indexing pipeline, and a prediction pipeline. The video indexing pipeline processes new videos ('New videos' box with a camera icon) through preprocessing and video encoding steps, ultimately storing the indexed information in a 'Video index table' database.  The text indexing pipeline processes new videos by extracting 'Manual tags' and 'Auto-generated tags' from videos using an 'Auto-tagger,' along with extracting 'Titles,' and stores this textual information in a separate 'Video index table.'  The core of the system is the 'Visual search' component, which takes an input text query ('Dogs playing indoor' box), preprocesses and encodes it, computes its embedding, and uses a 'Nearest neighbor service' to retrieve hundreds of videos from the 'Video index table.'  Simultaneously, the text query is also processed by 'Elasticsearch' to retrieve hundreds of videos based on textual information.  Both sets of videos are then fed into a 'Fusing layer,' which combines the results.  Finally, a 'Re-ranking service' refines the combined results, producing the final 'Search results' (box with multiple camera icons).  The entire process is depicted as a flow of information between different components, with data flowing from one stage to the next.
Figure 4.19: ML system design
Let's discuss each pipeline in more detail.

Prediction pipeline
This pipeline consists of:

Visual search
Text search
Fusing layer
Re-ranking service
Visual search. This component encodes the text query and uses the nearest neighbor service to find the most similar video embeddings to the text embedding. To accelerate the NN search, we use approximate nearest neighbor (ANN) algorithms, as described in Chapter 2, Visual Search System.

Image represents a system for retrieving similar videos based on a text query.  A rectangular box labeled 'Dogs playing indoor' and subtitled 'Query text' represents the user's input.  A dashed line connects this box to a scatter plot labeled 'Embedding space' with axes x1 and x2.  Multiple 'x' markers represent video embeddings in this space. A red 'x' marks the embedding generated from the query text. A blue dashed ellipse encircles the red 'x' and several nearby 'x' markers, visually representing videos semantically close to the query. A dashed arrow points from the ellipse to a rectangular box labeled 'Similar videos,' containing three video representations (rectangles with camera icons). One video representation is highlighted in pale yellow, suggesting it's the most similar video to the query, while the other two are in light pink, indicating lesser similarity. The overall diagram illustrates a process where a text query is converted into an embedding, compared to video embeddings in a shared space, and the closest videos are retrieved.
Figure 4.20: Retrieving the top 3 results for a given text query
Text search. Using Elasticsearch, this component finds videos with titles and tags that overlap the text query.

Fusing layer. This component takes two different lists of relevant videos from the previous step, and combines them into a new list of videos.

The fusing layer can be implemented in two ways, the easiest of which is to re-rank videos based on the weighted sum of their predicted relevance scores. A more complex approach is to adopt an additional model to re-rank the videos, which is more expensive because it requires model training. Additionally, it's slower at serving. As a result, we use the former approach.

Re-ranking service. This service modifies the ranked list of videos by incorporating business-level logic and policies.

Video indexing pipeline
A trained video encoder is used to compute video embeddings, which are then indexed. These indexed video embeddings are used by the nearest neighbor service.

Text indexing pipeline
This uses Elasticsearch for indexing titles, manual tags, and auto-generated tags.

Usually, when a user uploads a video, they provide tags to help better identify the video. But what if they do not manually enter tags? One option is to use a standalone model to generate tags. We name this component the auto-tagger and it is especially valuable in cases where a video has no manual tags. These tags may be noisier than manual tags, but they are still valuable.

Other Talking Points
Before concluding this chapter, it's important to note we have simplified the system design of the video search system. In practice, it is much more complex. Some improvements may include:

Use a multi-stage design (candidate generation + ranking).
Use more video features such as video length, video popularity, etc.
Instead of relying on annotated data, use interactions (e.g., clicks, likes, etc.) to construct and label data. This allows us to continuously train the model.
Use an ML model to find titles and tags which are semantically similar to the text query. This model can be combined with Elasticsearch to improve search quality.
If there's time left at the end of the interview, here are some additional talking points:

An important topic in search systems is query understanding, such as spelling correction, query category identification, and entity recognition. How to build a queryunderstanding component? [17].
How to build a multi-modal system that processes speech and audio to improve search results [18].
How to extend this work to support other languages [19].
Near-duplicate videos in the final output may negatively impact user experience. How to detect near-duplicate videos so we can remove them before displaying the results 
[
20
]
[20] ?
Text queries can be divided into head, torso, and tail queries. What are the different approaches commonly used in each case [21]?
How to consider popularity and freshness when producing the output list [22]?
How real-world search systems work [23][24][25].
References
Elasticsearch. https://www.tutorialspoint.com/elasticsearch/elasticsearch_query_dsl.htm.
Preprocessing text data. https://huggingface.co/docs/transformers/v4.42.0/preprocessing.
NFKD normalization. https://unicode.org/reports/tr15/.
What is Tokenization summary. https://huggingface.co/docs/transformers/tokenizer_summary.
Hash collision. https://en.wikipedia.org/wiki/Hash_collision.
Deep learning for NLP. http://cs224d.stanford.edu/lecture_notes/notes1.pdf.
TF-IDF. https://en.wikipedia.org/wiki/Tf%E2%80%93idf.
Word2Vec models. https://www.tensorflow.org/tutorials/text/word2vec.
Continuous bag of words. https://www.kdnuggets.com/2018/04/implementing-deep-learning-methods-feature-engineering-text-data-cbow.html.
Skip-gram model. http://mccormickml.com/2016/04/19/word2vec-tutorial-the-skip-gram-model/.
BERT model. https://arxiv.org/pdf/1810.04805.pdf.
GPT3 model. https://arxiv.org/pdf/2005.14165.pdf.
BLOOM model. https://bigscience.huggingface.co/blog/bloom.
Transformer implementation from scratch. https://peterbloem.nl/blog/transformers.
3D convolutions. https://www.kaggle.com/code/shivamb/3d-convolutions-understanding-use-case/notebook.
Vision Transformer. https://arxiv.org/pdf/2010.11929.pdf.
Query understanding for search engines. https://www.linkedin.com/pulse/ai-query-understanding-daniel-tunkelang/.
Multimodal video representation learning. https://arxiv.org/pdf/2012.04124.pdf.
Multilingual language models. https://arxiv.org/pdf/2107.00676.pdf.
Near-duplicate video detection. https://arxiv.org/pdf/2005.07356.pdf.
Generalizable search relevance. https://livebook.manning.com/book/ai-powered-search/chapter-10/v-10/20.
Freshness in search and recommendation systems. https://developers.google.com/machine-learning/recommendation/dnn/re-ranking.
Semantic product search by Amazon. https://arxiv.org/pdf/1907.00937.pdf.
Ranking relevance in Yahoo search. https://www.kdd.org/kdd2016/papers/files/adf0361-yinA.pdf.
Semantic product search in E-Commerce. https://arxiv.org/pdf/2008.08180.pdf.