# Declutter AI

A privacy-first desktop application that scans your local storage, scores your photos aesthetically, and uses AI to explain exactly why each file is worth cleaning up and then gates every deletion after your explicit consent.

Built with **Electron + React** (desktop) and **FastAPI** (local backend). All file analysis stays on your machine. Only metadata (filename, size, age, type) is sent to an AI model (works online, to give XAI reasons), not file contents.

---

## What it does (Phase 1 is completed so far)

| Feature | Description |
|---|---|
| **Storage Scanner** | Finds exact duplicates (SHA-256), near-duplicates (perceptual hash), large files, old files, and screenshots |
| **AI Explanations** | Generates a one-sentence reason per file using a 10-model fallback chain (Groq → Gemini → Mistral → DeepSeek → Cohere → Claude → GPT-4o) |
| **Grouped Results** | Files grouped by type — Screenshots, Duplicates, Large Files, Old Files — with per-group Select All, Delete, Skip, and Protect |
| **File Previews** | Real thumbnail for images; type-specific icons for video, audio, PDF, code, and archives |
| **Consent Gate** | Every deletion requires an explicit checkbox confirmation. Files go to the Recycle Bin (via `send2trash`), never permanently deleted (so can be be retreived) |
| **Protected Memories** | Mark folders or files as never-suggest-for-deletion |
| **Photo Picker** | Scores photos by sharpness, brightness, and composition and surfaces your top 10 to post on instagram |
| **Weekly Report** | Tracks a clutter score (0–100) and MB reclaimed per week with trend charts |

---

## Tech stack

