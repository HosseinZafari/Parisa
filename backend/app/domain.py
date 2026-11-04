import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select

from .config import settings
from .models import (
    ChangeRequest,
    Customer,
    Message,
    Notification,
    Order,
    OrderHistory,
    OrderItem,
    OrderRequirementValue,
    Payment,
    Product,
    ProductRequirement,
    Receipt,
    now,
)
from .schemas import Draft

STATUSES = {
    "awaiting_payment": "در انتظار پرداخت",
    "paid_awaiting_preparation": "پرداخت‌شده، منتظر آماده‌سازی",
    "in_preparation": "در حال آماده‌سازی",
    "ready_to_ship": "آمادهٔ ارسال",
    "change_requested": "درخواست تغییر",
    "awaiting_seller_approval": "منتظر تأیید فروشنده",
    "shipped": "ارسال‌شده",
    "canceled": "لغوشده",
}
TRANSITIONS = {
    "awaiting_payment": {"canceled"},
    "paid_awaiting_preparation": {"in_preparation", "canceled"},
    "in_preparation": {"ready_to_ship", "canceled"},
    "ready_to_ship": {"in_preparation", "shipped", "canceled"},
    "change_requested": {"awaiting_seller_approval", "canceled"},
    "awaiting_seller_approval": {"canceled"},
    "shipped": set(),
    "canceled": set(),
}
DELIVERY_LABELS = {
    "name": "نام گیرنده",
    "phone": "شمارهٔ همراه",
    "city": "شهر",
    "address": "نشانی کامل",
    "postal_code": "کد پستی",
}


def today():
    return datetime.now(timezone.utc).astimezone(ZoneInfo(settings().business_timezone)).date()


def business_day(value):
    return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(settings().business_timezone)).date().isoformat()


def get_or_404(db, model, ident):
    value = db.get(model, ident)
    if value is None:
        raise HTTPException(404, "مورد درخواستی پیدا نشد.")
    return value


def rows(db, model, **filters):
    return list(db.scalars(select(model).filter_by(**filters)))


def iso(value):
    return value.isoformat() + "Z" if value else None


def event(db, order, kind, text, actor="سامانه", details=None):
    db.add(OrderHistory(order_id=order.id, kind=kind, text=text, actor=actor, details=details or {}))


def notify(db, order, kind, text, key, *, conversation=None, priority="normal"):
    if not db.scalar(select(Notification).where(Notification.dedupe_key == key)):
        db.add(
            Notification(
                order_id=order.id if order else None,
                kind=kind,
                text=text,
                dedupe_key=key,
                conversation_id=conversation.id if conversation else None,
                priority=priority,
            )
        )
        db.flush()


def receipt_read(db, scope, key, payload):
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    receipt = db.scalar(select(Receipt).filter_by(scope=scope, key=key))
    if receipt and receipt.fingerprint != fingerprint:
        raise HTTPException(409, "شناسهٔ تکرار با اطلاعات دیگری استفاده شده است.")
    return receipt, fingerprint


def receipt_save(db, scope, key, fingerprint, result):
    db.add(Receipt(scope=scope, key=key, fingerprint=fingerprint, result=result))


def requirement_data(db, product_id):
    return [
        {
            "key": r.key,
            "label": r.label,
            "required": r.required,
            "allowed_values": r.allowed_values,
            "price_adjustments": r.price_adjustments,
        }
        for r in rows(db, ProductRequirement, product_id=product_id)
    ]


def product_data(db, p):
    return {
        "revision": iso(p.updated_at),
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "category": p.category,
        "aliases": p.aliases,
        "price": p.price,
        "inventory": p.inventory,
        "shipping_cost": p.shipping_cost,
        "preparation_days": p.preparation_days,
        "enabled": p.enabled,
        "color": p.color,
        "requirements": requirement_data(db, p.id),
    }


def validate_specs(schema, values):
    keys = {r["key"] for r in schema}
    if set(values) - keys:
        raise HTTPException(422, "مشخصات ناشناخته برای این محصول فرستاده شده است.")
    missing = []
    for r in schema:
        value = values.get(r["key"], "").strip()
        if not value and r["required"]:
            missing.append(r["label"])
        elif value and r["allowed_values"] and value not in r["allowed_values"]:
            missing.append(f"{r['label']} (انتخاب از: {'، '.join(r['allowed_values'])})")
    return missing


