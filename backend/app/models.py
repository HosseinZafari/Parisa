from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Timestamp:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class Seller(Timestamp, Base):
    __tablename__ = "sellers"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="پریسا")
    password_hash: Mapped[str] = mapped_column(Text)
    public_profile: Mapped[dict] = mapped_column(JSON, default=dict)


class SellerSession(Base):
    __tablename__ = "seller_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Customer(Timestamp, Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="مشتری جدید")
    username: Mapped[str] = mapped_column(String(200), unique=True)
    instagram_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    phone: Mapped[str] = mapped_column(String(30), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    postal_code: Mapped[str] = mapped_column(String(20), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    last_interaction_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Product(Timestamp, Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="سایر")
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    price: Mapped[int] = mapped_column(Integer)
    inventory: Mapped[int] = mapped_column(Integer, default=100)
    shipping_cost: Mapped[int] = mapped_column(Integer, default=0)
    preparation_days: Mapped[int] = mapped_column(Integer, default=3)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    color: Mapped[str] = mapped_column(String(30), default="sage")


class ProductRequirement(Base):
    __tablename__ = "product_requirements"
    __table_args__ = (UniqueConstraint("product_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    key: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(200))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_values: Mapped[list] = mapped_column(JSON, default=list)
    price_adjustments: Mapped[dict] = mapped_column(JSON, default=dict)


class Conversation(Timestamp, Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    channel: Mapped[str] = mapped_column(String(20), default="local")
    token: Mapped[str] = mapped_column(String(100), unique=True)
    draft: Mapped[dict] = mapped_column(JSON, default=dict)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    handover: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_requests: Mapped[int] = mapped_column(Integer, default=0)
    attention_status: Mapped[str] = mapped_column(String(20), default="none")
    attention_priority: Mapped[str] = mapped_column(String(20), default="normal")
    attention_version: Mapped[int] = mapped_column(Integer, default=0)
    handover_reason: Mapped[str] = mapped_column(Text, default="")
    attention_resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    attention_resolved_by: Mapped[str | None] = mapped_column(String(100))


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "client_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    role: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    client_id: Mapped[str | None] = mapped_column(String(200))
    external_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    delivery_status: Mapped[str] = mapped_column(String(30), default="saved")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Order(Timestamp, Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[str] = mapped_column(String(50), default="awaiting_payment")
    version: Mapped[int] = mapped_column(Integer, default=1)
    delivery: Mapped[dict] = mapped_column(JSON, default=dict)
    subtotal: Mapped[int] = mapped_column(Integer)
    shipping_cost: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    paid_amount: Mapped[int] = mapped_column(Integer, default=0)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    deadline: Mapped[str | None] = mapped_column(String(10))
    tracking_number: Mapped[str] = mapped_column(String(100), default="")
    carrier: Mapped[str] = mapped_column(String(100), default="پست")
    tracking_token: Mapped[str | None] = mapped_column(String(100), unique=True)
    seller_notes: Mapped[str] = mapped_column(Text, default="")
    customer_status_message: Mapped[str] = mapped_column(Text, default="")
    conversation_summary: Mapped[str] = mapped_column(Text, default="")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer)
    # قرارداد مشخصات هنگام تأیید؛ ویرایش بعدی کاتالوگ قرارداد سفارش را تغییر نمی‌دهد.
    requirement_schema: Mapped[list] = mapped_column(JSON, default=list)


class OrderRequirementValue(Base):
    __tablename__ = "order_requirement_values"
    __table_args__ = (UniqueConstraint("order_item_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"))
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(Text)


class Payment(Timestamp, Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    token: Mapped[str] = mapped_column(String(100), unique=True)
    amount: Mapped[int] = mapped_column(Integer)
    order_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    provider: Mapped[str] = mapped_column(String(30), default="mock")


class ChangeRequest(Timestamp, Base):
    __tablename__ = "change_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    original: Mapped[dict] = mapped_column(JSON)
    proposed: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    previous_status: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    responsible_user: Mapped[str | None] = mapped_column(String(100))


class OrderHistory(Base):
    __tablename__ = "order_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    kind: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(100), default="سامانه")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"))
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    kind: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(240), unique=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Receipt(Base):
    __tablename__ = "idempotency_receipts"
    __table_args__ = (UniqueConstraint("scope", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(200))
    fingerprint: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(200), unique=True)
    sender_id: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    message_at: Mapped[datetime] = mapped_column(DateTime, default=now)
