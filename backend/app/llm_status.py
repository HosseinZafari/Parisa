"""وضعیت عملیاتی بدون ذخیرهٔ متن گفتگو، کلید یا بدنهٔ خطای ارائه‌دهنده."""

from datetime import datetime, timezone
from threading import Lock
from time import monotonic

from .config import settings

MESSAGES = {
    "not_checked": "تنظیمات آماده است؛ پاسخ معتبر مدل هنوز تأیید نشده است.",
    "mock": "پردازش محلی فعال است و درخواست خارجی فرستاده نمی‌شود.",
    "missing_key": "کلید سرویس زبانی در تنظیمات سرور ثبت نشده است.",
    "ready": "اتصال و خروجی ساختاریافتهٔ مدل تأیید شد.",
    "billing_required": "اعتبار یا وضعیت صورتحساب سرویس کافی نیست؛ حساب ارائه‌دهنده را بررسی کنید.",
    "unauthorized": "کلید سرویس معتبر نیست یا اجازهٔ دسترسی ندارد.",
    "rate_limited": "سرویس محدودیت تعداد درخواست اعلام کرده است؛ کمی بعد دوباره امتحان کنید.",
    "unavailable": "پاسخ سرویس دریافت نشد؛ اتصال شبکه یا وضعیت ارائه‌دهنده را بررسی کنید.",
    "invalid_response": "پاسخ مدل با قرارداد استخراج سفارش سازگار نیست.",
    "request_rejected": "ارائه‌دهنده درخواست یا مدل انتخابی را نپذیرفت؛ تنظیمات سرور را بررسی کنید.",
}
_lock = Lock()
_state = {"status": "not_checked", "checked_at": None, "http_status": None}
_retry_at = 0.0


def record(status, http_status=None):
    global _retry_at
    with _lock:
        _state.update(status=status, http_status=http_status, checked_at=datetime.now(timezone.utc).isoformat())
        _retry_at = (
            monotonic() + settings().llm_retry_cooldown_seconds
            if status in {"billing_required", "unauthorized", "rate_limited"}
            else 0.0
        )


def cooling_down():
    with _lock:
        return monotonic() < _retry_at


def connection_status():
    config = settings()
    with _lock:
        state = dict(_state)
        retry_after = max(0, int(_retry_at - monotonic()) + 1) if _retry_at else 0
    if config.llm_mode == "mock":
        state = {"status": "mock", "checked_at": None, "http_status": None}
        retry_after = 0
    elif not config.llm_api_key:
        state = {"status": "missing_key", "checked_at": None, "http_status": None}
        retry_after = 0
    return {
        **state,
        "message": MESSAGES[state["status"]],
        "retry_after_seconds": retry_after,
        "model": config.llm_model if config.llm_mode == "api" else None,
    }
