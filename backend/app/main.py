from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.connectors  # noqa: F401  (registers connectors with app.connectors.registry)
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting up in environment=%s debug=%s", settings.environment, settings.debug)
    yield


app = FastAPI(
    title="Stackerbee Tender Intelligence & Opportunity Management Platform",
    description=(
        "Tender intelligence and decision-support API. Discovers, processes, and "
        "analyses government procurement opportunities; never autonomously bids, "
        "accepts terms, or declares final eligibility — see docs/architecture.md."
    ),
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "service": "stackerbee-tender-intelligence",
        "status": "ok",
        "docs": "/docs",
        "api_prefix": settings.api_v1_prefix,
    }
