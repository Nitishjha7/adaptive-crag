# Code Q&A — defending the decisions

Twenty-seven questions this code invites, with answers. They are not about lines;
they are about **decisions** — which is what anyone reading the code will actually
ask about.

**How to use this:** read a question, answer it out loud **without looking**. Where
you stall is the weak spot, and that is where a follow-up will land too. Don't
memorise the answers — every one of them explains a *why*, and that is the part that
survives a follow-up question.

Each question names its file and lines. **Open the code before reading the answer.**

---

## 1. `grade_documents.py` — the grader

[backend/app/nodes/grade_documents.py](../backend/app/nodes/grade_documents.py)

### Q1. Why a binary `yes`/`no`? A threshold on the cosine similarity score would have saved an entire LLM call.

A score **needs a threshold** — cut at 0.7, or 0.75? That differs per corpus and has
to be tuned. A binary verdict is deterministic and explainable: there is no tuned
constant that has to be revisited later.

More importantly, a similarity score does not ask the question that needs asking.
Cosine similarity says *"how similar is this text to the query"*, when the question
is *"does this text contain the answer"*. A document can be topically very close and
still not answer anything — that is precisely naive RAG's failure mode.

Asking the LLM for a decimal would be worse still: the model does not produce a
calibrated probability. Printing `0.87` would be **fake precision**, and this
project's rule is that a number that was not measured does not get displayed.

### Q2. What breaks if `parse_verdict` checks for `yes` first?

