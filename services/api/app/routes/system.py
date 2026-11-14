"""Liveness, readiness and collection listing. No session data, no secrets."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import require_demo_access
from app.intake_service import IntakeService, get_intake_service
from app.models import ApiErrorResponse, CollectionsResponse, HealthResponse, ReadinessResponse

router = APIRouter()

_ERRORS = {403: {"model": ApiErrorResponse}, 503: {"model": ApiErrorResponse}}


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/v1/readiness",
    response_model=ReadinessResponse,
    dependencies=[Depends(require_demo_access)],
    responses=_ERRORS,
    tags=["system"],
)
def readiness(service: IntakeService = Depends(get_intake_service)) -> ReadinessResponse:
    return service.readiness()


@router.get(
    "/v1/collections",
    response_model=CollectionsResponse,
    dependencies=[Depends(require_demo_access)],
    responses=_ERRORS,
    tags=["system"],
)
def collections(service: IntakeService = Depends(get_intake_service)) -> CollectionsResponse:
    return service.list_collections()
