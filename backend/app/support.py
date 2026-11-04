"""ارجاع پایدار گفتگو به فروشنده؛ بدون تغییر پرداخت، مبلغ یا وضعیت سفارش."""

from sqlalchemy import select

from .chat_knowledge import normalize_text
from .domain import event, iso, notify
from .models import Conversation, Customer, Notification, Order, Seller, now
from .schemas import SellerProfile, SupportSignal


def seller_profile(db):
    seller = db.scalar(select(Seller))
    profile = (
        SellerProfile.model_validate(seller.public_profile or {}).model_dump()
        if seller
        else SellerProfile().model_dump()
    )
    if not profile["store_name"]:
        profile["store_name"] = seller.name if seller else "فروشگاه"
    return profile


def detect_support(text):
    plain = normalize_text(text)
    hypothetical = any(w in plain for w in ["اگر ", "اگه ", "ممکنه ", "نکنه "])
    urgent_reports = {
        "safety": ["آتش گرفته", "آتش گرفت", "آتش سوزی", "سوختگی شدید", "آسیب جدی", "خطر جدی", "تهدیدم کرده"],
        "payment_problem": ["دوبار کم شده", "دو بار کم شده", "دو بار از حسابم کم", "دوبار از حسابم کم"],
        "delivery_problem": ["بسته ام گم شده", "بستم گم شده", "سفارشم گم شده"],
    }
    if not hypothetical:
        for category, phrases in urgent_reports.items():
            if any(value in plain for value in phrases):
                return SupportSignal(
                    priority="urgent",
                    category=category,
                    reason={
                        "safety": "مشتری یک مشکل جدی دربارهٔ ایمنی یا آسیب گزارش کرده است.",
                        "payment_problem": "مشتری برداشت تکراری از حساب را گزارش کرده است؛ پرداخت نیازمند بررسی فروشنده است.",
                        "delivery_problem": "مشتری مفقودی بسته یا سفارش را گزارش کرده است.",
                    }[category],
                )
    human = plain in {"فروشنده", "اپراتور", "انسان"} or (
        any(w in plain for w in ["فروشنده", "اپراتور", "آدم واقعی", "انسان واقعی", "مسئول فروشگاه"])
        and any(w in plain for w in ["صحبت", "کار دارم", "می خوام", "میخوام", "می خواهم", "وصل", "حرف", "تماس"])
    )
    if any(w in plain for w in ["چطور", "چجوری", "شماره", "راه ارتباط"]) and not any(
        w in plain for w in ["کار دارم", "می خوام", "میخوام", "می خواهم"]
    ):
        human = False
    if human and not any(w in plain for w in ["نمی خوام", "نمیخوام", "نمی خواهم", "کار ندارم"]):
        return SupportSignal(
            priority="urgent" if "فوری" in plain or "اضطراری" in plain else "normal",
            category="human_request",
            reason="مشتری درخواست پاسخ مستقیم فروشنده دارد.",
        )
    if (
        not hypothetical
        and any(w in plain for w in ["فوری", "اضطراری"])
        and any(w in plain for w in ["مشکل دارم", "مشکل جدی", "کمک لازم دارم"])
    ):
        return SupportSignal(
            priority="urgent", category="other", reason="مشتری درخواست رسیدگی فوری به یک مشکل را دارد."
        )
    return None


def attention_data(conv):
    return {
        "attention_status": conv.attention_status,
        "attention_priority": conv.attention_priority,
        "handover_reason": conv.handover_reason,
        "attention_resolved_at": iso(conv.attention_resolved_at),
        "attention_resolved_by": conv.attention_resolved_by,
    }


def request_attention(db, conv, signal):
    opened = conv.attention_status != "open"
    escalated = signal.priority == "urgent" and conv.attention_priority != "urgent"
    if opened:
        conv.attention_version += 1
        conv.attention_priority = signal.priority
        conv.attention_resolved_at = None
        conv.attention_resolved_by = None
    elif escalated:
        conv.attention_priority = "urgent"
    if opened or escalated or conv.attention_priority != "urgent":
        conv.handover_reason = signal.reason
    conv.attention_status, conv.handover = "open", True
    conv.updated_at = now()
    if opened or escalated:
        customer = db.get(Customer, conv.customer_id)
        order = db.get(Order, conv.order_id) if conv.order_id else None
        urgent = conv.attention_priority == "urgent"
        notify(
            db,
            order,
            "urgent_support" if urgent else "handover",
            f"{'فوری — ' if urgent else ''}{customer.name}: {conv.handover_reason}",
            f"attention:{conv.id}:{conv.attention_version}:{conv.attention_priority}",
            conversation=conv,
            priority=conv.attention_priority,
        )
        if order:
            event(
                db,
                order,
                "support_requested",
                conv.handover_reason,
                "مشتری",
                {"conversation_id": conv.id, "priority": conv.attention_priority},
            )
    return (
        "پیامت را با اولویت فوری برای فروشنده ثبت کردم و پاسخ خودکار این گفتگو متوقف شد. "
        if conv.attention_priority == "urgent"
        else "گفتگو به فروشنده واگذار شد و درخواستت در صف رسیدگی قرار گرفت. "
    ) + "پاسخ مستقیم فروشنده را همین‌جا دریافت می‌کنی."


def resolve_attention(db, conv, seller, *, resume_bot=False):
    conv.attention_status = "resolved"
    conv.attention_resolved_at = now()
    conv.attention_resolved_by = seller.username
    conv.handover = not resume_bot
    conv.updated_at = now()
    for notification in db.scalars(
        select(Notification).where(Notification.conversation_id == conv.id, Notification.read.is_(False))
    ):
        notification.read = True


def attention_queue(db):
    pending = list(
        db.scalars(
            select(Conversation)
            .where(Conversation.attention_status == "open")
            .order_by(Conversation.attention_priority.desc(), Conversation.updated_at.asc(), Conversation.id.asc())
        )
    )
    return {
        "pending_conversations": len(pending),
        "urgent_conversations": sum(c.attention_priority == "urgent" for c in pending),
        "attention_queue": [
            {
                "conversation_id": c.id,
                "customer_name": db.get(Customer, c.customer_id).name,
                "priority": c.attention_priority,
                "reason": c.handover_reason,
                "updated_at": iso(c.updated_at),
            }
            for c in pending[:20]
        ],
    }
