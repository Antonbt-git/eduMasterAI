from fastapi import APIRouter

from ...modules import academic, analytics, certificates, community, identity, ml, notifications, realtime, recommendations, tracking, tutor

api_router = APIRouter()
for m in (identity, academic, tracking, analytics, recommendations, certificates, community, notifications, ml, realtime, tutor):
    api_router.include_router(m.router)
api_router.include_router(certificates.public)
api_router.include_router(ml.internal)
