# Claude Code — Start Prompt for Declutter AI

Read CLAUDE.md fully before writing a single line of code.
Apply Karpathy's 4 rules to every task: think first, stay simple, surgical changes, verify done-state.

---

## YOUR TASK

Build Phase 1 of Declutter AI — a privacy-first desktop app.
Working directory: C:\Dev\Declutter AI
CLAUDE.md is in the project root. It is your source of truth.

## BUILD ORDER (strict — do not skip ahead)

### Step 1 — Backend foundation
```
cd backend
pip install -r requirements.txt
```
Create:
- app/database.py — SQLModel engine, create_all(), all 4 tables
- app/main.py — FastAPI app, CORS for localhost:5173, register all routers
- app/models/schemas.py — Pydantic models for FileSuggestion, ConsentRequest, ProtectedRule, WeeklySnapshot, PhotoScore
- app/routers/consent.py — /api/consent/confirm ONLY. confirmed=false → return immediately. confirmed=true → execute action → log to consent_log
Done when: uvicorn app.main:app --reload starts, GET /api/health returns {"status":"ok"}

### Step 2 — Storage scanner service
Create app/services/storage_service.py:
- walk_directory(path) → list of file metadata dicts (path, name, size_bytes, last_accessed, ext)
- find_exact_duplicates(files) → SHA-256 hash map → return duplicates
- find_near_duplicates(files) → pHash via imagehash, threshold=8 → return near-dupes
- find_large_files(files, threshold_mb=50)
- find_old_files(files, days=365)
- find_screenshots(files) → filename pattern match
- run_full_scan(directory) → combines all above, deduplicates by path
Create app/routers/storage.py — POST /scan (BackgroundTask), GET /scan/:id/status, GET /scan/:id/suggestions
Done when: POST /api/storage/scan {"directory": "C:/Users/test"} returns scan_id, status reaches "complete"

### Step 3 — XAI reason generation
Create app/services/xai_service.py:
- generate_batch_reasons(items, module) → calls Anthropic API
- Input: ONLY filename, size_mb, last_accessed, suggestion_type (never file content)
- Model: claude-sonnet-4-20250514, max_tokens=80 per item
- One sentence per item, specific (mentions actual age/size/type)
- Fallback to template string if API call fails
- Integrate into run_scan_job — reasons stream in after suggestions appear
Done when: scan results have non-empty reason field on every suggestion

### Step 4 — Protected Memories
Create app/services/protected_service.py:
- is_protected(path, rules) → bool
- Filter protected paths from scan results before returning
Create app/routers/protected.py — GET/POST/DELETE /api/protected/rules
Integrate: run_full_scan checks every suggestion against active rules before appending
Done when: adding a rule for a folder causes files in that folder to disappear from scan results

### Step 5 — Instagram photo picker
Create app/services/photo_scorer.py:
- sharpness_score(path) → Laplacian variance via PIL, normalized 0–100
- brightness_score(path) → mean luminance, penalize overexposed/underexposed
- composition_score(path) → rule-of-thirds proxy via edge density in thirds grid
- combined_score(path) → weighted average (sharpness 40%, brightness 30%, composition 30%)
- score_directory(directory) → score all images, return sorted list
Create app/routers/photos.py — POST /api/photos/score, GET /api/photos/score/:id/top
Done when: given a folder of photos, /top returns 10 items each with score 0–100 and reason

### Step 6 — Weekly Clutter Score
Create app/routers/report.py:
- GET /api/report/weekly → last 8 weekly_snapshots rows
- POST /api/report/snapshot → compute composite score from scan history, insert row
Done when: endpoint returns valid JSON with week_start, composite_score, mb_reclaimed

### Step 7 — Desktop Electron + React app
Scaffold using electron-react-boilerplate pattern (most starred: 22k★ on GitHub).
Stack: Electron + React 19 + TypeScript + Vite + Tailwind + shadcn/ui + Zustand + Recharts

Create:
- desktop/electron/main.ts — BrowserWindow 1280×800, load localhost:5173 in dev
- desktop/electron/preload.ts — contextBridge for fs path picker only
- desktop/src/lib/api.ts — typed fetch wrapper, base URL localhost:8000
- desktop/src/lib/tokens.ts — design tokens from CLAUDE.md
- desktop/src/hooks/useScan.ts — POST scan, poll /status every 2s, return {status, progress, suggestions}
- desktop/src/hooks/useConsent.ts — POST /consent/confirm, optimistic UI update

Components (dark theme, design tokens from CLAUDE.md):
- SuggestionCard.tsx — filename, type badge, XAI reason, confidence bar, [Confirm] [Skip] [Protect] buttons. Reason shows skeleton loader until populated.
- ConsentModal.tsx — "This will permanently delete X. This cannot be undone." + checkbox + Confirm button. No action fires without this.
- ClutterScoreRing.tsx — animated SVG ring, 0–100, color: <40 red, 40–70 amber, >70 green
- ProtectedBadge.tsx — shield icon, shows on protected items

Pages:
- Dashboard.tsx — ClutterScoreRing (composite), 3 module cards (Storage / Photos / Report), each with last scan time + quick scan button
- StoragePage.tsx — directory picker → triggers scan → progress bar → SuggestionCard list → bulk actions (confirm all / skip all)
- PhotoPickerPage.tsx — directory picker → score → masonry grid of top 10 with score badge + reason + copy-to-clipboard
- ReportPage.tsx — Recharts LineChart of last 8 weeks composite score + MB reclaimed bar chart

Done when: Electron window opens, Dashboard renders, StoragePage completes a full scan→consent→delete flow end-to-end

---

## CONSTRAINTS
- ANTHROPIC_API_KEY from env var only — never hardcode
- Backend runs on port 8000, frontend on 5173
- Every destructive action MUST go through /api/consent/confirm
- Privacy: Anthropic API receives metadata only — filename, size, age, type
- No features outside Phase 1 scope
- Install command: pip install -r requirements.txt then npm install in desktop/

## VERIFY BEFORE DONE
Run this checklist after each step:
[ ] uvicorn starts without errors
[ ] /api/health returns 200
[ ] scan completes and suggestions have reason populated
[ ] confirmed=false leaves files untouched
[ ] confirmed=true deletes/archives file and logs to consent_log
[ ] protected folder files absent from scan results
[ ] Electron window opens and renders Dashboard without console errors
[ ] Full flow works: scan → see suggestions → protect one → confirm delete another → check report
