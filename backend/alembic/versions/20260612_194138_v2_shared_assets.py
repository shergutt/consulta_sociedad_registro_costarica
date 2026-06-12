"""v2 shared assets

Revision ID: 20260612_194138
Revises:
Create Date: 2026-06-12 19:41:38.000000

Big-bang migration: drop v1 (per-user data) and create v2 (person-shared).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260612_194138"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop v1 in reverse-FK order
    op.execute("DROP TABLE IF EXISTS finca_query_outputs CASCADE")
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS source_files CASCADE")
    op.execute("DROP TABLE IF EXISTS query_outputs CASCADE")
    op.execute("DROP TABLE IF EXISTS movable_assets CASCADE")
    op.execute("DROP TABLE IF EXISTS fincas CASCADE")
    op.execute("DROP TABLE IF EXISTS analysis_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS persons CASCADE")

    # Create v2
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('admin', 'user')", name="check_user_role"),
    )

    op.create_table(
        "sessions",
        sa.Column("token", sa.String(255), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_sessions_user", "sessions", ["user_id"])
    op.create_index("idx_sessions_expires", "sessions", ["expires_at"])

    op.create_table(
        "persons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cedula", sa.String(20), nullable=False, unique=True),
        sa.Column("nombre", sa.String(500)),
        sa.Column("first_name", sa.String(255)),
        sa.Column("latest_folder_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "person_queries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("queried_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_person_queries_person", "person_queries", ["person_id", "queried_at"])
    op.create_index("idx_person_queries_user", "person_queries", ["user_id", "queried_at"])

    op.create_table(
        "query_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("folder_path", sa.Text(), nullable=False),
        sa.Column("report_path", sa.Text()),
        sa.Column("report_markdown", sa.Text()),
        sa.Column("finca_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alert_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_counts_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("person_id", "folder_path", name="uq_query_runs_person_folder"),
    )
    op.create_index("idx_query_runs_person", "query_runs", ["person_id", "ran_at"])

    op.create_table(
        "fincas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("persona_id", sa.Integer(), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_run_id", sa.Integer(), sa.ForeignKey("query_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("index_no", sa.Integer()),
        sa.Column("provincia", sa.String(255)),
        sa.Column("provincia_codigo", sa.String(20)),
        sa.Column("numero", sa.String(50)),
        sa.Column("derecho", sa.String(50)),
        sa.Column("duplicado", sa.String(50)),
        sa.Column("horizontal", sa.String(50)),
        sa.Column("matricula", sa.String(100)),
        sa.Column("naturaleza", sa.Text()),
        sa.Column("ubicacion", sa.Text()),
        sa.Column("zona_catastrada", sa.String(255)),
        sa.Column("medida", sa.Text()),
        sa.Column("plano", sa.String(100)),
        sa.Column("antecedentes", sa.Text()),
        sa.Column("identificador_predial", sa.String(100)),
        sa.Column("valor_fiscal_text", sa.String(255)),
        sa.Column("valor_fiscal_num", sa.Float()),
        sa.Column("propietario", sa.Text()),
        sa.Column("anotaciones", sa.Text()),
        sa.Column("gravamenes", sa.Text()),
        sa.Column("resumen_json", sa.Text(), nullable=False),
        sa.Column("detalle_json", sa.Text(), nullable=False),
        sa.Column("texto", sa.Text()),
        sa.Column("source_json", sa.Text()),
        sa.Column("source_txt", sa.Text()),
        sa.Column("source_html", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("persona_id", "numero", "derecho", "plano", name="uq_fincas_natural"),
    )
    op.create_index("idx_fincas_persona", "fincas", ["persona_id"])
    op.create_index("idx_fincas_numero", "fincas", ["numero"])
    op.create_index("idx_fincas_plano", "fincas", ["plano"])

    op.create_table(
        "movable_assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("persona_id", sa.Integer(), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_run_id", sa.Integer(), sa.ForeignKey("query_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("index_no", sa.Integer()),
        sa.Column("asset_type", sa.String(50), nullable=False, server_default="bien_mueble"),
        sa.Column("identificacion", sa.String(255)),
        sa.Column("nombre", sa.String(500)),
        sa.Column("tipo", sa.String(255)),
        sa.Column("numero", sa.String(100)),
        sa.Column("placa", sa.String(50)),
        sa.Column("matricula", sa.String(100)),
        sa.Column("marca", sa.String(100)),
        sa.Column("modelo", sa.String(100)),
        sa.Column("year", sa.String(10)),
        sa.Column("color", sa.String(100)),
        sa.Column("serie", sa.String(100)),
        sa.Column("vin", sa.String(100)),
        sa.Column("motor", sa.String(100)),
        sa.Column("chasis", sa.String(100)),
        sa.Column("propietario", sa.Text()),
        sa.Column("cedula_propietario", sa.String(20)),
        sa.Column("estado", sa.String(255)),
        sa.Column("anotaciones", sa.Text()),
        sa.Column("gravamenes", sa.Text()),
        sa.Column("resumen_json", sa.Text(), nullable=False),
        sa.Column("detalle_json", sa.Text(), nullable=False),
        sa.Column("texto", sa.Text()),
        sa.Column("source_json", sa.Text()),
        sa.Column("source_txt", sa.Text()),
        sa.Column("source_html", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_movable_persona", "movable_assets", ["persona_id"])
    op.create_index("idx_movable_placa", "movable_assets", ["placa"])
    op.create_index("idx_movable_vin", "movable_assets", ["vin"])
    op.create_unique_constraint(
        "uq_movable_natural",
        "movable_assets",
        ["persona_id", "placa", "vin", "serie", "motor", "chasis"],
    )

    op.create_table(
        "query_outputs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_run_id", sa.Integer(), sa.ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_type", sa.String(100), nullable=False),
        sa.Column("lookup_key", sa.String(255), nullable=False),
        sa.Column("consulta", sa.Text()),
        sa.Column("entrada_json", sa.Text()),
        sa.Column("origen_json", sa.Text()),
        sa.Column("payload_json", sa.Text()),
        sa.Column("texto", sa.Text()),
        sa.Column("source_json", sa.Text()),
        sa.Column("source_txt", sa.Text()),
        sa.Column("source_html", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_query_outputs_run", "query_outputs", ["query_run_id"])
    op.create_index("idx_query_outputs_type_key", "query_outputs", ["query_type", "lookup_key"])

    op.create_table(
        "finca_query_outputs",
        sa.Column("finca_id", sa.Integer(), sa.ForeignKey("fincas.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("query_output_id", sa.Integer(), sa.ForeignKey("query_outputs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("relation", sa.String(50), primary_key=True, nullable=False),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_run_id", sa.Integer(), sa.ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finca_id", sa.Integer(), sa.ForeignKey("fincas.id", ondelete="SET NULL")),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("label", sa.String(500)),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_alerts_run", "alerts", ["query_run_id"])

    op.create_table(
        "source_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_run_id", sa.Integer(), sa.ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("query_run_id", "relative_path", name="uq_source_file_run_path"),
    )
    op.create_index("idx_source_files_run", "source_files", ["query_run_id"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS finca_query_outputs CASCADE")
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS source_files CASCADE")
    op.execute("DROP TABLE IF EXISTS query_outputs CASCADE")
    op.execute("DROP TABLE IF EXISTS movable_assets CASCADE")
    op.execute("DROP TABLE IF EXISTS fincas CASCADE")
    op.execute("DROP TABLE IF EXISTS query_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS person_queries CASCADE")
    op.execute("DROP TABLE IF EXISTS sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS persons CASCADE")
