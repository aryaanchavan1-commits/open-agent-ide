from fastapi import APIRouter

from . import approvals, files, git, integrations, models, projects, settings

api_router = APIRouter(prefix="/api")
api_router.include_router(projects.router)
api_router.include_router(files.router)
api_router.include_router(git.router)
api_router.include_router(models.router)
api_router.include_router(approvals.router)
api_router.include_router(settings.router)
api_router.include_router(integrations.router)
