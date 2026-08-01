from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..models import AppSetting, ProjectSetting
from .secrets_service import SENSITIVE_KEYS, decrypt_value, encrypt_value

RUNTIME_KEYS = {
    "github_token",
    "openai_api_key",
    "openrouter_api_key",
    "mcp_servers",
    "auto_push",
}


def _store(key: str, value: str) -> str:
    return encrypt_value(value) if key in SENSITIVE_KEYS else value


def get_app_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row:
        return default
    return decrypt_value(row.value) if key in SENSITIVE_KEYS else row.value


def set_app_setting(db: Session, key: str, value: str) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    stored = _store(key, value)
    if row:
        row.value = stored
    else:
        db.add(AppSetting(key=key, value=stored))
    db.commit()


def get_project_setting(db: Session, project_id: int, key: str, default: str = "") -> str:
    row = (
        db.query(ProjectSetting)
        .filter(ProjectSetting.project_id == project_id, ProjectSetting.key == key)
        .first()
    )
    return row.value if row else default


def get_runtime_settings():
    """Settings with runtime DB overrides layered on top of .env values."""
    settings = get_settings()
    db = SessionLocal()
    try:
        rows = db.query(AppSetting).filter(AppSetting.key.in_(RUNTIME_KEYS)).all()
    finally:
        db.close()
    overrides: dict = {}
    for row in rows:
        if row.value:
            value = decrypt_value(row.value) if row.key in SENSITIVE_KEYS else row.value
            if value:
                overrides[row.key] = value
    if overrides:
        return settings.model_copy(update=overrides)
    return settings


def auto_push_enabled(db: Session, project_id: int) -> bool:
    per_project = get_project_setting(db, project_id, "auto_push")
    if per_project in ("true", "1", "yes"):
        return True
    if per_project in ("false", "0", "no"):
        return False
    return get_app_setting(db, "auto_push", "false").lower() in ("true", "1", "yes")
