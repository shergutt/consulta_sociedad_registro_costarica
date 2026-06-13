from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    token: str
    expires_at: str
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    username: str
    role: str

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    role: str = Field(default="user", pattern="^(admin|user)$")


class UserListItem(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SummaryResponse(BaseModel):
    db_path: str
    persons: int
    runs: int
    fincas: int
    movable_assets: int
    alerts: int
    source_files: int
    query_outputs: int
    total_fiscal_value: float


class PersonSummary(BaseModel):
    person_id: int
    cedula: str
    nombre: str
    first_name: Optional[str] = None
    latest_folder_path: Optional[str] = None
    run_id: Optional[int] = None
    folder_path: Optional[str] = None
    report_path: Optional[str] = None
    finca_count: Optional[int] = None
    alert_count: Optional[int] = None
    movable_asset_count: Optional[int] = None
    output_counts: dict = {}
    ran_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PersonsResponse(BaseModel):
    persons: list[PersonSummary]


class FincaOut(BaseModel):
    id: int
    persona_id: int
    query_run_id: int
    index_no: Optional[int] = None
    provincia: Optional[str] = None
    provincia_codigo: Optional[str] = None
    numero: Optional[str] = None
    derecho: Optional[str] = None
    duplicado: Optional[str] = None
    horizontal: Optional[str] = None
    matricula: Optional[str] = None
    naturaleza: Optional[str] = None
    ubicacion: Optional[str] = None
    zona_catastrada: Optional[str] = None
    medida: Optional[str] = None
    plano: Optional[str] = None
    antecedentes: Optional[str] = None
    identificador_predial: Optional[str] = None
    valor_fiscal_text: Optional[str] = None
    valor_fiscal_num: Optional[float] = None
    propietario: Optional[str] = None
    anotaciones: Optional[str] = None
    gravamenes: Optional[str] = None
    source_json: Optional[str] = None
    source_txt: Optional[str] = None
    source_html: Optional[str] = None
    created_at: datetime
    alert_count: int = 0
    linked_output_count: int = 0

    model_config = {"from_attributes": True}


class MovableAssetOut(BaseModel):
    id: int
    persona_id: int
    query_run_id: int
    index_no: Optional[int] = None
    asset_type: str
    identificacion: Optional[str] = None
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    numero: Optional[str] = None
    placa: Optional[str] = None
    matricula: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    year: Optional[str] = None
    color: Optional[str] = None
    serie: Optional[str] = None
    vin: Optional[str] = None
    motor: Optional[str] = None
    chasis: Optional[str] = None
    propietario: Optional[str] = None
    cedula_propietario: Optional[str] = None
    estado: Optional[str] = None
    anotaciones: Optional[str] = None
    gravamenes: Optional[str] = None
    source_json: Optional[str] = None
    source_txt: Optional[str] = None
    source_html: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    query_run_id: int
    finca_id: Optional[int] = None
    severity: str
    label: Optional[str] = None
    message: str
    source: str
    created_at: datetime
    finca_numero: Optional[str] = None
    finca_derecho: Optional[str] = None
    finca_provincia: Optional[str] = None

    model_config = {"from_attributes": True}


class QueryOutputOut(BaseModel):
    id: int
    query_type: str
    lookup_key: str
    consulta: Optional[str] = None
    source_json: Optional[str] = None
    source_txt: Optional[str] = None
    source_html: Optional[str] = None
    created_at: datetime
    fincas: Optional[str] = None

    model_config = {"from_attributes": True}


class SourceFileOut(BaseModel):
    id: int
    relative_path: str
    file_type: str
    size_bytes: int
    sha256: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceFileDetail(BaseModel):
    id: int
    query_run_id: int
    relative_path: str
    file_type: str
    size_bytes: int
    sha256: str
    content_text: Optional[str] = None
    created_at: datetime
    cedula: Optional[str] = None
    nombre: Optional[str] = None

    model_config = {"from_attributes": True}


class PersonDetailResponse(BaseModel):
    person: PersonOut
    analysis: dict
    fincas: list[FincaOut]
    movable_assets: list[MovableAssetOut]
    alerts: list[AlertOut]
    query_outputs: list[QueryOutputOut]
    source_files: list[SourceFileOut]


class RunAnalysisRequest(BaseModel):
    cedula: str = Field(..., min_length=9, max_length=12, pattern=r"^\d{9,12}$")
    pausa: float = Field(default=15.0, ge=0)
    limite: Optional[int] = None


class JobOut(BaseModel):
    id: str
    user_id: Optional[int] = None
    cedula: str
    ai_model: str
    status: str
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    returncode: Optional[int] = None
    command: Optional[list[str]] = None
    error: Optional[str] = None
    person: Optional[dict] = None
    log_tail: list[str] = []


class JobListResponse(BaseModel):
    jobs: list[JobOut]


class SearchResult(BaseModel):
    result_type: str
    cedula: Optional[str] = None
    nombre: Optional[str] = None
    provincia: Optional[str] = None
    numero: Optional[str] = None
    derecho: Optional[str] = None
    plano: Optional[str] = None
    naturaleza: Optional[str] = None
    valor_fiscal_text: Optional[str] = None
    run_id: Optional[int] = None
    tipo: Optional[str] = None
    placa: Optional[str] = None
    matricula: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    year: Optional[str] = None
    serie: Optional[str] = None
    vin: Optional[str] = None
    motor: Optional[str] = None
    chasis: Optional[str] = None
    propietario: Optional[str] = None

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    results: list[SearchResult]


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
