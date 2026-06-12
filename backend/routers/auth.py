from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session as DBSession
from database import get_db
from schemas import LoginRequest, LoginResponse, UserOut
from models import User
from auth import (
    authenticate_user,
    create_session,
    cleanup_expired_sessions,
    destroy_session,
    get_current_user,
    get_optional_user,
    security,
)
from config import get_settings

router = APIRouter(tags=["auth"])
settings = get_settings()


@router.post("/api/login", response_model=LoginResponse)
def login(body: LoginRequest, db: DBSession = Depends(get_db)):
    user = authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    cleanup_expired_sessions(db)
    session = create_session(db, user.id, hours=settings.session_hours)
    return LoginResponse(
        token=session.token,
        expires_at=session.expires_at.isoformat(),
        user=UserOut(id=user.id, username=user.username, role=user.role),
    )


@router.post("/api/logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: DBSession = Depends(get_db),
):
    if credentials:
        destroy_session(db, credentials.credentials)
    return {"ok": True}


@router.get("/api/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, username=user.username, role=user.role)
