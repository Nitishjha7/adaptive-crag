# Vector Databases

A vector database stores embeddings alongside the original text and metadata, and answers
nearest-neighbour queries over them.

## Exact vs approximate search

Exact search compares the query vector against every stored vector. It is perfectly
accurate and perfectly simple, and it is fine up to roughly a hundred thousand vectors.
Beyond that, approximate nearest neighbour (ANN) indexes such as HNSW trade a small amount
of recall for a very large speed gain by searching a navigable graph instead of the full
set.

## Embedded vs server mode

Chroma can run embedded - as a library writing to a local directory, with no separate
process. This removes an entire service from the deployment and is enough for a demo or a
small internal tool. In server mode it runs as its own process that multiple clients share,
which is what you want once more than one application instance needs the same index.

## Persistence

An embedded vector store that writes to a directory must have that directory persisted, or
the index is rebuilt on every restart. In Docker this means mounting the store directory as
a volume; re-embedding a corpus on each container start is slow and wasteful.

## Metadata filtering

Most vector stores support filtering on metadata alongside the similarity search - for
example restricting results to a single source document, a date range, or an access level.
Filtering before the similarity search keeps irrelevant material out of the candidate set
entirely, which is usually better than filtering the results afterwards.
