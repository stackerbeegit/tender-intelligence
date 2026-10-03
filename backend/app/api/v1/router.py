from fastapi import APIRouter

from app.api.v1 import auth, dashboard, health, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(dashboard.router)

# Sprint 2+: sources, tenders, search
# Sprint 5+: profile, matching
# Sprint 6+: opportunities, notifications
