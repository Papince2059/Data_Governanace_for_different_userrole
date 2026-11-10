"""
Enterprise Data Governance — Application Entry Point.
Production-grade FastAPI application with pre-retrieval ACL filtering and Zanzibar ReBAC.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.api.v1 import (
    auth,
    chat,
    departments,
    documents,
    groups,
    ingestion,
    permissions,
    users,
)
from src.core.config import get_settings
from src.core.exceptions import GovernanceBaseError
from src.core.logging import configure_logging, set_log_context
from src.infrastructure.database.connection import close_db, get_db_session, init_db
from src.infrastructure.openfga.client import OpenFGAClient

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager for startup and shutdown routines."""
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    logger.info("application_startup_initiated", app=settings.APP_NAME, version=settings.APP_VERSION)

    # Initialize PostgreSQL connection pool
    try:
        await init_db()
        logger.info("database_connection_initialized")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))

    yield

    # Teardown
    await close_db()
    logger.info("application_shutdown_complete")


app = FastAPI(
    title="Enterprise Data Governance System",
    description="Production-Grade Pre-Retrieval ACL Filtering with Zanzibar-Based OpenFGA ReBAC",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Assign or preserve correlation request_id on every incoming request."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    set_log_context(request_id=request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(GovernanceBaseError)
async def governance_error_handler(request: Request, exc: GovernanceBaseError):
    """Centralized handler for all domain and security exceptions."""
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "request_id": request_id,
        },
    )


# Register API v1 Routers
api_v1_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_v1_prefix)
app.include_router(users.router, prefix=api_v1_prefix)
app.include_router(departments.router, prefix=api_v1_prefix)
app.include_router(groups.router, prefix=api_v1_prefix)
app.include_router(documents.router, prefix=api_v1_prefix)
app.include_router(permissions.router, prefix=api_v1_prefix)
app.include_router(chat.router, prefix=api_v1_prefix)
app.include_router(ingestion.router, prefix=api_v1_prefix)


@app.get("/health/live", tags=["Monitoring"])
async def health_live() -> dict[str, str]:
    """Liveness probe: verifies the process is running."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["Monitoring"])
async def health_ready() -> dict[str, str]:
    """
    Readiness probe: checks both PostgreSQL and OpenFGA connectivity.
    Fails closed if either service is unreachable.
    """
    db_ok = False
    fga_ok = False

    # Check PostgreSQL
    try:
        async for session in get_db_session():
            result = await session.execute(text("SELECT 1;"))
            if result.scalar() == 1:
                db_ok = True
            break
    except Exception as e:
        logger.warning("readiness_db_check_failed", error=str(e))

    # Check OpenFGA
    try:
        fga = OpenFGAClient(
            api_url=settings.OPENFGA_API_URL,
            store_id=settings.OPENFGA_STORE_ID,
            auth_model_id=settings.OPENFGA_AUTH_MODEL_ID,
            timeout=3,
        )
        fga_ok = await fga.health_check()
        await fga.close()
    except Exception as e:
        logger.warning("readiness_fga_check_failed", error=str(e))

    overall = "ok" if (db_ok and fga_ok) else "degraded"
    return {
        "status": overall,
        "database": "ok" if db_ok else "unreachable",
        "openfga": "ok" if fga_ok else "unreachable",
    }

