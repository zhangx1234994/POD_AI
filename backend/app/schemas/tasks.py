from datetime import datetime
from pydantic import BaseModel, Field


class TaskSubmission(BaseModel):
    taskId: str
    action: str
    userId: str
    channel: str
    workflowParams: dict
    points: int = Field(..., gt=0)


class TaskResponse(BaseModel):
    taskId: str
    status: str


class TaskStatusResponse(BaseModel):
    taskId: str
    status: str
    progress: int
    resultUrl: str | None = None


class TaskListItem(BaseModel):
    taskId: str
    action: str
    status: str
    progress: int
    channel: str
    createdAt: datetime
    updatedAt: datetime
    finishedAt: datetime | None = None
    points: int | None = None
    resultUrl: str | None = None
    workflowParams: dict | None = None


class TaskListResponse(BaseModel):
    items: list[TaskListItem]
    total: int
    page: int
    size: int
