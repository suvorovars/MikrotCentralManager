from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class Task(Base):
    """Запланированная задача для устройств/групп."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    task_type = Column(String(50), nullable=False)

    schedule_expression = Column(String(100), nullable=False)
    schedule_timezone = Column(String(50), default="UTC")
    is_enabled = Column(Boolean, default=True)

    status = Column(String(20), default="idle")
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    targets = relationship("TaskTarget", back_populates="task", cascade="all, delete-orphan")
    executions = relationship("TaskExecution", back_populates="task", cascade="all, delete-orphan")


class TaskTarget(Base):
    """Целевые устройства/группы задачи."""
    __tablename__ = "task_targets"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    target_type = Column(String(20), nullable=False)  # device | group

    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("device_groups.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("Task", back_populates="targets")
    device = relationship("Device", back_populates="task_targets")
    group = relationship("DeviceGroup", back_populates="task_targets")


class TaskExecution(Base):
    """Запуск задачи."""
    __tablename__ = "task_executions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    status = Column(String(20), default="pending")
    triggered_by = Column(String(20), default="schedule")

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("Task", back_populates="executions")
    results = relationship("TaskResult", back_populates="execution", cascade="all, delete-orphan")


class TaskResult(Base):
    """Результат выполнения задачи по конкретному устройству."""
    __tablename__ = "task_results"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("task_executions.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    status = Column(String(20), default="pending")
    output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    execution = relationship("TaskExecution", back_populates="results")
    device = relationship("Device", back_populates="task_results")
