"""
Dashboard Analytics Schemas.
"""

from __future__ import annotations

from pydantic import BaseModel


class TopServiceStat(BaseModel):
    service_id: str
    service_name: str
    booking_count: int


class BusiestDayStat(BaseModel):
    booking_date: str
    booking_count: int


class DashboardStatsResponse(BaseModel):
    total_appointments: int
    scheduled_appointments: int
    confirmed_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
    total_patients: int
    new_patients_this_month: int
    blacklisted_patients_count: int
    top_services: list[TopServiceStat]
    busiest_days: list[BusiestDayStat]