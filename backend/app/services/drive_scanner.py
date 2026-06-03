"""
drive_scanner.py  →  backend/app/services/drive_scanner.py

Core Drive scanning service.
Handles: OAuth token refresh, file listing, duplicate detection,
         AI reason generation, Step 2 flag logic, Step 3 organising.

Privacy guarantee (same as Phase 1):
  - Never downloads file CONTENTS
  - Only metadata: name, size, mimeType, md5Checksum, modifiedTime,
    createdTime, imageMediaMetadata (location + date for photos)
  - Thumbnail URLs are passed to frontend — fetched client-side only
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from sqlmodel import Session, select

from app.models.gdrive_schemas import (
    DriveToken, DriveScanJob, DriveFileRecord, DriveFolderRule
)

logger = logging.getLogger(__name__)

# Fields we pull from Drive API — never file contents
DRIVE_FIELDS = (
    "nextPageToken, files("
    "id, name, mimeType, size, md5Checksum, "
    "createdTime, modifiedTime, viewedByMeTime, "
    "parents, thumbnailLink, webViewLink, "
    "imageMediaMetadata(location, time)"
    ")"
)

LARGE_FILE_THRESHOLD = 50 * 1024 * 1024   # 50 MB
OLD_FILE_DAYS = 365                         # 1 year untouched = "old"


class DriveScanner:
    """All Drive operations for a single linked account."""

    def __init__(self, db: Session, account_id: int):
        self.db = db
        self.account_id = account_id
        self.service = self._build_service()

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    def _build_service(self):
        token_row = self.db.get(DriveToken, self.account_id)
        if not token_row:
            raise ValueError(f"No Drive account with id={self.account_id}")

        creds = Credentials(
            token=token_row.access_token,
            refresh_token=token_row.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_row.access_token = creds.token
            token_row.token_expiry = creds.expiry
            self.db.add(token_row)
            self.db.commit()

        return build("drive", "v3", credentials=creds)

    # ------------------------------------------------------------------
    # Step 1 — Full metadata scan + duplicate detection
    # ------------------------------------------------------------------

    def run_scan(self, scan_id: str):
        """
        Background task: list ALL non-trashed Drive files,
        group duplicates by MD5, classify each file, generate AI reasons.
        Updates DriveScanJob row with progress.
        """
        job = self.db.get(DriveScanJob, scan_id)
        job.status = "running"
        self.db.add(job)
        self.db.commit()

        try:
            files = self._list_all_files(job)
            self._detect_duplicates(scan_id, files)
            self._classify_and_reason(scan_id, files, job)

            job.status = "done"
            job.finished_at = datetime.utcnow()
        except Exception as e:
            logger.exception("Drive scan failed")
            job.status = "error"
            job.error_message = str(e)
        finally:
            self.db.add(job)
            self.db.commit()

    def _list_all_files(self, job: DriveScanJob) -> list[dict]:
        """Page through Drive API and save DriveFileRecord rows."""
        all_files = []
        page_token = None
        query = "trashed = false and mimeType != 'application/vnd.google-apps.folder'"

        while True:
            params = {
                "q": query,
                "fields": DRIVE_FIELDS,
                "pageSize": 200,
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }
            if page_token:
                params["pageToken"] = page_token

            resp = self.service.files().list(**params).execute()
            batch = resp.get("files", [])
            all_files.extend(batch)

            # Upsert into DB
            for f in batch:
                record = self._api_file_to_record(f, job.id)
                self.db.add(record)

            job.total_files = len(all_files)
            job.processed_files = len(all_files)
            self.db.add(job)
            self.db.commit()

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return all_files

    def _api_file_to_record(self, f: dict, scan_id: str) -> DriveFileRecord:
        """Convert raw Drive API dict → DriveFileRecord."""
        img_meta = f.get("imageMediaMetadata", {}) or {}
        loc = img_meta.get("location", {}) or {}

        size = int(f.get("size", 0) or 0)
        mod_time = self._parse_dt(f.get("modifiedTime"))
        cre_time = self._parse_dt(f.get("createdTime"))
        acc_time = self._parse_dt(f.get("viewedByMeTime"))

        return DriveFileRecord(
            scan_id=scan_id,
            account_id=self.account_id,
            drive_id=f["id"],
            name=f.get("name", ""),
            mime_type=f.get("mimeType", ""),
            size_bytes=size,
            md5_checksum=f.get("md5Checksum"),
            created_at=cre_time,
            modified_at=mod_time,
            last_accessed_at=acc_time,
            parent_folder_id=(f.get("parents") or [None])[0],
            thumbnail_link=f.get("thumbnailLink"),
            web_view_link=f.get("webViewLink"),
            location_lat=loc.get("latitude"),
            location_lon=loc.get("longitude"),
            capture_date=img_meta.get("time"),
        )

    # ------------------------------------------------------------------
    # Step 1 — Duplicate detection (MD5-based, no content download)
    # ------------------------------------------------------------------

    def _detect_duplicates(self, scan_id: str, files: list[dict]):
        """
        Group files by md5Checksum.
        Files with same MD5 and size = exact duplicates.
        Marks all but the newest as category='duplicate'.
        """
        from collections import defaultdict
        groups: dict[str, list] = defaultdict(list)

        records = self.db.exec(
            select(DriveFileRecord).where(DriveFileRecord.scan_id == scan_id)
        ).all()

        for r in records:
            if r.md5_checksum:
                groups[r.md5_checksum].append(r)

        dup_count = 0
        bytes_reclaimable = 0

        for md5, group in groups.items():
            if len(group) < 2:
                continue

            # Sort: keep newest (most recent modifiedTime)
            group.sort(key=lambda r: r.modified_at or datetime.min, reverse=True)
            keeper = group[0]

            for dup in group[1:]:
                dup.category = "duplicate"
                dup.duplicate_group_hash = md5
                dup.suggested_action = "trash"
                self.db.add(dup)
                dup_count += 1
                bytes_reclaimable += dup.size_bytes

        job = self.db.get(DriveScanJob, scan_id)
        job.duplicates_found = dup_count
        job.bytes_reclaimable = bytes_reclaimable
        self.db.add(job)
        self.db.commit()

    # ------------------------------------------------------------------
    # Classification + AI reasons
    # ------------------------------------------------------------------

    def _classify_and_reason(self, scan_id: str, files: list, job: DriveScanJob):
        """Classify remaining files and attach AI reasons."""
        from app.services.xai_service import get_drive_reason

        records = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.category == None  # noqa: E711
            )
        ).all()

        now = datetime.utcnow()

        for r in records:
            # Large file
            if r.size_bytes > LARGE_FILE_THRESHOLD:
                r.category = "large"
                r.suggested_action = "compress"

            # Old / never-accessed
            elif r.last_accessed_at:
                days_idle = (now - r.last_accessed_at.replace(tzinfo=None)).days
                if days_idle > OLD_FILE_DAYS:
                    r.category = "old"
                    r.suggested_action = "trash"
            elif r.modified_at:
                days_old = (now - r.modified_at.replace(tzinfo=None)).days
                if days_old > OLD_FILE_DAYS:
                    r.category = "old"
                    r.suggested_action = "trash"

            # Screenshot heuristic (name pattern)
            if r.category is None:
                name_lower = r.name.lower()
                if any(x in name_lower for x in ["screenshot", "screen shot", "capture", "snip"]):
                    r.category = "screenshot"
                    r.suggested_action = "trash"

            # Generate AI reason (metadata only, never content)
            if r.category and r.category != "keep":
                try:
                    r.ai_reason = get_drive_reason(
                        filename=r.name,
                        size_mb=round(r.size_bytes / 1024 / 1024, 2),
                        category=r.category or "unused",
                        days_old=(now - (r.modified_at or now).replace(tzinfo=None)).days,
                        mime_type=r.mime_type,
                    )
                except Exception:
                    r.ai_reason = f"This {r.category} file can be cleaned up."

            self.db.add(r)

        self.db.commit()

    # ------------------------------------------------------------------
    # Step 1 AUTO-TRASH duplicates (no user permission needed)
    # ------------------------------------------------------------------

    def auto_trash_duplicates(self, scan_id: str) -> int:
        """
        Moves all category='duplicate' files to Drive Trash.
        Returns count of trashed files.
        No user confirmation needed — duplicates by definition are expendable.
        """
        records = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.category == "duplicate",
                DriveFileRecord.trashed_at == None,  # noqa: E711
            )
        ).all()

        trashed = 0
        for r in records:
            try:
                self.service.files().update(
                    fileId=r.drive_id,
                    body={"trashed": True}
                ).execute()
                r.trashed_at = datetime.utcnow()
                self.db.add(r)
                trashed += 1
            except Exception as e:
                logger.warning(f"Could not trash {r.drive_id}: {e}")

        self.db.commit()
        return trashed

    # ------------------------------------------------------------------
    # Step 2 — User flags a file
    # ------------------------------------------------------------------

    def apply_flag(self, file_record_id: int, flag: str, description: Optional[str]):
        """
        Mark a file as keep/delete/skip.
        If flag='keep' + description provided, protect similar files
        (same capture_date + approximate location).
        """
        r = self.db.get(DriveFileRecord, file_record_id)
        if not r:
            raise ValueError(f"No file record {file_record_id}")

        r.user_flag = flag
        r.user_description = description

        if flag == "keep":
            r.is_protected = True
            r.suggested_action = "keep"

            # Protect similar: same capture date + location cluster
            if r.capture_date or (r.location_lat and r.location_lon):
                self._protect_similar(r)

        elif flag == "delete":
            r.suggested_action = "trash"

        self.db.add(r)
        self.db.commit()
        return r

    def _protect_similar(self, anchor: DriveFileRecord):
        """
        Mark files with same capture_date (or within ~0.01° lat/lon) as protected.
        Privacy: we use only the location METADATA Google already stored — no content.
        """
        candidates = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == anchor.scan_id,
                DriveFileRecord.id != anchor.id,
            )
        ).all()

        protected_count = 0
        for c in candidates:
            match = False

            if anchor.capture_date and c.capture_date:
                # Same day
                match = anchor.capture_date[:10] == c.capture_date[:10]

            if not match and anchor.location_lat and c.location_lat:
                # Within ~1km
                match = (
                    abs(anchor.location_lat - c.location_lat) < 0.01 and
                    abs(anchor.location_lon - c.location_lon) < 0.01
                )

            if match:
                c.is_protected = True
                c.suggested_action = "keep"
                self.db.add(c)
                protected_count += 1

        logger.info(f"Protected {protected_count} similar files near {anchor.name}")
        self.db.commit()

    # ------------------------------------------------------------------
    # Step 3 — Organise: create folders + move files
    # ------------------------------------------------------------------

    def organise_by_paradigm(self, scan_id: str, paradigm: str) -> dict:
        """
        Creates Drive folders and moves files according to the chosen paradigm.
        paradigm options: date | type | personal_professional | usage_age

        Returns summary: {folders_created, files_moved}
        """
        records = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.user_flag != "delete",
                DriveFileRecord.trashed_at == None,  # noqa: E711
                DriveFileRecord.is_protected == True,
            )
        ).all()

        organiser = {
            "date": self._organise_by_date,
            "type": self._organise_by_type,
            "personal_professional": self._organise_by_context,
            "usage_age": self._organise_by_usage_age,
        }.get(paradigm)

        if not organiser:
            raise ValueError(f"Unknown paradigm: {paradigm}")

        folder_cache: dict[str, str] = {}  # folder_name → Drive folder id
        files_moved = 0

        for r in records:
            folder_name = organiser(r)
            if not folder_name:
                continue

            if folder_name not in folder_cache:
                folder_cache[folder_name] = self._get_or_create_folder(folder_name)

            try:
                # Move file to folder
                file = self.service.files().get(
                    fileId=r.drive_id, fields="parents"
                ).execute()
                prev_parents = ",".join(file.get("parents", []))

                self.service.files().update(
                    fileId=r.drive_id,
                    addParents=folder_cache[folder_name],
                    removeParents=prev_parents,
                    fields="id, parents",
                ).execute()

                r.moved_to_folder = folder_name
                self.db.add(r)
                files_moved += 1
            except Exception as e:
                logger.warning(f"Could not move {r.drive_id}: {e}")

        self.db.commit()
        return {"folders_created": len(folder_cache), "files_moved": files_moved}

    def _organise_by_date(self, r: DriveFileRecord) -> Optional[str]:
        dt = r.capture_date or (r.created_at.isoformat() if r.created_at else None)
        if not dt:
            return "Undated"
        year_month = dt[:7]  # "2024-03"
        return f"DECLUTTR/{year_month}"

    def _organise_by_type(self, r: DriveFileRecord) -> Optional[str]:
        mt = r.mime_type
        if mt.startswith("image/"): return "DECLUTTR/Images"
        if mt.startswith("video/"): return "DECLUTTR/Videos"
        if mt.startswith("audio/"): return "DECLUTTR/Audio"
        if "pdf" in mt: return "DECLUTTR/PDFs"
        if "spreadsheet" in mt or "excel" in mt: return "DECLUTTR/Spreadsheets"
        if "document" in mt or "word" in mt: return "DECLUTTR/Documents"
        if "presentation" in mt or "powerpoint" in mt: return "DECLUTTR/Presentations"
        if "zip" in mt or "archive" in mt: return "DECLUTTR/Archives"
        return "DECLUTTR/Other"

    def _organise_by_context(self, r: DriveFileRecord) -> Optional[str]:
        """Heuristic: professional vs personal based on name patterns."""
        name = r.name.lower()
        professional_signals = [
            "invoice", "report", "meeting", "contract", "proposal",
            "budget", "project", "client", "presentation", "resume", "cv"
        ]
        personal_signals = [
            "photo", "selfie", "family", "trip", "vacation", "holiday",
            "birthday", "wedding", "screenshot", "meme", "fun"
        ]

        prof_score = sum(1 for s in professional_signals if s in name)
        pers_score = sum(1 for s in personal_signals if s in name)

        if prof_score > pers_score:
            return "DECLUTTR/Professional"
        elif pers_score > 0:
            return "DECLUTTR/Personal"
        return "DECLUTTR/Downloaded"

    def _organise_by_usage_age(self, r: DriveFileRecord) -> Optional[str]:
        now = datetime.utcnow()
        ref = r.last_accessed_at or r.modified_at
        if not ref:
            return "DECLUTTR/Archive"
        days = (now - ref.replace(tzinfo=None)).days
        if days < 30: return "DECLUTTR/Recent"
        if days < 180: return "DECLUTTR/Last 6 months"
        if days < 365: return "DECLUTTR/Last year"
        return "DECLUTTR/Archive"

    def _get_or_create_folder(self, folder_path: str) -> str:
        """
        Creates nested Drive folders (e.g. 'DECLUTTR/Images') if they don't exist.
        Returns the leaf folder Drive ID.
        """
        parts = folder_path.split("/")
        parent_id = "root"

        for part in parts:
            query = (
                f"name='{part}' and '{parent_id}' in parents "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false"
            )
            results = self.service.files().list(
                q=query, fields="files(id)"
            ).execute()

            existing = results.get("files", [])
            if existing:
                parent_id = existing[0]["id"]
            else:
                folder_meta = {
                    "name": part,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                }
                created = self.service.files().create(
                    body=folder_meta, fields="id"
                ).execute()
                parent_id = created["id"]

        return parent_id

    # ------------------------------------------------------------------
    # Step 3 — Trash approved deletion list
    # ------------------------------------------------------------------

    def execute_deletion_list(self, scan_id: str) -> int:
        """
        Trash all files the user approved (user_flag='delete' OR
        category='duplicate' and not protected).
        Returns count.
        """
        records = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.user_flag == "delete",
                DriveFileRecord.is_protected == False,  # noqa: E712
                DriveFileRecord.trashed_at == None,  # noqa: E711
            )
        ).all()

        trashed = 0
        for r in records:
            try:
                self.service.files().update(
                    fileId=r.drive_id, body={"trashed": True}
                ).execute()
                r.trashed_at = datetime.utcnow()
                self.db.add(r)
                trashed += 1
            except Exception as e:
                logger.warning(f"Could not trash {r.drive_id}: {e}")

        self.db.commit()
        return trashed

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None