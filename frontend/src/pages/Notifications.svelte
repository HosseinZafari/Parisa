<script>
  import { onMount } from 'svelte';
  import { api, date, fa, navigate } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  export let notify, onread;
  let items = [],
    error = '',
    onlyUnread = false,
    loading = true;
  async function load() {
    try {
      items = await api('/notifications');
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
  onMount(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  });
  async function readAll() {
    try {
      await api('/notifications/read-all', { method: 'POST' });
      await load();
      onread();
      notify('همهٔ اعلان‌ها خوانده شدند.');
    } catch (e) {
      notify(e.message, true);
    }
  }
  async function open(n) {
    try {
      if (!n.read) await api('/notifications/' + n.id + '/read', { method: 'POST' });
      onread();
      if (n.order_id) navigate('/orders/' + n.order_id);
      else navigate('/conversations');
    } catch (e) {
      notify(e.message, true);
    }
  }
  const iconFor = (kind) =>
    kind.includes('payment')
      ? 'wallet'
      : kind.includes('change')
        ? 'edit'
        : kind.includes('shipped')
          ? 'truck'
          : kind.includes('overdue')
            ? 'alert'
            : kind.includes('instagram')
              ? 'instagram'
              : 'bell';
  $: shown = items.filter((n) => !onlyUnread || !n.read);
</script>

<div class="page-heading">
  <div>
    <span class="eyebrow">اتفاق‌هایی که باید بدانی</span>
    <h1>
      اعلان‌های فروشگاه <span class="pill-count">{fa(items.filter((n) => !n.read).length)} نخوانده</span>
    </h1>
    <p>پرداخت‌ها، تغییرها و یادآوری موعدها؛ بدون نیاز به تازه‌کردن صفحه.</p>
  </div>
  <button class="btn secondary" onclick={readAll}><Icon name="check" size={17} />همه را خواندم</button>
</div>
<div class="tabs notification-tabs">
  <button class="tab" class:active={!onlyUnread} onclick={() => (onlyUnread = false)}>همهٔ اعلان‌ها</button
  ><button class="tab" class:active={onlyUnread} onclick={() => (onlyUnread = true)}>فقط نخوانده‌ها</button>
</div>
{#if error}<div class="error-banner">{error}</div>{/if}{#if loading}<div class="loading">
    <span class="spinner"></span>
  </div>{:else}<section class="panel">
    <div class="notification-list">
      {#each shown as n}<button class="notification-item" class:unread={!n.read} onclick={() => open(n)}
          ><span
            class="notification-icon"
            class:warning={n.kind.includes('overdue') || n.kind.includes('failed')}
            ><Icon name={iconFor(n.kind)} size={20} /></span
          ><span class="notification-copy"
            ><strong>{n.text}</strong><small>{date(n.created_at, true)}</small></span
          >{#if !n.read}<span class="unread-dot"></span>{/if}<Icon name="chevron" size={16} /></button
        >{:else}<div class="empty">
          <Icon name="bell" size={35} /><strong>اعلانی برای نمایش ندارید.</strong><span
            >خبرهای تازه اینجا به شما می‌رسند.</span
          >
        </div>{/each}
    </div>
  </section>{/if}

<style>
  .notification-tabs {
    margin-bottom: 20px;
  }
  .notification-item {
    background: #fff;
    width: 100%;
    display: flex;
    text-align: right;
    gap: 16px;
    padding: 21px 24px;
    border-bottom: 1px solid var(--line);
    justify-content: flex-start;
  }
  .notification-item:last-child {
    border-bottom: 0;
  }
  .notification-item.unread {
    background: #fbfcf6;
  }
  .notification-icon {
    width: 43px;
    height: 43px;
    display: grid;
    place-items: center;
    background: #eef3e7;
    border-radius: 12px;
    color: #92a97c;
    flex-shrink: 0;
  }
  .notification-icon.warning {
    background: #faf0e5;
    color: #c1a379;
  }
  .notification-copy {
    flex: 1;
  }
  .notification-copy strong {
    font-size: 12px;
    font-weight: 400;
    line-height: 1.9;
    display: block;
  }
  .notification-copy small {
    font-size: 9px;
    color: #a7b298;
    display: block;
    margin-top: 6px;
  }
  .notification-item > :global(svg) {
    color: #abb99e;
    flex-shrink: 0;
  }
  .unread-dot {
    width: 6px;
    height: 6px;
    background: #9cb482;
    border-radius: 50%;
    flex-shrink: 0;
  }
  @media (max-width: 650px) {
    .notification-item {
      padding: 17px 15px;
      gap: 10px;
    }
    .notification-copy strong {
      font-size: 11px;
    }
    .notification-icon {
      width: 35px;
      height: 35px;
    }
  }
</style>
