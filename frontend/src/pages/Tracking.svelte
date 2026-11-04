<script>
  import { onMount } from 'svelte';
  import { api, date, money, fa, changeLabels } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  import Status from '../components/Status.svelte';
  export let token;
  let order,
    error = '';
  async function load() {
    try {
      order = await api('/tracking/' + token);
      error = '';
    } catch (e) {
      error = e.message;
      order = null;
    }
  }
  onMount(() => {
    load();
    const poll = setInterval(load, 15000);
    return () => clearInterval(poll);
  });
  $: step = order
    ? ['awaiting_payment', 'paid_awaiting_preparation', 'in_preparation', 'ready_to_ship', 'shipped'].indexOf(
        order.status,
      )
    : -1;
</script>

<main class="public-shell">
  <div class="public-brand"><Icon name="leaf" size={29} />پریسا</div>
  <section class="panel public-card">
    <div class="panel-body">
      {#if error}<div class="error-banner" role="alert">{error}</div>{:else if !order}<div class="loading">
          <span class="spinner"></span>در حال دریافت وضعیت…
        </div>{:else}<span class="eyebrow">همراه سفارش شما، تا رسیدن به دستتان</span>
        <h1>سفارش <bdi>#{fa(1000 + order.id)}</bdi></h1>
        <p class="subtitle">ثبت‌شده در {date(order.created_at)}</p>
        <Status status={order.status} />
        <div class="tracking-progress">
          {#each [{ icon: 'wallet', label: 'پرداخت' }, { icon: 'box', label: 'تأیید' }, { icon: 'edit', label: 'ساخت' }, { icon: 'check', label: 'آماده' }, { icon: 'truck', label: 'ارسال' }] as s, i}<div
              class:done={step >= i}
            >
              <span><Icon name={s.icon} size={17} /></span><small>{s.label}</small>
            </div>{/each}
        </div>
        {#if order.status_message}<div class="notice-banner">{order.status_message}</div>{/if}
        <hr />
        <h2>{order.product_name}</h2>
        <div class="info-list section-gap">
          <div class="info-row"><span>تعداد</span><strong>{fa(order.quantity)} عدد</strong></div>
          {#each order.requirement_schema as r}{#if order.specifications[r.key]}<div class="info-row">
                <span>{r.label}</span><strong>{order.specifications[r.key]}</strong>
              </div>{/if}{/each}
          <div class="info-row"><span>موعد ارسال</span><strong>{date(order.deadline)}</strong></div>
          <div class="info-row">
            <span>وضعیت پرداخت آزمایشی</span><strong class="green-text"
              >{order.balance ? 'در انتظار تسویه' : 'تسویه‌شده'}</strong
            >
          </div>
          <div class="info-row total"><span>مبلغ کل</span><strong>{money(order.total)}</strong></div>
          {#if order.balance}<div class="info-row">
              <span>ماندهٔ پرداخت</span><strong>{money(order.balance)}</strong>
            </div>{/if}
        </div>
        {#if order.tracking_number}<div class="parcel">
            <Icon name="truck" size={24} />
            <div>
              <strong>بسته به {order.carrier} تحویل داده شد.</strong>
              <p>کد رهگیری: <bdi>{order.tracking_number}</bdi></p>
              <small>{date(order.shipped_at, true)}</small>
            </div>
          </div>{/if}{#if order.changes.length}<hr />
          <h2>درخواست‌های تغییر</h2>
          <div class="timeline section-gap">
            {#each [...order.changes].reverse() as c}<div class="timeline-item">
                <p>درخواست تغییر: {changeLabels[c.status]}</p>
                {#if c.reason}<p class="muted">{c.reason}</p>{/if}<small>{date(c.created_at, true)}</small>
              </div>{/each}
          </div>{/if}{/if}
    </div>
  </section>
  <p class="public-footer">پیوند خصوصی همین سفارش · برای تغییر مشخصات، در گفتگو با ما در تماس باشید.</p>
</main>

<style>
  .tracking-progress {
    display: flex;
    justify-content: space-between;
    gap: 5px;
    margin: 30px 0;
  }
  .tracking-progress > div {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    flex: 1;
    color: #bac4ad;
    position: relative;
  }
  .tracking-progress > div:before {
    content: '';
    position: absolute;
    height: 1px;
    background: #e4ebdc;
    left: 70%;
    right: -30%;
    top: 18px;
  }
  .tracking-progress > div:first-child:before {
    display: none;
  }
  .tracking-progress span {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border: 1px solid #e2ead9;
    border-radius: 50%;
    background: #f9fbf5;
    z-index: 1;
  }
  .tracking-progress .done {
    color: #789565;
  }
  .tracking-progress .done span {
    background: #eaf1e2;
    border-color: #cdddc0;
  }
  .tracking-progress small {
    font-size: 9px;
  }
  .info-row strong {
    overflow-wrap: anywhere;
    max-width: 70%;
  }
  .parcel {
    display: flex;
    align-items: center;
    gap: 13px;
    padding: 19px;
    background: #edf4e5;
    border-radius: 10px;
    margin-top: 25px;
    color: #799762;
  }
  .parcel strong {
    font-size: 12px;
  }
  .parcel p {
    font-size: 11px;
    margin-top: 5px;
  }
  .parcel small {
    font-size: 9px;
    color: #a4b395;
  }
</style>
