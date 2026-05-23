# Declutter AI — Phase 1 Design Spec
**Date:** 2026-05-23  
**Scope:** Phase 1 only — local scanner, XAI reasons, protected memories, consent gate, photo picker, weekly score  
**Status:** Approved

---

## 1. Architecture Overview

```
[Electron shell]
      │  loads
      ▼
[React/Vite SPA]  ──── typed fetch ────▶  [FastAPI backend]
  port 5173                                   port 8000
                                                 │
                                          [SQLite via SQLModel]
```

- Electron is a thin shell: opens a `BrowserWindow` (1280×800), points to `localhost:5173` in dev.
- React SPA handles all UI; communicates with backend over HTTP only.
- FastAPI owns all business logic. Every destructive file action goes through one endpoint: `POST /api/consent/confirm`.
- SQLite holds suggestions, consent log, protected rules, weekly snapshots.

---

## 2. Backend

### 2.1 File Structure
```
backend/
  app/
    main.py              # FastAPI app, CORS, router registration
    database.py          # SQLModel engine + create_all()
    models/
      schemas.py         # Pydantic models
    routers/
      storage.py         # scan endpoints
      consent.py         # THE only write gate
      photos.py          # photo scoring endpoints
      protected.py       # protected rules CRUD
      report.py          # weekly snapshot endpoints
    services/
      storage_service.py
      xai_service.py
      photo_scorer.py
      protected_service.py
  requirements.txt
  run.py
```

### 2.2 SQLite Tables

```sql
suggestions(
  id TEXT PRIMARY KEY,
  scan_id TEXT,
  type TEXT,          -- "duplicate"|"near_duplicate"|"large_file"|"old_file"|"screenshot"
  path TEXT,
  size_bytes INTEGER,
  last_accessed INTEGER,  -- epoch
  reason TEXT,
  confidence REAL,
  action TEXT,            -- "delete" (all Phase 1 actions)
  consent_given INTEGER DEFAULT 0,
  skipped INTEGER DEFAULT 0,
  protected INTEGER DEFAULT 0
)

consent_log(
  id TEXT PRIMARY KEY,
  suggestion_id TEXT,
  action TEXT,
  confirmed_at TEXT,
  success INTEGER
)

protected_rules(
  id TEXT PRIMARY KEY,
  type TEXT,    -- "folder"|"path"
  value TEXT,
  label TEXT,
  created_at TEXT
)

weekly_snapshots(
  id TEXT PRIMARY KEY,
  week_start TEXT,
  storage_score REAL,
  photo_score REAL,
  composite_score REAL,
  mb_reclaimed REAL,
  items_cleared INTEGER
)
```

### 2.3 Scan State (in-memory)

Scan jobs are tracked in an app-level dict:
```python
scan_jobs: dict[str, dict] = {}
# key: scan_id
# value: { "status": "pending"|"scanning"|"generating_reasons"|"complete"|"error",
#           "progress": 0-100, "suggestions": [...] }
```

This is sufficient for a single-user desktop app. On scan completion, all suggestions are persisted to SQLite. `GET /scan/{id}/suggestions` reads from the in-memory job if it exists; falls back to SQLite by `scan_id` if the app has restarted. On restart, job status is lost (fine — user can re-scan; results survive in SQLite).

### 2.4 Storage Scanner (`storage_service.py`)

Functions:
- `walk_directory(path)` → list of file metadata dicts: `{path, name, size_bytes, last_accessed, ext}`
- `find_exact_duplicates(files)` → SHA-256 hash map, return groups with >1 member
- `find_near_duplicates(files)` → pHash via `imagehash` (phash algorithm, threshold=8 Hamming distance), image files only (`.jpg .jpeg .png .gif .bmp .webp .heic`)
- `find_large_files(files, threshold_mb=50)`
- `find_old_files(files, days=365)`
- `find_screenshots(files)` → filename pattern: starts with `Screenshot` / `screen` / `IMG_` combined with extension check
- `run_full_scan(directory, rules)` → combines all above, deduplicates by path, filters protected paths

### 2.5 XAI Service (`xai_service.py`)

