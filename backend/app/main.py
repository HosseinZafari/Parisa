import asyncio
from contextlib import asynccontextmanager, suppress
import hashlib
import hmac
import json
import logging
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import case, delete, select, text

from . import schemas as s
from . import responses as r
from .auth import create_session, limiter, password_valid, require_seller, token_hash
from .chat import chat_state, find_conversation, process_message, start_chat
from .config import ROOT, settings
from .db import SessionLocal, get_db
from .domain import (
    STATUSES,
    change_data,
    change_quote,
    check_version,
    confirm_payment,
    create_change,
    create_order,
    dashboard,
    deadline_notifications,
    event,
    get_or_404,
    iso,
    notification_data,
    notify,
    order_data,
    payment_data,
    payment_is_valid,
    payment_link,
    product_data,
    quote,
    receipt_read,
    receipt_save,
    resolve_change,
    rows,
    shipment_blocks,
    tracking_data,
    transition,
)
from .instagram import ingest_webhook, verify_signature, worker
from .llm import match_products
from .llm import check_connection
from .llm_status import connection_status
from .support import attention_data, request_attention, resolve_attention, seller_profile
from .models import (
    ChangeRequest,
    Conversation,
    Customer,
    Message,
    Notification,
    Order,
    Payment,
    Product,
    ProductRequirement,
    Seller,
    SellerSession,
    now,
)
from .seed import ensure_seller, seed

config = settings()
logger = logging.getLogger("parisa")


@asynccontextmanager
async def lifespan(app):
    with SessionLocal() as db:
        ensure_seller(db)
        if config.seed_demo:
            seed(db)
        db.commit()
    task = asyncio.create_task(worker())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="پریسا | مدیریت سفارش",
    version="0.1.0",
    description="رابط نمونهٔ آزمایشی تک‌فروشنده؛ مبلغ‌ها به تومان و زمان‌ها UTC هستند.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def safety_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if origin and origin.rstrip("/") not in config.origins:
            return JSONResponse({"detail": "مبدأ درخواست مجاز نیست."}, status_code=403)
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 65536:
                return JSONResponse({"detail": "حجم درخواست بیش از حد مجاز است."}, status_code=413)
        request._body = bytes(content)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.path in {"/docs", "/redoc"}:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        )
    if request.url.path.startswith(("/api", "/pay", "/track")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "اطلاعات ارسالی معتبر نیست؛ فیلدهای فرم را بررسی کنید.",
            "fields": [".".join(str(x) for x in e["loc"][1:]) for e in exc.errors()],
        },
    )


