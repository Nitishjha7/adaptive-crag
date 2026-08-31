"""Convenience re-export — `app.graph.state` se bhi CRAGState mile.

Canonical definition `app.schemas.crag_state` me hai. Do jagah define karna
drift ka rasta hai, isliye yahan sirf re-export.
"""

from app.schemas.crag_state import CRAGState, initial_state

__all__ = ["CRAGState", "initial_state"]