- Model: **`claude-sonnet-4-6`** (latest Sonnet, dateless format)
- Input fields sent to API: `filename`, `size_mb`, `last_accessed_days_ago`, `suggestion_type` — never file contents
- Strategy: single batch API call with all items listed in the prompt; parse response into per-item reasons
- Output: one sentence per item, specific (e.g., "screenshot.png is a 12.3MB screenshot that hasn't been opened in 847 days")
- Fallback: template string if API call fails: `"This {type} file ({size_mb:.1f} MB) hasn't been accessed in {days} days."`
- Env var: `ANTHROPIC_API_KEY` — never hardcoded

### 2.6 Consent Gate (`routers/consent.py`)

```
POST /api/consent/confirm
  body: { suggestion_id, module, action, confirmed: bool }

  if confirmed == false:
    return { "executed": false, "message": "Action not confirmed" }

  if confirmed == true:
    look up suggestion by id
    send file to Recycle Bin via send2trash
    log to consent_log (confirmed_at, success=true/false)
    update suggestion.consent_given = 1
    return { "executed": true }
```

This is the **only** endpoint that touches the filesystem. All other endpoints are read-only.

### 2.7 Protected Service (`protected_service.py`)

- `is_protected(path, rules)` → returns True if path starts with any folder rule's value, or exactly matches a path rule
- `run_full_scan` calls this before appending each suggestion

### 2.8 Photo Scorer (`photo_scorer.py`)

PIL-based heuristics (no PyTorch, no model weights — fast and zero-dependency):
- `sharpness_score(path)` → Laplacian variance on grayscale image, normalized 0–100
- `brightness_score(path)` → mean luminance in [0,255], penalise <30 (underexposed) and >220 (overexposed)
- `composition_score(path)` → edge density in thirds grid (rule of thirds proxy via PIL edge detection)
- `combined_score(path)` → weighted: sharpness×0.4 + brightness×0.3 + composition×0.3
- `score_directory(directory)` → score all images, return sorted list (desc by score)
- After scoring, the top-10 list is passed to `xai_service.generate_batch_reasons()` with `module="photos"` to generate one-sentence XAI reasons (e.g., "This sharp, well-lit photo scores 87/100 for composition and lighting."). Fallback to template string.

> Note: NIMA (2017), CLIP-IQA, and ArtiMuse (CVPR 2026) exist and are more accurate but require PyTorch + pretrained weights (100MB–2GB). Appropriate for Phase 2 upgrade if users want higher aesthetic precision.

### 2.9 API Contract (Phase 1)

```
GET  /api/health                           → {"status": "ok"}
POST /api/storage/scan                     body: {directory}  → {scan_id}
GET  /api/storage/scan/{id}/status         → {status, progress}
GET  /api/storage/scan/{id}/suggestions    → [{...FileSuggestion}]
POST /api/photos/score                     body: {directory}  → {job_id}
GET  /api/photos/score/{id}/top            → top 10 [{...PhotoScore}]
GET  /api/protected/rules                  → [{...ProtectedRule}]
POST /api/protected/rules                  body: {type, value, label}
DELETE /api/protected/rules/{id}
POST /api/consent/confirm                  body: {suggestion_id, module, action, confirmed}
GET  /api/report/weekly                    → last 8 weekly_snapshots
POST /api/report/snapshot                  → compute + insert new snapshot (called by frontend on Dashboard mount)
                                             mb_reclaimed  = sum(size_bytes/1e6) of confirmed consent_log rows this ISO week
                                             items_cleared = count of confirmed consent_log rows this ISO week
                                             storage_score = min(100, (mb_reclaimed / 500) * 100)   # 500 MB = 100
                                             photo_score   = mean(top10_scores) from last in-memory photo job, else 0
                                             composite     = storage_score * 0.7 + photo_score * 0.3
```

---

## 3. Desktop (Electron + React)

### 3.1 File Structure
```
desktop/
  electron/
    main.ts        # BrowserWindow 1280×800, loads localhost:5173 in dev
    preload.ts     # contextBridge: fs.showOpenDialog only
  src/
    App.tsx        # React Router routes
    pages/
      Dashboard.tsx
      StoragePage.tsx
      PhotoPickerPage.tsx
      ReportPage.tsx
    components/
      SuggestionCard.tsx
      ConsentModal.tsx
      ClutterScoreRing.tsx
      ProtectedBadge.tsx
    hooks/
      useScan.ts
      useConsent.ts
    lib/
      api.ts
      tokens.ts
  package.json
  vite.config.ts
  electron-builder.json  (or electron-vite config)
```

### 3.2 Design Tokens

