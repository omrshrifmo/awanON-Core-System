"""
SQLAlchemy models for core_api database tables.
"""
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class CoreTask(Base):
    """
    Core API task tracking table.
    This tracks tasks initiated by core_api before they go to RabbitMQ.
    Separate from the bridge's more detailed task tracking.
    """
    __tablename__ = "core_tasks"

    task_id = Column(String, primary_key=True, index=True)
    target_company_name = Column(String, nullable=False, index=True)
    details = Column(Text, nullable=False)  # The task details/prompt
    status = Column(String, nullable=False, default="PENDING")  # PENDING, QUEUED, DISPATCHED
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CoreTask(task_id='{self.task_id}', status='{self.status}', target_company='{self.target_company_name}')>"