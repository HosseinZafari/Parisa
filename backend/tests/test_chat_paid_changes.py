from sqlalchemy import select

from app.models import ChangeRequest, Conversation
from conftest import key
from test_order_flow import message


def paid_chat(client):
    token = client.post('/api/chat/start', json={}).json()['token']
    message(client, token, 'دو عدد شمع آوا وانیل بزرگ معمولی')
    message(client, token, 'نام: سارا؛ تلفن: 09120000000؛ شهر: تهران؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی: 1111111111')
    state = message(client, token, 'تأیید سفارش')
    payment = state['payment']['url'].split('/')[-1]
    assert client.post(f'/api/payments/{payment}/simulate', json={'outcome': 'success'}).status_code == 200
    return token, state['order']['id']


def test_paid_customer_change_clarification_same_value_and_dashboard(seller, env):
    token, order_id = paid_chat(seller)
    generic = message(seller, token, 'میخوام یه مشخصه ای رو برام تغییر بدی')
    assert 'کدام بخش سفارش' in generic['messages'][-1]['text']
    selected = message(seller, token, 'اندازه')
    assert 'سفارش فعلی «بزرگ»' in selected['messages'][-1]['text']
    assert selected['suggested_replies'] == ['کوچک', 'بزرگ']
    same = message(seller, token, 'می‌خوام اندازه‌اش بزرگ بشه')
    assert 'همان مقدار فعلی' in same['messages'][-1]['text']
    with env['sessions']() as db:
        assert not db.scalar(select(ChangeRequest))
    state = message(seller, token, 'کوچیک')
    assert 'منتظر تأیید فروشنده' in state['messages'][-1]['text']
    order = seller.get(f'/api/orders/{order_id}').json()
    assert order['specifications']['size'] == 'بزرگ'
    change = order['changes'][0]
    assert change['original']['specifications']['size'] == 'بزرگ'
    assert change['proposed']['specifications']['size'] == 'کوچک'
    dashboard = seller.get('/api/dashboard').json()
    assert dashboard['pending_changes'] == 1
    assert any(o['id'] == order_id and o['pending_change'] for o in dashboard['queue'])
    assert any(n['order_id'] == order_id and n['kind'] == 'change_requested' for n in seller.get('/api/notifications').json())
    assert 'درخواست تغییر' in ' '.join(order['shipping_blocks'])
    with env['sessions']() as db:
        assert '_change_asked' not in db.scalar(select(Conversation).where(Conversation.token == token)).draft
    assert seller.post(f"/api/changes/{change['id']}/approve", headers=key(), json={}).status_code == 200
    assert seller.get(f'/api/orders/{order_id}').json()['specifications']['size'] == 'کوچک'


def test_explicit_paid_chat_change_without_clarification(seller):
    token, order_id = paid_chat(seller)
    state = message(seller, token, 'میخوام اندازه اش کوچک بشه')
    assert state['order']['status'] == 'change_requested'
    order = seller.get(f'/api/orders/{order_id}').json()
    assert order['specifications']['size'] == 'بزرگ'
    assert order['changes'][0]['proposed']['specifications']['size'] == 'کوچک'
