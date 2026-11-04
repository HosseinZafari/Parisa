from datetime import timedelta
import secrets

from sqlalchemy import select

from .auth import password_hash
from .config import settings
from .domain import create_change, create_order, payment_link, confirm_payment, event, today
from .models import Conversation, Customer, Message, Order, Product, ProductRequirement, Seller, now


def ensure_seller(db):
    if not db.scalar(select(Seller)):
        db.add(
            Seller(
                username=settings().seller_username,
                name="پریسا",
                password_hash=password_hash(settings().seller_password),
            )
        )
        db.flush()


def seed(db):
    ensure_seller(db)
    if db.scalar(select(Product)):
        return
    catalog = [
        (
            "شمع دست‌ساز آوا",
            "شمع",
            ["شمع", "آوا", "شمع آوا"],
            185000,
            24,
            45000,
            2,
            "sand",
            "شمع گیاهی با رایحه‌های ملایم، برای لحظه‌های آرام خانه.",
            [
                ("scent", "رایحه", True, ["وانیل", "اسطوخودوس", "دارچین"], {}),
                ("size", "اندازه", True, ["کوچک", "بزرگ"], {"بزرگ": 95000}),
                ("packaging", "بسته‌بندی", True, ["معمولی", "هدیه"], {"هدیه": 35000}),
            ],
        ),
        (
            "صابون طبیعی باران",
            "صابون",
            ["صابون", "باران"],
            95000,
            40,
            40000,
            1,
            "sage",
            "صابون دست‌ساز با بسته‌بندی ساده و قابل بازیافت.",
            [
                ("type", "نوع صابون", True, ["زیتون", "عسل", "زغال"], {}),
                ("packaging", "بسته‌بندی", True, ["معمولی", "هدیه"], {"هدیه": 20000}),
            ],
        ),
        (
            "پیراهن لینن رها",
            "پوشاک",
            ["پیراهن", "لباس", "لینن", "رها"],
            890000,
            15,
            65000,
            5,
            "rose",
            "پیراهن سفارشی با پارچهٔ لینن؛ دوخته‌شده با اندازه‌های شما.",
            [
                ("color", "رنگ", True, ["کرم", "سبز", "مشکی"], {}),
                ("size", "سایز", True, ["کوچک", "متوسط", "بزرگ"], {}),
                ("measurements", "اندازه‌های بدن", True, [], {}),
                ("fabric", "پارچه", True, ["لینن"], {}),
                ("model", "مدل", True, ["ساده", "چین‌دار"], {"چین‌دار": 120000}),
            ],
        ),
        (
            "پرترهٔ سفارشی مهر",
            "هنر",
            ["پرتره", "نقاشی", "تابلو", "مهر"],
            1250000,
            8,
            85000,
            7,
            "lilac",
            "پرترهٔ شخصی از تصویر مرجع شما؛ تصویر را با پیوند قابل دسترسی معرفی کنید.",
            [
                ("reference", "پیوند تصویر مرجع", True, [], {}),
                ("dimensions", "ابعاد", True, ["۲۰×۳۰", "۳۰×۴۰"], {"۳۰×۴۰": 350000}),
                ("frame", "قاب", True, ["بدون قاب", "چوبی"], {"چوبی": 250000}),
                ("background", "رنگ پس‌زمینه", True, [], {}),
            ],
        ),
        (
            "کوکی خانگی نبات",
            "خوراکی",
            ["کوکی", "شیرینی", "نبات"],
            35000,
            100,
            55000,
            2,
            "sand",
            "کوکی تازهٔ خانگی؛ تاریخ تحویل را با فروشنده هماهنگ کنید.",
            [
                ("flavor", "طعم", True, ["شکلاتی", "وانیلی", "گردویی"], {"گردویی": 10000}),
                ("delivery_date", "تاریخ تحویل", True, [], {}),
                ("packaging", "بسته‌بندی", True, ["معمولی", "هدیه"], {"هدیه": 5000}),
            ],
        ),
    ]
    products = []
    for name, category, aliases, price, inventory, shipping, prep, color, desc, requirements in catalog:
        product = Product(
            name=name,
            category=category,
            aliases=aliases,
            price=price,
            inventory=inventory,
            shipping_cost=shipping,
            preparation_days=prep,
            color=color,
            description=desc,
        )
        db.add(product)
        db.flush()
        for key, label, required, allowed, adjustments in requirements:
            db.add(
                ProductRequirement(
                    product_id=product.id,
                    key=key,
                    label=label,
                    required=required,
                    allowed_values=allowed,
                    price_adjustments=adjustments,
                )
            )
        products.append(product)
    db.flush()
    names = [
        ("سارا احمدی", "sara.ahmadi"),
        ("نگار محمدی", "negar.art"),
        ("مریم رضایی", "maryam.rz"),
        ("الهام کریمی", "elham.k"),
        ("نازنین حسینی", "nazanin.h"),
        ("یلدا صادقی", "yalda.sd"),
        ("مهسا نوری", "mahsa.n"),
        ("آیدا رستمی", "aida.rostami"),
    ]
    specs = [
        {"scent": "وانیل", "size": "بزرگ", "packaging": "هدیه"},
        {"type": "زیتون", "packaging": "معمولی"},
        {"color": "کرم", "size": "متوسط", "measurements": "دور سینه ۹۰، قد ۱۰۰", "fabric": "لینن", "model": "ساده"},
        {"reference": "https://example.com/reference.jpg", "dimensions": "۲۰×۳۰", "frame": "چوبی", "background": "کرم"},
        {"flavor": "شکلاتی", "delivery_date": (today() + timedelta(days=3)).isoformat(), "packaging": "هدیه"},
    ]
    statuses = [
        "in_preparation",
        "paid_awaiting_preparation",
        "ready_to_ship",
        "paid_awaiting_preparation",
        "awaiting_payment",
        "in_preparation",
        "shipped",
        "awaiting_payment",
        "in_preparation",
        "ready_to_ship",
        "paid_awaiting_preparation",
        "canceled",
    ]
    for i, status in enumerate(statuses):
        if i < len(names):
            name, username = names[i]
            customer = Customer(
                name=name,
                username=username,
                phone=f"091200000{i:02d}",
                city="تهران",
                address="نشانی ساختگی برای آزمایش، خیابان نمونه، پلاک ۱۲",
                postal_code="1111111111",
                last_interaction_at=now() - timedelta(hours=i * 3),
            )
            db.add(customer)
            db.flush()
        else:
            customer = db.get(Customer, i - len(names) + 1)
        product = products[i % len(products)]
        draft = {
            "product_id": product.id,
            "quantity": (i % 3) + 1,
            "specifications": specs[i % 5],
            "delivery": {k: getattr(customer, k) for k in ["name", "phone", "address", "city", "postal_code"]},
        }
        order = create_order(db, customer, draft)
        order.created_at = now() - timedelta(days=6 - i % 7, hours=i)
        if status not in {"awaiting_payment", "canceled"}:
            p = payment_link(db, order)
            confirm_payment(db, p, "success")
            p.confirmed_at = order.paid_at = order.created_at + timedelta(minutes=10)
        order.status = status
        order.deadline = (today() + timedelta(days=[-2, 0, 0, 2, 3, 1, -1, 4, 2, 0, 3, 1][i])).isoformat()
        if status == "shipped":
            order.tracking_number = "123456789012345678901234"
            order.shipped_at = now() - timedelta(days=1)
        if status == "canceled":
            product.inventory += draft["quantity"]
            order.canceled_at = now()
        conv = Conversation(
            customer_id=customer.id, channel="local", token=secrets.token_urlsafe(32), order_id=order.id, draft={}
        )
        db.add(conv)
        db.flush()
        db.add_all(
            [
                Message(
                    conversation_id=conv.id,
                    order_id=order.id,
                    role="customer",
                    text=f"سلام، {draft['quantity']} عدد {product.name} می‌خواهم.",
                ),
                Message(
                    conversation_id=conv.id,
                    order_id=order.id,
                    role="assistant",
                    text="مشخصات و نشانی دریافت شد. لطفاً خلاصهٔ سفارش را تأیید کنید.",
                ),
                Message(conversation_id=conv.id, order_id=order.id, role="customer", text="تأیید سفارش"),
            ]
        )
        event(db, order, "demo", "دادهٔ نمایشی؛ تمام نام‌ها و نشانی‌ها ساختگی هستند.")
    db.flush()
    create_change(db, db.get(Order, 4), {"specifications": {"frame": "بدون قاب"}})
    db.commit()
