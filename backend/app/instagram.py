import asyncio
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from .auth import limiter
from .chat import process_message, start_chat
from .config import settings
from .db import SessionLocal
from .domain import notify, rows
from .models import Conversation, Customer, Message, Order, WebhookEvent, now


def verify_signature(body, signature):
    secret = settings().instagram_app_secret
    if not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def ingest_webhook(db, payload):
    config = settings()
    if payload.get("object") != "instagram":
        raise HTTPException(422, "نوع رویداد اینستاگرام معتبر نیست.")
    count = 0
    for entry in payload.get("entry", []):
        if str(entry.get("id")) != config.instagram_account_id:
            continue
        for item in entry.get("messaging", []):
            message = item.get("message", {})
            sender = str(item.get("sender", {}).get("id", ""))
            recipient = str(item.get("recipient", {}).get("id", ""))
            mid = str(message.get("mid", ""))
            if message.get("is_echo") or not mid or not sender or recipient != config.instagram_account_id:
                continue
            if len(mid) > 200 or len(sender) > 200:
                continue
            if db.scalar(select(WebhookEvent).where(WebhookEvent.external_id == mid)):
                continue
            text = message.get("text", "")
            if not text and message.get("attachments"):
                text = "مشتری پیوست فرستاده است؛ فروشنده لطفاً پیوست را در اینستاگرام بررسی کند."
            if not isinstance(text, str) or not text or len(text) > config.max_message_length:
                continue
            try:
                stamp = min(
                    datetime.fromtimestamp(int(item.get("timestamp", 0)) / 1000, timezone.utc).replace(tzinfo=None),
                    now(),
                )
            except (ValueError, TypeError, OverflowError, OSError):
                stamp = now() - timedelta(days=2)
            db.add(WebhookEvent(external_id=mid, sender_id=sender, text=text, message_at=stamp))
            db.flush()
            count += 1
    return {"accepted": count}


def begin(db):
    if db.bind.dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")


def process_inbox():
    with SessionLocal() as db:
        begin(db)
        item = db.scalar(select(WebhookEvent).where(WebhookEvent.status == "pending").order_by(WebhookEvent.id))
        if not item:
            return False
        customer = db.scalar(select(Customer).where(Customer.instagram_id == item.sender_id))
        if not customer:
            customer = Customer(
                username="ig_" + item.sender_id,
                instagram_id=item.sender_id,
                name="مشتری اینستاگرام",
                last_interaction_at=item.message_at,
            )
            db.add(customer)
            db.flush()
        conv = db.scalar(
            select(Conversation)
            .where(Conversation.customer_id == customer.id, Conversation.channel == "instagram")
            .order_by(Conversation.id.desc())
        )
        if not conv:
            conv = start_chat(db, customer=customer, channel="instagram")
        last_interaction = max(customer.last_interaction_at, item.message_at)
        try:
            state = process_message(db, conv, item.text, "ig:" + item.external_id, external_id=item.external_id)
            outgoing = db.scalar(
                select(Message)
                .where(Message.conversation_id == conv.id, Message.role == "assistant")
                .order_by(Message.id.desc())
            )
            if outgoing:
                outgoing.delivery_status = "pending"
            item.status = "processed"
            if state["handover"]:
                notify(
                    db,
                    db.get(Order, conv.order_id) if conv.order_id else None,
                    "handover",
                    "گفتگوی اینستاگرام نیازمند پاسخ فروشنده است.",
                    f"ig-handover:{item.id}",
                )
        except HTTPException:
            item.status = "manual"
            conv.handover = True
            notify(
                db,
                db.get(Order, conv.order_id) if conv.order_id else None,
                "instagram_manual",
                "پیام اینستاگرام نیازمند پیگیری دستی است.",
                f"ig-manual:{item.id}",
            )
        customer.last_interaction_at = last_interaction
        db.commit()
    return True


def send_outbox():
    config = settings()
    with SessionLocal() as db:
        begin(db)
        message = db.scalar(select(Message).where(Message.delivery_status == "pending").order_by(Message.id))
        if not message:
            return False
        conv = db.get(Conversation, message.conversation_id)
        customer = db.get(Customer, conv.customer_id)
        if conv.channel != "instagram":
            message.delivery_status = "saved"
            db.commit()
            return True
        ident, text, recipient, order_id = message.id, message.text, customer.instagram_id, message.order_id
        if customer.last_interaction_at < now() - timedelta(hours=24):
            message.delivery_status = "blocked"
            notify(
                db,
                db.get(Order, order_id) if order_id else None,
                "instagram_blocked",
                "پنجرهٔ پاسخ اینستاگرام بسته است؛ وضعیت در پیگیری خصوصی در دسترس است.",
                f"ig-send:{ident}:blocked",
            )
            db.commit()
            return True
        try:
            limiter.check("instagram:outgoing", config.instagram_sends_per_minute)
        except HTTPException:
            return False
        message.delivery_status = "sending"
        db.commit()
    status = "sent"
    if config.instagram_mode == "live":
        try:
            with httpx.Client(timeout=15) as client:
                response = client.post(
                    f"https://graph.instagram.com/{config.instagram_api_version}/{config.instagram_account_id}/messages",
                    headers={"Authorization": f"Bearer {config.instagram_access_token}"},
                    json={"recipient": {"id": recipient}, "message": {"text": text[:1900]}},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            # پاسخ نامعلوم خودکار تکرار نمی‌شود؛ جلوگیری از پیام تکراری بر عهدهٔ فروشنده.
            status = "unknown"
    with SessionLocal() as db:
        begin(db)
        message = db.get(Message, ident)
        message.delivery_status = status
        if status != "sent":
            notify(
                db,
                db.get(Order, order_id) if order_id else None,
                "instagram_failed",
                "تحویل پیام اینستاگرام تأیید نشد؛ پیش از ارسال مجدد صندوق پیام را بررسی کنید.",
                f"ig-send:{ident}:unknown",
            )
        db.commit()
    return True


async def worker():
    # پس از توقف در میانهٔ ارسال، پیام خودکار دوباره فرستاده نمی‌شود.
    with SessionLocal() as db:
        for message in rows(db, Message, delivery_status="sending"):
            message.delivery_status = "unknown"
            notify(
                db,
                db.get(Order, message.order_id) if message.order_id else None,
                "instagram_failed",
                "وضعیت تحویل پیام پس از راه‌اندازی مجدد نیازمند بررسی است.",
                f"ig-send:{message.id}:unknown",
            )
        db.commit()
    while True:
        try:
            await asyncio.to_thread(process_inbox)
            await asyncio.to_thread(send_outbox)
        except Exception:
            # بدنه، نشانی، توکن و خطای سرویس خارجی وارد لاگ نمی‌شوند.
            import logging

            logging.getLogger("parisa").warning("instagram_worker_retry")
        await asyncio.sleep(2)
