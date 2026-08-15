"""
Dashboard Analytics Service.

Calculates clinic KPIs, revenue drivers, booking states, top services, and busiest days.
"""

from __future__ import annotations

from datetime import date, datetime
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AppointmentStatus
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.service import Service
from app.schemas.dashboard import (
    BusiestDayStat,
    DashboardStatsResponse,
    TopServiceStat,
)

logger = structlog.get_logger(__name__)


class DashboardService:
    """Aggregates real-time analytical metrics for clinic management."""

    async def get_dashboard_stats(self, db: AsyncSession) -> DashboardStatsResponse:
        today = date.today()
        first_day_of_month = date(today.year, today.month, 1)

        # 1. إحصائيات حالات الحجوزات
        status_stmt = select(
            Appointment.status,
            func.count(Appointment.id),
        ).group_by(Appointment.status)
        status_res = await db.execute(status_stmt)
        status_counts = dict(status_res.all())

        total_appointments = sum(status_counts.values())
        scheduled = status_counts.get(AppointmentStatus.SCHEDULED, 0)
        confirmed = status_counts.get(AppointmentStatus.CONFIRMED, 0)
        completed = status_counts.get(AppointmentStatus.COMPLETED, 0)
        cancelled = status_counts.get(AppointmentStatus.CANCELLED, 0)
        no_show = status_counts.get(AppointmentStatus.NO_SHOW, 0)

        # 2. إحصائيات المرضى
        total_patients_res = await db.execute(select(func.count(Patient.id)))
        total_patients = total_patients_res.scalar() or 0

        new_patients_res = await db.execute(
            select(func.count(Patient.id)).where(Patient.created_at >= first_day_of_month)
        )
        new_patients_this_month = new_patients_res.scalar() or 0

        blacklisted_res = await db.execute(
            select(func.count(Patient.id)).where(Patient.is_blacklisted == True)
        )
        blacklisted_patients_count = blacklisted_res.scalar() or 0

        # 3. أكثر الخدمات طلباً (Top Services)
        top_services_stmt = (
            select(
                Service.id,
                Service.name,
                func.count(Appointment.id).label("cnt"),
            )
            .join(Appointment, Appointment.service_id == Service.id)
            .group_by(Service.id, Service.name)
            .order_by(func.count(Appointment.id).desc())
            .limit(5)
        )
        top_services_res = await db.execute(top_services_stmt)
        top_services = [
            TopServiceStat(
                service_id=str(row[0]),
                service_name=row[1],
                booking_count=row[2],
            )
            for row in top_services_res.all()
        ]

        # 4. أكثر الأيام ازدحاماً (Busiest Days)
        busiest_days_stmt = (
            select(
                Appointment.appointment_date,
                func.count(Appointment.id).label("cnt"),
            )
            .where(Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]))
            .group_by(Appointment.appointment_date)
            .order_by(func.count(Appointment.id).desc())
            .limit(5)
        )
        busiest_days_res = await db.execute(busiest_days_stmt)
        busiest_days = [
            BusiestDayStat(
                booking_date=str(row[0]),
                booking_count=row[1],
            )
            for row in busiest_days_res.all()
        ]

        return DashboardStatsResponse(
            total_appointments=total_appointments,
            scheduled_appointments=scheduled,
            confirmed_appointments=confirmed,
            completed_appointments=completed,
            cancelled_appointments=cancelled,
            no_show_appointments=no_show,
            total_patients=total_patients,
            new_patients_this_month=new_patients_this_month,
            blacklisted_patients_count=blacklisted_patients_count,
            top_services=top_services,
            busiest_days=busiest_days,
        )


dashboard_service = DashboardService()