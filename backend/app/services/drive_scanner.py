"""
Drive Scanner Service — Phase 2 Cloud Cleanup & Organization.

Step 1  Silent scan + exact-duplicate clustering (NO deletion here)
Step 2  User review gate is driven by the router; scanner exposes helpers
Step 3  Intelligent organization (paradigm priority -> target folder paths)
Step 4  Compression candidates (identification only; encode deferred)
Step 5  Folder creation + batch moves in Drive
Step 6  Deletion execution (soft delete -> Drive trash, 30-day restore)

Only metadata is ever read (name, size, dates, md5, mime). File CONTENT is
never downloaded, and user descriptions are never sent anywhere.
"""

import os
import uuid
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from sqlmodel import Session, select
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

from app.models.gdrive_schemas import (
    DriveToken, DriveScanJob, DriveFileRecord, DriveActionLog, CompressionTask,
)

logger = logging.getLogger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_APPS_PREFIX = "application/vnd.google-apps"
ORGANIZED_ROOT = "Organized"
LARGE_FILE_BYTES = 100 * 1024 * 1024        # 100 MB
ALREADY_COMPRESSED_EXT = (".zip", ".rar", ".7z", ".gz", ".mp4", ".m4v", ".jpg", ".jpeg", ".png", ".webp", ".mp3", ".aac")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _days_since(dt: Optional[datetime]) -> Optional[int]:
    if not dt:
        return None
    now = datetime.now(dt.tzinfo or timezone.utc)
    return (now - dt).days


