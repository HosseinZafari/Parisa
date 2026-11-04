import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from .auth import password_hash
from .db import Base, SessionLocal, engine
from .models import Seller
from .seed import ensure_seller, seed


def migrate():
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")


def main():
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="ابزار مدیریت پایگاه دادهٔ پریسا")
    parser.add_argument("action", choices=["migrate", "seed", "reset-demo", "set-password", "check-llm"])
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    if args.action == "check-llm":
        from .llm import check_connection

        status = check_connection()
        print(status["message"])
        if status["model"]:
            print("مدل:", status["model"])
        if status["http_status"]:
            print("وضعیت HTTP:", status["http_status"])
        raise SystemExit(0 if status["status"] in {"ready", "mock"} else 1)
    if args.action == "reset-demo":
        from .config import settings

        if settings().app_env != "local" or not args.yes:
            parser.error("بازنشانی فقط در محیط محلی با --yes مجاز است.")
        # ترتیب وابستگی دوری conversations/orders را برای حذف محلی کنترل می‌کنیم.
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            for table in reversed(Base.metadata.sorted_tables):
                conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{table.name}"')
            conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
            conn.commit()
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        migrate()
        with SessionLocal() as db:
            seed(db)
        print("داده‌های نمایشی از نو ساخته شدند.")
    elif args.action == "migrate":
        migrate()
        print("ساختار پایگاه داده به‌روز شد.")
    elif args.action == "seed":
        with SessionLocal() as db:
            seed(db)
    else:
        import getpass

        password = getpass.getpass("گذرواژهٔ تازه: ")
        if len(password) < 14:
            parser.error("گذرواژه باید حداقل ۱۴ نویسه باشد.")
        with SessionLocal() as db:
            ensure_seller(db)
            seller = db.scalar(select(Seller))
            seller.password_hash = password_hash(password)
            from .models import SellerSession
            from sqlalchemy import delete

            db.execute(delete(SellerSession))
            db.commit()
        print("گذرواژه تغییر کرد و نشست‌های قبلی بسته شدند.")


if __name__ == "__main__":
    main()
