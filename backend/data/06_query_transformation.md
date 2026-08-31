# Query Transformation

Query transformation rewrites the user's question before it is used for retrieval or search.
It exists because the form a question takes when a person types it is rarely the form that
retrieves best.

## Rewriting for search engines

Conversational questions carry filler that means nothing to a keyword-based search engine.
Rewriting "can you help me understand how the new pricing works" into a tight keyword query
strips the filler and leaves the terms that actually discriminate between documents. The
rewrite is a small, cheap language model call.

## HyDE

Hypothetical Document Embeddings takes the opposite approach for vector search: generate a
hypothetical answer to the question, then embed that answer and use it as the query. Because
the hypothetical answer is written in the same declarative register as the corpus, its
embedding often sits closer to the real answer than the question's embedding does. The
hypothetical answer does not need to be factually correct - only structurally similar.

## Multi-query expansion

Generating several paraphrases of the question, retrieving for each, and merging the results
increases recall when a single phrasing happens to miss. The cost is more retrieval calls
and a larger candidate set to rank.

## Decomposition

A compound question - one that asks about two things and compares them - retrieves poorly as
a single query, because no single chunk covers both halves. Decomposing it into sub-questions
and retrieving separately for each addresses this, at the cost of managing multiple retrieval
passes and combining their results.
