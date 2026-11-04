<script>
  import { onMount } from 'svelte';
  import { api, money, fa, date, navigate, paymentLabels } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  export let token;
  let payment,
    error = '',
    busy = false,
    result;
  onMount(async () => {
    try {
      payment = await api('/payments/' + token);
    } catch (e) {
      error = e.message;
    }
  });
  async function simulate(outcome) {
    busy = true;
    error = '';
    try {
      result = await api('/payments/' + token + '/simulate', { method: 'POST', body: { outcome } });
      payment = await api('/payments/' + token);
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }
</script>

<main class="public-shell">
  <a class="public-brand" href="/chat"><Icon name="leaf" size={29} />پریسا</a>
  <section class="panel public-card">
    <div class="panel-body">
      <div class="test-label"><Icon name="help" size={17} />درگاه کاملاً آزمایشی · بدون انتقال پول</div>
      {#if error}<div class="error-banner" role="alert">{error}</div>{/if}{#if !payment && !error}<div
          class="loading"
        >
          <span class="spinner"></span>
        </div>{/if}{#if payment}<div
          class="status-circle"
          class:error={['failed', 'canceled', 'expired'].includes(payment.status)}
        >
          <Icon
            name={payment.status === 'success' ? 'check' : payment.status === 'pending' ? 'wallet' : 'close'}
            size={32}
          />
        </div>
        <h1 class="payment-title">
          {payment.status === 'pending'
            ? 'یک قدم تا ثبت پرداخت آزمایشی'
            : payment.status === 'success'
              ? 'پرداخت آزمایشی موفق بود'
              : payment.status === 'expired'
                ? 'مهلت این پیوند تمام شده'
                : payment.status === 'failed'
                  ? 'پرداخت آزمایشی ناموفق بود'
                  : 'پرداخت آزمایشی لغو شد'}
        </h1>
        <p class="subtitle payment-title">
          سفارش <bdi>#{fa(1000 + payment.order_id)}</bdi> · مبلغ از روی سفارش در سرور خوانده شده است.
        </p>
        <div class="payment-amount">
          <span>مبلغ قابل پرداخت</span><strong>{money(payment.amount)}</strong>
        </div>
        <div class="info-row"><span>وضعیت</span><strong>{paymentLabels[payment.status]}</strong></div>
        <div class="info-row section-gap">
          <span>اعتبار پیوند</span><span>{date(payment.expires_at, true)}</span>
        </div>
        {#if result?.duplicate}<p class="notice-banner section-gap">
            این رویداد قبلاً ثبت شده است و پرداخت یا اعلان تازه‌ای ایجاد نشد.
          </p>{/if}
        {#if payment.status === 'pending'}<div class="notice-banner section-gap">
            اطلاعات کارت بانکی وارد نکنید. باز کردن یا بستن این صفحه وضعیت پرداخت را تغییر نمی‌دهد.
          </div>
          <div class="payment-buttons">
            <button class="btn" disabled={busy} onclick={() => simulate('success')}
              ><Icon name="check" size={17} />شبیه‌سازی پرداخت موفق</button
            >
            <div>
              <button class="btn secondary" disabled={busy} onclick={() => simulate('failed')}
                >پرداخت ناموفق</button
              ><button class="btn secondary" disabled={busy} onclick={() => simulate('canceled')}
                >لغو پرداخت</button
              >
            </div>
            <button class="text-button" disabled={busy} onclick={() => simulate('expired')}
              >آزمایش پیوند منقضی‌شده</button
            >
          </div>{:else if payment.status === 'success'}<button
            class="btn secondary duplicate-btn"
            disabled={busy}
            onclick={() => simulate('success')}>آزمایش تأیید تکراری پرداخت</button
          >{:else}<p class="muted section-gap">
            برای دریافت پیوند تازه به گفتگو برگردید. مبلغ یا وضعیت سفارش را نمی‌توان از این صفحه تغییر داد.
          </p>{/if}<button class="text-button return-link" onclick={() => navigate('/chat')}
          >بازگشت به گفتگو و پیگیری سفارش<Icon name="arrow" size={14} /></button
        >{/if}
    </div>
  </section>
  <p class="public-footer"><Icon name="lock" size={12} />این نمونه به هیچ درگاه بانکی متصل نیست.</p>
</main>

<style>
  .test-label {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    background: var(--tone-fbf4e5, #fbf4e5);
    color: var(--tone-b29764, #b29764);
    border: 1px solid var(--tone-eee1c5, #eee1c5);
    border-radius: 7px;
    font-size: 10px;
    padding: 11px;
    margin-bottom: 28px;
  }
  .payment-title {
    text-align: center;
  }
  .payment-amount {
    background: var(--tone-f1f5e9, #f1f5e9);
    border: 1px solid var(--tone-e6eddb, #e6eddb);
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    margin: 25px 0;
  }
  .payment-amount > span {
    display: block;
    font-size: 10px;
    color: var(--tone-a0af8c, #a0af8c);
  }
  .payment-amount strong {
    display: block;
    color: var(--tone-6f8b57, #6f8b57);
    font-size: 29px;
    font-weight: 500;
    margin-top: 7px;
  }
  .payment-buttons {
    display: grid;
    gap: 12px;
    margin-top: 25px;
  }
  .payment-buttons > div {
    display: flex;
    gap: 12px;
  }
  .payment-buttons > div > button {
    flex: 1;
  }
  .payment-buttons > .text-button {
    margin: 8px auto;
  }
  .return-link {
    margin: 26px auto 0;
    display: flex;
    font-size: 11px;
  }
  .duplicate-btn {
    width: 100%;
    margin-top: 25px;
  }
  .public-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
  }
</style>
