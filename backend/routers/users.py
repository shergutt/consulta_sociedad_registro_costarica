from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from datetime import datetime, timezone
from database import get_db
from schemas import CreateUserRequest, UserOut, UserListItem
from models import User
from auth import require_admin, hash_password, get_current_user

router = APIRouter(tags=["users"])


@router.get("/api/users")
def list_users(
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    rows = db.query(User).order_by(User.id).all()
    return {"users": [UserListItem.model_validate(u) for u in rows]}


@router.post("/api/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def add_user(
    body: CreateUserRequest,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, username=user.username, role=user.role)


@router.delete("/api/users/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    if admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No podés eliminar tu propia cuenta")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    db.delete(user)
    db.commit()
    return {"ok": True}
