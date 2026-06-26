"""
Services package — re-exports all service singletons.
"""

from app.services.appointment_service import appointment_service
from app.services.doctor_service import doctor_service
from app.services.patient_service import patient_service
from app.services.service_service import service_service

__all__ = [
    "patient_service",
    "doctor_service",
    "service_service",
    "appointment_service",
]