def delivery_missing(delivery):
    missing = [label for key, label in DELIVERY_LABELS.items() if not delivery.get(key, "").strip()]
    if delivery.get("phone") and not re.fullmatch(r"(?:09\d{9}|\+989\d{9})", delivery["phone"]):
        missing.append("شمارهٔ همراه معتبر")
    if delivery.get("postal_code") and not re.fullmatch(r"\d{10}", delivery["postal_code"]):
        missing.append("کد پستی ۱۰ رقمی")
    if delivery.get("address") and len(delivery["address"].strip()) < 10:
        missing.append("نشانی دقیق شامل خیابان و پلاک")
    return list(dict.fromkeys(missing))


def quote(db, draft):
    draft = Draft.model_validate(draft).model_dump()
    product = get_or_404(db, Product, draft["product_id"]) if draft["product_id"] else None
    if not product or not product.enabled:
        raise HTTPException(422, "یک محصول فعال انتخاب کنید.")
    schema = requirement_data(db, product.id)
    missing = validate_specs(schema, draft["specifications"])
    if not draft["quantity"]:
        missing.append("تعداد")
    elif draft["quantity"] > product.inventory:
        raise HTTPException(409, "موجودی کافی نیست؛ تعداد کمتری انتخاب کنید.")
    missing.extend(delivery_missing(draft["delivery"]))
    adjustment = sum(r["price_adjustments"].get(draft["specifications"].get(r["key"]), 0) for r in schema)
    unit_price = product.price + adjustment
    subtotal = unit_price * (draft["quantity"] or 0)
    earliest = (today() + timedelta(days=product.preparation_days)).isoformat()
    deadline = draft["deadline"] or earliest
    if deadline < earliest:
        missing.append(f"موعد قابل انجام (زودترین زمان {earliest})")
    return {
        "product_id": product.id,
        "product_name": product.name,
        "quantity": draft["quantity"],
        "specifications": draft["specifications"],
        "requirement_schema": schema,
        "delivery": draft["delivery"],
        "unit_price": unit_price,
        "subtotal": subtotal,
        "shipping_cost": product.shipping_cost,
        "total": subtotal + product.shipping_cost,
        "deadline": deadline,
        "missing": missing,
    }


def item_for(db, order):
    return db.scalar(select(OrderItem).where(OrderItem.order_id == order.id))


def snapshot(db, order):
    item = item_for(db, order)
    return {
        "product_id": item.product_id,
        "quantity": item.quantity,
        "specifications": {v.key: v.value for v in rows(db, OrderRequirementValue, order_item_id=item.id)},
        "delivery": dict(order.delivery),
        "deadline": order.deadline,
    }


def set_values(db, item, values):
    db.execute(delete(OrderRequirementValue).where(OrderRequirementValue.order_item_id == item.id))
    for key, value in values.items():
        db.add(OrderRequirementValue(order_item_id=item.id, key=key, value=value))


def create_order(db, customer, draft):
    q = quote(db, draft)
    if q["missing"]:
        raise HTTPException(422, "اطلاعات ناقص است: " + "، ".join(q["missing"]))
    product = db.get(Product, q["product_id"])
    product.inventory -= q["quantity"]
    order = Order(
        customer_id=customer.id,
        delivery=q["delivery"],
        subtotal=q["subtotal"],
        shipping_cost=q["shipping_cost"],
        total=q["total"],
        deadline=q["deadline"],
        tracking_token=secrets.token_urlsafe(32),
        conversation_summary=f"{q['quantity']} عدد {product.name}",
    )
    db.add(order)
    db.flush()
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        product_name=product.name,
        quantity=q["quantity"],
        unit_price=q["unit_price"],
        requirement_schema=q["requirement_schema"],
    )
    db.add(item)
    db.flush()
    set_values(db, item, q["specifications"])
    delivery = q["delivery"]
    for key in ["name", "phone", "address", "city", "postal_code"]:
        setattr(customer, key, delivery[key])
    event(db, order, "created", "خلاصهٔ سفارش توسط مشتری تأیید شد.", "مشتری", q)
    db.flush()
    return order


