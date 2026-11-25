"""alcance multi-tenant del registro de modelos + auditoría inmutable

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23 00:00:00.000000

- Añade organization_id (nullable) a model_runs y model_versions para aislar
  ejecuciones/versiones por institución (NULL = artefacto de plataforma DEMO).
- En PostgreSQL protege audit_logs contra UPDATE/DELETE (append-only); el sha256
  encadenado de la aplicación sigue siendo la defensa portátil.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = ("model_runs", "model_versions")


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as b:
            b.add_column(sa.Column("organization_id", sa.Uuid(), nullable=True))
            b.create_foreign_key(f"fk_{table}_organization_id_organizations", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")
            b.create_index(f"ix_{table}_organization_id", ["organization_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION audit_logs_immutable() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_logs es append-only (inmutable)';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_mutation ON audit_logs;")
        op.execute(
            "CREATE TRIGGER audit_logs_no_mutation BEFORE UPDATE OR DELETE ON audit_logs "
            "FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable();"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_mutation ON audit_logs;")
        op.execute("DROP FUNCTION IF EXISTS audit_logs_immutable();")

    for table in reversed(TABLES):
        with op.batch_alter_table(table) as b:
            b.drop_index(f"ix_{table}_organization_id")
            b.drop_constraint(f"fk_{table}_organization_id_organizations", type_="foreignkey")
            b.drop_column("organization_id")
