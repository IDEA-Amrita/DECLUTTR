from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends  # type: ignore
from sqlmodel import Session, select

from app.database import get_session
from app.models.schemas import WeeklySnapshot, ConsentLog, Suggestion

router = APIRouter()


def _iso_week_start() -> str:
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


@router.get("/report/weekly")
def get_weekly(session: Session = Depends(get_session)):
    rows = session.exec(
        select(WeeklySnapshot).order_by(WeeklySnapshot.week_start.desc()).limit(8)
    ).all()
    return list(reversed(rows))


@router.post("/report/snapshot")
def create_snapshot(session: Session = Depends(get_session)):
    from app.routers.photos import photo_jobs

    week_start = _iso_week_start()
    week_dt = datetime.fromisoformat(week_start)
    week_end_dt = week_dt + timedelta(days=7)

    logs = session.exec(select(ConsentLog)).all()
    week_logs = [
        lg for lg in logs
        if week_start <= lg.confirmed_at[:10] < week_end_dt.date().isoformat()
        and lg.success == 1
    ]

    mb_reclaimed = 0.0
    items_cleared = len(week_logs)
    for lg in week_logs:
        s = session.get(Suggestion, lg.suggestion_id)
        if s:
            mb_reclaimed += s.size_bytes / 1_048_576

    storage_score = min(100.0, (mb_reclaimed / 500) * 100)

    photo_score = 0.0
    if photo_jobs:
        last_job = list(photo_jobs.values())[-1]
        results = last_job.get("results", [])
        if results:
            photo_score = sum(r["score"] for r in results) / len(results)

    composite = round(storage_score * 0.7 + photo_score * 0.3, 2)

    existing = session.exec(
        select(WeeklySnapshot).where(WeeklySnapshot.week_start == week_start)
    ).first()

    if existing:
        existing.storage_score = storage_score
        existing.photo_score = photo_score
        existing.composite_score = composite
        existing.mb_reclaimed = round(mb_reclaimed, 2)
        existing.items_cleared = items_cleared
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    snap = WeeklySnapshot(
        week_start=week_start,
        storage_score=storage_score,
        photo_score=photo_score,
        composite_score=composite,
        mb_reclaimed=round(mb_reclaimed, 2),
        items_cleared=items_cleared,
    )
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
