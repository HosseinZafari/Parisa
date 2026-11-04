<script>
  import { onMount } from 'svelte';
  import { api, fa } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  let config,
    error = '';
  onMount(async () => {
    try {
      config = await api('/settings');
    } catch (e) {
      error = e.message;
    }
  });
</script>

<div class="page-heading">
  <div>
    <span class="eyebrow">پشت صحنهٔ دفتر شما</span>
    <h1>تنظیمات و اتصال‌ها</h1>
    <p>وضعیت سرویس‌ها و محدودهٔ آزمایش را اینجا ببینید.</p>
  </div>
</div>
{#if error}<div class="error-banner">{error}</div>{/if}{#if config}<div class="settings-grid">
    {#each [{ title: 'دستیار زبانی', icon: 'chat', mode: config.llm_mode, description: config.llm_mode === 'mock' ? 'پردازش فارسی به‌صورت محلی انجام می‌شود و به کلید سرویس نیاز ندارد.' : 'استخراج اطلاعات از سرویس تنظیم‌شده انجام می‌شود؛ کنترل سفارش در سرور باقی می‌ماند.' }, { title: 'اینستاگرام', icon: 'instagram', mode: config.instagram_mode, description: config.instagram_mode === 'mock' ? 'ارسال پیام شبیه‌سازی می‌شود. گفتگوی محلی مستقل از مجوزهای متا فعال است.' : 'رویدادها با امضای متا دریافت می‌شوند. دسترسی مشتریان واقعی باید جداگانه تأیید شود.' }, { title: 'پرداخت', icon: 'wallet', mode: config.payment_mode, description: 'درگاه آزمایشی است؛ مبلغ از سفارش در سرور خوانده می‌شود و پولی جابه‌جا نمی‌شود.' }] as item}<section
        class="panel"
      >
        <div class="panel-head">
          <span class="settings-icon"><Icon name={item.icon} size={23} /></span><span class="tag"
            >{item.mode === 'mock' ? 'شبیه‌سازی' : 'متصل به سرویس'}</span
          >
        </div>
        <div class="panel-body">
          <h2>{item.title}</h2>
          <p>{item.description}</p>
        </div>
      </section>{/each}
  </div>
  <section class="panel section-gap">
    <div class="panel-head">
      <h2>محدودهٔ این نمونه</h2>
      <Icon name="help" size={18} />
    </div>
    <div class="panel-body info-list">
      <div class="info-row"><span>منطقهٔ زمانی فروشگاه</span><strong>تهران</strong></div>
      <div class="info-row">
        <span>حداکثر طول هر پیام</span><strong>{fa(config.max_message_length)} نویسه</strong>
      </div>
      <div class="info-row">
        <span>حداکثر پیام‌های هر گفتگو</span><strong>{fa(config.max_conversation_messages)} پیام</strong>
      </div>
      <div class="info-row">
        <span>حداکثر فراخوانی سرویس زبانی در هر گفتگو</span><strong
          >{fa(config.max_llm_requests)} درخواست</strong
        >
      </div>
    </div>
  </section>
  <div class="notice-banner section-gap">
    <Icon name="lock" size={19} />
    <p>
      کلیدها و توکن‌ها فقط از تنظیمات سرور خوانده می‌شوند. برای تغییر اتصال‌ها، راهنمای پروژه و پروندهٔ نمونهٔ
      متغیرهای محیطی را ببینید.
    </p>
  </div>
  <a href="/docs" class="text-button docs-link" target="_blank" rel="noreferrer"
    >مستندات رابط برنامه در محیط محلی<Icon name="arrow" size={15} /></a
  >{:else}<div class="loading"><span class="spinner"></span></div>{/if}

<style>
  .settings-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }
  .settings-icon {
    width: 45px;
    height: 45px;
    border-radius: 12px;
    background: #eef3e6;
    display: grid;
    place-items: center;
    color: #91a77a;
  }
  .settings-grid .panel-body {
    padding-top: 0;
  }
  .settings-grid h2 {
    font-size: 14px;
  }
  .settings-grid p {
    font-size: 11px;
    color: #9baa8c;
    margin-top: 12px;
    line-height: 2.1;
  }
  .docs-link {
    margin-top: 25px;
    display: flex;
    width: max-content;
    font-size: 11px;
  }
  @media (max-width: 700px) {
    .settings-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
