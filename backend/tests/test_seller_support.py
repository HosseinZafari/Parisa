from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import make_engine
from app.models import Conversation, Message, Notification, Order, Seller, now
from app.schemas import Extraction, SupportSignal
from conftest import key
from test_order_flow import message


def start(client):
    return client.post("/api/chat/start", json={}).json()["token"]


def test_seller_public_help_uses_saved_profile_and_no_assumptions(seller):
    token = start(seller)
    unknown = message(seller, token, "ساعت کاری فروشنده چه ساعتیه؟")
    assert "هنوز توسط فروشنده ثبت نشده" in unknown["messages"][-1]["text"]
    assert not unknown["handover"]
    profile = {
        "store_name": "فروشگاه آوا",
        "working_hours": "روزهای شنبه تا چهارشنبه از ۱۰ تا ۱۶",
        "return_policy": "برای بررسی مرجوعی ابتدا با فروشنده هماهنگ کنید.",
        "contact": "آیدی فروشگاه: @example_shop",
    }
    saved = seller.put("/api/seller/profile", headers=key(), json=profile)
    assert saved.status_code == 200
    known = message(seller, token, "ساعت کاری فروشنده چه ساعتیه؟")
    assert profile["working_hours"] in known["messages"][-1]["text"]
    policy = message(seller, token, "چطور میتونم کالا رو مرجوع کنم؟")
    assert profile["return_policy"] in policy["messages"][-1]["text"]
    assert not policy["order"] and not policy["handover"]


def test_human_request_creates_one_linked_task_and_notification(seller, env):
    token = start(seller)
    state = message(seller, token, "من با فروشنده کار دارم میخوام با خودش صحبت کنم")
    assert state["handover"]
    message(seller, token, "فروشنده")
    conv = seller.get("/api/conversations").json()[0]
    assert conv["attention_status"] == "open" and conv["attention_priority"] == "normal"
    notifications = seller.get("/api/notifications").json()
    linked = [n for n in notifications if n["conversation_id"] == conv["id"]]
    assert len(linked) == 1 and linked[0]["order_id"] is None
    detail = seller.get("/api/conversations/" + str(conv["id"])).json()
    assert [m["role"] for m in detail["messages"]] == ["assistant", "customer", "assistant", "customer", "assistant"]
    assert "واگذار" in detail["messages"][2]["text"]


def test_urgent_report_is_immediate_even_while_handed_over_and_deduplicated(seller, env, monkeypatch):
    token = start(seller)
    message(seller, token, "فروشنده")

    def never_call_model(*args, **kwargs):
        raise AssertionError("گزارش فوری نباید منتظر مدل بماند")

    monkeypatch.setattr("app.chat.extract", never_call_model)
    urgent = message(seller, token, "شمع آتش گرفته و آسیب جدی دیده ام")
    assert "اولویت فوری" in urgent["messages"][-1]["text"]
    message(seller, token, "شمع آتش گرفته و آسیب جدی دیده ام")
    conv = seller.get("/api/conversations").json()[0]
    assert conv["attention_priority"] == "urgent"
    notifications = [n for n in seller.get("/api/notifications").json() if n["conversation_id"] == conv["id"]]
    assert len(notifications) == 2 and sum(n["priority"] == "urgent" for n in notifications) == 1
    dashboard = seller.get("/api/dashboard").json()
    assert dashboard["urgent_conversations"] == 1 and dashboard["attention_queue"][0]["conversation_id"] == conv["id"]


def test_llm_can_escalate_semantic_problem_without_controlling_order(seller, env, monkeypatch):
    token = start(seller)
    message(seller, token, "دو عدد شمع آوا وانیل کوچک معمولی")
    message(seller, token, "نام: سارا؛ تلفن: 09120000000؛ شهر: تهران؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی: 1111111111")
    before = message(seller, token, "تأیید سفارش")
    signal = Extraction(
        intent="handover",
        support=SupportSignal(
            priority="urgent", category="payment_problem", reason="مشتری مشکل جدی در تراکنش گزارش کرده است."
        ),
    )
    monkeypatch.setattr("app.chat.extract", lambda *args, **kwargs: (signal, False))
    state = message(seller, token, "وجه رفته ولی وضعیت حسابم با سفارشم همخوانی ندارد، کمک لازم دارم")
    assert state["handover"] and state["order"]["status"] == before["order"]["status"] == "awaiting_payment"
    with env["sessions"]() as db:
        order = db.get(Order, before["order"]["id"])
        assert order.paid_amount == 0
        assert db.scalar(select(Notification).where(Notification.priority == "urgent"))


