import json
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session as DBSession
from database import get_db
from schemas import SummaryResponse, PersonsResponse, PersonSummary, PersonDetailResponse, FincaOut, MovableAssetOut, AlertOut, QueryOutputOut, SourceFileOut
from models import Person, QueryRun, Finca, MovableAsset, Alert, QueryOutput, SourceFile, FincaQueryOutput
from auth import get_optional_user

router = APIRouter(tags=["summary"])


@router.get("/api/summary", response_model=SummaryResponse)
def summary(
    user = Depends(get_optional_user),
    db: DBSession = Depends(get_db),
):
    """All authenticated users see the same shared counts in v2."""
    persons = db.query(func.count(Person.id)).scalar() or 0
    runs = db.query(func.count(QueryRun.id)).scalar() or 0
    fincas = db.query(func.count(Finca.id)).scalar() or 0
    movable_assets = db.query(func.count(MovableAsset.id)).scalar() or 0
    alerts = db.query(func.count(Alert.id)).scalar() or 0
    source_files = db.query(func.count(SourceFile.id)).scalar() or 0
    query_outputs = db.query(func.count(QueryOutput.id)).scalar() or 0
    total_fiscal = db.query(func.coalesce(func.sum(Finca.valor_fiscal_num), 0)).scalar() or 0

    return SummaryResponse(
        db_path="postgresql",
        persons=persons,
        runs=runs,
        fincas=fincas,
        movable_assets=movable_assets,
        alerts=alerts,
        source_files=source_files,
        query_outputs=query_outputs,
        total_fiscal_value=float(total_fiscal),
    )


