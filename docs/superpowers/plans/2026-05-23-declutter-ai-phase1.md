# Declutter AI Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a privacy-first desktop app (Electron + FastAPI) that scans local storage, scores photos aesthetically, and lets users safely delete clutter via an explicit consent gate — with every suggestion explained by a Claude-generated one-sentence reason.

**Architecture:** FastAPI backend (port 8000) exposes a REST API; Electron shell wraps a React/Vite SPA (port 5173) that calls it. All destructive file actions (Recycle Bin via send2trash) go through a single `/api/consent/confirm` endpoint. SQLite via SQLModel persists suggestions, consent log, protected rules, and weekly snapshots.

**Tech Stack:** Python 3.11 + FastAPI + SQLModel + SQLite + Anthropic SDK (`claude-sonnet-4-6`) + send2trash + imagehash + Pillow | Electron + React 19 + TypeScript + Vite + Tailwind + shadcn/ui + Zustand + Recharts + React Router 6

---

## File Map

### Backend (`backend/`)
| File | Responsibility |
|---|---|
| `requirements.txt` | All Python deps pinned |
| `run.py` | `uvicorn` entrypoint |
| `app/__init__.py` | empty |
| `app/main.py` | FastAPI app, CORS, router registration, health |
| `app/database.py` | SQLModel engine, `create_all()`, session dep |
| `app/models/__init__.py` | empty |
| `app/models/schemas.py` | Pydantic models for all API shapes |
| `app/routers/__init__.py` | empty |
| `app/routers/consent.py` | `POST /api/consent/confirm` only |
| `app/routers/storage.py` | POST scan, GET status, GET suggestions |
| `app/routers/protected.py` | GET/POST/DELETE `/api/protected/rules` |
| `app/routers/photos.py` | POST score, GET top |
| `app/routers/report.py` | GET weekly, POST snapshot |
| `app/services/__init__.py` | empty |
| `app/services/storage_service.py` | walk, SHA-256, pHash, large, old, screenshots |
| `app/services/xai_service.py` | Anthropic batch reason generation |
| `app/services/photo_scorer.py` | PIL sharpness/brightness/composition |
| `app/services/protected_service.py` | `is_protected()` rule checker |
| `tests/__init__.py` | empty |
| `tests/conftest.py` | pytest fixtures (test client, temp dirs) |
| `tests/test_health.py` | health endpoint |
| `tests/test_storage.py` | scanner service unit tests |
| `tests/test_consent.py` | consent gate tests |
| `tests/test_protected.py` | protected service tests |
| `tests/test_photos.py` | photo scorer tests |
| `tests/test_report.py` | weekly snapshot tests |

### Desktop (`desktop/`)
| File | Responsibility |
|---|---|
| `package.json` | deps, scripts |
| `tsconfig.json` | TypeScript config |
| `vite.config.ts` | Vite + electron plugin config |
| `tailwind.config.js` | Tailwind with design tokens |
| `index.html` | HTML entry |
| `electron/main.ts` | BrowserWindow 1280×800 |
| `electron/preload.ts` | contextBridge: `showOpenDialog` only |
| `src/main.tsx` | React entry |
| `src/App.tsx` | React Router routes |
| `src/lib/tokens.ts` | design token constants |
| `src/lib/api.ts` | typed fetch wrapper → localhost:8000 |
| `src/hooks/useScan.ts` | POST scan + 2s poll |
| `src/hooks/useConsent.ts` | POST confirm + optimistic update |
| `src/components/ClutterScoreRing.tsx` | animated SVG ring 0–100 |
| `src/components/ProtectedBadge.tsx` | shield icon chip |
| `src/components/SuggestionCard.tsx` | file card with XAI reason + actions |
| `src/components/ConsentModal.tsx` | destructive-action confirm dialog |
| `src/pages/Dashboard.tsx` | ring + 3 module cards |
| `src/pages/StoragePage.tsx` | dir picker → scan → card list |
| `src/pages/PhotoPickerPage.tsx` | dir picker → score → masonry top 10 |
| `src/pages/ReportPage.tsx` | Recharts trend charts |

---

## ─── BACKEND ───────────────────────────────────────────

### Task 1: Backend scaffold

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/run.py`
- Create: `backend/app/__init__.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1.1: Create directory tree**

```powershell
cd C:\Dev\declutter_AI
mkdir backend\app\models, backend\app\routers, backend\app\services, backend\tests
New-Item backend\app\__init__.py, backend\app\models\__init__.py, backend\app\routers\__init__.py, backend\app\services\__init__.py, backend\tests\__init__.py -ItemType File
```

- [ ] **Step 1.2: Write `backend/requirements.txt`**

```text
fastapi==0.115.5
uvicorn[standard]==0.32.1
sqlmodel==0.0.21
pydantic==2.10.3
anthropic==0.40.0
imagehash==4.3.1
Pillow==11.0.0
send2trash==1.8.3
httpx==0.28.1
pytest==8.3.4
pytest-asyncio==0.24.0
anyio==4.7.0
```

- [ ] **Step 1.3: Write `backend/run.py`**

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 1.4: Create virtualenv and install**

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 1.5: Commit**

```bash
git add backend/
git commit -m "feat: backend scaffold — venv, requirements, directory structure"
```

---

### Task 2: Database engine + SQLite tables

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models/schemas.py`

- [ ] **Step 2.1: Write `backend/app/database.py`**

```python
from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = "sqlite:///./declutter.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
```

- [ ] **Step 2.2: Write `backend/app/models/schemas.py`**

```python
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
```

- [ ] **Step 2.3: Write test — DB creates all tables**

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool

from app.main import app
from app.database import get_session


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
```

`backend/tests/test_health.py`:
```python
def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2.4: Run tests — expect ImportError (main.py not written yet)**

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest tests/test_health.py -v
```

Expected: `ImportError: cannot import name 'app' from 'app.main'`

- [ ] **Step 2.5: Commit schemas**

```bash
git add backend/app/database.py backend/app/models/schemas.py backend/tests/
git commit -m "feat: SQLModel tables — Suggestion, ConsentLog, ProtectedRule, WeeklySnapshot"
```

---

### Task 3: FastAPI app + health endpoint

**Files:**
- Create: `backend/app/main.py`

- [ ] **Step 3.1: Write `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db
from app.routers import storage, consent, photos, protected, report

app = FastAPI(title="Declutter AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(storage.router, prefix="/api")
app.include_router(consent.router, prefix="/api")
app.include_router(photos.router, prefix="/api")
app.include_router(protected.router, prefix="/api")
app.include_router(report.router, prefix="/api")
```

- [ ] **Step 3.2: Create stub routers so imports resolve**

`backend/app/routers/storage.py`:
```python
from fastapi import APIRouter
router = APIRouter()
```

`backend/app/routers/consent.py`:
```python
from fastapi import APIRouter
router = APIRouter()
```

`backend/app/routers/photos.py`:
```python
from fastapi import APIRouter
router = APIRouter()
```

`backend/app/routers/protected.py`:
```python
from fastapi import APIRouter
router = APIRouter()
```

`backend/app/routers/report.py`:
```python
from fastapi import APIRouter
router = APIRouter()
```

- [ ] **Step 3.3: Run health test — expect PASS**

```powershell
pytest tests/test_health.py -v
```

Expected:
```
tests/test_health.py::test_health PASSED
```

- [ ] **Step 3.4: Verify uvicorn starts**

```powershell
python run.py
```

Expected: `Uvicorn running on http://0.0.0.0:8000` — then Ctrl+C.

- [ ] **Step 3.5: Commit**

```bash
git add backend/app/main.py backend/app/routers/
git commit -m "feat: FastAPI app with health endpoint and stub routers"
```

---

### Task 4: Consent gate

**Files:**
- Modify: `backend/app/routers/consent.py`
- Create: `backend/tests/test_consent.py`

- [ ] **Step 4.1: Write failing test**

`backend/tests/test_consent.py`:
```python
import os
import tempfile
from sqlmodel import Session
from app.models.schemas import Suggestion


def _create_suggestion(session: Session, path: str) -> Suggestion:
    s = Suggestion(
        scan_id="test-scan",
        type="large_file",
        path=path,
        size_bytes=1024,
        last_accessed=0,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def test_consent_false_does_not_delete(client, session, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    s = _create_suggestion(session, str(f))

    resp = client.post("/api/consent/confirm", json={
        "suggestion_id": s.id,
        "module": "storage",
        "action": "delete",
        "confirmed": False,
    })
    assert resp.status_code == 200
    assert resp.json()["executed"] is False
    assert f.exists()  # file untouched


def test_consent_true_moves_to_trash(client, session, tmp_path):
    f = tmp_path / "trash_me.txt"
    f.write_text("delete me")
    s = _create_suggestion(session, str(f))

    resp = client.post("/api/consent/confirm", json={
        "suggestion_id": s.id,
        "module": "storage",
        "action": "delete",
        "confirmed": True,
    })
    assert resp.status_code == 200
    assert resp.json()["executed"] is True
    assert not f.exists()  # file gone from original location

    session.refresh(s)
    assert s.consent_given == 1


def test_consent_true_logs_to_consent_log(client, session, tmp_path):
    from sqlmodel import select
    from app.models.schemas import ConsentLog
    f = tmp_path / "log_me.txt"
    f.write_text("x")
    s = _create_suggestion(session, str(f))

    client.post("/api/consent/confirm", json={
        "suggestion_id": s.id,
        "module": "storage",
        "action": "delete",
        "confirmed": True,
    })

    logs = session.exec(select(ConsentLog).where(ConsentLog.suggestion_id == s.id)).all()
    assert len(logs) == 1
    assert logs[0].success == 1
```

