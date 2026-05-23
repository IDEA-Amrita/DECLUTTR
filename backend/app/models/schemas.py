from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from datetime import datetime


def new_id() -> str:
    return str(uuid.uuid4())


# ── DB Tables ──────────────────────────────────────────────────────────────────

class Suggestion(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    scan_id: str
    type: str  # duplicate|near_duplicate|large_file|old_file|screenshot
    path: str
    size_bytes: int
    last_accessed: int  # epoch seconds
    reason: Optional[str] = None
    confidence: Optional[float] = None
    action: str = "delete"
    consent_given: int = Field(default=0)
    skipped: int = Field(default=0)
    protected: int = Field(default=0)


class ConsentLog(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    suggestion_id: str
    action: str
    confirmed_at: str
    success: int


class ProtectedRule(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    type: str  # folder|path
    value: str
    label: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class WeeklySnapshot(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    week_start: str  # ISO date string e.g. "2026-05-18"
    storage_score: float
    photo_score: float
    composite_score: float
    mb_reclaimed: float
    items_cleared: int


# ── API Shapes (not table=True) ────────────────────────────────────────────────

class ScanRequest(SQLModel):
    directory: str


class ConsentRequest(SQLModel):
    suggestion_id: str
    module: str
    action: str
    confirmed: bool


class ProtectedRuleCreate(SQLModel):
    type: str
    value: str
    label: str


class PhotoScoreRequest(SQLModel):
    directory: str


class FileSuggestionOut(SQLModel):
    id: str
    scan_id: str
    type: str
    path: str
    size_bytes: int
    last_accessed: int
    reason: Optional[str]
    confidence: Optional[float]
    action: str
    consent_given: int
    skipped: int
    protected: int


class PhotoScoreOut(SQLModel):
    path: str
    score: float
    sharpness: float
    brightness: float
    composition: float
    reason: Optional[str]
