<script>
  import { onMount } from 'svelte';
  import { api, fa } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  let config,
    error = '',
    checking = false;
  let profile = {},
    savingProfile = false,
    profileError = '',
    profileSaved = false;
  const profileFields = [
    ['store_name', 'نام عمومی فروشگاه', 200],
    ['about', 'معرفی فروشنده و فروشگاه', 1500],
    ['contact', 'راه ارتباط عمومی', 500],
    ['working_hours', 'ساعت پاسخ‌گویی', 500],
    ['shipping_policy', 'شرایط ارسال', 1500],
    ['return_policy', 'شرایط مرجوعی', 1500],
    ['custom_orders', 'شرایط سفارش اختصاصی', 1000],
    ['ordering_help', 'راهنمای خرید', 1500],
  ];
  async function saveProfile(e) {
    e.preventDefault();
    savingProfile = true;
    profileError = '';
    profileSaved = false;
    try {
      profile = await api('/seller/profile', { method: 'PUT', body: profile });
      config = { ...config, seller_profile: profile };
      profileSaved = true;
    } catch (e) {
      profileError = e.message;
    } finally {
      savingProfile = false;
    }
  }
  async function checkLLM() {
    checking = true;
    error = '';
    try {
      const connection = await api('/llm/check', { method: 'POST' });
      config = { ...config, llm_connection: connection };
    } catch (e) {
      error = e.message;
    } finally {
      checking = false;
    }
  }
  onMount(async () => {
    try {
      config = await api('/settings');
      profile = Object.fromEntries(profileFields.map(([key]) => [key, config.seller_profile?.[key] || '']));
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
            >{item.mode === 'mock' ? 'شبیه‌سازی' : 'سرویس واقعی'}</span
          >
        </div>
        <div class="panel-body">
          <h2>{item.title}</h2>
          <p>{item.description}</p>
          {#if item.icon === 'chat' && config.llm_connection}
            <div class="llm-connection" aria-live="polite">
              {#if config.llm_connection.model}<p>مدل: <bdi>{config.llm_connection.model}</bdi></p>{/if}
              <p class:danger-text={!['ready', 'mock', 'not_checked'].includes(config.llm_connection.status)}>
                {config.llm_connection.message}
              </p>
              <button
                class="btn secondary small"
                disabled={checking || config.llm_mode === 'mock'}
                onclick={checkLLM}
                >{#if checking}<span class="spinner"></span>{/if}{checking
                  ? 'در حال آزمایش…'
                  : 'آزمایش اتصال'}</button
              >
              <small class="field-hint"
                >با دادهٔ ساختگی و یک درخواست انجام می‌شود؛ ممکن است هزینهٔ سرویس داشته باشد.</small
              >
            </div>
          {/if}
        </div>
      </section>{/each}
  </div>
  <details class="panel section-gap seller-profile">
    <summary>اطلاعات عمومی فروشگاه و راهنمای دستیار <Icon name="down" size={17} /></summary>
    <form class="panel-body" onsubmit={saveProfile}>
      <p class="profile-help">
        این اطلاعات مبنای پاسخ به مشتری است. ساعت کاری، راه تماس و قوانین خودتان را بنویسید؛ دستیار دربارهٔ
        فیلدهای خالی حدس نمی‌زند. اطلاعات محرمانه را اینجا وارد نکنید.
      </p>
      <div class="form-grid">
        {#each profileFields as [key, label, limit]}<div class="field" class:full={limit > 500}>
            <label for={'profile-' + key}>{label}</label>
            {#if key === 'store_name'}<input
                id={'profile-' + key}
                bind:value={profile[key]}
                maxlength={limit}
              />
            {:else}<textarea id={'profile-' + key} bind:value={profile[key]} rows="2" maxlength={limit}
              ></textarea>{/if}
          </div>{/each}
      </div>
      {#if profileError}<p class="error-banner section-gap" role="alert">{profileError}</p>{/if}
      {#if profileSaved}<p class="profile-help green-text" role="status">
          اطلاعات فروشگاه ذخیره شد و در پاسخ‌های بعدی استفاده می‌شود.
        </p>{/if}
      <div class="form-footer">
        <button class="btn" disabled={savingProfile}
          >{savingProfile ? 'در حال ذخیره…' : 'ذخیرهٔ اطلاعات فروشگاه'}</button
        >
      </div>
    </form>
  </details>
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
  .seller-profile summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 15px;
    padding: 22px 24px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    list-style: none;
  }
  .seller-profile summary::-webkit-details-marker {
    display: none;
  }
  .profile-help {
    font-size: 12px;
    color: var(--muted);
    line-height: 2;
    margin-bottom: 22px;
  }
  .llm-connection {
    border-top: 1px solid var(--line);
    margin-top: 18px;
    padding-top: 8px;
  }
  .llm-connection .btn {
    margin-top: 12px;
  }
  .settings-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }
  .settings-icon {
    width: 45px;
    height: 45px;
    border-radius: 12px;
    background: var(--tone-eef3e6, #eef3e6);
    display: grid;
    place-items: center;
    color: var(--tone-91a77a, #91a77a);
  }
  .settings-grid .panel-body {
    padding-top: 0;
  }
  .settings-grid h2 {
    font-size: 14px;
  }
  .settings-grid p {
    font-size: 11px;
    color: var(--tone-9baa8c, #9baa8c);
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
