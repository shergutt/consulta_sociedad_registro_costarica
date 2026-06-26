from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import exists as sa_exists
from sqlalchemy.orm import Session as DBSession
from database import get_db
from schemas import SourceFileDetail
from models import SourceFile, QueryRun, Person, PersonQuery
from auth import get_optional_user

router = APIRouter(tags=["source_files"])


@router.get("/api/source-files/{source_id}", response_model=SourceFileDetail)
def source_file(
    source_id: int,
    user = Depends(get_optional_user),
    db: DBSession = Depends(get_db),
):
    row = (
        db.query(SourceFile, Person.id.label("person_id"), Person.cedula, Person.nombre)
        .join(QueryRun, QueryRun.id == SourceFile.query_run_id)
        .join(Person, Person.id == QueryRun.person_id)
        .filter(SourceFile.id == source_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No existe archivo fuente {source_id}")

    sf = row[0]
    person_id = row.person_id

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")
    if user.role != "admin":
        can_see = db.query(
            sa_exists().where(
                (PersonQuery.person_id == person_id) & (PersonQuery.user_id == user.id)
            )
        ).scalar()
        if not can_see:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No existe archivo fuente {source_id}")

    return SourceFileDetail(
        id=sf.id,
        query_run_id=sf.query_run_id,
        relative_path=sf.relative_path,
        file_type=sf.file_type,
        size_bytes=sf.size_bytes,
        sha256=sf.sha256,
        content_text=sf.content_text,
        created_at=sf.created_at,
        cedula=row.cedula,
        nombre=row.nombre,
    )
