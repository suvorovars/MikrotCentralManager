from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db import get_db
from backup_manager import schemas, service, models
from security.auth import get_current_user

router = APIRouter(
    prefix="/backups",
    tags=["backups"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/devices/{device_id}/run", response_model=schemas.BackupRunResponse)
async def run_device_backup(
    device_id: int,
    payload: schemas.BackupRunRequest,
    db: Session = Depends(get_db),
):
    backup_service = service.BackupService(db)
    try:
        records = await backup_service.run_backup_bundle(device_id, payload.backup_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return schemas.BackupRunResponse(
        records=[schemas.BackupRecordResponse.from_orm(record) for record in records]
    )


@router.post("/{backup_id}/restore", response_model=schemas.BackupRecordResponse)
async def restore_backup(
    backup_id: int,
    payload: schemas.BackupRestoreRequest,
    db: Session = Depends(get_db),
):
    backup_service = service.BackupService(db)
    try:
        record = await backup_service.restore_backup(backup_id, payload.confirm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return schemas.BackupRecordResponse.from_orm(record)


@router.get("/{backup_id}/download")
async def download_backup(
    backup_id: int,
    db: Session = Depends(get_db),
):
    backup_service = service.BackupService(db)
    try:
        record = await backup_service.get_backup_file(backup_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        path=record.storage_path,
        filename=record.filename,
        media_type="application/octet-stream",
    )
