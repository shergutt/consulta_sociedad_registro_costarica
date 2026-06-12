from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, func, literal_column
from sqlalchemy.orm import Session as DBSession
from database import get_db
from schemas import SearchResponse, SearchResult
from models import Person, Finca, MovableAsset
from auth import get_optional_user

router = APIRouter(tags=["search"])


@router.get("/api/search", response_model=SearchResponse)
def search(
    q: str = Query(default=""),
    user = Depends(get_optional_user),
    db: DBSession = Depends(get_db),
):
    term = (q or "").strip()
    if not term:
        return SearchResponse(results=[])

    like = f"%{term}%"

    finca_query = (
        db.query(
            literal_column("'finca'").label("result_type"),
            Person.cedula,
            func.coalesce(Person.nombre, Person.first_name, "").label("nombre"),
            Finca.provincia, Finca.numero, Finca.derecho, Finca.plano,
            Finca.naturaleza, Finca.valor_fiscal_text,
            Finca.query_run_id.label("run_id"),
        )
        .join(Person, Person.id == Finca.persona_id)
        .filter(
            or_(
                Person.cedula.ilike(like),
                Person.nombre.ilike(like),
                Finca.numero.ilike(like),
                Finca.plano.ilike(like),
                Finca.naturaleza.ilike(like),
                Finca.ubicacion.ilike(like),
            )
        )
        .order_by(Person.nombre, Finca.index_no)
        .limit(80)
    )

    asset_query = (
        db.query(
            literal_column("'bien_mueble'").label("result_type"),
            Person.cedula,
            func.coalesce(Person.nombre, Person.first_name, "").label("nombre"),
            MovableAsset.tipo.label("provincia"),
            MovableAsset.numero, MovableAsset.placa.label("derecho"),
            MovableAsset.matricula.label("plano"),
            MovableAsset.marca.label("naturaleza"),
            MovableAsset.modelo.label("valor_fiscal_text"),
            MovableAsset.query_run_id.label("run_id"),
        )
        .join(Person, Person.id == MovableAsset.persona_id)
        .filter(
            or_(
                Person.cedula.ilike(like),
                Person.nombre.ilike(like),
                MovableAsset.nombre.ilike(like),
                MovableAsset.propietario.ilike(like),
                MovableAsset.placa.ilike(like),
                MovableAsset.matricula.ilike(like),
                MovableAsset.serie.ilike(like),
                MovableAsset.vin.ilike(like),
                MovableAsset.motor.ilike(like),
                MovableAsset.chasis.ilike(like),
                MovableAsset.marca.ilike(like),
                MovableAsset.modelo.ilike(like),
            )
        )
        .order_by(Person.nombre, MovableAsset.index_no)
        .limit(80)
    )

    finca_rows = finca_query.all()
    asset_rows = asset_query.all()

    results = []
    for row in finca_rows:
        results.append(SearchResult(
            result_type=row.result_type, cedula=row.cedula, nombre=row.nombre,
            provincia=row.provincia, numero=row.numero, derecho=row.derecho,
            plano=row.plano, naturaleza=row.naturaleza,
            valor_fiscal_text=row.valor_fiscal_text, run_id=row.run_id,
        ))
    for row in asset_rows:
        results.append(SearchResult(
            result_type=row.result_type, cedula=row.cedula, nombre=row.nombre,
            tipo=row.provincia, numero=row.numero, placa=row.derecho,
            matricula=row.plano, marca=row.naturaleza, modelo=row.valor_fiscal_text,
            run_id=row.run_id,
        ))

    return SearchResponse(results=results)
