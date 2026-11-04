import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.auth import limiter, password_hash
from app.config import settings
from app.db import Base, get_db, make_engine
from app.main import app
from app.models import Customer, Product, ProductRequirement, Seller


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = make_engine("sqlite:///" + (tmp_path / "test.db").as_posix())
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    limiter.buckets.clear()
    config = settings()
    monkeypatch.setattr("app.llm_status._state", {"status": "not_checked", "checked_at": None, "http_status": None})
    monkeypatch.setattr("app.llm_status._retry_at", 0.0)
    monkeypatch.setattr(config, "llm_mode", "mock")
    monkeypatch.setattr(config, "instagram_mode", "mock")
    monkeypatch.setattr(config, "instagram_app_secret", "test-instagram-secret")
    monkeypatch.setattr(config, "instagram_account_id", "123456")
    monkeypatch.setattr(config, "instagram_verify_token", "test-verify")
    with sessions() as db:
        db.add(Seller(username="seller", name="پریسا", password_hash=password_hash("test-password-123")))
        db.add(
            Customer(
                name="سارا آزمایشی",
                username="sara",
                phone="09120000000",
                city="تهران",
                address="نشانی ساختگی، خیابان نمونه پلاک ۱۲",
                postal_code="1111111111",
            )
        )
        db.add(
            Product(
                name="شمع آوا",
                aliases=["شمع", "آوا"],
                price=100000,
                inventory=100,
                shipping_cost=30000,
                preparation_days=2,
            )
        )
        db.flush()
        db.add_all(
            [
                ProductRequirement(product_id=1, key="scent", label="رایحه", allowed_values=["وانیل", "اسطوخودوس"]),
                ProductRequirement(
                    product_id=1,
                    key="size",
                    label="اندازه",
                    allowed_values=["کوچک", "بزرگ"],
                    price_adjustments={"بزرگ": 50000},
                ),
                ProductRequirement(
                    product_id=1,
                    key="packaging",
                    label="بسته‌بندی",
                    allowed_values=["معمولی", "هدیه"],
                    price_adjustments={"هدیه": 20000},
                ),
            ]
        )
        db.commit()

    def override_db():
        with sessions() as db:
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield {
        "client": client,
        "sessions": sessions,
        "engine": engine,
        "path": tmp_path / "test.db",
        "db_dependency": override_db,
    }
    app.dependency_overrides.clear()
    client.close()
    engine.dispose()


@pytest.fixture
def client(env):
    return env["client"]


@pytest.fixture
def seller(client):
    response = client.post("/api/auth/login", json={"username": "seller", "password": "test-password-123"})
    assert response.status_code == 200
    return client


def key():
    return {"Idempotency-Key": secrets.token_hex(16)}


def draft():
    return {
        "customer_id": 1,
        "product_id": 1,
        "quantity": 2,
        "specifications": {"scent": "وانیل", "size": "کوچک", "packaging": "معمولی"},
        "delivery": {
            "name": "سارا آزمایشی",
            "phone": "09120000000",
            "city": "تهران",
            "address": "نشانی ساختگی، خیابان نمونه پلاک ۱۲",
            "postal_code": "1111111111",
        },
    }


def new_order(client):
    response = client.post("/api/orders", json=draft(), headers=key())
    assert response.status_code == 200, response.text
    return response.json()


def new_payment(client, order):
    response = client.post(f"/api/orders/{order['id']}/payment-link", headers=key())
    assert response.status_code == 200, response.text
    return response.json()["url"].split("/")[-1]


def paid_order(client):
    order = new_order(client)
    token = new_payment(client, order)
    assert client.post(f"/api/payments/{token}/simulate", json={"outcome": "success"}).json()["status"] == "success"
    return client.get(f"/api/orders/{order['id']}").json()


def ready_order(client):
    order = paid_order(client)
    for status in ["in_preparation", "ready_to_ship"]:
        response = client.post(
            f"/api/orders/{order['id']}/status", headers=key(), json={"status": status, "version": order["version"]}
        )
        assert response.status_code == 200, response.text
        order = response.json()
    return order
