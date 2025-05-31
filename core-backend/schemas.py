"""
Pydantic schemas for core_api request/response models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


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


# --- Authentication Schemas ---
class UserCreate(BaseModel):
    """Request payload for user registration."""
    username: str = Field(..., min_length=3, description="Username (minimum 3 characters)")
    email: Optional[EmailStr] = Field(None, description="Optional email address")
    password: str = Field(..., min_length=6, description="Password (minimum 6 characters)")


class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    username: str
    email: Optional[EmailStr] = None
    created_at: datetime

    class Config:
        from_attributes = True  # For SQLAlchemy model compatibility


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token payload data."""
    username: Optional[str] = None