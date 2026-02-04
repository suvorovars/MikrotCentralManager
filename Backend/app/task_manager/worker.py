import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from backup_manager.service import BackupService
from db import SessionLocal
from device_manager.models import Device
from device_manager.service import DeviceService
from firewall_manager.schemas import FirewallListType
from firewall_manager.service import FirewallListService
from mikrotik_connector import MikroTikConnector
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


def _load_task_payload(task: Task) -> Dict[str, Any]:
    if not task.payload:
        return {}
    try:
        return json.loads(task.payload)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid task payload JSON") from exc


def _get_device_credentials(session: Session, device_id: int) -> Dict[str, Any]:
    service = DeviceService(session)
    device_data = service.get_device_credentials(device_id)
    if not device_data:
        raise ValueError(f"Device {device_id} not found or credentials missing")
    return device_data


def _build_connector(device_data: Dict[str, Any]) -> MikroTikConnector:
    return MikroTikConnector(
        host=device_data["host"],
        username=device_data["username"],
        password=device_data["password"],
        api_port=device_data["api_port"],
        ssh_port=device_data["ssh_port"],
        use_ssl=device_data["use_ssl"],
    )


def _normalize_firewall_list_type(list_type_raw: Optional[str]) -> FirewallListType:
    if not list_type_raw:
        raise ValueError("Missing firewall list type")
    normalized = list_type_raw.strip().lower()
    if normalized in {"whitelist", "white"}:
        return FirewallListType.whitelist
    if normalized in {"blacklist", "black", "bladdress"}:
        return FirewallListType.blacklist
    raise ValueError(f"Unsupported firewall list type: {list_type_raw}")


def _escape_routeros_script(script: str) -> str:
    return script.replace("\\", "\\\\").replace("\"", "\\\"")


async def _execute_script_task(connector: MikroTikConnector, payload: Dict[str, Any]) -> Dict[str, Any]:
    script = payload.get("script")
    script_name = payload.get("script_name")
    if not script and not script_name:
        raise ValueError("Missing script or script_name for script execution")

    await connector.connect()
    try:
        if not connector.ssh_client:
            raise RuntimeError("SSH connection required for script execution")

        if script_name:
            output = connector.run_ssh_command(f"/system/script/run {script_name}")
            return {"script_name": script_name, "output": output}

        escaped_script = _escape_routeros_script(script)
        task_script_name = f"task_script_{uuid.uuid4().hex[:10]}"
        created = False
        connector.run_ssh_command(
            f"/system/script/add name=\"{task_script_name}\" source=\"{escaped_script}\""
        )
        created = True
        try:
            output = connector.run_ssh_command(f"/system/script/run {task_script_name}")
        finally:
            if created:
                connector.run_ssh_command(
                    f"/system/script/remove [find name=\"{task_script_name}\"]"
                )
        return {"script_name": task_script_name, "output": output}
    finally:
        await connector.disconnect()


async def _execute_reboot_task(connector: MikroTikConnector) -> Dict[str, Any]:
    await connector.connect()
    try:
        if not connector.ssh_client:
            raise RuntimeError("SSH connection required for reboot")
        output = connector.run_ssh_command("/system/reboot")
        return {"command": "/system/reboot", "output": output}
    finally:
        await connector.disconnect()


async def _execute_reset_task(connector: MikroTikConnector, payload: Dict[str, Any]) -> Dict[str, Any]:
    await connector.connect()
    try:
        if not connector.ssh_client:
            raise RuntimeError("SSH connection required for reset")
        options = payload.get("options", {}) if isinstance(payload.get("options", {}), dict) else {}
        args: List[str] = []
        if "keep_users" in options:
            args.append(f"keep-users={'yes' if options['keep_users'] else 'no'}")
        if "no_defaults" in options:
            args.append(f"no-defaults={'yes' if options['no_defaults'] else 'no'}")
        if "skip_backup" in options:
            args.append(f"skip-backup={'yes' if options['skip_backup'] else 'no'}")
        command = "/system/reset-configuration"
        if args:
            command = f"{command} {' '.join(args)}"
        output = connector.run_ssh_command(command)
        return {"command": command, "output": output}
    finally:
        await connector.disconnect()


def _execute_task_for_device(session: Session, task: Task, device_id: int) -> Dict[str, Any]:
    payload = _load_task_payload(task)
    base_payload = {
        "task_type": task.task_type,
        "device_id": device_id,
        "task_payload": payload,
    }
    if task.task_type == "check_availability":
        service = DeviceService(session)
        status = asyncio.run(service.check_device_availability(device_id))
        return {
            **base_payload,
            "result": {"status": status.dict() if status else {"error": "device_not_found"}},
        }

    if task.task_type in {"execute_script", "script_execution"}:
        device_data = _get_device_credentials(session, device_id)
        connector = _build_connector(device_data)
        result = asyncio.run(_execute_script_task(connector, payload))
        return {**base_payload, "result": {"script_execution": result}}

    if task.task_type == "firewall_list_update":
        operation = payload.get("operation")
        address = payload.get("address")
        comment = payload.get("comment")
        list_type = _normalize_firewall_list_type(payload.get("list_type"))
        if not operation or not address:
            raise ValueError("Firewall list update requires operation and address")

        service = FirewallListService(DeviceService(session))
        if operation == "add":
            response = asyncio.run(service.add_address(device_id, list_type, address, comment))
        elif operation == "remove":
            response = asyncio.run(service.remove_address(device_id, list_type, address))
        else:
            raise ValueError(f"Unsupported firewall operation: {operation}")
        return {**base_payload, "result": {"firewall_list_update": response.dict()}}

    if task.task_type == "backup_creation":
        backup_type = payload.get("backup_type", "backup")
        service = BackupService(session)
        records = asyncio.run(service.run_backup_bundle(device_id, backup_type))
        record_payload = [
            {
                "id": record.id,
                "backup_type": record.backup_type,
                "filename": record.filename,
                "storage_path": record.storage_path,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
            for record in records
        ]
        return {**base_payload, "result": {"backup_creation": record_payload}}

    if task.task_type == "reboot":
        device_data = _get_device_credentials(session, device_id)
        connector = _build_connector(device_data)
        result = asyncio.run(_execute_reboot_task(connector))
        return {**base_payload, "result": {"reboot": result}}

    if task.task_type == "reset":
        device_data = _get_device_credentials(session, device_id)
        connector = _build_connector(device_data)
        result = asyncio.run(_execute_reset_task(connector, payload))
        return {**base_payload, "result": {"reset": result}}

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
                started_at=datetime.now(timezone.utc),
            )
            session.add(result)
            results.append(result)
        session.commit()

        failures = 0
        for result in results:
            try:
                payload = _execute_task_for_device(session, task, result.device_id)
                result.status = "success"
                result.result_payload = json.dumps(payload, ensure_ascii=False)
                result.output = json.dumps(payload, ensure_ascii=False)
            except Exception as exc:
                failures += 1
                result.status = "failed"
                result.error_message = str(exc)
                error_payload = {"error": str(exc), "task_type": task.task_type}
                result.result_payload = json.dumps(error_payload, ensure_ascii=False)
                result.output = json.dumps(error_payload, ensure_ascii=False)
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
