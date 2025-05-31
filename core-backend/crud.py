"""
CRUD operations for core_api database interactions.
"""
from sqlalchemy.orm import Session
from models import CoreTask
from schemas import TaskCreationPayload


def create_core_task(db: Session, task_id: str, payload: TaskCreationPayload) -> CoreTask:
    """
    Create a new core task record in the database.
    """
    db_task = CoreTask(
        task_id=task_id,
        target_company_name=payload.target_company_name or "tswiqon",
        details=payload.details,
        status="PENDING"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_core_task(db: Session, task_id: str) -> CoreTask:
    """
    Retrieve a core task by task_id.
    """
    return db.query(CoreTask).filter(CoreTask.task_id == task_id).first()


def update_core_task_status(db: Session, task_id: str, status: str) -> CoreTask:
    """
    Update the status of a core task.
    """
    db_task = db.query(CoreTask).filter(CoreTask.task_id == task_id).first()
    if db_task:
        db_task.status = status
        db.commit()
        db.refresh(db_task)
    return db_task


def get_core_tasks(db: Session, skip: int = 0, limit: int = 100):
    """
    Retrieve a list of core tasks with pagination.
    """
    return db.query(CoreTask).offset(skip).limit(limit).all()