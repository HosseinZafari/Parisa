import hashlib
import hmac
import json
from types import SimpleNamespace

import httpx
from sqlalchemy import select

from app.config import settings
from app.domain import product_data
from app.instagram import process_inbox
from app.llm import extract
from app.models import Message, Product, WebhookEvent
from app.schemas import Draft, Extraction


def webhook():
    return {
        "object": "instagram",
        "entry": [
            {
                "id": "123456",
                "messaging": [
                    {
                        "sender": {"id": "customer-123"},
                        "recipient": {"id": "123456"},
                        "timestamp": 1793780000000,
                        "message": {"mid": "mid-test-123456", "text": "دو عدد شمع آوا وانیل کوچک معمولی"},
                    }
                ],
            }
        ],
    }


def signed(payload):
    raw = json.dumps(payload, ensure_ascii=False).encode()
    return raw, {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256="
        + hmac.new(settings().instagram_app_secret.encode(), raw, hashlib.sha256).hexdigest(),
    }


def test_webhook_signature_and_ownership(client):
    raw, headers = signed(webhook())
    assert client.post("/api/instagram/webhook", content=raw).status_code == 403
    assert client.post("/api/instagram/webhook", content=raw + b" ", headers=headers).status_code == 403
    assert (
        client.get(
            "/api/instagram/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "test-verify", "hub.challenge": "98765"},
        ).text
        == "98765"
    )
    assert (
        client.get("/api/instagram/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong"}).status_code
        == 403
    )


def test_duplicate_instagram_durable_inbox(client, env, monkeypatch):
    raw, headers = signed(webhook())
    assert client.post("/api/instagram/webhook", content=raw, headers=headers).json()["accepted"] == 1
    assert client.post("/api/instagram/webhook", content=raw, headers=headers).json()["accepted"] == 0
    monkeypatch.setattr("app.instagram.SessionLocal", env["sessions"])
    assert process_inbox()
    assert not process_inbox()
    with env["sessions"]() as db:
        messages = list(db.scalars(select(Message).where(Message.external_id == "mid-test-123456")))
        assert len(messages) == 1
        assert db.scalar(select(WebhookEvent)).status == "processed"


def test_webhook_wrong_account_and_echo_ignored(client):
    payload = webhook()
    payload["entry"][0]["id"] = "other-account"
    raw, headers = signed(payload)
    assert client.post("/api/instagram/webhook", content=raw, headers=headers).json()["accepted"] == 0
    payload = webhook()
    payload["entry"][0]["messaging"][0]["message"]["is_echo"] = True
    raw, headers = signed(payload)
    assert client.post("/api/instagram/webhook", content=raw, headers=headers).json()["accepted"] == 0


def test_llm_schema_and_service_fallback(env, monkeypatch):
    config = settings()
    monkeypatch.setattr(config, "llm_mode", "api")
    monkeypatch.setattr(config, "llm_api_key", "never-printed-test-key")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            assert kwargs["json"]["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
            assert kwargs["headers"]["Authorization"] == "Bearer never-printed-test-key"
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": Extraction(
                                    product_id=1, quantity=2, specifications={"scent": "وانیل"}
                                ).model_dump_json()
                            }
                        }
                    ]
                },
                request=httpx.Request("POST", "https://example.test"),
            )

    monkeypatch.setattr("app.llm.httpx.Client", FakeClient)
    with env["sessions"]() as db:
        products = [product_data(db, db.get(Product, 1))]
    conv = SimpleNamespace(draft={}, llm_requests=0)
    result, fallback = extract("دو عدد شمع آوا وانیل", products, Draft().model_dump(), [], conv)
    assert not fallback and result.quantity == 2 and conv.llm_requests == 1

    class InvalidClient(FakeClient):
        def post(self, *args, **kwargs):
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"price": 1, "paid": true}'}}]},
                request=httpx.Request("POST", "https://example.test"),
            )

    monkeypatch.setattr("app.llm.httpx.Client", InvalidClient)
    result, fallback = extract("دو عدد شمع آوا وانیل", products, Draft().model_dump(), [], conv)
    assert fallback and result.quantity == 2

    class BrokenClient(FakeClient):
        def post(self, *args, **kwargs):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr("app.llm.httpx.Client", BrokenClient)
    assert extract("دو عدد شمع آوا", products, Draft().model_dump(), [], conv)[1]


def test_message_and_conversation_limits(client, monkeypatch):
    token = client.post("/api/chat/start", json={}).json()["token"]
    monkeypatch.setattr(settings(), "max_message_length", 5)
    assert (
        client.post(
            f"/api/chat/{token}/messages", json={"client_id": "limit-test-123", "text": "این پیام بسیار طولانی است"}
        ).status_code
        == 422
    )
    monkeypatch.setattr(settings(), "max_conversation_messages", 1)
    assert (
        client.post(f"/api/chat/{token}/messages", json={"client_id": "limit-test-456", "text": "سلام"}).status_code
        == 429
    )


def test_instagram_closed_window_keeps_status_and_notifies_seller(client, env, monkeypatch):
    from datetime import timedelta
    from app.instagram import process_inbox, send_outbox
    from app.models import now, Notification

    payload = webhook()
    payload["entry"][0]["messaging"][0]["timestamp"] = int((now() - timedelta(days=2)).timestamp() * 1000)
    raw, headers = signed(payload)
    assert client.post("/api/instagram/webhook", content=raw, headers=headers).status_code == 200
    monkeypatch.setattr("app.instagram.SessionLocal", env["sessions"])
    assert process_inbox()
    assert send_outbox()
    with env["sessions"]() as db:
        assert db.scalar(select(Message).where(Message.delivery_status == "blocked"))
        assert db.scalar(select(Notification).where(Notification.kind == "instagram_blocked"))
