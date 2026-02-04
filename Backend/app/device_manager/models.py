# app/device_manager/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class DeviceGroup(Base):
    """Модель группы устройств"""
    __tablename__ = "device_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # Название группы (уникальное).
    description = Column(Text, nullable=True)  # Описание/назначение группы.
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # Дата создания записи.
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())  # Дата последнего обновления записи.

    # relationship — связь ORM между моделями (без явного хранения в БД),
    # описывающая доступ к связанным объектам через foreign key.
    devices = relationship("Device", back_populates="group")  # Список устройств в группе.
    task_targets = relationship("TaskTarget", back_populates="group")  # Цели задач, связанные с группой.


class Device(Base):
    """Модель устройства MikroTik"""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # Имя/идентификатор устройства.
    description = Column(Text, nullable=True)  # Дополнительная информация об устройстве.

    # Параметры подключения
    host = Column(String(100), nullable=False)  # IP/домен для подключения.
    api_port = Column(Integer, default=8728)  # Порт API RouterOS.
    ssh_port = Column(Integer, default=22)  # Порт SSH.
    username = Column(String(100), nullable=False)  # Логин для подключения.
    encrypted_password = Column(Text, nullable=False)  # Пароль (в зашифрованном виде).

    # Группировка
    # ForeignKey — ссылка на первичный ключ другой таблицы (device_groups.id),
    # которая физически хранится в БД и обеспечивает целостность данных.
    group_id = Column(Integer, ForeignKey("device_groups.id"), nullable=True)

    # Статус
    is_online = Column(Boolean, default=False)  # Признак доступности устройства.
    last_seen = Column(DateTime(timezone=True), nullable=True)  # Когда устройство было доступно последний раз.
    last_backup = Column(DateTime(timezone=True), nullable=True)  # Когда был сделан последний бэкап.

    # Настройки
    use_ssl = Column(Boolean, default=False)  # Использовать SSL для API.
    check_interval = Column(Integer, default=300)  # Интервал проверки состояния (в секундах).

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # Дата создания записи.
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())  # Дата последнего обновления записи.

    # relationship — ORM-связь на основе ForeignKey: дает доступ к связанным сущностям.
    group = relationship("DeviceGroup", back_populates="devices")  # Группа, к которой относится устройство.
    task_targets = relationship("TaskTarget", back_populates="device")  # Цели задач, связанные с устройством.
    task_results = relationship("TaskResult", back_populates="device")  # Результаты задач по устройству.
