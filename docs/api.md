# قرارداد رابط HTTP

نشانی پایهٔ محلی `http://127.0.0.1:8000/api` است. schema ورودی‌ها و عملیات در `/openapi.json` و رابط تعاملی در `/docs` ارائه می‌شوند. مبلغ‌ها عدد صحیح **تومان**، زمان‌ها ISO 8601 در UTC با پسوند Z و موعدها تاریخ `YYYY-MM-DD` بر مبنای منطقهٔ زمانی فروشگاه‌اند.

مسیرهای فروشنده از نشست HttpOnly استفاده می‌کنند. ابتدا login کنید و کوکی را در درخواست‌های بعدی نگه دارید. در مرورگر، درخواست‌ها باید از یکی از `ALLOWED_ORIGINS` باشند. همهٔ عملیات نوشتن سفارش/محصول/تغییر/گفتگو نیازمند هدر `Idempotency-Key` تصادفی ۸ تا ۱۵۰ نویسه‌اند. برای تکرار همان عملیات **همان کلید و بدنه** را بفرستید؛ برای عملیات تازه کلید تازه بسازید. login، logout، علامت خواندن و شبیه‌سازی پرداخت این هدر را لازم ندارند.

## مسیرها

مسیرها در جدول بدون پیشوند `/api` آمده‌اند. «خصوصی» یعنی نشست فروشنده لازم است؛ توکن‌های پیوند عمومی فقط به همان منبع محدودند.

| روش | مسیر | دسترسی / ورودی | خروجی |
| --- | --- | --- | --- |
| GET | `/health` | عمومی | status، database، version |
| POST | `/auth/login` | username، password | هویت فروشنده و کوکی نشست |
| GET | `/auth/me` | خصوصی | id، name، username |
| POST | `/auth/logout` | کوکی | ok |
| GET | `/catalog?q=...` | عمومی | محصولات فعال منطبق |
| GET | `/catalog/{id}` | عمومی | محصول و قرارداد الزامات |
| POST | `/chat/start` | name اختیاری | ChatState و توکن تصادفی گفتگو |
| GET | `/chat/{token}` | توکن گفتگو | ChatState تازه |
| POST | `/chat/{token}/messages` | text، client_id | ChatState؛ شناسهٔ پیام برای جلوگیری از تکرار |
| GET | `/dashboard` | خصوصی | آمار، صف سفارش‌ها، attention_queue و شمار گفتگوهای باز و فوری |
| GET | `/orders` | خصوصی | خلاصهٔ سفارش‌ها |
| POST | `/orders/quote` | خصوصی؛ Draft | مبلغ و موارد ناقص؛ بدون ثبت سفارش |
| POST | `/orders` | خصوصی؛ OrderCreate | سفارش تأییدشده با جزئیات |
| GET | `/orders/{id}` | خصوصی | جزئیات کامل سفارش |
| POST | `/orders/{id}/confirm` | خصوصی؛ version | پیوند پرداخت برای سفارش ثبت‌شده |
| POST | `/orders/{id}/payment-link` | خصوصی | پیوند پرداخت مانده |
| PATCH | `/orders/{id}` | خصوصی؛ version و فیلدهای ویرایش | جزئیات تازه |
| POST | `/orders/{id}/status` | خصوصی؛ version، status | جزئیات تازه؛ گذارهای مجاز فقط |
| POST | `/orders/{id}/ship` | خصوصی؛ version، tracking_number، carrier | سفارش ارسال‌شده یا خطای موانع |
| POST | `/orders/{id}/changes` | خصوصی؛ ChangeInput | درخواست با original و proposed |
| GET | `/changes/{id}/quote` | خصوصی | مبلغ و موعد پس از تغییر |
| POST | `/changes/{id}/review` | خصوصی؛ reason اختیاری | شروع بررسی و وضعیت awaiting_seller_approval |
| POST | `/changes/{id}/approve` | خصوصی؛ reason اختیاری | درخواست تأییدشده |
| POST | `/changes/{id}/reject` | خصوصی؛ reason اختیاری | درخواست ردشده |
| GET | `/payments/{token}` | توکن پرداخت | مبلغ، انقضا، وضعیت؛ بدون پرداخت خودکار |
| POST | `/payments/{token}/simulate` | outcome | نتیجهٔ شبیه‌سازی و duplicate |
| POST | `/payments/callback` | HMAC بدنه | نتیجهٔ تأیید؛ فقط امضای سرور |
| GET | `/tracking/{token}` | توکن پیگیری | خروجی امن و خواندنی یک سفارش |
| POST | `/orders/{id}/tracking/rotate` | خصوصی | پیوند تازه و ابطال قبلی |
| POST | `/orders/{id}/tracking/revoke` | خصوصی | tracking_url=null |
| GET / POST | `/products` | خصوصی؛ ورودی ایجاد ProductInput | فهرست / محصول |
| PUT | `/products/{id}` | خصوصی؛ ProductInput کامل | محصول و الزامات تازه |
| GET | `/customers` | خصوصی | مشتریان، شمار سفارش و مبلغ خرید |
| GET | `/customers/{id}` | خصوصی | مشتری و سفارش‌های قبلی |
| PATCH | `/customers/{id}` | خصوصی؛ CustomerEdit | اطلاعات و یادداشت مشتری |
| GET | `/notifications` | خصوصی | حداکثر ۲۰۰ اعلان تازه؛ order_id یا conversation_id و priority |
| POST | `/notifications/read-all` | خصوصی | ok |
| POST | `/notifications/{id}/read` | خصوصی | اعلان خوانده‌شده |
| GET | `/conversations` | خصوصی | حداکثر ۱۰۰ گفتگو؛ فوری‌های باز، سایر بازها و سپس گفتگوهای اخیر |
| GET | `/conversations/{id}` | خصوصی | پیام‌های مشتری، دستیار و فروشنده به ترتیب شناسه؛ وضعیت تحویل و رسیدگی |
| POST | `/conversations/{id}/reply` | خصوصی؛ text، resume_bot | پاسخ ذخیره‌شده و ارسال در صورت مجازبودن |
| POST | `/conversations/{id}/attention` | خصوصی؛ action و resume_bot اختیاری | جزئیات گفتگو پس از resolve، reopen یا take_over |
| GET | `/settings` | خصوصی | حالت سرویس‌ها، سقف‌ها و seller_profile؛ بدون راز |
| PUT | `/seller/profile` | خصوصی؛ SellerProfile کامل | اطلاعات عمومی تأییدشدهٔ فروشگاه برای پاسخ به مشتری |
| POST | `/llm/check` | خصوصی؛ حداکثر سه بار در دقیقه | آزمون صریح مدل با دادهٔ ساختگی و وضعیت امن اتصال |
| GET | `/instagram/webhook` | query استاندارد متا | challenge یا ۴۰۳ |
| POST | `/instagram/webhook` | X-Hub-Signature-256 | شمار رویدادهای پذیرفته‌شده |

