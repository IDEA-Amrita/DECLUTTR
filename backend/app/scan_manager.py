import logging
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.services.drive_service import DriveService
from app.services.duplicate_detector import DuplicateDetector
from app.config import settings
from app.database import Scan, FileRecord, get_db

logger = logging.getLogger(__name__)


class ScanManager:
    """Orchestrates scanning, duplicate detection, and database operations"""
    
    def __init__(self, db: Session, drive_service: DriveService):
        self.db = db
        self.drive_service = drive_service
        self.detector = DuplicateDetector(drive_service)
    
    def create_scan(self, user_id: str) -> Scan:
        """Create a new scan session"""
        scan_id = str(uuid.uuid4())
        scan = Scan(
            id=scan_id,
            user_id=user_id,
            status="pending",
            created_at=datetime.utcnow()
        )
        self.db.add(scan)
        self.db.commit()
        logger.info(f"Created scan {scan_id} for user {user_id}")
        return scan
    
    def update_scan_progress(self, scan_id: str, processed: int, total: int):
        """Update scan progress"""
        scan = self.db.query(Scan).filter(Scan.id == scan_id).first()
        if scan:
            scan.processed_files = processed
            scan.total_files = total
            scan.progress_percent = (processed / total * 100) if total > 0 else 0
            scan.updated_at = datetime.utcnow()
            self.db.commit()
    
    def run_scan(self, scan_id: str) -> dict:
        """
        Execute the full scan:
        1. List files from Drive
        2. Detect exact duplicates (MD5)
        3. Detect near-duplicates (pHash)
        4. Save results to database
        
        Returns: {
            'success': bool,
            'exact_duplicates': int,
            'near_duplicates': int,
            'total_files': int,
            'error': str (if failed)
        }
        """
        scan = self.db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            return {'success': False, 'error': 'Scan not found'}
        
        try:
            scan.status = "running"
            scan.updated_at = datetime.utcnow()
            self.db.commit()
            
            # Step 1: List all files from Drive
            logger.info(f"Scan {scan_id}: Listing files from Drive")
            files = self.drive_service.list_all_files()
            scan.total_files = len(files)
            self.db.commit()
            
            # Save all files to database
            logger.info(f"Scan {scan_id}: Saving {len(files)} files to database")
            for idx, file in enumerate(files):
                # Skip folders
                if file['mimeType'] == 'application/vnd.google-apps.folder':
                    continue
                
                file_record = FileRecord(
                    id=file['id'],
                    scan_id=scan_id,
                    name=file['name'],
                    size=int(file.get('size', 0)),
                    mime_type=file['mimeType'],
                    md5_hash=file.get('md5Checksum'),
                    created_at=datetime.fromisoformat(file['createdTime'].replace('Z', '+00:00')),
                    modified_at=datetime.fromisoformat(file['modifiedTime'].replace('Z', '+00:00')),
                    web_view_link=file.get('webViewLink')
                )
                self.db.add(file_record)
                
                if (idx + 1) % 100 == 0:
                    self.db.commit()
                    self.update_scan_progress(scan_id, idx + 1, len(files))
                    logger.info(f"Scan {scan_id}: Saved {idx + 1}/{len(files)} files")
            
            self.db.commit()
            
            # Step 2: Find exact duplicates (MD5)
            logger.info(f"Scan {scan_id}: Detecting exact duplicates by MD5")
            files_with_md5 = [f for f in files if f.get('md5Checksum')]
            exact_dups = self.detector.find_exact_duplicates(files_with_md5)
            
            # Mark exact duplicates in database
            exact_dup_count = 0
            for group_id, (md5, dup_files) in enumerate(exact_dups.items()):
                for dup_file in dup_files:
                    file_record = self.db.query(FileRecord).filter(
                        FileRecord.id == dup_file['id']
                    ).first()
                    if file_record:
                        file_record.is_duplicate = True
                        file_record.duplicate_group_id = f"exact_{group_id}"
                        file_record.md5_hash = md5
                        exact_dup_count += 1
            
            self.db.commit()
            logger.info(f"Scan {scan_id}: Found {exact_dup_count} exact duplicate files")
            
            # Step 3: Find near-duplicates (pHash)
            logger.info(f"Scan {scan_id}: Detecting near-duplicates by pHash")
            near_dups = self.detector.find_near_duplicates_phash(files)
            
            # Mark near-duplicates in database
            near_dup_count = 0
            for group_id, (cluster_id, near_dup_files) in enumerate(near_dups.items()):
                for near_dup_file in near_dup_files:
                    file_record = self.db.query(FileRecord).filter(
                        FileRecord.id == near_dup_file['id']
                    ).first()
                    if file_record and not file_record.is_duplicate:  # Don't override exact dups
                        file_record.is_near_duplicate = True
                        file_record.duplicate_group_id = f"near_{group_id}"
                        near_dup_count += 1
            
            self.db.commit()
            logger.info(f"Scan {scan_id}: Found {near_dup_count} near-duplicate files")
            
            # Update final status
            scan.status = "completed"
            scan.duplicates_found = exact_dup_count
            scan.near_duplicates_found = near_dup_count
            scan.progress_percent = 100.0
            scan.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Scan {scan_id}: Completed successfully")
            
            return {
                'success': True,
                'exact_duplicates': exact_dup_count,
                'near_duplicates': near_dup_count,
                'total_files': len(files)
            }
        
        except Exception as e:
            logger.error(f"Scan {scan_id} failed: {e}", exc_info=True)
            scan.status = "failed"
            scan.error_message = str(e)
            scan.updated_at = datetime.utcnow()
            self.db.commit()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_scan_status(self, scan_id: str) -> dict:
        """Get current scan status"""
        scan = self.db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            return {'error': 'Scan not found'}
        
        return {
            'id': scan.id,
            'status': scan.status,
            'progress_percent': scan.progress_percent,
            'processed_files': scan.processed_files,
            'total_files': scan.total_files,
            'duplicates_found': scan.duplicates_found,
            'near_duplicates_found': scan.near_duplicates_found,
            'error': scan.error_message
        }
    
    def get_duplicate_clusters(self, scan_id: str) -> list:
        """Get all duplicate clusters for a scan"""
        duplicate_files = self.db.query(FileRecord).filter(
            FileRecord.scan_id == scan_id,
            FileRecord.is_duplicate | FileRecord.is_near_duplicate
        ).all()
        
        # Group by duplicate_group_id
        clusters = {}
        for file in duplicate_files:
            group_id = file.duplicate_group_id
            if group_id not in clusters:
                clusters[group_id] = {
                    'group_id': group_id,
                    'type': 'exact' if file.is_duplicate else 'near',
                    'files': []
                }
            
            clusters[group_id]['files'].append({
                'id': file.id,
                'name': file.name,
                'size': file.size,
                'modified_at': file.modified_at.isoformat() if file.modified_at else None,
                'web_view_link': file.web_view_link,
                'is_flagged': file.is_flagged
            })
        
        return list(clusters.values())
    
    def flag_file(self, file_id: str, keep: bool = True) -> bool:
        """Mark a file as flagged (to be kept)"""
        file_record = self.db.query(FileRecord).filter(
            FileRecord.id == file_id
        ).first()
        
        if file_record:
            file_record.is_flagged = keep
            self.db.commit()
            logger.info(f"File {file_id} flagged={keep}")
            return True
        
        return False