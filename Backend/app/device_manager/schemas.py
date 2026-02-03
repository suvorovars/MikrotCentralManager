# app/device_manager/schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class DeviceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    host: str = Field(..., pattern=r'^(\d{1,3}\.){3}\d{1,3}$|^[a-zA-Z0-9.-]+$')
    api_port: int = Field(8728, ge=1, le=65535)
    ssh_port: int = Field(22, ge=1, le=65535)
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    group_id: Optional[int] = None
    use_ssl: bool = False
    check_interval: int = Field(300, ge=60)


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    """Схема для частичного обновления устройства"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    host: Optional[str] = Field(None, pattern=r'^(\d{1,3}\.){3}\d{1,3}$|^[a-zA-Z0-9.-]+$')
    api_port: Optional[int] = Field(None, ge=1, le=65535)
    ssh_port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=1)
    group_id: Optional[int] = None
    use_ssl: Optional[bool] = None
    check_interval: Optional[int] = Field(None, ge=60)

    @validator('password')
    def validate_password(cls, v):
        """Валидация пароля - если передали, должен быть непустым"""
        if v is not None and len(v) < 1:
            raise ValueError('Password must be at least 1 character long')
        return v


class DeviceResponse(BaseModel):
    id: int
    name: str
    host: str
    api_port: int
    ssh_port: int
    username: str
    group_id: Optional[int]
    is_online: bool
    last_seen: Optional[datetime]
    last_backup: Optional[datetime]
    use_ssl: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DeviceStatusResponse(DeviceResponse):
    connection_time: Optional[float] = None
    api_available: bool = False
    ssh_available: bool = False
    error_message: Optional[str] = None


class DeviceGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class DeviceGroupCreate(DeviceGroupBase):
    pass


class DeviceGroupUpdate(BaseModel):
    """Схема для частичного обновления группы"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class DeviceGroupResponse(DeviceGroupBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DeviceGroupDetail(DeviceGroupResponse):
    device_count: int = 0


class DeviceGroupWithDevices(DeviceGroupDetail):
    devices: List[DeviceResponse] = []