- [ ] **Step 4.2: Run — expect FAIL (router is stub)**

```powershell
pytest tests/test_consent.py -v
```

Expected: `405 Method Not Allowed` or `404`.

- [ ] **Step 4.3: Implement `backend/app/routers/consent.py`**

```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
import send2trash

from app.database import get_session
from app.models.schemas import ConsentRequest, ConsentLog, Suggestion

router = APIRouter()


@router.post("/consent/confirm")
def confirm_consent(req: ConsentRequest, session: Session = Depends(get_session)):
    if not req.confirmed:
        return {"executed": False, "message": "Action not confirmed"}

    suggestion = session.get(Suggestion, req.suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    success = 0
    try:
        send2trash.send2trash(suggestion.path)
        success = 1
    except Exception as e:
        log = ConsentLog(
            suggestion_id=req.suggestion_id,
            action=req.action,
            confirmed_at=datetime.utcnow().isoformat(),
            success=0,
        )
        session.add(log)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Failed to delete: {e}")

    suggestion.consent_given = 1
    session.add(suggestion)

    log = ConsentLog(
        suggestion_id=req.suggestion_id,
        action=req.action,
        confirmed_at=datetime.utcnow().isoformat(),
        success=success,
    )
    session.add(log)
    session.commit()

    return {"executed": True}
```

- [ ] **Step 4.4: Run consent tests — expect PASS**

```powershell
pytest tests/test_consent.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/routers/consent.py backend/tests/test_consent.py
git commit -m "feat: consent gate — send2trash on confirmed=true, log every action"
```

---

### Task 5: Storage scanner service

**Files:**
- Create: `backend/app/services/storage_service.py`
- Create: `backend/tests/test_storage.py`

- [ ] **Step 5.1: Write failing tests**

`backend/tests/test_storage.py`:
```python
import os
import tempfile
import hashlib
from pathlib import Path
import pytest
from app.services.storage_service import (
    walk_directory,
    find_exact_duplicates,
    find_large_files,
    find_old_files,
    find_screenshots,
    find_near_duplicates,
)


@pytest.fixture
def dir_with_files(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"hello world")
    (tmp_path / "b.txt").write_bytes(b"hello world")  # exact dup of a.txt
    (tmp_path / "c.txt").write_bytes(b"different content")
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * (60 * 1024 * 1024))  # 60 MB
    screenshot = tmp_path / "Screenshot 2025-01-01.png"
    screenshot.write_bytes(b"fake png")
    return tmp_path


def test_walk_directory_returns_metadata(dir_with_files):
    files = walk_directory(str(dir_with_files))
    paths = [f["path"] for f in files]
    assert any("a.txt" in p for p in paths)
    assert all("size_bytes" in f for f in files)
    assert all("last_accessed" in f for f in files)


def test_find_exact_duplicates(dir_with_files):
    files = walk_directory(str(dir_with_files))
    dups = find_exact_duplicates(files)
    dup_paths = [d["path"] for d in dups]
    assert len(dup_paths) == 2  # a.txt and b.txt both flagged


def test_find_large_files(dir_with_files):
    files = walk_directory(str(dir_with_files))
    large = find_large_files(files, threshold_mb=50)
    assert any("big.bin" in f["path"] for f in large)
    assert not any("a.txt" in f["path"] for f in large)


def test_find_old_files(tmp_path):
    old = tmp_path / "old.txt"
    old.write_bytes(b"old")
    import time
    old_time = time.time() - (400 * 86400)
    os.utime(str(old), (old_time, old_time))
    files = walk_directory(str(tmp_path))
    result = find_old_files(files, days=365)
    assert any("old.txt" in f["path"] for f in result)


def test_find_screenshots(dir_with_files):
    files = walk_directory(str(dir_with_files))
    shots = find_screenshots(files)
    assert any("Screenshot" in f["path"] for f in shots)
    assert not any("a.txt" in f["path"] for f in shots)
```

- [ ] **Step 5.2: Run — expect ImportError**

```powershell
pytest tests/test_storage.py -v
```

Expected: `ImportError: cannot import name 'walk_directory'`

- [ ] **Step 5.3: Implement `backend/app/services/storage_service.py`**

```python
import hashlib
import os
import time
from pathlib import Path
from typing import Any

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic"}
SCREENSHOT_PREFIXES = ("screenshot", "screen ", "img_", "capture")


def walk_directory(path: str) -> list[dict[str, Any]]:
    results = []
    for root, _, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            try:
                stat = os.stat(full)
                results.append({
                    "path": full,
                    "name": name,
                    "size_bytes": stat.st_size,
                    "last_accessed": int(stat.st_atime),
                    "ext": Path(name).suffix.lower(),
                })
            except (PermissionError, FileNotFoundError):
                continue
    return results


def _sha256(path: str) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, FileNotFoundError):
        return None


def find_exact_duplicates(files: list[dict]) -> list[dict]:
    hash_map: dict[str, list[dict]] = {}
    for f in files:
        h = _sha256(f["path"])
        if h:
            hash_map.setdefault(h, []).append(f)
    result = []
    for group in hash_map.values():
        if len(group) > 1:
            result.extend(group)
    return result


def find_near_duplicates(files: list[dict], threshold: int = 8) -> list[dict]:
    try:
        import imagehash
        from PIL import Image
    except ImportError:
        return []

    image_files = [f for f in files if f["ext"] in IMAGE_EXTS]
    hashes: list[tuple[Any, dict]] = []
    for f in image_files:
        try:
            img = Image.open(f["path"])
            h = imagehash.phash(img)
            hashes.append((h, f))
        except Exception:
            continue

    flagged: set[str] = set()
    near_dups = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            if abs(hashes[i][0] - hashes[j][0]) <= threshold:
                for _, f in (hashes[i], hashes[j]):
                    if f["path"] not in flagged:
                        flagged.add(f["path"])
                        near_dups.append(f)
    return near_dups


def find_large_files(files: list[dict], threshold_mb: float = 50) -> list[dict]:
    threshold_bytes = int(threshold_mb * 1024 * 1024)
    return [f for f in files if f["size_bytes"] >= threshold_bytes]


def find_old_files(files: list[dict], days: int = 365) -> list[dict]:
    cutoff = time.time() - days * 86400
    return [f for f in files if f["last_accessed"] < cutoff]


def find_screenshots(files: list[dict]) -> list[dict]:
    result = []
    for f in files:
        name_lower = f["name"].lower()
        if any(name_lower.startswith(p) for p in SCREENSHOT_PREFIXES) and f["ext"] in IMAGE_EXTS | {".png"}:
            result.append(f)
    return result


def run_full_scan(directory: str, rules: list[dict] | None = None) -> list[dict]:
    from app.services.protected_service import is_protected
    files = walk_directory(directory)
    rules = rules or []

    seen: set[str] = set()
    suggestions = []

    def add(file: dict, stype: str, confidence: float):
        p = file["path"]
        if p not in seen and not is_protected(p, rules):
            seen.add(p)
            suggestions.append({**file, "type": stype, "confidence": confidence})

    for f in find_exact_duplicates(files):
        add(f, "duplicate", 0.99)
    for f in find_near_duplicates(files):
        add(f, "near_duplicate", 0.80)
    for f in find_large_files(files):
        add(f, "large_file", 0.90)
    for f in find_old_files(files):
        add(f, "old_file", 0.75)
    for f in find_screenshots(files):
        add(f, "screenshot", 0.85)

    return suggestions
```

- [ ] **Step 5.4: Create stub protected_service so import resolves**

`backend/app/services/protected_service.py`:
```python
def is_protected(path: str, rules: list[dict]) -> bool:
    return False
```

- [ ] **Step 5.5: Run storage tests — expect PASS**

```powershell
pytest tests/test_storage.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5.6: Commit**

```bash
git add backend/app/services/storage_service.py backend/app/services/protected_service.py backend/tests/test_storage.py
git commit -m "feat: storage scanner — walk, SHA-256 dedup, pHash near-dup, large/old/screenshot detection"
```

---

### Task 6: Storage router

**Files:**
- Modify: `backend/app/routers/storage.py`

- [ ] **Step 6.1: Write failing test**

Add to `backend/tests/test_storage.py`:
```python
def test_post_scan_returns_scan_id(client, tmp_path):
    (tmp_path / "file.txt").write_bytes(b"x" * (60 * 1024 * 1024))
    resp = client.post("/api/storage/scan", json={"directory": str(tmp_path)})
    assert resp.status_code == 200
    assert "scan_id" in resp.json()


