from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.config import settings
from app.db import Base, make_engine
from app.main import app
from app.models import Product, ProductRequirement
from conftest import draft, key, new_order, new_payment, paid_order
from test_order_flow import message


def test_ambiguous_product_preserves_quantity_and_other_data(client, env):
    with env["sessions"]() as db:
        original = db.get(Product, 1)
        second = Product(
            name="شمع سپید",
            aliases=["شمع", "سپید"],
            price=120000,
            inventory=10,
            shipping_cost=30000,
            preparation_days=2,
        )
        db.add(second)
        db.flush()
        for r in db.scalars(select(ProductRequirement).where(ProductRequirement.product_id == original.id)):
            db.add(
                ProductRequirement(
                    product_id=second.id,
                    key=r.key,
                    label=r.label,
                    required=r.required,
                    allowed_values=r.allowed_values,
                    price_adjustments=r.price_adjustments,
                )
            )
        db.commit()
    token = client.post("/api/chat/start", json={}).json()["token"]
    state = message(client, token, "سه عدد شمع وانیل کوچک معمولی؛ نام: سارا")
    assert "چند محصول" in state["messages"][-1]["text"]
    assert state["draft"]["quantity"] == 3
    state = message(client, token, "شمع سپید")
    assert state["draft"]["quantity"] == 3 and state["draft"]["delivery"]["name"] == "سارا"
    assert state["draft"]["specifications"]["scent"] == "وانیل"
    assert "تعداد" not in state["messages"][-1]["text"]


def test_customer_chat_change_and_repeat(seller, env):
    token = seller.post("/api/chat/start", json={}).json()["token"]
    message(seller, token, "یک عدد شمع آوا وانیل کوچک معمولی")
    message(seller, token, "نام: سارا؛ تلفن: 09120000000؛ شهر: تهران؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی: 1111111111")
    state = message(seller, token, "تأیید سفارش")
    order_id = state["order"]["id"]
    assert state["payment"]
    changed = message(seller, token, "تغییر تعداد: ۴")
    assert changed["order"]["quantity"] == 1 and changed["order"]["changes"][0]["status"] == "pending"
    message(seller, token, "سفارش جدید")
    repeated = message(seller, token, "تکرار سفارش")
    assert repeated["draft"]["quantity"] == 1 and repeated["draft"]["delivery"]["name"] == "سارا"
    assert not repeated["order"] and not repeated["payment"]
    repeated = message(seller, token, "تأیید سفارش")
    assert repeated["ready_to_confirm"] and not repeated["order"]
    repeated = message(seller, token, "تأیید سفارش")
    assert repeated["order"]["id"] != order_id


def test_start_review_and_cancel_resolves_change(seller, env):
    order = paid_order(seller)
    response = seller.post(f"/api/orders/{order['id']}/changes", headers=key(), json={"quantity": 3})
    change = response.json()
    assert seller.post(f"/api/changes/{change['id']}/review", headers=key(), json={}).status_code == 200
    reviewed = seller.get("/api/orders/" + str(order["id"])).json()
    assert reviewed["status"] == "awaiting_seller_approval"
    response = seller.post(
        f"/api/orders/{order['id']}/status", headers=key(), json={"status": "canceled", "version": reviewed["version"]}
    )
    assert response.status_code == 200 and not response.json()["pending_change"]
    with env["sessions"]() as db:
        assert db.get(Product, 1).inventory == 100


def test_payment_retry_has_fresh_link(seller):
    order = new_order(seller)
    old = new_payment(seller, order)
    seller.post(f"/api/payments/{old}/simulate", json={"outcome": "failed"})
    new = new_payment(seller, order)
    assert new != old
    assert seller.post(f"/api/payments/{old}/simulate", json={"outcome": "success"}).json()["status"] == "failed"
    assert seller.post(f"/api/payments/{new}/simulate", json={"outcome": "success"}).json()["status"] == "success"


def test_stock_cannot_be_oversold(seller, env):
    with env["sessions"]() as db:
        db.get(Product, 1).inventory = 2
        db.commit()
    new_order(seller)
    response = seller.post("/api/orders", headers=key(), json=draft())
    assert response.status_code == 409


def test_api_limits_and_secrets(seller):
    config = seller.get("/api/settings").json()
    assert not any("secret" in k or "token" in k or "api_key" in k for k in config)
    response = seller.post("/api/chat/start", content=b"x" * 65537)
    assert response.status_code == 413
    order = new_order(seller)
    assert (
        seller.patch(
            "/api/orders/" + str(order["id"]), headers=key(), json={"version": order["version"], "seller_notes": None}
        ).status_code
        == 422
    )


def test_migration_builds_schema_and_second_upgrade_is_safe(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "migration.db").as_posix()
    monkeypatch.setattr(settings(), "database_url", url)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")
    engine = make_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert set(Base.metadata.tables) <= tables
    engine.dispose()


def test_application_lifespan_restarts_preserve_chat(seller, env, monkeypatch):
    import asyncio

    token = seller.post("/api/chat/start", json={}).json()["token"]
    state = message(seller, token, "دو عدد شمع آوا وانیل کوچک معمولی")
    monkeypatch.setattr("app.main.SessionLocal", env["sessions"])
    monkeypatch.setattr(settings(), "seed_demo", False)

    async def no_external_worker():
        await asyncio.sleep(3600)

    monkeypatch.setattr("app.main.worker", no_external_worker)
    with TestClient(app) as restarted:
        response = restarted.get("/api/chat/" + token)
        assert response.status_code == 200 and response.json()["messages"] == state["messages"]
    with TestClient(app) as restarted:
        assert restarted.get("/api/chat/" + token).json()["draft"]["quantity"] == 2


def test_stale_catalog_cannot_restore_reserved_stock(seller, env):
    product = seller.get("/api/products").json()[0]
    ident = product.pop("id")
    new_order(seller)
    product["description"] = "توضیح تازه"
    assert seller.put("/api/products/" + str(ident), headers=key(), json=product).status_code == 409
    with env["sessions"]() as db:
        assert db.get(Product, ident).inventory == 98


def test_private_note_keeps_existing_payment_valid(seller):
    order = new_order(seller)
    token = new_payment(seller, order)
    response = seller.patch(
        "/api/orders/" + str(order["id"]),
        headers=key(),
        json={"version": order["version"], "seller_notes": "بسته را بررسی کنم."},
    )
    assert response.status_code == 200
    assert seller.get("/api/payments/" + token).json()["status"] == "pending"
    assert (
        seller.post("/api/payments/" + token + "/simulate", json={"outcome": "success"}).json()["status"] == "success"
    )
