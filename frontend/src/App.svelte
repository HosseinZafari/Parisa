<script>
  import { onMount } from 'svelte';
  import { initialTheme, applyTheme } from './lib/theme';
  let theme = initialTheme();
  applyTheme(theme);
  function toggleTheme() {
    theme = theme === 'light' ? 'dark' : 'light';
    applyTheme(theme);
  }
  import { api, navigate, fa, date } from './lib/api';
  import Icon from './components/Icon.svelte';
  import Dashboard from './pages/Dashboard.svelte';
  import Orders from './pages/Orders.svelte';
  import OrderDetail from './pages/OrderDetail.svelte';
  import Products from './pages/Products.svelte';
  import Customers from './pages/Customers.svelte';
  import Chat from './pages/Chat.svelte';
  import Payment from './pages/Payment.svelte';
  import Tracking from './pages/Tracking.svelte';
  import Notifications from './pages/Notifications.svelte';
  import Conversations from './pages/Conversations.svelte';
  import Settings from './pages/Settings.svelte';
  let path = window.location.pathname;
  let seller = null,
    checking = true,
    mobileNav = false;
  let username = 'parisa',
    password = '',
    loginError = '',
    busy = false;
  let toast = '',
    toastError = false,
    toastTimer;
  let unread = 0,
    urgentUnread = 0;
  const nav = [
    { path: '/dashboard', label: 'نمای کلی', icon: 'grid' },
    { path: '/orders', label: 'سفارش‌ها', icon: 'orders' },
    { path: '/conversations', label: 'گفتگوها', icon: 'chat' },
    { path: '/products', label: 'محصولات', icon: 'box' },
    { path: '/customers', label: 'مشتری‌ها', icon: 'people' },
    { path: '/notifications', label: 'اعلان‌ها', icon: 'bell' },
  ];
  $: publicPage = path.startsWith('/pay/') || path.startsWith('/track/') || path === '/chat';
  $: active = nav.find((n) => path.startsWith(n.path));
  function notify(text, error = false) {
    toast = text;
    toastError = error;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast = ''), 5000);
  }
  async function refreshUnread() {
    if (!seller) return;
    try {
      const items = await api('/notifications');
      unread = items.filter((n) => !n.read).length;
      urgentUnread = items.filter((n) => !n.read && n.priority === 'urgent').length;
    } catch {}
  }
  async function login(e) {
    e.preventDefault();
    busy = true;
    loginError = '';
    try {
      seller = await api('/auth/login', { method: 'POST', body: { username, password } });
      password = '';
      refreshUnread();
    } catch (e) {
      loginError = e.message;
    } finally {
      busy = false;
    }
  }
  async function logout() {
    await api('/auth/logout', { method: 'POST' });
    seller = null;
  }
  onMount(() => {
    const pop = () => {
      path = window.location.pathname;
      mobileNav = false;
      window.scrollTo(0, 0);
    };
    const expired = () => {
      seller = null;
      notify('نشست شما پایان یافته است؛ دوباره وارد شوید.', true);
    };
    window.addEventListener('popstate', pop);
    window.addEventListener('session-expired', expired);
    api('/auth/me')
      .then((s) => {
        seller = s;
        refreshUnread();
      })
      .catch(() => {})
      .finally(() => (checking = false));
    const interval = setInterval(refreshUnread, 5000);
    return () => {
      window.removeEventListener('popstate', pop);
      window.removeEventListener('session-expired', expired);
      clearInterval(interval);
      clearTimeout(toastTimer);
    };
  });
</script>

<svelte:head
  ><title>{publicPage ? 'پریسا | همراه سفارش شما' : 'پریسا | ' + (active?.label || 'دفتر سفارش‌ها')}</title
  ></svelte:head
>

