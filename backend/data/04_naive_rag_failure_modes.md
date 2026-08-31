# Failure Modes of Naive RAG

Naive RAG is a straight pipeline: embed the question, fetch the top-k nearest chunks, stuff
them into a prompt, generate an answer. It rests on one assumption - that whatever came back
from the vector store is relevant. That assumption fails in predictable ways.

## Retrieval mismatch

Similarity search always returns k results. If the knowledge base contains nothing relevant,
it still returns the k least-irrelevant chunks, and a low similarity score never reaches the
language model. The model receives them as authoritative context and stitches together a
plausible-sounding answer from material that does not actually address the question.

## Staleness

If a fact in the knowledge base has changed since ingestion, the system answers confidently
from the stale version. It has no mechanism for noticing that its own data is out of date.

## Query-document mismatch

Users write conversational questions; documents are written in declarative prose. The
embedding of "can you help me understand how this works" is not close to the embedding of
the paragraph that explains it. This is the gap that query rewriting addresses.

## Lost in the middle

Language models attend most reliably to the beginning and end of a long context. Relevant
material buried in the middle of a large stuffed context is often effectively ignored, which
is one reason retrieving more chunks does not monotonically improve answer quality.

## No abstention

A naive pipeline has no path that ends in "I don't know". Every query produces an answer,
because generation is unconditional. Adding an explicit relevance decision before generation
is what makes abstention - or correction - possible.