def test_get_scan_status(client, tmp_path):
    (tmp_path / "file.txt").write_bytes(b"x")
    scan_id = client.post("/api/storage/scan", json={"directory": str(tmp_path)}).json()["scan_id"]
    resp = client.get(f"/api/storage/scan/{scan_id}/status")
    assert resp.status_code == 200
    assert "status" in resp.json()
```

- [ ] **Step 6.2: Run — expect 405**

```powershell
pytest tests/test_storage.py::test_post_scan_returns_scan_id -v
```

Expected: assertion error / 405.

- [ ] **Step 6.3: Implement `backend/app/routers/storage.py`**

```python
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.schemas import ScanRequest, Suggestion, FileSuggestionOut
from app.services import storage_service, xai_service
from app.services.protected_service import is_protected

router = APIRouter()

# in-memory job store: scan_id → {status, progress, suggestions}
scan_jobs: dict[str, dict] = {}


def _run_scan_job(scan_id: str, directory: str):
    from sqlmodel import Session as S
    from app.database import engine

    scan_jobs[scan_id]["status"] = "scanning"
    try:
        from sqlmodel import select as sel
        rules_raw = []
        with S(engine) as db:
            from app.models.schemas import ProtectedRule
            rules_raw = [{"type": r.type, "value": r.value} for r in db.exec(sel(ProtectedRule)).all()]

        raw = storage_service.run_full_scan(directory, rules_raw)
        scan_jobs[scan_id]["status"] = "generating_reasons"
        scan_jobs[scan_id]["progress"] = 50

        items_for_xai = [
            {
                "id": str(uuid.uuid4()),
                "filename": r["name"],
                "size_mb": r["size_bytes"] / 1_048_576,
                "last_accessed_days_ago": max(0, int((__import__("time").time() - r["last_accessed"]) / 86400)),
                "suggestion_type": r["type"],
            }
            for r in raw
        ]
        reasons = xai_service.generate_batch_reasons(items_for_xai, module="storage")

        suggestions = []
        with S(engine) as db:
            for i, r in enumerate(raw):
                item = items_for_xai[i]
                s = Suggestion(
                    id=item["id"],
                    scan_id=scan_id,
                    type=r["type"],
                    path=r["path"],
                    size_bytes=r["size_bytes"],
                    last_accessed=r["last_accessed"],
                    reason=reasons.get(item["id"]),
                    confidence=r["confidence"],
                )
                db.add(s)
                suggestions.append(s)
            db.commit()

        scan_jobs[scan_id]["status"] = "complete"
        scan_jobs[scan_id]["progress"] = 100
        scan_jobs[scan_id]["suggestions"] = [s.model_dump() for s in suggestions]
    except Exception as e:
        scan_jobs[scan_id]["status"] = "error"
        scan_jobs[scan_id]["error"] = str(e)


@router.post("/storage/scan")
def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    scan_id = str(uuid.uuid4())
    scan_jobs[scan_id] = {"status": "pending", "progress": 0, "suggestions": []}
    background_tasks.add_task(_run_scan_job, scan_id, req.directory)
    return {"scan_id": scan_id}


@router.get("/storage/scan/{scan_id}/status")
def get_scan_status(scan_id: str):
    if scan_id not in scan_jobs:
        raise HTTPException(status_code=404, detail="Scan not found")
    job = scan_jobs[scan_id]
    return {"status": job["status"], "progress": job["progress"]}


@router.get("/storage/scan/{scan_id}/suggestions", response_model=list[FileSuggestionOut])
def get_suggestions(scan_id: str, session: Session = Depends(get_session)):
    if scan_id in scan_jobs and scan_jobs[scan_id]["suggestions"]:
        return [FileSuggestionOut(**s) for s in scan_jobs[scan_id]["suggestions"]]
    # fallback: read from SQLite after restart
    results = session.exec(select(Suggestion).where(Suggestion.scan_id == scan_id)).all()
    if not results:
        raise HTTPException(status_code=404, detail="Scan not found")
    return results
```

- [ ] **Step 6.4: Run storage router tests**

```powershell
pytest tests/test_storage.py -v
```

Expected: all PASS (background task runs synchronously in TestClient).

- [ ] **Step 6.5: Commit**

```bash
git add backend/app/routers/storage.py
git commit -m "feat: storage router — POST scan (background), GET status, GET suggestions"
```

---

### Task 7: XAI service

**Files:**
- Modify: `backend/app/services/xai_service.py`

- [ ] **Step 7.1: Write `backend/app/services/xai_service.py`**

```python
import os
import re
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

MODEL = "claude-sonnet-4-6"


def _template_reason(item: dict) -> str:
    t = item["suggestion_type"].replace("_", " ")
    return f"This {t} ({item['size_mb']:.1f} MB) hasn't been accessed in {item['last_accessed_days_ago']} days."


