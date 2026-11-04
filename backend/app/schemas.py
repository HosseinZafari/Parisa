import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(StrictModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class RequirementInput(StrictModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")
    label: str = Field(min_length=1, max_length=100)
    required: bool = True
    allowed_values: list[str] = Field(default_factory=list, max_length=30)
    price_adjustments: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_adjustments(self):
        if any(k not in self.allowed_values or v < 0 or v > 100_000_000 for k, v in self.price_adjustments.items()):
            raise ValueError("افزایش قیمت باید غیرمنفی و مربوط به یکی از گزینه‌ها باشد.")
        if any(not s or len(s) > 200 for s in self.allowed_values):
            raise ValueError("گزینهٔ مشخصات نامعتبر است.")
        return self


class ProductInput(StrictModel):
    revision: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=3000)
    category: str = Field(default="سایر", max_length=100)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    price: int = Field(ge=1, le=100_000_000)
    inventory: int = Field(ge=0, le=100_000)
    shipping_cost: int = Field(ge=0, le=10_000_000)
    preparation_days: int = Field(ge=0, le=365)
    enabled: bool = True
    color: Literal["sage", "rose", "sand", "blue", "lilac"] = "sage"
    requirements: list[RequirementInput] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_keys(self):
        if len({r.key for r in self.requirements}) != len(self.requirements):
            raise ValueError("شناسهٔ مشخصات تکراری است.")
        return self


def normalize_digits(s):
    return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


class Delivery(StrictModel):
    name: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=30)
    address: str = Field(default="", max_length=1500)
    city: str = Field(default="", max_length=100)
    postal_code: str = Field(default="", max_length=20)
    notes: str = Field(default="", max_length=1000)

    @field_validator("phone", "postal_code")
    @classmethod
    def digits(cls, value):
        return re.sub(r"[\s\-]", "", normalize_digits(value))


class Draft(StrictModel):
    product_id: int | None = Field(default=None, ge=1)
    quantity: int | None = Field(default=None, ge=1, le=1000)
    specifications: dict[str, str] = Field(default_factory=dict)
    delivery: Delivery = Field(default_factory=Delivery)
    deadline: str | None = None
    delivery_confirmed: bool = False

    @field_validator("specifications")
    @classmethod
    def values(cls, value):
        if len(value) > 30 or any(len(k) > 50 or len(v) > 2000 for k, v in value.items()):
            raise ValueError("مشخصات بیش از اندازه طولانی است.")
        return value

    @field_validator("deadline")
    @classmethod
    def valid_date(cls, value):
        if value:
            date.fromisoformat(value)
        return value


class Extraction(StrictModel):
    intent: Literal["order", "correct", "confirm", "change", "handover", "repeat", "new", "other"] = "order"
    product_id: int | None = Field(default=None, ge=1)
    quantity: int | None = Field(default=None, ge=1, le=1000)
    specifications: dict[str, str] = Field(default_factory=dict)
    delivery: Delivery = Field(default_factory=Delivery)
    deadline: str | None = None
    uncertain_fields: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("specifications")
    @classmethod
    def values(cls, value):
        return Draft.values(value)

    @field_validator("deadline")
    @classmethod
    def valid_date(cls, value):
        return Draft.valid_date(value)


class ChatStart(StrictModel):
    name: str = Field(default="", max_length=200)


class ChatMessage(StrictModel):
    text: str = Field(min_length=1, max_length=10000)
    client_id: str = Field(min_length=8, max_length=100)


class OrderCreate(Draft):
    customer_id: int = Field(ge=1)


class VersionInput(StrictModel):
    version: int = Field(ge=1)


class StatusInput(VersionInput):
    status: Literal["awaiting_payment", "paid_awaiting_preparation", "in_preparation", "ready_to_ship", "canceled"]


class OrderEdit(VersionInput):
    deadline: str | None = None
    seller_notes: str | None = Field(default=None, max_length=5000)
    customer_status_message: str | None = Field(default=None, max_length=1500)

    @field_validator("deadline")
    @classmethod
    def valid_date(cls, value):
        return Draft.valid_date(value)


class ShipmentInput(VersionInput):
    tracking_number: str = Field(min_length=5, max_length=100)
    carrier: str = Field(default="پست", min_length=1, max_length=100)


class ChangeInput(StrictModel):
    product_id: int | None = Field(default=None, ge=1)
    quantity: int | None = Field(default=None, ge=1, le=1000)
    specifications: dict[str, str] | None = None
    delivery: Delivery | None = None
    deadline: str | None = None

    @field_validator("deadline")
    @classmethod
    def valid_date(cls, value):
        return Draft.valid_date(value)

    @field_validator("specifications")
    @classmethod
    def values(cls, value):
        return Draft.values(value) if value is not None else None


class ChangeDecision(StrictModel):
    reason: str = Field(default="", max_length=1500)


class PaymentSimulation(StrictModel):
    outcome: Literal["success", "failed", "canceled", "expired"]


class PaymentCallback(PaymentSimulation):
    event_id: str = Field(min_length=8, max_length=150)
    payment_token: str = Field(min_length=20, max_length=100)


class CustomerEdit(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(default="", max_length=30)
    address: str = Field(default="", max_length=1500)
    city: str = Field(default="", max_length=100)
    postal_code: str = Field(default="", max_length=20)
    notes: str = Field(default="", max_length=5000)


class SellerReply(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    resume_bot: bool = False
