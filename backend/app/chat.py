import secrets

from fastapi import HTTPException
from sqlalchemy import select

from .config import settings
from .domain import (
    DELIVERY_LABELS,
    create_change,
    create_order,
    get_or_404,
    item_for,
    iso,
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
from .chat_knowledge import answer_questions, field_prompt, requirement_prompt, normalize_text
from .support import detect_support, request_attention, seller_profile
from .schemas import SupportSignal


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
        "suggested_replies": suggested_replies(db, conv),
        "order": tracking_data(db, db.get(Order, conv.order_id)) if conv.order_id else None,
        "tracking_url": f"{settings().public_base_url}/track/{db.get(Order, conv.order_id).tracking_token}"
        if conv.order_id and db.get(Order, conv.order_id).tracking_token
        else None,
        "payment": _active_payment(db, conv),
    }


def suggested_replies(db, conv):
    if conv.handover or conv.draft.get("_ready"):
        return []
    asked = conv.draft.get("_change_asked" if conv.order_id else "_asked", "") or ""
    if not asked.startswith("specifications.") or not conv.draft.get("product_id"):
        return []
    product = db.get(Product, conv.draft["product_id"])
    if not product or not product.enabled:
        return []
    requirement = next(
        (r for r in product_data(db, product)["requirements"] if r["key"] == asked.split(".", 1)[1]), None
    )
    return requirement["allowed_values"][:6] if requirement else []


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
            return "specifications." + r["key"], requirement_prompt(product, r)
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
                return f"delivery.{key}", field_prompt(f"delivery.{key}", product)
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
    signal = detect_support(text)
    if signal:
        reply = request_attention(db, conv, signal)
    elif conv.handover:
        if conv.attention_status != "open":
            request_attention(db, conv, SupportSignal(reason="پیام تازهٔ مشتری نیازمند پاسخ فروشنده است."))
        reply = "پیام شما برای فروشنده ذخیره شد؛ پاسخ را همین‌جا دریافت می‌کنید."
        # توقف پاسخ‌گویی خودکار، تشخیص یک مشکل تازه و جدی را متوقف نمی‌کند.
        try:
            classified, _ = extract(text, products, draft, history, conv, seller_info=seller_profile(db))
            if classified.support and classified.support.priority == "urgent":
                reply = request_attention(db, conv, classified.support)
        except (ValueError, TypeError):
            pass
    else:
        try:
            result, fallback = extract(text, products, draft, history, conv, seller_info=seller_profile(db))
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


def canonical_field(key, product):
    if key in {"name", "phone", "address", "city", "postal_code", "notes"}:
        return "delivery." + key
    if product and key in {r["key"] for r in product["requirements"]}:
        return "specifications." + key
    return key


def uncertainty_question(uncertain, product):
    return field_prompt(sorted(uncertain)[0], product, uncertain=True)


def apply_extraction(db, conv, customer, draft, result, products, text):
    if result.support:
        return request_attention(db, conv, result.support)
    product = next((p for p in products if p["id"] == (result.product_id or draft.get("product_id"))), None)
    if conv.order_id and product and result.intent not in {"new", "handover"}:
        change_help = clarify_order_change(db, conv, draft, result, product, text)
        if change_help:
            return change_help
    if result.intent == "question":
        uncertain = {canonical_field(k, product) for k in conv.draft.get("_uncertain", [])}
        confirmed_price = None
        if conv.order_id and product and product["id"] == draft.get("product_id"):
            order = db.get(Order, conv.order_id)
            confirmed_price = {
                "unit_price": item_for(db, order).unit_price,
                "shipping_cost": order.shipping_cost,
                "total": order.total,
            }
        reply, covered = answer_questions(
            result.questions,
            product,
            draft,
            uncertain=uncertain,
            asked=conv.draft.get("_asked"),
            confirmed_price=confirmed_price,
            seller_info=seller_profile(db),
            catalog=products,
        )
        if not conv.order_id and product and product["id"] == draft.get("product_id"):
            try:
                asked, followup = (
                    (sorted(uncertain)[0], uncertainty_question(uncertain, product))
                    if uncertain
                    else ask_missing(db, draft, products)
                )
                if asked and asked not in covered:
                    reply += "\n\nبرای ادامهٔ سفارشت: " + followup
            except HTTPException:
                pass
        return reply
    reply = _apply_extraction(db, conv, customer, draft, result, products, text)
    if result.questions:
        updated = snapshot(db, db.get(Order, conv.order_id)) if conv.order_id else draft_data(conv)
        product = next((p for p in products if p["id"] == updated.get("product_id")), product)
        answer, covered = answer_questions(
            result.questions,
            product,
            updated,
            uncertain=conv.draft.get("_uncertain", []),
            asked=conv.draft.get("_asked"),
            seller_info=seller_profile(db),
            catalog=products,
        )
        return answer if conv.draft.get("_asked") in covered else answer + "\n\n" + reply
    return reply


