"""
gdrive_schemas.py
SQLModel tables + Pydantic request/response shapes for the Phase 2
Cloud Cleanup & Organization flow.

Mirrors the existing DECLUTTR SQLModel style.
"""

from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field
import uuid as _uuid


# ---------------------------------------------------------------------------
# DB Tables
# ---------------------------------------------------------------------------

class DriveToken(SQLModel, table=True):
    """Stores OAuth2 tokens per linked Google account."""
    __tablename__ = "drive_token"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    access_token: str
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    linked_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


class DriveScanJob(SQLModel, table=True):
    """Tracks a full Drive metadata scan (async background task)."""
    __tablename__ = "drive_scan_job"

    id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True)
    account_id: int = Field(foreign_key="drive_token.id")
    status: str = Field(default="pending")   # pending | scanning | done | error
    phase: Optional[str] = None              # human-readable phase label
    total_files: int = Field(default=0)
    processed_files: int = Field(default=0)
    duplicates_found: int = Field(default=0)
    clusters_found: int = Field(default=0)
    deletion_candidates: int = Field(default=0)
    bytes_reclaimable: int = Field(default=0)
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


class DriveFileRecord(SQLModel, table=True):
    """One file discovered during a Drive scan."""
    __tablename__ = "drive_file_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: str = Field(foreign_key="drive_scan_job.id", index=True)
    account_id: int = Field(foreign_key="drive_token.id")

    # Google Drive metadata (never file content)
    drive_id: str = Field(index=True)           # Drive file id
    name: str
    mime_type: str = Field(default="")
    size_bytes: int = Field(default=0)
    md5_checksum: Optional[str] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    parent_folder_id: Optional[str] = None
    thumbnail_link: Optional[str] = None
    web_view_link: Optional[str] = None

    # Location metadata (from EXIF only — never file content)
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    capture_date: Optional[str] = None

    # Classification
    category: Optional[str] = None             # duplicate | near_duplicate | large | old | screenshot | unused | normal
    duplicate_group_id: Optional[str] = None   # cluster id shared across a duplicate set
    duplicate_group_hash: Optional[str] = None # md5 group key
    is_cluster_original: bool = False          # the file kept from a duplicate cluster
    suggested_action: Optional[str] = None     # trash | compress | keep | organize
    ai_reason: Optional[str] = None
    confidence: int = Field(default=0)         # 1-100 safe-to-delete confidence

    # User review (Step 2)
    user_flag: Optional[str] = None            # keep_forever | review_later | normal
    user_description: Optional[str] = None     # local-only description
    location_tag: Optional[str] = None
    is_protected: bool = False                 # protected by description / flag / whitelist

    # Deletion list (Step 6)
    in_deletion_list: bool = False
    deletion_bucket: Optional[str] = None      # old_screenshots | duplicate_attachments | unused_downloads | near_duplicate | large_unused

    # Organization (Step 5)
    target_folder_path: Optional[str] = None
    moved_to_folder: Optional[str] = None
    is_organized: bool = False

    # Compression (Step 4)
    compressible: bool = False

    # Outcome
    trashed_at: Optional[datetime] = None


class DriveFolderRule(SQLModel, table=True):
    """User-defined folder organisation rules (Step 3)."""
    __tablename__ = "drive_folder_rule"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="drive_token.id")
    paradigm: str                               # type | category | time | location | smart
    folder_name: str
    match_condition: str                        # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DriveActionLog(SQLModel, table=True):
    """Records every mutating action so a cleanup can be undone (30-day window)."""
    __tablename__ = "drive_action_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: str = Field(index=True)
    account_id: int
    action_type: str                            # trash | move | create_folder
    drive_id: Optional[str] = None              # affected file / folder
    prev_parents: Optional[str] = None          # comma-separated parent ids (for move undo)
    new_parents: Optional[str] = None
    detail: Optional[str] = None
    undone: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CompressionTask(SQLModel, table=True):
    """Tracks a large-file compression task (Step 4)."""
    __tablename__ = "drive_compression_task"

    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: str = Field(index=True)
    source_file_id: str
    name: str
    compression_type: str                       # video_encode | image_optimize | archive
    original_size: int = 0
    estimated_size: int = 0
    compressed_size: int = 0
    status: str = Field(default="pending")      # pending | in_progress | completed | failed | skipped
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Pydantic request / response shapes
# ---------------------------------------------------------------------------

class DriveScanRequest(SQLModel):
    account_id: Optional[int] = None


class DriveKeepRequest(SQLModel):
    """Step 2 — keep ONE file from a cluster, optionally with context."""
    record_id: int
    description: Optional[str] = None
    flag: str = "normal"                        # keep_forever | review_later | normal
    location_tag: Optional[str] = None


class DriveOrganiseRequest(SQLModel):
    """Step 3 — ordered list of paradigms (highest priority first)."""
    paradigms: List[str]                        # ["type", "time", "category", ...]


class DriveDeletionToggleRequest(SQLModel):
    record_id: int
    in_deletion_list: bool


class DriveExecuteRequest(SQLModel):
    do_delete: bool = True
    do_organize: bool = True
    do_compress: bool = False
