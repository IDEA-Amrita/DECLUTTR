import time
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session, engine
from app.models.schemas import ScanRequest, Suggestion, FileSuggestionOut, ProtectedRule
from app.services import storage_service, xai_service

router = APIRouter()

# in-memory job store: scan_id → {status, progress, suggestions}
scan_jobs: dict[str, dict] = {}


def _run_scan_job(scan_id: str, directory: str):
    from sqlmodel import Session as S

    scan_jobs[scan_id]["status"] = "scanning"
    try:
        with S(engine) as db:
            rules_raw = [
                {"type": r.type, "value": r.value}
                for r in db.exec(select(ProtectedRule)).all()
            ]

        raw = storage_service.run_full_scan(directory, rules_raw)
        scan_jobs[scan_id]["status"] = "generating_reasons"
        scan_jobs[scan_id]["progress"] = 50

        items_for_xai = [
            {
                "id": str(uuid.uuid4()),
                "filename": r["name"],
                "size_mb": r["size_bytes"] / 1_048_576,
                "last_accessed_days_ago": max(0, int((time.time() - r["last_accessed"]) / 86400)),
                "suggestion_type": r["type"],
            }
            for r in raw
        ]
        reasons = xai_service.generate_batch_reasons(items_for_xai, module="storage")

        suggestions_out = []
        with S(engine) as db:
            for i, r in enumerate(raw):
                item = items_for_xai[i]
                s = Suggestion(
                    id=item["id"],
                    scan_id=scan_id,
                    type=r["type"],
                    path=r["path"],
                    size_bytes=r["size_bytes"],
                    last_accessed=r["last_accessed"],
                    reason=reasons.get(item["id"]),
                    confidence=r["confidence"],
                )
                db.add(s)
                suggestions_out.append(s.model_dump())
            db.commit()

        scan_jobs[scan_id]["status"] = "complete"
        scan_jobs[scan_id]["progress"] = 100
        scan_jobs[scan_id]["suggestions"] = suggestions_out
    except Exception as e:
        scan_jobs[scan_id]["status"] = "error"
        scan_jobs[scan_id]["error"] = str(e)


@router.post("/storage/scan")
def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    scan_id = str(uuid.uuid4())
    scan_jobs[scan_id] = {"status": "pending", "progress": 0, "suggestions": []}
    background_tasks.add_task(_run_scan_job, scan_id, req.directory)
    return {"scan_id": scan_id}


@router.get("/storage/scan/{scan_id}/status")
def get_scan_status(scan_id: str):
    if scan_id not in scan_jobs:
        raise HTTPException(status_code=404, detail="Scan not found")
    job = scan_jobs[scan_id]
    return {"status": job["status"], "progress": job["progress"]}


@router.get("/storage/scan/{scan_id}/suggestions", response_model=list[FileSuggestionOut])
def get_suggestions(scan_id: str, session: Session = Depends(get_session)):
    if scan_id in scan_jobs and scan_jobs[scan_id]["suggestions"]:
        return [FileSuggestionOut(**s) for s in scan_jobs[scan_id]["suggestions"]]
    # fallback: read from SQLite after restart
    results = session.exec(select(Suggestion).where(Suggestion.scan_id == scan_id)).all()
    if not results:
        raise HTTPException(status_code=404, detail="Scan not found")
    return results
