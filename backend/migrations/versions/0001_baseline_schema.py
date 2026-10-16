"""Baseline schema matching original create_all tables

Revision ID: 0001_baseline_schema
Revises: None
Create Date: 2026-10-16 05:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_baseline_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blood_banks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=50), nullable=False),
        sa.Column("locality", sa.String(length=255), nullable=False),
        sa.CheckConstraint("city IN ('Delhi', 'Lucknow')", name="ck_blood_bank_city"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "stock_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("blood_bank_id", sa.Integer(), nullable=False),
        sa.Column("blood_group", sa.String(length=10), nullable=False),
        sa.Column("units_reported", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("data_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_status", sa.String(length=50), nullable=False),
        sa.CheckConstraint(
            "blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')",
            name="ck_stock_report_blood_group",
        ),
        sa.ForeignKeyConstraint(["blood_bank_id"], ["blood_banks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blood_bank_id", "blood_group", name="uq_blood_bank_blood_group"),
    )

    op.create_index("ix_stock_reports_blood_bank_id", "stock_reports", ["blood_bank_id"], unique=False)
    op.create_index("ix_stock_reports_blood_group", "stock_reports", ["blood_group"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stock_reports_blood_group", table_name="stock_reports")
    op.drop_index("ix_stock_reports_blood_bank_id", table_name="stock_reports")
    op.drop_table("stock_reports")
    op.drop_table("blood_banks")
