"""
Database Backup Service.

Generates full database backups (SQL dumps / JSON snapshots)
for data safety and Disaster Recovery.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

BACKUP_DIR = Path("backups")


class BackupService:
    """Handles automated and manual database backups."""

    def __init__(self) -> None:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    async def create_json_backup(self, db: AsyncSession) -> str:
        """Export all main tables into a structured JSON backup file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"clinic_backup_{timestamp}.json"
        backup_path = BACKUP_DIR / backup_filename

        backup_data = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "version": "v1.0",
            },
            "tables": {},
        }

        tables = ["patients", "doctors", "services", "appointments"]

        for table in tables:
            stmt = text(f"SELECT * FROM {table}")
            res = await db.execute(stmt)
            columns = res.keys()
            rows = res.fetchall()

            table_rows = []
            for row in rows:
                row_dict = {}
                for col, val in zip(columns, row):
                    if isinstance(val, (datetime, datetime)):
                        row_dict[col] = val.isoformat()
                    else:
                        row_dict[col] = str(val) if val is not None else None
                table_rows.append(row_dict)

            backup_data["tables"][table] = table_rows

        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        logger.info("backup_created_successfully", path=str(backup_path))
        return str(backup_path)


backup_service = BackupService()