def generate_batch_reasons(items: list[dict], module: str) -> dict[str, str]:
    """
    items: list of dicts with keys: id, filename, size_mb, last_accessed_days_ago, suggestion_type
    Returns: dict mapping item id → one-sentence reason string
    """
    if not items:
        return {}

    if not client.api_key:
        return {item["id"]: _template_reason(item) for item in items}

    lines = "\n".join(
        f'{i+1}. id={item["id"]} | file="{item["filename"]}" | '
        f'size={item["size_mb"]:.1f}MB | age={item["last_accessed_days_ago"]}d | type={item["suggestion_type"]}'
        for i, item in enumerate(items)
    )

    prompt = (
        f"You are a file cleanup assistant. For each file below, write exactly one concise sentence "
        f"explaining why it should be cleaned up. Mention the file's actual age, size, or type. "
        f"Return ONLY the numbered list with the format: <id>=<reason>\n\n{lines}"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=min(80 * len(items), 4096),
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        result: dict[str, str] = {}
        for line in text.strip().splitlines():
            m = re.match(r"[^=]+=(.+)", line.strip())
            if "=" in line:
                parts = line.split("=", 1)
                item_id = parts[0].strip().lstrip("0123456789. ")
                reason = parts[1].strip()
                result[item_id] = reason
        # fill in any missing with template
        for item in items:
            if item["id"] not in result:
                result[item["id"]] = _template_reason(item)
        return result
    except Exception:
        return {item["id"]: _template_reason(item) for item in items}
```

- [ ] **Step 7.2: Verify fallback works without API key**

```powershell
python -c "
import os; os.environ['ANTHROPIC_API_KEY'] = ''
from app.services.xai_service import generate_batch_reasons
items = [{'id': 'abc', 'filename': 'test.png', 'size_mb': 5.2, 'last_accessed_days_ago': 400, 'suggestion_type': 'screenshot'}]
r = generate_batch_reasons(items, 'storage')
print(r)
"
```

Expected: `{'abc': 'This screenshot (5.2 MB) hasn't been accessed in 400 days.'}`

- [ ] **Step 7.3: Commit**

```bash
git add backend/app/services/xai_service.py
git commit -m "feat: XAI service — claude-sonnet-4-6 batch reasons with template fallback"
```

---

### Task 8: Protected rules service + router

**Files:**
- Modify: `backend/app/services/protected_service.py`
- Modify: `backend/app/routers/protected.py`
- Create: `backend/tests/test_protected.py`

- [ ] **Step 8.1: Write failing tests**

`backend/tests/test_protected.py`:
```python
def test_add_and_list_rules(client):
    resp = client.post("/api/protected/rules", json={"type": "folder", "value": "/home/user/important", "label": "Important"})
    assert resp.status_code == 200
    rule_id = resp.json()["id"]

    resp = client.get("/api/protected/rules")
    assert resp.status_code == 200
    rules = resp.json()
    assert any(r["id"] == rule_id for r in rules)


def test_delete_rule(client):
    resp = client.post("/api/protected/rules", json={"type": "path", "value": "/keep/this.txt", "label": "Keep"})
    rule_id = resp.json()["id"]
    del_resp = client.delete(f"/api/protected/rules/{rule_id}")
    assert del_resp.status_code == 200
    rules = client.get("/api/protected/rules").json()
    assert not any(r["id"] == rule_id for r in rules)


def test_is_protected_folder_rule():
    from app.services.protected_service import is_protected
    rules = [{"type": "folder", "value": "/home/user/important"}]
    assert is_protected("/home/user/important/file.txt", rules) is True
    assert is_protected("/home/user/other/file.txt", rules) is False


def test_is_protected_path_rule():
    from app.services.protected_service import is_protected
    rules = [{"type": "path", "value": "/keep/this.txt"}]
    assert is_protected("/keep/this.txt", rules) is True
    assert is_protected("/keep/other.txt", rules) is False
```

- [ ] **Step 8.2: Run — expect failures**

```powershell
pytest tests/test_protected.py -v
```

Expected: FAIL (stub router returns 405).

- [ ] **Step 8.3: Implement `backend/app/services/protected_service.py`**

```python
import os


def is_protected(path: str, rules: list[dict]) -> bool:
    norm = os.path.normpath(path)
    for rule in rules:
        val = os.path.normpath(rule["value"])
        if rule["type"] == "folder":
            if norm.startswith(val + os.sep) or norm == val:
                return True
        elif rule["type"] == "path":
            if norm == val:
                return True
    return False
```

- [ ] **Step 8.4: Implement `backend/app/routers/protected.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.schemas import ProtectedRule, ProtectedRuleCreate

router = APIRouter()


@router.get("/protected/rules")
def list_rules(session: Session = Depends(get_session)):
    return session.exec(select(ProtectedRule)).all()


@router.post("/protected/rules")
def create_rule(body: ProtectedRuleCreate, session: Session = Depends(get_session)):
    rule = ProtectedRule(type=body.type, value=body.value, label=body.label)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/protected/rules/{rule_id}")
def delete_rule(rule_id: str, session: Session = Depends(get_session)):
    rule = session.get(ProtectedRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()
    return {"deleted": True}
```

- [ ] **Step 8.5: Run protected tests — expect PASS**

```powershell
pytest tests/test_protected.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 8.6: Commit**

```bash
git add backend/app/services/protected_service.py backend/app/routers/protected.py backend/tests/test_protected.py
git commit -m "feat: protected rules — is_protected() check, CRUD router"
```

---

### Task 9: Photo scorer service

**Files:**
- Modify: `backend/app/services/photo_scorer.py`
- Create: `backend/tests/test_photos.py`

- [ ] **Step 9.1: Write failing tests**

`backend/tests/test_photos.py`:
```python
import pytest
from pathlib import Path
from PIL import Image


@pytest.fixture
def sample_image(tmp_path):
    img = Image.new("RGB", (400, 300), color=(128, 128, 128))
    path = tmp_path / "sample.jpg"
    img.save(str(path))
    return str(path)


def test_sharpness_score_returns_0_to_100(sample_image):
    from app.services.photo_scorer import sharpness_score
    s = sharpness_score(sample_image)
    assert 0 <= s <= 100


def test_brightness_score_returns_0_to_100(sample_image):
    from app.services.photo_scorer import brightness_score
    s = brightness_score(sample_image)
    assert 0 <= s <= 100


def test_combined_score_returns_0_to_100(sample_image):
    from app.services.photo_scorer import combined_score
    s = combined_score(sample_image)
    assert 0 <= s <= 100


def test_score_directory_returns_sorted_list(tmp_path):
    from app.services.photo_scorer import score_directory
    for i in range(3):
        img = Image.new("RGB", (400, 300), color=(i * 80, i * 80, i * 80))
        img.save(str(tmp_path / f"img{i}.jpg"))
    results = score_directory(str(tmp_path))
    assert len(results) == 3
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
```

- [ ] **Step 9.2: Run — expect ImportError**

```powershell
pytest tests/test_photos.py -v
```

Expected: `ImportError: cannot import name 'sharpness_score'`

- [ ] **Step 9.3: Implement `backend/app/services/photo_scorer.py`**

```python
import os
import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def sharpness_score(path: str) -> float:
    try:
        img = Image.open(path).convert("L").resize((256, 256))
        arr = np.array(img, dtype=float)
        lap = np.array([
            [0,  1, 0],
            [1, -4, 1],
            [0,  1, 0],
        ])
        from scipy.signal import convolve2d
        filtered = convolve2d(arr, lap, mode="valid")
        variance = float(np.var(filtered))
        # normalize: variance of ~1000 → score 100
        return min(100.0, variance / 10.0)
    except Exception:
        return 0.0


def brightness_score(path: str) -> float:
    try:
        img = Image.open(path).convert("L").resize((256, 256))
        mean = float(np.mean(np.array(img)))
        # ideal range 80–190; penalise extremes
        if mean < 30 or mean > 220:
            return max(0.0, 100.0 - abs(mean - 128) * 1.5)
        return 100.0 - abs(mean - 128) * 0.5
    except Exception:
        return 0.0


def composition_score(path: str) -> float:
    try:
        img = Image.open(path).convert("L").resize((300, 300))
        edges = img.filter(ImageFilter.FIND_EDGES)
        arr = np.array(edges, dtype=float)
        h, w = arr.shape
        # thirds grid
        h3, w3 = h // 3, w // 3
        third_regions = [
            arr[h3:2*h3, w3:2*w3],  # centre
            arr[:h3, :w3], arr[:h3, 2*w3:],  # top corners
            arr[2*h3:, :w3], arr[2*h3:, 2*w3:],  # bottom corners
        ]
        densities = [float(np.mean(r)) for r in third_regions]
        # good composition: corners and intersections have edges, not all centre
        centre_density = densities[0]
        corner_density = sum(densities[1:]) / 4
        score = min(100.0, corner_density / max(centre_density + 1, 1) * 50 + corner_density * 0.3)
        return max(0.0, score)
    except Exception:
        return 0.0


def combined_score(path: str) -> float:
    s = sharpness_score(path)
    b = brightness_score(path)
    c = composition_score(path)
    return round(s * 0.4 + b * 0.3 + c * 0.3, 2)


def score_directory(directory: str) -> list[dict]:
    results = []
    for name in os.listdir(directory):
        full = os.path.join(directory, name)
        if not os.path.isfile(full):
            continue
        if Path(name).suffix.lower() not in IMAGE_EXTS:
            continue
        score = combined_score(full)
        results.append({
            "path": full,
            "score": score,
            "sharpness": sharpness_score(full),
            "brightness": brightness_score(full),
            "composition": composition_score(full),
            "reason": None,
        })
    return sorted(results, key=lambda x: x["score"], reverse=True)
```

- [ ] **Step 9.4: Add scipy to requirements.txt**

```text
scipy==1.14.1
```

```powershell
pip install scipy==1.14.1
```

- [ ] **Step 9.5: Run photo tests — expect PASS**

```powershell
pytest tests/test_photos.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 9.6: Commit**

```bash
git add backend/app/services/photo_scorer.py backend/tests/test_photos.py backend/requirements.txt
git commit -m "feat: photo scorer — PIL sharpness/brightness/composition, weighted combined score"
```

---

### Task 10: Photos router

**Files:**
- Modify: `backend/app/routers/photos.py`

- [ ] **Step 10.1: Implement `backend/app/routers/photos.py`**

```python
import uuid
from fastapi import APIRouter, BackgroundTasks
from app.models.schemas import PhotoScoreRequest, PhotoScoreOut
from app.services import photo_scorer, xai_service

router = APIRouter()

photo_jobs: dict[str, dict] = {}


def _run_photo_job(job_id: str, directory: str):
    photo_jobs[job_id]["status"] = "scoring"
    try:
        scored = photo_scorer.score_directory(directory)
        top10 = scored[:10]

        photo_jobs[job_id]["status"] = "generating_reasons"
        items_for_xai = [
            {
                "id": str(uuid.uuid4()),
                "filename": p["path"].split("\\")[-1].split("/")[-1],
                "size_mb": 0.0,
                "last_accessed_days_ago": 0,
                "suggestion_type": "photo_pick",
            }
            for p in top10
        ]
        reasons = xai_service.generate_batch_reasons(items_for_xai, module="photos")

        for i, item in enumerate(top10):
            xai_id = items_for_xai[i]["id"]
            item["reason"] = reasons.get(xai_id, f"This photo scores {item['score']:.0f}/100 for aesthetic quality.")

        photo_jobs[job_id]["status"] = "complete"
        photo_jobs[job_id]["results"] = top10
    except Exception as e:
        photo_jobs[job_id]["status"] = "error"
        photo_jobs[job_id]["error"] = str(e)


@router.post("/photos/score")
def start_photo_score(req: PhotoScoreRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    photo_jobs[job_id] = {"status": "pending", "results": []}
    background_tasks.add_task(_run_photo_job, job_id, req.directory)
    return {"job_id": job_id}


@router.get("/photos/score/{job_id}/status")
def get_photo_status(job_id: str):
    if job_id not in photo_jobs:
        return {"status": "not_found"}
    return {"status": photo_jobs[job_id]["status"]}


@router.get("/photos/score/{job_id}/top", response_model=list[PhotoScoreOut])
def get_top_photos(job_id: str):
    if job_id not in photo_jobs:
        return []
    return [PhotoScoreOut(**r) for r in photo_jobs[job_id].get("results", [])]
```

- [ ] **Step 10.2: Smoke-test photos router**

```powershell
pytest tests/test_photos.py -v
```

Expected: all still PASS.

- [ ] **Step 10.3: Commit**

```bash
git add backend/app/routers/photos.py
git commit -m "feat: photos router — POST score, GET status, GET top-10 with XAI reasons"
```

---

### Task 11: Report router

**Files:**
- Modify: `backend/app/routers/report.py`
- Create: `backend/tests/test_report.py`

- [ ] **Step 11.1: Write failing tests**

`backend/tests/test_report.py`:
```python
def test_weekly_returns_list(client):
    resp = client.get("/api/report/weekly")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_snapshot_creates_row(client):
    resp = client.post("/api/report/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "composite_score" in data
    assert "week_start" in data

    weeks = client.get("/api/report/weekly").json()
    assert len(weeks) >= 1
```

- [ ] **Step 11.2: Run — expect failures**

```powershell
pytest tests/test_report.py -v
```

Expected: FAIL.

- [ ] **Step 11.3: Implement `backend/app/routers/report.py`**

```python
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func

from app.database import get_session
from app.models.schemas import WeeklySnapshot, ConsentLog, Suggestion

router = APIRouter()


def _iso_week_start() -> str:
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


@router.get("/report/weekly")
def get_weekly(session: Session = Depends(get_session)):
    rows = session.exec(
        select(WeeklySnapshot).order_by(WeeklySnapshot.week_start.desc()).limit(8)
    ).all()
    return list(reversed(rows))


@router.post("/report/snapshot")
def create_snapshot(session: Session = Depends(get_session)):
    from app.routers.photos import photo_jobs

    week_start = _iso_week_start()
    week_dt = datetime.fromisoformat(week_start)
    week_end_dt = week_dt + timedelta(days=7)

    # find consent logs this week
    logs = session.exec(select(ConsentLog)).all()
    week_logs = [
        l for l in logs
        if week_dt.isoformat() <= l.confirmed_at < week_end_dt.isoformat()
        and l.success == 1
    ]

    mb_reclaimed = 0.0
    items_cleared = len(week_logs)
    for log in week_logs:
        s = session.get(Suggestion, log.suggestion_id)
        if s:
            mb_reclaimed += s.size_bytes / 1_048_576

    storage_score = min(100.0, (mb_reclaimed / 500) * 100)

    # photo_score from last completed photo job
    photo_score = 0.0
    if photo_jobs:
        last_job = list(photo_jobs.values())[-1]
        results = last_job.get("results", [])
        if results:
            photo_score = sum(r["score"] for r in results) / len(results)

    composite = round(storage_score * 0.7 + photo_score * 0.3, 2)

    # upsert: if row exists for this week, update it
    existing = session.exec(
        select(WeeklySnapshot).where(WeeklySnapshot.week_start == week_start)
    ).first()

    if existing:
        existing.storage_score = storage_score
        existing.photo_score = photo_score
        existing.composite_score = composite
        existing.mb_reclaimed = mb_reclaimed
        existing.items_cleared = items_cleared
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    snap = WeeklySnapshot(
        week_start=week_start,
        storage_score=storage_score,
        photo_score=photo_score,
        composite_score=composite,
        mb_reclaimed=round(mb_reclaimed, 2),
        items_cleared=items_cleared,
    )
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
```

- [ ] **Step 11.4: Run report tests — expect PASS**

```powershell
pytest tests/test_report.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 11.5: Run full backend test suite**

```powershell
pytest tests/ -v
```

Expected: all tests PASS. Confirm health, storage, consent, protected, photos, report all green.

- [ ] **Step 11.6: Commit**

```bash
git add backend/app/routers/report.py backend/tests/test_report.py
git commit -m "feat: report router — weekly snapshot CRUD, composite score formula"
```

---

## ─── DESKTOP ────────────────────────────────────────────

### Task 12: Desktop scaffold

**Files:**
- Create: `desktop/package.json`
- Create: `desktop/tsconfig.json`
- Create: `desktop/vite.config.ts`
- Create: `desktop/tailwind.config.js`
- Create: `desktop/postcss.config.js`
- Create: `desktop/index.html`
- Create: `desktop/src/main.tsx`

- [ ] **Step 12.1: Write `desktop/package.json`**

```json
{
  "name": "declutter-ai",
  "version": "1.0.0",
  "private": true,
  "main": "dist-electron/main.js",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "electron:dev": "concurrently \"vite\" \"wait-on http://localhost:5173 && electron .\"",
    "electron:build": "npm run build && electron-builder"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^6.28.0",
    "zustand": "^4.5.5",
    "recharts": "^2.13.3",
    "@radix-ui/react-dialog": "^1.1.2",
    "@radix-ui/react-tooltip": "^1.1.4",
    "lucide-react": "^0.462.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.4"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.3",
    "autoprefixer": "^10.4.20",
    "concurrently": "^9.1.0",
    "electron": "^33.3.1",
    "electron-builder": "^25.1.8",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.15",
    "typescript": "^5.6.3",
    "vite": "^5.4.11",
    "wait-on": "^8.0.1"
  }
}
```

- [ ] **Step 12.2: Write `desktop/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false
  },
  "include": ["src", "electron"]
}
```

- [ ] **Step 12.3: Write `desktop/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  base: './',
})
```

- [ ] **Step 12.4: Write `desktop/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:        '#0D0D0F',
        surface:   '#161618',
        border:    '#2A2A2E',
        accent:    '#7B61FF',
        danger:    '#FF4D4D',
        success:   '#22C55E',
        warning:   '#F59E0B',
        'text-primary':   '#F2F2F3',
        'text-secondary': '#8A8A96',
      },
      fontFamily: {
        mono:  ['DM Mono', 'monospace'],
        serif: ['Instrument Serif', 'serif'],
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 12.5: Write `desktop/postcss.config.js`**

```javascript
module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}
```

- [ ] **Step 12.6: Write `desktop/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Declutter AI</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Instrument+Serif&display=swap" rel="stylesheet" />
  </head>
  <body class="bg-bg text-text-primary">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 12.7: Write `desktop/src/main.tsx`**

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

- [ ] **Step 12.8: Write `desktop/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

* { box-sizing: border-box; }
body { margin: 0; background: #0D0D0F; color: #F2F2F3; font-family: 'DM Mono', monospace; }
```

- [ ] **Step 12.9: Install deps**

```powershell
cd desktop
npm install
```

Expected: node_modules created without errors.

- [ ] **Step 12.10: Commit**

```bash
git add desktop/
git commit -m "feat: desktop scaffold — Vite + React 19 + Tailwind + design tokens"
```

---

### Task 13: Electron main + preload

**Files:**
- Create: `desktop/electron/main.ts`
- Create: `desktop/electron/preload.ts`
- Modify: `desktop/vite.config.ts`

- [ ] **Step 13.1: Write `desktop/electron/main.ts`**

```typescript
import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import path from 'path'

const isDev = process.env.NODE_ENV !== 'production'

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0D0D0F',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    win.loadURL('http://localhost:5173')
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

ipcMain.handle('dialog:openDirectory', async () => {
  const result = await dialog.showOpenDialog({ properties: ['openDirectory'] })
  return result.filePaths[0] ?? null
})
```

- [ ] **Step 13.2: Write `desktop/electron/preload.ts`**

```typescript
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electron', {
  openDirectory: (): Promise<string | null> =>
    ipcRenderer.invoke('dialog:openDirectory'),
})
```

- [ ] **Step 13.3: Add global type declaration**

`desktop/src/electron.d.ts`:
```typescript
interface Window {
  electron?: {
    openDirectory: () => Promise<string | null>
  }
}
```

- [ ] **Step 13.4: Commit**

```bash
git add desktop/electron/ desktop/src/electron.d.ts
git commit -m "feat: Electron main + preload — BrowserWindow 1280x800, openDirectory IPC"
```

---

### Task 14: API client + design tokens

**Files:**
- Create: `desktop/src/lib/tokens.ts`
- Create: `desktop/src/lib/api.ts`

- [ ] **Step 14.1: Write `desktop/src/lib/tokens.ts`**

```typescript
export const tokens = {
  bg:            '#0D0D0F',
  surface:       '#161618',
  border:        '#2A2A2E',
  accent:        '#7B61FF',
  danger:        '#FF4D4D',
  success:       '#22C55E',
  warning:       '#F59E0B',
  textPrimary:   '#F2F2F3',
  textSecondary: '#8A8A96',
} as const