| Layer | Tools |
|---|---|
| Desktop | Electron 33 · React 19 · TypeScript · Vite · Tailwind CSS |
| State | Zustand (scan state persists across page navigation) |
| Charts | Recharts |
| Backend | FastAPI · SQLModel · SQLite · Python 3.11+ · Uvicorn |
| AI / LLM | 10-model fallback chain across 7 providers (details given below) |
| Image scoring | Pillow · SciPy (Laplacian sharpness, luminance, edge composition) |
| Duplicate detection | SHA-256 exact · imagehash pHash near-duplicate |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/declutter-ai.git
cd declutter-ai
```

### 2. Backend — Python virtual environment

```powershell
cd backend
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate        # macOS / Linux
pip install -r requirements.txt
```

### 3. API keys (optional but recommended)

The app works without any keys.. it falls back to template reasons. For AI-generated explanations, copy the example env file and fill in whichever keys you have:

```powershell
cp .env.example .env
# Open .env and paste your keys
```

| Env variable | Provider | Get key at |
|---|---|---|---|
| `GROQ_API_KEY` | Groq (llama-3.3-70b) | https://console.groq.com/keys |
| `GOOGLE_API_KEY` | Gemini 2.0 Flash + 1.5 Flash | https://aistudio.google.com/app/apikey |
| `MISTRAL_API_KEY` | Mistral Small | https://console.mistral.ai/api-keys |
| `DEEPSEEK_API_KEY` | DeepSeek Chat | https://platform.deepseek.com/api-keys |
| `COHERE_API_KEY` | Command-R+ | https://dashboard.cohere.com/api-keys |
| `ANTHROPIC_API_KEY` | Claude Haiku + Sonnet | https://console.anthropic.com/settings/keys |
| `OPENAI_API_KEY` | GPT-4o Mini + GPT-4o | https://platform.openai.com/api-keys |

You only need **one key** to get AI reasons. Start with Groq or Google bcoz both have free tiers.

### 4. Frontend — Node dependencies

```powershell
cd ../desktop
npm install
```

---

## Running the app

You need **two terminals running simultaneously**.

**Terminal 1 — Backend**
```powershell
cd backend
venv\Scripts\Activate.ps1
python run.py
# Uvicorn starts on http://localhost:8000
```

**Terminal 2 — Desktop (Electron)**
```powershell
cd desktop
npm run dev
# Vite starts, Electron window opens automatically
```

Open http://localhost:5173 in a browser if you just want the web UI without Electron.

---

## Project structure

```
declutter-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, router registration
│   │   ├── database.py              # SQLModel + SQLite setup
│   │   ├── models/schemas.py        # Pydantic models + SQLModel table definitions
│   │   ├── routers/
│   │   │   ├── storage.py           # POST /api/storage/scan  +  status/suggestions
│   │   │   ├── consent.py           # POST /api/consent/confirm  ← only write gate
│   │   │   ├── photos.py            # POST /api/photos/score  +  top results
│   │   │   ├── protected.py         # GET/POST/DELETE /api/protected/rules
│   │   │   └── report.py            # GET /api/report/weekly  +  POST /api/report/snapshot
│   │   └── services/
│   │       ├── xai_service.py       # 10-model LLM fallback chain
│   │       ├── storage_service.py   # SHA-256, pHash, file walker
│   │       ├── photo_scorer.py      # sharpness + brightness + composition
│   │       └── protected_service.py # folder/path rule matching
│   ├── tests/                       # 21 pytest tests (all passing)
│   ├── .env.example                 # API key template
│   ├── requirements.txt
│   └── run.py                       # Entrypoint — loads .env then starts uvicorn
│
└── desktop/
    ├── electron/
    │   ├── main.ts                  # Electron main process + native folder picker IPC
    │   └── preload.ts               # Context bridge (window.electron.openDirectory)
    └── src/
        ├── App.tsx                  # BrowserRouter + sidebar nav (4 routes)
        ├── pages/
        │   ├── Dashboard.tsx        # ClutterScoreRing + module status cards
        │   ├── StoragePage.tsx      # Grouped scan results, multi-select, bulk delete
        │   ├── PhotoPickerPage.tsx  # Top-10 aesthetic picks
        │   └── ReportPage.tsx       # Recharts weekly trend charts
        ├── components/
        │   ├── SuggestionCard.tsx   # Compact file row with thumbnail + checkbox
        │   ├── FilePreview.tsx      # Image preview (file://) + icon fallbacks
        │   ├── ConsentModal.tsx     # Batch-capable deletion confirm dialog
        │   ├── ClutterScoreRing.tsx # Animated SVG 0–100 ring
        │   └── ProtectedBadge.tsx
        ├── store/
        │   └── scanStore.ts         # Zustand — scan state persists across navigation
        ├── hooks/
        │   ├── useScan.ts           # Thin wrapper around scanStore
        │   └── useConsent.ts        # confirm() + skip() with API calls
        └── lib/
            ├── api.ts               # Typed fetch wrapper → localhost:8000
            └── tokens.ts            # Design tokens
```

---

## API reference (Phase 1)

```
GET  /api/health
POST /api/storage/scan                   { directory: string }
GET  /api/storage/scan/{id}/status
GET  /api/storage/scan/{id}/suggestions
POST /api/photos/score                   { directory: string }
GET  /api/photos/score/{id}/top
GET  /api/protected/rules
POST /api/protected/rules                { type, value, label }
DELETE /api/protected/rules/{id}
POST /api/consent/confirm                { suggestion_id, module, action, confirmed: true }
GET  /api/report/weekly
POST /api/report/snapshot
```

---

## Privacy guarantee

The AI providers receive **only:**
- Filename (not the full path)
- File size in MB
- Days since last access
- Suggestion type (duplicate / large_file / screenshot / etc.)

File contents, photos, and personal data are **never transmitted**.

---

## Consent guarantee

Every destructive action requires:

1. An explicit checkbox: "I understand - move this file to the Recycle Bin"
2. A confirmed `POST /api/consent/confirm` call with `confirmed: true`

All consent events are logged to the `consent_log` SQLite table. Files are moved to the OS Recycle Bin via `send2trash` ,they are never permanently deleted.

---

## Running tests

```powershell
cd backend
venv\Scripts\Activate.ps1
pytest tests/ -v
# 21 passed
```
 
---

## Phase 2 ( yet to build)

Gmail triage · Google Drive dedup · True Unsubscribe Engine · Smart Auto-Organizer · Subscription Spend Tracker · Mobile (Expo)
