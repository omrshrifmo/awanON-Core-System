"""
Pydantic schemas for core_api request/response models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TaskCreationPayload(BaseModel):
    """Request payload for creating a new task."""
    details: str = Field(..., description="The specific details or prompt for the task.")
    target_company_name: Optional[str] = Field("tswiqon", description="The target AI company service to handle the task (e.g., 'tswiqon'). Defaults to 'tswiqon'.")


class TaskCreationResponse(BaseModel):
    """Response for task creation."""
    task_id: str
    message: str
    status_code: int
    target_queue: str


class CoreTaskResponse(BaseModel):
    """Response model for core task status."""
    task_id: str
    target_company_name: str
    details: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # For SQLAlchemy model compatibility


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = "OK"