مشتری تغییر سفارش را در پیام گفتگوی خودش درخواست می‌کند؛ API تغییر سفارش با شناسهٔ عددی عمومی نیست. ارسال خروجی اینستاگرام از مسیر reply خصوصی و صندوق خروجی انجام می‌شود؛ توکن اینستاگرام به مرورگر داده نمی‌شود.

## شکل داده‌ها

`Draft`: `product_id`، `quantity`، `specifications` (نگاشت کلیدهای کاتالوگ به رشته)، `delivery`، `deadline` اختیاری و `delivery_confirmed`. برای ثبت مستقیم سفارش، `customer_id` نیز لازم است. فیلدهای delivery عبارت‌اند از `name`، `phone`، `address`، `city`، `postal_code` و `notes`. نام، شمارهٔ معتبر ایرانی، شهر، نشانی حداقل ۱۰ نویسه و کد پستی ۱۰ رقمی الزامی هستند.

`ChatState`: `token`، `messages`، `draft`، `summary`، `ready_to_confirm`، `suggested_replies`، `order`، `payment`، `tracking_url` و `handover`. پیشنهادهای پاسخ از گزینه‌های واقعی آخرین مشخصهٔ پرسیده‌شده می‌آیند. خلاصه حاوی محصول، تعداد، مشخصات، نشانی، قیمت واحد، جمع، ارسال، کل، موعد و `missing` است. پیش از تأیید order برابر null است.