def check_version(order, version):
    if order.version != version:
        raise HTTPException(409, "این سفارش تغییر کرده است؛ اطلاعات تازه را بارگیری کنید.")


def pending_changes(db, order):
    return rows(db, ChangeRequest, order_id=order.id, status="pending")


def order_missing(db, order):
    item = item_for(db, order)
    values = snapshot(db, order)["specifications"]
    return validate_specs(item.requirement_schema, values) + delivery_missing(order.delivery)


def shipment_blocks(db, order):
    blocks = []
    if order.paid_amount < order.total or not order.paid_at:
        blocks.append("پرداخت کامل تأیید نشده است")
    if pending_changes(db, order):
        blocks.append("درخواست تغییر در انتظار بررسی است")
    missing = order_missing(db, order)
    if missing:
        blocks.append("اطلاعات ناقص: " + "، ".join(missing))
    if not order.deadline:
        blocks.append("موعد ارسال مشخص نشده است")
    if order.status != "ready_to_ship":
        blocks.append("سفارش هنوز آمادهٔ ارسال نیست")
    return blocks


def invalidate_payments(db, order):
    for p in rows(db, Payment, order_id=order.id, status="pending"):
        p.status = "expired"


def payment_link(db, order):
    if order.status in {"shipped", "canceled"} or pending_changes(db, order):
        raise HTTPException(409, "امکان پرداخت این سفارش در وضعیت فعلی وجود ندارد.")
    amount = max(0, order.total - order.paid_amount)
    if not amount:
        raise HTTPException(409, "ماندهٔ قابل پرداختی وجود ندارد.")
    for p in rows(db, Payment, order_id=order.id, status="pending"):
        if p.expires_at > now() and p.amount == amount:
            return p
        p.status = "expired"
    p = Payment(
        order_id=order.id,
        token=secrets.token_urlsafe(32),
        amount=amount,
        order_version=order.version,
        expires_at=now() + timedelta(minutes=settings().payment_link_minutes),
    )
    db.add(p)
    db.flush()
    event(db, order, "payment_link", "پیوند پرداخت آزمایشی ایجاد شد.", details={"payment_id": p.id, "amount": p.amount})
    return p


def payment_data(p):
    return {
        "id": p.id,
        "order_id": p.order_id,
        "amount": p.amount,
        "status": p.status,
        "expires_at": iso(p.expires_at),
        "confirmed_at": iso(p.confirmed_at),
        "url": f"{settings().public_base_url}/pay/{p.token}",
        "provider": p.provider,
    }


def payment_is_valid(db, p):
    order = db.get(Order, p.order_id)
    return (
        p.expires_at > now()
        and p.amount == max(0, order.total - order.paid_amount)
        and order.status not in {"canceled", "shipped"}
        and not pending_changes(db, order)
    )


def confirm_payment(db, p, outcome):
    # فقط این تابعِ سمت سرور حق افزودن مبلغ پرداخت‌شده را دارد.
    order = db.get(Order, p.order_id)
    if p.status == "success":
        return {"status": "success", "duplicate": True, "order_id": order.id}
    if p.status != "pending":
        return {"status": p.status, "duplicate": True, "order_id": order.id}
    if not payment_is_valid(db, p) or outcome == "expired":
        p.status = "expired"
        event(db, order, "payment_expired", "پیوند پرداخت آزمایشی منقضی شد.")
        return {"status": "expired", "duplicate": False, "order_id": order.id}
    p.status = outcome
    if outcome == "success":
        p.confirmed_at = now()
        order.paid_amount += p.amount
        order.paid_at = now()
        order.status = "paid_awaiting_preparation"
        order.version += 1
        event(
            db,
            order,
            "payment_success",
            "پرداخت آزمایشی با تأیید سرور انجام شد.",
            details={"payment_id": p.id, "amount": p.amount},
        )
        notify(
            db,
            order,
            "payment_success",
            f"پرداخت سفارش #{order.id} تأیید شد؛ آماده‌سازی را شروع کنید.",
            f"payment:{p.id}:success",
        )
    else:
        event(
            db,
            order,
            f"payment_{outcome}",
            "پرداخت آزمایشی ناموفق بود." if outcome == "failed" else "پرداخت توسط مشتری لغو شد.",
        )
        notify(
            db,
            order,
            f"payment_{outcome}",
            f"پرداخت سفارش #{order.id} {'ناموفق بود' if outcome == 'failed' else 'لغو شد'}.",
            f"payment:{p.id}:{outcome}",
        )
    return {"status": p.status, "duplicate": False, "order_id": order.id}


