"""REST API routes for notification settings (Pushover, etc.)."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict, Optional

from app.services.notification_service import notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ── Schemas ──────────────────────────────────────────────────────────────

class NotificationSettingsUpdate(BaseModel):
    """Incoming payload for saving notification settings.

    Every field is optional — only supplied keys are updated.
    """
    pushover_enabled: Optional[bool] = None
    pushover_app_token: Optional[str] = None
    pushover_user_key: Optional[str] = None
    pushover_priority: Optional[int] = None
    pushover_sound: Optional[str] = None


class TestNotificationRequest(BaseModel):
    """Optionally override settings for a test notification.

    If fields are supplied they are used instead of the saved values,
    so the user can test *before* saving.
    """
    pushover_enabled: Optional[bool] = None
    pushover_app_token: Optional[str] = None
    pushover_user_key: Optional[str] = None
    pushover_priority: Optional[int] = None
    pushover_sound: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────

def _schema_to_settings(data: dict) -> Dict[str, Any]:
    """Convert flat schema keys (pushover_enabled) → dotted keys (pushover.enabled)."""
    mapping = {
        "pushover_enabled": "pushover.enabled",
        "pushover_app_token": "pushover.app_token",
        "pushover_user_key": "pushover.user_key",
        "pushover_priority": "pushover.priority",
        "pushover_sound": "pushover.sound",
    }
    out: Dict[str, Any] = {}
    for schema_key, dotted_key in mapping.items():
        val = data.get(schema_key)
        if val is not None:
            out[dotted_key] = val
    return out


def _settings_to_response(settings: Dict[str, Any]) -> dict:
    """Convert dotted keys → flat response keys for the frontend."""
    return {
        "pushover_enabled": settings.get("pushover.enabled", False),
        "pushover_app_token": settings.get("pushover.app_token", ""),
        "pushover_user_key": settings.get("pushover.user_key", ""),
        "pushover_priority": settings.get("pushover.priority", 1),
        "pushover_sound": settings.get("pushover.sound", "persistent"),
    }


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/settings")
def get_notification_settings():
    """Return current notification settings (tokens masked)."""
    masked = notification_service.get_settings_masked()
    return _settings_to_response(masked)


@router.put("/settings")
def update_notification_settings(payload: NotificationSettingsUpdate):
    """Save notification settings."""
    incoming = _schema_to_settings(payload.model_dump(exclude_none=True))
    updated = notification_service.save_settings(incoming)
    return _settings_to_response(updated)


@router.post("/test")
async def send_test_notification(payload: TestNotificationRequest = None):
    """Send a test push notification.

    If the request body contains override values they are used instead of
    the saved settings, so the user can test *before* saving.
    """
    override = None
    if payload:
        override_raw = _schema_to_settings(payload.model_dump(exclude_none=True))
        if override_raw:
            # Merge overrides on top of saved settings
            saved = notification_service.get_settings()
            saved.update(override_raw)
            override = saved

    result = await notification_service.send_test_notification(override)
    return result
