"""Aggregated /api/v1 router."""

from fastapi import APIRouter

from app.api.v1 import analyze, auth, datasets, jobs, models

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(analyze.router)
api_router.include_router(datasets.router)
api_router.include_router(jobs.router)
api_router.include_router(models.router)
