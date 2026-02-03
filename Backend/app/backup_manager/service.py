import os
import re
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from backup_manager import crud
from device_manager import crud as device_crud
from mikrotik_connector import MikroTikConnector


class BackupService:
    def __init__(self, db: Session, storage_root: str = "/storage/backups"):
        self.db = db
        self.storage_root = storage_root
        self.backup_crud = crud.BackupCRUD(db)
        self.device_crud = device_crud.DeviceCRUD(db)

    def _sanitize_name(self, name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_") or "device"

    def _build_paths(self, device_id: int, device_name: str, backup_type: str):
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_name = self._sanitize_name(device_name)
        base_name = f"{safe_name}_{device_id}_{timestamp}_{backup_type}"
        ext = "backup" if backup_type == "backup" else "rsc"
        filename = f"{base_name}.{ext}"
        device_dir = os.path.join(self.storage_root, f"device_{device_id}")
        os.makedirs(device_dir, exist_ok=True)
        storage_path = os.path.join(device_dir, filename)
        return base_name, filename, storage_path

    async def run_backup(self, device_id: int, backup_type: str):
        device_data = self.device_crud.get_device_with_password(device_id)
        if not device_data:
            raise ValueError("Device not found")

        base_name, filename, storage_path = self._build_paths(
            device_id=device_id,
            device_name=device_data["name"],
            backup_type=backup_type,
        )

        connector = MikroTikConnector(
            host=device_data["host"],
            username=device_data["username"],
            password=device_data["password"],
            api_port=device_data["api_port"],
            ssh_port=device_data["ssh_port"],
            use_ssl=device_data["use_ssl"],
        )

        try:
            await connector.connect()

            if not connector.ssh_client or not connector.sftp_client:
                raise RuntimeError("SSH/SFTP connection required for backup")

            if backup_type == "backup":
                command = f"/system/backup/save name={base_name}"
                remote_file = f"{base_name}.backup"
            elif backup_type == "export":
                command = f"/export file={base_name}"
                remote_file = f"{base_name}.rsc"
            else:
                raise ValueError("Unsupported backup type")

            connector.run_ssh_command(command)
            connector.download_file(remote_file, storage_path)

            record = self.backup_crud.create_backup_record(
                device_id=device_id,
                backup_type=backup_type,
                filename=filename,
                storage_path=storage_path,
            )

            self.device_crud.update_last_backup(device_id, func.now())

            return record
        finally:
            await connector.disconnect()

    async def run_backup_bundle(self, device_id: int, backup_type: str) -> List:
        types = [backup_type]
        if backup_type == "both":
            types = ["backup", "export"]

        records = []
        for backup_kind in types:
            record = await self.run_backup(device_id, backup_kind)
            records.append(record)
        return records

    async def restore_backup(self, backup_id: int, confirm: bool):
        if not confirm:
            raise ValueError("Restore requires confirmation")

        record = self.backup_crud.get_backup_record(backup_id)
        if not record:
            raise ValueError("Backup record not found")

        device_data = self.device_crud.get_device_with_password(record.device_id)
        if not device_data:
            raise ValueError("Device not found")

        if not os.path.isfile(record.storage_path):
            raise FileNotFoundError("Backup file not found in storage")

        connector = MikroTikConnector(
            host=device_data["host"],
            username=device_data["username"],
            password=device_data["password"],
            api_port=device_data["api_port"],
            ssh_port=device_data["ssh_port"],
            use_ssl=device_data["use_ssl"],
        )

        try:
            await connector.connect()

            if not connector.ssh_client or not connector.sftp_client:
                raise RuntimeError("SSH/SFTP connection required for restore")

            remote_filename = os.path.basename(record.storage_path)
            remote_path = remote_filename
            connector.upload_file(record.storage_path, remote_path)

            if record.backup_type == "backup":
                base_name = remote_filename.rsplit(".backup", 1)[0]
                command = f"/system/backup/load name={base_name}"
            elif record.backup_type == "export":
                command = f"/import file={remote_filename}"
            else:
                raise ValueError("Unsupported backup type")

            connector.run_ssh_command(command)
            return record
        finally:
            await connector.disconnect()
