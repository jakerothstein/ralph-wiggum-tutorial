"""Custom SQLAlchemy column types.

The single tricky type here is :class:`EmbeddingVector`. The application stores
chunk embeddings in PostgreSQL using the ``pgvector`` extension (so we can run
cosine-distance similarity search in the database). However, the unit-test suite
runs against SQLite in-memory, which has no ``vector`` type.

Rather than maintain two parallel model definitions (which would violate the
"single source of truth, no migrations/adapters" rule), we define one column
type that adapts by dialect:

* On PostgreSQL it resolves to ``pgvector.sqlalchemy.Vector`` so real similarity
  search works in production.
* On any other dialect (SQLite in tests) it falls back to a ``TEXT`` column that
  stores the vector as a JSON array, so the model still creates and round-trips.

This keeps every model, controller, and test importing the same models without
SQLite-incompatible columns breaking the suite.
"""
from __future__ import annotations

import json
from typing import Any, Sequence, cast

from pgvector.sqlalchemy import Vector
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator, TypeEngine


class EmbeddingVector(TypeDecorator[Any]):
    """A vector column that uses pgvector on PostgreSQL and JSON text elsewhere."""

    impl = Text
    cache_ok = True

    def __init__(self, dims: int) -> None:
        self.dims = dims
        super().__init__()

    def load_dialect_impl(self, dialect: Any) -> TypeEngine[Any]:
        if dialect.name == 'postgresql':
            return cast(TypeEngine[Any], dialect.type_descriptor(Vector(self.dims)))
        return cast(TypeEngine[Any], dialect.type_descriptor(Text()))

    def process_bind_param(
        self, value: Sequence[float] | None, dialect: Any
    ) -> Any:
        if value is None:
            return None
        if dialect.name == 'postgresql':
            # pgvector accepts a plain list of floats.
            return list(value)
        return json.dumps([float(x) for x in value])

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if dialect.name == 'postgresql':
            return list(value)
        return json.loads(value)
