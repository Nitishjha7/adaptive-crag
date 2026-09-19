"""Episodic and semantic memory for repeat queries.

Every other design decision in this project treats one query as fully
independent (see `schemas/crag_state.py`'s `initial_state`: "There is no
checkpointer and no memory — the graph is stateless"). That is still true of
`CRAGState` itself. This package adds something orthogonal: memory that spans
*across* queries, not state inside one.

Two of the three usual memory types, not three:

* **episodic** (`episodic.py`) - has a similar question been asked before, and
  was the answer to it grounded (`guardrail_passed`) or not. Retrieved by real
  vector similarity, reusing the exact `get_embeddings()` / Chroma setup
  `app/config.py` already has for retrieval - a second FastEmbed model or a
  second vector store would be solving a problem this project has already
  solved once.
* **semantic** (`semantic.py`) - facts distilled from *clusters* of episodes
  that share the same ungrounded verdict, e.g. "questions about topic X
  consistently fail groundedness on this corpus." Built from episodic, not
  independent of it.

**No long-term memory here, and that is a stated limitation, not an
oversight.** Long-term memory needs a scope to persist *for* - in
self-healing-sql-agent that is `thread_id`, in code-guardian that is
`repo_id`. This project has no client identity of any kind: `/api/query`
takes a question and nothing else, no cookie, no header, no id. Inventing one
purely to check a box would be a fake feature - a `client_id` nothing else in
this stateless one-shot RAG app needs. See docs/ROADMAP.md for the honest
account of what would have to change first.

Same fail-open contract as the sibling projects: if Chroma or the embedding
model is unavailable, memory is silently off and a query answers exactly as
it did before this package existed.
"""
