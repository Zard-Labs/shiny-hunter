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


# ── Seed template helpers ──────────────────────────────────────────


def _seed_templates_base() -> Path:
    """Return the base directory for bundled seed templates.

    In development this is ``backend/seed_templates/``.
    In a PyInstaller package the directory is bundled inside the exe.
    """
    if is_packaged():
        import sys
        return Path(getattr(sys, '_MEIPASS', '')) / "seed_templates"
    return Path(__file__).parent.parent / "seed_templates"


def _templates_runtime_base() -> Path:
    """Return the runtime directory where per-template image folders live."""
    if is_packaged():
        return get_user_data_path() / "templates"
    return Path(__file__).parent.parent / "templates"


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
        
        # --- Add video_clip_path column to encounters if missing ---
        if _table_exists(inspector, 'encounters') and not _column_exists(inspector, 'encounters', 'video_clip_path'):
            conn.execute(text("""
                ALTER TABLE encounters ADD COLUMN video_clip_path VARCHAR(255)
            """))
            conn.commit()
        
        # --- Add automation_template_id column to hunts if missing ---
        if _table_exists(inspector, 'hunts') and not _column_exists(inspector, 'hunts', 'automation_template_id'):
            conn.execute(text("""
                ALTER TABLE hunts ADD COLUMN automation_template_id VARCHAR(36)
            """))
            conn.commit()
        
        # --- Add skipped_reason column to encounters if missing ---
        if _table_exists(inspector, 'encounters') and not _column_exists(inspector, 'encounters', 'skipped_reason'):
            conn.execute(text("""
                ALTER TABLE encounters ADD COLUMN skipped_reason VARCHAR(255)
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
        
        # --- Migrate battle sparkle detection thresholds ---
        # The original thresholds (spark_threshold=10, peak_threshold=50) caused
        # every encounter to false-positive as shiny.  Update any template that
        # still has the broken defaults to the new variance-aware values.
        if _table_exists(inspector, 'automation_templates'):
            _migrate_sparkle_thresholds(conn)
        
        # --- Seed automation templates from seed_templates/ ---
        _seed_templates_from_directory(conn, inspector)


def _migrate_sparkle_thresholds(conn):
    """Update battle sparkle detection thresholds in existing templates.

    The original defaults (spark_threshold=10, peak_threshold=50) were far
    too low: the HSV mask matches ~28 000 bright pixels on a normal battle
    screen, so every encounter false-positived as shiny.

    This migration patches any stored template definition whose detection
    method is ``battle_sparkle`` and still carries the broken defaults,
    replacing them with the new variance-aware values.
    """
    rows = conn.execute(text(
        "SELECT id, definition FROM automation_templates WHERE definition IS NOT NULL"
    )).fetchall()

    updated = 0
    for row in rows:
        try:
            defn = json.loads(row[1])
        except (json.JSONDecodeError, TypeError):
            continue

        det = defn.get("detection", {})
        if det.get("method") != "battle_sparkle":
            continue

        # Only patch if still carrying the broken defaults
        needs_patch = (
            det.get("spark_threshold") == 10
            or det.get("peak_threshold") == 50
            or "min_variance" not in det
        )
        if not needs_patch:
            continue

        # Patch detection block
        det["spark_threshold"] = 500
        det["peak_threshold"] = 1000
        det.setdefault("min_spike_frames", 3)
        det["spike_delta_pct"] = 0.15
        det["min_variance"] = 50.0
        defn["detection"] = det

        # Also patch any battle_shiny_check steps
        for step in defn.get("steps", []):
            if step.get("type") == "battle_shiny_check":
                step["spark_threshold"] = 500
                step["peak_threshold"] = 1000
                step.setdefault("min_spike_frames", 3)
                step["spike_delta_pct"] = 0.15
                step["min_variance"] = 50.0

        conn.execute(text(
            "UPDATE automation_templates SET definition = :defn WHERE id = :id"
        ), {"defn": json.dumps(defn), "id": row[0]})
        updated += 1

    if updated:
        conn.commit()
        print(f"[migrate] Updated sparkle thresholds in {updated} template(s)")


def _backfill_template_images(conn, template_id, seed_data, seed_dir, runtime_base, now):
    """Backfill missing template_images rows and image files for an existing template.

    Called during startup when a seed template already exists in the DB
    but may be missing its ``template_images`` rows or image files on disk
    (e.g. the user upgraded from an older version that didn't seed images).
    """
    seed_images = seed_data.get("images", [])
    if not seed_images:
        return  # Nothing to backfill

    # Check which image keys already exist in the DB for this template
    existing_rows = conn.execute(
        text("SELECT key FROM template_images WHERE automation_template_id = :tid"),
        {"tid": template_id},
    ).fetchall()
    existing_keys = {row[0] for row in existing_rows}

    # Insert any missing template_images rows
    added = 0
    for img_info in seed_images:
        key = img_info.get("key", "")
        if not key or key in existing_keys:
            continue
        conn.execute(text("""
            INSERT INTO template_images
                (id, automation_template_id, key, label,
                 description, threshold, created_at)
            VALUES
                (:id, :tmpl_id, :key, :label,
                 :desc, :threshold, :now)
        """), {
            "id": str(uuid.uuid4()),
            "tmpl_id": template_id,
            "key": key,
            "label": img_info.get("label", key.replace("_", " ").title()),
            "desc": img_info.get("description", ""),
            "threshold": img_info.get("threshold", 0.80),
            "now": now,
        })
        added += 1

    # Copy any missing seed image files into the runtime directory
    seed_images_dir = seed_dir / "images"
    tmpl_runtime_dir = runtime_base / template_id
    tmpl_runtime_dir.mkdir(parents=True, exist_ok=True)

    if seed_images_dir.exists():
        for src_file in seed_images_dir.iterdir():
            if src_file.is_file() and src_file.suffix.lower() == ".png":
                dst_file = tmpl_runtime_dir / src_file.name
                if not dst_file.exists():
                    shutil.copy2(str(src_file), str(dst_file))

    # Update image_path / color_image_path for any newly-added rows
    for img_info in seed_images:
        key = img_info.get("key", "")
        if not key:
            continue
        gray_path = tmpl_runtime_dir / f"{key}.png"
        color_path = tmpl_runtime_dir / f"{key}_color.png"
        conn.execute(text("""
            UPDATE template_images
            SET image_path = COALESCE(image_path, :gray),
                color_image_path = COALESCE(color_image_path, :color)
            WHERE automation_template_id = :tmpl_id AND key = :key
              AND (image_path IS NULL OR color_image_path IS NULL)
        """), {
            "gray": str(gray_path) if gray_path.exists() else None,
            "color": str(color_path) if color_path.exists() else None,
            "tmpl_id": template_id,
            "key": key,
        })

    if added > 0:
        conn.commit()
        print(f"[seed] Backfilled {added} missing image(s) for template '{seed_data.get('name', '?')}' (id={template_id})")


def _seed_templates_from_directory(conn, inspector):
    """Scan ``seed_templates/`` and seed any bundled automation templates.

    Each subdirectory containing a ``definition.json`` is treated as a
    seed template.  For every seed template we:

    1. Check if a template with the same **name** already exists in the DB.
       If it does we skip it — even if the user modified the steps.
    2. Create an ``automation_templates`` row with a fresh UUID.
    3. Create ``template_images`` rows for each image entry.
    4. Copy the reference images into ``templates/<new-uuid>/``.

    This is safe to run on every startup: existing templates are never
    overwritten.  New community-contributed seed templates are added
    automatically when the user updates the app.
    """
    if not _table_exists(inspector, 'automation_templates'):
        return  # Table not yet created

    seed_base = _seed_templates_base()
    if not seed_base.exists():
        return  # No seed data available

    runtime_base = _templates_runtime_base()
    now = datetime.utcnow().isoformat()

    # Check if there are ANY existing templates (used to decide active flag)
    existing_count = conn.execute(
        text("SELECT COUNT(*) FROM automation_templates")
    ).scalar()
    first_template_id = None
    seeded_count = 0

    # Sort directories so seed order is deterministic (alphabetical)
    seed_dirs = sorted(
        [d for d in seed_base.iterdir() if d.is_dir() and (d / "definition.json").exists()]
    )

    for seed_dir in seed_dirs:
        definition_path = seed_dir / "definition.json"
        try:
            with open(definition_path, "r", encoding="utf-8") as f:
                seed_data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[seed] Skipping {seed_dir.name}: {exc}")
            continue

        seed_name = seed_data.get("name", seed_dir.name)

        # ── Check if a template with this name already exists ────
        existing_row = conn.execute(
            text("SELECT id FROM automation_templates WHERE name = :name"),
            {"name": seed_name},
        ).fetchone()
        if existing_row is not None:
            # Template exists — but backfill any missing image rows and files
            # (handles upgrades from older versions that didn't seed images)
            _backfill_template_images(
                conn, existing_row[0], seed_data, seed_dir, runtime_base, now,
            )
            continue

        template_id = str(uuid.uuid4())
        # Set the first seeded template as active ONLY if the DB was empty
        is_first = (first_template_id is None) and (existing_count == 0)
        if first_template_id is None:
            first_template_id = template_id

        # ── Insert automation_template row ──────────────────────
        conn.execute(text("""
            INSERT INTO automation_templates
                (id, name, description, game, pokemon_name,
                 definition, is_active, created_at, updated_at, version)
            VALUES
                (:id, :name, :desc, :game, :pokemon,
                 :definition, :active, :now, :now, 1)
        """), {
            "id": template_id,
            "name": seed_data.get("name", seed_dir.name),
            "desc": seed_data.get("description", ""),
            "game": seed_data.get("game", "Unknown"),
            "pokemon": seed_data.get("pokemon_name", "Unknown"),
            "definition": json.dumps(seed_data.get("definition", {})),
            "active": 1 if is_first else 0,
            "now": now,
        })

        # ── Insert template_image rows ──────────────────────────
        for img_info in seed_data.get("images", []):
            img_id = str(uuid.uuid4())
            key = img_info.get("key", "")
            conn.execute(text("""
                INSERT INTO template_images
                    (id, automation_template_id, key, label,
                     description, threshold, created_at)
                VALUES
                    (:id, :tmpl_id, :key, :label,
                     :desc, :threshold, :now)
            """), {
                "id": img_id,
                "tmpl_id": template_id,
                "key": key,
                "label": img_info.get("label", key.replace("_", " ").title()),
                "desc": img_info.get("description", ""),
                "threshold": img_info.get("threshold", 0.80),
                "now": now,
            })

        # ── Copy seed images into per-template runtime directory ─
        seed_images_dir = seed_dir / "images"
        tmpl_runtime_dir = runtime_base / template_id
        tmpl_runtime_dir.mkdir(parents=True, exist_ok=True)

        if seed_images_dir.exists():
            for src_file in seed_images_dir.iterdir():
                if src_file.is_file() and src_file.suffix.lower() == ".png":
                    dst_file = tmpl_runtime_dir / src_file.name
                    shutil.copy2(str(src_file), str(dst_file))

        # ── Update image_path / color_image_path in DB ──────────
        for img_info in seed_data.get("images", []):
            key = img_info.get("key", "")
            gray_path = tmpl_runtime_dir / f"{key}.png"
            color_path = tmpl_runtime_dir / f"{key}_color.png"
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

        seeded_count += 1
        print(f"[seed] Seeded template '{seed_name}' "
              f"(id={template_id}, images={len(seed_data.get('images', []))})")

    # Link the first seeded template to the active hunt (only on fresh DB)
    if first_template_id and existing_count == 0:
        conn.execute(text("""
            UPDATE hunts SET automation_template_id = :tmpl_id
            WHERE status = 'active' AND automation_template_id IS NULL
        """), {"tmpl_id": first_template_id})

    if seeded_count > 0:
        conn.commit()
        print(f"[seed] Done — seeded {seeded_count} new template(s)")
    else:
        print("[seed] All seed templates already present — nothing to add")


def init_db():
    """Initialize database tables and run migrations."""
    # Create any brand-new tables (includes automation_templates, template_images)
    Base.metadata.create_all(bind=engine)
    # Run migrations for existing databases
    _migrate_db()
