import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from db import SessionLocal
from device_manager.models import Device
from device_manager.service import DeviceService
from task_manager.celery_app import celery_app
from task_manager.models import Task, TaskExecution, TaskResult, TaskTarget

logger = get_task_logger(__name__)


def _parse_cron_field(value: str, minimum: int, maximum: int) -> List[int]:
    if value == "*":
        return list(range(minimum, maximum + 1))

    values: List[int] = []
    for part in value.split(","):
        part = part.strip()
        if part.startswith("*/"):
            step = int(part.replace("*/", ""))
            values.extend(range(minimum, maximum + 1, step))
        elif "-" in part:
            start, end = part.split("-", 1)
            values.extend(range(int(start), int(end) + 1))
        else:
            values.append(int(part))
    return sorted({v for v in values if minimum <= v <= maximum})


def cron_matches(dt: datetime, expression: str) -> bool:
    minute_s, hour_s, day_s, month_s, weekday_s = expression.split()
    minutes = _parse_cron_field(minute_s, 0, 59)
    hours = _parse_cron_field(hour_s, 0, 23)
    days = _parse_cron_field(day_s, 1, 31)
    months = _parse_cron_field(month_s, 1, 12)
    weekdays = _parse_cron_field(weekday_s, 0, 6)

    return (
        dt.minute in minutes
        and dt.hour in hours
        and dt.day in days
        and dt.month in months
        and dt.weekday() in weekdays
    )


def compute_next_run(now: datetime, expression: str, lookahead_minutes: int = 60 * 24) -> datetime:
    check_time = now + timedelta(minutes=1)
    for _ in range(lookahead_minutes):
        if cron_matches(check_time, expression):
            return check_time
        check_time += timedelta(minutes=1)
    return now + timedelta(minutes=lookahead_minutes)


def _collect_target_device_ids(session: Session, task: Task) -> List[int]:
    device_ids: List[int] = []
    for target in task.targets:
        if target.target_type == "device" and target.device_id:
            device_ids.append(target.device_id)
        elif target.target_type == "group" and target.group_id:
            group_devices = (
                session.query(Device)
                .filter(Device.group_id == target.group_id)
                .all()
            )
            device_ids.extend([device.id for device in group_devices])
    return sorted(set(device_ids))


def _execute_task_for_device(session: Session, task: Task, device_id: int) -> dict:
    if task.task_type == "check_availability":
        service = DeviceService(session)
        status = asyncio.run(service.check_device_availability(device_id))
        return status.dict() if status else {"error": "device_not_found"}
    raise ValueError(f"Unsupported task type: {task.task_type}")


@celery_app.task(name="task_manager.worker.execute_task", bind=True)
def execute_task(self, task_id: int, triggered_by: str = "schedule") -> None:
    session = SessionLocal()
    try:
        task = session.query(Task).filter(Task.id == task_id).first()
        if not task or not task.is_enabled:
            logger.warning("Task %s not found or disabled", task_id)
            return

        execution = TaskExecution(task_id=task.id, status="running", triggered_by=triggered_by)
        session.add(execution)
        session.commit()
        session.refresh(execution)

        device_ids = _collect_target_device_ids(session, task)
        results: List[TaskResult] = []

        for device_id in device_ids:
            result = TaskResult(
                execution_id=execution.id,
                device_id=device_id,
                status="running",
            )
            session.add(result)
            results.append(result)
        session.commit()

        failures = 0
        for result in results:
            try:
                payload = _execute_task_for_device(session, task, result.device_id)
                result.status = "success"
                result.output = json.dumps(payload, ensure_ascii=False)
            except Exception as exc:
                failures += 1
                result.status = "failed"
                result.error_message = str(exc)
            result.finished_at = datetime.now(timezone.utc)
            session.add(result)
        session.commit()

        execution.status = "failed" if failures else "success"
        execution.finished_at = datetime.now(timezone.utc)
        task.last_run_at = datetime.now(timezone.utc)
        task.next_run_at = compute_next_run(task.last_run_at, task.schedule_expression)
        session.add_all([execution, task])
        session.commit()
    finally:
        session.close()


@celery_app.task(name="task_manager.worker.dispatch_scheduled_tasks")
def dispatch_scheduled_tasks() -> None:
    session = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        tasks: Iterable[Task] = session.query(Task).filter(Task.is_enabled.is_(True)).all()
        for task in tasks:
            next_run = task.next_run_at
            if not next_run:
                task.next_run_at = compute_next_run(now, task.schedule_expression)
                session.add(task)
                session.commit()
                continue

            if next_run <= now and cron_matches(now, task.schedule_expression):
                logger.info("Dispatching task %s", task.id)
                execute_task.delay(task.id, "schedule")
                task.last_run_at = now
                task.next_run_at = compute_next_run(now, task.schedule_expression)
                session.add(task)
                session.commit()
    finally:
        session.close()
