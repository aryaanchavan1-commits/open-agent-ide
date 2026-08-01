from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    permission_mode: str = "ask"
    default_model: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tech_stack: Optional[list[str]] = None
    permission_mode: Optional[str] = None
    default_model: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    workspace_path: str
    tech_stack: list[Any]
    status: str
    permission_mode: str
    default_model: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: Optional[int] = None


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    agent_type: str
    meta: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: int
    project_id: int
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentRunRequest(BaseModel):
    agent_type: str = Field(min_length=1)
    prompt: str = ""
    task_id: Optional[str] = None
    conversation_id: Optional[int] = None


class TaskCreate(BaseModel):
    task_id: Optional[str] = None
    title: str
    description: str = ""
    priority: str = "medium"
    dependencies: list[str] = Field(default_factory=list)
    status: str = "pending"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    dependencies: Optional[list[str]] = None
    status: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    project_id: int
    task_id: str
    title: str
    description: str
    priority: str
    dependencies: list[Any]
    status: str
    agent_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileWrite(BaseModel):
    path: str = Field(min_length=1)
    content: str = ""
    overwrite: bool = True


class FileEdit(BaseModel):
    path: str = Field(min_length=1)
    old_snippet: str = Field(min_length=1)
    new_snippet: str = ""


class ExecuteRequest(BaseModel):
    command: str = Field(min_length=1)
    reason: str = ""
    timeout: int = 300


class ApprovalResponse(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")


class GitCommitRequest(BaseModel):
    message: str = Field(min_length=1)


class GitBranchCreate(BaseModel):
    name: str = Field(min_length=1)


class CheckpointCreate(BaseModel):
    name: str = ""
    message: str = ""


class SettingsUpdate(BaseModel):
    key: str
    value: str


class ModelPullRequest(BaseModel):
    model: str = Field(min_length=1)


class RunStatus(BaseModel):
    run_id: int
    project_id: int
    agent_type: str
    status: str
    output: str = ""
    error: str = ""

    model_config = {"from_attributes": True}
