# Corrective RAG (CRAG)

Corrective RAG adds an evaluation step between retrieval and generation. Rather than
trusting retrieved documents, the system grades them first and chooses a path based on that
grade. The approach was described by Yan et al. in 2024, and sits in the same family as
Self-RAG, which has a model critique its own retrieval and generation.

## The retrieval evaluator

A lightweight evaluator scores whether the retrieved documents actually support answering
the question. The evaluator runs before any answer is generated, so a bad retrieval is
caught while it is still cheap to fix.

A binary verdict - relevant or not relevant - is the simplest form. It is coarser than a
continuous score, but routing on it is deterministic and easy to explain, and there is no
threshold to tune. Running the evaluator at temperature zero keeps the verdict stable
across identical inputs.

## Knowledge refinement and fallback

When the evaluator finds the local documents insufficient, the system seeks knowledge
elsewhere - typically a web search - instead of generating from material it has already
judged inadequate. The retrieved web content replaces the rejected local documents rather
than being merged with them: documents already graded irrelevant would only dilute the
context and reintroduce the hallucination risk the grading step exists to remove.

## Why fallback rather than always searching

Searching the web on every query would make every request pay a network round trip and
extra tokens, discarding the main advantage of a local index, which is that a hit is fast
and cheap. The evaluator call is the price paid to keep the common path fast; the expensive
correction path runs only when it is actually needed. This conditional routing is what makes
the system adaptive rather than fixed.
