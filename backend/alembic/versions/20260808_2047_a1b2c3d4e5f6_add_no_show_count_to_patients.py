"""add_no_show_count_to_patients

Revision ID: a1b2c3d4e5f6
Revises: 0985bedb4424
Create Date: 2026-08-08 20:47:00.000000+00:00

Note: is_blacklisted and banned_until were already added to the DB via
fix_patients_table.py (raw ALTER TABLE). This migration only adds
no_show_count which was completely missing from the DB schema.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0985bedb4424"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add no_show_count column -- was never in the DB schema.
    op.add_column(
        "patients",
        sa.Column(
            "no_show_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )

    # Ensure is_blacklisted and banned_until exist (idempotent, safe to run
    # even if they were already added via fix_patients_table.py).
    op.execute(
        "ALTER TABLE patients ADD COLUMN IF NOT EXISTS "
        "is_blacklisted BOOLEAN NOT NULL DEFAULT FALSE;"
    )
    op.execute(
        "ALTER TABLE patients ADD COLUMN IF NOT EXISTS "
        "banned_until TIMESTAMP WITH TIME ZONE;"
    )


def downgrade() -> None:
    op.drop_column("patients", "no_show_count")
    # Note: we do NOT drop is_blacklisted or banned_until in downgrade
    # since they were added outside alembic and may contain production data.
