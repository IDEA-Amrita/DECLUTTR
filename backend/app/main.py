from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db
from app.routers import storage, consent, photos, protected, report


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


app = FastAPI(title="Declutter AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(storage.router, prefix="/api")
app.include_router(consent.router, prefix="/api")
app.include_router(photos.router, prefix="/api")
app.include_router(protected.router, prefix="/api")
app.include_router(report.router, prefix="/api")
