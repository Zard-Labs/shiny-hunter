"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


# ── Automation Template schemas ──────────────────────────────────────

class AutomationTemplateCreate(BaseModel):
    """Create a new automation template."""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    game: str = Field(default="Pokemon Red", max_length=50)
    pokemon_name: str = Field(default="Charmander", max_length=50)
    definition: Dict[str, Any] = Field(..., description="JSON definition with steps, detection, etc.")


class AutomationTemplateUpdate(BaseModel):
    """Update an existing automation template."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    game: Optional[str] = Field(None, max_length=50)
    pokemon_name: Optional[str] = Field(None, max_length=50)
    definition: Optional[Dict[str, Any]] = None


class AutomationTemplateResponse(BaseModel):
    """Automation template with metadata (no full definition)."""
    id: str
    name: str
    description: Optional[str] = None
    game: str
    pokemon_name: str
    is_active: bool
    version: int
    step_count: int = 0
    image_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutomationTemplateDetail(BaseModel):
    """Full automation template with definition included."""
    id: str
    name: str
    description: Optional[str] = None
    game: str
    pokemon_name: str
    definition: Dict[str, Any]
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    images: List["TemplateImageResponse"] = []

    class Config:
        from_attributes = True


class TemplateImageResponse(BaseModel):
    """Template image metadata."""
    id: str
    automation_template_id: str
    key: str
    label: Optional[str] = None
    description: Optional[str] = None
    threshold: float = 0.80
    captured: bool = False
    preview_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateImageCapture(BaseModel):
    """Request to capture a template image from the current frame."""
    key: str = Field(..., max_length=50)
    label: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    threshold: float = Field(default=0.80, ge=0.0, le=1.0)


# ── Encounter schemas ────────────────────────────────────────────────

# Encounter schemas
class EncounterBase(BaseModel):
    encounter_number: int
    pokemon_name: str = "Charmander"
    is_shiny: bool
    gender: Optional[str] = None
    nature: Optional[str] = None
    session_id: Optional[str] = None
    hunt_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    detection_confidence: Optional[float] = None
    state_at_capture: Optional[str] = None


class EncounterCreate(EncounterBase):
    pass


class EncounterResponse(EncounterBase):
    id: int
    timestamp: datetime
    
    class Config:
        from_attributes = True


# Session schemas
class SessionBase(BaseModel):
    status: str = "active"


class SessionCreate(SessionBase):
    id: str  # UUID


class SessionResponse(SessionBase):
    id: str
    hunt_id: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_encounters: int = 0
    shiny_found: bool = False
    
    class Config:
        from_attributes = True


# Hunt schemas
class HuntResponse(BaseModel):
    id: str
    name: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_encounters: int = 0
    status: str = "active"
    
    class Config:
        from_attributes = True


# Configuration schemas
class ConfigUpdate(BaseModel):
    key: str
    value: str


class ConfigResponse(BaseModel):
    key: str
    value: str
    updated_at: datetime
    
    class Config:
        from_attributes = True


# API request/response schemas
class ButtonCommand(BaseModel):
    button: str = Field(..., description="Button to press: A, B, START, UP, DOWN, LEFT, RIGHT, RESET")


class AutomationStatus(BaseModel):
    is_running: bool
    state: str
    encounter_count: int
    session_id: Optional[str] = None


class StatisticsResponse(BaseModel):
    encounters: int
    natures: Dict[str, int]
    genders: Dict[str, int]
    last_encounter: Optional[Dict] = None
    hunt_id: Optional[str] = None
    hunt_name: Optional[str] = None


class HistoryResponse(BaseModel):
    total: int
    encounters: List[EncounterResponse]


class CalibrationZone(BaseModel):
    zone_type: str = Field(..., description="shiny or gender")
    coordinates: Dict[str, int] = Field(..., description="Dict with ux, uy, lx, ly keys")


# WebSocket message schemas
class WSMessage(BaseModel):
    type: str
    data: Dict


class StateUpdate(BaseModel):
    state: str
    encounter_number: int
    is_running: bool


class EncounterDetected(BaseModel):
    encounter_number: int
    gender: str
    nature: str
    is_shiny: bool
    screenshot_url: str


class ShinyFound(BaseModel):
    encounter_number: int
    screenshot_url: str
    timestamp: str


class ErrorMessage(BaseModel):
    message: str
    severity: str