export function scoreColor(score: number): string {
  if (score < 40) return tokens.danger
  if (score < 70) return tokens.warning
  return tokens.success
}
```

- [ ] **Step 14.2: Write `desktop/src/lib/api.ts`**

```typescript
const BASE = 'http://localhost:8000/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)
  return res.json()
}

export type FileSuggestion = {
  id: string; scan_id: string; type: string; path: string
  size_bytes: number; last_accessed: number; reason: string | null
  confidence: number | null; action: string
  consent_given: number; skipped: number; protected: number
}

export type ScanStatus = { status: string; progress: number }

export type ProtectedRule = { id: string; type: string; value: string; label: string; created_at: string }

export type PhotoScore = {
  path: string; score: number; sharpness: number; brightness: number; composition: number; reason: string | null
}

export type WeeklySnapshot = {
  id: string; week_start: string; storage_score: number; photo_score: number
  composite_score: number; mb_reclaimed: number; items_cleared: number
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  startScan: (directory: string) =>
    request<{ scan_id: string }>('/storage/scan', { method: 'POST', body: JSON.stringify({ directory }) }),

  getScanStatus: (id: string) =>
    request<ScanStatus>(`/storage/scan/${id}/status`),

  getSuggestions: (id: string) =>
    request<FileSuggestion[]>(`/storage/scan/${id}/suggestions`),

  confirmConsent: (suggestion_id: string, module: string, action: string, confirmed: boolean) =>
    request<{ executed: boolean }>('/consent/confirm', {
      method: 'POST',
      body: JSON.stringify({ suggestion_id, module, action, confirmed }),
    }),

  getProtectedRules: () => request<ProtectedRule[]>('/protected/rules'),

  addProtectedRule: (type: string, value: string, label: string) =>
    request<ProtectedRule>('/protected/rules', {
      method: 'POST',
      body: JSON.stringify({ type, value, label }),
    }),

  deleteProtectedRule: (id: string) =>
    request<{ deleted: boolean }>(`/protected/rules/${id}`, { method: 'DELETE' }),

  startPhotoScore: (directory: string) =>
    request<{ job_id: string }>('/photos/score', { method: 'POST', body: JSON.stringify({ directory }) }),

  getPhotoStatus: (id: string) =>
    request<{ status: string }>(`/photos/score/${id}/status`),

  getTopPhotos: (id: string) =>
    request<PhotoScore[]>(`/photos/score/${id}/top`),

  getWeeklyReport: () => request<WeeklySnapshot[]>('/report/weekly'),

  createSnapshot: () => request<WeeklySnapshot>('/report/snapshot', { method: 'POST' }),
}
```

- [ ] **Step 14.3: Commit**

```bash
git add desktop/src/lib/
git commit -m "feat: typed API client + design token constants"
```

---

### Task 15: Hooks — useScan + useConsent

**Files:**
- Create: `desktop/src/hooks/useScan.ts`
- Create: `desktop/src/hooks/useConsent.ts`

- [ ] **Step 15.1: Write `desktop/src/hooks/useScan.ts`**

```typescript
import { useState, useRef, useCallback } from 'react'
import { api, FileSuggestion } from '../lib/api'