class DriveScanner:
    def __init__(self, db: Session, token: DriveToken):
        self.db = db
        self.token = token
        self.service = self._build_service()
        self._folder_cache: Dict[str, str] = {}   # path -> folder id

    def _build_service(self):
        creds = Credentials(
            token=self.token.access_token,
            refresh_token=self.token.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        )
        return build("drive", "v3", credentials=creds)

    # ------------------------------------------------------------------
    # STEP 1 — Scan + duplicate clustering (no deletion)
    # ------------------------------------------------------------------
    def run_scan(self, scan_id: str):
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def run_scan(self, scan_id: str):
        """
        Phase A: Pull file list + metadata from Drive.
        Detect exact duplicates (MD5) and near-duplicates (pHash of thumbnails).
        """
        job = self.db.get(DriveScanJob, scan_id)
        if not job:
            logger.error(f"Scan {scan_id} not found")
            return

        try:
            job.status = "scanning"
            job.phase = "Listing files"
            job.processed_files = 0
            self.db.add(job)
            self.db.commit()

            protected_values = self._load_protected_values()
            all_files = [f for f in self._list_drive_files() if f.get("mimeType") != FOLDER_MIME]
            # Phase A.1: Pull file list + metadata
            all_files = self._list_drive_files()
            # Filter out folder MIME type so we only process files
            all_files = [f for f in all_files if f.get("mimeType") != "application/vnd.google-apps.folder"]
            
            job.total_files = len(all_files)
            job.phase = "Detecting duplicates"
            self.db.add(job)
            self.db.commit()

            clusters = self._build_exact_clusters(all_files)
            originals, dupes = self._resolve_cluster_roles(clusters)

            duplicates_found = 0
            deletion_candidates = 0
            bytes_reclaimable = 0

            for f in all_files:
                fid = f["id"]
                size = int(f.get("size", 0) or 0)
                modified = _parse_dt(f.get("modifiedTime"))
                created = _parse_dt(f.get("createdTime"))
                viewed = _parse_dt(f.get("viewedByMeTime"))
                group_id = clusters.get(fid)
                is_dupe = fid in dupes
                is_original = fid in originals

                loc = (f.get("imageMediaMetadata") or {}).get("location") or {}
                category, confidence, bucket = self._classify(
                    f, size, modified, viewed, is_dupe
                )
                protected = self._is_protected(f, protected_values)

                in_deletion = (not protected) and bucket is not None and confidence >= 50 and not is_original
            # Phase A.2: Detect exact duplicates by MD5
            duplicates = self._detect_exact_duplicates(all_files)
            
            # Phase A.3: Detect near-duplicates by pHash
            near_dupes = self._detect_near_duplicates(all_files)

            # Phase A.4: Store file records
            for idx, file_data in enumerate(all_files):
                is_duplicate = file_data["id"] in duplicates
                is_near_dupe = file_data["id"] in near_dupes
                
                # Determine category & default ai reason
                category = "unused"
                ai_reason = "Rarely used or active file. Review to ensure it is still required."
                user_flag = None
                suggested_action = "keep"

                if is_duplicate:
                    category = "duplicate"
                    suggested_action = "trash"
                    user_flag = "delete"
                    ai_reason = "Exact duplicate of another file, safe to delete."
                elif is_near_dupe:
                    category = "duplicate"
                    suggested_action = "trash"
                    user_flag = "delete"
                    ai_reason = "Very similar file detected — consider reviewing."
                else:
                    # Check size
                    size_mb = int(file_data.get("size", 0)) / (1024 * 1024)
                    if size_mb >= 50:
                        category = "large"
                        ai_reason = f"Large file ({size_mb:.1f} MB) taking up substantial space."
                    else:
                        # Check modified time
                        mod_time_str = file_data.get("modifiedTime")
                        if mod_time_str:
                            try:
                                mod_date = datetime.fromisoformat(mod_time_str.replace("Z", "+00:00"))
                                days_old = (datetime.now(mod_date.tzinfo) - mod_date).days
                                if days_old > 365:
                                    category = "old"
                                    ai_reason = f"File has not been modified in {days_old} days. Consider archiving."
                            except Exception:
                                pass
                        
                        # Check screenshot
                        name_lower = file_data["name"].lower()
                        if any(name_lower.startswith(p) for p in ["screenshot", "screen ", "img_", "capture"]):
                            category = "screenshot"
                            ai_reason = "Screenshot file, typically safe to delete if no longer needed."

                # Check if it was trashed silently
                trashed_at = None
                if is_duplicate:
                    trashed_at = datetime.utcnow()

                record = DriveFileRecord(
                    scan_id=scan_id,
                    account_id=self.token.id,
                    drive_id=fid,
                    name=f.get("name", "(unnamed)"),
                    mime_type=f.get("mimeType", ""),
                    size_bytes=size,
                    md5_checksum=f.get("md5Checksum"),
                    created_at=created,
                    modified_at=modified,
                    last_accessed_at=viewed,
                    parent_folder_id=(f.get("parents") or [None])[0],
                    thumbnail_link=f.get("thumbnailLink"),
                    web_view_link=f.get("webViewLink"),
                    location_lat=loc.get("latitude"),
                    location_lon=loc.get("longitude"),
                    capture_date=(f.get("imageMediaMetadata") or {}).get("time"),
                    category=category,
                    duplicate_group_id=group_id,
                    duplicate_group_hash=f.get("md5Checksum") if group_id else None,
                    is_cluster_original=is_original,
                    confidence=confidence,
                    suggested_action="trash" if in_deletion else ("compress" if size > LARGE_FILE_BYTES else "keep"),
                    ai_reason=self._reason(category, size, modified),
                    is_protected=protected,
                    in_deletion_list=in_deletion,
                    deletion_bucket=bucket if in_deletion else None,
                    compressible=self._is_compressible(f, size),
                    drive_id=file_data["id"],
                    name=file_data["name"],
                    mime_type=file_data.get("mimeType", ""),
                    size_bytes=int(file_data.get("size", 0)),
                    md5_checksum=file_data.get("md5Checksum"),
                    created_at=self._parse_date(file_data.get("createdTime")),
                    modified_at=self._parse_date(file_data.get("modifiedTime")),
                    category=category,
                    duplicate_group_hash=file_data.get("md5Checksum") if is_duplicate else None,
                    suggested_action=suggested_action,
                    ai_reason=ai_reason,
                    user_flag=user_flag,
                    is_protected=False,
                    trashed_at=trashed_at
                )
                self.db.add(record)

                if is_dupe:
                    duplicates_found += 1
                if in_deletion:
                    deletion_candidates += 1
                    bytes_reclaimable += size

                job.processed_files += 1
                if job.processed_files % 200 == 0:
                    self.db.add(job)
                    self.db.commit()

                # Commit progress every 20 files
                if idx % 20 == 0:
                    self.db.add(job)
                    self.db.commit()
            
            # Phase A.5: Auto-trash exact duplicates silently
            trashed = self._move_exact_dupes_to_bin(duplicates)
            job.duplicates_found = len(duplicates)
            job.bytes_reclaimable = sum(int(f.get("size", 0)) for f in all_files if f["id"] in duplicates)

            job.duplicates_found = duplicates_found
            job.clusters_found = len(set(v for v in clusters.values()))
            job.deletion_candidates = deletion_candidates
            job.bytes_reclaimable = bytes_reclaimable
            job.status = "done"
            job.phase = "Complete"
            job.finished_at = datetime.utcnow()
            self.db.add(job)
            self.db.commit()
            logger.info(
                f"Scan {scan_id} done: {job.total_files} files, "
                f"{duplicates_found} dupes, {deletion_candidates} deletion candidates"
            )
        except Exception as e:
            logger.exception(f"Scan {scan_id} failed")
            job.status = "error"
            job.error_message = str(e)
            self.db.add(job)
            self.db.commit()

    def _list_drive_files(self, folder_id: str = "root") -> List[Dict]:
        files: List[Dict] = []
        page_token = None
        fields = (
            "nextPageToken, files(id, name, mimeType, size, createdTime, "
            "modifiedTime, viewedByMeTime, md5Checksum, parents, thumbnailLink, "
            "webViewLink, imageMediaMetadata(time, location))"
        )
        try:
            while True:
                results = self.service.files().list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    spaces="drive",
                    fields=fields,
                    pageToken=page_token,
                    pageSize=1000,
                ).execute()
                for f in results.get("files", []):
                    files.append(f)
                    if f.get("mimeType") == FOLDER_MIME:
                        files.extend(self._list_drive_files(f["id"]))
                page_token = results.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as e:
            logger.warning(f"Error listing files under {folder_id}: {e}")
        return files

    def _build_exact_clusters(self, files: List[Dict]) -> Dict[str, str]:
        """Return { file_id -> group_id } for every file that has >=1 md5 twin."""
        by_hash: Dict[str, List[Dict]] = {}
        for f in files:
            md5 = f.get("md5Checksum")
            if md5:
                by_hash.setdefault(md5, []).append(f)
        mapping: Dict[str, str] = {}
        for md5, group in by_hash.items():
            if len(group) > 1:
                gid = f"grp_{md5[:12]}"
                for f in group:
                    mapping[f["id"]] = gid
        return mapping

    def _resolve_cluster_roles(self, clusters: Dict[str, str]) -> Tuple[set, set]:
        """Pick one original (kept) per cluster; the rest are duplicates."""
        # clusters maps file_id -> gid; we need the file objects' modified time.
        # We re-derive using group membership only; original chosen at review time
        # can override, but default original = first seen id per group.
        groups: Dict[str, List[str]] = {}
        for fid, gid in clusters.items():
            groups.setdefault(gid, []).append(fid)
        originals, dupes = set(), set()
        for gid, ids in groups.items():
            originals.add(ids[0])
            for fid in ids[1:]:
                dupes.add(fid)
        return originals, dupes

    def _classify(self, f: Dict, size: int, modified: Optional[datetime],
                  viewed: Optional[datetime], is_dupe: bool) -> Tuple[str, int, Optional[str]]:
        """Return (category, confidence 1-100, deletion_bucket|None)."""
        name = f.get("name", "").lower()
        mime = f.get("mimeType", "")
        days_mod = _days_since(modified) or 0
        days_view = _days_since(viewed) if viewed else None

        if is_dupe:
            return "duplicate", 95, "duplicate_attachments"

        is_screenshot = "screenshot" in name or "screen shot" in name or name.startswith("scr")
        if is_screenshot and days_mod > 90:
            return "screenshot", 80, "old_screenshots"

        never_opened = viewed is None
        if (never_opened and days_mod > 180) or (days_view is not None and days_view > 365):
            bucket = "unused_downloads" if ("download" in name or mime.startswith("application/")) else "near_duplicate"
            return "unused", 85, bucket

        if size > LARGE_FILE_BYTES and days_mod > 180:
            return "large", 55, "large_unused"

        if days_mod > 365:
            return "old", 60, "unused_downloads"

        return "normal", 0, None

    def _is_compressible(self, f: Dict, size: int) -> bool:
        if size <= LARGE_FILE_BYTES:
            return False
        name = f.get("name", "").lower()
        mime = f.get("mimeType", "")
        if mime.startswith(GOOGLE_APPS_PREFIX):
            return False
        if name.endswith(ALREADY_COMPRESSED_EXT):
            return False
        return True

    def _reason(self, category: str, size: int, modified: Optional[datetime]) -> str:
        mb = size / 1e6
        days = _days_since(modified) or 0
        return {
            "duplicate": f"Exact copy of another file — removing saves {mb:.1f} MB.",
            "screenshot": f"Screenshot untouched for {days} days.",
            "unused": f"Not opened in {days} days — strong cleanup candidate.",
            "large": f"Large file ({mb:.0f} MB) idle for {days} days — consider compressing.",
            "old": f"Unchanged for {days} days — likely safe to archive.",
        }.get(category, "")

    def _load_protected_values(self) -> List[str]:
        """Load Phase 1 whitelist keywords (folder/path values), lowercased."""
        try:
            from app.models.schemas import ProtectedRule
            rules = self.db.exec(select(ProtectedRule)).all()
            return [r.value.lower() for r in rules if r.value]
        except Exception:
            return []

    def _is_protected(self, f: Dict, protected_values: List[str]) -> bool:
        name = f.get("name", "").lower()
        return any(v and v in name for v in protected_values)

    # ------------------------------------------------------------------
    # STEP 2 — review gate helper: keep one file, flag the rest of cluster
    # ------------------------------------------------------------------
    def keep_file(self, record_id: int, description: Optional[str],
                  flag: str, location_tag: Optional[str]) -> Dict[str, Any]:
        record = self.db.get(DriveFileRecord, record_id)
        if not record:
            raise ValueError("File record not found")

        record.user_description = description or None
        record.user_flag = flag or "normal"
        record.location_tag = location_tag or None
        record.is_cluster_original = True
        record.is_protected = True
        record.in_deletion_list = False
        record.deletion_bucket = None
        self.db.add(record)

        moved_to_deletion = 0
        if record.duplicate_group_id:
            siblings = self.db.exec(
                select(DriveFileRecord).where(
                    DriveFileRecord.scan_id == record.scan_id,
                    DriveFileRecord.duplicate_group_id == record.duplicate_group_id,
                    DriveFileRecord.id != record.id,
                )
            ).all()
            for s in siblings:
                s.is_cluster_original = False
                if not s.is_protected:
                    s.in_deletion_list = True
                    s.deletion_bucket = s.deletion_bucket or "duplicate_attachments"
                    moved_to_deletion += 1
                self.db.add(s)

        self.db.commit()
        return {"record_id": record.id, "protected": True, "moved_to_deletion": moved_to_deletion}

    # ------------------------------------------------------------------
    # STEP 3 — organization: compute target folder path per file
    # ------------------------------------------------------------------
    def plan_organization(self, scan_id: str, paradigms: List[str]) -> Dict[str, Any]:
        if not paradigms:
            paradigms = ["type"]
        records = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.in_deletion_list == False,  # noqa: E712
            )
        ).all()

        tree: Dict[str, int] = {}
        for r in records:
            path = self._target_path(r, paradigms)
            r.target_folder_path = path
            self.db.add(r)
            tree[path] = tree.get(path, 0) + 1
        self.db.commit()

        folders = [{"path": p, "count": c} for p, c in sorted(tree.items())]
        return {"paradigms": paradigms, "folders": folders, "files_planned": len(records)}

    def _target_path(self, r: DriveFileRecord, paradigms: List[str]) -> str:
        segments = [ORGANIZED_ROOT]
        primary = paradigms[0]
        segments += self._paradigm_segments(r, primary)
        if len(paradigms) > 1:
            segments += self._paradigm_segments(r, paradigms[1])[:1]
        return "/".join(segments)

    def _paradigm_segments(self, r: DriveFileRecord, paradigm: str) -> List[str]:
        if paradigm == "type":
            return self._type_segments(r.mime_type, r.name)
        if paradigm == "category":
            return ["By_Category", self._category_of(r.name, r.mime_type)]
        if paradigm == "time":
            return ["By_Time", self._time_bucket(r.modified_at)]
        if paradigm == "location":
            tag = r.location_tag or ("Geotagged" if r.location_lat else "No_Location")
            return ["By_Location", tag]
        return ["Smart", self._category_of(r.name, r.mime_type)]

    def _type_segments(self, mime: str, name: str) -> List[str]:
        n = name.lower()
        if mime.startswith("image/"):
            sub = "Screenshots" if "screenshot" in n else "Photos"
            return ["By_File_Type", "Images", sub]
        if mime.startswith("video/"):
            return ["By_File_Type", "Videos"]
        if mime.startswith("audio/"):
            return ["By_File_Type", "Audio"]
        if "pdf" in mime:
            return ["By_File_Type", "Documents", "PDF"]
        if "spreadsheet" in mime or "excel" in mime or n.endswith((".csv", ".xlsx")):
            return ["By_File_Type", "Documents", "Sheets"]
        if "document" in mime or "word" in mime or n.endswith((".doc", ".docx", ".txt")):
            return ["By_File_Type", "Documents", "Word"]
        if n.endswith((".py", ".js", ".ts", ".tsx", ".java", ".cpp", ".go", ".rs")):
            return ["By_File_Type", "Code"]
        return ["By_File_Type", "Misc"]

    def _category_of(self, name: str, mime: str) -> str:
        n = name.lower()
        if any(x in n for x in ["screenshot", "photo", "img", "vacation", "family"]):
            return "Personal"
        if any(x in n for x in ["work", "project", "report", "invoice", "business", "deck"]):
            return "Professional"
        if any(x in n for x in ["download", "setup", "installer", ".zip", ".dmg", ".exe"]):
            return "Downloaded"
        if any(x in n for x in ["design", "edit", "render", "mix", "draft"]):
            return "Creative"
        return "Archive"

    def _time_bucket(self, modified: Optional[datetime]) -> str:
        days = _days_since(modified)
        if days is None:
            return "Unknown"
        if days < 30:
            return "Recent_Active"
        if days < 180:
            return "Active_Use"
        if days < 365:
            return "Inactive_Review"
        return "Archive_Historical"

    # ------------------------------------------------------------------
    # STEP 4 — compression candidates (identification only)
    # ------------------------------------------------------------------
    def compression_candidates(self, scan_id: str) -> List[Dict[str, Any]]:
        records = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.compressible == True,   # noqa: E712
                DriveFileRecord.in_deletion_list == False,  # noqa: E712
            )
        ).all()
        out = []
        for r in records:
            ctype = "image_optimize" if r.mime_type.startswith("image/") else (
                "video_encode" if r.mime_type.startswith("video/") else "archive"
            )
            est = int(r.size_bytes * (0.35 if ctype == "video_encode" else 0.5))
            out.append({
                "record_id": r.id,
                "name": r.name,
                "original_size": r.size_bytes,
                "estimated_size": est,
                "compression_type": ctype,
                "savings_pct": round((1 - est / r.size_bytes) * 100) if r.size_bytes else 0,
            })
        return out

    # ------------------------------------------------------------------
    # STEP 5 + 6 — execute: organize (move) and delete (trash)
    # ------------------------------------------------------------------
    def execute_cleanup(self, scan_id: str, do_delete: bool,
                        do_organize: bool, do_compress: bool) -> Dict[str, Any]:
        deleted = moved = folders_created = compressed = 0

        if do_organize:
            folders_created, moved = self._execute_organization(scan_id)

        if do_delete:
            deleted = self._execute_deletions(scan_id)

        if do_compress:
            compressed = self._queue_compression(scan_id)

        protected = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.is_protected == True,  # noqa: E712
            )
        ).all()

        return {
            "deleted": deleted,
            "moved": moved,
            "folders_created": folders_created,
            "compressed_queued": compressed,
            "protected": len(protected),
        }

    def _execute_organization(self, scan_id: str) -> Tuple[int, int]:
        records = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.in_deletion_list == False,  # noqa: E712
                DriveFileRecord.target_folder_path != None,  # noqa: E711
                DriveFileRecord.is_organized == False,  # noqa: E712
            )
        ).all()
        folders_before = len(self._folder_cache)
        moved = 0
        for r in records:
            try:
                leaf_id = self._ensure_folder_path(r.target_folder_path, scan_id)
                prev_parents = r.parent_folder_id or "root"
                self.service.files().update(
                    fileId=r.drive_id,
                    addParents=leaf_id,
                    removeParents=prev_parents,
                    fields="id, parents",
                ).execute()
                r.moved_to_folder = r.target_folder_path
                r.is_organized = True
                self.db.add(r)
                self._log(scan_id, "move", r.drive_id, prev_parents, leaf_id,
                          detail=r.target_folder_path)
                moved += 1
            except HttpError as e:
                logger.warning(f"Move failed for {r.drive_id}: {e}")
        self.db.commit()
        folders_created = len(self._folder_cache) - folders_before
        return folders_created, moved

    def _execute_deletions(self, scan_id: str) -> int:
        records = self.db.exec(
            select(DriveFileRecord).where(
                DriveFileRecord.scan_id == scan_id,
                DriveFileRecord.in_deletion_list == True,  # noqa: E712
                DriveFileRecord.is_protected == False,  # noqa: E712
                DriveFileRecord.trashed_at == None,  # noqa: E711
            )
        ).all()
        deleted = 0
        for r in records:
            try:
                self.service.files().update(
                    fileId=r.drive_id, body={"trashed": True}
                ).execute()
                r.trashed_at = datetime.utcnow()
                self.db.add(r)
                self._log(scan_id, "trash", r.drive_id, detail=r.name)
                deleted += 1
            except HttpError as e:
                logger.warning(f"Trash failed for {r.drive_id}: {e}")
        self.db.commit()
        return deleted

    def _queue_compression(self, scan_id: str) -> int:
        candidates = self.compression_candidates(scan_id)
        for c in candidates:
            self.db.add(CompressionTask(
                scan_id=scan_id,
                source_file_id=str(c["record_id"]),
                name=c["name"],
                compression_type=c["compression_type"],
                original_size=c["original_size"],
                estimated_size=c["estimated_size"],
                status="pending",
            ))
        self.db.commit()
        return len(candidates)

    def _ensure_folder_path(self, path: str, scan_id: str) -> str:
        """Create nested folders as needed, caching ids. Returns leaf folder id."""
        if path in self._folder_cache:
            return self._folder_cache[path]

        parent = "root"
        accum = []
        for segment in path.split("/"):
            accum.append(segment)
            sub_path = "/".join(accum)
            if sub_path in self._folder_cache:
                parent = self._folder_cache[sub_path]
                continue
            folder_id = self._find_folder(segment, parent)
            if not folder_id:
                folder_id = self.service.files().create(
                    body={
                        "name": segment,
                        "mimeType": FOLDER_MIME,
                        "parents": [parent],
                    },
                    fields="id",
                ).execute().get("id")
                self._log(scan_id, "create_folder", folder_id, detail=sub_path)
            self._folder_cache[sub_path] = folder_id
            parent = folder_id
        return parent

    def _find_folder(self, name: str, parent: str) -> Optional[str]:
    def _get_folder_structure(self, groups: Dict, paradigm: str) -> Dict:
        """
        Use AI to suggest folder names and structure.
        For now, use simple heuristics.
        """
        structure = {}
        for group_name, files in groups.items():
            structure[group_name] = {
                "folder_name": group_name,
                "file_ids": [f.drive_id for f in files],
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
                        # Get current parents to remove them
                        file_info = self.service.files().get(
                            fileId=file_id,
                            fields='parents'
                        ).execute()
                        previous_parents = ",".join(file_info.get('parents', []))

                        self.service.files().update(
                            fileId=file_id,
                            addParents=folder_id,
                            removeParents=previous_parents,
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
            safe = name.replace("'", "\\'")
            res = self.service.files().list(
                q=(f"name='{safe}' and mimeType='{FOLDER_MIME}' "
                   f"and '{parent}' in parents and trashed=false"),
                spaces="drive",
                fields="files(id)",
                pageSize=1,
            ).execute()
            files = res.get("files", [])
            return files[0]["id"] if files else None
        except HttpError:
            return None

    def _log(self, scan_id: str, action_type: str, drive_id: Optional[str] = None,
             prev_parents: Optional[str] = None, new_parents: Optional[str] = None,
             detail: Optional[str] = None):
        self.db.add(DriveActionLog(
            scan_id=scan_id,
            account_id=self.token.id,
            action_type=action_type,
            drive_id=drive_id,
            prev_parents=prev_parents,
            new_parents=new_parents,
            detail=detail,
        ))

    # ------------------------------------------------------------------
    # UNDO — reverse the last executed cleanup
    # ------------------------------------------------------------------
    def undo(self, scan_id: str) -> Dict[str, Any]:
        logs = self.db.exec(
            select(DriveActionLog).where(
                DriveActionLog.scan_id == scan_id,
                DriveActionLog.undone == False,  # noqa: E712
            )
        ).all()
        restored = moved_back = 0
        # Reverse chronological so moves undo before their folders are removed.
        for log in sorted(logs, key=lambda x: x.id or 0, reverse=True):
            try:
                if log.action_type == "trash" and log.drive_id:
                    self.service.files().update(
                        fileId=log.drive_id, body={"trashed": False}
                    ).execute()
                    restored += 1
                elif log.action_type == "move" and log.drive_id and log.prev_parents:
                    self.service.files().update(
                        fileId=log.drive_id,
                        addParents=log.prev_parents,
                        removeParents=log.new_parents or "",
                        fields="id, parents",
                    ).execute()
                    moved_back += 1
                log.undone = True
                self.db.add(log)
            except HttpError as e:
                logger.warning(f"Undo failed for {log.drive_id}: {e}")

        # Reset record state
        records = self.db.exec(
            select(DriveFileRecord).where(DriveFileRecord.scan_id == scan_id)
        ).all()
        for r in records:
            r.trashed_at = None
            r.is_organized = False
            r.moved_to_folder = None
            self.db.add(r)
        self.db.commit()
        return {"restored": restored, "moved_back": moved_back}
