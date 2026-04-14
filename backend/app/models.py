"""Database models."""
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, Index
from sqlalchemy.sql import func
from app.database import Base


class AutomationTemplate(Base):
    """Automation template defining a complete hunt workflow.
    
    Each template is a self-contained recipe: the state-machine steps,
    detection config, soft-reset timing and the list of required
    screenshot templates — all serialised as a JSON blob in `definition`.
    
    Only one template may be active at a time (is_active=True).
    """
    __tablename__ = "automation_templates"
    
    id = Column(String(36), primary_key=True)               # UUID
    name = Column(String(100), nullable=False)               # e.g. "Starter Charmander Hunt"
    description = Column(Text, nullable=True)                # Optional long description
    game = Column(String(50), default="Pokemon Red")         # Game title
    pokemon_name = Column(String(50), default="Charmander")  # Target Pokemon
    definition = Column(Text, nullable=False)                # JSON blob (steps, rules, detection)
    is_active = Column(Boolean, default=False)               # Currently selected template
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    version = Column(Integer, default=1)
    
    __table_args__ = (
        Index('idx_template_active', 'is_active'),
    )


class TemplateImage(Base):
    """Screenshot template image belonging to an automation template.
    
    Each automation template references a set of screen-matching images
    (e.g. title screen, summary screen).  Images are stored on the
    filesystem under ``templates/<automation_template_id>/``.
    """
    __tablename__ = "template_images"
    
    id = Column(String(36), primary_key=True)                              # UUID
    automation_template_id = Column(String(36), nullable=False, index=True)  # FK (logical)
    key = Column(String(50), nullable=False)                               # e.g. "title_screen"
    label = Column(String(100), nullable=True)                             # Display label
    description = Column(String(255), nullable=True)                       # What this screenshot shows
    image_path = Column(String(255), nullable=True)                        # Grayscale PNG path
    color_image_path = Column(String(255), nullable=True)                  # Color preview path
    threshold = Column(Float, default=0.80)                                # Match confidence threshold
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_tmpl_img_template', 'automation_template_id'),
        Index('idx_tmpl_img_key', 'automation_template_id', 'key', unique=True),
    )


class Hunt(Base):
    """Hunt table for grouping encounters into hunting runs.
    
    A hunt represents a complete shiny hunting attempt. When the user
    'resets stats', the current hunt is archived and a new one is created.
    There is always exactly one active hunt at a time.
    """
    __tablename__ = "hunts"
    
    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(100), nullable=True)  # Optional display name
    automation_template_id = Column(String(36), nullable=True)  # FK to active template at hunt creation
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    total_encounters = Column(Integer, default=0)
    status = Column(String(20), default='active')  # 'active', 'archived'
    
    __table_args__ = (
        Index('idx_hunt_status', 'status'),
    )


class Encounter(Base):
    """Encounter table storing all Pokemon encounters."""
    __tablename__ = "encounters"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    encounter_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    pokemon_name = Column(String(20), default="Charmander")
    is_shiny = Column(Boolean, nullable=False)
    gender = Column(String(10))  # 'Male', 'Female', 'Unknown'
    nature = Column(String(50))  # e.g., 'Adamant/Firme'
    session_id = Column(String(36))  # UUID for grouping sessions
    hunt_id = Column(String(36))  # UUID linking to active hunt
    screenshot_path = Column(String(255))
    detection_confidence = Column(Float)  # 0.0 - 1.0
    state_at_capture = Column(String(50))  # State machine phase
    
    __table_args__ = (
        Index('idx_session', 'session_id'),
        Index('idx_hunt', 'hunt_id'),
        Index('idx_shiny', 'is_shiny'),
        Index('idx_timestamp', 'timestamp'),
    )


class Session(Base):
    """Session table for grouping hunting sessions."""
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True)  # UUID
    hunt_id = Column(String(36))  # UUID linking to active hunt
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    total_encounters = Column(Integer, default=0)
    shiny_found = Column(Boolean, default=False)
    status = Column(String(20))  # 'active', 'completed', 'stopped'


class Configuration(Base):
    """Configuration table for storing calibration settings."""
    __tablename__ = "configuration"
    
    key = Column(String(100), primary_key=True)
    value = Column(String)  # JSON serialized values
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
