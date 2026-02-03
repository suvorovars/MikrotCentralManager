# app/device_manager/crud.py
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from device_manager import models, schemas
from security import encrypt_password, decrypt_password
from sqlalchemy import func  # Добавьте этот импорт


class DeviceCRUD:
    def __init__(self, db: Session):
        self.db = db

    def create_device(self, device_data: schemas.DeviceCreate) -> models.Device:
        """Создание нового устройства с шифрованием пароля"""
        encrypted_password = encrypt_password(device_data.password)

        db_device = models.Device(
            name=device_data.name,
            description=device_data.description,
            host=device_data.host,
            api_port=device_data.api_port,
            ssh_port=device_data.ssh_port,
            username=device_data.username,
            encrypted_password=encrypted_password,
            group_id=device_data.group_id,
            use_ssl=device_data.use_ssl,
            check_interval=device_data.check_interval
        )

        self.db.add(db_device)
        self.db.commit()
        self.db.refresh(db_device)
        return db_device

    def get_device(self, device_id: int) -> Optional[models.Device]:
        """Получение устройства по ID"""
        return self.db.query(models.Device).filter(models.Device.id == device_id).first()

    def get_device_with_password(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Получение устройства с расшифрованным паролем"""
        device = self.get_device(device_id)
        if device:
            return {
                'id': device.id,
                'name': device.name,
                'description': device.description,
                'host': device.host,
                'api_port': device.api_port,
                'ssh_port': device.ssh_port,
                'username': device.username,
                'password': decrypt_password(device.encrypted_password),
                'group_id': device.group_id,
                'use_ssl': device.use_ssl,
                'check_interval': device.check_interval,
                'is_online': device.is_online,
                'last_seen': device.last_seen,
                'last_backup': device.last_backup
            }
        return None

    def get_devices_by_group(self, group_id: int) -> List[models.Device]:
        """Получение всех устройств в группе"""
        return self.db.query(models.Device).filter(
            models.Device.group_id == group_id
        ).all()

    def get_all_devices(self, skip: int = 0, limit: int = 100) -> List[models.Device]:
        """Получение всех устройств с пагинацией"""
        return self.db.query(models.Device).offset(skip).limit(limit).all()

    def update_device(self, device_id: int, device_data: schemas.DeviceUpdate) -> Optional[models.Device]:
        """Частичное обновление устройства (только переданные поля)"""
        db_device = self.get_device(device_id)
        if not db_device:
            return None

        # Получаем только переданные поля (исключаем None)
        update_data = device_data.model_dump(exclude_unset=True, exclude_none=True)

        # Обработка пароля
        if 'password' in update_data:
            update_data['encrypted_password'] = encrypt_password(update_data.pop('password'))

        # Обновляем только переданные поля
        for field, value in update_data.items():
            setattr(db_device, field, value)

        self.db.commit()
        self.db.refresh(db_device)
        return db_device

    def delete_device(self, device_id: int) -> bool:
        """Удаление устройства"""
        db_device = self.get_device(device_id)
        if not db_device:
            return False

        self.db.delete(db_device)
        self.db.commit()
        return True

    def update_device_status(self, device_id: int, is_online: bool) -> None:
        """Обновление статуса устройства"""
        db_device = self.get_device(device_id)
        if db_device:
            db_device.is_online = is_online
            if is_online:
                from sqlalchemy.sql import func
                db_device.last_seen = func.now()
            self.db.commit()

    def update_last_backup(self, device_id: int, backup_time) -> None:
        """Обновление времени последнего бэкапа"""
        db_device = self.get_device(device_id)
        if db_device:
            db_device.last_backup = backup_time
            self.db.commit()


class DeviceGroupCRUD:
    def __init__(self, db: Session):
        self.db = db

    def create_group(self, group_data: schemas.DeviceGroupCreate) -> models.DeviceGroup:
        """Создание новой группы"""
        db_group = models.DeviceGroup(
            name=group_data.name,
            description=group_data.description
        )

        self.db.add(db_group)
        self.db.commit()
        self.db.refresh(db_group)
        return db_group

    def get_group(self, group_id: int) -> Optional[models.DeviceGroup]:
        """Получение группы по ID"""
        return self.db.query(models.DeviceGroup).filter(
            models.DeviceGroup.id == group_id
        ).first()

    def get_all_groups(self) -> List[models.DeviceGroup]:
        """Получение всех групп"""
        return self.db.query(models.DeviceGroup).all()

    def update_group(self, group_id: int, group_data: schemas.DeviceGroupUpdate) -> Optional[models.DeviceGroup]:
        """Частичное обновление группы (только переданные поля)"""
        db_group = self.get_group(group_id)
        if not db_group:
            return None

        # Получаем только переданные поля (исключаем None)
        update_data = group_data.model_dump(exclude_unset=True, exclude_none=True)

        # Обновляем только переданные поля
        for field, value in update_data.items():
            setattr(db_group, field, value)

        self.db.commit()
        self.db.refresh(db_group)
        return db_group

    def delete_group(self, group_id: int) -> bool:
        """Удаление группы (устройства остаются без группы)"""
        db_group = self.get_group(group_id)
        if not db_group:
            return False

        # Сбрасываем группу у всех устройств
        for device in db_group.devices:
            device.group_id = None

        self.db.delete(db_group)
        self.db.commit()
        return True