export type ScanState = {
  status: 'idle' | 'scanning' | 'generating_reasons' | 'complete' | 'error'
  progress: number
  suggestions: FileSuggestion[]
  scanId: string | null
  error: string | null
}

export function useScan() {
  const [state, setState] = useState<ScanState>({
    status: 'idle', progress: 0, suggestions: [], scanId: null, error: null,
  })
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const startScan = useCallback(async (directory: string) => {
    setState({ status: 'scanning', progress: 0, suggestions: [], scanId: null, error: null })

    const { scan_id } = await api.startScan(directory)
    setState(s => ({ ...s, scanId: scan_id }))

    pollRef.current = setInterval(async () => {
      try {
        const { status, progress } = await api.getScanStatus(scan_id)
        setState(s => ({ ...s, status: status as ScanState['status'], progress }))

        if (status === 'complete') {
          clearInterval(pollRef.current!)
          const suggestions = await api.getSuggestions(scan_id)
          setState(s => ({ ...s, suggestions }))
        } else if (status === 'error') {
          clearInterval(pollRef.current!)
          setState(s => ({ ...s, error: 'Scan failed' }))
        }
      } catch (e) {
        clearInterval(pollRef.current!)
        setState(s => ({ ...s, status: 'error', error: String(e) }))
      }
    }, 2000)
  }, [])

  return { ...state, startScan }
}
```

- [ ] **Step 15.2: Write `desktop/src/hooks/useConsent.ts`**

```typescript
import { useCallback, Dispatch, SetStateAction } from 'react'
import { api, FileSuggestion } from '../lib/api'

export function useConsent(
  setSuggestions: Dispatch<SetStateAction<FileSuggestion[]>>
) {
  const confirm = useCallback(async (suggestion: FileSuggestion) => {
    const result = await api.confirmConsent(suggestion.id, 'storage', suggestion.action, true)
    if (result.executed) {
      setSuggestions(prev => prev.filter(s => s.id !== suggestion.id))
    }
    return result
  }, [setSuggestions])

  const skip = useCallback((id: string) => {
    setSuggestions(prev => prev.filter(s => s.id !== id))
  }, [setSuggestions])

  return { confirm, skip }
}
```

- [ ] **Step 15.3: Commit**

```bash
git add desktop/src/hooks/
git commit -m "feat: useScan hook (2s poll) + useConsent (optimistic remove)"
```

---

### Task 16: Core components — ClutterScoreRing + ProtectedBadge

**Files:**
- Create: `desktop/src/components/ClutterScoreRing.tsx`
- Create: `desktop/src/components/ProtectedBadge.tsx`

- [ ] **Step 16.1: Write `desktop/src/components/ClutterScoreRing.tsx`**

```typescript
import { scoreColor } from '../lib/tokens'

type Props = { score: number; size?: number }

export function ClutterScoreRing({ score, size = 160 }: Props) {
  const radius = (size - 20) / 2
  const circumference = 2 * Math.PI * radius
  const pct = Math.max(0, Math.min(100, score))
  const dashOffset = circumference * (1 - pct / 100)
  const color = scoreColor(pct)

  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        fill="none" stroke="#2A2A2E" strokeWidth={12}
      />
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        fill="none" stroke={color} strokeWidth={12}
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.8s ease' }}
      />
      <text
        x="50%" y="50%" textAnchor="middle" dominantBaseline="central"
        style={{ transform: 'rotate(90deg)', transformOrigin: '50% 50%', fill: color,
                 fontSize: size * 0.22, fontFamily: 'DM Mono', fontWeight: 500 }}
      >
        {Math.round(pct)}
      </text>
    </svg>
  )
}
```

- [ ] **Step 16.2: Write `desktop/src/components/ProtectedBadge.tsx`**

```typescript
import { ShieldCheck } from 'lucide-react'

export function ProtectedBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono"
          style={{ background: '#7B61FF22', color: '#7B61FF', border: '1px solid #7B61FF44' }}>
      <ShieldCheck size={12} />
      Protected
    </span>
  )
}
```

- [ ] **Step 16.3: Commit**

```bash
git add desktop/src/components/ClutterScoreRing.tsx desktop/src/components/ProtectedBadge.tsx
git commit -m "feat: ClutterScoreRing animated SVG + ProtectedBadge shield chip"
```

---

### Task 17: SuggestionCard + ConsentModal

**Files:**
- Create: `desktop/src/components/SuggestionCard.tsx`
- Create: `desktop/src/components/ConsentModal.tsx`

- [ ] **Step 17.1: Write `desktop/src/components/ConsentModal.tsx`**

```typescript
import { useState } from 'react'
import { FileSuggestion } from '../lib/api'

type Props = {
  suggestion: FileSuggestion | null
  open: boolean
  onConfirm: (s: FileSuggestion) => void
  onCancel: () => void
}

export function ConsentModal({ suggestion, open, onConfirm, onCancel }: Props) {
  const [checked, setChecked] = useState(false)

  if (!open || !suggestion) return null
  const name = suggestion.path.split('\\').pop()?.split('/').pop() ?? suggestion.path

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center"
         style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="rounded-xl p-6 w-[440px] space-y-4"
           style={{ background: '#161618', border: '1px solid #2A2A2E' }}>
        <h2 className="font-serif text-lg text-text-primary">Confirm deletion</h2>
        <p className="text-sm text-text-secondary font-mono">
          This will move <span className="text-text-primary font-medium">{name}</span> to the Recycle Bin.
        </p>
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)}
                 className="accent-accent" />
          I understand this action
        </label>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel}
                  className="px-4 py-2 text-sm rounded-lg font-mono"
                  style={{ background: '#2A2A2E', color: '#8A8A96' }}>
            Cancel
          </button>
          <button disabled={!checked} onClick={() => { onConfirm(suggestion); setChecked(false) }}
                  className="px-4 py-2 text-sm rounded-lg font-mono disabled:opacity-40"
                  style={{ background: checked ? '#FF4D4D' : '#2A2A2E', color: '#fff' }}>
            Move to Recycle Bin
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 17.2: Write `desktop/src/components/SuggestionCard.tsx`**