`SellerProfile`: `store_name`، `about`، `contact`، `working_hours`، `shipping_policy`، `return_policy`، `custom_orders` و `ordering_help`. این اطلاعات برای مشتری قابل استفاده است؛ کلید سرویس و یادداشت خصوصی در آن قرار ندهید. مقدار خالی یعنی اطلاعات ثبت نشده؛ سیستم برای آن ساعت کاری یا سیاست فروش نمی‌سازد.

وضعیت رسیدگی گفتگو از وضعیت سفارش جداست: `attention_status` یکی از `none/open/resolved`، `attention_priority` یکی از `normal/urgent`، به همراه `handover_reason` و زمان و مسئول آخرین رسیدگی. `resolve` درخواست را می‌بندد؛ فقط با `resume_bot=true` پاسخ خودکار فعال می‌شود. `reopen` و `take_over` درخواست را باز و دستیار را متوقف می‌کنند. خواندن اعلان به‌تنهایی درخواست رسیدگی را نمی‌بندد. هر چرخهٔ رسیدگی و ارتقای آن به فوری، اعلان یکتای مرتبط با گفتگو دارد.

`OrderDetail`: خلاصهٔ سفارش به همراه `version`، `delivery`، `specifications`، `requirement_schema`، `payments`، `changes`، `messages`، `history`، `notifications`، یادداشت خصوصی، پیام مشتری و `shipping_blocks`. تغییر بعدی باید version همین پاسخ را بفرستد. `allowed_statuses` گذارهای انتخابی مجاز را می‌دهد؛ تأیید پرداخت و ارسال مسیر اختصاصی دارند.

`ProductInput`: نام، توضیح، دسته، aliases، price، inventory، shipping_cost، preparation_days، enabled، color و requirements. برای ویرایش، مقدار `revision` پاسخ خواندن محصول را نیز بفرستید؛ اگر موجودی یا محصول پس از خواندن تغییر کرده باشد، خطای ۴۰۹ از بازنویسی دادهٔ تازه جلوگیری می‌کند. هر الزام key لاتین یکتا، label فارسی، required، allowed_values و price_adjustments دارد. افزایش قیمت‌ها غیرمنفی و مربوط به گزینه‌های مجازند. برای پاسخ آزاد، allowed_values را خالی بگذارید.

`ChangeInput`: یک یا چند مورد از product_id، quantity، specifications، delivery و deadline. مقدار قبلی از سفارش اصلی خوانده می‌شود؛ کلاینت نمی‌تواند original یا قیمت را تعیین کند. پیشنهاد جدید در original/proposed ذخیره می‌شود. resolved_at و responsible_user فقط هنگام تصمیم سرور ثبت می‌شوند.

## نمونهٔ درخواست با نشست و تکرار امن

```python
import uuid
import httpx

with httpx.Client(base_url="http://127.0.0.1:8000/api") as client:
    client.post("/auth/login", json={"username": "parisa", "password": "parisa-demo-1405"}).raise_for_status()
    order = client.get("/orders/1").json()
    operation_key = str(uuid.uuid4())
    response = client.patch(
        "/orders/1",
        headers={"Idempotency-Key": operation_key},
        json={"version": order["version"], "seller_notes": "بسته‌بندی را دوباره بررسی کنم."},
    )
    response.raise_for_status()
```

آزمون callback فقط در بک‌اند: JSON شامل `event_id`، `payment_token` و outcome از مجموعهٔ `success`، `failed`، `canceled`، `expired` است. چکیدهٔ `HMAC-SHA256(PAYMENT_SECRET, raw_body)` به صورت hex در `X-Payment-Signature` فرستاده می‌شود. بدنه پس از امضا نباید دوباره قالب‌بندی شود. هیچ مبلغ ورودی قبول نمی‌شود.

خطاها `{ "detail": "پیام فارسی" }` هستند. ۴۰۱ نشست نامعتبر، ۴۰۳ مبدأ یا امضای نامعتبر، ۴۰۴ منبع/پیوند ناموجود، ۴۰۹ تضاد نسخه یا عملیات نامجاز، ۴۲۲ ورودی نامعتبر، ۴۲۹ سقف درخواست و ۴۱۳ بدنهٔ بزرگ را نشان می‌دهد. کلاینت در خطای شبکه باید همان کلید عملیات را حفظ کند و وضعیت را از سرور بخواند.
