"""
Repositories package — re-exports all repository singletons.
"""

from app.repositories.appointment import appointment_repository
from app.repositories.base import BaseRepository
from app.repositories.conversation_history import conversation_repository
from app.repositories.doctor import doctor_repository
from app.repositories.patient import patient_repository
from app.repositories.service import service_repository

__all__ = [
    "BaseRepository",
    "patient_repository",
    "doctor_repository",
    "service_repository",
    "appointment_repository",
    "conversation_repository",
]
