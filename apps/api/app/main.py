"""FastAPI application entry point."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router as v1_router
from app.core.config import get_settings


def _expire_orders_once() -> int:
    """One sweeper pass: cancel abandoned gateway checkouts and commit."""
    from app.db.session import get_session_factory
    from app.modules.sales import service as sales

    with get_session_factory()() as session:
        expired = sales.expire_unpaid_orders(session)
        session.commit()
        return expired


async def _sweep_unpaid_orders(interval_seconds: int) -> None:
    """Background loop: release stock held by unpaid storefront orders."""
    log = logging.getLogger("erp.orders")
    while True:
        await asyncio.sleep(max(interval_seconds, 30))
        try:
            expired = await asyncio.to_thread(_expire_orders_once)
            if expired:
                log.info("expired unpaid storefront orders", extra={"count": expired})
        except Exception:  # a failed sweep must not kill the loop
            log.exception("order expiry sweep failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.getLogger("erp").info("startup", extra={"app_env": settings.app_env})
    from app.shared.cache import init_cache

    init_cache()
    sweeper = None
    if settings.order_payment_timeout_minutes > 0 and settings.order_expiry_sweep_seconds > 0:
        sweeper = asyncio.create_task(_sweep_unpaid_orders(settings.order_expiry_sweep_seconds))
    yield
    if sweeper is not None:
        sweeper.cancel()
    logging.getLogger("erp").info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ERP API",
        version="0.1.0",
        description="E-commerce, inventory, delivery and accounting ERP",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next) -> Response:
        import uuid

        cid = request.headers.get("X-Request-Id") or str(uuid.uuid4())[:8]
        request.state.correlation_id = cid
        logging.getLogger("erp.request").debug(
            f"{request.method} {request.url.path} [{cid}]"
        )
        response = await call_next(request)
        response.headers["X-Request-Id"] = cid
        return response

    @app.get("/health", tags=["ops"])
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/db", tags=["ops"])
    async def health_db() -> dict:
        from sqlalchemy import text

        from app.db.session import build_engine

        engine = build_engine()
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ok", "db": True}
        except Exception:
            return {"status": "degraded", "db": False}

    from app.core.exceptions import install_exception_handlers

    install_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()
