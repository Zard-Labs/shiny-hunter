"""Database models."""
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class Hunt(Base):
    """Hunt table for grouping encounters into hunting runs.
    
    A hunt represents a complete shiny hunting attempt. When the user
    'resets stats', the current hunt is archived and a new one is created.
    There is always exactly one active hunt at a time.
    """
    __tablename__ = "hunts"
    
    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(100), nullable=True)  # Optional display name
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