```ts
bg:           "#0D0D0F"
surface:      "#161618"
border:       "#2A2A2E"
accent:       "#7B61FF"
danger:       "#FF4D4D"
success:      "#22C55E"
warning:      "#F59E0B"
textPrimary:  "#F2F2F3"
textSecondary:"#8A8A96"
// Font: DM Mono (data/stats) + Instrument Serif (headings)
```

### 3.3 Component Contracts

**SuggestionCard** — props: `suggestion`, `onConfirm`, `onSkip`, `onProtect`  
Shows: filename, type badge, XAI reason (skeleton loader until reason populated), confidence bar, three action buttons.

**ConsentModal** — props: `suggestion`, `open`, `onConfirm`, `onCancel`  
Shows: "This will move [filename] to the Recycle Bin." + checkbox "I understand this action" + Confirm button. No action fires without checkbox checked.

**ClutterScoreRing** — props: `score: number`  
Animated SVG ring, 0–100. Color: <40 → danger, 40–70 → warning, >70 → success.

**ProtectedBadge** — props: none (visual only). Shield icon, shown on protected items.

### 3.4 Page Behaviour

**Dashboard** — ClutterScoreRing (composite), three module cards (Storage / Photos / Report) each with last scan time and quick-scan button.

**StoragePage** — native dir picker (via preload IPC) → POST scan → poll `/status` every 2s → progress bar → SuggestionCard list → bulk actions (Confirm all / Skip all).

**PhotoPickerPage** — dir picker → POST score → poll → masonry grid of top 10, each with score badge, XAI reason, copy-to-clipboard button.

**ReportPage** — Recharts `LineChart` of last 8 weeks composite score + `BarChart` of MB reclaimed per week.

### 3.5 Hooks

**useScan(directory)**: POST scan → starts polling `/status` every 2000ms → updates `{status, progress, suggestions}` → stops polling on `"complete"` or `"error"`.

**useConsent()**: calls `POST /api/consent/confirm`, handles optimistic state update (removes suggestion from list on confirmed=true).

### 3.6 Stack

| Layer | Choice | Version |
|---|---|---|
| Runtime | Electron | latest stable |
| Frontend | React | 19 |
| Language | TypeScript | 5.x |
| Build | Vite | 5.x |
| Styling | Tailwind CSS | 3.x + shadcn/ui |
| State | Zustand | 4.x |
| Charts | Recharts | 2.x |
| Routing | React Router | 6.x |

---

## 4. Privacy Guarantees

| What | Rule |
|---|---|
| Anthropic API payload | filename, size_mb, last_accessed_days_ago, suggestion_type only. Never file contents. |
| File deletion | Only via `POST /api/consent/confirm` with `confirmed=true`. All other endpoints are read-only. |
| Consent log | Every action (confirmed or rejected) written to `consent_log` table. |
| Protected rules | Checked before any suggestion is returned. Protected files never appear in results. |

---

## 5. Key Decisions Log

| Decision | Choice | Rationale |
|---|---|---|
| File deletion method | `send2trash` → Recycle Bin | Recoverable; user confirmed preference |
| Python env | `backend/venv` virtualenv | Isolates deps from system Python |
| Scan state | In-memory dict | Single-user desktop; no need for persistent job queue |
| XAI model | `claude-sonnet-4-6` | Latest Sonnet (dateless format); replaces old `claude-sonnet-4-20250514` |
| Photo scoring | PIL heuristics | Fast, zero extra deps; NIMA/ArtiMuse deferred to Phase 2 |
| pHash library | `imagehash` | Most maintained Python pHash lib (confirmed 2025-2026) |
| pHash scope | Image files only | pHash is undefined for non-image files |
| Desktop scaffold | Write from scratch (electron-vite-react pattern) | Clean repo, exact files needed, no boilerplate cruft |

---

## 6. Done Criteria

- [ ] `uvicorn app.main:app --reload` starts, `GET /api/health` → `{"status": "ok"}`
- [ ] `POST /api/storage/scan` returns `scan_id`; status reaches `"complete"` with ≥1 suggestion
- [ ] Every suggestion has non-empty `reason` field
- [ ] `confirmed=false` → file untouched
- [ ] `confirmed=true` → file in Recycle Bin, row in `consent_log`
- [ ] Adding a protected folder rule → its files absent from next scan
- [ ] Electron window opens, Dashboard renders `ClutterScoreRing` without console errors
- [ ] Full flow: scan → see suggestions → protect one → confirm-delete another → check report
