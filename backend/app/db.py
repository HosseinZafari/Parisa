from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import ROOT, settings


class Base(DeclarativeBase):
    pass


def make_engine(url):
    if url.startswith("sqlite:///./"):
        target = ROOT / "backend" / url.removeprefix("sqlite:///./")
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{target.as_posix()}"
    elif url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        hide_parameters=True,
        connect_args={"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {},
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def sqlite_setup(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")

    return engine


engine = make_engine(settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        # یک نویسنده در SQLite؛ خواندن موجودی و اثر پرداخت در همان تراکنش اتمی است.
        if db.bind.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
