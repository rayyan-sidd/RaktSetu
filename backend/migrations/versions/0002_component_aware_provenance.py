"""Component-aware provenance schema and demo backfill

Revision ID: 0002_component_aware_provenance
Revises: 0001_baseline_schema
Create Date: 2026-10-16 05:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_component_aware_provenance"
down_revision: Union[str, None] = "0001_baseline_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Documented legacy retrieval timestamp for pre-existing synthetic demo records
LEGACY_DEMO_RETRIEVAL_TIMESTAMP: str = "2026-10-16 00:00:00"


def upgrade() -> None:
    # 1. Add new columns to blood_banks table
    with op.batch_alter_table("blood_banks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("source_type", sa.String(length=50), server_default="demo", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "source_name",
                sa.String(length=255),
                server_default="Synthetic demo dataset",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("source_facility_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("raw_address", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("category", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("facility_type", sa.String(length=50), nullable=True))

    # 2. Backfill existing facilities with deterministic demo facility identity
    op.execute(
        "UPDATE blood_banks SET source_facility_id = 'demo:' || id, "
        "source_type = 'demo', source_name = 'Synthetic demo dataset' "
        "WHERE source_facility_id IS NULL"
    )

    # 3. Apply unique constraint on (source_name, source_facility_id)
    with op.batch_alter_table("blood_banks", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_blood_bank_source_facility", ["source_name", "source_facility_id"]
        )

    # 4. Modify stock_reports: add component, dual timestamps, freshness indicator,
    # and transition to component-aware unique constraint
    with op.batch_alter_table("stock_reports", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "blood_component",
                sa.String(length=100),
                server_default="Unspecified",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("source_reported_timestamp", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "retrieval_timestamp",
                sa.DateTime(timezone=True),
                server_default=LEGACY_DEMO_RETRIEVAL_TIMESTAMP,
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("freshness_indicator", sa.String(length=50), nullable=True))

        # Drop legacy single-group unique constraint and replace with component-aware constraint
        batch_op.drop_constraint("uq_blood_bank_blood_group", type_="unique")
        batch_op.create_unique_constraint(
            "uq_blood_bank_group_component",
            ["blood_bank_id", "blood_group", "blood_component"],
        )
        batch_op.create_index(
            "ix_stock_reports_blood_component", ["blood_component"], unique=False
        )

    # 5. Ensure legacy stock reports have source_reported_timestamp=NULL and blood_component='Unspecified'
    op.execute(
        f"UPDATE stock_reports SET blood_component = 'Unspecified', "
        f"source_reported_timestamp = NULL, "
        f"retrieval_timestamp = '{LEGACY_DEMO_RETRIEVAL_TIMESTAMP}', "
        f"freshness_indicator = NULL "
        f"WHERE verification_status = 'demo' AND (blood_component IS NULL OR blood_component = '')"
    )


def downgrade() -> None:
    # 1. Downgrade stock_reports
    with op.batch_alter_table("stock_reports", schema=None) as batch_op:
        batch_op.drop_index("ix_stock_reports_blood_component")
        batch_op.drop_constraint("uq_blood_bank_group_component", type_="unique")
        batch_op.create_unique_constraint(
            "uq_blood_bank_blood_group", ["blood_bank_id", "blood_group"]
        )
        batch_op.drop_column("freshness_indicator")
        batch_op.drop_column("retrieval_timestamp")
        batch_op.drop_column("source_reported_timestamp")
        batch_op.drop_column("blood_component")

    # 2. Downgrade blood_banks
    with op.batch_alter_table("blood_banks", schema=None) as batch_op:
        batch_op.drop_constraint("uq_blood_bank_source_facility", type_="unique")
        batch_op.drop_column("facility_type")
        batch_op.drop_column("category")
        batch_op.drop_column("raw_address")
        batch_op.drop_column("source_facility_id")
        batch_op.drop_column("source_name")
        batch_op.drop_column("source_type")
