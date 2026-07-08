from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Float, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from app.config import settings 
import logging


# Create engine
engine = create_engine(
    "sqlite:///./decluttr.db",
    connect_args={"check_same_thread": False}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function for existing routers
def get_session():
    """Get database session"""
    return SessionLocal()

# Function for FastAPI dependencies
def get_db():
    """FastAPI dependency for DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)
logger = logging.getLogger(__name__)

# SQLAlchemy setup
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Scan(Base):
    """Represents a single scan session"""
    __tablename__ = "scans"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, running, completed, failed
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    duplicates_found = Column(Integer, default=0)
    near_duplicates_found = Column(Integer, default=0)
    progress_percent = Column(Float, default=0.0)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    files = relationship("FileRecord", back_populates="scan")
    
    __table_args__ = (
        Index('idx_scan_user_id', 'user_id'),
        Index('idx_scan_status', 'status'),
    )


class FileRecord(Base):
    """Represents a file from Google Drive"""
    __tablename__ = "files"
    
    id = Column(String, primary_key=True)  # Google Drive file ID
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    name = Column(String, nullable=False)
    size = Column(Integer, default=0)
    mime_type = Column(String)
    md5_hash = Column(String, nullable=True)
    phash = Column(String, nullable=True)
    is_duplicate = Column(Boolean, default=False)
    is_near_duplicate = Column(Boolean, default=False)
    is_flagged = Column(Boolean, default=False)
    duplicate_group_id = Column(String, nullable=True)  # Groups duplicates together
    created_at = Column(DateTime)
    modified_at = Column(DateTime)
    web_view_link = Column(String, nullable=True)
    
    scan = relationship("Scan", back_populates="files")
    
    __table_args__ = (
        Index('idx_file_scan_id', 'scan_id'),
        Index('idx_file_md5', 'md5_hash'),
        Index('idx_file_phash', 'phash'),
        Index('idx_file_dup_group', 'duplicate_group_id'),
    )


def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_db():
    """Dependency for FastAPI to get DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _migrate_sqlite_columns():
    """
    Idempotently add any columns that were introduced after a table was first
    created. SQLite's create_all never ALTERs existing tables, so on an already
    populated dev DB new SQLModel fields would be missing without this.
    """
    from sqlalchemy import inspect, text

    # column_name -> SQL type/default used in ADD COLUMN
    expected = {
        "drive_scan_job": {
            "phase": "TEXT",
            "clusters_found": "INTEGER DEFAULT 0",
            "deletion_candidates": "INTEGER DEFAULT 0",
        },
        "drive_file_record": {
            "duplicate_group_id": "TEXT",
            "is_cluster_original": "BOOLEAN DEFAULT 0",
            "confidence": "INTEGER DEFAULT 0",
            "user_flag": "TEXT",
            "user_description": "TEXT",
            "location_tag": "TEXT",
            "is_protected": "BOOLEAN DEFAULT 0",
            "in_deletion_list": "BOOLEAN DEFAULT 0",
            "deletion_bucket": "TEXT",
            "target_folder_path": "TEXT",
            "moved_to_folder": "TEXT",
            "is_organized": "BOOLEAN DEFAULT 0",
            "compressible": "BOOLEAN DEFAULT 0",
            "last_accessed_at": "DATETIME",
            "location_lat": "FLOAT",
            "location_lon": "FLOAT",
            "capture_date": "TEXT",
            "ai_reason": "TEXT",
            "suggested_action": "TEXT",
            "category": "TEXT",
        },
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in expected.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for col, ddl in columns.items():
                if col not in present:
                    try:
                        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}'))
                        logger.info(f"Migrated: added {table}.{col}")
                    except Exception as e:  # pragma: no cover
                        logger.warning(f"Could not add {table}.{col}: {e}")


def create_db():
    """Create all database tables (SQLAlchemy Base + SQLModel) and migrate columns."""
    Base.metadata.create_all(bind=engine)
    # SQLModel tables (DriveToken, DriveFileRecord, Suggestion, etc.) live on
    # SQLModel.metadata, not the SQLAlchemy declarative Base.
    try:
        from sqlmodel import SQLModel
        import app.models.schemas  # noqa: F401 — registers all SQLModel tables
        SQLModel.metadata.create_all(bind=engine)
        _migrate_sqlite_columns()
    except Exception as e:  # pragma: no cover
        logger.error(f"SQLModel table creation/migration failed: {e}")
