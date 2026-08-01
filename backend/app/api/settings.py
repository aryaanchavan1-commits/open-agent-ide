from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project, ProjectSetting
from ..schemas import SettingsUpdate

router = APIRouter(prefix="/projects/{project_id}/settings", tags=["settings"])


@router.get("")
def get_settings(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    rows = db.execute(
        select(ProjectSetting).where(ProjectSetting.project_id == project_id)
    ).scalars().all()
    return {
        "permission_mode": project.permission_mode,
        "default_model": project.default_model,
        "values": {r.key: r.value for r in rows},
    }


@router.post("")
def update_setting(project_id: int, data: SettingsUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if data.key == "permission_mode":
        if data.value not in ("safe", "ask", "auto"):
            raise HTTPException(400, "permission_mode must be safe, ask or auto")
        project.permission_mode = data.value
        db.commit()
        return {"ok": True, "key": "permission_mode", "value": data.value}
    row = db.execute(
        select(ProjectSetting).where(
            ProjectSetting.project_id == project_id, ProjectSetting.key == data.key
        )
    ).scalar_one_or_none()
    if row:
        row.value = data.value
    else:
        row = ProjectSetting(project_id=project_id, key=data.key, value=data.value)
        db.add(row)
    db.commit()
    return {"ok": True, "key": data.key, "value": data.value}