def create_change(db, order, proposed):
    if order.status == "canceled":
        raise HTTPException(409, "سفارش لغوشده قابل تغییر نیست.")
    if pending_changes(db, order):
        raise HTTPException(409, "ابتدا باید درخواست تغییر قبلی بررسی شود.")
    original = snapshot(db, order)
    patch = {k: v for k, v in proposed.items() if v is not None}
    merged = {**original, **patch}
    if "delivery" in patch:
        merged["delivery"] = {**original["delivery"], **{k: v for k, v in patch["delivery"].items() if v}}
    if "specifications" in patch:
        merged["specifications"] = {**original["specifications"], **patch["specifications"]}
    if merged["product_id"] != original["product_id"]:
        merged["specifications"] = patch.get("specifications", {})
    Draft.model_validate(merged)
    if original == merged:
        raise HTTPException(422, "تغییری نسبت به سفارش فعلی ثبت نشده است.")
    manual = order.status == "shipped"
    change = ChangeRequest(
        order_id=order.id,
        original=original,
        proposed=merged,
        status="manual" if manual else "pending",
        previous_status=order.status,
    )
    db.add(change)
    db.flush()
    if not manual:
        invalidate_payments(db, order)
        order.status = "change_requested"
        order.version += 1
    event(
        db,
        order,
        "change_requested",
        "درخواست تغییر برای پیگیری دستی ثبت شد." if manual else "مشتری درخواست تغییر ثبت کرد.",
        "مشتری",
        {"change_id": change.id},
    )
    notify(
        db,
        order,
        "change_requested",
        f"درخواست تغییر سفارش #{order.id} {'نیازمند پیگیری دستی است' if manual else 'منتظر بررسی شماست'}.",
        f"change:{change.id}:new",
    )
    return change


def change_quote(db, order, change):
    old_item = item_for(db, order)
    new = change.proposed
    product = get_or_404(db, Product, new["product_id"])
    if not product.enabled:
        raise HTTPException(409, "محصول انتخاب‌شده غیرفعال است.")
    # موجودی رزروشدهٔ سفارش فعلی هنگام بررسی درخواست به ظرفیت قابل استفاده برمی‌گردد.
    available = product.inventory + (old_item.quantity if old_item.product_id == product.id else 0)
    if new["quantity"] > available:
        raise HTTPException(409, "موجودی برای تأیید این تغییر کافی نیست.")
    schema = requirement_data(db, product.id)
    missing = validate_specs(schema, new["specifications"]) + delivery_missing(new["delivery"])
    if missing:
        raise HTTPException(422, "اطلاعات درخواست تغییر ناقص است: " + "، ".join(missing))
    unit = product.price + sum(r["price_adjustments"].get(new["specifications"].get(r["key"]), 0) for r in schema)
    product_changed = any(new[k] != change.original[k] for k in ["product_id", "quantity", "specifications"])
    # تغییر صرفاً نشانی، قیمت توافق‌شدهٔ کالا را تغییر نمی‌دهد.
    if not product_changed:
        unit = old_item.unit_price
        shipping = order.shipping_cost
    else:
        shipping = product.shipping_cost
    deadline = new.get("deadline")
    if product_changed:
        earliest = (today() + timedelta(days=product.preparation_days)).isoformat()
        deadline = max(deadline or earliest, earliest)
    if not deadline:
        raise HTTPException(422, "موعد ارسال درخواست باید مشخص شود.")
    return {
        "unit_price": unit,
        "subtotal": unit * new["quantity"],
        "shipping_cost": shipping,
        "total": unit * new["quantity"] + shipping,
        "deadline": deadline,
        "schema": schema,
    }


