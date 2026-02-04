import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Загружаем переменные окружения из файла .env, чтобы они были доступны через os.getenv.
load_dotenv()

# Формируем DATABASE_URL из переменной окружения, содержащей строку подключения к БД.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL must be set. Example: "
        "postgresql+psycopg2://user:password@localhost:5432/mikrotik_manager"
    )

# Создаем engine подключения; для SQLite добавляем check_same_thread=False,
# чтобы разрешить доступ к соединению из разных потоков.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

# SessionLocal — фабрика сессий SQLAlchemy для работы с транзакциями.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base — базовый класс для декларативных моделей.
Base = declarative_base()


# get_db() — генератор, который выдает сессию и гарантирует ее закрытие
# после завершения запроса (через finally).
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
