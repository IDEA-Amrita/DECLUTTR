import os
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.database import get_session
from app.models.gdrive_schemas import DriveToken, DriveScanJob, DriveFileRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gdrive", tags=["gdrive"])

SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
BACKEND_ORIGIN  = os.getenv("BACKEND_ORIGIN",  "http://localhost:8000")
REDIRECT_URI    = f"{BACKEND_ORIGIN}/api/gdrive/auth/callback"


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id":     os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    # Create flow without PKCE (we have client_secret, so PKCE not needed)
    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    # Disable PKCE by removing code_challenge_method
    if hasattr(flow, 'code_challenge_method'):
        flow.code_challenge_method = None
    return flow


def _get_token(db: Session) -> DriveToken:
    token = db.exec(select(DriveToken)).first()
    if not token:
        raise HTTPException(404, "Drive not linked. Please link your Google Drive first.")
    return token


def _build_service(token: DriveToken):
    creds = Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    )
    return build("drive", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.get("/auth/url")
def get_auth_url():
    """Generate OAuth URL."""
    flow = _build_flow()

    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true"
    )
    
    return {"auth_url": auth_url}


@router.get("/auth/callback")
def oauth_callback(code: str = Query(...), db: Session = Depends(get_session)):
    """OAuth callback."""
    flow = _build_flow()
    
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        logger.error(f"OAuth token fetch failed: {e}")
        return RedirectResponse(url=f"{FRONTEND_ORIGIN}/gdrive?error=oauth_failed")
    
    creds: Credentials = flow.credentials

    user_info_service = build("oauth2", "v2", credentials=creds)
    user_info = user_info_service.userinfo().get().execute()
    email = user_info.get("email", "unknown@gmail.com")

    existing = db.exec(select(DriveToken).where(DriveToken.user_email == email)).first()
    if existing:
        existing.access_token  = creds.token
        existing.refresh_token = creds.refresh_token or existing.refresh_token
        existing.token_expiry  = str(creds.expiry)
        db.add(existing)
    else:
        db.add(DriveToken(
            user_email=email,
            access_token=creds.token,
            refresh_token=creds.refresh_token or "",
            token_expiry=str(creds.expiry),
        ))
    db.commit()
    return RedirectResponse(url=f"{FRONTEND_ORIGIN}/gdrive?linked=1")


@router.get("/auth/status")
def auth_status(db: Session = Depends(get_session)):
    """Returns accounts in the shape the frontend expects: { linked, accounts: [{id, email}] }"""
    tokens = db.exec(select(DriveToken)).all()
    return {
        "linked": len(tokens) > 0,
        "accounts": [{"id": t.id, "email": t.user_email} for t in tokens],
    }


@router.delete("/auth/unlink")
def unlink_auth(db: Session = Depends(get_session)):
    token = db.exec(select(DriveToken)).first()
    if token:
        db.delete(token)
        db.commit()
    return {"unlinked": True}


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

@router.post("/scan")
def start_scan(
    background_tasks: BackgroundTasks,
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
):
    """Starts a full Drive metadata scan. account_id is optional — uses first linked account if omitted."""
    if account_id:
        token = db.get(DriveToken, account_id)
    else:
        token = db.exec(select(DriveToken)).first()

    if not token:
        raise HTTPException(404, "Drive not linked")

    job = DriveScanJob(user_email=token.user_email)
    db.add(job)
    db.commit()
    db.refresh(job)

    def _run(scan_id: str, email: str):
        from app.database import engine
        with Session(engine) as session:
            from app.services.drive_scanner import DriveScanner
            scanner = DriveScanner(session, email)
            scanner.run_scan(scan_id)

    background_tasks.add_task(_run, job.id, token.user_email)
    return {"scan_id": job.id}


@router.get("/scan/{scan_id}/status")
def scan_status(scan_id: str, db: Session = Depends(get_session)):
    job = db.get(DriveScanJob, scan_id)
    if not job:
        raise HTTPException(404, "Scan not found")
    return {
        "scan_id":          job.id,
        "status":           job.status,
        "total_files":      job.total_files,
        "processed_files":  job.processed_files,
        "duplicates_found": job.duplicates_found,
        "bytes_reclaimable": job.bytes_reclaimable,
        "error_message":    job.error_message,
    }


@router.get("/scan/{scan_id}/files")
def scan_files(scan_id: str, db: Session = Depends(get_session)):
    records = db.exec(
        select(DriveFileRecord).where(DriveFileRecord.scan_id == scan_id)
    ).all()
    return records


# ---------------------------------------------------------------------------
# Step 1 — Auto-trash duplicates
# ---------------------------------------------------------------------------

@router.post("/duplicates/auto-trash")
def auto_trash_duplicates(
    scan_id: str = Query(...),
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
):
    if account_id:
        token = db.get(DriveToken, account_id)
    else:
        token = _get_token(db)

    service = _build_service(token)

    records = db.exec(
        select(DriveFileRecord).where(
            DriveFileRecord.scan_id == scan_id,
            DriveFileRecord.is_duplicate == 1,
        )
    ).all()

    trashed = 0
    for r in records:
        try:
            service.files().update(fileId=r.drive_file_id, body={"trashed": True}).execute()
            trashed += 1
        except Exception as e:
            logger.warning(f"Could not trash {r.drive_file_id}: {e}")

    return {"trashed": trashed}


# ---------------------------------------------------------------------------
# Step 2 — Flag file
# ---------------------------------------------------------------------------

@router.post("/file/flag")
def flag_file(
    file_id: int = Query(...),
    flag: str = Query(...),
    description: Optional[str] = Query(None),
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
):
    record = db.get(DriveFileRecord, file_id)
    if not record:
        raise HTTPException(404, "File not found")

    record.user_flag = flag
    record.description = description or ""
    if flag == "keep":
        record.is_flagged = 1
    db.add(record)
    db.commit()
    return {"file_record_id": record.id, "flag": flag, "is_protected": flag == "keep"}


# ---------------------------------------------------------------------------
# Step 3 — Organise + deletions
# ---------------------------------------------------------------------------

@router.post("/organise")
def organise_drive(
    scan_id: str = Query(...),
    paradigm: str = Query("type"),
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
):
    from app.services.drive_scanner import DriveScanner
    if account_id:
        token = db.get(DriveToken, account_id)
    else:
        token = _get_token(db)
    scanner = DriveScanner(db, token.user_email)
    result = scanner.organise_by_paradigm(scan_id, paradigm)
    return result


@router.post("/deletion-list/execute")
def execute_deletion(
    scan_id: str = Query(...),
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
):
    if account_id:
        token = db.get(DriveToken, account_id)
    else:
        token = _get_token(db)

    service = _build_service(token)

    records = db.exec(
        select(DriveFileRecord).where(
            DriveFileRecord.scan_id == scan_id,
            DriveFileRecord.user_flag == "delete",
        )
    ).all()

    trashed = 0
    for r in records:
        try:
            service.files().update(fileId=r.drive_file_id, body={"trashed": True}).execute()
            trashed += 1
        except Exception as e:
            logger.warning(f"Could not trash {r.drive_file_id}: {e}")

    return {"trashed": trashed}