def resolve_change(db, order, change, approve, seller, reason):
    target = "approved" if approve else "rejected"
    if change.status == target:
        return change
    if change.status != "pending":
        raise HTTPException(409, "این درخواست قبلاً بررسی شده یا نیازمند پیگیری دستی است.")
    if order.status in {"shipped", "canceled"}:
        raise HTTPException(409, "سفارش بسته شده است.")
    if approve:
        q = change_quote(db, order, change)
        new = change.proposed
        item = item_for(db, order)
        old_product = db.get(Product, item.product_id)
        old_product.inventory += item.quantity
        product = db.get(Product, new["product_id"])
        product.inventory -= new["quantity"]
        item.product_id, item.product_name = product.id, product.name
        item.quantity, item.unit_price, item.requirement_schema = new["quantity"], q["unit_price"], q["schema"]
        set_values(db, item, new["specifications"])
        order.delivery = dict(new["delivery"])
        order.subtotal, order.shipping_cost, order.total = q["subtotal"], q["shipping_cost"], q["total"]
        order.deadline = q["deadline"]
        change.proposed = {**new, "deadline": q["deadline"]}
        order.status = "awaiting_payment" if order.paid_amount < order.total else "paid_awaiting_preparation"
        if order.paid_amount > order.total:
            notify(
                db,
                order,
                "refund_manual",
                f"سفارش #{order.id} بستانکار است؛ بازپرداخت آزمایشی را دستی بررسی کنید.",
                f"change:{change.id}:refund",
            )
        event(
            db,
            order,
            "change_approved",
            "تغییر مشتری تأیید و نسخهٔ فعال سفارش به‌روز شد.",
            seller.username,
            {"before": change.original, "after": change.proposed, "total": order.total},
        )
    else:
        order.status = change.previous_status
        event(
            db,
            order,
            "change_rejected",
            "درخواست تغییر رد شد." + (f" دلیل: {reason}" if reason else ""),
            seller.username,
        )
    change.status = target
    change.reason = reason
    change.resolved_at = now()
    change.responsible_user = seller.username
    order.version += 1
    invalidate_payments(db, order)
    notify(
        db,
        order,
        f"change_{target}",
        f"درخواست تغییر سفارش #{order.id} {'تأیید' if approve else 'رد'} شد.",
        f"change:{change.id}:{target}",
    )
    db.flush()
    return change


def transition(db, order, status, seller):
    if order.status == status:
        return
    if status not in TRANSITIONS.get(order.status, set()):
        raise HTTPException(409, "تغییر وضعیت درخواستی مجاز نیست.")
    if status in {"in_preparation", "ready_to_ship", "shipped"}:
        if order.paid_amount < order.total or not order.paid_at:
            raise HTTPException(409, "ابتدا باید پرداخت کامل تأیید شود.")
        if pending_changes(db, order):
            raise HTTPException(409, "درخواست تغییر هنوز بررسی نشده است.")
    if status == "canceled":
        item = item_for(db, order)
        db.get(Product, item.product_id).inventory += item.quantity
        order.canceled_at = now()
        invalidate_payments(db, order)
        for c in pending_changes(db, order):
            c.status, c.resolved_at, c.responsible_user = "rejected", now(), seller.username
            c.reason = "سفارش توسط فروشنده لغو شد."
        if order.paid_amount:
            notify(
                db,
                order,
                "refund_manual",
                f"بازپرداخت سفارش لغوشدهٔ #{order.id} نیازمند بررسی دستی است.",
                f"order:{order.id}:cancel_refund",
            )
    order.status = status
    order.version += 1
    if status == "ready_to_ship":
        notify(
            db, order, "ready_to_ship", f"سفارش #{order.id} آمادهٔ ارسال است.", f"order:{order.id}:ready:{order.version}"
        )
    event(db, order, "status_changed", f"وضعیت سفارش به «{STATUSES[status]}» تغییر کرد.", seller.username)


