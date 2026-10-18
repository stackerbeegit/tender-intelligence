from fastapi import APIRouter

from app.api.v1 import analysis, auth, dashboard, documents, health, sources, tenders, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)
api_router.include_router(sources.router)
api_router.include_router(tenders.router)
api_router.include_router(documents.router)
api_router.include_router(analysis.router)

# Sprint 5+: profile, matching
# Sprint 6+: opportunities, notifications
