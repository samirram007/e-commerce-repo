"""Unit-of-Work / transaction boundary.

The use case (service chain under one request endpoint) owns the commit:
FastAPI dependency `get_db` yields a session; a successful handler commits
once, and any unhandled error rolls the whole request back. Repositories and
nested services must never commit. See AGENT.md §3/§6.
"""
from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_session_factory


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