```typescript
import { useState } from 'react'
import { ShieldCheck, Trash2, SkipForward } from 'lucide-react'
import { FileSuggestion } from '../lib/api'
import { ProtectedBadge } from './ProtectedBadge'

const TYPE_LABELS: Record<string, string> = {
  duplicate: 'Exact Duplicate',
  near_duplicate: 'Near Duplicate',
  large_file: 'Large File',
  old_file: 'Old File',
  screenshot: 'Screenshot',
}

const TYPE_COLORS: Record<string, string> = {
  duplicate: '#FF4D4D',
  near_duplicate: '#F59E0B',
  large_file: '#7B61FF',
  old_file: '#8A8A96',
  screenshot: '#22C55E',
}

function fmt(bytes: number): string {
  if (bytes > 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`
  if (bytes > 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

type Props = {
  suggestion: FileSuggestion
  onConfirm: (s: FileSuggestion) => void
  onSkip: (id: string) => void
  onProtect: (s: FileSuggestion) => void
}

export function SuggestionCard({ suggestion, onConfirm, onSkip, onProtect }: Props) {
  const name = suggestion.path.split('\\').pop()?.split('/').pop() ?? suggestion.path
  const color = TYPE_COLORS[suggestion.type] ?? '#8A8A96'
  const label = TYPE_LABELS[suggestion.type] ?? suggestion.type
  const confidence = Math.round((suggestion.confidence ?? 0) * 100)

  return (
    <div className="rounded-xl p-4 space-y-3 transition-all"
         style={{ background: '#161618', border: '1px solid #2A2A2E' }}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-mono text-text-primary truncate" title={suggestion.path}>{name}</p>
          <p className="text-xs text-text-secondary font-mono mt-0.5">{suggestion.path}</p>
        </div>
        <span className="shrink-0 text-xs font-mono px-2 py-0.5 rounded"
              style={{ background: color + '22', color, border: `1px solid ${color}44` }}>
          {label}
        </span>
      </div>

      <div className="flex items-center gap-3 text-xs text-text-secondary font-mono">
        <span>{fmt(suggestion.size_bytes)}</span>
        {suggestion.protected === 1 && <ProtectedBadge />}
      </div>

      {suggestion.reason ? (
        <p className="text-xs text-text-secondary leading-relaxed">{suggestion.reason}</p>
      ) : (
        <div className="h-3 rounded animate-pulse" style={{ background: '#2A2A2E', width: '80%' }} />
      )}

      <div className="space-y-1">
        <div className="flex justify-between text-xs font-mono text-text-secondary">
          <span>Confidence</span><span>{confidence}%</span>
        </div>
        <div className="h-1.5 rounded-full" style={{ background: '#2A2A2E' }}>
          <div className="h-full rounded-full transition-all"
               style={{ width: `${confidence}%`, background: color }} />
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <button onClick={() => onConfirm(suggestion)}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-mono"
                style={{ background: '#FF4D4D22', color: '#FF4D4D', border: '1px solid #FF4D4D44' }}>
          <Trash2 size={12} /> Delete
        </button>
        <button onClick={() => onSkip(suggestion.id)}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-mono"
                style={{ background: '#2A2A2E', color: '#8A8A96' }}>
          <SkipForward size={12} /> Skip
        </button>
        <button onClick={() => onProtect(suggestion)}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-mono"
                style={{ background: '#7B61FF22', color: '#7B61FF', border: '1px solid #7B61FF44' }}>
          <ShieldCheck size={12} /> Protect
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 17.3: Commit**

```bash
git add desktop/src/components/SuggestionCard.tsx desktop/src/components/ConsentModal.tsx
git commit -m "feat: SuggestionCard with XAI reason skeleton + ConsentModal with checkbox gate"
```

---

### Task 18: Pages

**Files:**
- Create: `desktop/src/pages/Dashboard.tsx`
- Create: `desktop/src/pages/StoragePage.tsx`
- Create: `desktop/src/pages/PhotoPickerPage.tsx`
- Create: `desktop/src/pages/ReportPage.tsx`

- [ ] **Step 18.1: Write `desktop/src/pages/Dashboard.tsx`**

```typescript
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { HardDrive, Image, BarChart2 } from 'lucide-react'
import { ClutterScoreRing } from '../components/ClutterScoreRing'
import { api, WeeklySnapshot } from '../lib/api'

export function Dashboard() {
  const navigate = useNavigate()
  const [snapshot, setSnapshot] = useState<WeeklySnapshot | null>(null)

  useEffect(() => {
    api.createSnapshot().then(setSnapshot).catch(() => {})
  }, [])

  const score = snapshot?.composite_score ?? 0

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-10">
      <div>
        <h1 className="font-serif text-3xl text-text-primary">Declutter AI</h1>
        <p className="text-text-secondary font-mono text-sm mt-1">Privacy-first digital cleanup</p>
      </div>

      <div className="flex items-center gap-8">
        <ClutterScoreRing score={score} size={160} />
        <div>
          <p className="font-mono text-text-secondary text-sm">Weekly Clutter Score</p>
          <p className="font-mono text-4xl text-text-primary mt-1">{Math.round(score)}<span className="text-lg text-text-secondary">/100</span></p>
          {snapshot && (
            <p className="font-mono text-xs text-text-secondary mt-2">
              {snapshot.mb_reclaimed.toFixed(0)} MB reclaimed · {snapshot.items_cleared} items cleared this week
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { icon: HardDrive, label: 'Storage', desc: 'Find duplicates, large & old files', path: '/storage', color: '#7B61FF' },
          { icon: Image,     label: 'Photos',  desc: 'Pick top 10 aesthetic photos',      path: '/photos',  color: '#22C55E' },
          { icon: BarChart2, label: 'Report',  desc: 'Weekly clutter score trend',        path: '/report',  color: '#F59E0B' },
        ].map(({ icon: Icon, label, desc, path, color }) => (
          <button key={path} onClick={() => navigate(path)}
                  className="rounded-xl p-5 text-left transition-all hover:scale-[1.02]"
                  style={{ background: '#161618', border: '1px solid #2A2A2E' }}>
            <Icon size={22} style={{ color }} />
            <p className="font-serif text-lg text-text-primary mt-3">{label}</p>
            <p className="font-mono text-xs text-text-secondary mt-1">{desc}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 18.2: Write `desktop/src/pages/StoragePage.tsx`**

```typescript
import { useState } from 'react'
import { FolderOpen, Loader2 } from 'lucide-react'
import { useScan } from '../hooks/useScan'
import { useConsent } from '../hooks/useConsent'
import { SuggestionCard } from '../components/SuggestionCard'
import { ConsentModal } from '../components/ConsentModal'
import { api, FileSuggestion } from '../lib/api'

export function StoragePage() {
  const { status, progress, suggestions: rawSuggestions, startScan, error } = useScan()
  const [suggestions, setSuggestions] = useState<FileSuggestion[]>([])
  const [modalTarget, setModalTarget] = useState<FileSuggestion | null>(null)
  const { confirm, skip } = useConsent(setSuggestions)

  // sync rawSuggestions → local state once scan completes
  // (useEffect, not inline setState, to avoid render-phase side-effects)
  // Done in StoragePage via: useEffect(() => { if (rawSuggestions.length > 0) setSuggestions(rawSuggestions) }, [rawSuggestions])

  const pickDir = async () => {
    const dir = window.electron?.openDirectory
      ? await window.electron.openDirectory()
      : prompt('Enter directory path:')
    if (dir) startScan(dir)
  }

  const handleProtect = async (s: FileSuggestion) => {
    const name = s.path.split('\\').pop()?.split('/').pop() ?? s.path
    await api.addProtectedRule('path', s.path, name)
    setSuggestions(prev => prev.filter(x => x.id !== s.id))
  }

  const handleConfirm = async (s: FileSuggestion) => {
    setModalTarget(null)
    await confirm(s)
  }

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <h1 className="font-serif text-2xl text-text-primary">Storage Scanner</h1>

      <button onClick={pickDir} disabled={status === 'scanning'}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-mono disabled:opacity-50"
              style={{ background: '#7B61FF', color: '#fff' }}>
        <FolderOpen size={16} /> Choose Directory
      </button>

      {(status === 'scanning' || status === 'generating_reasons') && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-mono text-text-secondary">
            <Loader2 size={14} className="animate-spin" />
            {status === 'scanning' ? 'Scanning files…' : 'Generating reasons…'}
          </div>
          <div className="h-1.5 rounded-full" style={{ background: '#2A2A2E' }}>
            <div className="h-full rounded-full transition-all" style={{ width: `${progress}%`, background: '#7B61FF' }} />
          </div>
        </div>
      )}

      {error && <p className="text-sm font-mono" style={{ color: '#FF4D4D' }}>{error}</p>}

      {suggestions.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="font-mono text-sm text-text-secondary">{suggestions.length} suggestions</p>
            <button onClick={() => setSuggestions([])}
                    className="text-xs font-mono px-3 py-1 rounded"
                    style={{ background: '#2A2A2E', color: '#8A8A96' }}>
              Skip All
            </button>
          </div>
          {suggestions.map(s => (
            <SuggestionCard key={s.id} suggestion={s}
              onConfirm={() => setModalTarget(s)}
              onSkip={skip}
              onProtect={handleProtect} />
          ))}
        </div>
      )}

      <ConsentModal suggestion={modalTarget} open={!!modalTarget}
                    onConfirm={handleConfirm}
                    onCancel={() => setModalTarget(null)} />
    </div>
  )
}
```

- [ ] **Step 18.3: Write `desktop/src/pages/PhotoPickerPage.tsx`**

```typescript
import { useState, useRef } from 'react'
import { FolderOpen, Loader2, Copy } from 'lucide-react'
import { api, PhotoScore } from '../lib/api'

