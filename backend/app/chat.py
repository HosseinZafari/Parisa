import secrets

from fastapi import HTTPException
from sqlalchemy import select

from .config import settings
from .domain import (
    DELIVERY_LABELS,
    create_change,
    create_order,
    get_or_404,
    iso,
    notify,
    payment_data,
    payment_link,
    product_data,
    quote,
    receipt_read,
    receipt_save,
    rows,
    snapshot,
    tracking_data,
)
from .llm import extract, match_products
from .models import Conversation, Customer, Message, Order, Product, now
from .schemas import Draft


def draft_data(conversation):
    return Draft.model_validate({k: v for k, v in conversation.draft.items() if not k.startswith("_")}).model_dump()


def find_conversation(db, token):
    conversation = db.scalar(select(Conversation).where(Conversation.token == token))
    if not conversation:
        raise HTTPException(404, "گفتگو پیدا نشد؛ یک گفتگوی تازه آغاز کنید.")
    return conversation


def start_chat(db, name="", customer=None, channel="local"):
    if customer is None:
        customer = Customer(name=name or "مشتری آزمایشی", username="test_" + secrets.token_hex(6))
        db.add(customer)
        db.flush()
    conv = Conversation(customer_id=customer.id, channel=channel, token=secrets.token_urlsafe(32), draft={})
    db.add(conv)
    db.flush()
    db.add(
        Message(
            conversation_id=conv.id,
            role="assistant",
            text="سلام! خوش آمدید 🌿 چه محصولی و چند عدد می‌خواهید؟ اگر مشخصات و نشانی را می‌دانید، همه را در یک پیام بنویسید.",
        )
    )
    db.flush()
    return conv


def chat_state(db, conv):
    draft = draft_data(conv)
    summary = None
    if draft["product_id"] and draft["quantity"]:
        try:
            summary = quote(db, draft)
        except HTTPException:
            pass
    return {
        "token": conv.token,
        "handover": conv.handover,
        "channel": conv.channel,
        "messages": [
            {"id": m.id, "role": m.role, "text": m.text, "created_at": iso(m.created_at)}
            for m in db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id))
        ],
        "draft": draft,
        "summary": summary if not conv.order_id else None,
        "ready_to_confirm": bool(conv.draft.get("_ready")) and not conv.order_id,
        "order": tracking_data(db, db.get(Order, conv.order_id)) if conv.order_id else None,
        "tracking_url": f"{settings().public_base_url}/track/{db.get(Order, conv.order_id).tracking_token}"
        if conv.order_id and db.get(Order, conv.order_id).tracking_token
        else None,
        "payment": _active_payment(db, conv),
    }


def _active_payment(db, conv):
    if conv.order_id:
        order = db.get(Order, conv.order_id)
        if order.status == "awaiting_payment":
            try:
                return payment_data(payment_link(db, order))
            except HTTPException:
                pass
    return None


def ask_missing(db, draft, products):
    if not draft["product_id"]:
        return "product_id", "کدام محصول را می‌خواهید؟ " + "، ".join(p["name"] for p in products)
    product = next((p for p in products if p["id"] == draft["product_id"]), None)
    if not product:
        return "product_id", "این محصول در حال حاضر قابل سفارش نیست. محصول دیگری انتخاب کنید."
    if not draft["quantity"]:
        return "quantity", "چند عدد می‌خواهید؟"
    for r in product["requirements"]:
        value = draft["specifications"].get(r["key"])
        if (r["required"] and not value) or (value and r["allowed_values"] and value not in r["allowed_values"]):
            options = " انتخاب‌ها: " + "، ".join(r["allowed_values"]) if r["allowed_values"] else ""
            return "specifications." + r["key"], f"{r['label']} را مشخص کنید.{options}"
    from .domain import delivery_missing

    missing = delivery_missing(draft["delivery"])
    if missing:
        for key, label in DELIVERY_LABELS.items():
            if (
                not draft["delivery"].get(key)
                or (key == "phone" and "شمارهٔ همراه معتبر" in missing)
                or (key == "postal_code" and "کد پستی ۱۰ رقمی" in missing)
                or (key == "address" and "نشانی دقیق شامل خیابان و پلاک" in missing)
            ):
                return f"delivery.{key}", f"لطفاً {label} را بفرستید." + (
                    " کد پستی باید ۱۰ رقم باشد." if key == "postal_code" else ""
                )
    q = quote(db, draft)
    if q["missing"]:
        return "deadline", "لطفاً این موارد را روشن کنید: " + "، ".join(q["missing"])
    return (
        None,
        "اطلاعات کامل شد. خلاصهٔ سفارش و نشانی را بررسی کنید؛ اگر درست است «تأیید سفارش» را بفرستید. برای اصلاح، مقدار تازه را بنویسید.",
    )


