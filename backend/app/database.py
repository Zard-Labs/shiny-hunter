"""Database configuration and setup."""
import json
import shutil
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


# ── Default Charmander template definition ─────────────────────────
DEFAULT_TEMPLATE_DEFINITION = {
    "version": 1,
    "detection": {
        "method": "yellow_star_pixels",
        "zone": {"upper_x": 264, "upper_y": 109, "lower_x": 312, "lower_y": 151},
        "threshold": 20,
        "color_bounds": {
            "lower_hsv": [20, 100, 150],
            "upper_hsv": [35, 255, 255]
        }
    },
    "gender_detection": {
        "enabled": True,
        "zone": {}
    },
    "nature_detection": {
        "enabled": True,
        "zone": {}
    },
    "soft_reset": {
        "hold_duration": 0.5,
        "wait_after": 3.0,
        "max_retries": 3
    },
    "steps": [
        {
            "name": "BOOT",
            "display_name": "Boot and Navigate Menus",
            "type": "navigate",
            "cooldown": 0.6,
            "rules": [
                {
                    "condition": {"type": "template_match", "template": "nickname_screen", "threshold": 0.75},
                    "actions": [
                        {"type": "press_button", "button": "START", "wait": 0.5},
                        {"type": "press_button", "button": "A", "wait": 0.5}
                    ],
                    "transition": "OVERWORLD"
                },
                {
                    "condition": {"type": "template_match", "template": "load_game", "threshold": 0.70},
                    "actions": [{"type": "press_button", "button": "A"}]
                },
                {
                    "condition": {"type": "template_match", "template": "title_screen", "threshold": 0.80},
                    "actions": [{"type": "press_button", "button": "A"}]
                }
            ],
            "default_action": [{"type": "press_button", "button": "A"}]
        },
        {
            "name": "OVERWORLD",
            "display_name": "Navigate Oaks Lab",
            "type": "navigate",
            "cooldown": 0.6,
            "rules": [
                {
                    "condition": {"type": "template_match", "template": "oak_lab", "threshold": 0.90},
                    "actions": [],
                    "transition": "OVERWORLD_WAIT"
                }
            ],
            "default_action": [
                {"type": "press_button", "button": "A", "wait": 0.5},
                {"type": "press_button", "button": "START", "wait": 0.5}
            ]
        },
        {
            "name": "OVERWORLD_WAIT",
            "display_name": "Wait for Text to Clear",
            "type": "timed_wait",
            "duration": 7.0,
            "during_wait_action": [{"type": "press_button", "button": "A", "wait": 1.0}],
            "on_complete_actions": [{"type": "press_button", "button": "START", "wait": 1.0}],
            "transition": "MENU"
        },
        {
            "name": "MENU",
            "display_name": "Navigate to Summary Screen",
            "type": "navigate",
            "cooldown": 0.8,
            "rules": [
                {
                    "condition": {"type": "template_match", "template": "summary_screen", "threshold": 0.85},
                    "actions": [],
                    "transition": "CHECK"
                },
                {
                    "condition": {"type": "template_match", "template": "choose_pokemon", "threshold": 0.85},
                    "actions": [{"type": "press_button", "button": "A", "wait": 0.5}]
                },
                {
                    "condition": {"type": "template_match", "template": "pokemon_menu", "threshold": 0.85},
                    "actions": [{"type": "press_button", "button": "A", "wait": 0.1}]
                }
            ]
        },
        {
            "name": "CHECK",
            "display_name": "Shiny Check",
            "type": "shiny_check",
            "pre_check_delay": 1.5,
            "buffer_flush_frames": 20,
            "collect_gender": True,
            "collect_nature": True,
            "on_shiny": "STOP",
            "on_normal_actions": [{"type": "soft_reset"}],
            "on_normal_transition": "BOOT"
        }
    ]
}

