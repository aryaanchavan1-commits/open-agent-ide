from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project
from ..schemas import FileEdit, FileWrite
from ..tools.files import (
    create_directory,
    delete_file,
    edit_file,
    list_directory,
    read_file,
    search_files,
    search_text,
    write_file,
)
from ..services.workspace import project_source_dir

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])


def _project_and_source(project_id: int, db: Session) -> tuple[Project, Path]:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project, project_source_dir(project)


@router.get("")
def list_files(project_id: int, path: str = Query(".", max_length=2000), db: Session = Depends(get_db)):
    _, source = _project_and_source(project_id, db)
    return list_directory(source, path)


@router.get("/tree")
def file_tree(project_id: int, db: Session = Depends(get_db)):
    _, source = _project_and_source(project_id, db)
    ignore = {".git", ".arynox", "node_modules", "__pycache__", ".venv", "venv", ".next", "dist", "build"}

    def build(node: Path) -> dict:
        children = []
        for child in sorted(node.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if child.name in ignore:
                continue
            if child.is_dir():
                children.append({"name": child.name, "type": "directory", "children": build(child)})
            else:
                try:
                    size = child.stat().st_size
                except OSError:
                    size = 0
                children.append({"name": child.name, "type": "file", "size": size})
        return children

    if not source.exists():
        return []
    return build(source)


@router.get("/content")
def get_file_content(project_id: int, path: str = Query(..., max_length=2000), db: Session = Depends(get_db)):
    _, source = _project_and_source(project_id, db)
    result = read_file(source, path)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "File not found"))
    return result


@router.post("")
def create_file(project_id: int, data: FileWrite, db: Session = Depends(get_db)):
    _, source = _project_and_source(project_id, db)
    result = write_file(source, data.path, data.content, data.overwrite)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Write failed"))
    return result


@router.post("/edit")
def edit_file_endpoint(project_id: int, data: FileEdit, db: Session = Depends(get_db)):
    _, source = _project_and_source(project_id, db)
    result = edit_file(source, data.path, data.old_snippet, data.new_snippet)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Edit failed"))
    return result


@router.delete("")
def delete_file_endpoint(project_id: int, path: str = Query(..., max_length=2000), db: Session = Depends(get_db)):
    _, source = _project_and_source(project_id, db)
    result = delete_file(source, path)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Delete failed"))
    return result


@router.post("/directory")
def make_directory(project_id: int, path: str = Query(..., max_length=2000), db: Session = Depends(get_db)):
    _, source = _project_and_source(project_id, db)
    result = create_directory(source, path)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Create failed"))
    return result


@router.get("/search-files")
def search_files_endpoint(
    project_id: int, pattern: str = Query("*.py"), path: str = Query("."), db: Session = Depends(get_db)
):
    _, source = _project_and_source(project_id, db)
    return search_files(source, pattern, path)


@router.get("/search-text")
def search_text_endpoint(
    project_id: int, query: str = Query(..., min_length=1), path: str = Query("."), db: Session = Depends(get_db)
):
    _, source = _project_and_source(project_id, db)
    return search_text(source, query, path)
