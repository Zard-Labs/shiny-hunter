"""Database configuration and setup."""
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

from app.config import is_packaged, get_user_data_path

# Database file path — use user data dir in packaged mode so it survives upgrades
if is_packaged():
    DB_PATH = get_user_data_path() / "shiny_hunter.db"
else:
    DB_PATH = Path(__file__).parent.parent / "shiny_hunter.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def _table_exists(inspector, table_name: str) -> bool:
    """Check if a table exists."""
    return table_name in inspector.get_table_names()


def _migrate_db():
    """Run lightweight migrations for schema changes.
    
    Adds new columns and tables that don't exist yet,
    and backfills existing data into a default hunt.
    """
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        # --- Create hunts table if missing ---
        if not _table_exists(inspector, 'hunts'):
            conn.execute(text("""
                CREATE TABLE hunts (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(100),
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ended_at DATETIME,
                    total_encounters INTEGER DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'active'
                )
            """))
            conn.execute(text("""
                CREATE INDEX idx_hunt_status ON hunts (status)
            """))
            conn.commit()
        
        # --- Add hunt_id column to encounters if missing ---
        if _table_exists(inspector, 'encounters') and not _column_exists(inspector, 'encounters', 'hunt_id'):
            conn.execute(text("""
                ALTER TABLE encounters ADD COLUMN hunt_id VARCHAR(36)
            """))
            conn.execute(text("""
                CREATE INDEX idx_hunt ON encounters (hunt_id)
            """))
            conn.commit()
        
        # --- Add hunt_id column to sessions if missing ---
        if _table_exists(inspector, 'sessions') and not _column_exists(inspector, 'sessions', 'hunt_id'):
            conn.execute(text("""
                ALTER TABLE sessions ADD COLUMN hunt_id VARCHAR(36)
            """))
            conn.commit()
        
        # --- Ensure there's an active hunt; backfill orphaned data ---
        result = conn.execute(text("SELECT id FROM hunts WHERE status = 'active' LIMIT 1"))
        active_hunt = result.fetchone()
        
        if active_hunt is None:
            # Check if there are existing encounters without a hunt_id
            result = conn.execute(text("SELECT COUNT(*) FROM encounters WHERE hunt_id IS NULL"))
            orphaned_count = result.scalar()
            
            # Create the default hunt
            hunt_id = str(uuid.uuid4())
            hunt_name = "Hunt #1" if orphaned_count > 0 else "Hunt #1"
            conn.execute(text("""
                INSERT INTO hunts (id, name, started_at, total_encounters, status)
                VALUES (:id, :name, :started_at, :total, 'active')
            """), {
                "id": hunt_id,
                "name": hunt_name,
                "started_at": datetime.utcnow().isoformat(),
                "total": orphaned_count
            })
            
            # Backfill orphaned encounters
            if orphaned_count > 0:
                conn.execute(text("""
                    UPDATE encounters SET hunt_id = :hunt_id WHERE hunt_id IS NULL
                """), {"hunt_id": hunt_id})
            
            # Backfill orphaned sessions
            conn.execute(text("""
                UPDATE sessions SET hunt_id = :hunt_id WHERE hunt_id IS NULL
            """), {"hunt_id": hunt_id})
            
            conn.commit()


def init_db():
    """Initialize database tables and run migrations."""
    # Create any brand-new tables
    Base.metadata.create_all(bind=engine)
    # Run migrations for existing databases
    _migrate_db()
