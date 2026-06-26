"""
API v1 aggregated router.

Registers all sub-routers under the ``/api/v1`` prefix.
Adding a new resource means:
  1. Create a file in ``app/api/v1/routers/``
  2. Import the router here and call ``router.include_router()``
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers.appointments import router as appointments_router
from app.api.v1.routers.chat import router as chat_router
from app.api.v1.routers.doctors import router as doctors_router
from app.api.v1.routers.documents import router as documents_router
from app.api.v1.routers.patients import router as patients_router
from app.api.v1.routers.services import router as services_router

router = APIRouter()

router.include_router(patients_router)
router.include_router(doctors_router)
router.include_router(services_router)
router.include_router(appointments_router)
router.include_router(chat_router)
router.include_router(documents_router)
