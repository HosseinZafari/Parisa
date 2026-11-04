<script>
  import { modal } from '../lib/modal';
  import { onMount } from 'svelte';
  import { api, fa, money, date, navigate, copy, statuses, changeLabels, paymentLabels } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  import Status from '../components/Status.svelte';
  export let id, notify;
  let order,
    error = '',
    busy = false,
    note = '',
    deadline = '',
    statusMessage = '',
    tracking = '',
    carrier = 'پست',
    selectedStatus = '',
    reason = '',
    tab = 'details',
    quotes = {};
  let editingChange = false,
    changeQuantity = 1;
  async function load() {
    try {
      order = await api('/orders/' + id);
      note = order.seller_notes;
      deadline = order.deadline || '';
      statusMessage = order.customer_status_message;
      tracking = order.tracking_number;
      carrier = order.carrier;
      changeQuantity = order.quantity;
      selectedStatus = '';
      error = '';
    } catch (e) {
      error = e.message;
    }
  }
  onMount(load);
  async function act(path, body, success, method = 'POST') {
    busy = true;
    try {
      await api(path, { method, body });
      notify(success);
      await load();
    } catch (e) {
      notify(e.message, true);
      if (e.message.includes('تغییر کرده')) await load();
    } finally {
      busy = false;
    }
  }
  async function save(e) {
    e.preventDefault();
    await act(
      '/orders/' + id,
      {
        version: order.version,
        ...(!['shipped', 'canceled'].includes(order.status) ? { deadline: deadline || null } : {}),
        seller_notes: note,
        customer_status_message: statusMessage,
      },
      'تغییرات ذخیره شد.',
      'PATCH',
    );
  }
  async function decide(change, decision) {
    if (decision === 'approve' && !quotes[change.id]) {
      try {
        await api('/changes/' + change.id + '/review', { method: 'POST', body: {} });
        quotes = { ...quotes, [change.id]: await api('/changes/' + change.id + '/quote') };
        await load();
      } catch (e) {
        notify(e.message, true);
      }
      return;
    }
    await act(
      '/changes/' + change.id + '/' + decision,
      { reason },
      decision === 'approve' ? 'تغییر تأیید شد.' : 'تغییر رد شد.',
    );
    reason = '';
  }
  async function paylink() {
    busy = true;
    try {
      const p = await api('/orders/' + id + '/payment-link', { method: 'POST' });
      notify('پیوند آزمایشی آماده شد.');
      await load();
      navigate('/pay/' + p.url.split('/').at(-1));
    } catch (e) {
      notify(e.message, true);
    } finally {
      busy = false;
    }
  }
  async function copyTracking() {
    try {
      await copy(order.tracking_url);
      notify('پیوند پیگیری کپی شد.');
    } catch {
      notify('امکان کپی خودکار نیست؛ پیوند را از صفحهٔ پیگیری بردارید.', true);
    }
  }
  async function sendChange(e) {
    e.preventDefault();
    await act('/orders/' + id + '/changes', { quantity: +changeQuantity }, 'درخواست تغییر ثبت شد.');
    editingChange = false;
  }
  function valueLabel(key, value) {
    if (key === 'delivery')
      return Object.values(value || {})
        .filter(Boolean)
        .join('، ');
    if (key === 'specifications')
      return Object.entries(value || {})
        .map(([k, v]) => (order.requirement_schema.find((r) => r.key === k)?.label || k) + ': ' + v)
        .join(' · ');
    if (key === 'product_id') return 'شناسهٔ محصول ' + fa(value);
    if (key === 'deadline') return date(value);
    return fa(value);
  }
  const changeKeys = {
    product_id: 'محصول',
    quantity: 'تعداد',
    specifications: 'مشخصات',
    delivery: 'اطلاعات ارسال',
    deadline: 'موعد ارسال',
  };
</script>

<button class="text-button back-button" onclick={() => navigate('/orders')}
  ><Icon name="chevron" size={14} />بازگشت به سفارش‌ها</button