# Template image definitions for the default Charmander template
_DEFAULT_TEMPLATE_IMAGES = {
    "title_screen":    {"label": "Title Screen",     "description": "The game's main title/start screen",  "filename": "title_screen.png",    "threshold": 0.80},
    "load_game":       {"label": "Load Game Menu",   "description": "The Continue / load save menu",       "filename": "load_game.png",       "threshold": 0.70},
    "nickname_screen": {"label": "Nickname Screen",  "description": "The Give a nickname? prompt",         "filename": "nickname_screen.png", "threshold": 0.75},
    "oak_lab":         {"label": "Oak's Lab",        "description": "Professor Oak in his lab",             "filename": "oak_lab.png",         "threshold": 0.90},
    "pokemon_menu":    {"label": "Pokemon Menu",     "description": "The Pokemon party menu screen",       "filename": "pokemon_menu.png",    "threshold": 0.85},
    "choose_pokemon":  {"label": "Choose Pokemon",   "description": "Starter selection screen",            "filename": "choose_pokemon.png",  "threshold": 0.85},
    "summary_screen":  {"label": "Summary Screen",   "description": "Pokemon summary showing nature/stats","filename": "summary_screen.png",  "threshold": 0.85},
}


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
        
        # --- Add automation_template_id column to hunts if missing ---
        if _table_exists(inspector, 'hunts') and not _column_exists(inspector, 'hunts', 'automation_template_id'):
            conn.execute(text("""
                ALTER TABLE hunts ADD COLUMN automation_template_id VARCHAR(36)
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
        
        # --- Seed default automation template ---
        _seed_default_template(conn, inspector)


def _seed_default_template(conn, inspector):
    """Create the default Charmander automation template if none exists.
    
    Also copies any existing template images from the legacy
    ``templates/pokemon_red/`` directory into the per-template folder.
    """
    if not _table_exists(inspector, 'automation_templates'):
        return  # Table created by create_all, but just in case
    
    result = conn.execute(text("SELECT COUNT(*) FROM automation_templates"))
    if result.scalar() > 0:
        return  # Already seeded
    
    template_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    conn.execute(text("""
        INSERT INTO automation_templates
            (id, name, description, game, pokemon_name, definition, is_active, created_at, updated_at, version)
        VALUES
            (:id, :name, :desc, :game, :pokemon, :definition, 1, :now, :now, 1)
    """), {
        "id": template_id,
        "name": "Starter Charmander Hunt",
        "desc": "Soft-reset starter Charmander shiny hunt in Pokemon Red. "
                "Boot → navigate Oak's lab → check summary → reset.",
        "game": "Pokemon Red",
        "pokemon": "Charmander",
        "definition": json.dumps(DEFAULT_TEMPLATE_DEFINITION),
        "now": now,
    })
    
    # Insert template image rows
    for key, info in _DEFAULT_TEMPLATE_IMAGES.items():
        img_id = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO template_images
                (id, automation_template_id, key, label, description, threshold, created_at)
            VALUES
                (:id, :tmpl_id, :key, :label, :desc, :threshold, :now)
        """), {
            "id": img_id,
            "tmpl_id": template_id,
            "key": key,
            "label": info["label"],
            "desc": info["description"],
            "threshold": info["threshold"],
            "now": now,
        })
    
    # Link the active hunt to this template
    conn.execute(text("""
        UPDATE hunts SET automation_template_id = :tmpl_id
        WHERE status = 'active' AND automation_template_id IS NULL
    """), {"tmpl_id": template_id})
    
    conn.commit()
    
    # Copy legacy template images into per-template directory
    _copy_legacy_template_images(template_id)


def _copy_legacy_template_images(template_id: str):
    """Copy images from legacy templates/pokemon_red/ to templates/<id>/."""
    if is_packaged():
        base = get_user_data_path()
    else:
        base = Path(__file__).parent.parent
    
    legacy_dir = base / "templates" / "pokemon_red"
    new_dir = base / "templates" / template_id
    
    if not legacy_dir.exists():
        return
    
    new_dir.mkdir(parents=True, exist_ok=True)
    
    for key, info in _DEFAULT_TEMPLATE_IMAGES.items():
        src_gray = legacy_dir / info["filename"]
        src_color = legacy_dir / f"{key}_color.png"
        
        if src_gray.exists():
            shutil.copy2(str(src_gray), str(new_dir / info["filename"]))
        if src_color.exists():
            shutil.copy2(str(src_color), str(new_dir / f"{key}_color.png"))
    
    # Update image_path and color_image_path in the DB
    with engine.connect() as conn:
        for key, info in _DEFAULT_TEMPLATE_IMAGES.items():
            gray_path = new_dir / info["filename"]
            color_path = new_dir / f"{key}_color.png"
            conn.execute(text("""
                UPDATE template_images
                SET image_path = :gray, color_image_path = :color
                WHERE automation_template_id = :tmpl_id AND key = :key
            """), {
                "gray": str(gray_path) if gray_path.exists() else None,
                "color": str(color_path) if color_path.exists() else None,
                "tmpl_id": template_id,
                "key": key,
            })
        conn.commit()


def init_db():
    """Initialize database tables and run migrations."""
    # Create any brand-new tables (includes automation_templates, template_images)
    Base.metadata.create_all(bind=engine)
    # Run migrations for existing databases
    _migrate_db()