@app.exception_handler(Exception)
async def unexpected_error(_, exc):
    logger.error("request_failed type=%s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "خطای داخلی رخ داد؛ دوباره تلاش کنید."})


def key_required(idempotency_key: str = Header(min_length=8, max_length=150)):
    return idempotency_key


def mutate(db, scope, key, payload, action):
    previous, fingerprint = receipt_read(db, scope, key, payload)
    if previous:
        return previous.result
    result = action()
    db.flush()
    receipt_save(db, scope, key, fingerprint, result)
    return result


def customer_message(db, order, text):
    conv = db.scalar(select(Conversation).where(Conversation.order_id == order.id).order_by(Conversation.id.desc()))
    if conv:
        db.add(
            Message(
                conversation_id=conv.id,
                order_id=order.id,
                role="assistant",
                text=text,
                delivery_status="pending" if conv.channel == "instagram" else "saved",
            )
        )


@app.get("/api/health", response_model=r.Health, tags=["سلامت"])
def health(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok", "version": "0.1.0"}


@app.post("/api/auth/login", response_model=r.Identity, tags=["احراز هویت"])
def login(body: s.Login, request: Request, response: Response, db=Depends(get_db)):
    limiter.check("login:" + request.client.host, 10, 300)
    seller = db.scalar(select(Seller).where(Seller.username == body.username))
    if not seller or not password_valid(body.password, seller.password_hash):
        raise HTTPException(401, "نام کاربری یا گذرواژه نادرست است.")
    token = create_session(db, seller)
    response.set_cookie(
        "parisa_session",
        token,
        httponly=True,
        secure=config.cookie_secure,
        samesite="strict",
        max_age=43200,
        path="/api",
    )
    return {"id": seller.id, "name": seller.name, "username": seller.username}


@app.post("/api/auth/logout", response_model=r.Ok, tags=["احراز هویت"])
def logout(request: Request, response: Response, db=Depends(get_db)):
    db.execute(
        delete(SellerSession).where(SellerSession.token_hash == token_hash(request.cookies.get("parisa_session", "")))
    )
    response.delete_cookie("parisa_session", path="/api")
    return {"ok": True}


@app.get("/api/auth/me", response_model=r.Identity, tags=["احراز هویت"])
def me(seller=Depends(require_seller)):
    return {"id": seller.id, "name": seller.name, "username": seller.username}


@app.get("/api/catalog", response_model=list[r.ProductResponse], tags=["کاتالوگ"])
def catalog(q: str = "", db=Depends(get_db)):
    products = [product_data(db, p) for p in rows(db, Product, enabled=True)]
    return match_products(q[:200], products) if q else products


@app.get("/api/catalog/{product_id}", response_model=r.ProductResponse, tags=["کاتالوگ"])
def catalog_product(product_id: int, db=Depends(get_db)):
    product = get_or_404(db, Product, product_id)
    if not product.enabled:
        raise HTTPException(404, "محصول پیدا نشد.")
    return product_data(db, product)


@app.post("/api/chat/start", response_model=r.ChatState, tags=["گفتگوی مشتری"])
def new_chat(body: s.ChatStart, request: Request, db=Depends(get_db)):
    limiter.check("start:" + request.client.host, 20, 300)
    return chat_state(db, start_chat(db, body.name))


@app.get("/api/chat/{token}", response_model=r.ChatState, tags=["گفتگوی مشتری"])
def get_chat(token: str, db=Depends(get_db)):
    return chat_state(db, find_conversation(db, token))


@app.post("/api/chat/{token}/messages", response_model=r.ChatState, tags=["گفتگوی مشتری"])
def chat_message(token: str, body: s.ChatMessage, request: Request, db=Depends(get_db)):
    limiter.check("chat-ip:" + request.client.host, config.chat_requests_per_minute * 3)
    limiter.check("chat:" + token, config.chat_requests_per_minute)
    return process_message(db, find_conversation(db, token), body.text, body.client_id)


@app.get("/api/dashboard", response_model=r.Dashboard, tags=["داشبورد"])
def get_dashboard(seller=Depends(require_seller), db=Depends(get_db)):
    return dashboard(db)


@app.get("/api/settings", response_model=r.SettingsResponse, tags=["تنظیمات"])
def get_settings(seller=Depends(require_seller)):
    return {
        "llm_connection": connection_status(),
        "seller_profile": s.SellerProfile.model_validate(
            {
                **(seller.public_profile or {}),
                "store_name": (seller.public_profile or {}).get("store_name") or seller.name,
            }
        ).model_dump(),
        "llm_mode": config.llm_mode,
        "llm_model": config.llm_model if config.llm_mode == "api" else None,
        "instagram_mode": config.instagram_mode,
        "payment_mode": config.payment_mode,
        "instagram_configured": bool(config.instagram_account_id),
        "app_env": config.app_env,
        "business_timezone": config.business_timezone,
        "max_message_length": config.max_message_length,
        "max_conversation_messages": config.max_conversation_messages,
        "max_llm_requests": config.max_llm_requests,
    }


@app.post("/api/llm/check", response_model=r.LLMConnectionStatus, tags=["تنظیمات"])
def test_llm_connection(request: Request, seller=Depends(require_seller)):
    limiter.check("llm-check:" + str(seller.id), 3)
    return check_connection()


@app.put("/api/seller/profile", response_model=s.SellerProfile, tags=["تنظیمات"])
def update_seller_profile(
    body: s.SellerProfile, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)
):
    def action():
        seller.public_profile = body.model_dump()
        db.flush()
        return seller_profile(db)

    return mutate(db, "seller:profile", key, body.model_dump(), action)


@app.get("/api/orders", response_model=list[r.OrderSummary], tags=["سفارش"])
def orders(seller=Depends(require_seller), db=Depends(get_db)):
    return [order_data(db, o) for o in db.scalars(select(Order).order_by(Order.id.desc()))]


@app.post("/api/orders/quote", response_model=r.Quote, tags=["سفارش"])
def order_quote(body: s.Draft, seller=Depends(require_seller), db=Depends(get_db)):
    return quote(db, body.model_dump())


@app.post("/api/orders", response_model=r.OrderDetail, tags=["سفارش"])
def new_order(body: s.OrderCreate, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)):
    def action():
        draft = body.model_dump(exclude={"customer_id"})
        order = create_order(db, get_or_404(db, Customer, body.customer_id), draft)
        return order_data(db, order, True)

    return mutate(db, "order:create", key, body.model_dump(), action)


