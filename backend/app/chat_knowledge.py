"""پاسخ‌های محاوره‌ای از واقعیت‌های کاتالوگ؛ انتخاب و مبلغ را مشتری یا مدل جعل نمی‌کند."""

import re

from .schemas import CatalogQuestion, normalize_digits


def normalize_text(text):
    return normalize_digits(text).replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").strip().lower()


def money(amount):
    return f"{amount:,}".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")) + " تومان"


FIELD_HELP = {
    "delivery.name": (
        "نام گیرنده",
        "نام گیرنده را بنویس؛ یعنی اسم و نام خانوادگی کسی که بسته را تحویل می‌گیرد. مثلاً «سارا احمدی».",
    ),
    "delivery.phone": ("شمارهٔ همراه", "شمارهٔ موبایل گیرنده را بفرست؛ باید ۱۱ رقم باشد و با ۰۹ شروع شود."),
    "delivery.address": ("نشانی کامل", "نشانی گیرنده را شامل خیابان، کوچه، پلاک و واحد بنویس تا بسته قابل ارسال باشد."),
    "delivery.city": ("شهر", "بسته به کدام شهر فرستاده شود؟ نام شهر را بنویس."),
    "delivery.postal_code": ("کد پستی", "کد پستی ۱۰ رقمی نشانی گیرنده را بفرست؛ بدون فاصله یا خط تیره."),
    "delivery.notes": ("توضیحات ارسال", "اگر برای تحویل بسته نکته‌ای هست، مثل زمان مناسب تماس، اینجا بنویس."),
    "quantity": ("تعداد", "چند عدد می‌خواهی؟ مثلاً بنویس «۲ عدد»."),
    "deadline": (
        "موعد ارسال",
        "تاریخ موردنظرت را دقیق بنویس؛ مثلاً با قالب سال-ماه-روز میلادی. زمان قابل انجام در خلاصه مشخص می‌شود.",
    ),
}

SELLER_FIELDS = {
    "store_name": "نام فروشگاه",
    "about": "دربارهٔ فروشنده",
    "contact": "راه ارتباط با فروشنده",
    "working_hours": "ساعت پاسخ‌گویی",
    "shipping_policy": "شرایط ارسال",
    "return_policy": "شرایط مرجوعی",
    "custom_orders": "سفارش اختصاصی",
    "ordering_help": "راهنمای خرید",
}


def detect_questions(text, product, asked=None):
    """برای پرسش‌های رایج در حالت محلی یا خروجی ناقصِ طبقه‌بندی مدل."""
    plain = normalize_text(text)
    if not (
        any(c in plain for c in ["?", "؟"])
        or re.search(r"(?:^|\s)(?:چی|چیه|چیا|چه)(?:\s|[؟?]|$)", plain)
        or any(
            w in plain
            for w in ["چطور", "کدوم", "یعنی", "بگو", "توضیح", "فرق", "چقدر", "چنده", "موجوده", "دارید"]
        )
    ):
        return []
    questions = []
    for field, keywords in {
        "working_hours": ["ساعت کاری", "ساعت پاسخ", "کی جواب", "چه ساعتی"],
        "contact": ["راه ارتباط", "شماره فروشنده", "تماس با فروشنده"],
        "return_policy": ["مرجوع", "پس بدم", "پس بدهم", "برگردون", "بازگشت کالا"],
        "shipping_policy": ["قوانین ارسال", "شرایط ارسال"],
        "custom_orders": ["سفارش اختصاصی", "سفارشی قبول", "سفارشی هم", "سفارشی می ساز"],
        "ordering_help": ["چطور سفارش", "چجوری سفارش", "چطور خرید", "روش خرید"],
        "about": ["درباره فروشنده", "فروشنده کیه", "فروشگاهتون", "خودتون"],
    }.items():
        if any(keyword in plain for keyword in keywords):
            questions.append(CatalogQuestion(topic="seller", field="seller." + field))
    requirements = product.get("requirements", []) if product else []
    for requirement in requirements:
        aliases = [normalize_text(requirement["label"])]
        aliases += {
            "packaging": ["بسته بند", "بسته بندی", "کادوی"],
            "scent": ["رایحه", "بوی"],
            "size": ["اندازه", "سایز"],
        }.get(requirement["key"], [])
        aliases += [normalize_text(value) for value in requirement["allowed_values"]]
        if any(alias in plain for alias in aliases if alias):
            topic = "details" if any(w in plain for w in ["فرق", "یعنی", "شکل", "ظاهر"]) else "options"
            questions.append(CatalogQuestion(topic=topic, field="specifications." + requirement["key"]))
    if any(w in plain for w in ["ارسال", "پست", "تحویل"]) and not any(
        w in plain for w in ["کد پستی", "کدپستی", "آدرس", "نشانی"]
    ):
        questions.append(
            CatalogQuestion(
                topic="preparation"
                if any(w in plain for w in ["کی ", "روز", "زمان", "طول", "چقدر طول"])
                else "shipping"
            )
        )
    elif any(w in plain for w in ["قیمت", "چنده", "هزینه", "چقدر میشه", "چقدر می شه"]):
        questions.append(CatalogQuestion(topic="price"))
    for key, (label, _) in FIELD_HELP.items():
        if key.startswith("delivery.") and (
            normalize_text(label) in plain or (key.endswith("address") and "آدرس" in plain)
        ):
            questions.append(CatalogQuestion(topic="field_help", field=key))
    if any(w in plain for w in ["موجود", "هنوز دارید", "هنوز دارین"]):
        questions.append(CatalogQuestion(topic="availability"))
    if not questions and any(
        w in plain for w in ["محصول", "کالا", "درباره", "معرفی", "توضیح", "چی ساخته", "چیه"]
    ):
        questions.append(CatalogQuestion(topic="product"))
    if not questions and asked and any(w in plain for w in ["یعنی", "چی", "توضیح", "چه ", "کدوم"]):
        questions.append(CatalogQuestion(topic="field_help", field=asked))
    return questions[:5]


