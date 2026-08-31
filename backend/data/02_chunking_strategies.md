# Chunking Strategies

Documents must be split before embedding, because an embedding compresses an entire
passage into one vector. Embed a whole 40-page document and you get a vector that
represents its average topic and matches nothing precisely.

## Chunk size

Small chunks (200-400 characters) give precise matches but often lack the surrounding
context needed to answer the question. Large chunks (1500+ characters) carry context but
dilute the embedding, so the relevant sentence gets averaged away with unrelated text.
A common starting point is 800 characters with 100 characters of overlap.

## Overlap

Overlap means consecutive chunks share some text at their boundary. Without it, a sentence
that straddles a split point is broken across two chunks and neither one retrieves well.
Overlap of roughly 10-15 percent of the chunk size is typical.

## Recursive character splitting

The recursive character splitter tries a list of separators in order - paragraph breaks,
then line breaks, then sentences, then words - and only falls back to the next separator
when a chunk is still too large. This keeps semantically related text together far more
often than splitting on a fixed character count.

## Structure-aware splitting

For Markdown or HTML, splitting on headings preserves the document's own hierarchy, and
each chunk can carry its heading path as metadata. That metadata is useful both for
filtering at retrieval time and for citing sources in the final answer.
