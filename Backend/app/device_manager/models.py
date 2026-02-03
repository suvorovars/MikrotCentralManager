# app/device_manager/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class DeviceGroup(Base):
    """Модель группы устройств"""
    __tablename__ = "device_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    devices = relationship("Device", back_populates="group")
    task_targets = relationship("TaskTarget", back_populates="group")


class Device(Base):
    """Модель устройства MikroTik"""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Параметры подключения
    host = Column(String(100), nullable=False)
    api_port = Column(Integer, default=8728)
    ssh_port = Column(Integer, default=22)
    username = Column(String(100), nullable=False)
    encrypted_password = Column(Text, nullable=False)

    # Группировка
    group_id = Column(Integer, ForeignKey("device_groups.id"), nullable=True)

    # Статус
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    last_backup = Column(DateTime(timezone=True), nullable=True)

    # Настройки
    use_ssl = Column(Boolean, default=False)
    check_interval = Column(Integer, default=300)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    group = relationship("DeviceGroup", back_populates="devices")
    task_targets = relationship("TaskTarget", back_populates="device")
    task_results = relationship("TaskResult", back_populates="device")
