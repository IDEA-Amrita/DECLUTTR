import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional

from app.scan_manager import ScanManager
from pydantic import BaseModel
from app.database import get_db  # NOT from database import
from app.services.drive_service import DriveService
from app.services.duplicate_detector import DuplicateDetector
from app.database import FileRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scan", tags=["scan"])


# Pydantic models for request/response
class StartScanRequest(BaseModel):
    user_id: str


class ScanStatusResponse(BaseModel):
    id: str
    status: str
    progress_percent: float
    processed_files: int
    total_files: int
    duplicates_found: int
    near_duplicates_found: int
    error: Optional[str] = None


class DuplicateFile(BaseModel):
    id: str
    name: str
    size: int
    modified_at: Optional[str]
    web_view_link: Optional[str]
    is_flagged: bool


class DuplicateCluster(BaseModel):
    group_id: str
    type: str  # 'exact' or 'near'
    files: list[DuplicateFile]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/start")
async def start_scan(
    request: StartScanRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> dict:
    """
    Start a new scan session.
    Returns scan ID and initial status.
    """
    try:
        # Get user's Google credentials from session/token
        # For now, using a placeholder - you'll replace with your auth logic
        credentials = None  # TODO: Get from request context/session
        
        # Create Drive service
        drive_service = DriveService(credentials)
        
        # Create scan in database
        scan_manager = ScanManager(db, drive_service)
        scan = scan_manager.create_scan(request.user_id)
        
        # Run scan in background
        background_tasks.add_task(scan_manager.run_scan, scan.id)
        
        logger.info(f"Started scan {scan.id} for user {request.user_id}")
        
        return {
            "scan_id": scan.id,
            "status": scan.status,
            "user_id": request.user_id,
            "message": "Scan started. Check status with scan_id."
        }
    
    except Exception as e:
        logger.error(f"Failed to start scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{scan_id}")
async def get_scan_status(
    scan_id: str,
    db: Session = Depends(get_db)
) -> ScanStatusResponse:
    """
    Get current scan status and progress.
    Poll this endpoint to track scanning progress.
    """
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        return ScanStatusResponse(
            id=scan.id,
            status=scan.status,
            progress_percent=scan.progress_percent,
            processed_files=scan.processed_files,
            total_files=scan.total_files,
            duplicates_found=scan.duplicates_found,
            near_duplicates_found=scan.near_duplicates_found,
            error=scan.error_message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/duplicates/{scan_id}")
async def get_duplicates(
    scan_id: str,
    db: Session = Depends(get_db)
) -> list[DuplicateCluster]:
    """
    Get all duplicate clusters for a completed scan.
    Only available when scan.status == "completed".
    """
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        if scan.status != "completed":
            raise HTTPException(status_code=400, detail=f"Scan still {scan.status}")
        
        # Get duplicate clusters from database
        from services.drive_service import DriveService
        drive_service = DriveService()
        scan_manager = ScanManager(db, drive_service)
        clusters = scan_manager.get_duplicate_clusters(scan_id)
        
        # Convert to response format
        return [
            DuplicateCluster(
                group_id=c['group_id'],
                type=c['type'],
                files=[DuplicateFile(**f) for f in c['files']]
            )
            for c in clusters
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flag/{file_id}")
async def flag_file(
    file_id: str,
    keep: bool = True,
    db: Session = Depends(get_db)
) -> dict:
    """
    Flag a file to be kept (not deleted).
    When user marks "Keep this file", other duplicates in cluster are queued for deletion.
    """
    try:
        from services.drive_service import DriveService
        drive_service = DriveService()
        scan_manager = ScanManager(db, drive_service)
        
        success = scan_manager.flag_file(file_id, keep)
        
        if not success:
            raise HTTPException(status_code=404, detail="File not found")
        
        return {
            "file_id": file_id,
            "flagged": keep,
            "message": "File marked to keep" if keep else "File marked for deletion"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to flag file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/{scan_id}")
async def get_scan_summary(
    scan_id: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Get a summary of the scan results.
    Shows breakdown: exact duplicates vs near-duplicates, storage saved, etc.
    """
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        if scan.status != "completed":
            raise HTTPException(status_code=400, detail=f"Scan still {scan.status}")
        
        # Calculate storage statistics
        from database import FileRecord
        duplicate_files = db.query(FileRecord).filter(
            FileRecord.scan_id == scan_id,
            (FileRecord.is_duplicate | FileRecord.is_near_duplicate)
        ).all()
        
        total_dup_size = sum(f.size for f in duplicate_files)
        
        return {
            "scan_id": scan_id,
            "total_files": scan.total_files,
            "duplicates_found": scan.duplicates_found,
            "near_duplicates_found": scan.near_duplicates_found,
            "total_duplicate_files": len(duplicate_files),
            "potential_storage_saved_mb": total_dup_size / (1024 * 1024),
            "status": scan.status,
            "completed_at": scan.updated_at.isoformat() if scan.updated_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))