from typing import Optional, List
from sqlalchemy.orm import Session
from backup_manager import models


class BackupCRUD:
    def __init__(self, db: Session):
        self.db = db

    def create_backup_record(
        self,
        device_id: int,
        backup_type: str,
        filename: str,
        storage_path: str,
    ) -> models.BackupRecord:
        record = models.BackupRecord(
            device_id=device_id,
            backup_type=backup_type,
            filename=filename,
            storage_path=storage_path,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_backup_record(self, backup_id: int) -> Optional[models.BackupRecord]:
        return self.db.query(models.BackupRecord).filter(models.BackupRecord.id == backup_id).first()

    def list_device_backups(self, device_id: int) -> List[models.BackupRecord]:
        return (
            self.db.query(models.BackupRecord)
            .filter(models.BackupRecord.device_id == device_id)
            .order_by(models.BackupRecord.created_at.desc())
            .all()
        )
