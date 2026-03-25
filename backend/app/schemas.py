"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


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