@app.get("/api/orders/{order_id}", response_model=r.OrderDetail, tags=["سفارش"])
def get_order(order_id: int, seller=Depends(require_seller), db=Depends(get_db)):
    return order_data(db, get_or_404(db, Order, order_id), True)


@app.post("/api/orders/{order_id}/confirm", response_model=r.PaymentLink, tags=["سفارش"])
def order_confirmation(
    order_id: int, body: s.VersionInput, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)
):
    def action():
        order = get_or_404(db, Order, order_id)
        check_version(order, body.version)
        return payment_data(payment_link(db, order))

    return mutate(db, f"order:{order_id}:confirm", key, body.model_dump(), action)


@app.post("/api/orders/{order_id}/payment-link", response_model=r.PaymentLink, tags=["پرداخت"])
def new_payment_link(order_id: int, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)):
    return mutate(
        db,
        f"order:{order_id}:payment",
        key,
        {},
        lambda: payment_data(payment_link(db, get_or_404(db, Order, order_id))),
    )


@app.patch("/api/orders/{order_id}", response_model=r.OrderDetail, tags=["سفارش"])
def edit_order(
    order_id: int, body: s.OrderEdit, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)
):
    def action():
        order = get_or_404(db, Order, order_id)
        check_version(order, body.version)
        updates = body.model_dump(exclude_unset=True, exclude={"version"})
        if any(updates.get(field, "") is None for field in ["seller_notes", "customer_status_message"]):
            raise HTTPException(422, "برای پاک‌کردن یادداشت، رشتهٔ خالی بفرستید.")
        if "deadline" in updates and order.status in {"shipped", "canceled"}:
            raise HTTPException(409, "موعد سفارش بسته‌شده قابل تغییر نیست.")
        previous_status_message = order.customer_status_message
        for field, value in updates.items():
            setattr(order, field, value)
        order.version += 1
        event(db, order, "seller_updated", "یادداشت یا موعد سفارش به‌روز شد.", seller.username)
        if body.customer_status_message and body.customer_status_message != previous_status_message:
            customer_message(db, order, body.customer_status_message)
        return order_data(db, order, True)

    return mutate(db, f"order:{order_id}:edit", key, body.model_dump(exclude_unset=True), action)


@app.post("/api/orders/{order_id}/status", response_model=r.OrderDetail, tags=["سفارش"])
def set_status(
    order_id: int, body: s.StatusInput, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)
):
    def action():
        order = get_or_404(db, Order, order_id)
        check_version(order, body.version)
        transition(db, order, body.status, seller)
        customer_message(db, order, f"وضعیت سفارش #{order.id}: {STATUSES[order.status]}")
        return order_data(db, order, True)

    return mutate(db, f"order:{order_id}:status", key, body.model_dump(), action)


