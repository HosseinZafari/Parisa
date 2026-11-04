from types import SimpleNamespace

import httpx
import pytest

from app.config import settings
from app.domain import product_data
from app.llm import check_connection, extract
from app.models import Product
from app.schemas import Draft, Extraction


def fake_service(monkeypatch, *, code=200, content=None):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            calls.append(kwargs)
            payload = (
                {"choices": [{"message": {"content": content}}]}
                if code == 200
                else {"error": {"message": "secret-test-key private-address must-never-be-returned"}}
            )
            return httpx.Response(code, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(settings(), "llm_mode", "api")
    monkeypatch.setattr(settings(), "llm_api_key", "secret-test-key")
    monkeypatch.setattr(settings(), "llm_model", "glm-5.3-flash")
    monkeypatch.setattr("app.llm.httpx.Client", Client)
    return calls


def test_connection_uses_fake_catalog_and_validated_extraction(env, monkeypatch):
    result = Extraction(product_id=1, quantity=2, specifications={"scent": "وانیل"})
    calls = fake_service(monkeypatch, content=result.model_dump_json())
    status = check_connection()
    assert status["status"] == "ready"
    assert calls[0]["json"]["model"] == "glm-5.3-flash"
    assert calls[0]["json"]["max_tokens"] == settings().llm_max_output_tokens
    assert "شمع آزمایشی" in calls[0]["json"]["messages"][0]["content"]
    assert "secret-test-key" not in str(status)


@pytest.mark.parametrize(
    "code,status",
    [
        (401, "unauthorized"),
        (402, "billing_required"),
        (403, "unauthorized"),
        (429, "rate_limited"),
        (500, "unavailable"),
        (400, "request_rejected"),
    ],
)
def test_safe_errors_and_cooldown(env, monkeypatch, code, status):
    calls = fake_service(monkeypatch, code=code)
    outcome = check_connection()
    assert outcome["status"] == status and outcome["http_status"] == code
    assert not any(value in str(outcome) for value in ["secret-test-key", "private-address", "must-never"])
    if code in {401, 402, 403, 429}:
        with env["sessions"]() as db:
            products = [product_data(db, db.get(Product, 1))]
        conversation = SimpleNamespace(draft={}, llm_requests=0)
        result, fallback = extract("دو عدد شمع آوا", products, Draft().model_dump(), [], conversation)
        assert fallback and result.quantity == 2
        assert len(calls) == 1 and conversation.llm_requests == 0
        # آزمون دستی می‌تواند بعد از اصلاح حساب، بلافاصله اتصال را دوباره بررسی کند.
        check_connection()
        assert len(calls) == 2


def test_diagnostics_mock_and_missing_key_do_not_request(env, monkeypatch):
    assert check_connection()["status"] == "mock"
    monkeypatch.setattr(settings(), "llm_mode", "api")
    monkeypatch.setattr(settings(), "llm_api_key", "")
    assert check_connection()["status"] == "missing_key"


def test_schema_and_semantic_errors_are_not_reported_as_connected(env, monkeypatch):
    fake_service(monkeypatch, content='{"paid":true}')
    assert check_connection()["status"] == "invalid_response"
    fake_service(monkeypatch, content=Extraction(product_id=1, quantity=1).model_dump_json())
    assert check_connection()["status"] == "invalid_response"


def test_check_endpoint_requires_seller_and_has_request_limit(seller, monkeypatch):
    fake_service(monkeypatch, code=402)
    assert seller.post("/api/llm/check").json()["status"] == "billing_required"
    info = seller.get("/api/settings").json()
    assert info["llm_connection"]["status"] == "billing_required"
    assert "secret-test-key" not in str(info)
    for _ in range(2):
        assert seller.post("/api/llm/check").status_code == 200
    assert seller.post("/api/llm/check").status_code == 429
    seller.post("/api/auth/logout")
    assert seller.post("/api/llm/check").status_code == 401


def test_go_route_normalizes_prefix_and_sends_stable_private_session(env, monkeypatch):
    calls = fake_service(
        monkeypatch, content=Extraction(product_id=1, quantity=2, specifications={"scent": "وانیل"}).model_dump_json()
    )
    monkeypatch.setattr(settings(), "llm_model", "opencode-go/glm-5.3-flash")
    monkeypatch.setattr(settings(), "llm_base_url", "https://opencode.ai/inference/go/openai/v1")
    for _ in range(2):
        assert check_connection()["status"] == "ready"
    assert calls[0]["json"]["model"] == "glm-5.3-flash"
    assert calls[0]["headers"]["User-Agent"] == "parisa-orders-mvp/0.1"
    assert calls[0]["headers"]["x-opencode-session"] == calls[1]["headers"]["x-opencode-session"]
    assert "connection-check" not in calls[0]["headers"]["x-opencode-session"]


def test_go_model_cannot_accidentally_use_separate_billing_endpoint():
    from app.config import Settings

    with pytest.raises(ValueError, match="نشانی اشتراکی"):
        Settings(
            _env_file=None,
            llm_model="opencode-go/glm-5.3-flash",
            llm_base_url="https://opencode.ai/inference/openai/v1",
        )


@pytest.mark.parametrize("uncertain_key", ["delivery.name", "name"])
def test_customer_clarification_clears_delivery_uncertainty(client, monkeypatch, uncertain_key):
    from test_order_flow import message
    from app.schemas import Delivery

    token = client.post("/api/chat/start", json={}).json()["token"]
    message(client, token, "دو عدد شمع آوا وانیل کوچک معمولی")
    original = message(
        client, token, "نام: سارا؛ تلفن: 09120000000؛ شهر: تهران؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی: 1111111111"
    )
    assert original["ready_to_confirm"]
    ambiguous = Extraction(intent="correct", delivery=Delivery(name="سارا یا نگار"), uncertain_fields=[uncertain_key])
    monkeypatch.setattr("app.chat.extract", lambda *args, **kwargs: (ambiguous, False))
    pending = message(client, token, "شاید اسم گیرنده سارا یا نگار باشد")
    assert not pending["ready_to_confirm"] and pending["draft"]["delivery"]["name"] == "سارا"
    assert "نام گیرنده" in pending["messages"][-1]["text"]
    assert "delivery.name" not in pending["messages"][-1]["text"]
    clarified = Extraction(intent="correct", delivery=Delivery(name="نگار"))
    monkeypatch.setattr("app.chat.extract", lambda *args, **kwargs: (clarified, False))
    resolved = message(client, token, "نام گیرنده نگار است")
    assert resolved["ready_to_confirm"] and resolved["draft"]["delivery"]["name"] == "نگار"


def test_prefixed_uncertain_spec_does_not_replace_confirmed_value(client, monkeypatch):
    from test_order_flow import message

    token = client.post("/api/chat/start", json={}).json()["token"]
    message(client, token, "دو عدد شمع آوا وانیل کوچک معمولی")
    ambiguous = Extraction(intent="correct", specifications={"size": "بزرگ"}, uncertain_fields=["specifications.size"])
    monkeypatch.setattr("app.chat.extract", lambda *args, **kwargs: (ambiguous, False))
    pending = message(client, token, "شاید بزرگ بخواهم")
    assert pending["draft"]["specifications"]["size"] == "کوچک"
    clarified = Extraction(intent="correct", specifications={"size": "بزرگ"})
    monkeypatch.setattr("app.chat.extract", lambda *args, **kwargs: (clarified, False))
    resolved = message(client, token, "بله بزرگ باشد")
    assert resolved["draft"]["specifications"]["size"] == "بزرگ"
    assert "مبهم" not in resolved["messages"][-1]["text"]
