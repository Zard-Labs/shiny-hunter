"""Notification service for sending push notifications on events (e.g. shiny found).

Currently supports Pushover. Designed with a provider pattern so additional
notification methods (Discord, email, etc.) can be added later.
"""
import base64
import json
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.database import SessionLocal
from app.models import Configuration
from app.utils.logger import logger

# ── Constants ────────────────────────────────────────────────────────────
PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"

# DB key prefix for notification settings
_PREFIX = "notifications."

# Default values
DEFAULTS: Dict[str, Any] = {
    "pushover.enabled": False,
    "pushover.app_token": "",
    "pushover.user_key": "",
    "pushover.priority": 1,       # -2=lowest … 2=emergency
    "pushover.sound": "persistent",
}


class NotificationService:
    """Singleton service that dispatches notifications."""

    # ── Settings helpers ─────────────────────────────────────────────

    def _db_key(self, key: str) -> str:
        """Return the full DB key for a notification setting."""
        return f"{_PREFIX}{key}"

    def get_settings(self) -> Dict[str, Any]:
        """Load all notification settings from the Configuration table."""
        db = SessionLocal()
        try:
            settings: Dict[str, Any] = {}
            for short_key, default in DEFAULTS.items():
                full_key = self._db_key(short_key)
                row = db.query(Configuration).filter(Configuration.key == full_key).first()
                if row is not None:
                    settings[short_key] = json.loads(row.value)
                else:
                    settings[short_key] = default
            return settings
        finally:
            db.close()

    def get_settings_masked(self) -> Dict[str, Any]:
        """Return settings with sensitive tokens partially masked for the UI."""
        settings = self.get_settings()
        for key in ("pushover.app_token", "pushover.user_key"):
            val = settings.get(key, "")
            if isinstance(val, str) and len(val) > 4:
                settings[key] = "*" * (len(val) - 4) + val[-4:]
        return settings

    def save_settings(self, incoming: Dict[str, Any]) -> Dict[str, Any]:
        """Persist notification settings to the Configuration table.

        If a token/key field is submitted with only asterisks + last-4 chars,
        the existing DB value is preserved (the user didn't change it).
        """
        db = SessionLocal()
        try:
            current = self.get_settings()

            for short_key in DEFAULTS:
                if short_key not in incoming:
                    continue

                new_val = incoming[short_key]

                # Preserve masked tokens — don't overwrite with asterisks
                if short_key in ("pushover.app_token", "pushover.user_key"):
                    if isinstance(new_val, str) and new_val.startswith("*"):
                        continue  # keep existing value

                full_key = self._db_key(short_key)
                row = db.query(Configuration).filter(Configuration.key == full_key).first()
                serialized = json.dumps(new_val)

                if row is not None:
                    row.value = serialized
                else:
                    row = Configuration(key=full_key, value=serialized)
                    db.add(row)

            db.commit()
            return self.get_settings_masked()
        finally:
            db.close()

    # ── Pushover sender ──────────────────────────────────────────────

    async def _send_pushover(
        self,
        message: str,
        title: str = "ShinyStarter",
        *,
        settings: Optional[Dict[str, Any]] = None,
        screenshot_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Send a Pushover notification.

        Parameters
        ----------
        message : str
            Notification body text.
        title : str
            Notification title.
        settings : dict, optional
            Override settings (used by tests so unsaved values can be tested).
        screenshot_path : Path, optional
            Path to a screenshot to attach as an image.

        Returns
        -------
        dict  with ``success`` (bool) and ``detail`` (str).
        """
        cfg = settings or self.get_settings()
        app_token = cfg.get("pushover.app_token", "")
        user_key = cfg.get("pushover.user_key", "")

        if not app_token or not user_key:
            return {"success": False, "detail": "Pushover app_token or user_key is not configured."}

        payload: Dict[str, Any] = {
            "token": app_token,
            "user": user_key,
            "message": message,
            "title": title,
            "priority": int(cfg.get("pushover.priority", 1)),
            "sound": cfg.get("pushover.sound", "persistent"),
        }

        # Emergency priority (2) requires retry + expire parameters
        if payload["priority"] == 2:
            payload["retry"] = 60
            payload["expire"] = 3600

        files = None
        if screenshot_path and screenshot_path.exists():
            try:
                image_data = screenshot_path.read_bytes()
                payload["attachment_base64"] = base64.b64encode(image_data).decode("utf-8")
                payload["attachment_type"] = "image/png"
            except Exception as exc:
                logger.warning(f"[Notifications] Could not attach screenshot: {exc}")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(PUSHOVER_API_URL, data=payload)
                body = resp.json()

                if resp.status_code == 200 and body.get("status") == 1:
                    logger.info("[Notifications] Pushover notification sent successfully.")
                    return {"success": True, "detail": "Notification sent successfully."}
                else:
                    errors = body.get("errors", [])
                    detail = "; ".join(errors) if errors else f"HTTP {resp.status_code}"
                    logger.warning(f"[Notifications] Pushover API error: {detail}")
                    return {"success": False, "detail": detail}

        except httpx.TimeoutException:
            logger.error("[Notifications] Pushover API request timed out.")
            return {"success": False, "detail": "Request timed out."}
        except Exception as exc:
            logger.error(f"[Notifications] Pushover send failed: {exc}")
            return {"success": False, "detail": str(exc)}

    # ── Public API ───────────────────────────────────────────────────

    async def send_shiny_notification(
        self,
        pokemon_name: str = "Pokémon",
        encounter_count: int = 0,
        screenshot_path: Optional[Path] = None,
        extra_text: str = "",
    ) -> None:
        """Fire-and-forget notification when a shiny is found.

        Reads the saved settings. If Pushover is disabled or not configured
        the call silently returns.

        Parameters
        ----------
        extra_text : str, optional
            Additional text to append to the message body (e.g. skip reason).
        """
        settings = self.get_settings()

        # Pushover
        if settings.get("pushover.enabled"):
            message = (
                f"✨ SHINY {pokemon_name.upper()} FOUND after "
                f"{encounter_count:,} encounters!"
            )
            if extra_text:
                message += f"\n{extra_text}"
            try:
                result = await self._send_pushover(
                    message=message,
                    title="✨ SHINY FOUND!",
                    settings=settings,
                    screenshot_path=screenshot_path,
                )
                if not result["success"]:
                    logger.warning(
                        f"[Notifications] Shiny notification failed: {result['detail']}"
                    )
            except Exception as exc:
                logger.error(f"[Notifications] Shiny notification error: {exc}")

    async def send_test_notification(
        self,
        override_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a test notification so the user can verify their config.

        Parameters
        ----------
        override_settings : dict, optional
            If provided, use these settings instead of the saved ones.
            This allows testing *before* saving.
        """
        settings = override_settings or self.get_settings()

        if settings.get("pushover.enabled", True):
            return await self._send_pushover(
                message=(
                    "🔔 ShinyStarter test notification — "
                    "if you see this, your Pushover config is working!"
                ),
                title="ShinyStarter Test",
                settings=settings,
            )

        return {"success": False, "detail": "No notification method is enabled."}


# Global singleton
notification_service = NotificationService()
