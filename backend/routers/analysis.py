from fastapi import APIRouter, Depends, HTTPException, status
from database import get_db
from schemas import RunAnalysisRequest, JobOut, JobListResponse
from models import User
from auth import get_current_user
from services import analysis_runner

router = APIRouter(tags=["analysis"])


@router.post("/api/run-analysis", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def run_analysis(
    body: RunAnalysisRequest,
    user: User = Depends(get_current_user),
):
    try:
        job = analysis_runner.start_analysis(
            cedula=body.cedula,
            user_id=user.id,
            pausa=body.pausa,
            limite=body.limite,
        )
        return JobOut(**job)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/api/jobs", response_model=JobListResponse)
def list_jobs(user: User = Depends(get_current_user)):
    jobs = analysis_runner.list_jobs(user_id=user.id, is_admin=(user.role == "admin"))
    return JobListResponse(jobs=[JobOut(**j) for j in jobs])


@router.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: User = Depends(get_current_user)):
    try:
        job = analysis_runner.get_job(
            job_id, user_id=user.id, is_admin=(user.role == "admin"), include_log=True,
        )
        return JobOut(**job)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
