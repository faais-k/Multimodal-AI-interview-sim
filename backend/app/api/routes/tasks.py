from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
from backend.app.worker import app as celery_app

router = APIRouter()

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Check the status of a background task."""
    result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": result.status,
    }
    
    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            # Task failed
            response["error"] = str(result.result)
            
    return response
