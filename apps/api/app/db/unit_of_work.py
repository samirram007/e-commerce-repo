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


def commit_before_reply(session: Session) -> None:
    """Commit the request's unit of work *before* the response is sent.

    FastAPI runs dependency teardown — and with it `get_db`'s commit — after the
    response has been flushed to the client, so a reply is visible a moment
    before the rows it describes are durable. An endpoint whose caller
    immediately follows up with a request that reads what it just wrote (the
    storefront's checkout → Razorpay order pair) must therefore commit eagerly:
    otherwise the follow-up can reach another connection before the commit lands
    and report the new row as missing.

    `get_db` still owns the transaction — its commit is simply a no-op, and it
    still rolls back if the handler raises.
    """
    session.commit()