def _apply_extraction(db, conv, customer, draft, result, products, text):
    if result.intent == "handover":
        return request_attention(db, conv, SupportSignal(reason="مشتری درخواست پاسخ مستقیم فروشنده دارد."))
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
    selected_product = next((p for p in products if p["id"] == (result.product_id or draft.get("product_id"))), None)
    current_uncertain = {canonical_field(k, selected_product) for k in result.uncertain_fields}
    patch = {}
    if result.product_id and "product_id" not in current_uncertain:
        patch["product_id"] = result.product_id
    if result.quantity and "quantity" not in current_uncertain:
        patch["quantity"] = result.quantity
    if result.specifications:
        patch["specifications"] = {
            k: v for k, v in result.specifications.items() if "specifications." + k not in current_uncertain
        }
    delivered = {k: v for k, v in extracted["delivery"].items() if v and "delivery." + k not in current_uncertain}
    if delivered:
        patch["delivery"] = delivered
    if result.deadline and "deadline" not in current_uncertain:
        patch["deadline"] = result.deadline
    if conv.order_id:
        if current_uncertain:
            conv.draft = {**conv.draft, "_change_asked": sorted(current_uncertain)[0]}
            return uncertainty_question(current_uncertain, selected_product)
        order = get_or_404(db, Order, conv.order_id)
        if patch:
            try:
                change = create_change(db, order, patch)
                conv.draft = {k: v for k, v in conv.draft.items() if k != "_change_asked"}
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
        **{
            k: v
            for k, v in proposed_specs.items()
            if k in allowed_keys and "specifications." + k not in current_uncertain
        },
    }
    new["delivery"] = {**new["delivery"], **delivered}
    if "deadline" in patch:
        new["deadline"] = patch["deadline"]
    new = Draft.model_validate(new).model_dump()
    previous_uncertain = {canonical_field(k, product) for k in conv.draft.get("_uncertain", [])}
    resolved = {"specifications." + k for k in patch.get("specifications", {})} | {"delivery." + k for k in delivered}
    resolved |= {k for k in ("quantity", "product_id", "deadline") if k in patch}
    uncertain = (previous_uncertain - resolved) | current_uncertain
    if uncertain:
        conv.draft = {**new, "_uncertain": sorted(uncertain), "_asked": sorted(uncertain)[0], "_ready": False}
        return uncertainty_question(uncertain, product)
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


def clarify_order_change(db, conv, draft, result, product, text):
    """درخواست ناقص تغییر را به انتخاب مشخصه و سپس مقدار تازه تبدیل می‌کند."""
    plain = normalize_text(text)
    requested = result.intent in {"change", "correct"} or any(
        word in plain for word in ["تغییر", "عوض", "اصلاح", "بجاش", "به جاش"]
    )
    asked = conv.draft.get("_change_asked")
    if not requested and not asked:
        return None
    if result.intent == "question" and not requested and plain not in {
        normalize_text(r["label"]) for r in product["requirements"]
    }:
        return None
    values = result.model_dump()
    changed = (
        (result.product_id and result.product_id != draft["product_id"])
        or (result.quantity and result.quantity != draft["quantity"])
        or (result.deadline and result.deadline != draft.get("deadline"))
        or any(v != draft["specifications"].get(k) for k, v in result.specifications.items())
        or any(v and v != draft["delivery"].get(k) for k, v in values["delivery"].items())
    )
    if changed or result.uncertain_fields:
        # انتخاب صریح همراه سؤال هم باید در مسیر درخواست تغییر بررسی شود.
        if result.intent == "question" and not is_change_question(plain):
            result.intent = "change"
        return None
    order = db.get(Order, conv.order_id)
    if order.status == "canceled":
        return "این سفارش لغو شده و قابل تغییر نیست؛ برای بررسی بیشتر فروشنده را بخواه."
    if order.status == "shipped":
        return "این سفارش ارسال شده است. مقدار دقیق تغییر را بنویس تا برای پیگیری دستی فروشنده ثبت شود."
    for field, aliases in {
        "quantity": ["تعداد"],
        "delivery.address": ["نشانی", "آدرس"],
        "delivery.phone": ["شماره همراه", "شماره موبایل", "تلفن"],
        "delivery.city": ["شهر"],
        "deadline": ["موعد", "تاریخ ارسال", "تاریخ تحویل"],
    }.items():
        if (requested and any(alias in plain for alias in aliases)) or plain in aliases:
            conv.draft = {**conv.draft, "_change_asked": field}
            return "برای درخواست تغییر: " + field_prompt(field, product) + "\nمقدار تازه برای تأیید فروشنده ارسال می‌شود."
    requirement = next((r for r in product["requirements"] if normalize_text(r["label"]) in plain), None)
    if not requirement and asked and not requested:
        requirement = next((r for r in product["requirements"] if asked == "specifications." + r["key"]), None)
    if requirement:
        field = "specifications." + requirement["key"]
        conv.draft = {**conv.draft, "_change_asked": field}
        current = draft["specifications"].get(requirement["key"], "ثبت نشده")
        return (
            f"{requirement['label']} سفارش فعلی «{current}» است. "
            + ("این همان مقدار فعلی است؛ برای تغییر، مقدار دیگری انتخاب کن.\n" if result.specifications else "مقدار جدیدش چه باشد؟\n")
            + requirement_prompt(product, requirement)
            + "\nانتخاب تازه فقط به‌عنوان درخواست برای تأیید فروشنده ثبت می‌شود."
        )
    if requested:
        conv.draft = {**conv.draft, "_change_asked": "field"}
        choices = [f"{r['label']}: {draft['specifications'].get(r['key'], 'ثبت نشده')}" for r in product["requirements"]]
        return (
            "کدام بخش سفارش را می‌خواهی تغییر بدهی؟\n"
            + "\n".join("• " + choice for choice in choices)
            + "\nتعداد، نشانی یا موعد ارسال را هم می‌توانی تغییر بدهی. مثلاً بنویس «اندازه» یا «اندازه کوچک بشه». درخواست برای تأیید فروشنده فرستاده می‌شود."
        )
    return None


def is_change_question(text):
    return any(word in text for word in ["میشه", "می شه", "می شود", "امکان", "می تونم", "میتونم"])
