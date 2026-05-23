from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
import send2trash

from app.database import get_session
from app.models.schemas import ConsentRequest, ConsentLog, Suggestion

router = APIRouter()


@router.post("/consent/confirm")
def confirm_consent(req: ConsentRequest, session: Session = Depends(get_session)):
    if not req.confirmed:
        return {"executed": False, "message": "Action not confirmed"}

    suggestion = session.get(Suggestion, req.suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    success = 0
    try:
        send2trash.send2trash(suggestion.path)
        success = 1
    except Exception as e:
        log = ConsentLog(
            suggestion_id=req.suggestion_id,
            action=req.action,
            confirmed_at=datetime.now(timezone.utc).isoformat(),
            success=0,
        )
        session.add(log)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Failed to delete: {e}")

    suggestion.consent_given = 1
    session.add(suggestion)

    log = ConsentLog(
        suggestion_id=req.suggestion_id,
        action=req.action,
        confirmed_at=datetime.now(timezone.utc).isoformat(),
        success=success,
    )
    session.add(log)
    session.commit()

    return {"executed": True}