[grade_documents.py:44-47](../backend/app/nodes/grade_documents.py#L44-L47)

The model can return something like `"no, because the documents mention yes..."`.
Check `yes` first and that substring matches, so the verdict comes out **inverted** —
a "no" case read as "yes".

The reverse order is safe: the string `"yes"` never appears inside `"no"`.

The other half of the same decision: when nothing parses, the default is **`no`**,
not `yes`. The reason is asymmetry — a wrong `no` costs one extra web call; a wrong
`yes` means answering from context that was just rejected, which is a hallucination.
The cheap mistake is the one to choose.

### Q3. What if the grader ran at `temperature` 0.7?

[grade_documents.py:61-63](../backend/app/nodes/grade_documents.py#L61-L63)

**Routing would become non-deterministic** — the same question would sometimes go
local and sometimes to the web. Three things break:

1. **The demo** — click the same chip, get a different route
2. **Debugging** — a bug cannot be reproduced
3. **The eval** — routing accuracy stops meaning anything. Two runs give different
   numbers with no way to tell whether the code changed or only the sampling

Some randomness in generation is fine. **In a decision it is not.**

### Q4. Why skip the LLM call when `documents` is empty?

[grade_documents.py:54-59](../backend/app/nodes/grade_documents.py#L54-L59)

There is nothing to grade. Sending empty context and asking "does this contain the
answer" is a call whose answer is already known. Return `no` directly and let the
fallback run.

This is not only an optimisation: if the model answered `yes` on empty documents,
`generate` would produce an answer with no context at all.

### Q5. Does the grader see all four chunks at once, or one at a time?

[grade_documents.py:67](../backend/app/nodes/grade_documents.py#L67) — `"\n\n---\n\n".join(documents)`

All at once, in a single call. Per-chunk grading would be more granular — you would
learn *which* chunk was useful — but it costs **k times more LLM calls**, and this
project's whole cost argument rests on call counts.

**There is a real consequence that the eval surfaced:** because the grader
concatenates the chunks, **ordering is invisible to it**. That is why reranking —
which improves ordering — could not move routing at all. That negative result in
`RESULTS.md` traces back to exactly this line.

---

## 2. `build_graph.py` — the conditional edge

[backend/app/graph/build_graph.py](../backend/app/graph/build_graph.py)

### Q6. A chain would have worked. Why a graph?

Because which node runs after `grade_documents` is **not fixed at compile time** —
it is decided at runtime by reading state. A linear chain cannot express that; in a
chain every step's successor is written in advance.

That is what "Adaptive" means here: the path can differ per query.

### Q7. Why is `decide_to_generate` so empty? What decision is it actually making?

[build_graph.py:30-41](../backend/app/graph/build_graph.py#L30-L41)

**It is deliberately empty.** The whole decision happens in `grade_documents`; this
function only reads the result.

The reason: keeping grading logic and routing logic apart means they can be **tested
separately**. The router's test runs with no LLM at all — set `relevance_score` in
state and check which string comes back. If grading happened here, that test would
need a mocked model.

### Q8. Why does it default to `transform_query` rather than `generate`?

[build_graph.py:41](../backend/app/graph/build_graph.py#L41)

```python
return "generate" if state.get("relevance_score") == "yes" else "transform_query"
```

Only an exact `"yes"` reaches generation. Everything else — `"no"`, an empty string,
a missing key, any unexpected value — goes to the fallback.

The same asymmetry again: if `relevance_score` is empty because of a bug, the safe
direction is the correction path, not answering from unverified context.

### Q9. Why not two `generate` nodes, one for local and one for web?

[build_graph.py:68-70](../backend/app/graph/build_graph.py#L68-L70)

Because `generate` only reads `state["documents"]`. It should not know where the
context came from — that is a good contract. Two nodes would duplicate the same
prompt and the same logic, and both would have to be changed together.

Both branches merge at `generate`; the source difference lives in `source_type`,
which exists only for the UI badge and the eval.

---

## 3. `web_search_fallback.py` — the correction path

[backend/app/nodes/web_search_fallback.py](../backend/app/nodes/web_search_fallback.py)

### Q10. **(The most-asked one)** Why not merge the web snippets with the local documents? Surely more context is better?

[web_search_fallback.py:61-66](../backend/app/nodes/web_search_fallback.py#L61-L66)

**No.** Those local documents were just graded `"no"` — the grader said they do not
contain the answer. Keeping them in context:

1. **Dilutes** the good web context
2. **Reintroduces** exactly the hallucination risk the grading step exists to remove

The entire grading step would be pointless if rejected material still reached the
prompt. So `documents` is **replaced**, not appended to.

This matters enough to have its own test: `test_routing.py` asserts that no local
document survives into context after a fallback.

### Q11. Why replace `sources` too?

[web_search_fallback.py:54-56](../backend/app/nodes/web_search_fallback.py#L54-L56)

Otherwise the UI would **cite local filenames underneath a web-sourced answer**. That
is a lie to the user — the answer was not built from those files.

The search-failure path sets `sources: []` for the same reason.

### Q12. Why such a broad `except Exception`? Isn't that bad practice?

[web_search_fallback.py:48-59](../backend/app/nodes/web_search_fallback.py#L48-L59)

It is deliberate here, and the comment says so. A failed search is **recoverable** —
rate limiting, network, a missing key — and the correct behaviour is identical for
all three.

Crashing would turn the whole request into a 500 and stop the demo. Instead the node
returns empty documents and `generate` states plainly that no context was found. The
exception type and message both go to the log, so debugging does not suffer.

**The difference is that failing is not silent** — the trace shows `FAILED` and the
UI marks that step in red.

### Q13. The URL appears both in the snippet text and in the `sources` list. Isn't that duplication?

[web_search_fallback.py:22-38](../backend/app/nodes/web_search_fallback.py#L22-L38)

No — they serve different consumers. The URL in the text is **for the model**, so it
can cite inline. The list is **for the UI**, for structured citations. Remove it from
the text and inline citation dies.

---

## 4. `crag_state.py` — state design

[backend/app/schemas/crag_state.py](../backend/app/schemas/crag_state.py)

### Q14. **(The deepest one)** `logs` has a reducer and `documents` does not. Why?

[crag_state.py:72](../backend/app/schemas/crag_state.py#L72)

```python
logs: Annotated[List[str], operator.add]
```

`logs` is **additive** — each node appends one line. No node needs to know what ran
before it, and the full execution trace assembles itself for free. That trace is what
the UI renders.

`documents` **overwrites** (the default, no reducer) — and this is the single most
important design decision in the project. With `operator.add` here, the snippets from
`web_search_fallback` would be **concatenated** onto the local documents. That is the
Q10 mistake all over again, except caused by one line of reducer, silently, without
any node's code changing.

**A single `Annotated` line can undo the entire correction step.**

`sources` overwrites for the same reason.

### Q15. Why is `initial_state()` a separate function? Why not build the dict inline?

[crag_state.py:76-92](../backend/app/schemas/crag_state.py#L76-L92)

The additive reducer on `logs` operates **on a list** — it crashes on `None`. So it
has to be initialised to `[]`. Writing that once rather than at every call site means
there is exactly one place to get it wrong.

The second reason shows up in the demo: **every request builds a fresh
`initial_state()`.** There is no checkpointer and no memory — the graph is stateless.
That is why the UI's history is labelled as a *record* rather than conversation
memory.

### Q16. Why is `question` never mutated?

The rewrite goes into a separate key, `transformed_query`. Overwriting the original
would make it impossible to see, in the trace, what the user asked versus what the
system turned it into. Showing that difference is the most convincing part of the
fallback path — the UI's *"Rewritten for search: ..."* comes from exactly this.

---

## 5. Retrieval — hybrid and reranking

[backend/app/tools/reranker.py](../backend/app/tools/reranker.py)

### Q17. What is the difference between a bi-encoder and a cross-encoder?

- **Bi-encoder (the retriever):** embeds the query and the document **separately**.
  Document vectors are computed ahead of time; at query time it is one embedding plus
  a nearest-neighbour lookup. That is why it is fast — and also why it cannot see any
  query-document interaction, because the two never enter the model together.
- **Cross-encoder (the reranker):** puts both into the model **together** and reads
  each in the context of the other. Considerably more accurate. The cost: one forward
  pass per (query, document) pair, which is impossible across a whole corpus.

Hence the two stages: **a cheap retriever proposes candidates, an expensive reranker
picks the best of them.**

### Q18. Why doesn't RRF normalise the scores?

[reranker.py:66-75](../backend/app/tools/reranker.py#L66-L75)

Vector search returns a cosine **distance** (0 is best) and BM25 returns an unbounded
positive score (higher is best). Those are different scales, and converting one into
the other is corpus-specific tuning — which will be wrong on the next corpus.

RRF uses **rank only**: `score(d) = Σ 1 / (60 + rank(d))`. What the score value was
does not matter, so any two retrievers can be fused without knowing their scales.

### Q19. Why doesn't `rerank()` raise when it fails?

[reranker.py:57-60](../backend/app/tools/reranker.py#L57-L60)

Reranking is an **improvement, not a requirement**. If the model fails to load,
retrieval should still work — just slightly less accurately. So the original order is
returned (fail open).

The alternative — a failed reranker killing the whole query — lets an optional
component take down the core path.

### Q20. Is the reranker there for answer quality, or something else?

In this project it feeds **the grader's input**. `grade_documents` decides whether the
local context is sufficient. If retrieval found the right chunk but left it low in the
top-k, the grader never sees it and can return a wrong `"no"`. The reranker lifts the
right chunk up.

**But** — recall Q5 — the grader concatenates the chunks, so ordering is invisible to
it. That is why the A/B came back flat. Hold both facts together: the reranker could
have helped the grader in theory, and cannot help *this* grader given how it is built.

---

## 6. The eval — where the follow-ups will land

### Q21. Routing accuracy is 100%. Does that mean the router is perfect?

**No, it means the task is easy.** The corpus gap is **categorical** — concepts in,
vendor/pricing/news out — so most web cases differ along an obvious axis. I designed
that gap, and I wrote the labels.

Which is why 8 **ambiguous** cases were added, where the corpus half-covers the topic,
and they are scored on **stability** rather than **correctness** — because the right
answer for them is genuinely debatable.

### Q22. You wrote the corpus and you wrote the labels. Isn't that bias?

**Yes, and it is stated.** That is why BEIR SciFact was added: there the `local` case
labels come from the dataset's own **qrels** — expert judgements about which abstract
answers which claim. I did not create those labels.

The `web` cases are still hand-written, and that is stated too — but they are the easy
half: SciFact is 2020-era scientific abstracts, so a question about today's pricing
cannot possibly be in it.

### Q23. Why is there no latency number?

Because it could not be measured, and saying so is itself a finding.

The first run went in file order — all the local cases, then all the web ones. Result:
`local 13.7s vs web 18.5s`, a clean win for local. **It was an artifact.** The
per-case timings show everything after case 5 landing at 15–22s regardless of route —
Groq was throttling, and because the local cases ran first, the entire slowdown fell
into their bucket.

`interleave()` was added to alternate local and web. Re-run: `local 16.2s vs web
14.9s` — web apparently **faster**, which is structurally impossible since it does
strictly more work. Both numbers were noise.

So the cost argument rests on **LLM call counts** (local 3, web 4), which follow from
the shape of the graph and reproduce exactly.

### Q24. What is the difference between a "missed fallback" and an "unnecessary fallback"?

- **Missed fallback** — answered locally when it should not have.
  **The expensive error**: the user gets a confident answer built on the wrong context.
- **Unnecessary fallback** — searched the web when the local documents were enough.
  **The cheap error**: one extra LLM call and some latency; the answer is still right.

Missed fallbacks are **0** on both corpora. The router only errs in the cheap
direction — and that is the result of a design choice (Q2, Q8), not luck.

### Q25. What did hybrid search and reranking actually improve?

**Nothing on the concepts corpus** — routing 20/20 either way, stability 8/8 either
way. But retrieval genuinely changed: **27 of 28 questions** were answered from
different chunks, and 0 were identical.

The reason is in Q5: the grader does not read ordering, and on a 22-chunk corpus a
change in membership rarely changes the topic.

**It moved on SciFact:** routing 75.0% → 78.6%, recall@k 65% → 70%. But that is
**exactly one case** out of 28, and one gold document out of 20 — inside the noise.
What is established is the mechanism, not the magnitude.

### Q26. So is reranking useless?

No — **it was measured against the wrong metric.** Reranking should show up in the
*answer* (which passages the model writes from), not in routing. Which is why an
**answer verdict** metric was added afterwards: SciFact is a claim-verification
dataset, so the dataset itself says whether the gold abstract SUPPORTS or CONTRADICTS
the claim — and it can be measured whether our answer says the same.

That is not an LLM judge: the dataset decides right and wrong, and the model is used
only to *read* what stand the answer took.

### Q27. SciFact is 78.6%. Is the grader bad?

**The opposite.** On the baseline run the correlation was perfect:

| Gold document | Cases | Route | Correct |
|---|---|---|---|
| Retrieved | 13 | local | **13 / 13** |
| Missed | 7 | web | 0 / 7 |

**The grader made zero independent errors.** Every "routing failure" was a retrieval
miss that the grader correctly caught — it saw four chunks that did not contain the
answer and said so. 78.6% **under-reports** the grader; the bottleneck is retrieval,
not grading.

## 6.1 `app/memory/` — episodic and semantic

### Q28. Why does episodic memory use real vector similarity while the sibling projects use exact matching?

Because the unit of comparison is different. self-healing-sql-agent's episodic
memory compares SQL questions where an exact-signature match (after normalizing
whitespace and identifiers) is the right granularity; code-guardian compares code
shapes the same way. Here the unit is a natural-language question, which is
exactly what an embedding model is for — and this project already has one loaded
for retrieval (`get_embeddings()`), so reusing it for memory cost nothing extra.

### Q29. What was the bug `test_consolidate_writes_fact_at_threshold` caught?

An early version stored the fact's own declarative sentence as the embedded
document (`'Questions like "X" have repeatedly failed...'`), and `recall_facts`
searched by the incoming *question*. A declarative sentence sits much further
from a question in embedding space than another question does, so the fact
almost never came back for the very question it was written for. Fixed by
embedding the cluster's representative question instead, and moving the fact's
prose into metadata. This is exactly the kind of bug a fake-embedding unit test
would never catch — it only shows up against the real model.

### Q30. `POST /api/memory/consolidate` is a separate endpoint from the query path. Why not run it automatically?

Because it is a full-collection scan (`consolidate_facts()` clusters every
ungrounded episode), not a per-query cost. Running it inline on every request
would mean every user's question pays for an aggregate over the entire memory
store — the same reasoning self-healing-sql-agent gives its own
`consolidate_facts()`, arrived at independently here because the constraint is
identical regardless of what backs the store.

### Q31. Why did the same fact appear in one process but not another right after being written?

A real bug, not a hypothetical — see docs/CODE_NOTES.md's `app/memory/` section
for the full account. `chromadb`'s `PersistentClient` is cached process-wide by
persist path, so a running server's in-memory client did not see a write another
process (or even the same process's earlier collection handle) made to the same
SQLite-backed directory. Fixed with `SharedSystemClient.clear_system_cache()`
after a consolidation writes anything. Every unit test passed the whole time,
because each test starts a fresh process — this only surfaces against a
long-running server, which is why it was caught by manual live verification
against `docker compose up`, not by the test suite.

---

## 7. Break a test on purpose

Faster than reading. Break it, see what fails, then put it back.

**Exercise 1 — the docs-replace invariant**

In [web_search_fallback.py:65](../backend/app/nodes/web_search_fallback.py#L65):

```python
"documents": snippets,                      # as written
"documents": state["documents"] + snippets, # try this
```

Then run `.\dev.ps1 test`. Which test fails? Read its name and work out **why** it was
written. Then put it back.

**Exercise 2 — the reducer**

In [crag_state.py:35](../backend/app/schemas/crag_state.py#L35), make `documents`
`Annotated[List[str], operator.add]`. Now **no node's code has changed** — and the same
bug is back. Run the tests.

This is the best exercise for understanding that state design is as load-bearing as
the code.

**Exercise 3 — the default direction**

In [build_graph.py:41](../backend/app/graph/build_graph.py#L41), invert the condition:

```python
return "generate" if state.get("relevance_score") == "yes" else "transform_query"   # as written
return "transform_query" if state.get("relevance_score") == "no" else "generate"    # try this
```

Both behave **identically** for `"yes"` and `"no"`. Now think: if `relevance_score`
ended up empty — a bug, or a new output format from the grader — what happens in each?
Which version is safe, and why?

No test catches this, because no test sends an empty `relevance_score`. Which is what
makes it the most useful exercise here: some decisions are caught by thinking, not by
the suite.

---

## If one of these does not come out

Open the file the question is about and read its docstring — the reason for each
decision is written there. Then answer the question again without looking.

And if an answer here seems **wrong** to you, that is valid too. Disagreeing with the
code is worth more than reciting it.
