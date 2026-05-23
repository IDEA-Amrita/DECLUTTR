import uuid
from fastapi import APIRouter, BackgroundTasks
from app.models.schemas import PhotoScoreRequest, PhotoScoreOut
from app.services import photo_scorer, xai_service

router = APIRouter()

photo_jobs: dict[str, dict] = {}


def _run_photo_job(job_id: str, directory: str):
    photo_jobs[job_id]["status"] = "scoring"
    try:
        scored = photo_scorer.score_directory(directory)
        top10 = scored[:10]

        photo_jobs[job_id]["status"] = "generating_reasons"
        items_for_xai = [
            {
                "id": str(uuid.uuid4()),
                "filename": p["path"].replace("\\", "/").split("/")[-1],
                "size_mb": 0.0,
                "last_accessed_days_ago": 0,
                "suggestion_type": "photo_pick",
            }
            for p in top10
        ]
        reasons = xai_service.generate_batch_reasons(items_for_xai, module="photos")

        for i, item in enumerate(top10):
            xai_id = items_for_xai[i]["id"]
            item["reason"] = reasons.get(
                xai_id,
                f"This photo scores {item['score']:.0f}/100 for aesthetic quality.",
            )

        photo_jobs[job_id]["status"] = "complete"
        photo_jobs[job_id]["results"] = top10
    except Exception as e:
        photo_jobs[job_id]["status"] = "error"
        photo_jobs[job_id]["error"] = str(e)


@router.post("/photos/score")
def start_photo_score(req: PhotoScoreRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    photo_jobs[job_id] = {"status": "pending", "results": []}
    background_tasks.add_task(_run_photo_job, job_id, req.directory)
    return {"job_id": job_id}


@router.get("/photos/score/{job_id}/status")
def get_photo_status(job_id: str):
    if job_id not in photo_jobs:
        return {"status": "not_found"}
    return {"status": photo_jobs[job_id]["status"]}


@router.get("/photos/score/{job_id}/top", response_model=list[PhotoScoreOut])
def get_top_photos(job_id: str):
    if job_id not in photo_jobs:
        return []
    return [PhotoScoreOut(**r) for r in photo_jobs[job_id].get("results", [])]
