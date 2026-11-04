<script>
  import { onMount, tick } from 'svelte';
  import { api, date, fa, navigate } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  export let notify;
  let items = [],
    selected = null,
    detail = null,
    text = '',
    resume = false,
    error = '',
    busy = false,
    search = '',
    messageLog;
  async function load() {
    try {
      items = await api('/conversations');
      if (selected) await select(items.find((c) => c.id === selected.id) || selected, false);
    } catch (e) {
      error = e.message;
    }
  }
  async function select(c, scroll = true) {
    selected = c;
    try {
      detail = await api('/conversations/' + c.id);
      if (scroll) {
        await tick();
        if (messageLog) messageLog.scrollTop = messageLog.scrollHeight;
      }
    } catch (e) {
      notify(e.message, true);
    }
  }
  onMount(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  });
  async function reply(e) {
    e.preventDefault();
    busy = true;
    try {
      await api('/conversations/' + selected.id + '/reply', {
        method: 'POST',
        body: { text, resume_bot: resume },
      });
      text = '';
      notify('پاسخ ذخیره شد.');
      await load();
      await tick();
      if (messageLog) messageLog.scrollTop = messageLog.scrollHeight;
    } catch (e) {
      notify(e.message, true);
    } finally {
      busy = false;
    }
  }
  $: shown = items
    .filter((c) => [c.customer_name, c.customer_username, c.last_message].some((v) => v.includes(search)))
    .sort((a, b) => Number(b.handover) - Number(a.handover));
</script>

<div class="page-heading">
  <div>
    <span class="eyebrow">همهٔ سلام‌ها، در یک جا</span>
    <h1>گفتگوهای مشتری‌ها</h1>
    <p>گفتگوهای واگذارشده به شما، بالاتر از بقیه نمایش داده می‌شوند.</p>
  </div>
  <button class="btn secondary" onclick={() => navigate('/chat')}
    ><Icon name="chat" size={16} />گفتگوی آزمایشی</button
  >
