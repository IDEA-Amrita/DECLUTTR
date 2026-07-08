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

def create_db():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    from sqlmodel import SQLModel
    from app.models import schemas, gdrive_schemas
    SQLModel.metadata.create_all(bind=engine)