def change_data(c):
    return {
        "id": c.id,
        "original": c.original,
        "proposed": c.proposed,
        "status": c.status,
        "reason": c.reason,
        "created_at": iso(c.created_at),
        "resolved_at": iso(c.resolved_at),
        "responsible_user": c.responsible_user,
    }


def next_action(db, order):
    if order.status in {"shipped", "canceled"}:
        return "مشاهدهٔ سابقه"
    if pending_changes(db, order):
        return "بررسی تغییر مشتری"
    if order.paid_amount < order.total:
        return "پیگیری پرداخت"
    if order_missing(db, order):
        return "تکمیل اطلاعات سفارش"
    if not order.deadline:
        return "تعیین موعد ارسال"
    return {
        "paid_awaiting_preparation": "شروع آماده‌سازی",
        "in_preparation": "تکمیل آماده‌سازی",
        "ready_to_ship": "ثبت کد رهگیری و ارسال",
    }.get(order.status, "تماس با مشتری")


def order_data(db, order, detail=False):
    item = item_for(db, order)
    customer = db.get(Customer, order.customer_id)
    data = {
        "id": order.id,
        "customer_id": customer.id,
        "customer_name": customer.name,
        "customer_username": customer.username,
        "customer_phone": customer.phone,
        "status": order.status,
        "status_label": STATUSES[order.status],
        "version": order.version,
        "product_name": item.product_name,
        "product_id": item.product_id,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "subtotal": order.subtotal,
        "shipping_cost": order.shipping_cost,
        "total": order.total,
        "paid_amount": order.paid_amount,
        "balance": max(0, order.total - order.paid_amount),
        "payment_status": "paid" if order.paid_amount >= order.total and order.paid_at else "unpaid",
        "deadline": order.deadline,
        "tracking_number": order.tracking_number,
        "carrier": order.carrier,
        "created_at": iso(order.created_at),
        "paid_at": iso(order.paid_at),
        "shipped_at": iso(order.shipped_at),
        "overdue": bool(
            order.deadline and order.deadline < today().isoformat() and order.status not in {"shipped", "canceled"}
        ),
        "pending_change": bool(pending_changes(db, order)),
        "next_action": next_action(db, order),
    }
    if detail:
        messages = list(db.scalars(select(Message).where(Message.order_id == order.id).order_by(Message.id)))
        data.update(
            {
                "delivery": order.delivery,
                "specifications": snapshot(db, order)["specifications"],
                "requirement_schema": item.requirement_schema,
                "tracking_url": f"{settings().public_base_url}/track/{order.tracking_token}"
                if order.tracking_token
                else None,
                "seller_notes": order.seller_notes,
                "customer_status_message": order.customer_status_message,
                "conversation_summary": order.conversation_summary,
                "shipping_blocks": shipment_blocks(db, order),
                "history": [
                    {"id": h.id, "kind": h.kind, "text": h.text, "actor": h.actor, "created_at": iso(h.created_at)}
                    for h in rows(db, OrderHistory, order_id=order.id)
                ],
                "changes": [change_data(c) for c in rows(db, ChangeRequest, order_id=order.id)],
                "messages": [
                    {"id": m.id, "role": m.role, "text": m.text, "created_at": iso(m.created_at)} for m in messages
                ],
                "payments": [payment_data(p) for p in rows(db, Payment, order_id=order.id)],
                "notifications": [notification_data(n) for n in rows(db, Notification, order_id=order.id)],
                "allowed_statuses": sorted(TRANSITIONS[order.status] - {"shipped"}),
            }
        )
    return data


def notification_data(n):
    return {
        "id": n.id,
        "order_id": n.order_id,
        "conversation_id": n.conversation_id,
        "priority": n.priority,
        "kind": n.kind,
        "text": n.text,
        "read": n.read,
        "created_at": iso(n.created_at),
    }


