from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    auth,
    dashboard,
    documents,
    health,
    profile,
    qualification,
    sources,
    tenders,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(sources.router)
api_router.include_router(tenders.router)
api_router.include_router(documents.router)
api_router.include_router(analysis.router)
api_router.include_router(profile.router)
api_router.include_router(qualification.router)

# Sprint 6+: opportunities, notifications
