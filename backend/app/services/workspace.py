import json
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Project
from ..schemas import ProjectCreate


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def create_workspace(db: Session, data: ProjectCreate) -> Project:
    settings = get_settings()
    root = settings.projects_root_path
    root.mkdir(parents=True, exist_ok=True)
    base_slug = slugify(data.name)
    slug = base_slug
    n = 1
    while (root / slug).exists():
        n += 1
        slug = f"{base_slug}-{n}"
    project_dir = root / slug
    source_dir = project_dir / "source"
    meta_dir = project_dir / ".arynox"
    logs_dir = project_dir / "logs"
    tests_dir = project_dir / "tests"
    for d in (project_dir, source_dir, meta_dir, logs_dir, tests_dir):
        d.mkdir(parents=True, exist_ok=True)
    project = Project(
        name=data.name,
        slug=slug,
        description=data.description,
        workspace_path=str(project_dir),
        tech_stack=data.tech_stack,
        permission_mode=data.permission_mode or settings.default_permission_mode,
        default_model=data.default_model or settings.effective_default_model,
        status="created",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    write_meta(project_dir, "project.json", {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "tech_stack": project.tech_stack,
        "created_at": str(project.created_at),
    })
    return project


def write_meta(project_dir: Path, filename: str, data: Any):
    meta = project_dir / ".arynox" / filename
    meta.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def read_meta(project_dir: Path, filename: str) -> dict:
    meta = project_dir / ".arynox" / filename
    if meta.exists():
        try:
            return json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def project_source_dir(project: Project) -> Path:
    return Path(project.workspace_path) / "source"


def project_logs_dir(project: Project) -> Path:
    return Path(project.workspace_path) / "logs"


def write_project_log(project: Project, filename: str, text: str):
    logs = project_logs_dir(project)
    logs.mkdir(parents=True, exist_ok=True)
    (logs / filename).write_text(text, encoding="utf-8")


def delete_workspace(project: Project):
    if project.workspace_path:
        shutil.rmtree(project.workspace_path, ignore_errors=True)
