from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal
from auth import ensure_default_admin
from config import get_settings
from routers import auth, users, persons, search, source_files, analysis

settings = get_settings()

app = FastAPI(
    title="RNP Intelligence Desk API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(persons.router)
app.include_router(search.router)
app.include_router(source_files.router)
app.include_router(analysis.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = f"error: {exc}"
    finally:
        db.close()
    return {"status": "ok", "database": db_status, "version": "1.0.0"}
