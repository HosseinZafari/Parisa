import hashlib
import hmac
import secrets
from collections import defaultdict, deque
from datetime import timedelta
from time import monotonic

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from .db import get_db
from .models import Seller, SellerSession, now


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def password_valid(password, stored):
    try:
        _, salt, expected = stored.split("$")
        actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except ValueError:
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db, seller):
    token = secrets.token_urlsafe(32)
    db.add(SellerSession(seller_id=seller.id, token_hash=token_hash(token), expires_at=now() + timedelta(hours=12)))
    return token


def require_seller(request: Request, db=Depends(get_db)):
    session = db.scalar(
        select(SellerSession).where(SellerSession.token_hash == token_hash(request.cookies.get("parisa_session", "")))
    )
    if not session or session.expires_at <= now():
        raise HTTPException(401, "برای ادامه وارد حساب فروشنده شوید.")
    return db.get(Seller, session.seller_id)


class Limiter:
    """محدودکنندهٔ فرایند واحد؛ استقرار این نمونه فقط با یک worker است."""

    def __init__(self):
        self.buckets = defaultdict(deque)

    def check(self, key, maximum, seconds=60):
        stamp = monotonic()
        bucket = self.buckets[key]
        while bucket and bucket[0] < stamp - seconds:
            bucket.popleft()
        if len(bucket) >= maximum:
            raise HTTPException(429, "تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید.")
        bucket.append(stamp)
        if len(self.buckets) > 10000:
            self.buckets = defaultdict(deque, {k: v for k, v in self.buckets.items() if v and v[-1] > stamp - 3600})


limiter = Limiter()