@router.get("/api/persons", response_model=PersonsResponse)
def persons(
    user = Depends(get_optional_user),
    db: DBSession = Depends(get_db),
):
    """List all persons. Each entry shows the latest query_run info."""
    latest_run_subq = (
        db.query(QueryRun.id)
        .filter(QueryRun.person_id == Person.id)
        .order_by(QueryRun.ran_at.desc(), QueryRun.id.desc())
        .limit(1)
        .correlate(Person)
        .scalar_subquery()
    )

    movable_count_subq = (
        db.query(func.count(MovableAsset.id))
        .filter(MovableAsset.persona_id == Person.id)
        .correlate(Person)
        .scalar_subquery()
    )

    finca_count_subq = (
        db.query(func.count(Finca.id))
        .filter(Finca.persona_id == Person.id)
        .correlate(Person)
        .scalar_subquery()
    )

    query = (
        db.query(
            Person.id.label("person_id"),
            Person.cedula,
            func.coalesce(Person.nombre, Person.first_name, "").label("nombre"),
            Person.first_name,
            Person.latest_folder_path,
            QueryRun.id.label("run_id"),
            QueryRun.folder_path,
            QueryRun.report_path,
            QueryRun.finca_count,
            QueryRun.alert_count,
            finca_count_subq.label("finca_count_current"),
            movable_count_subq.label("movable_asset_count"),
            QueryRun.output_counts_json,
            QueryRun.ran_at,
            QueryRun.created_at,
        )
        .outerjoin(QueryRun, QueryRun.id == latest_run_subq)
        .order_by(QueryRun.ran_at.desc().nulls_last(), Person.cedula)
    )
    rows = query.all()

    people = []
    for row in rows:
        output_counts = {}
        try:
            output_counts = json.loads(row.output_counts_json or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        people.append(PersonSummary(
            person_id=row.person_id,
            cedula=row.cedula,
            nombre=row.nombre,
            first_name=row.first_name,
            latest_folder_path=row.latest_folder_path,
            run_id=row.run_id,
            folder_path=row.folder_path,
            report_path=row.report_path,
            finca_count=row.finca_count_current if row.finca_count_current is not None else row.finca_count,
            alert_count=row.alert_count,
            movable_asset_count=row.movable_asset_count or 0,
            output_counts=output_counts,
            ran_at=row.ran_at,
            updated_at=row.ran_at,
        ))

    return PersonsResponse(persons=people)


@router.get("/api/persons/{cedula}", response_model=PersonDetailResponse)
def person_detail(
    cedula: str,
    user = Depends(get_optional_user),
    db: DBSession = Depends(get_db),
):
    cedula_clean = re.sub(r"\D", "", cedula or "")
    if not cedula_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cédula inválida")

    person = db.query(Person).filter(Person.cedula == cedula_clean).first()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No hay datos para cédula {cedula_clean}")

    run = (
        db.query(QueryRun)
        .filter(QueryRun.person_id == person.id)
        .order_by(QueryRun.ran_at.desc(), QueryRun.id.desc())
        .first()
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No hay corridas para cédula {cedula_clean}")

    alert_count_subq = (
        db.query(func.count(Alert.id))
        .filter(Alert.finca_id == Finca.id)
        .correlate(Finca)
        .scalar_subquery()
    )
    linked_count_subq = (
        db.query(func.count(FincaQueryOutput.finca_id))
        .filter(FincaQueryOutput.finca_id == Finca.id)
        .correlate(Finca)
        .scalar_subquery()
    )

    fincas = (
        db.query(
            Finca,
            alert_count_subq.label("alert_count"),
            linked_count_subq.label("linked_output_count"),
        )
        .filter(Finca.persona_id == person.id)
        .order_by(Finca.index_no, Finca.id)
        .all()
    )

    finca_outs = []
    for finca, ac, lc in fincas:
        finca_outs.append(FincaOut(
            id=finca.id, persona_id=finca.persona_id, query_run_id=finca.query_run_id,
            index_no=finca.index_no,
            provincia=finca.provincia, provincia_codigo=finca.provincia_codigo,
            numero=finca.numero, derecho=finca.derecho, duplicado=finca.duplicado,
            horizontal=finca.horizontal, matricula=finca.matricula,
            naturaleza=finca.naturaleza, ubicacion=finca.ubicacion,
            zona_catastrada=finca.zona_catastrada, medida=finca.medida,
            plano=finca.plano, antecedentes=finca.antecedentes,
            identificador_predial=finca.identificador_predial,
            valor_fiscal_text=finca.valor_fiscal_text,
            valor_fiscal_num=finca.valor_fiscal_num,
            propietario=finca.propietario, anotaciones=finca.anotaciones,
            gravamenes=finca.gravamenes, source_json=finca.source_json,
            source_txt=finca.source_txt, source_html=finca.source_html,
            created_at=finca.created_at, alert_count=ac or 0,
            linked_output_count=lc or 0,
        ))

    alerts = (
        db.query(Alert, Finca.numero.label("finca_numero"), Finca.derecho.label("finca_derecho"), Finca.provincia.label("finca_provincia"))
        .outerjoin(Finca, Finca.id == Alert.finca_id)
        .filter(Alert.query_run_id == run.id)
        .order_by(
            text("CASE WHEN alerts.severity = 'high' THEN 1 WHEN alerts.severity = 'medium' THEN 2 ELSE 3 END"),
            Alert.id,
        )
        .all()
    )
    alert_outs = [
        AlertOut(
            id=a.Alert.id, query_run_id=a.Alert.query_run_id, finca_id=a.Alert.finca_id,
            severity=a.Alert.severity, label=a.Alert.label, message=a.Alert.message,
            source=a.Alert.source, created_at=a.Alert.created_at,
            finca_numero=a.finca_numero, finca_derecho=a.finca_derecho,
            finca_provincia=a.finca_provincia,
        )
        for a in alerts
    ]

    outputs = (
        db.query(
            QueryOutput.id, QueryOutput.query_type, QueryOutput.lookup_key,
            QueryOutput.consulta, QueryOutput.source_json, QueryOutput.source_txt,
            QueryOutput.source_html, QueryOutput.created_at,
            func.string_agg(Finca.numero + ":" + Finca.derecho, ", ").label("fincas"),
        )
        .outerjoin(FincaQueryOutput, FincaQueryOutput.query_output_id == QueryOutput.id)
        .outerjoin(Finca, Finca.id == FincaQueryOutput.finca_id)
        .filter(QueryOutput.query_run_id == run.id)
        .group_by(QueryOutput.id)
        .order_by(QueryOutput.query_type, QueryOutput.lookup_key)
        .all()
    )
    output_outs = [
        QueryOutputOut(
            id=o.id, query_type=o.query_type, lookup_key=o.lookup_key,
            consulta=o.consulta, source_json=o.source_json, source_txt=o.source_txt,
            source_html=o.source_html, created_at=o.created_at, fincas=o.fincas,
        )
        for o in outputs
    ]

    movable_assets = (
        db.query(MovableAsset)
        .filter(MovableAsset.persona_id == person.id)
        .order_by(MovableAsset.index_no, MovableAsset.id)
        .all()
    )
    asset_outs = [MovableAssetOut.model_validate(ma) for ma in movable_assets]

    source_files = (
        db.query(SourceFile.id, SourceFile.relative_path, SourceFile.file_type,
                  SourceFile.size_bytes, SourceFile.sha256, SourceFile.created_at)
        .filter(SourceFile.query_run_id == run.id)
        .order_by(SourceFile.relative_path)
        .all()
    )
    source_outs = [SourceFileOut.model_validate(sf) for sf in source_files]

    output_counts = {}
    try:
        output_counts = json.loads(run.output_counts_json or "{}")
    except (json.JSONDecodeError, TypeError):
        pass

    analysis_dict = {
        "id": run.id,
        "person_id": run.person_id,
        "triggered_by_user_id": run.triggered_by_user_id,
        "cedula": person.cedula,
        "folder_path": run.folder_path,
        "report_path": run.report_path,
        "report_markdown": run.report_markdown,
        "finca_count": run.finca_count,
        "alert_count": run.alert_count,
        "output_counts": output_counts,
        "ran_at": run.ran_at.isoformat() if run.ran_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.ran_at.isoformat() if run.ran_at else None,
    }

    return PersonDetailResponse(
        person={
            "cedula": person.cedula,
            "nombre": person.nombre,
            "first_name": person.first_name,
            "latest_folder_path": person.latest_folder_path,
        },
        analysis=analysis_dict,
        fincas=finca_outs,
        movable_assets=asset_outs,
        alerts=alert_outs,
        query_outputs=output_outs,
        source_files=source_outs,
    )
