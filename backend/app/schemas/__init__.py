"""
Schemas package — re-exports all public schemas.
"""

from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentDetailResponse,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.schemas.chat import ChatRequest, ChatResponse, DocumentUploadResponse
from app.schemas.common import (
    ErrorResponse,
    IDResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationParams,
)
from app.schemas.doctor import DoctorCreate, DoctorResponse, DoctorUpdate
from app.schemas.patient import PatientCreate, PatientResponse, PatientUpdate
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate

__all__ = [
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "MessageResponse",
    "IDResponse",
    "ErrorResponse",
    # Patient
    "PatientCreate",
    "PatientUpdate",
    "PatientResponse",
    # Doctor
    "DoctorCreate",
    "DoctorUpdate",
    "DoctorResponse",
    # Service
    "ServiceCreate",
    "ServiceUpdate",
    "ServiceResponse",
    # Appointment
    "AppointmentCreate",
    "AppointmentUpdate",
    "AppointmentResponse",
    "AppointmentDetailResponse",
    # Chat
    "ChatRequest",
    "ChatResponse",
    "DocumentUploadResponse",
]
