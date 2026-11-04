from sqlalchemy import select

from app.models import Conversation, Order, Payment, Product, ProductRequirement
from app.schemas import CatalogQuestion, Extraction
from test_order_flow import message
from test_llm_connection import fake_service


def test_address_with_kooche_and_packaging_is_data_not_a_question(client):
    token = client.post('/api/chat/start', json={}).json()['token']
    message(client, token, 'دو عدد شمع آوا وانیل بزرگ معمولی')
    state = message(client, token, 'نام: سارا نمونه\nشهر: کرج\nتلفن: 09120000000\nآدرس: خیابان نمونه کوچه نسترن پلاک ۲۳ واحد ۵\nبسته بندی هم به صورت هدیه نظرم عوض شد')
    assert state['draft']['delivery']['name'] == 'سارا نمونه'
    assert state['draft']['delivery']['city'] == 'کرج'
    assert 'کوچه نسترن' in state['draft']['delivery']['address']
    assert state['draft']['specifications']['packaging'] == 'هدیه'


def pending_packaging(client, env):
    token = client.post("/api/chat/start", json={}).json()["token"]
    message(client, token, "دو عدد شمع آوا وانیل بزرگ")
    with env["sessions"]() as db:
        conv = db.scalar(select(Conversation).where(Conversation.token == token))
        conv.draft = {
            **conv.draft,
            "_uncertain": ["specifications.packaging"],
            "_asked": "specifications.packaging",
            "_ready": False,
        }
        db.commit()
    return token


def test_question_from_screenshot_lists_real_choices_and_preserves_order(client, env):
    token = pending_packaging(client, env)
    before = client.get("/api/chat/" + token).json()["draft"]
    state = message(client, token, "چه نوع بسته بندی هایی هستن ؟")
    reply = state["messages"][-1]["text"]
    assert "معمولی" in reply and "هدیه" in reply
    assert "۲۰,۰۰۰ تومان" in reply and "برای هر عدد" in reply
    assert state["draft"] == before and not state["ready_to_confirm"]
    assert state["suggested_replies"] == ["معمولی", "هدیه"]
    resolved = message(client, token, "هدیه")
    assert resolved["draft"]["specifications"]["packaging"] == "هدیه"
    assert "نام گیرنده" in resolved["messages"][-1]["text"]
    assert "مبهم" not in resolved["messages"][-1]["text"]


def test_api_misclassifies_question_as_old_uncertainty_but_customer_gets_options(client, env, monkeypatch):
    token = pending_packaging(client, env)
    fake_service(
        monkeypatch, content=Extraction(intent="other", uncertain_fields=["specifications.packaging"]).model_dump_json()
    )
    state = message(client, token, "چه نوع بسته‌بندی‌هایی دارید؟")
    assert "معمولی" in state["messages"][-1]["text"] and "هدیه" in state["messages"][-1]["text"]
    assert "این بخش مبهم است" not in state["messages"][-1]["text"]
    assert state["draft"]["quantity"] == 2 and state["draft"]["specifications"]["size"] == "بزرگ"
    assert not state["draft"]["specifications"].get("packaging")


def test_comparison_question_does_not_choose_either_value(client, env, monkeypatch):
    token = pending_packaging(client, env)
    # حتی اگر مدل از ذکر گزینه‌ها یک انتخاب حدس زده باشد، سؤال صرف سفارش را تغییر نمی‌دهد.
    fake_service(
        monkeypatch,
        content=Extraction(
            intent="order",
            specifications={"packaging": "هدیه"},
            questions=[CatalogQuestion(topic="details", field="specifications.packaging")],
        ).model_dump_json(),
    )
    state = message(client, token, "بسته بندی معمولی و هدیه چه فرقی دارن؟")
    assert not state["draft"]["specifications"].get("packaging")
    assert "توضیح بیشتری در کاتالوگ ثبت نشده" in state["messages"][-1]["text"]
    assert "جعبه" not in state["messages"][-1]["text"]  # جزئیات ظاهریِ ثبت‌نشده ساخته نمی‌شوند.


def test_misplaced_llm_question_metadata_does_not_trigger_fallback_or_change_draft(client, env, monkeypatch):
    token = pending_packaging(client, env)
    before = client.get("/api/chat/" + token).json()["draft"]
    fake_service(
        monkeypatch,
        content=Extraction(
            intent="question",
            uncertain_fields=["questions.topic=seller", "questions.field=seller.working_hours"],
        ).model_dump_json(),
    )
    state = message(client, token, "ساعت کاری فروشنده چه ساعتیه؟")
    assert "ساعت پاسخ‌گویی هنوز توسط فروشنده ثبت نشده" in state["messages"][-1]["text"]
    assert "سرویس زبانی در دسترس نیست" not in state["messages"][-1]["text"]
    assert state["draft"] == before


def test_mixed_selection_and_question_keeps_both(client, env):
    token = client.post("/api/chat/start", json={}).json()["token"]
    state = message(client, token, "دو عدد شمع آوا بزرگ وانیل می‌خواهم؛ چه بسته‌بندی‌هایی دارید؟")
    assert state["draft"]["quantity"] == 2 and state["draft"]["specifications"]["size"] == "بزرگ"
    assert "هدیه" in state["messages"][-1]["text"]
    assert state["suggested_replies"] == ["معمولی", "هدیه"]


