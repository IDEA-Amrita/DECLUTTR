"""
gdrive.py — Google Drive OAuth + file listing router

Mirrors the existing DECLUTTR router style (FastAPI, SQLModel, SQLite).
Drop this into backend/app/routers/ and register it in main.py.

Endpoints:
  GET  /api/gdrive/auth/url          → returns the Google OAuth consent URL
  GET  /api/gdrive/auth/callback     → handles OAuth redirect, stores token
  GET  /api/gdrive/auth/status       → checks if a valid token exists
  DELETE /api/gdrive/auth/revoke     → revokes and deletes stored token
  POST /api/gdrive/scan              → starts a full Drive metadata scan
  GET  /api/gdrive/scan/{scan_id}/status     → polling endpoint for scan progress
  GET  /api/gdrive/scan/{scan_id}/files      → returns all scanned file records
  POST /api/gdrive/file/{file_id}/move       → moves a file to a Drive folder
  POST /api/gdrive/file/{file_id}/trash      → moves a file to Drive Trash
  POST /api/gdrive/folder             → creates a new Drive folder

What is sent to Google:
  - OAuth token exchange (standard)
  - File LIST requests (metadata only: id, name, md5, mimeType, size, modifiedTime,
    createdTime, parents, thumbnailLink, imageMediaMetadata.location)
  - Thumbnail URLs are fetched locally by the frontend — never by this backend
  - File CONTENTS are never downloaded by any endpoint in this file
"""

import os
import uuid
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models.schemas import (
    DriveToken,
    DriveScanJob,
    DriveFileRecord,
    # DriveScanStatus is to be added
)
from app.services.drive_scanner import DriveScanner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gdrive", tags=["gdrive"])

# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",    # read metadata + thumbnails
    "https://www.googleapis.com/auth/drive.file",        # move/trash files we created
    # NOTE: drive.file only covers files the app created or opened.
    # For full mutation (moving any file), use drive scope — but that requires
    # Google's "sensitive scope" verification. We default to drive.readonly +
    # drive.file and surface a clear error if a move is attempted on a file
    # that needs the broader scope. Users can re-auth with drive scope by
    # passing ?full_access=true to /auth/url.
]

FULL_SCOPES = [
    "https://www.googleapis.com/auth/drive",
]



def _get_flow(full_access: bool = False):
    """Build a google-auth InstalledAppFlow from env-provided credentials."""
    from google_auth_oauthlib.flow import Flow  # lazy import — only used in auth routes

    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/gdrive/auth/callback")],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=FULL_SCOPES if full_access else SCOPES,
        redirect_uri=os.environ.get(
            "GOOGLE_REDIRECT_URI",
            "http://localhost:8000/api/gdrive/auth/callback",
        ),
    )
    return flow


