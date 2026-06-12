from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    person_queries = relationship("PersonQuery", back_populates="user")
    query_runs = relationship("QueryRun", back_populates="triggered_by_user")

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="check_user_role"),
    )


class Session(Base):
    __tablename__ = "sessions"

    token = Column(String(255), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_expires", "expires_at"),
    )


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cedula = Column(String(20), nullable=False, unique=True)
    nombre = Column(String(500))
    first_name = Column(String(255))
    latest_folder_path = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    fincas = relationship("Finca", back_populates="person", cascade="all, delete-orphan")
    movable_assets = relationship("MovableAsset", back_populates="person", cascade="all, delete-orphan")
    query_runs = relationship("QueryRun", back_populates="person", cascade="all, delete-orphan")
    person_queries = relationship("PersonQuery", back_populates="person", cascade="all, delete-orphan")


class PersonQuery(Base):
    __tablename__ = "person_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    queried_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    person = relationship("Person", back_populates="person_queries")
    user = relationship("User", back_populates="person_queries")

    __table_args__ = (
        Index("idx_person_queries_person", "person_id", "queried_at"),
        Index("idx_person_queries_user", "user_id", "queried_at"),
    )


class QueryRun(Base):
    __tablename__ = "query_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    triggered_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    folder_path = Column(Text, nullable=False)
    report_path = Column(Text)
    report_markdown = Column(Text)
    finca_count = Column(Integer, nullable=False, default=0)
    alert_count = Column(Integer, nullable=False, default=0)
    output_counts_json = Column(Text, nullable=False, default="{}")
    ran_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    person = relationship("Person", back_populates="query_runs")
    triggered_by_user = relationship("User", back_populates="query_runs")
    query_outputs = relationship("QueryOutput", back_populates="query_run", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="query_run", cascade="all, delete-orphan")
    source_files = relationship("SourceFile", back_populates="query_run", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("person_id", "folder_path", name="uq_query_runs_person_folder"),
        Index("idx_query_runs_person", "person_id", "ran_at"),
    )


class Finca(Base):
    __tablename__ = "fincas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    persona_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    query_run_id = Column(Integer, ForeignKey("query_runs.id", ondelete="RESTRICT"), nullable=False)
    index_no = Column(Integer)
    provincia = Column(String(255))
    provincia_codigo = Column(String(20))
    numero = Column(String(50))
    derecho = Column(String(50))
    duplicado = Column(String(50))
    horizontal = Column(String(50))
    matricula = Column(String(100))
    naturaleza = Column(Text)
    ubicacion = Column(Text)
    zona_catastrada = Column(String(255))
    medida = Column(Text)
    plano = Column(String(100))
    antecedentes = Column(Text)
    identificador_predial = Column(String(100))
    valor_fiscal_text = Column(String(255))
    valor_fiscal_num = Column(Float)
    propietario = Column(Text)
    anotaciones = Column(Text)
    gravamenes = Column(Text)
    resumen_json = Column(Text, nullable=False)
    detalle_json = Column(Text, nullable=False)
    texto = Column(Text)
    source_json = Column(Text)
    source_txt = Column(Text)
    source_html = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    person = relationship("Person", back_populates="fincas")
    alerts = relationship("Alert", back_populates="finca")
    finca_query_outputs = relationship("FincaQueryOutput", back_populates="finca", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("persona_id", "numero", "derecho", "plano", name="uq_fincas_natural"),
        Index("idx_fincas_persona", "persona_id"),
        Index("idx_fincas_numero", "numero"),
        Index("idx_fincas_plano", "plano"),
    )


class MovableAsset(Base):
    __tablename__ = "movable_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    persona_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    query_run_id = Column(Integer, ForeignKey("query_runs.id", ondelete="RESTRICT"), nullable=False)
    index_no = Column(Integer)
    asset_type = Column(String(50), nullable=False, default="bien_mueble")
    identificacion = Column(String(255))
    nombre = Column(String(500))
    tipo = Column(String(255))
    numero = Column(String(100))
    placa = Column(String(50))
    matricula = Column(String(100))
    marca = Column(String(100))
    modelo = Column(String(100))
    year = Column(String(10))
    color = Column(String(100))
    serie = Column(String(100))
    vin = Column(String(100))
    motor = Column(String(100))
    chasis = Column(String(100))
    propietario = Column(Text)
    cedula_propietario = Column(String(20))
    estado = Column(String(255))
    anotaciones = Column(Text)
    gravamenes = Column(Text)
    resumen_json = Column(Text, nullable=False)
    detalle_json = Column(Text, nullable=False)
    texto = Column(Text)
    source_json = Column(Text)
    source_txt = Column(Text)
    source_html = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    person = relationship("Person", back_populates="movable_assets")

    __table_args__ = (
        Index("idx_movable_persona", "persona_id"),
        Index("idx_movable_placa", "placa"),
        Index("idx_movable_vin", "vin"),
        UniqueConstraint("persona_id", "placa", "vin", "serie", "motor", "chasis", name="uq_movable_natural"),
    )


class QueryOutput(Base):
    __tablename__ = "query_outputs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_run_id = Column(Integer, ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False)
    query_type = Column(String(100), nullable=False)
    lookup_key = Column(String(255), nullable=False)
    consulta = Column(Text)
    entrada_json = Column(Text)
    origen_json = Column(Text)
    payload_json = Column(Text)
    texto = Column(Text)
    source_json = Column(Text)
    source_txt = Column(Text)
    source_html = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    query_run = relationship("QueryRun", back_populates="query_outputs")
    finca_query_outputs = relationship("FincaQueryOutput", back_populates="query_output", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_query_outputs_run", "query_run_id"),
        Index("idx_query_outputs_type_key", "query_type", "lookup_key"),
    )


class FincaQueryOutput(Base):
    __tablename__ = "finca_query_outputs"

    finca_id = Column(Integer, ForeignKey("fincas.id", ondelete="CASCADE"), primary_key=True)
    query_output_id = Column(Integer, ForeignKey("query_outputs.id", ondelete="CASCADE"), primary_key=True)
    relation = Column(String(50), nullable=False, primary_key=True)

    finca = relationship("Finca", back_populates="finca_query_outputs")
    query_output = relationship("QueryOutput", back_populates="finca_query_outputs")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_run_id = Column(Integer, ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False)
    finca_id = Column(Integer, ForeignKey("fincas.id", ondelete="SET NULL"))
    severity = Column(String(20), nullable=False)
    label = Column(String(500))
    message = Column(Text, nullable=False)
    source = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    query_run = relationship("QueryRun", back_populates="alerts")
    finca = relationship("Finca", back_populates="alerts")

    __table_args__ = (
        Index("idx_alerts_run", "query_run_id"),
    )


class SourceFile(Base):
    __tablename__ = "source_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_run_id = Column(Integer, ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False)
    relative_path = Column(Text, nullable=False)
    file_type = Column(String(20), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    content_text = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    query_run = relationship("QueryRun", back_populates="source_files")

    __table_args__ = (
        UniqueConstraint("query_run_id", "relative_path", name="uq_source_file_run_path"),
        Index("idx_source_files_run", "query_run_id"),
    )
