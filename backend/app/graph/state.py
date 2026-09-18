"""Convenience re-export — makes `CRAGState` importable from `app.graph.state` too.

The canonical definition lives in `app.schemas.crag_state`. Defining it in two
places is how definitions drift, so this is only a re-export.
"""

from app.schemas.crag_state import CRAGState, initial_state

__all__ = ["CRAGState", "initial_state"]
