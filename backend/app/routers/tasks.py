"""任务路由：提供提交和查询接口。"""

from fastapi import APIRouter, HTTPException, Query

from app.schemas import tasks as schemas
from app.services.wallet import wallet_service
from app.services.notify import notify_service
from app.services.task_service import task_service
from app.services.task_dispatcher import task_dispatcher_service

router = APIRouter()


def to_status_response(task) -> schemas.TaskStatusResponse:
    result_url = None
    if task and task.result_payload:
        result_url = (
            task.result_payload.get("url")
            or task.result_payload.get("resultUrl")
            or task.result_payload.get("inputPreview")
        )
    return schemas.TaskStatusResponse(
        taskId=task.id,
        status=task.status,
        progress=task.progress,
        resultUrl=result_url,
    )


def to_list_item(task) -> schemas.TaskListItem:
    result_url = None
    if task.result_payload:
        result_url = (
            task.result_payload.get("url")
            or task.result_payload.get("resultUrl")
            or task.result_payload.get("inputPreview")
        )
    return schemas.TaskListItem(
        taskId=task.id,
        action=task.tool_action,
        status=task.status,
        progress=task.progress,
        channel=task.channel,
        createdAt=task.created_at,
        updatedAt=task.updated_at,
        finishedAt=task.finished_at,
        points=task.points_cost,
        resultUrl=result_url,
        workflowParams=task.input_payload,
    )


@router.post("/v1/submit", response_model=schemas.TaskResponse)
async def submit_task(payload: schemas.TaskSubmission) -> schemas.TaskResponse:
    hold_id, _ = wallet_service.freeze(payload.userId, payload.taskId, payload.points)
    task = task_service.create_task(payload, hold_id)
    await notify_service.broadcast(
        {
            "type": "task.status",
            "payload": {
                "taskId": payload.taskId,
                "status": task.status,
                "progress": task.progress,
                "points": payload.points,
            },
        }
    )
    return schemas.TaskResponse(taskId=task.id, status=task.status)


@router.get("/v1/{task_id}", response_model=schemas.TaskStatusResponse)
async def get_task(task_id: str) -> schemas.TaskStatusResponse:
    task = task_service.get_task(task_id)
    if not task:
        return schemas.TaskStatusResponse(taskId=task_id, status="pending", progress=0)
    return to_status_response(task)


@router.post("/v1/{task_id}/complete")
async def complete_task(task_id: str, success: bool = True) -> dict:
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="TASK_NOT_FOUND")
    if not task.wallet_hold_id:
        raise HTTPException(status_code=400, detail="HOLD_NOT_FOUND")
    if success:
        wallet_service.confirm(task.wallet_hold_id)
        updated = task_service.complete_task(task_id, True)
        await notify_service.broadcast(
            {
                "type": "task.status",
                "payload": {"taskId": task_id, "status": updated.status, "progress": updated.progress},
            }
        )
        await notify_service.broadcast(
            {
                "type": "wallet.points",
                "payload": {"taskId": task_id, "status": "deducted"},
            }
        )
        return {"status": updated.status}
    _, balance = wallet_service.release(task.wallet_hold_id)
    updated = task_service.complete_task(task_id, False)
    await notify_service.broadcast(
        {
            "type": "task.status",
            "payload": {"taskId": task_id, "status": updated.status, "progress": updated.progress},
        }
    )
    await notify_service.broadcast(
        {
            "type": "wallet.points",
            "payload": {"taskId": task_id, "status": "released", "balance": balance},
        }
    )
    return {"status": updated.status, "balance": balance}


@router.get("/v1", response_model=schemas.TaskListResponse)
async def list_tasks(
    userId: str = Query(..., alias="userId"),
    action: str | None = None,
    status: str | None = None,
    page: int = 0,
    size: int = 10,
) -> schemas.TaskListResponse:
    page = max(page, 0)
    size = min(max(size, 1), 50)
    tasks, total = task_service.list_tasks(
        user_id=userId,
        action=action,
        status=status,
        page=page,
        size=size,
    )
    items = [to_list_item(task) for task in tasks]
    return schemas.TaskListResponse(items=items, total=total, page=page, size=size)


@router.post("/v1/dispatch")
async def dispatch_tasks(limit: int = 5) -> dict:
    limit = min(max(limit, 1), 20)
    reports = task_dispatcher_service.dispatch_pending(limit=limit)
    dispatched = []
    for report in reports:
        await notify_service.broadcast(
            {
                "type": "task.status",
                "payload": {"taskId": report.task_id, "status": report.status, "progress": report.progress},
            }
        )
        if report.wallet_event:
            await notify_service.broadcast(report.wallet_event)
        dispatched.append(
            {"taskId": report.task_id, "status": report.status, "message": report.message, "progress": report.progress}
        )
    return {"processed": len(reports), "results": dispatched}
