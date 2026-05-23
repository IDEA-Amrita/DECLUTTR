# Declutter AI — CLAUDE.md
# Karpathy's 4 Rules applied to every task in this repo

## RULE 1 — THINK BEFORE CODING
Before writing any code:
- State your assumptions explicitly
- Surface any ambiguity — ask, don't guess
- List tradeoffs when multiple approaches exist
- If the task is unclear, ask ONE clarifying question before proceeding
Never silently pick an interpretation and run with it.

## RULE 2 — SIMPLICITY FIRST
- Implement exactly what was asked. Nothing more.
- No extra abstractions, configs, or "future-proofing" unless requested
- No unrequested dependencies
- When stuck in complexity, return to the smallest viable solution
If you find yourself adding a layer "just in case" — stop and delete it.

## RULE 3 — SURGICAL CHANGES
- Touch only what the task requires
- Match the existing code style, naming, and structure exactly
- Never refactor code outside the scope of the current task
- Diffs must contain only what was requested
One task = one change surface. Never widen scope without asking.

## RULE 4 — GOAL-DRIVEN EXECUTION
- Every task has a verifiable done-state — define it before starting
- Check your output against it before declaring done
- Run the app. Verify it works. Don't assume.
- If a step fails, diagnose before retrying

---

## PROJECT: AI Digital Declutter & Decision Engine

### What it is
Privacy-first desktop app (Electron + React + FastAPI) that scans local storage,
Gmail, and Google Drive, then uses on-device logic + Anthropic API (metadata only,
never file content) to suggest cleanup actions with a generated XAI reason per item.
Write/delete actions are gated behind explicit per-item user consent.

### Stack
- Backend: FastAPI (Python 3.11), SQLModel + SQLite, Anthropic SDK
- Desktop: Electron + React 19 + TypeScript + Vite + Tailwind + shadcn/ui
- Boilerplate reference: electron-react-boilerplate (22k★ on GitHub)

### Working directory
C:\Dev\Declutter AI

### Phase 1 scope (build this, nothing else)
1. Local storage scanner — duplicates (SHA-256 + pHash), large files, old files, screenshots
2. XAI reason per suggestion — generated via Anthropic API (metadata only)
3. Protected Memories — user marks folders/files as never-suggest-for-deletion
4. Consent gate — single /api/consent/confirm endpoint; write actions only execute after confirmed=true
5. Instagram photo picker — aesthetic scoring (sharpness + brightness + composition) → top 10 picks
6. Weekly Clutter Score — SQLite snapshots, 0–100 composite score, trend chart

### Phase 2 (do NOT build yet)
Gmail triage, True Unsubscribe Engine, Google Drive dedup, Smart Auto-Organizer,
Subscription Spend Tracker, mobile (Expo)

### Privacy rule (non-negotiable)
Anthropic API receives ONLY: filename, size_bytes, last_accessed (epoch), suggestion_type.
Never send file contents, email bodies, or personal data.

### Consent rule (non-negotiable)
Every suggestion has write_enabled: false by default.
Only /api/consent/confirm with confirmed=true executes destructive actions.
Log every consent action to SQLite consent_log table.

### Design tokens
bg: #0D0D0F | surface: #161618 | border: #2A2A2E
accent: #7B61FF | danger: #FF4D4D | success: #22C55E | warning: #F59E0B
text-primary: #F2F2F3 | text-secondary: #8A8A96
Font: DM Mono (data/stats) + Instrument Serif (headings)
Aesthetic: dark, industrial-minimal — Linear meets a filesystem tool

### Key repos to reference (most starred, battle-tested)
- electron-react-boilerplate/electron-react-boilerplate (22k★) — desktop scaffold
- electron-vite/electron-vite-react (4k★) — Vite-native Electron
- tiangolo/fastapi (80k★) — backend
- fastapi/full-stack-fastapi-template (28k★) — FastAPI project structure
- JohannesKaufmann/html-to-markdown — for email parsing
- JohannesGruber/imagehash (3k★) — perceptual hashing
- anthropics/anthropic-sdk-python — Anthropic API
- shadcn-ui/ui (80k★) — component library
- pmndrs/zustand (48k★) — frontend state management
- recharts/recharts (24k★) — weekly score trend chart

### File structure
backend/
  app/
    main.py              # FastAPI app, CORS, router registration
    models/schemas.py    # Pydantic models
    routers/
      storage.py         # scan endpoints
      consent.py         # THE only write gate
      photos.py          # Instagram picker scoring
      report.py          # weekly clutter score
    services/
      storage_service.py # SHA-256, pHash, file walk
      xai_service.py     # Anthropic API integration
      photo_scorer.py    # sharpness + brightness + composition scoring
      protected_service.py # protected rules registry
    database.py          # SQLModel setup, table creation
  requirements.txt
  run.py

desktop/
  electron/
    main.ts              # Electron main process
    preload.ts           # IPC bridge
  src/
    App.tsx
    pages/
      Dashboard.tsx      # ClutterScoreRing + module cards
      StoragePage.tsx    # scan + suggestion cards
      PhotoPickerPage.tsx
      ReportPage.tsx     # trend chart
    components/
      SuggestionCard.tsx # XAI rationale + confidence + Confirm/Skip/Protect
      ConsentModal.tsx   # explicit confirm gate
      ClutterScoreRing.tsx # animated SVG 0–100
      ProtectedBadge.tsx
    hooks/
      useScan.ts         # polling /status every 2s
      useConsent.ts
    lib/
      api.ts             # typed fetch wrapper → localhost:8000
      tokens.ts          # design tokens
  package.json
  vite.config.ts

### API contract (Phase 1 only)
GET  /api/health
POST /api/storage/scan          { directory: string }
GET  /api/storage/scan/:id/status
GET  /api/storage/scan/:id/suggestions
POST /api/photos/score          { directory: string }
GET  /api/photos/score/:id/top  → top 10 with score + reason
GET  /api/protected/rules
POST /api/protected/rules       { type: "folder"|"path", value: string, label: string }
DELETE /api/protected/rules/:id
POST /api/consent/confirm       { suggestion_id, module, action, confirmed: true }
GET  /api/report/weekly
GET  /api/health

### SQLite tables
suggestions(id, scan_id, type, path, size_bytes, last_accessed, reason, confidence, action, consent_given, skipped, protected)
consent_log(id, suggestion_id, action, confirmed_at, success)
protected_rules(id, type, value, label, created_at)
weekly_snapshots(id, week_start, storage_score, photo_score, composite_score, mb_reclaimed, items_cleared)

### Done criteria per task
- Backend: uvicorn starts, /api/health returns {"status":"ok"}, all routes registered
- Scanner: given ~/Downloads, returns ≥1 suggestion with reason populated
- Consent gate: confirmed=false → no file touched; confirmed=true → file deleted/archived
- Photo picker: given a folder with images, returns top 10 with score 0–100
- Desktop: Electron window opens, Dashboard renders ClutterScoreRing, StoragePage triggers scan
- Protected: marking a folder prevents its files from appearing in future scan results