def process_message(db, conv, text, client_id, external_id=None):
    config = settings()
    if len(text) > config.max_message_length:
        raise HTTPException(422, f"پیام باید حداکثر {config.max_message_length} نویسه باشد.")
    prior, fingerprint = receipt_read(db, f"chat:{conv.id}", client_id, {"text": text})
    if prior:
        return prior.result
    history = list(db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)))
    if len(history) + 2 > config.max_conversation_messages:
        raise HTTPException(
            429, "ظرفیت این گفتگو پر شده است؛ برای ادامه با فروشنده تماس بگیرید یا گفتگوی تازه‌ای شروع کنید."
        )
    incoming = Message(
        conversation_id=conv.id,
        role="customer",
        text=text,
        client_id=client_id,
        external_id=external_id,
        order_id=conv.order_id,
    )
    db.add(incoming)
    customer = db.get(Customer, conv.customer_id)
    customer.last_interaction_at = now()
    products = [product_data(db, p) for p in rows(db, Product, enabled=True)]
    draft = snapshot(db, db.get(Order, conv.order_id)) if conv.order_id else draft_data(conv)
    result = None
    fallback = False
    if conv.handover:
        reply = "پیام شما برای فروشنده ذخیره شد؛ پاسخ را همین‌جا دریافت می‌کنید."
    else:
        try:
            result, fallback = extract(text, products, draft, history, conv)
        except (ValueError, TypeError):
            reply = (
                "این مقدار روشن نیست. لطفاً تعداد یا تاریخ را دقیق‌تر بنویسید؛ برای کمک می‌توانید «فروشنده» را بفرستید."
            )
        if result:
            reply = apply_extraction(db, conv, customer, draft, result, products, text)
    if fallback:
        reply += "\nسرویس زبانی در دسترس نیست؛ ادامه با پردازش محلی انجام می‌شود."
    db.add(Message(conversation_id=conv.id, role="assistant", text=reply, order_id=conv.order_id))
    if conv.order_id:
        incoming.order_id = conv.order_id
    conv.updated_at = now()
    db.flush()
    state = chat_state(db, conv)
    receipt_save(db, f"chat:{conv.id}", client_id, fingerprint, state)
    return state


