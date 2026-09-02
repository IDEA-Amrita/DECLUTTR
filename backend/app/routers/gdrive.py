import os
import logging
from typing import Optional, List, Dict, Any
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select, SQLModel
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import app.database as db_module
from app.models.gdrive_schemas import (
    DriveToken, DriveScanJob, DriveFileRecord, CompressionTask,
    DriveKeepRequest, DriveOrganiseRequest, DriveDeletionToggleRequest, DriveExecuteRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gdrive", tags=["gdrive"])

SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
BACKEND_ORIGIN  = os.getenv("BACKEND_ORIGIN",  "http://localhost:8000")
REDIRECT_URI    = f"{BACKEND_ORIGIN}/api/gdrive/auth/callback"

_flow_store: Dict[str, Flow] = {}


# ---------------------------------------------------------------------------
# DB session dependency — a real SQLModel Session so .exec() works
# ---------------------------------------------------------------------------
def get_db():
    with Session(db_module.engine) as session:
        yield session



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
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI)


def _resolve_token(db: Session, account_id: Optional[int]) -> DriveToken:
    token = db.get(DriveToken, account_id) if account_id else db.exec(select(DriveToken)).first()
    if not token:
        raise HTTPException(404, "Drive not linked. Please link your Google Drive first.")
    return token


def _scanner(db: Session, token: DriveToken):
    from app.services.drive_scanner import DriveScanner
    return DriveScanner(db, token)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@router.get("/auth/url")
def get_auth_url():
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )
    _flow_store[state] = flow
    return {"auth_url": auth_url}


from fastapi.responses import RedirectResponse, HTMLResponse

