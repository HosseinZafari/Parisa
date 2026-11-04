"""قراردادهای خروجی عمومی؛ فیلدهای پیگیری عمداً به فهرست مجاز محدودند."""

from typing import Literal

from pydantic import BaseModel, Field

from .schemas import Draft, RequirementInput, SellerProfile


OrderStatus = Literal[
    "awaiting_payment",
    "paid_awaiting_preparation",
    "in_preparation",
    "ready_to_ship",
    "change_requested",
    "awaiting_seller_approval",
    "shipped",
    "canceled",
]
PaymentStatus = Literal["pending", "success", "failed", "canceled", "expired"]


class Ok(BaseModel):
    ok: bool


class Identity(BaseModel):
    id: int
    name: str
    username: str


class Health(BaseModel):
    status: str
    database: str
    version: str


class ProductResponse(BaseModel):
    id: int
    revision: str
    name: str
    description: str
    category: str
    aliases: list[str]
    price: int
    inventory: int
    shipping_cost: int
    preparation_days: int
    enabled: bool
    color: str
    requirements: list[RequirementInput]


class Quote(BaseModel):
    product_id: int
    product_name: str
    quantity: int | None
    specifications: dict[str, str]
    requirement_schema: list[RequirementInput]
    delivery: dict[str, str]
    unit_price: int
    subtotal: int
    shipping_cost: int
    total: int
    deadline: str
    missing: list[str]


class PaymentLink(BaseModel):
    id: int
    order_id: int
    amount: int
    status: PaymentStatus
    expires_at: str
    confirmed_at: str | None
    url: str
    provider: str


class PaymentView(BaseModel):
    order_id: int
    amount: int
    status: PaymentStatus
    expires_at: str
    test_only: bool


class PaymentResult(BaseModel):
    status: PaymentStatus
    duplicate: bool
    order_id: int


class ChangeResponse(BaseModel):
    id: int
    original: dict
    proposed: dict
    status: Literal["pending", "approved", "rejected", "manual"]
    reason: str
    created_at: str
    resolved_at: str | None
    responsible_user: str | None


class ChangeQuote(BaseModel):
    unit_price: int
    subtotal: int
    shipping_cost: int
    total: int
    deadline: str
    schema_: list[RequirementInput] = Field(alias="schema")


class NotificationResponse(BaseModel):
    conversation_id: int | None = None
    priority: Literal["normal", "urgent"] = "normal"
    id: int
    order_id: int | None
    kind: str
    text: str
    read: bool
    created_at: str


class OrderSummary(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    customer_username: str
    customer_phone: str
    status: OrderStatus
    status_label: str
    version: int
    product_name: str
    product_id: int
    quantity: int
    unit_price: int
    subtotal: int
    shipping_cost: int
    total: int
    paid_amount: int
    balance: int
    payment_status: Literal["paid", "unpaid"]
    deadline: str | None
    tracking_number: str
    carrier: str
    created_at: str
    paid_at: str | None
    shipped_at: str | None
    overdue: bool
    pending_change: bool
    next_action: str


class MessageResponse(BaseModel):
    id: int
    role: str
    text: str
    created_at: str


class HistoryResponse(BaseModel):
    id: int
    kind: str
    text: str
    actor: str
    created_at: str


class OrderDetail(OrderSummary):
    delivery: dict[str, str]
    specifications: dict[str, str]
    requirement_schema: list[RequirementInput]
    tracking_url: str | None
    seller_notes: str
    customer_status_message: str
    conversation_summary: str
    shipping_blocks: list[str]
    history: list[HistoryResponse]
    changes: list[ChangeResponse]
    messages: list[MessageResponse]
    payments: list[PaymentLink]
    notifications: list[NotificationResponse]
    allowed_statuses: list[OrderStatus]


class TrackingChange(BaseModel):
    id: int
    status: str
    created_at: str
    resolved_at: str | None
    reason: str
    specifications: dict[str, str]


class Tracking(BaseModel):
    id: int
    product_name: str
    quantity: int
    specifications: dict[str, str]
    requirement_schema: list[RequirementInput]
    status: OrderStatus
    status_label: str
    total: int
    paid_amount: int
    balance: int
    deadline: str | None
    tracking_number: str
    carrier: str
    status_message: str
    changes: list[TrackingChange]
    created_at: str
    shipped_at: str | None


class ChatState(BaseModel):
    suggested_replies: list[str] = Field(default_factory=list)
    token: str
    handover: bool
    channel: str
    messages: list[MessageResponse]
    draft: Draft
    summary: Quote | None
    ready_to_confirm: bool
    order: Tracking | None
    tracking_url: str | None
    payment: PaymentLink | None


class CustomerResponse(BaseModel):
    id: int
    name: str
    username: str
    phone: str
    address: str
    city: str
    postal_code: str
    notes: str
    total_orders: int
    total_paid: int
    last_interaction_at: str


class CustomerDetail(CustomerResponse):
    orders: list[OrderDetail]


class DailyStat(BaseModel):
    date: str
    orders: int
    paid: int


class RecentCustomer(Identity):
    last_interaction_at: str


class ConversationTask(BaseModel):
    conversation_id: int
    customer_name: str
    priority: Literal["normal", "urgent"]
    reason: str
    updated_at: str


class Dashboard(BaseModel):
    attention_queue: list[ConversationTask] = Field(default_factory=list)
    pending_conversations: int = 0
    urgent_conversations: int = 0
    total_orders: int
    total_customers: int
    paid_total: int
    unread_notifications: int
    overdue: int
    due_today: int
    pending_changes: int
    status_counts: dict[str, int]
    queue: list[OrderSummary]
    daily: list[DailyStat]
    today: str
    recent_customers: list[RecentCustomer]


class TrackingLink(BaseModel):
    tracking_url: str | None


class LLMConnectionStatus(BaseModel):
    status: str
    message: str
    model: str | None
    checked_at: str | None
    http_status: int | None
    retry_after_seconds: int


class SettingsResponse(BaseModel):
    seller_profile: SellerProfile = Field(default_factory=SellerProfile)
    llm_connection: LLMConnectionStatus
    llm_mode: Literal["mock", "api"]
    llm_model: str | None
    instagram_mode: Literal["mock", "live"]
    payment_mode: Literal["mock"]
    instagram_configured: bool
    app_env: str
    business_timezone: str
    max_message_length: int
    max_conversation_messages: int
    max_llm_requests: int


class AttentionFields(BaseModel):
    attention_status: Literal["none", "open", "resolved"] = "none"
    attention_priority: Literal["normal", "urgent"] = "normal"
    handover_reason: str = ""
    attention_resolved_at: str | None = None
    attention_resolved_by: str | None = None


class ConversationSummary(AttentionFields):
    id: int
    customer_name: str
    customer_username: str
    customer_id: int
    order_id: int | None
    handover: bool
    channel: str
    updated_at: str
    last_message: str


class DeliveryMessage(MessageResponse):
    delivery_status: str


class ConversationDetail(AttentionFields):
    id: int
    handover: bool
    order_id: int | None
    messages: list[DeliveryMessage]


class WebhookAccepted(BaseModel):
    accepted: int
