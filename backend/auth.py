import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import and_
from database import get_db
from models import User, Session as SessionModel

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:16]
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}${hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split("$", 1)
        check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        return secrets.compare_digest(check, hashed)
    except (ValueError, AttributeError):
        return False


def create_session_token() -> str:
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()


def session_expires(hours: int = 24) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def authenticate_user(db: DBSession, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: DBSession, user_id: int, hours: int = 24) -> SessionModel:
    token = create_session_token()
    now = datetime.now(timezone.utc)
    expires = session_expires(hours)
    session = SessionModel(token=token, user_id=user_id, created_at=now, expires_at=expires)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_user(db: DBSession, token: str) -> User | None:
    if not token:
        return None
    now = datetime.now(timezone.utc)
    result = (
        db.query(User)
        .join(SessionModel, SessionModel.user_id == User.id)
        .filter(and_(SessionModel.token == token, SessionModel.expires_at > now))
        .first()
    )
    return result


def destroy_session(db: DBSession, token: str) -> None:
    db.query(SessionModel).filter(SessionModel.token == token).delete()
    db.commit()


def cleanup_expired_sessions(db: DBSession) -> None:
    now = datetime.now(timezone.utc)
    db.query(SessionModel).filter(SessionModel.expires_at <= now).delete()
    db.commit()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: DBSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")
    user = get_session_user(db, credentials.credentials)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida o expirada")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: DBSession = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    return get_session_user(db, credentials.credentials)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores")
    return user
