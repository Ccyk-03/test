"""数据库引擎与会话管理（SQLite + SQLAlchemy 2.x）。"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# 确保数据目录存在（SQLite 文件位于 backend/data/app.db）
if settings.database_url.startswith("sqlite:///"):
    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)

# SQLite 需关闭同线程检查；FastAPI 每请求使用独立 session
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db():
    """FastAPI 依赖：每请求一个独立数据库会话，用完自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
