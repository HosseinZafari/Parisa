from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import hmac
import json
import secrets

import pytest
from sqlalchemy import select

from app.config import settings
from app.domain import product_data, today
from app.llm import match_products, mock_extract
from app.models import Notification, Order, OrderHistory, OrderRequirementValue, Payment, Product, now
from conftest import draft, key, new_order, new_payment, paid_order, ready_order


def message(client, token, text, ident=None):
    response = client.post(
        f"/api/chat/{token}/messages", json={"text": text, "client_id": ident or secrets.token_hex(16)}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_product_matching_and_extraction(env):
    with env["sessions"]() as db:
        products = [product_data(db, db.get(Product, 1))]
        assert match_products("دو عدد شمع آوا", products)[0]["id"] == 1
        result = mock_extract("دو عدد شمع آوا وانیل بزرگ هدیه", products, {})
        assert result.quantity == 2
        assert result.specifications == {"scent": "وانیل", "size": "بزرگ", "packaging": "هدیه"}


def test_chat_collects_only_missing_and_confirms(client, env):
    chat = client.post("/api/chat/start", json={}).json()
    token = chat["token"]
    state = message(client, token, "دو عدد شمع آوا، وانیل، کوچک، معمولی")
    assert "نام گیرنده" in state["messages"][-1]["text"]
    assert "رایحه" not in state["messages"][-1]["text"]
    state = message(
        client, token, "نام: سارا؛ شهر: تهران؛ تلفن: ۰۹۱۲۰۰۰۰۰۰۰؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی: ۱۱۱۱۱۱۱۱۱۱"
    )
    assert state["ready_to_confirm"]
    assert state["order"] is None
    assert state["summary"]["total"] == 230000
    state = message(client, token, "اصلاح تعداد: ۳")
    assert state["draft"]["quantity"] == 3
    state = message(client, token, "تأیید سفارش")
    assert state["order"]["status"] == "awaiting_payment"
    assert state["payment"]["amount"] == 330000
    assert len(state["order"]["specifications"]) == 3
    with env["sessions"]() as db:
        assert db.get(Product, 1).inventory == 97


def test_premature_confirmation_and_payment_claim_are_not_payment(client):
    token = client.post("/api/chat/start", json={}).json()["token"]
    state = message(client, token, "تأیید سفارش")
    assert state["order"] is None
    assert state["payment"] is None
    state = message(client, token, "پرداخت کردم، عکس رسید فرستادم")
    assert state["order"] is None


def test_correction_and_ambiguous_requirement(client):
    token = client.post("/api/chat/start", json={}).json()["token"]
    state = message(client, token, "یک عدد شمع آوا وانیل اسطوخودوس کوچک معمولی")
    assert "مبهم" in state["messages"][-1]["text"]
    assert "scent" not in state["draft"]["specifications"]
    state = message(client, token, "اصلاح رایحه: اسطوخودوس")
    assert state["draft"]["specifications"]["scent"] == "اسطوخودوس"
    assert "مبهم" not in state["messages"][-1]["text"]


def test_duplicate_chat_and_handover(client, seller):
    token = client.post("/api/chat/start", json={}).json()["token"]
    ident = secrets.token_hex(16)
    first = message(client, token, "یک عدد شمع آوا", ident)
    assert message(client, token, "یک عدد شمع آوا", ident) == first
    state = message(client, token, "فروشنده")
    assert state["handover"]
    conv = client.get("/api/conversations").json()[0]
    client.post(
        f"/api/conversations/{conv['id']}/reply", headers=key(), json={"text": "سلام، در خدمتم.", "resume_bot": False}
    )
    assert client.get("/api/chat/" + token).json()["messages"][-1]["role"] == "seller"


def test_order_creation_is_idempotent_and_validated(seller):
    headers = key()
    first = seller.post("/api/orders", json=draft(), headers=headers)
    assert first.status_code == 200
    assert seller.post("/api/orders", json=draft(), headers=headers).json()["id"] == first.json()["id"]
    changed = {**draft(), "quantity": 3}
    assert seller.post("/api/orders", json=changed, headers=headers).status_code == 409
    invalid = draft()
    invalid["delivery"]["phone"] = "1234"
    assert seller.post("/api/orders", json=invalid, headers=key()).status_code == 422


def test_opening_payment_does_not_pay(seller, env):
    order = new_order(seller)
    token = new_payment(seller, order)
    assert seller.get("/api/payments/" + token).json()["status"] == "pending"
    with env["sessions"]() as db:
        assert db.get(Order, order["id"]).paid_amount == 0


@pytest.mark.parametrize("outcome", ["success", "failed", "canceled", "expired"])
def test_simulated_payment_outcomes(seller, outcome, env):
    order = new_order(seller)
    token = new_payment(seller, order)
    response = seller.post(f"/api/payments/{token}/simulate", json={"outcome": outcome})
    assert response.status_code == 200
    assert response.json()["status"] == outcome
    with env["sessions"]() as db:
        saved = db.get(Order, order["id"])
        assert saved.paid_amount == (230000 if outcome == "success" else 0)
        assert saved.status == ("paid_awaiting_preparation" if outcome == "success" else "awaiting_payment")


def test_expired_by_clock(seller, env):
    token = new_payment(seller, new_order(seller))
    with env["sessions"]() as db:
        p = db.scalar(select(Payment).where(Payment.token == token))
        p.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert seller.get("/api/payments/" + token).json()["status"] == "expired"
    assert seller.post(f"/api/payments/{token}/simulate", json={"outcome": "success"}).json()["status"] == "expired"


def test_duplicate_and_concurrent_callbacks(seller, env):
    order = new_order(seller)
    token = new_payment(seller, order)
    payload = json.dumps({"event_id": "callback-123456", "payment_token": token, "outcome": "success"}).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Payment-Signature": hmac.new(settings().payment_secret.encode(), payload, hashlib.sha256).hexdigest(),
    }
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(
            pool.map(lambda _: seller.post("/api/payments/callback", content=payload, headers=headers), range(3))
        )
    assert all(r.status_code == 200 and r.json()["status"] == "success" for r in responses)
    # شناسهٔ رویداد تازه هم نباید همان پرداخت را دوباره اعمال کند.
    assert seller.post(f"/api/payments/{token}/simulate", json={"outcome": "success"}).json()["duplicate"]
    with env["sessions"]() as db:
        assert db.get(Order, order["id"]).paid_amount == 230000
        assert len(list(db.scalars(select(Notification).where(Notification.kind == "payment_success")))) == 1
        assert len(list(db.scalars(select(OrderHistory).where(OrderHistory.kind == "payment_success")))) == 1