@app.post("/api/orders/{order_id}/ship", response_model=r.OrderDetail, tags=["ارسال"])
def ship(
    order_id: int, body: s.ShipmentInput, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)
):
    def action():
        order = get_or_404(db, Order, order_id)
        check_version(order, body.version)
        blocks = shipment_blocks(db, order)
        if blocks:
            raise HTTPException(409, "ارسال مجاز نیست: " + "؛ ".join(blocks))
        order.tracking_number, order.carrier, order.shipped_at = body.tracking_number, body.carrier, now()
        transition(db, order, "shipped", seller)
        notify(db, order, "shipped", f"سفارش #{order.id} به {body.carrier} تحویل داده شد.", f"order:{order.id}:shipped")
        customer_message(
            db,
            order,
            f"سفارش شما ارسال شد. کد رهگیری: {body.tracking_number}\n{config.public_base_url}/track/{order.tracking_token}",
        )
        return order_data(db, order, True)

    return mutate(db, f"order:{order_id}:ship", key, body.model_dump(), action)


@app.post("/api/orders/{order_id}/changes", response_model=r.ChangeResponse, tags=["تغییر سفارش"])
def request_change(
    order_id: int, body: s.ChangeInput, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)
):
    return mutate(
        db,
        f"order:{order_id}:change",
        key,
        body.model_dump(exclude_unset=True),
        lambda: change_data(create_change(db, get_or_404(db, Order, order_id), body.model_dump(exclude_unset=True))),
    )


@app.get("/api/changes/{change_id}/quote", response_model=r.ChangeQuote, tags=["تغییر سفارش"])
def preview_change(change_id: int, seller=Depends(require_seller), db=Depends(get_db)):
    change = get_or_404(db, ChangeRequest, change_id)
    return change_quote(db, get_or_404(db, Order, change.order_id), change)


@app.post("/api/changes/{change_id}/{decision}", response_model=r.ChangeResponse, tags=["تغییر سفارش"])
def decide_change(
    change_id: int,
    decision: str,
    body: s.ChangeDecision,
    key=Depends(key_required),
    seller=Depends(require_seller),
    db=Depends(get_db),
):
    if decision not in {"approve", "reject", "review"}:
        raise HTTPException(404, "عملیات پیدا نشد.")

    def action():
        change = get_or_404(db, ChangeRequest, change_id)
        order = db.get(Order, change.order_id)
        if decision == "review":
            if change.status != "pending":
                raise HTTPException(409, "این درخواست دیگر منتظر بررسی نیست.")
            if order.status == "change_requested":
                transition(db, order, "awaiting_seller_approval", seller)
            return change_data(change)
        result = resolve_change(db, order, change, decision == "approve", seller, body.reason)
        customer_message(
            db,
            order,
            f"درخواست تغییر شما {'تأیید' if decision == 'approve' else 'رد'} شد."
            + (f" {body.reason}" if body.reason else ""),
        )
        if order.status == "awaiting_payment":
            customer_message(
                db, order, "پیوند پرداخت آزمایشی ماندهٔ سفارش: " + payment_data(payment_link(db, order))["url"]
            )
        return change_data(result)

    return mutate(db, f"change:{change_id}:{decision}", key, body.model_dump(), action)


@app.get("/api/payments/{token}", response_model=r.PaymentView, tags=["پرداخت"])
def get_payment(token: str, db=Depends(get_db)):
    p = db.scalar(select(Payment).where(Payment.token == token))
    if not p:
        raise HTTPException(404, "پیوند پرداخت پیدا نشد.")
    status = p.status if p.status != "pending" or payment_is_valid(db, p) else "expired"
    return {
        "order_id": p.order_id,
        "amount": p.amount,
        "status": status,
        "expires_at": iso(p.expires_at),
        "test_only": True,
    }


