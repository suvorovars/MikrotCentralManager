# main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from db import engine, Base

from device_manager.api import router as device_router
from backup_manager.api import router as backup_router
from task_manager import models as task_models
from firewall_manager.api import router as firewall_router

import uvicorn

from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Создаем таблицы в БД при старте
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

    yield  # Здесь приложение запущено и готово обрабатывать запросы

    # Код очистки при завершении
    print("Shutting down application...")


# Создаем FastAPI приложение
app = FastAPI(
    title="MikroTik ITT Central Manager",
    description="Веб-приложение для централизованного управления устройствами MikroTik",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры микросервисов

app.include_router(device_router)
app.include_router(backup_router)
app.include_router(firewall_router)



# Маршруты для проверки здоровья приложения
@app.get("/")
async def root():
    """Корневой маршрут - информация о приложении"""
    return {
        "message": "MikroTik ITT Central Manager API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Проверка состояния приложения"""
    return {
        "status": "healthy",
        "database": "connected",
        "timestamp": "2024-01-13T10:00:00Z"
    }


@app.get("/api/v1/status")
async def api_status():
    """Статус API"""
    return {
        "api_version": "1.0",
        "services": {
            "device_manager": "active",
            "firewall_manager": "active",
            "mikrotik_connector": "active"
        },
        "endpoints": {
            "devices": "/devices/",
            "device_groups": "/devices/groups/",
            "device_status": "/devices/{id}/status",
            "firewall_lists": "/firewall/lists/"
        }
    }


# Кастомная документация Swagger
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="MikroTik Manager API",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


# Кастомная OpenAPI схема
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="MikroTik ITT Central Manager API",
        version="1.0.0",
        description="API для управления устройствами MikroTik",
        routes=app.routes,
    )

    # Добавляем информацию о безопасности
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"

    )