def test_resolve_reply_resume_and_reopen_are_audited_and_idempotent(seller):
    token = start(seller)
    message(seller, token, "من با فروشنده کار دارم")
    conv = seller.get("/api/conversations").json()[0]
    ident = conv["id"]
    headers = key()
    payload = {"action": "resolve", "resume_bot": True}
    resolved = seller.post(f"/api/conversations/{ident}/attention", headers=headers, json=payload)
    assert resolved.status_code == 200
    assert seller.post(f"/api/conversations/{ident}/attention", headers=headers, json=payload).json() == resolved.json()
    assert resolved.json()["attention_status"] == "resolved" and not resolved.json()["handover"]
    assert resolved.json()["attention_resolved_at"] and resolved.json()["attention_resolved_by"] == "seller"
    assert not seller.get("/api/dashboard").json()["attention_queue"]
    message(seller, token, "من با فروشنده کار دارم")
    assert seller.get("/api/dashboard").json()["pending_conversations"] == 1
    response = seller.post(
        f"/api/conversations/{ident}/reply", headers=key(), json={"text": "در حال بررسی هستم.", "resume_bot": True}
    )
    assert response.status_code == 200
    detail = seller.get(f"/api/conversations/{ident}").json()
    assert detail["messages"][-1]["role"] == "seller" and detail["attention_status"] == "resolved"


def test_reading_notification_does_not_close_support_ticket(seller):
    token = start(seller)
    message(seller, token, "فروشنده فوری میخوام")
    seller.post("/api/notifications/read-all")
    assert seller.get("/api/dashboard").json()["urgent_conversations"] == 1


def test_paused_bot_still_classifies_new_semantic_urgent_issue(seller, monkeypatch):
    token = start(seller)
    message(seller, token, "فروشنده")
    signal = Extraction(
        support=SupportSignal(priority="urgent", category="other", reason="گزارش تازهٔ مشتری نیازمند رسیدگی فوری است.")
    )
    monkeypatch.setattr("app.chat.extract", lambda *args, **kwargs: (signal, False))
    state = message(seller, token, "یک اتفاق تازه افتاده که باید همین الان به ایشون منتقل بشه")
    assert "اولویت فوری" in state["messages"][-1]["text"]
    assert seller.get("/api/dashboard").json()["urgent_conversations"] == 1


@pytest.mark.parametrize(
    "text", ["اگه شمع آتش گرفته باشه چه کار کنم؟", "چطور با فروشنده تماس بگیرم؟", "ساعت کاری فروشنده چه ساعتیه؟"]
)
def test_guidance_and_hypothetical_questions_do_not_create_urgent_tasks(client, env, text):
    token = start(client)
    state = message(client, token, text)
    assert not state["handover"]
    with env["sessions"]() as db:
        assert not db.scalar(select(Notification).where(Notification.priority == "urgent"))


def test_support_and_profile_routes_require_seller(client):
    assert client.put("/api/seller/profile", headers=key(), json={"store_name": "test"}).status_code == 401
    assert client.post("/api/conversations/1/attention", headers=key(), json={"action": "resolve"}).status_code == 401


def test_migration_preserves_existing_conversation_and_opens_old_handover(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "upgrade.db").as_posix()
    monkeypatch.setattr(settings(), "database_url", url)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "8c6d8d6608cc")
    engine = make_engine(url)
    tables = MetaData()
    seller = Table("sellers", tables, autoload_with=engine)
    customer = Table("customers", tables, autoload_with=engine)
    conversation = Table("conversations", tables, autoload_with=engine)
    message_table = Table("messages", tables, autoload_with=engine)
    stamp = now()
    with engine.begin() as db:
        db.execute(
            seller.insert().values(
                id=1, username="seller", name="پریسا", password_hash="unused", created_at=stamp, updated_at=stamp
            )
        )
        db.execute(
            customer.insert().values(
                id=1,
                name="مشتری",
                username="test",
                phone="",
                address="",
                postal_code="",
                city="",
                notes="",
                last_interaction_at=stamp,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.execute(
            conversation.insert().values(
                id=1,
                customer_id=1,
                channel="local",
                token="preserved-conversation",
                draft={},
                handover=True,
                llm_requests=0,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        for index, role in enumerate(["customer", "assistant"], 1):
            db.execute(
                message_table.insert().values(
                    id=index,
                    conversation_id=1,
                    role=role,
                    text="پیام حفظ‌شده",
                    delivery_status="saved",
                    created_at=stamp,
                )
            )
    command.upgrade(cfg, "head")
    with Session(engine) as db:
        conv = db.get(Conversation, 1)
        assert conv.attention_status == "open" and conv.handover and conv.token == "preserved-conversation"
        assert len(list(db.scalars(select(Message)))) == 2
        assert db.get(Seller, 1).public_profile == {}
    engine.dispose()
