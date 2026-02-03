# app/device_manager/service.py
from typing import List, Optional, Dict, Any
from mikrotik_connector import MikroTikConnector
from device_manager import crud, schemas
from sqlalchemy.orm import Session
import asyncio
import socket
import time


class DeviceService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = crud.DeviceCRUD(db)

    async def check_device_availability(self, device_id: int) -> Optional[schemas.DeviceStatusResponse]:
        """Проверка доступности устройства"""
        device_data = self.crud.get_device_with_password(device_id)
        if not device_data:
            return None

        # Получаем полную информацию об устройстве для ответа
        device = self.crud.get_device(device_id)
        if not device:
            return None

        # Создаем базовый ответ из модели устройства
        status_data = schemas.DeviceResponse.from_orm(device).dict()

        # Создаем объект статуса
        status = schemas.DeviceStatusResponse(**status_data)

        # Проверка ping и порта
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((device_data['host'], device_data['api_port']))
            sock.close()
            status.connection_time = time.time() - start_time

            if result == 0:
                # Создаем коннектор
                connector = MikroTikConnector(
                    host=device_data['host'],
                    username=device_data['username'],
                    password=device_data['password'],
                    api_port=device_data['api_port'],
                    ssh_port=device_data['ssh_port'],
                    use_ssl=device_data['use_ssl'],
                    api_timeout=5
                )

                try:
                    # Подключаемся
                    await connector.connect()

                    # Проверяем доступность API
                    status.api_available = connector.api_connection is not None

                    # Проверяем доступность SSH
                    status.ssh_available = connector.ssh_client is not None

                    # Тестовая команда через унифицированный интерфейс
                    if connector.api_connection:
                        try:
                            test_result = await connector.ros_execute(
                                path="/system/identity",
                                action="print"
                            )
                            status.api_available = test_result is not None and len(test_result) > 0
                        except Exception as api_test_error:
                            print(f"API test command failed: {api_test_error}")
                            status.api_available = False

                    status.is_online = True

                finally:
                    # Всегда отключаемся
                    await connector.disconnect()

            else:
                status.is_online = False
                status.error_message = "Port is closed"

        except Exception as e:
            status.is_online = False
            status.error_message = str(e)

        # Обновляем статус в БД
        self.crud.update_device_status(device_id, status.is_online)

        return status

    async def check_multiple_devices(self, device_ids: List[int]) -> List[schemas.DeviceStatusResponse]:
        """Проверка доступности нескольких устройств параллельно"""
        tasks = [self.check_device_availability(device_id) for device_id in device_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Фильтруем исключения и None
        valid_results = []
        for result in results:
            if not isinstance(result, Exception) and result is not None:
                valid_results.append(result)

        return valid_results

    def get_device_credentials(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Получение учетных данных устройства"""
        return self.crud.get_device_with_password(device_id)

    def get_device_for_api(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Получение устройства для использования в API MikroTik"""
        device_data = self.crud.get_device_with_password(device_id)
        if device_data:
            return {
                'host': device_data['host'],
                'username': device_data['username'],
                'password': device_data['password'],
                'api_port': device_data['api_port'],
                'ssh_port': device_data['ssh_port'],
                'use_ssl': device_data['use_ssl']
            }
        return None

    async def execute_routeros_command(
            self,
            device_id: int,
            path: str,
            action: str,
            params: Optional[Dict] = None,
            where: Optional[Dict] = None
    ) -> List[Dict]:
        """Выполнение команды на устройстве через унифицированный интерфейс"""
        device_data = self.get_device_credentials(device_id)
        if not device_data:
            raise ValueError(f"Device {device_id} not found or credentials missing")

        connector = MikroTikConnector(
            host=device_data['host'],
            username=device_data['username'],
            password=device_data['password'],
            api_port=device_data['api_port'],
            ssh_port=device_data['ssh_port'],
            use_ssl=device_data['use_ssl']
        )

        try:
            await connector.connect()
            return await connector.ros_execute(
                path=path,
                action=action,
                params=params or {},
                where=where or {}
            )
        finally:
            await connector.disconnect()


class DeviceGroupService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = crud.DeviceGroupCRUD(db)
        self.device_crud = crud.DeviceCRUD(db)

    def get_group_with_devices(self, group_id: int) -> Optional[schemas.DeviceGroupWithDevices]:
        """Получение группы со всеми устройствами"""
        group = self.crud.get_group(group_id)
        if not group:
            return None

        devices = self.device_crud.get_devices_by_group(group_id)

        return schemas.DeviceGroupWithDevices(
            id=group.id,
            name=group.name,
            description=group.description,
            device_count=len(devices),
            created_at=group.created_at,
            devices=[schemas.DeviceResponse.from_orm(device) for device in devices]
        )

    def get_group_devices_credentials(self, group_id: int) -> List[Dict[str, Any]]:
        """Получение учетных данных всех устройств в группе"""
        devices = self.device_crud.get_devices_by_group(group_id)
        credentials = []

        for device in devices:
            creds = self.device_crud.get_device_with_password(device.id)
            if creds:
                credentials.append({
                    'device_id': device.id,
                    'device_name': device.name,
                    'host': creds['host'],
                    'username': creds['username'],
                    'password': creds['password'],
                    'api_port': creds['api_port'],
                    'ssh_port': creds['ssh_port'],
                    'use_ssl': creds['use_ssl']
                })

        return credentials

    async def check_group_devices_availability(self, group_id: int) -> List[schemas.DeviceStatusResponse]:
        """Проверка доступности всех устройств в группе"""
        devices = self.device_crud.get_devices_by_group(group_id)
        device_ids = [device.id for device in devices]

        # Используем DeviceService для проверки
        device_service = DeviceService(self.db)
        return await device_service.check_multiple_devices(device_ids)