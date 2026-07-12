"""FR-12, NFR-6: Gateway package — app factory re-export."""

from .app import create_app

__all__ = ["create_app"]