{#if publicPage}
  {#if path.startsWith('/pay/')}<Payment token={path.split('/')[2]} />
  {:else if path.startsWith('/track/')}<Tracking token={path.split('/')[2]} />
  {:else}<Chat />{/if}
{:else if checking}
  <div class="loading"><span class="spinner"></span>در حال باز کردن دفتر…</div>
{:else if !seller}
  <main class="login-shell">
    <div class="login-art">
      <div class="art-mark"><Icon name="leaf" size={85} stroke={0.8} /></div>
      <span>هر سفارش، یک قول کوچک.</span>
      <p>از اولین سلام تا رسیدن بسته،<br />خیالت از سفارش‌ها راحت باشد.</p>
      <div class="art-rings"></div>
      <small>پریسا · دفتر سفارش‌های شما</small>
    </div>
    <div class="login-content">
      <a href="/" class="login-brand"><Icon name="leaf" size={30} />پریسا<span>دفتر سفارش‌ها</span></a>
      <div class="login-form">
        <span class="eyebrow">خوش آمدید به فضای کارتان</span>
        <h1>دفترت را باز کن.</h1>
        <p class="muted">سفارش‌ها، گفتگوها و کارهای امروز، همه یک‌جا.</p>
        <form onsubmit={login}>
          <div class="field">
            <label for="username">نام کاربری</label><input
              id="username"
              dir="ltr"
              autocomplete="username"
              bind:value={username}
              required
            />
          </div>
          <div class="field">
            <label for="password">گذرواژه</label><input
              id="password"
              type="password"
              dir="ltr"
              autocomplete="current-password"
              bind:value={password}
              required
            />
          </div>
          {#if loginError}<div class="error-banner" role="alert">{loginError}</div>{/if}
          <button class="btn" type="submit" disabled={busy}
            >{busy ? 'در حال ورود…' : 'ورود به دفتر'}<Icon name="arrow" size={17} /></button
          >
        </form>
        <div class="demo-note">
          <Icon name="help" size={18} />
          <p>
            حساب پیش‌فرض محلی: <bdi>parisa</bdi><br />گذرواژه: <bdi>parisa-demo-1405</bdi><br /><small
              >اگر تنظیمات را تغییر داده‌اید، گذرواژهٔ خودتان را وارد کنید.</small
            >
          </p>
        </div>
        <button class="text-button" onclick={() => navigate('/chat')}
          >شروع گفتگوی آزمایشی مشتری <Icon name="arrow" size={15} /></button
        >
      </div>
      <small class="login-foot">نسخهٔ آزمایشی · ساخته‌شده برای کسب‌وکارهای کوچک</small>
    </div>
  </main>
{:else}
  <div class="app-shell">
    {#if mobileNav}<button class="nav-shade" aria-label="بستن فهرست" onclick={() => (mobileNav = false)}
      ></button>{/if}
    <aside class:mobile-open={mobileNav}>
      <a
        class="brand"
        href="/dashboard"
        onclick={(e) => {
          e.preventDefault();
          navigate('/dashboard');
        }}
        ><span class="brand-mark"><Icon name="leaf" size={27} /></span><span
          >پریسا<small>دفتر سفارش‌های شما</small></span
        ></a
      >
      <div class="shop-card">
        <span class="shop-avatar">پ</span>
        <div><strong>فروشگاه پریسا</strong><small>کسب‌وکار کوچک، رؤیاهای بزرگ</small></div>
        <Icon name="down" size={13} />
      </div>
      <span class="nav-caption">میز کار شما</span>
      <nav>
        {#each nav as item}<a
            href={item.path}
            class:active={path.startsWith(item.path) || (item.path === '/dashboard' && path === '/')}
            onclick={(e) => {
              e.preventDefault();
              navigate(item.path);
            }}
            ><Icon name={item.icon} size={19} /><span>{item.label}</span
            >{#if item.path === '/notifications' && unread}<b class="nav-count">{fa(unread)}</b>{/if}</a
          >{/each}
      </nav>
      <div class="nav-bottom">
        <div class="little-note">
          <span class="little-leaf"><Icon name="leaf" size={24} stroke={1.2} /></span><strong
            >هیچ سفارشی جا نمی‌ماند.</strong
          >
          <p>از دل گفتگوها،<br />تا رسیدن به دست مشتری.</p>
          <button class="text-button" onclick={() => navigate('/chat')}
            >امتحان گفتگوی مشتری <Icon name="arrow" size={13} /></button
          >
        </div>
        <a
          class="settings-link"
          href="/settings"
          onclick={(e) => {
            e.preventDefault();
            navigate('/settings');
          }}><Icon name="settings" size={19} />تنظیمات و اتصال‌ها</a
        >
        <div class="seller-card">
          <span class="avatar">پ</span>
          <div><strong>{seller.name}</strong><small>مدیر فروشگاه</small></div>
          <button class="icon-button" aria-label="خروج از حساب" onclick={logout}
            ><Icon name="logout" size={17} /></button
          >
        </div>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="breadcrumb">
          <button
            class="icon-button mobile-menu"
            aria-label="باز کردن فهرست"
            onclick={() => (mobileNav = true)}><Icon name="menu" /></button
          ><span>میز کار</span><Icon name="chevron" size={12} /><strong
            >{active?.label || (path === '/settings' ? 'تنظیمات' : 'نمای کلی')}</strong
          >
        </div>
        <div class="topbar-left">
          {#if urgentUnread}<button
              class="urgent-notice"
              onclick={() => navigate('/notifications')}
              aria-label={'اعلان‌های فوری، ' + fa(urgentUnread) + ' مورد'}
              ><Icon name="alert" size={16} /><span class="urgent-copy">رسیدگی فوری</span><span
                aria-live="polite">{fa(urgentUnread)}</span
              ></button
            >{/if}
          <button
            class="btn secondary small theme-toggle"
            onclick={toggleTheme}
            aria-label={theme === 'light' ? 'فعال کردن حالت تاریک' : 'فعال کردن حالت روشن'}
            aria-pressed={theme === 'dark'}
            ><span aria-hidden="true">{theme === 'light' ? '☾' : '☀'}</span>{theme === 'light'
              ? 'تاریک'
              : 'روشن'}</button
          >
          <span class="connection"><i></i>فضای آزمایشی</span><span class="topbar-date"
            ><Icon name="calendar" size={15} />{date(new Date().toISOString())}</span
          ><button
            class="notification-button icon-button"
            aria-label="اعلان‌ها"
            onclick={() => navigate('/notifications')}
            ><Icon name="bell" />{#if unread}<i></i>{/if}</button
          >
        </div>
      </header>
      <main class="main-content">
        {#key path}
          {#if path === '/' || path === '/dashboard'}<Dashboard />
          {:else if /^\/orders\/\d+$/.test(path)}<OrderDetail id={+path.split('/')[2]} {notify} />
          {:else if path === '/orders'}<Orders />
          {:else if path === '/products'}<Products {notify} />
          {:else if path.startsWith('/customers')}<Customers id={path.split('/')[2]} {notify} />
          {:else if path === '/notifications'}<Notifications {notify} onread={refreshUnread} />
          {:else if path === '/conversations'}<Conversations {notify} />
          {:else if path === '/settings'}<Settings />
          {:else}<div class="empty">
              <h1>این صفحه پیدا نشد.</h1>
              <button class="btn" onclick={() => navigate('/dashboard')}>بازگشت به میز کار</button>
            </div>{/if}
        {/key}
        <footer class="workspace-footer">
          <span><Icon name="leaf" size={13} />با حوصله، برای سفارش‌های شما</span><span
            >پریسا · نسخهٔ آزمایشی ۰.۱</span
          >
        </footer>
      </main>
    </div>
  </div>
{/if}
{#if toast}<div class:error={toastError} class="toast" role="status">{toast}</div>{/if}

<style>
  .urgent-notice {
    display: flex;
    align-items: center;
    gap: 7px;
    min-height: 36px;
    border: 1px solid var(--red);
    border-radius: 8px;
    padding: 7px 10px;
    background: var(--paper);
    color: var(--red);
    font-size: 11px;
    white-space: nowrap;
  }
  @media (max-width: 700px) {
    .urgent-copy {
      display: none;
    }
    .urgent-notice {
      padding: 7px;
      gap: 4px;
    }
  }
  aside {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 238px;
    padding: 31px 20px 0;
    background: var(--tone-fcfdf9, #fcfdf9);
    border-left: 1px solid var(--tone-e7ece1, #e7ece1);
    z-index: 40;
    display: flex;
    flex-direction: column;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 0 15px;
    font-size: 27px;
    font-weight: 700;
    color: var(--tone-2d563f, #2d563f);
    letter-spacing: -0.5px;
  }
  .brand small {
    display: block;
    font-size: 9px;
    font-weight: 400;
    color: var(--tone-8b9980, #8b9980);
    letter-spacing: 0;
    margin-top: -2px;
  }
  .brand-mark {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 43px;
    height: 45px;
    background: var(--tone-e8efdf, #e8efdf);
    border-radius: 14px 14px 14px 3px;
    color: var(--tone-668453, #668453);
  }
  .shop-card {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--tone-fff, #fff);
    border: 1px solid var(--tone-e7ecdf, #e7ecdf);
    border-radius: 10px;
    padding: 12px 9px;
    margin: 30px 0;
  }
  .shop-card > :global(svg) {
    margin-right: auto;
    color: var(--tone-8e9b83, #8e9b83);
  }
  .shop-card strong {
    font-size: 10px;
    display: block;
  }
  .shop-card small {
    font-size: 8px;
    color: var(--tone-9ba48f, #9ba48f);
    display: block;
    margin-top: 5px;
  }
  .shop-avatar {
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--tone-f1efe2, #f1efe2);
    border: 1px solid var(--tone-e7e3d0, #e7e3d0);
    width: 32px;
    height: 32px;
    border-radius: 9px;
    color: var(--tone-aa9c73, #aa9c73);
  }
  .nav-caption {
    font-size: 9px;
    color: var(--tone-a0aa95, #a0aa95);
    padding: 0 14px;
    margin: 0 0 10px;
  }
  nav {
    display: grid;
    gap: 6px;
  }
  nav a {
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 12px 15px;
    border-radius: 8px;
    color: var(--tone-829078, #829078);
    font-size: 12px;
  }
  nav a:hover {
    background: var(--tone-f3f6ed, #f3f6ed);
  }
  nav a.active {
    background: var(--tone-eaf0e2, #eaf0e2);
    color: var(--tone-416536, #416536);
    font-weight: 600;
  }
  nav a.active :global(svg) {
    color: var(--tone-5e7d49, #5e7d49);
  }
  .nav-count {
    margin-right: auto;
    border-radius: 4px;
    font-weight: 400;
    background: var(--tone-dce7cf, #dce7cf);
    padding: 1px 6px;
    font-size: 9px;
  }
  .nav-bottom {
    margin-top: auto;
    padding-top: 25px;
  }
  .little-note {
    background: var(--tone-f1f4e9, #f1f4e9);
    border: 1px solid var(--tone-e9eddc, #e9eddc);
    border-radius: 11px;
    margin: 0 4px 22px;
    padding: 17px 14px;
    position: relative;
    overflow: hidden;
  }
  .little-leaf {
    position: absolute;
    left: 10px;
    top: 12px;
    color: var(--tone-b8c5a8, #b8c5a8);
    transform: rotate(-25deg);
  }
  .little-note strong {
    font-size: 10px;
    color: var(--tone-7a8e67, #7a8e67);
  }
  .little-note p {
    font-size: 10px;
    color: var(--tone-a0ac90, #a0ac90);
    margin: 8px 0 12px;
  }
  .little-note button {
    font-size: 9px;
    color: var(--tone-778d63, #778d63);
  }
  .settings-link {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 10px 14px 22px;
    font-size: 11px;
    color: var(--tone-8b9881, #8b9881);
  }
  .seller-card {
    border-top: 1px solid var(--tone-e7ecdf, #e7ecdf);
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 17px 5px;
  }
  .seller-card strong {
    display: block;
    font-size: 11px;
  }
  .seller-card small {
    display: block;
    color: var(--tone-9da792, #9da792);
    font-size: 9px;
    margin-top: 2px;
  }
  .seller-card button {
    margin-right: auto;
  }
  .workspace {
    margin-right: 238px;
    min-height: 100vh;
  }
  .topbar {
    height: 79px;
    border-bottom: 1px solid var(--tone-e7ece1, #e7ece1);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 38px;
    background: var(--tone-fdfefa99, #fdfefa99);
    gap: 15px;
  }
  .breadcrumb,
  .topbar-left {
    display: flex;
    align-items: center;
    gap: 14px;
    font-size: 10px;
    color: var(--tone-a0a894, #a0a894);
  }
  .breadcrumb strong {
    color: var(--tone-718266, #718266);
    font-weight: 400;
  }
  .topbar-left {
    gap: 23px;
  }
  .topbar-date {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 10px;
    color: var(--tone-9aa58c, #9aa58c);
  }
  .connection {
    font-size: 9px;
    color: var(--tone-8b9b7c, #8b9b7c);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .connection i {
    width: 5px;
    height: 5px;
    background: var(--tone-8ba477, #8ba477);
    border-radius: 50%;
  }
  .notification-button {
    position: relative;
    border: 1px solid var(--tone-e6ebdf, #e6ebdf);
    background: var(--tone-fcfdf9, #fcfdf9);
    border-radius: 9px;
  }
  .notification-button i {
    position: absolute;
    top: 8px;
    right: 10px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--tone-c49c70, #c49c70);
    border: 1px solid var(--tone-fff, #fff);
  }
  .main-content {
    padding: 31px 38px 0;
    max-width: 1740px;
    margin: auto;
  }
  .workspace-footer {
    display: flex;
    justify-content: space-between;
    gap: 15px;
    margin-top: 38px;
    padding: 22px 0;
    border-top: 1px solid var(--tone-e7ecdf, #e7ecdf);
    color: var(--tone-acb49f, #acb49f);
    font-size: 9px;
  }
  .workspace-footer span:first-child {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .mobile-menu {
    display: none;
  }
  .login-shell {
    display: grid;
    grid-template-columns: 1fr 1.1fr;
    min-height: 100vh;
    background: var(--tone-fafbf7, #fafbf7);
    direction: ltr;
  }
  .login-art {
    background: var(--tone-2c5240, #2c5240);
    color: var(--tone-e1e8d6, #e1e8d6);
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    direction: rtl;
    padding: 50px;
  }
  .login-art > span {
    font-size: 30px;
    margin-top: 25px;
    z-index: 1;
  }
  .login-art > p {
    font-size: 14px;
    line-height: 2.1;
    text-align: center;
    color: var(--tone-adc0a2, #adc0a2);
    margin-top: 15px;
    z-index: 1;
  }
  .login-art > small {
    position: absolute;
    bottom: 45px;
    color: var(--tone-9bb28d, #9bb28d);
    font-size: 10px;
  }
  .art-mark {
    color: var(--tone-b7c99f, #b7c99f);
    z-index: 1;
  }
  .art-rings {
    position: absolute;
    width: 650px;
    height: 650px;
    border: 1px solid var(--tone-ffffff0d, #ffffff0d);
    border-radius: 50%;
    bottom: -360px;
    left: -200px;
    box-shadow:
      0 0 0 70px var(--tone-ffffff03, #ffffff03),
      0 0 0 140px var(--tone-ffffff02, #ffffff02);
  }
  .login-content {
    direction: rtl;
    display: flex;
    flex-direction: column;
    padding: 45px 70px;
  }
  .login-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 23px;
    font-weight: 700;
  }
  .login-brand span {
    font-size: 10px;
    color: var(--tone-a4ae98, #a4ae98);
    font-weight: 400;
    margin-right: 10px;
  }
  .login-form {
    max-width: 350px;
    width: 100%;
    margin: auto;
    padding: 55px 0;
  }
  .login-form > p {
    font-size: 12px;
    margin-top: 9px;
  }
  .login-form form {
    margin: 30px 0 20px;
    display: grid;
    gap: 19px;
  }
  .login-form form > .btn {
    width: 100%;
    margin-top: 5px;
  }
  .demo-note {
    display: flex;
    gap: 9px;
    padding: 13px;
    background: var(--tone-f0f3e9, #f0f3e9);
    border-radius: 8px;
    margin-bottom: 22px;
    color: var(--tone-899877, #899877);
  }
  .demo-note p {
    font-size: 10px;
  }
  .demo-note :global(svg) {
    margin-top: 2px;
    flex-shrink: 0;
  }
  .demo-note small {
    font-size: 9px;
    color: var(--tone-a1aa92, #a1aa92);
  }
  .login-foot {
    font-size: 9px;
    color: var(--tone-a6b096, #a6b096);
    text-align: center;
  }
  .nav-shade {
    display: none;
  }
  @media (max-width: 1200px) {
    aside {
      width: 211px;
      padding: 25px 15px 0;
    }
    .workspace {
      margin-right: 211px;
    }
    .main-content {
      padding: 25px 24px 0;
    }
    .topbar {
      padding: 0 24px;
    }
    .little-note {
      margin-bottom: 15px;
    }
    .login-content {
      padding: 35px;
    }
  }
  @media (max-height: 780px) {
    .little-note {
      display: none;
    }
    .nav-bottom {
      padding-top: 10px;
    }
  }
  @media (max-width: 850px) {
    aside {
      display: none;
      width: 238px;
    }
    .workspace {
      margin-right: 0;
    }
    .mobile-open {
      display: flex;
    }
    .mobile-menu {
      display: flex;
    }
    .topbar {
      height: 65px;
      padding: 0 17px;
    }
    .topbar-left {
      gap: 12px;
    }
    .nav-shade {
      display: block;
      position: fixed;
      inset: 0;
      z-index: 39;
      background: var(--tone-19332166, #19332166);
      backdrop-filter: blur(2px);
    }
    .little-note {
      display: block;
    }
    .login-shell {
      grid-template-columns: 1fr;
    }
    .login-art {
      display: none;
    }
    .login-content {
      min-height: 100vh;
      padding: 30px;
    }
    .login-form {
      padding: 50px 0;
    }
  }
  @media (max-width: 550px) {
    .main-content {
      padding: 22px 15px 0;
    }
    .connection {
      display: none;
    }
    .topbar-date {
      font-size: 9px;
    }
    .breadcrumb {
      gap: 9px;
    }
    .workspace-footer {
      font-size: 8px;
    }
    .topbar-left {
      gap: 9px;
    }
  }
</style>