def is_question_only(text):
    plain = normalize_text(text)
    # «می‌خواهم بدانم» درخواست انتخاب کالا نیست.
    plain = re.sub(r"می\s*(?:خوام|خواهم)\s*(?:بدونم|بدانم)", "", plain)
    if re.search(r"(?:\d+|یک|دو|سه|چهار|پنج)\s*(?:عدد|تا)[^؟?؛،]*[؛،]", plain):
        return False
    return not any(
        w in plain
        for w in ["می خوام", "میخوام", "می خواهم", "باشه", "باشد", "بذار", "بگذار", "اصلاح", "تغییر بده", "اضافه کن"]
    )


def requirement_prompt(product, requirement, *, uncertain=False):
    label, options = requirement["label"], requirement["allowed_values"]
    prefix = f"انتخاب {label} هنوز مبهم است. " if uncertain else ""
    if options:
        lines = [f"{prefix}برای «{product['name']}»، {label} این گزینه‌ها را دارد:"]
        for value in options:
            extra = requirement["price_adjustments"].get(value, 0)
            detail = f"{money(extra)} اضافه برای هر عدد" if extra else "بدون افزایش قیمت"
            lines.append(f"• {value}: {detail}")
        lines.append(f"کدام را برای سفارشت می‌خواهی؟ می‌توانی فقط بنویسی «{options[0]}».")
        return "\n".join(lines)
    return f"{prefix}لطفاً {label} موردنظرت برای «{product['name']}» را بنویس. می‌توانی با «{label}: …» بفرستی."


def field_prompt(field, product, *, uncertain=False):
    if product and field.startswith("specifications."):
        requirement = next((r for r in product["requirements"] if r["key"] == field.split(".", 1)[1]), None)
        if requirement:
            return requirement_prompt(product, requirement, uncertain=uncertain)
    if field in FIELD_HELP:
        label, explanation = FIELD_HELP[field]
        return (f"{label} هنوز روشن نیست. " if uncertain else "") + explanation
    if field == "product_id":
        return "نام محصولی را که می‌خواهی سفارش بدهی مشخص کن تا گزینه‌های مربوط به همان را بگویم."
    return "منظورت کدام بخش سفارش است؟ نامش را بگو تا دقیق‌تر راهنمایی‌ات کنم."


