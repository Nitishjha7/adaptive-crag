# Agent Graphs and State

A chain is a fixed sequence of steps. A graph is a set of nodes connected by edges, where
some edges are chosen at runtime. That distinction is the reason an agent that must decide
what to do next cannot be expressed as a chain.

## Nodes, edges, conditional edges

A node is a function that receives the current state and returns a partial update to it. A
normal edge always routes from one node to the same next node. A conditional edge routes to
different nodes depending on a routing function that reads the state - this is where a
runtime decision lives.

## State and reducers

State is a typed object threaded through every node. A node returns only the keys it wants
to change, and those updates are merged into the state rather than replacing it wholesale.

By default a returned key overwrites the existing value. A reducer changes that merge
behaviour per key: an additive reducer on a list makes each node's returned items append to
the list instead of replacing it. This is how an execution log is accumulated across nodes -
every node appends one line, and no node has to know what came before it.

Overwrite semantics are the right choice when a node genuinely supersedes a value. A node
that replaces the working document set with a different set wants to overwrite, not append.

## Explainability

Because every node writes to the same state object, the state carries a complete record of
what ran and in what order by the time execution ends. Returning that trace alongside the
answer turns the system from a black box into something whose decisions can be inspected -
which node ran, what the routing decision was, and which source the answer came from.

## Merging branches

When two branches produce the same kind of result, they should merge back into one shared
node rather than duplicating it per branch. A generation node that reads only the working
document set does not need to know which branch filled that set, so one node serves both
paths and there is only one prompt to maintain.