def test_invalid_payment_signature_and_frontend_amount(seller):
    token = new_payment(seller, new_order(seller))
    assert (
        seller.post(
            "/api/payments/callback", json={"payment_token": token, "event_id": "test-event", "outcome": "success"}
        ).status_code
        == 403
    )
    assert seller.post(f"/api/payments/{token}/simulate", json={"outcome": "success", "amount": 1}).status_code == 422


def create_change(client, order, payload):
    response = client.post(f"/api/orders/{order['id']}/changes", headers=key(), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_change_keeps_active_values_and_rejection(seller):
    order = paid_order(seller)
    change = create_change(seller, order, {"quantity": 4})
    unchanged = seller.get(f"/api/orders/{order['id']}").json()
    assert unchanged["quantity"] == 2
    assert change["original"]["quantity"] == 2 and change["proposed"]["quantity"] == 4
    response = seller.post(f"/api/changes/{change['id']}/reject", headers=key(), json={"reason": "زمان کافی نداریم."})
    assert response.status_code == 200
    assert response.json()["resolved_at"] and response.json()["responsible_user"] == "seller"
    unchanged = seller.get(f"/api/orders/{order['id']}").json()
    assert unchanged["quantity"] == 2 and unchanged["total"] == 230000
    assert unchanged["status"] == "paid_awaiting_preparation"


def test_change_approval_additional_payment_old_link_invalid(seller, env):
    order = paid_order(seller)
    change = create_change(seller, order, {"quantity": 4, "specifications": {"size": "بزرگ"}})
    quote = seller.get(f"/api/changes/{change['id']}/quote").json()
    assert quote["total"] == 630000
    response = seller.post(f"/api/changes/{change['id']}/approve", headers=key(), json={})
    assert response.status_code == 200, response.text
    order = seller.get(f"/api/orders/{order['id']}").json()
    assert order["status"] == "awaiting_payment" and order["balance"] == 400000
    token = new_payment(seller, order)
    assert seller.get("/api/payments/" + token).json()["amount"] == 400000
    seller.post(f"/api/payments/{token}/simulate", json={"outcome": "success"})
    order = seller.get(f"/api/orders/{order['id']}").json()
    assert order["paid_amount"] == 630000
    with env["sessions"]() as db:
        assert db.get(Product, 1).inventory == 96


def test_amount_change_expires_old_payment(seller):
    order = new_order(seller)
    token = new_payment(seller, order)
    change = create_change(seller, order, {"quantity": 3})
    seller.post(f"/api/changes/{change['id']}/approve", headers=key(), json={})
    assert seller.post(f"/api/payments/{token}/simulate", json={"outcome": "success"}).json()["status"] == "expired"
    updated = seller.get(f"/api/orders/{order['id']}").json()
    assert updated["paid_amount"] == 0 and updated["total"] == 330000


def test_shipment_blocked_by_pending_change(seller):
    order = ready_order(seller)
    create_change(seller, order, {"quantity": 4})
    order = seller.get(f"/api/orders/{order['id']}").json()
    response = seller.post(
        f"/api/orders/{order['id']}/ship",
        headers=key(),
        json={"version": order["version"], "tracking_number": "1234567890"},
    )
    assert response.status_code == 409 and "تغییر" in response.json()["detail"]


@pytest.mark.parametrize("missing", ["specification", "address", "deadline", "payment"])
def test_shipment_blocks_each_required_condition(seller, env, missing):
    order = ready_order(seller)
    with env["sessions"]() as db:
        saved = db.get(Order, order["id"])
        if missing == "specification":
            value = db.scalar(select(OrderRequirementValue).where(OrderRequirementValue.key == "scent"))
            db.delete(value)
        elif missing == "address":
            saved.delivery = {**saved.delivery, "address": ""}
        elif missing == "deadline":
            saved.deadline = None
        else:
            saved.paid_amount = 0
        db.commit()
    response = seller.post(
        f"/api/orders/{order['id']}/ship",
        headers=key(),
        json={"version": order["version"], "tracking_number": "1234567890"},
    )
    assert response.status_code == 409


def test_shipping_tracking_idempotency_and_manual_change(seller):
    order = ready_order(seller)
    headers = key()
    payload = {"version": order["version"], "tracking_number": "1234567890"}
    shipped = seller.post(f"/api/orders/{order['id']}/ship", headers=headers, json=payload)
    assert shipped.status_code == 200 and shipped.json()["status"] == "shipped"
    assert seller.post(f"/api/orders/{order['id']}/ship", headers=headers, json=payload).json() == shipped.json()
    change = create_change(seller, order, {"quantity": 5})
    assert change["status"] == "manual"
    assert seller.get(f"/api/orders/{order['id']}").json()["quantity"] == 2


def test_invalid_transition_and_stale_version(seller):
    order = new_order(seller)
    assert (
        seller.post(
            f"/api/orders/{order['id']}/status",
            headers=key(),
            json={"version": order["version"], "status": "ready_to_ship"},
        ).status_code
        == 409
    )
    assert (
        seller.patch(
            f"/api/orders/{order['id']}", headers=key(), json={"version": 99, "seller_notes": "یادداشت"}
        ).status_code
        == 409
    )


def test_tracking_is_private_and_revocable(seller, client):
    order = paid_order(seller)
    token = order["tracking_url"].split("/")[-1]
    response = client.get("/api/tracking/" + token)
    assert response.status_code == 200
    assert (
        not {"seller_notes", "delivery", "customer_phone", "messages", "notifications", "tracking_token"}
        & response.json().keys()
    )
    assert client.get("/api/tracking/guessable").status_code == 404
    assert client.post("/api/tracking/" + token, json={"status": "shipped"}).status_code == 405
    seller.post(f"/api/orders/{order['id']}/tracking/revoke", headers=key())
    assert client.get("/api/tracking/" + token).status_code == 404


def test_seller_authorization_csrf_and_logout(client):
    for path in [
        "/api/orders",
        "/api/dashboard",
        "/api/products",
        "/api/customers",
        "/api/conversations",
        "/api/notifications",
    ]:
        assert client.get(path).status_code == 401
    assert client.post("/api/auth/login", json={"username": "seller", "password": "wrong"}).status_code == 401
    login = client.post("/api/auth/login", json={"username": "seller", "password": "test-password-123"})
    assert "HttpOnly" in login.headers["set-cookie"] and "SameSite=strict" in login.headers["set-cookie"]
    assert (
        client.post("/api/orders", headers={**key(), "Origin": "https://evil.example"}, json=draft()).status_code == 403
    )
    client.post("/api/auth/logout")
    assert client.get("/api/orders").status_code == 401


def test_dashboard_notifications_and_priority(seller, env):
    order = paid_order(seller)
    with env["sessions"]() as db:
        db.get(Order, order["id"]).deadline = (today() - timedelta(days=1)).isoformat()
        db.commit()
    first = seller.get("/api/dashboard").json()
    second = seller.get("/api/dashboard").json()
    assert first["overdue"] == 1 and first["queue"][0]["id"] == order["id"]
    assert second["unread_notifications"] == first["unread_notifications"]
    seller.post("/api/notifications/read-all")
    assert all(n["read"] for n in seller.get("/api/notifications").json())


def test_catalog_edits_do_not_change_confirmed_order(seller):
    order = paid_order(seller)
    product = seller.get("/api/products").json()[0]
    ident = product.pop("id")
    product["price"] = 900000
    product["requirements"] = []
    assert seller.put("/api/products/" + str(ident), headers=key(), json=product).status_code == 200
    unchanged = seller.get("/api/orders/" + str(order["id"])).json()
    assert unchanged["total"] == 230000 and len(unchanged["requirement_schema"]) == 3


def test_persistent_state_after_engine_restart(seller, env):
    from app.db import make_engine
    from sqlalchemy.orm import Session

    order = paid_order(seller)
    env["engine"].dispose()
    restarted = make_engine("sqlite:///" + env["path"].as_posix())
    with Session(restarted) as db:
        saved = db.get(Order, order["id"])
        assert saved.paid_amount == 230000
        assert saved.tracking_token == order["tracking_url"].split("/")[-1]
        assert db.scalar(select(OrderHistory).where(OrderHistory.order_id == saved.id))
    restarted.dispose()