@router.get("/auth/callback")
def oauth_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    error_html = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Connection Error - Declutter AI</title>
      <style>
        body { background: #0D0D0F; color: #F2F2F3; font-family: system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .card { background: #161618; border: 1px solid #FF4D4D; padding: 40px; border-radius: 16px; text-align: center; max-width: 420px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        h1 { font-size: 20px; color: #FF4D4D; margin: 0 0 10px; }
        p { color: #8A8A96; font-size: 14px; margin: 0; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Authentication Failed</h1>
        <p>Could not connect Google Drive. Please return to the Declutter AI desktop application and try again.</p>
      </div>
    </body>
    </html>
    """

    if state not in _flow_store:
        return HTMLResponse(content=error_html, status_code=400)
    flow = _flow_store.pop(state)
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        logger.error(f"Token fetch failed: {e}")
        return HTMLResponse(content=error_html, status_code=400)

    creds: Credentials = flow.credentials
    try:
        info = build("oauth2", "v2", credentials=creds).userinfo().get().execute()
        email = info.get("email", "unknown@gmail.com")
    except Exception as e:
        logger.error(f"user info failed: {e}")
        return HTMLResponse(content=error_html, status_code=400)

    existing = db.exec(select(DriveToken).where(DriveToken.email == email)).first()
    if existing:
        existing.access_token  = creds.token
        existing.refresh_token = creds.refresh_token or existing.refresh_token
        existing.token_expiry  = creds.expiry
        db.add(existing)
    else:
        db.add(DriveToken(
            email=email,
            access_token=creds.token,
            refresh_token=creds.refresh_token or "",
            token_expiry=creds.expiry,
        ))
    db.commit()

    success_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Google Drive Connected - Declutter AI</title>
      <style>
        body {{ background: #0D0D0F; color: #F2F2F3; font-family: system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .card {{ background: #161618; border: 1px solid #2A2A2E; padding: 40px; border-radius: 16px; text-align: center; max-width: 420px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
        .icon {{ font-size: 48px; margin-bottom: 16px; }}
        h1 {{ font-size: 22px; margin: 0 0 10px; color: #22C55E; font-weight: 600; }}
        p {{ color: #8A8A96; font-size: 14px; margin-bottom: 16px; line-height: 1.5; }}
        .email {{ background: #1C1C20; color: #7B61FF; padding: 6px 12px; border-radius: 20px; font-family: monospace; font-size: 13px; border: 1px solid #2A2A2E; display: inline-block; margin-bottom: 20px; }}
        .btn {{ background: #7B61FF; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="icon">✨</div>
        <h1>Google Drive Connected</h1>
        <div class="email">{email}</div>
        <p>Your Google Drive account has been successfully linked to <strong>Declutter AI</strong>.</p>
        <p>You can close this tab and return to the desktop application.</p>
        <button class="btn" onclick="window.close()">Close Tab</button>
      </div>
      <script>
        setTimeout(function() {{ window.close(); }}, 2500);
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=success_html)


@router.get("/auth/status")
def auth_status(db: Session = Depends(get_db)):
    tokens = db.exec(select(DriveToken)).all()
    return {
        "linked": len(tokens) > 0,
        "email": tokens[0].email if tokens else None,
        "accounts": [{"id": t.id, "email": t.email} for t in tokens],
    }


@router.delete("/auth/unlink")
def unlink_auth(db: Session = Depends(get_db)):
    for t in db.exec(select(DriveToken)).all():
        db.delete(t)
    db.commit()
    return {"unlinked": True}


# ---------------------------------------------------------------------------
# STEP 1 — Scan
# ---------------------------------------------------------------------------
@router.post("/scan")
def start_scan(background_tasks: BackgroundTasks,
               account_id: Optional[int] = Query(None),
               db: Session = Depends(get_db)):
    token = _resolve_token(db, account_id)
    job = DriveScanJob(account_id=token.id)
    db.add(job)
    db.commit()
    db.refresh(job)

    def _run(scan_id: str, token_id: int):
        with Session(db_module.engine) as s:
            from app.services.drive_scanner import DriveScanner
            tok = s.get(DriveToken, token_id)
            DriveScanner(s, tok).run_scan(scan_id)


    background_tasks.add_task(_run, job.id, token.id)
    return {"scan_id": job.id}


@router.get("/scan/{scan_id}/status")
def scan_status(scan_id: str, db: Session = Depends(get_db)):
    job = db.get(DriveScanJob, scan_id)
    if not job:
        raise HTTPException(404, "Scan not found")
    progress = int((job.processed_files / job.total_files) * 100) if job.total_files else (
        100 if job.status == "done" else 0
    )
    return {
        "scan_id": job.id,
        "status": job.status,
        "phase": job.phase,
        "progress": progress,
        "total_files": job.total_files,
        "processed_files": job.processed_files,
        "duplicates_found": job.duplicates_found,
        "clusters_found": job.clusters_found,
        "deletion_candidates": job.deletion_candidates,
        "bytes_reclaimable": job.bytes_reclaimable,
        "error_message": job.error_message,
    }


def _file_dict(r: DriveFileRecord) -> Dict[str, Any]:
    return {
        "id": r.id,
        "drive_id": r.drive_id,
        "name": r.name,
        "mime_type": r.mime_type,
        "size_bytes": r.size_bytes,
        "category": r.category,
        "confidence": r.confidence,
        "duplicate_group_id": r.duplicate_group_id,
        "is_cluster_original": r.is_cluster_original,
        "ai_reason": r.ai_reason,
        "user_flag": r.user_flag,
        "user_description": r.user_description,
        "is_protected": r.is_protected,
        "in_deletion_list": r.in_deletion_list,
        "deletion_bucket": r.deletion_bucket,
        "thumbnail_link": r.thumbnail_link,
        "web_view_link": r.web_view_link,
        "target_folder_path": r.target_folder_path,
        "modified_at": r.modified_at.isoformat() if r.modified_at else None,
    }


@router.get("/scan/{scan_id}/files")
def scan_files(scan_id: str, db: Session = Depends(get_db)):
    records = db.exec(select(DriveFileRecord).where(DriveFileRecord.scan_id == scan_id)).all()
    return [_file_dict(r) for r in records]


# ---------------------------------------------------------------------------
# STEP 2 — Duplicate cluster review
# ---------------------------------------------------------------------------
@router.get("/scan/{scan_id}/clusters")
def get_clusters(scan_id: str, db: Session = Depends(get_db)):
    records = db.exec(
        select(DriveFileRecord).where(
            DriveFileRecord.scan_id == scan_id,
            DriveFileRecord.duplicate_group_id != None,  # noqa: E711
        )
    ).all()
    groups: Dict[str, List[DriveFileRecord]] = defaultdict(list)
    for r in records:
        groups[r.duplicate_group_id].append(r)

    clusters = []
    for gid, files in groups.items():
        files.sort(key=lambda x: (not x.is_cluster_original, x.name))
        clusters.append({
            "group_id": gid,
            "count": len(files),
            "total_bytes": sum(f.size_bytes for f in files),
            "files": [_file_dict(f) for f in files],
        })
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return {"clusters": clusters, "cluster_count": len(clusters)}


@router.post("/scan/{scan_id}/keep")
def keep_file(scan_id: str, req: DriveKeepRequest,
              account_id: Optional[int] = Query(None),
              db: Session = Depends(get_db)):
    token = _resolve_token(db, account_id)
    try:
        return _scanner(db, token).keep_file(
            req.record_id, req.description, req.flag, req.location_tag
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


# ---------------------------------------------------------------------------
# STEP 3 / 5 — Organization planning
# ---------------------------------------------------------------------------
@router.post("/scan/{scan_id}/organise")
def plan_organise(scan_id: str, req: DriveOrganiseRequest,
                  account_id: Optional[int] = Query(None),
                  db: Session = Depends(get_db)):
    token = _resolve_token(db, account_id)
    return _scanner(db, token).plan_organization(scan_id, req.paradigms)


# ---------------------------------------------------------------------------
# STEP 4 — Compression candidates (identification only)
# ---------------------------------------------------------------------------
@router.get("/scan/{scan_id}/compression")
def compression(scan_id: str, account_id: Optional[int] = Query(None),
                db: Session = Depends(get_db)):
    token = _resolve_token(db, account_id)
    candidates = _scanner(db, token).compression_candidates(scan_id)
    total_orig = sum(c["original_size"] for c in candidates)
    total_est = sum(c["estimated_size"] for c in candidates)
    return {
        "candidates": candidates,
        "count": len(candidates),
        "original_bytes": total_orig,
        "estimated_bytes": total_est,
        "savings_bytes": total_orig - total_est,
    }


# ---------------------------------------------------------------------------
# STEP 6 — Deletion list + execution
# ---------------------------------------------------------------------------
_BUCKET_LABELS = {
    "old_screenshots": "Old Screenshots",
    "duplicate_attachments": "Duplicates",
    "unused_downloads": "Unused Downloads",
    "near_duplicate": "Near Duplicates",
    "large_unused": "Large Idle Files",
}


@router.get("/scan/{scan_id}/deletion-list")
def deletion_list(scan_id: str, db: Session = Depends(get_db)):
    all_records = db.exec(
        select(DriveFileRecord).where(DriveFileRecord.scan_id == scan_id)
    ).all()
    del_records = [r for r in all_records if r.in_deletion_list and not r.is_protected]

    buckets: Dict[str, List[DriveFileRecord]] = defaultdict(list)
    for r in del_records:
        buckets[r.deletion_bucket or "near_duplicate"].append(r)

    bucket_out = []
    for key, files in buckets.items():
        bucket_out.append({
            "key": key,
            "label": _BUCKET_LABELS.get(key, key),
            "count": len(files),
            "total_bytes": sum(f.size_bytes for f in files),
            "files": [_file_dict(f) for f in sorted(files, key=lambda x: -x.size_bytes)],
        })
    bucket_out.sort(key=lambda b: b["count"], reverse=True)

    total_bytes = sum(r.size_bytes for r in del_records)
    avg_conf = int(sum(r.confidence for r in del_records) / len(del_records)) if del_records else 0

    excluded_described = sum(1 for r in all_records if r.user_description)
    excluded_protected = sum(1 for r in all_records if r.is_protected)
    excluded_recent = sum(
        1 for r in all_records
        if not r.in_deletion_list and (r.category in (None, "normal"))
    )

    return {
        "total_files": len(del_records),
        "total_bytes": total_bytes,
        "avg_confidence": avg_conf,
        "buckets": bucket_out,
        "excluded": {
            "described": excluded_described,
            "protected": excluded_protected,
            "recent": excluded_recent,
        },
    }


@router.post("/scan/{scan_id}/deletion-list/toggle")
def toggle_deletion(scan_id: str, req: DriveDeletionToggleRequest,
                    db: Session = Depends(get_db)):
    record = db.get(DriveFileRecord, req.record_id)
    if not record or record.scan_id != scan_id:
        raise HTTPException(404, "File not found")
    record.in_deletion_list = req.in_deletion_list
    if not req.in_deletion_list:
        record.deletion_bucket = None
    elif not record.deletion_bucket:
        record.deletion_bucket = record.deletion_bucket or (record.category or "near_duplicate")
    db.add(record)
    db.commit()
    return {"record_id": record.id, "in_deletion_list": record.in_deletion_list}


@router.post("/scan/{scan_id}/execute")
def execute_cleanup(scan_id: str, req: DriveExecuteRequest,
                    account_id: Optional[int] = Query(None),
                    db: Session = Depends(get_db)):
    token = _resolve_token(db, account_id)
    return _scanner(db, token).execute_cleanup(
        scan_id, req.do_delete, req.do_organize, req.do_compress
    )


@router.post("/scan/{scan_id}/undo")
def undo_cleanup(scan_id: str, account_id: Optional[int] = Query(None),
                 db: Session = Depends(get_db)):
    token = _resolve_token(db, account_id)
    return _scanner(db, token).undo(scan_id)