def apply_extraction(db, conv, customer, draft, result, products, text):
    if result.intent == "handover":
        conv.handover = True
        order = db.get(Order, conv.order_id) if conv.order_id else None
        notify(
            db,
            order,
            "handover",
            f"{customer.name} درخواست گفتگو با فروشنده دارد.",
            f"handover:{conv.id}:{len(rows(db, Message, conversation_id=conv.id))}",
        )
        return "گفتگو به فروشنده واگذار شد. پیام بعدی شما نیز برای او ذخیره می‌شود."
    if result.intent == "new":
        conv.order_id, conv.draft = None, {}
        return "سفارش تازه را شروع کنیم؛ نام محصول و تعداد را بفرستید."
    if result.intent == "repeat" and not conv.order_id:
        previous = db.scalar(
            select(Order).where(Order.customer_id == customer.id, Order.status != "canceled").order_by(Order.id.desc())
        )
        if not previous:
            return "هنوز سفارش قبلی ندارید؛ نام محصول و تعداد را بفرستید."
        data = snapshot(db, previous)
        data["deadline"] = None
        conv.draft = data
        return "اطلاعات سفارش قبلی بازیابی شد. مشخصات و نشانی را تأیید یا اصلاح کنید؛ هیچ پرداختی بدون تأیید تازه ایجاد نمی‌شود."
    extracted = result.model_dump()
    patch = {}
    if result.product_id:
        patch["product_id"] = result.product_id
    if result.quantity:
        patch["quantity"] = result.quantity
    if result.specifications:
        patch["specifications"] = result.specifications
    delivered = {k: v for k, v in extracted["delivery"].items() if v}
    if delivered:
        patch["delivery"] = delivered
    if result.deadline:
        patch["deadline"] = result.deadline
    if conv.order_id:
        order = get_or_404(db, Order, conv.order_id)
        if patch:
            try:
                change = create_change(db, order, patch)
                return (
                    "درخواست تغییر برای پیگیری دستی به فروشنده رسید."
                    if change.status == "manual"
                    else "درخواست تغییر ثبت شد و منتظر تأیید فروشنده است. تا آن زمان سفارش قبلی معتبر می‌ماند."
                )
            except HTTPException as exc:
                return str(exc.detail)
        return "سفارش شما ثبت شده است. وضعیت و پرداخت را از پیوندهای زیر ببینید. برای تغییر، مقدار تازه را بنویسید؛ برای خرید مجدد «سفارش جدید» را بفرستید."
    # چند محصول هم‌نام نیازمند انتخاب صریح است.
    candidates = match_products(text, products)
    if len(candidates) > 1 and not result.product_id:
        held = Draft.model_validate(draft).model_dump()
        if result.quantity:
            held["quantity"] = result.quantity
        held["delivery"] = {**held["delivery"], **delivered}
        if result.deadline:
            held["deadline"] = result.deadline
        conv.draft = {
            **held,
            "_unassigned_specs": {**conv.draft.get("_unassigned_specs", {}), **result.specifications},
            "_candidates": [p["id"] for p in candidates],
            "_ready": False,
        }
        return "چند محصول پیدا شد؛ نام دقیق یکی را بفرستید: " + "، ".join(p["name"] for p in candidates)
    old = Draft.model_validate(draft).model_dump()
    new = {**old}
    if patch.get("product_id") and patch["product_id"] != old["product_id"]:
        new["product_id"], new["specifications"], new["deadline"] = patch["product_id"], {}, None
    if "quantity" in patch:
        new["quantity"] = patch["quantity"]
    product = next((p for p in products if p["id"] == new["product_id"]), None)
    allowed_keys = {r["key"] for r in product["requirements"]} if product else set()
    proposed_specs = {**conv.draft.get("_unassigned_specs", {}), **patch.get("specifications", {})}
    new["specifications"] = {
        **new["specifications"],
        **{k: v for k, v in proposed_specs.items() if k in allowed_keys and k not in result.uncertain_fields},
    }
    new["delivery"] = {**new["delivery"], **delivered}
    if result.deadline:
        new["deadline"] = result.deadline
    new = Draft.model_validate(new).model_dump()
    previous_uncertain = set(conv.draft.get("_uncertain", []))
    resolved = set(patch.get("specifications", {})) | set(delivered) | ({"deadline"} if result.deadline else set())
    uncertain = (previous_uncertain - resolved) | set(result.uncertain_fields)
    if uncertain:
        labels = {r["key"]: r["label"] for r in product["requirements"]} if product else {}
        conv.draft = {**new, "_uncertain": sorted(uncertain), "_ready": False}
        return "این بخش مبهم است؛ فقط مقدار نهایی را مشخص کنید: " + "، ".join(
            labels.get(k, k) for k in sorted(uncertain)
        )
    try:
        asked, question = ask_missing(db, new, products)
    except HTTPException as exc:
        conv.draft = {**new, "_ready": False}
        return str(exc.detail)
    ready = asked is None
    if result.intent == "confirm" and ready and conv.draft.get("_ready") and new == old:
        order = create_order(db, customer, new)
        conv.order_id = order.id
        for m in rows(db, Message, conversation_id=conv.id):
            if m.order_id is None:
                m.order_id = order.id
        payment = payment_link(db, order)
        conv.draft = {**new, "_ready": False}
        return (
            f"سفارش #{order.id} ثبت شد. مبلغ {order.total:,} تومان است. "
            f"پرداخت کاملاً آزمایشی است و پولی جابه‌جا نمی‌شود.\nپیوند پرداخت: {payment_data(payment)['url']}\n"
            f"پیگیری خصوصی: {settings().public_base_url}/track/{order.tracking_token}"
        )
    conv.draft = {**new, "_asked": asked, "_ready": ready, "_uncertain": []}
    return question
