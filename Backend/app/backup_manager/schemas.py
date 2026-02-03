from pydantic import BaseModel, Field
from typing import Literal, List
from datetime import datetime


class BackupRunRequest(BaseModel):
    backup_type: Literal["backup", "export", "both"] = Field("both")


class BackupRecordResponse(BaseModel):
    id: int
    device_id: int
    backup_type: str
    filename: str
    storage_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class BackupRestoreRequest(BaseModel):
    confirm: bool = Field(False, description="Подтверждение восстановления")


class BackupRunResponse(BaseModel):
    records: List[BackupRecordResponse]