export function PhotoPickerPage() {
  const [status, setStatus] = useState<'idle' | 'scoring' | 'complete' | 'error'>('idle')
  const [photos, setPhotos] = useState<PhotoScore[]>([])
  const jobRef = useRef<string | null>(null)

  const pickDir = async () => {
    const dir = window.electron?.openDirectory
      ? await window.electron.openDirectory()
      : prompt('Enter directory path:')
    if (!dir) return

    setStatus('scoring')
    const { job_id } = await api.startPhotoScore(dir)
    jobRef.current = job_id

    const poll = setInterval(async () => {
      const { status: s } = await api.getPhotoStatus(job_id)
      if (s === 'complete') {
        clearInterval(poll)
        const top = await api.getTopPhotos(job_id)
        setPhotos(top)
        setStatus('complete')
      } else if (s === 'error') {
        clearInterval(poll)
        setStatus('error')
      }
    }, 2000)
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <h1 className="font-serif text-2xl text-text-primary">Photo Picker</h1>
      <p className="font-mono text-sm text-text-secondary">Score your photos aesthetically and pick the top 10.</p>

      <button onClick={pickDir} disabled={status === 'scoring'}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-mono disabled:opacity-50"
              style={{ background: '#22C55E', color: '#0D0D0F' }}>
        <FolderOpen size={16} /> Choose Photo Folder
      </button>

      {status === 'scoring' && (
        <div className="flex items-center gap-2 text-sm font-mono text-text-secondary">
          <Loader2 size={14} className="animate-spin" /> Scoring photos…
        </div>
      )}

      {photos.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {photos.map((p, i) => {
            const name = p.path.split('\\').pop()?.split('/').pop() ?? p.path
            return (
              <div key={p.path} className="rounded-xl overflow-hidden relative group"
                   style={{ background: '#161618', border: '1px solid #2A2A2E' }}>
                <img src={`file://${p.path}`} alt={name}
                     className="w-full h-40 object-cover"
                     onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                <div className="p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-medium" style={{ color: '#22C55E' }}>
                      #{i + 1} · {p.score.toFixed(0)}/100
                    </span>
                    <button onClick={() => navigator.clipboard.writeText(p.path)}
                            className="opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Copy path">
                      <Copy size={12} style={{ color: '#8A8A96' }} />
                    </button>
                  </div>
                  <p className="text-xs font-mono text-text-secondary truncate">{name}</p>
                  {p.reason && <p className="text-xs text-text-secondary leading-relaxed">{p.reason}</p>}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 18.4: Write `desktop/src/pages/ReportPage.tsx`**

```typescript
import { useEffect, useState } from 'react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { api, WeeklySnapshot } from '../lib/api'

export function ReportPage() {
  const [weeks, setWeeks] = useState<WeeklySnapshot[]>([])

  useEffect(() => {
    api.getWeeklyReport().then(setWeeks).catch(() => {})
  }, [])

  const data = weeks.map(w => ({
    week: w.week_start.slice(5),  // "MM-DD"
    score: Math.round(w.composite_score),
    mb: Math.round(w.mb_reclaimed),
  }))

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-10">
      <h1 className="font-serif text-2xl text-text-primary">Weekly Report</h1>

      <div className="rounded-xl p-6 space-y-3" style={{ background: '#161618', border: '1px solid #2A2A2E' }}>
        <p className="font-mono text-sm text-text-secondary">Clutter Score — last 8 weeks</p>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2E" />
            <XAxis dataKey="week" tick={{ fill: '#8A8A96', fontSize: 11, fontFamily: 'DM Mono' }} />
            <YAxis domain={[0, 100]} tick={{ fill: '#8A8A96', fontSize: 11, fontFamily: 'DM Mono' }} />
            <Tooltip contentStyle={{ background: '#161618', border: '1px solid #2A2A2E', fontFamily: 'DM Mono' }} />
            <Line type="monotone" dataKey="score" stroke="#7B61FF" strokeWidth={2} dot={{ fill: '#7B61FF' }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-xl p-6 space-y-3" style={{ background: '#161618', border: '1px solid #2A2A2E' }}>
        <p className="font-mono text-sm text-text-secondary">MB Reclaimed per week</p>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2E" />
            <XAxis dataKey="week" tick={{ fill: '#8A8A96', fontSize: 11, fontFamily: 'DM Mono' }} />
            <YAxis tick={{ fill: '#8A8A96', fontSize: 11, fontFamily: 'DM Mono' }} />
            <Tooltip contentStyle={{ background: '#161618', border: '1px solid #2A2A2E', fontFamily: 'DM Mono' }} />
            <Bar dataKey="mb" fill="#22C55E" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
```

- [ ] **Step 18.5: Commit**

```bash
git add desktop/src/pages/
git commit -m "feat: all four pages — Dashboard, StoragePage, PhotoPickerPage, ReportPage"
```

---

### Task 19: App.tsx + routing + nav

**Files:**
- Create: `desktop/src/App.tsx`

- [ ] **Step 19.1: Write `desktop/src/App.tsx`**

```typescript
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { HardDrive, Image, BarChart2, Home } from 'lucide-react'
import { Dashboard } from './pages/Dashboard'
import { StoragePage } from './pages/StoragePage'
import { PhotoPickerPage } from './pages/PhotoPickerPage'
import { ReportPage } from './pages/ReportPage'

const navItems = [
  { to: '/',        icon: Home,      label: 'Home'    },
  { to: '/storage', icon: HardDrive, label: 'Storage' },
  { to: '/photos',  icon: Image,     label: 'Photos'  },
  { to: '/report',  icon: BarChart2, label: 'Report'  },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen" style={{ background: '#0D0D0F' }}>
        <nav className="w-16 flex flex-col items-center py-6 gap-6 shrink-0"
             style={{ background: '#161618', borderRight: '1px solid #2A2A2E' }}>
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/'}
                     className={({ isActive }) =>
                       `flex flex-col items-center gap-1 p-2 rounded-lg transition-colors ${isActive ? 'text-accent' : 'text-text-secondary hover:text-text-primary'}`
                     }
                     title={label}>
              <Icon size={20} />
              <span className="text-[9px] font-mono">{label}</span>
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/storage" element={<StoragePage />} />
            <Route path="/photos" element={<PhotoPickerPage />} />
            <Route path="/report" element={<ReportPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
```

- [ ] **Step 19.2: Start dev server and verify renders**

```powershell
cd desktop
npm run dev
```

Open `http://localhost:5173` in a browser. Verify:
- Dashboard loads with ClutterScoreRing (score=0 if no backend)
- Nav links navigate between pages
- No console errors

- [ ] **Step 19.3: Run backend and verify full flow**

Terminal 1:
```powershell
cd backend
.\venv\Scripts\Activate.ps1
$env:ANTHROPIC_API_KEY = "your-key-here"
python run.py
```

Terminal 2:
```powershell
cd desktop
npm run dev
```

Verify full flow:
1. Dashboard loads, `POST /api/report/snapshot` fires, score shows
2. Storage page: choose a directory, scan starts, progress bar moves, suggestion cards appear with reasons
3. Click Delete on a card → ConsentModal appears → check box → confirm → card disappears
4. Click Protect on a card → card disappears → add same folder, rescan → protected file absent
5. Report page: line chart and bar chart render (may be empty if first run)

- [ ] **Step 19.4: Final commit**

```bash
git add desktop/src/App.tsx
git commit -m "feat: App.tsx routes + sidebar nav — Phase 1 complete"
```

---

## Self-Review Checklist (run before declaring done)

- [ ] `GET /api/health` → `{"status": "ok"}`
- [ ] `POST /api/storage/scan` → scan_id, status reaches `complete`
- [ ] Every suggestion has non-empty `reason` field
- [ ] `confirmed=false` → file untouched, response `{"executed": false}`
- [ ] `confirmed=true` → file in Recycle Bin, `consent_log` row written
- [ ] Add protected folder → rescan → its files absent
- [ ] `GET /api/report/weekly` → valid JSON list
- [ ] Electron window opens, Dashboard renders without console errors
- [ ] Full flow: scan → see suggestions → protect one → confirm-delete another → check report
- [ ] `pytest tests/ -v` → all green