@app.post("/api/payments/{token}/simulate", response_model=r.PaymentResult, tags=["پرداخت"])
def simulate_payment(token: str, body: s.PaymentSimulation, request: Request, db=Depends(get_db)):
    limiter.check("payment:" + request.client.host, 60)
    p = db.scalar(select(Payment).where(Payment.token == token))
    if not p:
        raise HTTPException(404, "پیوند پرداخت پیدا نشد.")
    # شبیه‌ساز درگاه قابل جایگزینی است؛ هیچ مبلغی از مرورگر قبول نمی‌شود.
    return confirm_payment(db, p, body.outcome)


@app.post("/api/payments/callback", response_model=r.PaymentResult, tags=["پرداخت"])
async def payment_callback(request: Request, db=Depends(get_db)):
    raw = await request.body()
    expected = hmac.new(config.payment_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("x-payment-signature", "")):
        raise HTTPException(403, "امضای تأیید پرداخت معتبر نیست.")
    try:
        body = s.PaymentCallback.model_validate_json(raw)
    except ValueError:
        raise HTTPException(422, "ساختار تأیید پرداخت معتبر نیست.")

    def action():
        p = db.scalar(select(Payment).where(Payment.token == body.payment_token))
        if not p:
            raise HTTPException(404, "پرداخت پیدا نشد.")
        return confirm_payment(db, p, body.outcome)

    return mutate(db, "payment:callback", body.event_id, body.model_dump(), action)


@app.get("/api/tracking/{token}", response_model=r.Tracking, tags=["پیگیری خصوصی"])
def tracking(token: str, db=Depends(get_db)):
    order = db.scalar(select(Order).where(Order.tracking_token == token))
    if not order:
        raise HTTPException(404, "پیوند پیگیری معتبر نیست یا باطل شده است.")
    return tracking_data(db, order)


@app.post("/api/orders/{order_id}/tracking/{action}", response_model=r.TrackingLink, tags=["پیگیری خصوصی"])
def manage_tracking(
    order_id: int, action: str, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)
):
    if action not in {"revoke", "rotate"}:
        raise HTTPException(404, "عملیات پیدا نشد.")

    def change_token():
        order = get_or_404(db, Order, order_id)
        order.tracking_token = secrets.token_urlsafe(32) if action == "rotate" else None
        event(db, order, "tracking_changed", "پیوند پیگیری خصوصی تعویض یا باطل شد.", seller.username)
        return {
            "tracking_url": f"{config.public_base_url}/track/{order.tracking_token}" if order.tracking_token else None
        }

    return mutate(db, f"tracking:{order_id}:{action}", key, {}, change_token)


@app.get("/api/products", response_model=list[r.ProductResponse], tags=["مدیریت محصول"])
def products(seller=Depends(require_seller), db=Depends(get_db)):
    return [product_data(db, p) for p in rows(db, Product)]


def save_product(db, product, body):
    if product.id and body.revision != iso(product.updated_at):
        raise HTTPException(409, "این محصول یا موجودی آن تغییر کرده است؛ اطلاعات تازه را دریافت کنید.")
    if product.id:
        product.updated_at = now()
    for field, value in body.model_dump(exclude={"requirements", "revision"}).items():
        setattr(product, field, value)
    db.add(product)
    db.flush()
    db.execute(delete(ProductRequirement).where(ProductRequirement.product_id == product.id))
    for requirement in body.requirements:
        db.add(ProductRequirement(product_id=product.id, **requirement.model_dump()))
    db.flush()
    return product_data(db, product)


@app.post("/api/products", response_model=r.ProductResponse, tags=["مدیریت محصول"])
def add_product(body: s.ProductInput, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)):
    return mutate(db, "product:create", key, body.model_dump(), lambda: save_product(db, Product(), body))