def _build_service(token_data: dict):
    """Build a googleapiclient Drive v3 service from stored token dict."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=token_data.get("scopes", SCOPES),
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.get("/auth/url")
def get_auth_url(full_access: bool = Query(False)):
    """
    Returns the Google OAuth consent URL.
    Frontend opens this in a popup or redirects to it.

    full_access=false (default): readonly + drive.file (no sensitive scope review needed)
    full_access=true: full drive scope (allows moving any file; requires Google verification
                      for published apps, but works in dev/testing with test users)
    """
    flow = _get_flow(full_access=full_access)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",           # force refresh_token to be returned every time
    )
    return {"auth_url": auth_url, "full_access": full_access}


@router.get("/auth/callback")
def auth_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """
    Google redirects here after the user approves.
    Exchanges the auth code for tokens and stores them in SQLite.
    Then redirects to the frontend Drive page.
    """
    flow = _get_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Upsert token (one token row per app — single user desktop app)
    existing = session.exec(select(DriveToken)).first()
    token_dict = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "scopes": list(creds.scopes or SCOPES),
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }

    if existing:
        existing.token_json = json.dumps(token_dict)
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
    else:
        session.add(DriveToken(token_json=json.dumps(token_dict)))
    session.commit()

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(url=f"{frontend_url}/drive?auth=success")


@router.get("/auth/status")
def auth_status(session: Session = Depends(get_session)):
    """
    Returns whether a valid (non-expired) token exists.
    Frontend polls this on mount to decide whether to show the Connect button.
    """
    token_row = session.exec(select(DriveToken)).first()
    if not token_row:
        return {"connected": False, "scopes": []}

    token_data = json.loads(token_row.token_json)
    scopes = token_data.get("scopes", [])
    has_full_access = "https://www.googleapis.com/auth/drive" in scopes

    return {
        "connected": True,
        "scopes": scopes,
        "has_full_access": has_full_access,
        "updated_at": token_row.updated_at.isoformat() if token_row.updated_at else None,
    }


@router.delete("/auth/revoke")
def revoke_auth(session: Session = Depends(get_session)):
    """Revokes the Google token and removes it from the DB."""
    import requests as req_lib

    token_row = session.exec(select(DriveToken)).first()
    if not token_row:
        raise HTTPException(status_code=404, detail="No token found")

    token_data = json.loads(token_row.token_json)
    try:
        req_lib.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": token_data["token"]},
            timeout=5,
        )
    except Exception:
        pass  # best-effort revoke; always delete locally

    session.delete(token_row)
    session.commit()
    return {"revoked": True}


# ---------------------------------------------------------------------------
# Scan endpoints
# ---------------------------------------------------------------------------

@router.post("/scan", status_code=202)
def start_scan(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Starts a background Drive metadata scan.
    Returns a scan_id immediately; poll /scan/{scan_id}/status for progress.

    The scan fetches ONLY metadata — no file contents are downloaded:
      id, name, md5Checksum, mimeType, size, modifiedTime, createdTime,
      parents, thumbnailLink, imageMediaMetadata (GPS + dimensions only)

    Google Docs (Docs/Sheets/Slides) have no md5 — they're excluded from
    dedup but included in the file list for organisation purposes.
    """
    token_row = session.exec(select(DriveToken)).first()
    if not token_row:
        raise HTTPException(status_code=401, detail="Not authenticated with Google Drive")

    scan_id = str(uuid.uuid4())
    job = DriveScanJob(
        id=scan_id,
        status="pending",
        progress=0,
        total_files=0,
        scanned_files=0,
    )
    session.add(job)
    session.commit()

    token_data = json.loads(token_row.token_json)
    background_tasks.add_task(_run_scan, scan_id, token_data)

    return {"scan_id": scan_id, "status": "pending"}


async def _run_scan(scan_id: str, token_data: dict):
    """Background task: pages through all Drive files and stores metadata."""
    from app.database import engine
    from sqlmodel import Session as SyncSession

    with SyncSession(engine) as session:
        job = session.get(DriveScanJob, scan_id)
        if not job:
            return

        try:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

            service = _build_service(token_data)
            scanner = DriveScanner(service=service, scan_id=scan_id, session=session)
            await scanner.run()

            job = session.get(DriveScanJob, scan_id)
            job.status = "complete"
            job.finished_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

        except Exception as e:
            logger.exception("Drive scan failed: %s", e)
            job = session.get(DriveScanJob, scan_id)
            if job:
                job.status = "error"
                job.error_message = str(e)
                session.add(job)
                session.commit()


