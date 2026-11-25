"""alinea FK organization_id de modelos con ondelete CASCADE

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24 00:00:00.000000
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLES = ("model_runs", "model_versions")
NAME = "fk_{table}_organization_id_organizations"


def upgrade() -> None:
    for table in TABLES:
        op.drop_constraint(NAME.format(table=table), table, type_="foreignkey")
        op.create_foreign_key(NAME.format(table=table), table, "organizations",
                              ["organization_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    for table in TABLES:
        op.drop_constraint(NAME.format(table=table), table, type_="foreignkey")
        op.create_foreign_key(NAME.format(table=table), table, "organizations",
                              ["organization_id"], ["id"])