@app.put("/api/products/{product_id}", response_model=r.ProductResponse, tags=["مدیریت محصول"])
def edit_product(
    product_id: int, body: s.ProductInput, key=Depends(key_required), seller=Depends(require_seller), db=Depends(get_db)
):
    return mutate(
        db,
        f"product:{product_id}",
        key,
        body.model_dump(),
        lambda: save_product(db, get_or_404(db, Product, product_id), body),
    )


def customer_data(db, c):
    orders = rows(db, Order, customer_id=c.id)
    return {
        "id": c.id,
        "name": c.name,
        "username": c.username,
        "phone": c.phone,
        "address": c.address,
        "city": c.city,
        "postal_code": c.postal_code,
        "notes": c.notes,
        "total_orders": len(orders),
        "total_paid": sum(o.paid_amount for o in orders),
        "last_interaction_at": iso(c.last_interaction_at),
    }


@app.get("/api/customers", response_model=list[r.CustomerResponse], tags=["مدیریت مشتری"])
def customers(seller=Depends(require_seller), db=Depends(get_db)):
    return [customer_data(db, c) for c in db.scalars(select(Customer).order_by(Customer.last_interaction_at.desc()))]


@app.get("/api/customers/{customer_id}", response_model=r.CustomerDetail, tags=["مدیریت مشتری"])
def customer_detail(customer_id: int, seller=Depends(require_seller), db=Depends(get_db)):
    c = get_or_404(db, Customer, customer_id)
    return {**customer_data(db, c), "orders": [order_data(db, o, True) for o in rows(db, Order, customer_id=c.id)]}


@app.patch("/api/customers/{customer_id}", response_model=r.CustomerResponse, tags=["مدیریت مشتری"])
def edit_customer(
    customer_id: int,
    body: s.CustomerEdit,
    key=Depends(key_required),
    seller=Depends(require_seller),
    db=Depends(get_db),
):
    def action():
        c = get_or_404(db, Customer, customer_id)
        for field, value in body.model_dump().items():
            setattr(c, field, value)
        return customer_data(db, c)

    return mutate(db, f"customer:{customer_id}", key, body.model_dump(), action)


@app.get("/api/notifications", response_model=list[r.NotificationResponse], tags=["اعلان"])
def notifications(seller=Depends(require_seller), db=Depends(get_db)):
    deadline_notifications(db)
    return [notification_data(n) for n in db.scalars(select(Notification).order_by(Notification.id.desc()).limit(200))]


@app.post("/api/notifications/read-all", response_model=r.Ok, tags=["اعلان"])
def read_all(seller=Depends(require_seller), db=Depends(get_db)):
    for n in rows(db, Notification, read=False):
        n.read = True
    return {"ok": True}


@app.post("/api/notifications/{notification_id}/read", response_model=r.NotificationResponse, tags=["اعلان"])
def read_notification(notification_id: int, seller=Depends(require_seller), db=Depends(get_db)):
    n = get_or_404(db, Notification, notification_id)
    n.read = True
    return notification_data(n)


@app.get("/api/conversations", response_model=list[r.ConversationSummary], tags=["گفتگوهای فروشنده"])
def conversations(seller=Depends(require_seller), db=Depends(get_db)):
    result = []
    for c in db.scalars(
        select(Conversation)
        .order_by(
            case(
                ((Conversation.attention_status == "open") & (Conversation.attention_priority == "urgent"), 0),
                (Conversation.attention_status == "open", 1),
                else_=2,
            ),
            Conversation.updated_at.desc(),
        )
        .limit(100)
    ):
        customer = db.get(Customer, c.customer_id)
        latest = db.scalar(select(Message).where(Message.conversation_id == c.id).order_by(Message.id.desc()))
        result.append(
            {
                **attention_data(c),
                "id": c.id,
                "customer_name": customer.name,
                "customer_username": customer.username,
                "customer_id": customer.id,
                "order_id": c.order_id,
                "handover": c.handover,
                "channel": c.channel,
                "updated_at": iso(c.updated_at),
                "last_message": latest.text if latest else "",
            }
        )
    return result