def answer_questions(
    questions, product, draft, *, uncertain=(), asked=None, confirmed_price=None, seller_info=None, catalog=()
):
    answers, covered = [], set()
    if not questions:
        return "می‌خواهی دربارهٔ گزینه‌های محصول، قیمت یا ارسال بدانی؟ بگو کدام بخش را توضیح بدهم.", covered
    active = bool(product and product["id"] == draft.get("product_id"))
    for question in questions:
        if question.topic in {"seller", "policy"}:
            key = (question.field or "seller.about").removeprefix("seller.")
            label = SELLER_FIELDS.get(key, "اطلاعات فروشگاه")
            value = (seller_info or {}).get(key, "")
            answers.append(
                f"{label}: {value}"
                if value
                else f"{label} هنوز توسط فروشنده ثبت نشده است. اگر می‌خواهی مستقیم از او بپرسی، بنویس «با فروشنده کار دارم». "
            )
            covered.add("seller." + key)
            continue
        if question.topic == "field_help" and question.field in FIELD_HELP:
            answers.append(field_prompt(question.field, product))
            covered.add(question.field)
            continue
        if not product:
            if question.topic == "product" and catalog:
                answers.append(
                    "محصولات فعلی فروشگاه:\n"
                    + "\n".join(f"• {p['name']}: قیمت پایهٔ هر عدد {money(p['price'])}" for p in catalog)
                    + "\nدربارهٔ کدام محصول بیشتر بدانی؟ نامش را بگو."
                )
            else:
                answers.append("بگو دربارهٔ کدام محصول می‌پرسی تا گزینه‌ها و قیمت همان را توضیح بدهم.")
            continue
        field = question.field or asked
        if field and "." not in field:
            if field in {r["key"] for r in product["requirements"]}:
                field = "specifications." + field
            elif "delivery." + field in FIELD_HELP:
                field = "delivery." + field
        requirement = next((r for r in product["requirements"] if field == "specifications." + r["key"]), None)
        if question.topic in {"options", "details", "field_help"}:
            if requirement:
                reply = requirement_prompt(product, requirement)
                choice = draft.get("specifications", {}).get(requirement["key"]) if active else None
                if choice and field not in uncertain:
                    reply = reply.rsplit("\n", 1)[0] if requirement["allowed_values"] else reply
                    reply += f"\nانتخاب فعلی سفارشت «{choice}» است. اگر می‌خواهی عوض شود، مقدار تازه را بنویس."
                if question.topic == "details":
                    reply += "\nدربارهٔ ظاهر یا جزئیات این گزینه‌ها توضیح بیشتری در کاتالوگ ثبت نشده؛ برای توضیح دقیق‌تر می‌توانی فروشنده را بخواهی."
                covered.add(field)
            elif field:
                reply = field_prompt(field, product)
                covered.add(field)
            else:
                reply = "دربارهٔ کدام مشخصه می‌پرسی؟ " + "، ".join(r["label"] for r in product["requirements"])
        elif question.topic == "price":
            if question.field and requirement:
                reply = requirement_prompt(product, requirement)
                answers.append(reply)
                covered.add(field)
                continue
            if confirmed_price:
                reply = f"در سفارش ثبت‌شده‌ات، قیمت هر عدد {money(confirmed_price['unit_price'])} و هزینهٔ ارسال {money(confirmed_price['shipping_cost'])} است. مبلغ کل ثبت‌شده: {money(confirmed_price['total'])}."
                answers.append(reply)
                continue
            reply = f"قیمت پایهٔ هر عدد «{product['name']}» {money(product['price'])} است."
            if active:
                extra = sum(
                    r["price_adjustments"].get(draft.get("specifications", {}).get(r["key"]), 0)
                    for r in product["requirements"]
                )
                reply += f" با انتخاب‌های فعلی، هر عدد {money(product['price'] + extra)} می‌شود."
                if draft.get("quantity"):
                    reply += f" جمع {draft['quantity']} عدد با ارسال: {money((product['price'] + extra) * draft['quantity'] + product['shipping_cost'])}."
            reply += "\nگزینه‌های انتخاب‌نشده ممکن است مبلغ نهایی را تغییر بدهند؛ پیش از پرداخت خلاصهٔ کامل را می‌بینی."
        elif question.topic == "shipping":
            cost = confirmed_price["shipping_cost"] if confirmed_price else product["shipping_cost"]
            reply = f"هزینهٔ ارسال «{product['name']}» برای این سفارش {money(cost)} است."
            reply += " برای تحویل، نام گیرنده، همراه، شهر، نشانی کامل و کد پستی لازم است."
        elif question.topic == "preparation":
            reply = f"زمان آماده‌سازی «{product['name']}» طبق کاتالوگ {product['preparation_days']} روز است. تاریخ ارسال در خلاصهٔ سفارش مشخص می‌شود؛ زمان رسیدن بسته هنوز قطعی نیست."
        elif question.topic == "availability":
            reply = f"از «{product['name']}» در حال حاضر {product['inventory']} عدد قابل سفارش است. موجودی هنگام ثبت سفارش دوباره بررسی می‌شود."
        else:
            reply = (
                product["name"]
                + ": "
                + (product.get("description") or "هنوز توضیح بیشتری برای این محصول ثبت نشده است.")
            )
        if reply not in answers:
            answers.append(reply)
    return "\n\n".join(answers), covered
