# Vector Embeddings

An embedding is a fixed-length vector of floating point numbers that represents the
meaning of a piece of text. Texts with similar meanings land close together in the
vector space, which is what makes semantic search possible: instead of matching
keywords, you compare positions in that space.

## Similarity metrics

Cosine similarity is the most common metric for text embeddings. It measures the angle
between two vectors and ignores their magnitude, which matters because embedding models
often produce vectors whose length varies with text length rather than with meaning. A
cosine score of 1.0 means the vectors point in the same direction; 0.0 means they are
unrelated.

Dot product and Euclidean (L2) distance are the other common options. For normalised
embeddings (unit length), cosine similarity and dot product rank results identically.

## Model size trade-off

Small embedding models such as BAAI/bge-small-en-v1.5 produce 384-dimensional vectors and
run fast on CPU. Larger models produce 768 or 1024 dimensions and capture finer semantic
distinctions, at the cost of more compute per document and a bigger index. For a small
knowledge base the retrieval quality difference is usually smaller than the difference a
good chunking strategy makes.

## Local vs hosted embeddings

Hosted embedding APIs require a network round trip and an API key for every document and
every query. Local ONNX-based models like FastEmbed run entirely in-process, which removes
that latency and cost from the retrieval path and lets the system work offline.
