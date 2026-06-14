"""
Drive Scanner Service
Phases A-E: Duplicate detection → Flagging → Organization → Compression → Deletion
"""

import hashlib
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Session, select
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
import os

from app.models.gdrive_schemas import DriveToken, DriveScanJob, DriveFileRecord
from app.services.xai_service import get_drive_reason

logger = logging.getLogger(__name__)

DECLUTTR_FOLDER = "/__DECLUTTR_DUPES__"
PHASE_A_FOLDER = "/__DECLUTTR_ORGANIZED__"


class DriveScanner:
    def __init__(self, db: Session, token: DriveToken):
        self.db = db
        self.token = token
        self.service = self._build_service()

    def _build_service(self):
        """Build Drive API service from token."""
        creds = Credentials(
            token=self.token.access_token,
            refresh_token=self.token.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        )
        return build("drive", "v3", credentials=creds)

    def run_scan(self, scan_id: str):
        """
        Phase A: Pull file list + metadata from Drive.
        Detect exact duplicates (MD5) and near-duplicates (pHash of thumbnails).
        Move dupes to /__DECLUTTR_DUPES__/ folder silently.
        """
        job = self.db.get(DriveScanJob, scan_id)
        if not job:
            logger.error(f"Scan {scan_id} not found")
            return

        try:
            job.status = "scanning"
            job.total_files = 0
            job.processed_files = 0
            self.db.add(job)
            self.db.commit()

            # Phase A.1: Pull file list + metadata
            all_files = self._list_drive_files()
            job.total_files = len(all_files)
            self.db.add(job)
            self.db.commit()

            # Phase A.2: Detect exact duplicates by MD5
            duplicates = self._detect_exact_duplicates(all_files)
            
            # Phase A.3: Detect near-duplicates by pHash
            near_dupes = self._detect_near_duplicates(all_files)

            # Phase A.4: Store file records
            for file_data in all_files:
                is_duplicate = file_data["id"] in duplicates
                is_near_dupe = file_data["id"] in near_dupes
                
                reason = None
                if is_duplicate:
                    reason = "Exact duplicate — safe to remove, saving space."
                elif is_near_dupe:
                    reason = "Very similar file detected — consider reviewing."
                
                record = DriveFileRecord(
                    scan_id=scan_id,
                    drive_file_id=file_data["id"],
                    filename=file_data["name"],
                    mime_type=file_data.get("mimeType", ""),
                    size_bytes=int(file_data.get("size", 0)),
                    created_time=file_data.get("createdTime"),
                    modified_time=file_data.get("modifiedTime"),
                    is_duplicate=1 if is_duplicate else 0,
                    is_near_duplicate=1 if is_near_dupe else 0,
                    reason=reason,
                )
                self.db.add(record)
                job.processed_files += 1
            
            # Phase A.5: Auto-trash exact duplicates silently
            trashed = self._move_exact_dupes_to_bin(duplicates)
            job.duplicates_found = len(duplicates)
            job.bytes_reclaimable = sum(
                f.get("size", 0) for fid, f in zip(
                    [d["id"] for d in all_files], all_files
                ) if fid in duplicates
            )

            job.status = "done"
            self.db.add(job)
            self.db.commit()
            logger.info(f"Scan {scan_id} complete. Duplicates: {len(duplicates)}")

        except Exception as e:
            logger.error(f"Scan {scan_id} failed: {e}")
            job.status = "error"
            job.error_message = str(e)
            self.db.add(job)
            self.db.commit()

    def _list_drive_files(self, folder_id: str = "root") -> List[Dict]:
        """Recursively list all Drive files with metadata (no content download)."""
        files = []
        page_token = None
        
        try:
            while True:
                results = self.service.files().list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    spaces="drive",
                    fields="files(id, name, mimeType, size, createdTime, modifiedTime, md5Checksum, parents)",
                    pageToken=page_token,
                    pageSize=1000,
                ).execute()
                
                for file_data in results.get("files", []):
                    files.append(file_data)
                    # Recurse into folders
                    if file_data["mimeType"] == "application/vnd.google-apps.folder":
                        files.extend(self._list_drive_files(file_data["id"]))
                
                page_token = results.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as e:
            logger.warning(f"Error listing files: {e}")
        
        return files

    def _detect_exact_duplicates(self, files: List[Dict]) -> set:
        """
        Phase A.2: Detect exact duplicates by MD5.
        Google Drive provides md5Checksum natively — use that.
        Returns set of file IDs that are duplicates (not the first occurrence).
        """
        hash_map = {}
        duplicates = set()
        
        for file_data in files:
            md5 = file_data.get("md5Checksum")
            if not md5:
                continue  # Skip files without MD5 (e.g., Google Docs)
            
            if md5 not in hash_map:
                hash_map[md5] = []
            hash_map[md5].append(file_data)
        
        # Mark all but the newest as duplicates
        for md5, file_list in hash_map.items():
            if len(file_list) > 1:
                # Sort by modifiedTime, newest first
                file_list.sort(
                    key=lambda f: f.get("modifiedTime", ""), reverse=True
                )
                # All except the first (newest) are duplicates
                for file_data in file_list[1:]:
                    duplicates.add(file_data["id"])
        
        return duplicates

    def _detect_near_duplicates(self, files: List[Dict]) -> set:
        """
        Phase A.3: Detect near-duplicates by pHash of thumbnails.
        For now, returns empty set (can be implemented with PIL + pHash library).
        """
        # TODO: Download thumbnails, compute pHash, cluster by similarity
        return set()

    def _move_exact_dupes_to_bin(self, duplicate_ids: set) -> int:
        """
        Phase A.4: Move duplicate files to Drive Trash (bin).
        Returns count of trashed files.
        """
        trashed = 0
        for file_id in duplicate_ids:
            try:
                self.service.files().update(
                    fileId=file_id,
                    body={"trashed": True}
                ).execute()
                trashed += 1
            except HttpError as e:
                logger.warning(f"Could not trash {file_id}: {e}")
        
        return trashed

    def organise_by_paradigm(self, scan_id: str, paradigm: str) -> Dict[str, Any]:
        """
        Phase C: Smart Organisation.
        Paradigm options:
          - "type": photos / docs / downloads / code
          - "context": personal / professional / downloaded
          - "time": recent / active / archived / dormant
        
        Returns: { folders_created, files_moved }
        """
        records = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.user_flag != "delete",
            )
        ).all()
        
        # Group by paradigm
        groups = self._group_by_paradigm(records, paradigm)
        
        # Get AI folder suggestions
        folder_structure = self._get_folder_structure(groups, paradigm)
        
        # Create folders and move files
        folders_created, files_moved = self._create_and_move_folders(folder_structure)
        
        return {
            "folders_created": folders_created,
            "files_moved": files_moved,
        }

    def _group_by_paradigm(self, records: List[DriveFileRecord], paradigm: str) -> Dict:
        """Group files by the selected paradigm."""
        groups = {}
        
        if paradigm == "type":
            for record in records:
                file_type = self._get_file_type(record.mime_type)
                if file_type not in groups:
                    groups[file_type] = []
                groups[file_type].append(record)
        
        elif paradigm == "context":
            # Simple heuristic: Downloads folder, Personal folder, etc.
            for record in records:
                context = self._infer_context(record.filename)
                if context not in groups:
                    groups[context] = []
                groups[context].append(record)
        
        elif paradigm == "time":
            for record in records:
                time_bucket = self._get_time_bucket(record.modified_time)
                if time_bucket not in groups:
                    groups[time_bucket] = []
                groups[time_bucket].append(record)
        
        return groups

    def _get_file_type(self, mime_type: str) -> str:
        """Infer file type from MIME type."""
        if mime_type.startswith("image/"):
            return "Photos"
        elif mime_type.startswith("video/"):
            return "Videos"
        elif mime_type.startswith("application/pdf"):
            return "Documents"
        elif mime_type.startswith("text/"):
            return "Documents"
        elif mime_type.startswith("application/vnd.google-apps"):
            return "Google Files"
        else:
            return "Other"

    def _infer_context(self, filename: str) -> str:
        """Infer context (personal/professional/downloaded) from filename."""
        lower = filename.lower()
        if any(x in lower for x in ["screenshot", "photo", "personal", "vacation"]):
            return "Personal"
        elif any(x in lower for x in ["work", "project", "report", "business"]):
            return "Professional"
        elif any(x in lower for x in ["download", "zip", "archive"]):
            return "Downloaded"
        else:
            return "Mixed"

    def _get_time_bucket(self, modified_time: str) -> str:
        """Bucket file by modification time."""
        if not modified_time:
            return "Unknown"
        
        try:
            mod_date = datetime.fromisoformat(modified_time.replace("Z", "+00:00"))
            now = datetime.now(mod_date.tzinfo)
            days_old = (now - mod_date).days
            
            if days_old < 30:
                return "Recent (< 1 month)"
            elif days_old < 90:
                return "Active (1-3 months)"
            elif days_old < 365:
                return "Archive (3-12 months)"
            else:
                return "Dormant (> 1 year)"
        except:
            return "Unknown"

    def _get_folder_structure(self, groups: Dict, paradigm: str) -> Dict:
        """
        Use AI to suggest folder names and structure.
        For now, use simple heuristics.
        """
        structure = {}
        for group_name, files in groups.items():
            structure[group_name] = {
                "folder_name": group_name,
                "file_ids": [f.drive_file_id for f in files],
                "count": len(files),
            }
        return structure

    def _create_and_move_folders(self, structure: Dict) -> tuple:
        """Create folders and move files into them."""
        folders_created = 0
        files_moved = 0
        
        for group_name, group_data in structure.items():
            try:
                # Create folder if it doesn't exist
                folder_id = self._get_or_create_folder(group_name)
                folders_created += 1
                
                # Move files into folder
                for file_id in group_data["file_ids"]:
                    try:
                        self.service.files().update(
                            fileId=file_id,
                            addParents=folder_id,
                            removeParents="root",
                            fields="id, parents"
                        ).execute()
                        files_moved += 1
                    except HttpError as e:
                        logger.warning(f"Could not move {file_id}: {e}")
            except Exception as e:
                logger.warning(f"Could not create folder {group_name}: {e}")
        
        return folders_created, files_moved

    def _get_or_create_folder(self, folder_name: str) -> str:
        """Get existing folder or create a new one."""
        # Search for existing folder
        try:
            results = self.service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces="drive",
                fields="files(id)",
                pageSize=1,
            ).execute()
            
            if results.get("files"):
                return results["files"][0]["id"]
        except HttpError:
            pass
        
        # Create new folder
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = self.service.files().create(
            body=file_metadata, fields="id"
        ).execute()
        return folder.get("id")