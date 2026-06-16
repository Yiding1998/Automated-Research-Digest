from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from .config import env_value
from .http import HTTPClient


def write_digest(path: str | Path, body: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def send_email(config: dict[str, Any], subject: str, body: str) -> None:
    settings = config.get("delivery", {}).get("email", {})
    host = _setting_or_env(settings, "smtp_host", "smtp_host_env")
    port = int(_setting_or_env(settings, "smtp_port", "smtp_port_env", "587"))
    username = _setting_or_env(settings, "username", "username_env")
    password = _setting_or_env(settings, "password", "password_env")
    sender = _setting_or_env(settings, "from", "from_env", username)
    recipients = _recipient_list(settings)

    missing = []
    for label, value in [("SMTP_HOST", host), ("SMTP_FROM", sender), ("SMTP_TO", recipients)]:
        if not value:
            missing.append(label)
    if missing:
        raise RuntimeError(f"missing email settings: {', '.join(missing)}")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    if port == 465:
        with smtplib.SMTP_SSL(host, port) as smtp:
            _login_if_needed(smtp, username, password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(host, port) as smtp:
        if settings.get("use_starttls", True):
            smtp.starttls()
        _login_if_needed(smtp, username, password)
        smtp.send_message(message)


def send_webhook(config: dict[str, Any], body: str) -> None:
    settings = config.get("delivery", {}).get("webhook", {})
    url = env_value(settings.get("url_env"))
    if not url:
        raise RuntimeError("missing webhook URL")
    HTTPClient(timeout=20).post_json(url, {"text": body})


def _login_if_needed(smtp: smtplib.SMTP, username: str, password: str) -> None:
    if username and password:
        smtp.login(username, password)


def _setting_or_env(settings: dict[str, Any], direct_key: str, env_key: str, default: str = "") -> str:
    value = settings.get(direct_key)
    if value not in (None, ""):
        return str(value)
    return env_value(settings.get(env_key), default)


def _recipient_list(settings: dict[str, Any]) -> list[str]:
    configured = settings.get("to", [])
    recipients: list[str] = []
    if isinstance(configured, str):
        recipients.extend(value.strip() for value in configured.split(",") if value.strip())
    elif isinstance(configured, list):
        recipients.extend(str(value).strip() for value in configured if str(value).strip())

    recipients.extend(value.strip() for value in env_value(settings.get("to_env")).split(",") if value.strip())
    return list(dict.fromkeys(recipients))
