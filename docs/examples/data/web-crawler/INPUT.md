Design A Web Crawler
In this chapter, we focus on web crawler design: an interesting and classic system design interview question.

A web crawler is known as a robot or spider. It is widely used by search engines to discover new or updated content on the web. Content can be a web page, an image, a video, a PDF file, etc. A web crawler starts by collecting a few web pages and then follows links on those pages to collect new content. Figure 1 shows a visual example of the crawl process.

Image represents a diagram illustrating a website's redirection or linking structure.  A central 'a.com page' box displays the URLs `www.a.com`, `www.b.com`, and `www.c.com`.  Blue arrows emanate from this central box, each pointing to another webpage representation. The first arrow connects to a 'b.com page' displaying `www.banana.com`, which in turn has an arrow pointing to a 'banana.com page'. The second arrow from 'a.com page' connects to a 'c.com page' showing `www.orange.com` and `www.plum.com`, with separate arrows leading to 'orange.com page' and 'plum.com page' respectively.  Finally, a third arrow from 'a.com page' points to an 'a.com page' displaying `www.lime.com`, `www.peach.com`, and `www.mango.com`, with subsequent arrows connecting to individual 'lime.com page', 'peach.com page', and 'mango.com page' representations.  Each webpage representation is a simple browser window icon with three dots in the address bar, suggesting multiple tabs or windows.  The overall structure shows how a single website (`a.com`) can link to and redirect users to multiple other websites.
Figure 1
A crawler is used for many purposes:

Search engine indexing: This is the most common use case. A crawler collects web pages to create a local index for search engines. For example, Googlebot is the web crawler behind the Google search engine.

Web archiving: This is the process of collecting information from the web to preserve data for future uses. For instance, many national libraries run crawlers to archive web sites. Notable examples are the US Library of Congress [1] and the EU web archive [2].

Web mining: The explosive growth of the web presents an unprecedented opportunity for data mining. Web mining helps to discover useful knowledge from the internet. For example, top financial firms use crawlers to download shareholder meetings and annual reports to learn key company initiatives.

Web monitoring. The crawlers help to monitor copyright and trademark infringements over the Internet. For example, Digimarc [3] utilizes crawlers to discover pirated works and reports.

The complexity of developing a web crawler depends on the scale we intend to support. It could be either a small school project, which takes only a few hours to complete or a gigantic project that requires continuous improvement from a dedicated engineering team. Thus, we will explore the scale and features to support below.

Step 1 - Understand the problem and establish design scope
The basic algorithm of a web crawler is simple:

1. Given a set of URLs, download all the web pages addressed by the URLs.

2. Extract URLs from these web pages

3. Add new URLs to the list of URLs to be downloaded. Repeat these 3 steps.

Does a web crawler work truly as simple as this basic algorithm? Not exactly. Designing a vastly scalable web crawler is an extremely complex task. It is unlikely for anyone to design a massive web crawler within the interview duration. Before jumping into the design, we must ask questions to understand the requirements and establish design scope:

Candidate: What is the main purpose of the crawler? Is it used for search engine indexing, data mining, or something else?
Interviewer: Search engine indexing.

Candidate: How many web pages does the web crawler collect per month?
Interviewer: 1 billion pages.

Candidate: What content types are included? HTML only or other content types such as PDFs and images as well?
Interviewer: HTML only.

Candidate: Shall we consider newly added or edited web pages?
Interviewer: Yes, we should consider the newly added or edited web pages.

Candidate: Do we need to store HTML pages crawled from the web?
Interviewer: Yes, up to 5 years

Candidate: How do we handle web pages with duplicate content?
Interviewer: Pages with duplicate content should be ignored.

Above are some of the sample questions that you can ask your interviewer. It is important to understand the requirements and clarify ambiguities. Even if you are asked to design a straightforward product like a web crawler, you and your interviewer might not have the same assumptions.

Beside functionalities to clarify with your interviewer, it is also important to note down the following characteristics of a good web crawler:

Scalability: The web is very large. There are billions of web pages out there. Web crawling should be extremely efficient using parallelization.

Robustness: The web is full of traps. Bad HTML, unresponsive servers, crashes, malicious links, etc. are all common. The crawler must handle all those edge cases.

Politeness: The crawler should not make too many requests to a website within a short time interval.

Extensibility: The system is flexible so that minimal changes are needed to support new content types. For example, if we want to crawl image files in the future, we should not need to redesign the entire system.

Back of the envelope estimation
The following estimations are based on many assumptions, and it is important to communicate with the interviewer to be on the same page.

Assume 1 billion web pages are downloaded every month.

QPS: 1,000,000,000 / 30 days / 24 hours / 3600 seconds = ~400 pages per second.

Peak QPS = 2 * QPS = 800

Assume the average web page size is 500k.

1-billion-page x 500k = 500 TB storage per month. If you are unclear about digital storage units, go through “Power of 2” section in the "Back-of-the-envelope Estimation" chapter again.

Assuming data are stored for five years, 500 TB * 12 months * 5 years = 30 PB. A 30 PB storage is needed to store five-year content.