@app.get("/api/conversations/{conversation_id}", response_model=r.ConversationDetail, tags=["گفتگوهای فروشنده"])
def conversation_detail(conversation_id: int, seller=Depends(require_seller), db=Depends(get_db)):
    c = get_or_404(db, Conversation, conversation_id)
    return {
        **attention_data(c),
        "id": c.id,
        "handover": c.handover,
        "order_id": c.order_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "text": m.text,
                "delivery_status": m.delivery_status,
                "created_at": iso(m.created_at),
            }
            for m in db.scalars(select(Message).where(Message.conversation_id == c.id).order_by(Message.id))
        ],
    }


@app.post("/api/conversations/{conversation_id}/reply", response_model=r.Ok, tags=["گفتگوهای فروشنده"])
def reply(
    conversation_id: int,
    body: s.SellerReply,
    key=Depends(key_required),
    seller=Depends(require_seller),
    db=Depends(get_db),
):
    def action():
        c = get_or_404(db, Conversation, conversation_id)
        c.handover = not body.resume_bot
        if body.resume_bot:
            resolve_attention(db, c, seller, resume_bot=True)
        c.updated_at = now()
        db.add(
            Message(
                conversation_id=c.id,
                order_id=c.order_id,
                role="seller",
                text=body.text,
                delivery_status="pending" if c.channel == "instagram" else "saved",
            )
        )
        return {"ok": True}

    return mutate(db, f"conversation:{conversation_id}:reply", key, body.model_dump(), action)


@app.post(
    "/api/conversations/{conversation_id}/attention", response_model=r.ConversationDetail, tags=["گفتگوهای فروشنده"]
)
def manage_conversation_attention(
    conversation_id: int,
    body: s.AttentionAction,
    key=Depends(key_required),
    seller=Depends(require_seller),
    db=Depends(get_db),
):
    def action():
        c = get_or_404(db, Conversation, conversation_id)
        if body.action == "resolve":
            resolve_attention(db, c, seller, resume_bot=body.resume_bot)
        else:
            request_attention(db, c, s.SupportSignal(reason="گفتگو برای رسیدگی فروشنده باز شد."))
        db.flush()
        return conversation_detail(conversation_id, seller=seller, db=db)

    return mutate(db, f"conversation:{conversation_id}:attention", key, body.model_dump(), action)


@app.get("/api/instagram/webhook", tags=["اینستاگرام"])
def verify_webhook(request: Request):
    query = request.query_params
    if (
        query.get("hub.mode") != "subscribe"
        or not config.instagram_verify_token
        or not hmac.compare_digest(query.get("hub.verify_token", ""), config.instagram_verify_token)
    ):
        raise HTTPException(403, "توکن تأیید وب‌هوک معتبر نیست.")
    return PlainTextResponse(query.get("hub.challenge", ""))


@app.post("/api/instagram/webhook", response_model=r.WebhookAccepted, tags=["اینستاگرام"])
async def instagram_webhook(request: Request, db=Depends(get_db)):
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(403, "امضای وب‌هوک معتبر نیست.")
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError()
        return ingest_webhook(db, payload)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, "ساختار رویداد اینستاگرام معتبر نیست.")


# خروجی Vite در استقرار توسط همین سرویس ارائه می‌شود؛ مسیر API ناشناخته هرگز HTML نیست.
dist = ROOT / "frontend" / "dist"
if (dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
if (dist / "fonts").exists():
    app.mount("/fonts", StaticFiles(directory=dist / "fonts"), name="fonts")


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "مسیر پیدا نشد.")
    if (dist / "index.html").exists():
        return FileResponse(dist / "index.html")
    return {"message": "برای رابط کاربری، سرور Vite را روی درگاه ۵۱۷۳ اجرا کنید.", "api_docs": "/docs"}
