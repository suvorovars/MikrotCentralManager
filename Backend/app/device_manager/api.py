# app/device_manager/api.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from db import get_db
from device_manager import schemas, service, crud, models
from security import encrypt_password

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/", response_model=schemas.DeviceResponse)
def create_device(
        device: schemas.DeviceCreate,
        db: Session = Depends(get_db)
):
    """Создание нового устройства"""
    device_crud = crud.DeviceCRUD(db)

    # Проверяем уникальность имени
    existing = db.query(models.Device).filter(
        models.Device.name == device.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device with this name already exists")

    return device_crud.create_device(device)


@router.get("/", response_model=List[schemas.DeviceResponse])
def get_devices(
        skip: int = 0,
        limit: int = 100,
        group_id: Optional[int] = None,
        db: Session = Depends(get_db)
):
    """Получение списка устройств"""
    device_crud = crud.DeviceCRUD(db)

    if group_id:
        return device_crud.get_devices_by_group(group_id)
    return device_crud.get_all_devices(skip, limit)


@router.get("/{device_id}", response_model=schemas.DeviceResponse)
def get_device(
        device_id: int,
        db: Session = Depends(get_db)
):
    """Получение устройства по ID"""
    device_crud = crud.DeviceCRUD(db)
    device = device_crud.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("/{device_id}/status", response_model=schemas.DeviceStatusResponse)
async def get_device_status(
        device_id: int,
        db: Session = Depends(get_db)
):
    """Проверка статуса устройства"""
    device_service = service.DeviceService(db)
    status = await device_service.check_device_availability(device_id)
    if not status:
        raise HTTPException(status_code=404, detail="Device not found")
    return status


@router.post("/check", response_model=List[schemas.DeviceStatusResponse])
async def check_devices(
        device_ids: List[int],
        db: Session = Depends(get_db)
):
    """Проверка доступности нескольких устройств"""
    device_service = service.DeviceService(db)
    results = await device_service.check_multiple_devices(device_ids)
    return results


@router.get("/{device_id}/credentials")
def get_device_credentials(
        device_id: int,
        db: Session = Depends(get_db)
):
    """Получение учетных данных устройства (только для внутреннего использования)"""
    device_service = service.DeviceService(db)
    credentials = device_service.get_device_credentials(device_id)
    if not credentials:
        raise HTTPException(status_code=404, detail="Device not found")
    return credentials


@router.put("/{device_id}", response_model=schemas.DeviceResponse)
def update_device_full(
        device_id: int,
        device_data: schemas.DeviceCreate,
        db: Session = Depends(get_db)
):
    """Полное обновление устройства (PUT - требует все поля)"""
    device_crud = crud.DeviceCRUD(db)

    # Получаем текущее устройство
    db_device = device_crud.get_device(device_id)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Создаем словарь с новыми данными
    update_data = device_data.model_dump()
    update_data['encrypted_password'] = encrypt_password(update_data.pop('password'))

    # Обновляем все поля
    for field, value in update_data.items():
        setattr(db_device, field, value)

    db.commit()
    db.refresh(db_device)
    return db_device


@router.patch("/{device_id}", response_model=schemas.DeviceResponse)
def update_device_partial(
        device_id: int,
        device_data: schemas.DeviceUpdate,
        db: Session = Depends(get_db)
):
    """Частичное обновление устройства (PATCH - только указанные поля)"""
    device_crud = crud.DeviceCRUD(db)
    updated = device_crud.update_device(device_id, device_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Device not found")
    return updated


@router.delete("/{device_id}")
def delete_device(
        device_id: int,
        db: Session = Depends(get_db)
):
    """Удаление устройства"""
    device_crud = crud.DeviceCRUD(db)
    success = device_crud.delete_device(device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"message": "Device deleted successfully"}


# Группы устройств
@router.post("/groups/", response_model=schemas.DeviceGroupResponse)
def create_group(
        group: schemas.DeviceGroupCreate,
        db: Session = Depends(get_db)
):
    """Создание новой группы"""
    group_crud = crud.DeviceGroupCRUD(db)

    # Проверяем уникальность имени
    existing = db.query(models.DeviceGroup).filter(
        models.DeviceGroup.name == group.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group with this name already exists")

    return group_crud.create_group(group)


@router.get("/groups/", response_model=List[schemas.DeviceGroupDetail])
def get_groups(db: Session = Depends(get_db)):
    """Получение всех групп с количеством устройств"""
    group_crud = crud.DeviceGroupCRUD(db)
    groups = group_crud.get_all_groups()

    result = []
    for group in groups:
        # Получаем количество устройств в группе
        device_count = db.query(models.Device).filter(
            models.Device.group_id == group.id
        ).count()

        group_detail = schemas.DeviceGroupDetail(
            id=group.id,
            name=group.name,
            description=group.description,
            device_count=device_count,
            created_at=group.created_at
        )
        result.append(group_detail)

    return result


@router.get("/groups/{group_id}", response_model=schemas.DeviceGroupWithDevices)
def get_group(
        group_id: int,
        db: Session = Depends(get_db)
):
    """Получение группы с устройствами"""
    group_crud = crud.DeviceGroupCRUD(db)
    device_crud = crud.DeviceCRUD(db)

    group = group_crud.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Получаем устройства в группе
    devices = device_crud.get_devices_by_group(group_id)

    return schemas.DeviceGroupWithDevices(
        id=group.id,
        name=group.name,
        description=group.description,
        device_count=len(devices),
        created_at=group.created_at,
        devices=[schemas.DeviceResponse.from_orm(device) for device in devices]
    )


@router.get("/groups/{group_id}/check", response_model=List[schemas.DeviceStatusResponse])
async def check_group_devices(
        group_id: int,
        db: Session = Depends(get_db)
):
    """Проверка всех устройств в группе"""
    device_crud = crud.DeviceCRUD(db)

    # Проверяем существование группы
    group_crud = crud.DeviceGroupCRUD(db)
    group = group_crud.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Получаем устройства в группе
    devices = device_crud.get_devices_by_group(group_id)
    if not devices:
        return []

    device_ids = [device.id for device in devices]

    # Проверяем устройства
    device_service = service.DeviceService(db)
    results = await device_service.check_multiple_devices(device_ids)
    return results


@router.put("/groups/{group_id}", response_model=schemas.DeviceGroupResponse)
def update_group_full(
        group_id: int,
        group_data: schemas.DeviceGroupCreate,
        db: Session = Depends(get_db)
):
    """Полное обновление группы (PUT - требует все поля)"""
    group_crud = crud.DeviceGroupCRUD(db)

    # Получаем текущую группу
    db_group = group_crud.get_group(group_id)
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Обновляем все поля
    db_group.name = group_data.name
    db_group.description = group_data.description

    db.commit()
    db.refresh(db_group)
    return db_group


@router.patch("/groups/{group_id}", response_model=schemas.DeviceGroupResponse)
def update_group_partial(
        group_id: int,
        group_data: schemas.DeviceGroupUpdate,
        db: Session = Depends(get_db)
):
    """Частичное обновление группы (PATCH - только указанные поля)"""
    group_crud = crud.DeviceGroupCRUD(db)
    updated = group_crud.update_group(group_id, group_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Group not found")
    return updated


@router.delete("/groups/{group_id}")
def delete_group(
        group_id: int,
        db: Session = Depends(get_db)
):
    """Удаление группы"""
    group_crud = crud.DeviceGroupCRUD(db)
    success = group_crud.delete_group(group_id)
    if not success:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"message": "Group deleted successfully"}