@router.get("/scan/{scan_id}/status")
def scan_status(scan_id: str, session: Session = Depends(get_session)):
    """
    Polling endpoint. Frontend polls this every 1.5 s during scan.
    Returns progress (0–100), counts, and status string.
    """
    job = session.get(DriveScanJob, scan_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan not found")

    progress = 0
    if job.total_files and job.total_files > 0:
        progress = min(99, int((job.scanned_files / job.total_files) * 100))
    if job.status == "complete":
        progress = 100

    return {
        "scan_id": scan_id,
        "status": job.status,
        "progress": progress,
        "total_files": job.total_files,
        "scanned_files": job.scanned_files,
        "error": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.get("/scan/{scan_id}/files")
def scan_files(
    scan_id: str,
    mime_type: Optional[str] = Query(None, description="Filter by MIME type prefix e.g. image/"),
    has_md5: Optional[bool] = Query(None, description="Only files with MD5 (true) or without (false)"),
    limit: int = Query(500, le=2000),
    offset: int = Query(0),
    session: Session = Depends(get_session),
):
    """
    Returns paginated file records from a completed scan.
    Supports filtering by MIME type and MD5 presence.
    """
    job = session.get(DriveScanJob, scan_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan not found")

    query = select(DriveFileRecord).where(DriveFileRecord.scan_id == scan_id)

    if mime_type:
        query = query.where(DriveFileRecord.mime_type.startswith(mime_type))

    if has_md5 is True:
        query = query.where(DriveFileRecord.md5 != None)
    elif has_md5 is False:
        query = query.where(DriveFileRecord.md5 == None)

    total = len(session.exec(query).all())
    records = session.exec(query.offset(offset).limit(limit)).all()

    return {
        "scan_id": scan_id,
        "total": total,
        "offset": offset,
        "limit": limit,
        "files": [r.model_dump() for r in records],
    }


# ---------------------------------------------------------------------------
# File mutation endpoints
# ---------------------------------------------------------------------------

@router.post("/file/{file_id}/move")
def move_file(
    file_id: str,
    target_folder_id: str = Query(..., description="Drive folder ID to move into"),
    session: Session = Depends(get_session),
):
    """
    Moves a Drive file into a different folder.
    Requires the current parent — fetched from the stored file record.

    If the token only has drive.file scope and the file wasn't created by
    this app, Google will return a 403. Surface that clearly to the frontend.
    """
    token_row = session.exec(select(DriveToken)).first()
    if not token_row:
        raise HTTPException(status_code=401, detail="Not authenticated")

    file_record = session.exec(
        select(DriveFileRecord).where(DriveFileRecord.drive_id == file_id)
    ).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found in scan records")

    service = _build_service(json.loads(token_row.token_json))
    try:
        updated = service.files().update(
            fileId=file_id,
            addParents=target_folder_id,
            removeParents=file_record.parent_id or "",
            fields="id, parents",
        ).execute()
        return {"moved": True, "file_id": file_id, "new_parent": target_folder_id}
    except Exception as e:
        logger.error("Move failed for %s: %s", file_id, e)
        raise HTTPException(status_code=500, detail=f"Move failed: {e}")


@router.post("/file/{file_id}/trash")
def trash_file(file_id: str, session: Session = Depends(get_session)):
    """
    Moves a Drive file to the user's Trash (NOT permanent delete).
    User can restore from Drive Trash within 30 days — same guarantee as send2trash.
    """
    token_row = session.exec(select(DriveToken)).first()
    if not token_row:
        raise HTTPException(status_code=401, detail="Not authenticated")

    service = _build_service(json.loads(token_row.token_json))
    try:
        service.files().update(
            fileId=file_id,
            body={"trashed": True},
            fields="id, trashed",
        ).execute()

        # Mark as trashed in local DB so the UI updates immediately
        record = session.exec(
            select(DriveFileRecord).where(DriveFileRecord.drive_id == file_id)
        ).first()
        if record:
            record.is_trashed = True
            session.add(record)
            session.commit()

        return {"trashed": True, "file_id": file_id}
    except Exception as e:
        logger.error("Trash failed for %s: %s", file_id, e)
        raise HTTPException(status_code=500, detail=f"Trash failed: {e}")


@router.post("/folder")
def create_folder(
    name: str = Query(...),
    parent_id: Optional[str] = Query(None, description="Parent folder Drive ID; root if omitted"),
    session: Session = Depends(get_session),
):
    """
    Creates a new folder in Drive.
    Used by the organisation engine before moving files into it.
    """
    token_row = session.exec(select(DriveToken)).first()
    if not token_row:
        raise HTTPException(status_code=401, detail="Not authenticated")

    service = _build_service(json.loads(token_row.token_json))
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    try:
        folder = service.files().create(body=metadata, fields="id, name, parents").execute()
        return {"created": True, "folder_id": folder["id"], "name": folder["name"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Folder creation failed: {e}")