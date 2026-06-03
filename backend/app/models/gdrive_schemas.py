"""
gdrive_schemas.py
Add these models to your existing backend/app/models/schemas.py
(or import from here and include in the SQLModel metadata)

Mirrors the existing DECLUTTR SQLModel + Pydantic style exactly.
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
    status: str = Field(default="pending")   # pending | running | done | error
    total_files: int = Field(default=0)
    processed_files: int = Field(default=0)
    duplicates_found: int = Field(default=0)
    bytes_reclaimable: int = Field(default=0)
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


class DriveFileRecord(SQLModel, table=True):
    """One file discovered during a Drive scan."""
    __tablename__ = "drive_file_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: str = Field(foreign_key="drive_scan_job.id")
    account_id: int = Field(foreign_key="drive_token.id")

    # Google Drive metadata
    drive_id: str = Field(index=True)           # Drive file id
    name: str
    mime_type: str
    size_bytes: int = Field(default=0)
    md5_checksum: Optional[str] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    parent_folder_id: Optional[str] = None
    thumbnail_link: Optional[str] = None
    web_view_link: Optional[str] = None

    # Location metadata (for photos/videos — never file content)
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    capture_date: Optional[str] = None         # EXIF date from imageMediaMetadata

    # Classification
    category: Optional[str] = None             # duplicate | large | old | unused | screenshot
    duplicate_group_hash: Optional[str] = None # md5 group key
    suggested_action: Optional[str] = None     # trash | compress | keep
    ai_reason: Optional[str] = None

    # User review (Step 2)
    user_flag: Optional[str] = None            # keep | delete | skip
    user_description: Optional[str] = None     # Short description user writes
    is_protected: bool = False

    # Outcome
    trashed_at: Optional[datetime] = None
    moved_to_folder: Optional[str] = None


class DriveFolderRule(SQLModel, table=True):
    """User-defined folder organisation rules (Step 3)."""
    __tablename__ = "drive_folder_rule"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="drive_token.id")
    paradigm: str                               # date | type | personal_professional | usage_age
    folder_name: str
    match_condition: str                        # JSON string — e.g. {"mime_prefix": "image/"}
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Pydantic request / response shapes
# ---------------------------------------------------------------------------

class DriveScanRequest(SQLModel):
    account_id: int

class DriveFileFlag(SQLModel):
    file_id: int                # DriveFileRecord primary key
    flag: str                   # keep | delete | skip
    description: Optional[str] = None

class DriveMoveRequest(SQLModel):
    file_id: str                # Drive file id
    folder_id: str              # destination Drive folder id

class DriveOrganiseRequest(SQLModel):
    account_id: int
    paradigm: str               # date | type | personal_professional | usage_age

class DriveScanStatusResponse(SQLModel):
    scan_id: str
    status: str
    total_files: int
    processed_files: int
    duplicates_found: int
    bytes_reclaimable: int
    error_message: Optional[str] = None

class DriveFileResponse(SQLModel):
    id: int
    drive_id: str
    name: str
    mime_type: str
    size_bytes: int
    category: Optional[str]
    duplicate_group_hash: Optional[str]
    suggested_action: Optional[str]
    ai_reason: Optional[str]
    user_flag: Optional[str]
    user_description: Optional[str]
    thumbnail_link: Optional[str]
    web_view_link: Optional[str]
    capture_date: Optional[str]
    modified_at: Optional[datetime]
    is_protected: bool