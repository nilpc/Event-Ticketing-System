"""NFR-6: SQLAlchemy 2.0 async declarative base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for identity and booking schemas."""