def test_complete_summary_questions_do_not_confirm_or_mutate(client, env):
    token = client.post("/api/chat/start", json={}).json()["token"]
    message(client, token, "دو عدد شمع آوا وانیل کوچک هدیه")
    before = message(
        client, token, "نام: سارا؛ تلفن: 09120000000؛ شهر: تهران؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی: 1111111111"
    )
    assert before["ready_to_confirm"]
    answered = message(client, token, "قیمتش چنده؟")
    assert answered["draft"] == before["draft"] and answered["ready_to_confirm"]
    assert answered["order"] is None and answered["payment"] is None
    assert "۲۷۰,۰۰۰ تومان" in answered["messages"][-1]["text"]
    with env["sessions"]() as db:
        assert not db.scalar(select(Order)) and not db.scalar(select(Payment))


def test_new_catalog_option_and_price_appear_without_prompt_changes(client, env):
    token = pending_packaging(client, env)
    with env["sessions"]() as db:
        requirement = db.scalar(select(ProductRequirement).where(ProductRequirement.key == "packaging"))
        requirement.allowed_values = ["ساده", "ویژه"]
        requirement.price_adjustments = {"ویژه": 47000}
        db.commit()
    state = message(client, token, "بسته بندی هاتون چیا هستن؟")
    assert "ویژه" in state["messages"][-1]["text"] and "۴۷,۰۰۰ تومان" in state["messages"][-1]["text"]
    assert state["suggested_replies"] == ["ساده", "ویژه"]


def test_question_can_explain_delivery_without_losing_previous_fields(client, env):
    token = client.post("/api/chat/start", json={}).json()["token"]
    before = message(client, token, "دو عدد شمع آوا وانیل کوچک معمولی")
    state = message(client, token, "نام گیرنده یعنی چی؟")
    assert "کسی که بسته را تحویل می‌گیرد" in state["messages"][-1]["text"]
    assert state["draft"] == before["draft"]


def test_help_before_product_selection_lists_catalog_and_explains_delivery(client):
    token = client.post("/api/chat/start", json={}).json()["token"]
    listed = message(client, token, "چه محصولاتی دارید؟")
    assert "شمع" in listed["messages"][-1]["text"] and "قیمت پایه" in listed["messages"][-1]["text"]
    assert not listed["draft"]["product_id"] and not listed["order"]
    helped = message(client, token, "نام گیرنده یعنی چی؟")
    assert "کسی که بسته را تحویل می‌گیرد" in helped["messages"][-1]["text"]
    assert not helped["draft"]["delivery"]["name"]


def test_product_help_and_availability_use_database_without_selecting_order(client, env):
    with env["sessions"]() as db:
        product = db.get(Product, 1)
        product.description = "توضیح ثبت‌شدهٔ آزمایشی برای شمع."
        product.inventory = 7
        db.commit()
    token = client.post("/api/chat/start", json={}).json()["token"]
    described = message(client, token, "درباره شمع آوا توضیح بده")
    assert "توضیح ثبت‌شدهٔ آزمایشی برای شمع" in described["messages"][-1]["text"]
    assert not described["draft"]["product_id"] and not described["order"]
    available = message(client, token, "شمع آوا موجوده؟")
    assert "7 عدد قابل سفارش" in available["messages"][-1]["text"]
    assert not available["draft"]["product_id"]


def test_question_about_other_product_does_not_switch_order(client, env, monkeypatch):
    token = pending_packaging(client, env)
    with env["sessions"]() as db:
        other = Product(
            name="صابون", aliases=["صابون"], price=70000, shipping_cost=10000, inventory=10, preparation_days=1
        )
        db.add(other)
        db.commit()
        other_id = other.id
    fake_service(
        monkeypatch,
        content=Extraction(
            intent="question", product_id=other_id, questions=[CatalogQuestion(topic="price")]
        ).model_dump_json(),
    )
    state = message(client, token, "قیمت صابون چنده؟")
    assert "۷۰,۰۰۰ تومان" in state["messages"][-1]["text"] and state["draft"]["product_id"] == 1


def test_price_question_after_confirmation_uses_original_order_contract(seller, env):
    token = seller.post("/api/chat/start", json={}).json()["token"]
    message(seller, token, "دو عدد شمع آوا وانیل کوچک هدیه")
    message(seller, token, "نام: سارا؛ تلفن: 09120000000؛ شهر: تهران؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی: 1111111111")
    confirmed = message(seller, token, "تأیید سفارش")
    original_total = confirmed["order"]["total"]
    with env["sessions"]() as db:
        db.get(Product, 1).price = 999000
        db.commit()
    state = message(seller, token, "قیمت سفارشم چنده؟")
    assert "۲۷۰,۰۰۰ تومان" in state["messages"][-1]["text"]
    assert state["order"]["total"] == original_total and not state["order"]["changes"]


def test_shipping_question_after_confirmation_preserves_agreed_shipping(seller, env):
    token = seller.post("/api/chat/start", json={}).json()["token"]
    message(seller, token, "دو عدد شمع آوا وانیل کوچک هدیه")
    message(seller, token, "نام: سارا؛ تلفن: 09120000000؛ شهر: تهران؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی: 1111111111")
    confirmed = message(seller, token, "تأیید سفارش")
    with env["sessions"]() as db:
        db.get(Product, 1).shipping_cost = 999000
        db.commit()
    state = message(seller, token, "هزینه ارسال چقدره؟")
    assert "۳۰,۰۰۰ تومان" in state["messages"][-1]["text"]
    assert state["order"]["total"] == confirmed["order"]["total"]
    assert not state["order"]["changes"]
