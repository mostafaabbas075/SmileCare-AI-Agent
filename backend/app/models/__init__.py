"""
Models package.

Import all models here so that:

  1. Alembic's ``--autogenerate`` can detect every table.
  2. SQLAlchemy resolves all relationship back-references at import time.

Every new model file MUST be imported in this module.
"""

from app.models.appointment import Appointment
from app.models.conversation_history import ConversationHistory
from app.models.doctor import Doctor
from app.models.knowledge_document import KnowledgeDocument
from app.models.patient import Patient
from app.models.service import Service

__all__ = [
    "Patient",
    "Doctor",
    "Service",
    "Appointment",
    "ConversationHistory",
    "KnowledgeDocument",
]