</div>
{#if error}<div class="error-banner">{error}</div>{/if}
<div class="conversation-layout panel">
  <div class="conversation-list">
    <div class="list-search">
      <div class="search-box">
        <Icon name="search" size={16} /><input
          aria-label="جستجوی گفتگو"
          bind:value={search}
          placeholder="جستجو در گفتگوها…"
        />
      </div>
    </div>
    {#each shown as c}<button
        class="conversation-row"
        class:active={selected?.id === c.id}
        onclick={() => select(c)}
        ><span class="avatar tone-{c.id % 4}">{c.customer_name.slice(0, 1)}</span>
        <div>
          <strong>{c.customer_name}</strong>
          <p>{c.last_message}</p>
          <small>{c.channel === 'instagram' ? 'اینستاگرام' : 'گفتگوی محلی'} · {date(c.updated_at)}</small>
        </div>
        {#if c.handover}<span class="handover-dot" title="نیازمند پاسخ فروشنده"></span>{/if}</button
      >{:else}<div class="empty">گفتگویی پیدا نشد.</div>{/each}
  </div>
  <section class="conversation-detail">
    {#if selected && detail}<div class="conversation-head">
        <div>
          <h2>{selected.customer_name}</h2>
          <small>{detail.handover ? 'گفتگو در اختیار فروشنده است' : 'پاسخ‌گویی خودکار فعال است'}</small>
        </div>
        {#if detail.order_id}<button
            class="text-button"
            onclick={() => navigate('/orders/' + detail.order_id)}
            >سفارش <bdi>#{fa(1000 + detail.order_id)}</bdi><Icon name="arrow" size={14} /></button
          >{/if}
      </div>
      <div class="conversation-messages" bind:this={messageLog}>
        {#each detail.messages as m}<div class="seller-message" class:customer={m.role === 'customer'}>
            <small>{m.role === 'customer' ? 'مشتری' : m.role === 'seller' ? 'شما' : 'دستیار'}</small>
            <p>{m.text}</p>
            <time
              >{date(m.created_at, true)}{#if ['blocked', 'unknown'].includes(m.delivery_status)}
                · تحویل نیازمند بررسی{/if}</time
            >
          </div>{/each}
      </div>
      <form class="reply-form" onsubmit={reply}>
        <label for="reply">پاسخ شما به مشتری</label><textarea
          id="reply"
          bind:value={text}
          required
          maxlength="2000"
          rows="2"
          placeholder="با حوصله برای مشتری بنویس…"></textarea>
        <div>
          <label class="check-label"
            ><input type="checkbox" bind:checked={resume} />پس از پاسخ، دستیار دوباره فعال شود</label
          ><button class="btn" disabled={busy || !text.trim()}
            ><Icon name="send" size={16} />ارسال پاسخ</button
          >
        </div>
      </form>{:else}<div class="empty choose-chat">
        <Icon name="chat" size={46} /><strong>یک گفتگو انتخاب کنید.</strong><span
          >پیام‌ها و سفارش مرتبط را همین‌جا می‌بینید.</span
        >
      </div>{/if}
  </section>
</div>

<style>
  .conversation-layout {
    display: grid;
    grid-template-columns: 300px 1fr;
    min-height: 620px;
    height: 70vh;
    max-height: 850px;
  }
  .conversation-list {
    overflow: auto;
    border-left: 1px solid var(--line);
  }
  .list-search {
    padding: 16px;
    position: sticky;
    top: 0;
    background: #fff;
    z-index: 1;
  }
  .conversation-row {
    width: 100%;
    text-align: right;
    justify-content: flex-start;
    gap: 10px;
    background: #fff;
    padding: 18px 16px;
    border-bottom: 1px solid var(--line);
  }
  .conversation-row.active {
    background: #f0f5e9;
  }
  .conversation-row > div {
    min-width: 0;
  }
  .conversation-row strong {
    font-size: 11px;
  }
  .conversation-row p {
    font-size: 10px;
    color: #a1ae91;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 180px;
    margin-top: 5px;
  }
  .conversation-row small {
    font-size: 8px;
    color: #afbaa0;
    display: block;
    margin-top: 8px;
  }
  .handover-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #c6a279;
    margin-right: auto;
    flex-shrink: 0;
  }
  .conversation-detail {
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .conversation-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding: 20px;
    border-bottom: 1px solid var(--line);
  }
  .conversation-head h2 {
    font-size: 13px;
  }
  .conversation-head small {
    font-size: 9px;
    color: #9fac92;
    display: block;
    margin-top: 5px;
  }
  .conversation-head .text-button {
    font-size: 10px;
  }
  .conversation-messages {
    flex: 1;
    overflow: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 13px;
  }
  .seller-message {
    max-width: 88%;
    width: max-content;
    padding: 13px 16px;
    border-radius: 11px;
    background: #f0f4e8;
  }
  .seller-message.customer {
    background: #f7f3ed;
    align-self: flex-end;
  }
  .seller-message > small {
    font-size: 8px;
    color: #9eaf8c;
  }
  .seller-message p {
    font-size: 11px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .seller-message time {
    font-size: 8px;
    color: #b0bca1;
    display: block;
    margin-top: 7px;
  }
  .reply-form {
    padding: 18px;
    border-top: 1px solid var(--line);
  }
  .reply-form textarea {
    font-size: 11px;
  }
  .reply-form > div {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    margin-top: 12px;
  }
  .check-label {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 9px;
    color: #9dad8d;
    margin: 0;
  }
  .check-label input {
    width: 14px;
    min-height: 14px;
    accent-color: #7a9a65;
  }
  .choose-chat {
    margin: auto;
  }
  @media (max-width: 1050px) {
    .conversation-layout {
      grid-template-columns: 240px 1fr;
    }
    .conversation-row p {
      max-width: 140px;
    }
  }
  @media (max-width: 700px) {
    .conversation-layout {
      display: block;
      height: auto;
      min-height: 0;
    }
    .conversation-list {
      max-height: 250px;
      border-left: 0;
      border-bottom: 1px solid var(--line);
    }
    .conversation-messages {
      max-height: 450px;
      min-height: 300px;
    }
    .conversation-row p {
      max-width: 100%;
    }
    .reply-form > div {
      flex-wrap: wrap;
    }
    .choose-chat {
      padding: 50px 20px;
    }
  }
</style>