def tracking_data(db, order):
    item = item_for(db, order)
    # فهرست مجاز صریح: هیچ نشانی، شماره، یادداشت فروشنده یا پیام داخلی منتشر نمی‌شود.
    return {
        "id": order.id,
        "product_name": item.product_name,
        "quantity": item.quantity,
        "specifications": snapshot(db, order)["specifications"],
        "requirement_schema": item.requirement_schema,
        "status": order.status,
        "status_label": STATUSES[order.status],
        "total": order.total,
        "paid_amount": order.paid_amount,
        "balance": max(0, order.total - order.paid_amount),
        "deadline": order.deadline,
        "tracking_number": order.tracking_number,
        "carrier": order.carrier,
        "status_message": order.customer_status_message,
        "changes": [
            {
                "id": c.id,
                "status": c.status,
                "created_at": iso(c.created_at),
                "resolved_at": iso(c.resolved_at),
                "reason": c.reason,
                "specifications": c.proposed.get("specifications", {}),
            }
            for c in rows(db, ChangeRequest, order_id=order.id)
        ],
        "created_at": iso(order.created_at),
        "shipped_at": iso(order.shipped_at),
    }


def deadline_notifications(db):
    day = today().isoformat()
    for order in db.scalars(select(Order).where(Order.status.not_in(["shipped", "canceled"]))):
        if not order.deadline:
            notify(
                db,
                order,
                "missing_required",
                f"موعد سفارش #{order.id} مشخص نیست.",
                f"missing-deadline:{order.id}",
            )
        elif order.deadline < day:
            notify(
                db,
                order,
                "overdue",
                f"سفارش #{order.id} از موعد ارسال گذشته است.",
                f"overdue:{order.id}:{order.deadline}",
            )
        elif order.deadline <= (today() + timedelta(days=1)).isoformat():
            notify(
                db,
                order,
                "deadline_approaching",
                f"موعد ارسال سفارش #{order.id} نزدیک است.",
                f"due:{order.id}:{order.deadline}",
            )
        missing = order_missing(db, order)
        if missing:
            notify(
                db,
                order,
                "missing_required",
                f"اطلاعات سفارش #{order.id} کامل نیست.",
                f"missing:{order.id}:" + hashlib.sha256("|".join(sorted(missing)).encode()).hexdigest()[:16],
            )


def dashboard(db):
    from .support import attention_queue

    deadline_notifications(db)
    orders = [order_data(db, o) for o in db.scalars(select(Order).order_by(Order.id.desc()))]
    active = [o for o in orders if o["status"] not in {"shipped", "canceled"}]
    queue = sorted(
        active,
        key=lambda o: (
            not o["overdue"],
            o["deadline"] or "9999",
            not o["pending_change"],
            o["paid_at"] or "9999",
            o["created_at"],
        ),
    )
    customers = list(db.scalars(select(Customer).order_by(Customer.last_interaction_at.desc()).limit(5)))
    daily = []
    for offset in range(6, -1, -1):
        day = (today() - timedelta(days=offset)).isoformat()
        daily.append(
            {
                "date": day,
                "orders": sum(
                    business_day(datetime.fromisoformat(o["created_at"].removesuffix("Z"))) == day for o in orders
                ),
                "paid": sum(
                    p.amount
                    for p in db.scalars(select(Payment).where(Payment.status == "success"))
                    if p.confirmed_at and business_day(p.confirmed_at) == day
                ),
            }
        )
    return {
        **attention_queue(db),
        "total_orders": len(orders),
        "total_customers": len(rows(db, Customer)),
        "paid_total": sum(p.amount for p in db.scalars(select(Payment).where(Payment.status == "success"))),
        "unread_notifications": len(rows(db, Notification, read=False)),
        "overdue": sum(o["overdue"] for o in active),
        "due_today": sum(o["deadline"] == today().isoformat() for o in active),
        "pending_changes": sum(o["pending_change"] for o in active),
        "status_counts": {s: sum(o["status"] == s for o in orders) for s in STATUSES},
        "queue": queue,
        "daily": daily,
        "today": today().isoformat(),
        "recent_customers": [
            {"id": c.id, "name": c.name, "username": c.username, "last_interaction_at": iso(c.last_interaction_at)}
            for c in customers
        ],
    }