>
{#if error}<div class="error-banner" role="alert">
    {error}<button class="text-button" onclick={load}>تلاش دوباره</button>
  </div>{/if}
{#if !order}<div class="loading"><span class="spinner"></span>در حال باز کردن سفارش…</div>{:else}
  <div class="page-heading">
    <div>
      <span class="eyebrow">دفتر سفارش‌ها / جزئیات سفارش</span>
      <h1>سفارش <bdi>#{fa(1000 + order.id)}</bdi> <Status status={order.status} /></h1>
      <p>ثبت‌شده در {date(order.created_at, true)} · نسخهٔ {fa(order.version)}</p>
    </div>
    <div class="heading-actions">
      <button class="btn secondary" onclick={() => navigate('/customers/' + order.customer_id)}
        ><Icon name="people" size={16} />سابقهٔ مشتری</button
      >{#if order.tracking_url}<button class="btn secondary" onclick={copyTracking}
          ><Icon name="link" size={16} />کپی پیوند پیگیری</button
        >{/if}
    </div>
  </div>
  {#if order.overdue}<div class="error-banner section-gap">
      <Icon name="alert" size={18} />موعد ارسال این سفارش گذشته است. با مشتری هماهنگ کنید و موعد تازه‌ای تعیین
      کنید.
    </div>{/if}
  <div class="order-action">
    <div><span class="eyebrow">قدم بعدی شما</span><strong>{order.next_action}</strong></div>
    <Icon name="arrow" size={22} />
  </div>
  <div class="two-columns">
    <div class="page-stack">
      <section class="panel">
        <div class="panel-head">
          <h2>جزئیات سفارش</h2>
          <span class="tag">{fa(order.quantity)} عدد</span>
        </div>
        <div class="panel-body item-body">
          <div class="order-product">
            <span class="product-icon"><Icon name="box" size={30} /></span>
            <div>
              <h3>{order.product_name}</h3>
              <p>قیمت واحد: {money(order.unit_price)}</p>
            </div>
          </div>
          <div class="spec-grid">
            {#each order.requirement_schema as requirement}<div>
                <span>{requirement.label}</span><strong
                  >{order.specifications[requirement.key] || 'ثبت نشده'}</strong
                >
              </div>{/each}
          </div>
          <div class="info-list">
            <div class="info-row"><span>جمع محصولات</span><strong>{money(order.subtotal)}</strong></div>
            <div class="info-row"><span>هزینهٔ ارسال</span><strong>{money(order.shipping_cost)}</strong></div>
            <div class="info-row total"><span>مبلغ کل</span><strong>{money(order.total)}</strong></div>
            <div class="info-row">
              <span>پرداخت آزمایشی تأییدشده</span><strong class="green-text"
                >{money(order.paid_amount)}</strong
              >
            </div>
            {#if order.balance}<div class="info-row">
                <span>ماندهٔ پرداخت</span><strong class="danger-text">{money(order.balance)}</strong>
              </div>{/if}
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>گیرنده و نشانی ارسال</h2>
          <Icon name="truck" size={18} />
        </div>
        <div class="panel-body">
          <div class="delivery-heading">
            <span class="avatar">{order.customer_name.slice(0, 1)}</span>
            <div>
              <strong>{order.delivery.name}</strong><small dir="ltr">@{order.customer_username}</small>
            </div>
            <bdi>{order.delivery.phone}</bdi>
          </div>
          <p class="address">{order.delivery.city}، {order.delivery.address}</p>
          <div class="info-row"><span>کد پستی</span><bdi>{order.delivery.postal_code}</bdi></div>
          {#if order.delivery.notes}<p class="muted address">یادداشت ارسال: {order.delivery.notes}</p>{/if}
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>درخواست‌های تغییر <span class="pill-count">{fa(order.changes.length)}</span></h2>
          {#if !['canceled'].includes(order.status)}<button
              class="text-button"
              onclick={() => (editingChange = true)}><Icon name="plus" size={14} />ثبت درخواست</button
            >{/if}
        </div>
        <div class="panel-body changes-body">
          {#each order.changes as change}<article class="change-card">
              <div class="change-top">
                <strong>{changeLabels[change.status]}</strong><small>{date(change.created_at, true)}</small>
              </div>
              <div class="change-comparison">
                {#each Object.entries(changeKeys) as [key, label]}{#if JSON.stringify(change.original[key]) !== JSON.stringify(change.proposed[key])}<div
                    >
                      <span>{label}</span>
                      <p>
                        <del>{valueLabel(key, change.original[key])}</del><Icon
                          name="arrow"
                          size={13}
                        /><strong>{valueLabel(key, change.proposed[key])}</strong>
                      </p>
                    </div>{/if}{/each}
              </div>
              {#if change.reason}<p class="muted">دلیل: {change.reason}</p>{/if}{#if change.resolved_at}<small
                  class="muted"
                  >بررسی توسط {change.responsible_user} در {date(change.resolved_at, true)}</small
                >{/if}{#if change.status === 'manual'}<p class="notice-banner">
                  سفارش قبلاً ارسال شده است؛ این درخواست را مستقیماً با مشتری هماهنگ کنید.
                </p>{/if}
              {#if change.status === 'pending'}{#if quotes[change.id]}<div class="notice-banner">
                    مبلغ تازه: {money(quotes[change.id].total)} · موعد تازه: {date(
                      quotes[change.id].deadline,
                    )} · ماندهٔ تازه: {money(Math.max(0, quotes[change.id].total - order.paid_amount))}
                  </div>{/if}<label for={'reason-' + change.id}>توضیح تصمیم (اختیاری)</label><input
                  id={'reason-' + change.id}
                  bind:value={reason}
                  maxlength="1500"
                  placeholder="توضیحی برای مشتری…"
                />
                <div class="form-footer">
                  <button class="btn danger small" disabled={busy} onclick={() => decide(change, 'reject')}
                    >رد درخواست</button
                  ><button class="btn small" disabled={busy} onclick={() => decide(change, 'approve')}
                    >{quotes[change.id] ? 'تأیید نهایی تغییر' : 'بررسی مبلغ و موعد تازه'}</button
                  >
                </div>{/if}
            </article>{:else}<p class="muted">هنوز درخواست تغییری ثبت نشده است.</p>{/each}
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <div class="tabs">
            <button class="tab" class:active={tab === 'details'} onclick={() => (tab = 'details')}
              >مسیر سفارش</button
            ><button class="tab" class:active={tab === 'messages'} onclick={() => (tab = 'messages')}
              >گفتگوهای مرتبط</button
            ><button class="tab" class:active={tab === 'payments'} onclick={() => (tab = 'payments')}
              >پرداخت‌ها</button
            ><button
              class="tab"
              class:active={tab === 'notifications'}
              onclick={() => (tab = 'notifications')}>اعلان‌ها</button
            >
          </div>
        </div>
        <div class="panel-body">
          {#if tab === 'details'}<div class="timeline">
              {#each [...order.history].reverse() as h}<div class="timeline-item">
                  <p>{h.text}</p>
                  <small>{h.actor} · {date(h.created_at, true)}</small>
                </div>{/each}
            </div>
          {:else if tab === 'messages'}<p class="summary-text">{order.conversation_summary}</p>
            <div class="detail-messages">
              {#each order.messages as m}<div
                  class="detail-message"
                  class:from-customer={m.role === 'customer'}
                >
                  <small>{m.role === 'customer' ? 'مشتری' : m.role === 'seller' ? 'فروشنده' : 'دستیار'}</small
                  >
                  <p>{m.text}</p>
                  <time>{date(m.created_at, true)}</time>
                </div>{:else}<p class="muted">پیام مرتبطی ثبت نشده است.</p>{/each}
            </div>
          {:else if tab === 'payments'}<div class="info-list">
              {#each [...order.payments].reverse() as p}<div class="payment-row">
                  <div>
                    <strong>{money(p.amount)}</strong><small
                      >{paymentLabels[p.status]} · {date(p.expires_at, true)}</small
                    >
                  </div>
                  {#if p.status === 'pending'}<a class="btn secondary small" href={p.url}>درگاه آزمایشی</a
                    >{/if}
                </div>{:else}<p class="muted">هنوز پیوند پرداختی ایجاد نشده است.</p>{/each}
            </div>
          {:else}<div class="timeline">
              {#each [...order.notifications].reverse() as n}<div class="timeline-item">
                  <p>{n.text}</p>
                  <small>{date(n.created_at, true)}</small>
                </div>{/each}
            </div>{/if}
        </div>
      </section>
    </div>
    <div class="page-stack order-side">
      <section class="panel">
        <div class="panel-head">
          <h2>اقدام‌های سفارش</h2>
          <Icon name="edit" size={17} />
        </div>
        <div class="panel-body">
          <label for="order-status">تغییر وضعیت</label><select id="order-status" bind:value={selectedStatus}
            ><option value="">یک وضعیت انتخاب کنید</option>{#each order.allowed_statuses as status}<option
                value={status}>{statuses[status]}</option
              >{/each}</select
          ><button
            class="btn wide"
            disabled={busy || !selectedStatus}
            onclick={() =>
              act(
                '/orders/' + id + '/status',
                { version: order.version, status: selectedStatus },
                'وضعیت سفارش تغییر کرد.',
              )}>ذخیرهٔ وضعیت</button
          >{#if order.balance && !order.pending_change && !['canceled', 'shipped'].includes(order.status)}<hr
            />
            <button class="btn secondary wide" disabled={busy} onclick={paylink}
              ><Icon name="wallet" size={16} />ساخت / باز کردن پرداخت آزمایشی</button
            >{/if}
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>یادداشت و موعد ارسال</h2></div>
        <form class="panel-body" onsubmit={save}>
          <div class="field">
            <label for="deadline">موعد ارسال</label><input
              id="deadline"
              type="date"
              bind:value={deadline}
              disabled={['shipped', 'canceled'].includes(order.status)}
            /><small class="field-hint">بر مبنای منطقهٔ زمانی تهران</small>
          </div>
          <div class="field section-gap">
            <label for="note">یادداشت خصوصی فروشنده</label><textarea
              id="note"
              rows="3"
              bind:value={note}
              maxlength="5000"
              placeholder="نکته‌ای که باید یادت بماند…"></textarea>
          </div>
          <div class="field section-gap">
            <label for="status-message">پیام قابل مشاهده برای مشتری</label><textarea
              id="status-message"
              rows="2"
              bind:value={statusMessage}
              maxlength="1500"
              placeholder="مثلاً: بسته‌بندی سفارش شما در حال انجام است."></textarea>
          </div>
          <button class="btn secondary wide" disabled={busy}>ذخیرهٔ اطلاعات</button>
        </form>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>تحویل به پست</h2>
          <Icon name="truck" size={18} />
        </div>
        <div class="panel-body">
          {#if order.shipped_at}<div class="notice-banner">
              <Icon name="check" size={17} />ارسال در {date(order.shipped_at, true)}
            </div>
            <p class="tracking-number">
              {order.carrier}: <bdi>{order.tracking_number}</bdi>
            </p>{:else}{#if order.shipping_blocks.length}<div class="shipping-blocks">
                <strong><Icon name="lock" size={14} />پیش از ارسال</strong>
                <ul>
                  {#each order.shipping_blocks as block}<li>{block}</li>{/each}
                </ul>
              </div>{/if}
            <form
              onsubmit={(e) => {
                e.preventDefault();
                act(
                  '/orders/' + id + '/ship',
                  { version: order.version, tracking_number: tracking, carrier },
                  'تحویل به پست ثبت شد.',
                );
              }}
            >
              <label for="carrier">شرکت حمل</label><input
                id="carrier"
                bind:value={carrier}
                required
                maxlength="100"
              /><label class="section-gap" for="tracking-number">کد رهگیری</label><input
                id="tracking-number"
                dir="ltr"
                bind:value={tracking}
                required
                minlength="5"
                maxlength="100"
              /><button class="btn wide" disabled={busy || order.shipping_blocks.length > 0}
                ><Icon name="truck" size={16} />ثبت تحویل و ارسال</button
              >
            </form>{/if}
        </div>
      </section>
      <section class="panel">
        <div class="panel-body">
          <h3>پیگیری خصوصی مشتری</h3>
          <p class="muted tracking-help">
            این پیوند فقط همین سفارش را نشان می‌دهد. با تعویض یا ابطال، پیوند قبلی از دسترس خارج می‌شود.
          </p>
          <div class="tracking-actions">
            {#if order.tracking_url}<a class="btn secondary small" href={order.tracking_url}>دیدن پیگیری</a
              ><button
                class="text-button danger-text"
                disabled={busy}
                onclick={() => act('/orders/' + id + '/tracking/revoke', null, 'پیوند باطل شد.')}
                >ابطال پیوند</button
              >{/if}<button
              class="text-button"
              disabled={busy}
              onclick={() => act('/orders/' + id + '/tracking/rotate', null, 'پیوند تازه ساخته شد.')}
              >ساخت پیوند تازه</button
            >
          </div>
        </div>
      </section>
    </div>
  </div>
{/if}
{#if editingChange}<div class="modal-backdrop" role="presentation">
    <dialog
      use:modal
      oncancel={() => (editingChange = false)}
      class="modal"
      aria-modal="true"
      aria-labelledby="change-title"
    >
      <div class="modal-header">
        <h2 id="change-title">ثبت درخواست تغییر تعداد</h2>
        <button class="icon-button" aria-label="بستن" onclick={() => (editingChange = false)}
          ><Icon name="close" /></button
        >
      </div>
      <form class="modal-content" onsubmit={sendChange}>
        <p class="muted">
          برای تغییر سایر مشخصات از گفتگوی مشتری یا رابط برنامه استفاده کنید. تغییر تا تأیید فروشنده روی سفارش
          اعمال نمی‌شود.
        </p>
        <label for="change-quantity" class="section-gap">تعداد پیشنهادی</label><input
          id="change-quantity"
          type="number"
          min="1"
          max="1000"
          bind:value={changeQuantity}
          required
        />
        <div class="form-footer">
          <button type="button" class="btn secondary" onclick={() => (editingChange = false)}>انصراف</button
          ><button class="btn" disabled={busy}>ثبت درخواست</button>
        </div>
      </form>
    </dialog>
  </div>{/if}

<style>
  .back-button {
    margin-bottom: 20px;
    color: #97a28c;
    font-size: 11px;
  }
  .page-heading h1 :global(.status-badge) {
    vertical-align: middle;
    margin-right: 10px;
  }
  .order-action {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 23px;
    background: #ebf1e3;
    border: 1px solid #e0e9d5;
    border-radius: 11px;
    color: #739061;
    margin: 23px 0;
  }
  .order-action .eyebrow {
    display: block;
    font-size: 9px;
    color: #98ab86;
  }
  .order-action strong {
    font-size: 14px;
    font-weight: 500;
  }
  .item-body {
    padding-top: 3px;
  }
  .order-product {
    display: flex;
    align-items: center;
    gap: 15px;
    margin: 0 0 25px;
  }
  .product-icon {
    width: 62px;
    height: 62px;
    background: #f2f4eb;
    display: grid;
    place-items: center;
    color: #a6b091;
    border-radius: 13px;
  }
  .order-product p {
    font-size: 11px;
    color: #9aa68b;
    margin-top: 6px;
  }
  .spec-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 18px;
    padding: 20px 0 25px;
    margin-bottom: 20px;
    border-block: 1px solid var(--line);
  }
  .spec-grid > div > span {
    display: block;
    color: #a0aa94;
    font-size: 10px;
    margin-bottom: 6px;
  }
  .spec-grid strong {
    font-size: 12px;
    overflow-wrap: anywhere;
  }
  .delivery-heading {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .delivery-heading strong {
    display: block;
    font-size: 12px;
  }
  .delivery-heading small {
    display: block;
    color: #a4af99;
    font-size: 10px;
    margin-top: 4px;
    text-align: right;
  }
  .delivery-heading > bdi {
    margin-right: auto;
    font-size: 12px;
  }
  .address {
    font-size: 12px;
    color: #809071;
    margin: 20px 0;
    line-height: 2.1;
  }
  .wide {
    width: 100%;
    margin-top: 15px;
  }
  .shipping-blocks {
    background: #f8f4e9;
    border: 1px solid #eee7d6;
    border-radius: 8px;
    padding: 13px;
    margin-bottom: 20px;
    font-size: 10px;
    color: #a2916d;
  }
  .shipping-blocks strong {
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .shipping-blocks ul {
    padding: 0 17px 0 0;
    margin-bottom: 0;
    line-height: 2.1;
  }
  .change-card {
    border: 1px solid #e7e7dc;
    background: #fcfcf6;
    padding: 17px;
    border-radius: 9px;
    margin-bottom: 15px;
  }
  .change-card:last-child {
    margin-bottom: 0;
  }
  .change-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 15px;
  }
  .change-top strong {
    font-size: 11px;
    color: #b7996c;
  }
  .change-top small {
    font-size: 9px;
    color: #a4ae95;
  }
  .change-comparison {
    display: grid;
    gap: 15px;
    margin: 15px 0;
  }
  .change-comparison > div > span {
    font-size: 10px;
    color: #a9b19e;
  }
  .change-comparison p {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 11px;
    flex-wrap: wrap;
    margin-top: 5px;
  }
  .change-comparison del {
    color: #aeb6a3;
  }
  .change-comparison strong {
    font-weight: 500;
    color: #769261;
    overflow-wrap: anywhere;
  }
  .change-card .notice-banner {
    font-size: 10px;
    margin-bottom: 15px;
  }
  .tracking-help {
    font-size: 10px;
    margin: 12px 0 18px;
  }
  .tracking-actions {
    display: flex;
    gap: 15px;
    align-items: center;
    flex-wrap: wrap;
  }
  .tracking-actions .text-button {
    font-size: 10px;
  }
  .tracking-number {
    margin-top: 15px;
    font-size: 11px;
  }
  .detail-messages {
    display: grid;
    gap: 12px;
  }
  .detail-message {
    background: #f2f5eb;
    border-radius: 8px;
    padding: 13px;
    max-width: 92%;
    width: max-content;
  }
  .detail-message.from-customer {
    background: #f6f4ee;
    margin-right: auto;
  }
  .detail-message > small {
    color: #a4b295;
    font-size: 9px;
  }
  .detail-message p {
    font-size: 11px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .detail-message time {
    color: #b1baa5;
    display: block;
    font-size: 8px;
    margin-top: 7px;
  }
  .summary-text {
    font-size: 11px;
    color: #94a184;
    margin-bottom: 20px;
  }
  .payment-row {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    align-items: center;
  }
  .payment-row strong {
    font-size: 12px;
  }
  .payment-row small {
    display: block;
    font-size: 9px;
    color: #a5af99;
    margin-top: 5px;
  }
  @media (max-width: 700px) {
    .page-heading h1 :global(.status-badge) {
      margin-right: 4px;
      font-size: 9px;
    }
    .page-heading h1 {
      font-size: 22px;
    }
    .delivery-heading {
      flex-wrap: wrap;
    }
    .spec-grid {
      gap: 15px;
    }
    .order-action {
      padding: 15px 18px;
    }
    .change-top {
      flex-wrap: wrap;
    }
    .change-card {
      padding: 13px;
    }
  }
</style>
