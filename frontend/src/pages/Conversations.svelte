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
    messageLog,
    detailLoading = false,
    detailError = '',
    unreadMessages = 0;
  let detailVersion = 0,
    disposed = false,
    refreshing = false;
  const drafts = new Map();
  const initialId = Number(new URLSearchParams(location.search).get('id')) || null;
  const isOpen = (c) => c?.attention_status === 'open';
  const isUrgent = (c) => isOpen(c) && c.attention_priority === 'urgent';
  function nearBottom() {
    return !messageLog || messageLog.scrollHeight - messageLog.scrollTop - messageLog.clientHeight < 90;
  }
  async function scrollToLatest() {
    await tick();
    if (messageLog) messageLog.scrollTop = messageLog.scrollHeight;
    unreadMessages = 0;
  }
  async function load() {
    if (refreshing || disposed) return;
    refreshing = true;
    try {
      const next = await api('/conversations');
      if (disposed) return;
      items = next;
      error = '';
      if (selected) {
        selected = items.find((c) => c.id === selected.id) || selected;
        await refreshDetail(selected.id);
      } else if (initialId) {
        const target = items.find((c) => c.id === initialId);
        if (target) await select(target);
      }
    } catch (e) {
      error = e.message;
    } finally {
      refreshing = false;
    }
  }
  async function refreshDetail(id, scroll = false) {
    const version = ++detailVersion;
    const follow = scroll || nearBottom();
    const previous = detail?.id === id ? detail.messages : [];
    try {
      const next = await api('/conversations/' + id);
      if (disposed || version !== detailVersion || selected?.id !== id) return;
      const known = new Set(previous.map((m) => m.id));
      const added = next.messages.filter((m) => !known.has(m.id)).length;
      detail = next;
      detailError = '';
      detailLoading = false;
      if (follow) await scrollToLatest();
      else unreadMessages += added;
    } catch (e) {
      if (version !== detailVersion || selected?.id !== id) return;
      detailError = e.message;
      detailLoading = false;
    }
  }
  async function select(c) {
    if (selected?.id !== c.id) {
      if (selected) drafts.set(selected.id, text);
      text = drafts.get(c.id) || '';
      resume = false;
      detail = null;
      unreadMessages = 0;
    }
    selected = c;
    detailLoading = true;
    history.replaceState({}, '', '/conversations?id=' + c.id);
    await refreshDetail(c.id, true);
  }
  onMount(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => {
      disposed = true;
      detailVersion++;
      clearInterval(interval);
    };
  });
  async function reply(e) {
    e.preventDefault();
    if (!selected || busy || !text.trim()) return;
    const id = selected.id,
      submitted = text;
    busy = true;
    try {
      await api('/conversations/' + id + '/reply', {
        method: 'POST',
        body: { text: submitted, resume_bot: resume },
      });
      drafts.delete(id);
      if (selected?.id === id && text === submitted) text = '';
      notify('پاسخ ذخیره شد.');
      if (selected?.id === id) await refreshDetail(id, true);
      await load();
    } catch (e) {
      notify(e.message, true);
    } finally {
      busy = false;
    }
  }
  async function attention(action, resumeBot = false) {
    if (!selected || busy) return;
    const id = selected.id;
    busy = true;
    try {
      await api('/conversations/' + id + '/attention', {
        method: 'POST',
        body: { action, resume_bot: resumeBot },
      });
      notify(
        resumeBot
          ? 'دستیار دوباره فعال شد.'
          : action === 'take_over'
            ? 'گفتگو در اختیار شماست.'
            : action === 'reopen'
              ? 'رسیدگی دوباره باز شد.'
              : 'رسیدگی ثبت شد.',
      );
      if (selected?.id === id) await refreshDetail(id);
      await load();
    } catch (e) {
      notify(e.message, true);
    } finally {
      busy = false;
    }
  }
  $: shown = items
    .filter((c) => [c.customer_name, c.customer_username, c.last_message].some((v) => v.includes(search)))
    .sort((a, b) => Number(isUrgent(b)) - Number(isUrgent(a)) || Number(isOpen(b)) - Number(isOpen(a)));
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
          {#if isOpen(c)}<span class="attention-badge" class:urgent={isUrgent(c)}
              >{isUrgent(c) ? 'فوری' : 'نیازمند رسیدگی'}</span
            >{:else if c.attention_status === 'resolved'}<span class="resolved-label">رسیدگی‌شده</span>{/if}
        </div>
        {#if isOpen(c)}<span class="handover-dot" class:urgent={isUrgent(c)} title="نیازمند پاسخ فروشنده"
          ></span>{/if}</button
      >{:else}<div class="empty">گفتگویی پیدا نشد.</div>{/each}
  </div>
  <section class="conversation-detail">
    {#if selected}<div class="conversation-head">
        <div>
          <h2>{selected.customer_name}</h2>
          <small>{detail?.handover ? 'گفتگو در اختیار فروشنده است' : 'پاسخ‌گویی خودکار فعال است'}</small>
        </div>
        {#if detail?.order_id}<button
            class="text-button"
            onclick={() => navigate('/orders/' + detail.order_id)}
            >سفارش <bdi>#{fa(1000 + detail.order_id)}</bdi><Icon name="arrow" size={14} /></button
          >{/if}
      </div>
      {#if detail && isOpen(detail)}<div class="attention-notice" class:urgent={isUrgent(detail)}>
          <strong
            >{isUrgent(detail)
              ? 'این گفتگو به رسیدگی فوری نیاز دارد.'
              : 'مشتری منتظر رسیدگی فروشنده است.'}</strong
          >
          {#if detail.handover_reason}<p>{detail.handover_reason}</p>{/if}
          <div>
            {#if !detail.handover}<button
                class="btn secondary small"
                disabled={busy}
                onclick={() => attention('take_over')}>شروع رسیدگی</button
              >{/if}<button class="btn secondary small" disabled={busy} onclick={() => attention('resolve')}
              >رسیدگی شد</button
            ><button class="text-button" disabled={busy} onclick={() => attention('resolve', true)}
              >رسیدگی شد؛ دستیار ادامه دهد</button
            >
          </div>
        </div>{:else if detail?.attention_status === 'resolved'}<div class="resolved-notice">
          <span
            >رسیدگی‌شده{#if detail.attention_resolved_at}
              · {date(detail.attention_resolved_at, true)}{/if}</span
          >{#if detail.handover}<button
              class="text-button"
              disabled={busy}
              onclick={() => attention('resolve', true)}>فعال‌کردن دستیار</button
            >{/if}<button class="text-button" disabled={busy} onclick={() => attention('reopen')}
            >بازکردن دوبارهٔ رسیدگی</button
          >
        </div>{/if}
      {#if detailError}<div class="detail-error error-banner" role="alert">
          {detailError}<button class="text-button" onclick={() => refreshDetail(selected.id, true)}
            >تلاش دوباره</button
          >
        </div>{/if}
      <div
        class="conversation-messages"
        bind:this={messageLog}
        role="log"
        aria-label="پیام‌های گفتگو"
        aria-live="polite"
        onscroll={() => {
          if (nearBottom()) unreadMessages = 0;
        }}
      >
        {#if detailLoading && !detail}<div class="conversation-loading" role="status">
            <span class="spinner"></span>در حال دریافت گفتگو…
          </div>{/if}
        {#each detail?.messages || [] as m (m.id)}<div
            class="seller-message"
            class:customer={m.role === 'customer'}
            class:assistant={m.role === 'assistant'}
            class:seller={m.role === 'seller'}
            data-message-role={m.role}
          >
            <small
              >{#if m.role === 'assistant'}<Icon name="leaf" size={12} />{/if}{m.role === 'customer'
                ? 'مشتری'
                : m.role === 'seller'
                  ? 'فروشنده'
                  : 'دستیار هوش مصنوعی'}</small
            >
            <p>{m.text}</p>
            <time
              >{date(m.created_at, true)}{#if ['blocked', 'unknown'].includes(m.delivery_status)}
                · تحویل نیازمند بررسی{/if}</time
            >
          </div>{/each}
      </div>
      {#if unreadMessages}<button class="new-messages" onclick={scrollToLatest}
          >{fa(unreadMessages)} پیام تازه · رفتن به آخر گفتگو<Icon name="down" size={14} /></button
        >{/if}
      {#if detail}
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
        </form>{/if}{:else}<div class="empty choose-chat">
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
    min-height: 0;
    border-left: 1px solid var(--line);
  }
  .list-search {
    padding: 16px;
    position: sticky;
    top: 0;
    background: var(--tone-fff, #fff);
    z-index: 1;
  }
  .conversation-row {
    width: 100%;
    text-align: right;
    justify-content: flex-start;
    gap: 10px;
    background: var(--tone-fff, #fff);
    padding: 18px 16px;
    border-bottom: 1px solid var(--line);
  }
  .conversation-row.active {
    background: var(--tone-f0f5e9, #f0f5e9);
  }
  .conversation-row > div {
    min-width: 0;
  }
  .conversation-row strong {
    font-size: 11px;
  }
  .conversation-row p {
    font-size: 10px;
    color: var(--tone-a1ae91, #a1ae91);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 180px;
    margin-top: 5px;
  }
  .conversation-row small {
    font-size: 8px;
    color: var(--tone-afbaa0, #afbaa0);
    display: block;
    margin-top: 8px;
  }
  .handover-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--tone-c6a279, #c6a279);
    margin-right: auto;
    flex-shrink: 0;
  }
  .handover-dot.urgent {
    background: var(--red);
  }
  .attention-badge {
    display: inline-block;
    margin-top: 8px;
    padding: 3px 7px;
    border-radius: 5px;
    font-size: 9px;
    background: var(--mint);
    color: var(--green);
  }
  .attention-badge.urgent {
    color: var(--red);
    border: 1px solid currentColor;
    background: transparent;
  }
  .resolved-label {
    display: block;
    margin-top: 7px;
    font-size: 9px;
    color: var(--muted);
  }
  .conversation-detail {
    min-width: 0;
    min-height: 0;
    overflow: hidden;
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
    flex-shrink: 0;
  }
  .conversation-head h2 {
    font-size: 13px;
  }
  .conversation-head small {
    font-size: 9px;
    color: var(--tone-9fac92, #9fac92);
    display: block;
    margin-top: 5px;
  }
  .conversation-head .text-button {
    font-size: 10px;
  }
  .conversation-messages {
    flex: 1;
    min-height: 0;
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
    background: var(--tone-f0f4e8, #f0f4e8);
    flex-shrink: 0;
    border: 1px solid var(--line);
  }
  .seller-message.assistant {
    border-inline-start: 3px solid var(--green);
    background: var(--mint);
  }
  .seller-message.seller {
    background: var(--paper);
  }
  .seller-message.customer {
    background: var(--tone-f7f3ed, #f7f3ed);
    align-self: flex-end;
  }
  .seller-message > small {
    font-size: 10px;
    color: var(--green);
    display: flex;
    align-items: center;
    gap: 5px;
    margin-bottom: 5px;
  }
  .seller-message p {
    font-size: 12px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .seller-message time {
    font-size: 8px;
    color: var(--tone-b0bca1, #b0bca1);
    display: block;
    margin-top: 7px;
  }
  .reply-form {
    padding: 18px;
    border-top: 1px solid var(--line);
    flex-shrink: 0;
  }
  .attention-notice {
    margin: 14px 18px 0;
    padding: 13px 15px;
    border: 1px solid var(--line);
    border-radius: 9px;
    background: var(--mint);
    flex-shrink: 0;
  }
  .attention-notice.urgent {
    border-color: var(--red);
  }
  .attention-notice strong {
    display: block;
    font-size: 12px;
    color: var(--green);
  }
  .attention-notice.urgent strong {
    color: var(--red);
  }
  .attention-notice p {
    font-size: 11px;
    color: var(--muted);
    margin-top: 7px;
  }
  .attention-notice > div {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 12px;
  }
  .attention-notice .text-button {
    font-size: 10px;
  }
  .resolved-notice {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    padding: 12px 18px;
    font-size: 10px;
    color: var(--muted);
    border-bottom: 1px solid var(--line);
    flex-shrink: 0;
  }
  .resolved-notice .text-button {
    font-size: 10px;
  }
  .new-messages {
    align-self: center;
    flex-shrink: 0;
    background: var(--green);
    color: var(--paper);
    border-radius: 20px;
    padding: 8px 15px;
    margin: 0 12px 10px;
    font-size: 11px;
  }
  .detail-error {
    margin: 12px 18px;
    flex-shrink: 0;
  }
  .conversation-loading {
    margin: auto;
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--muted);
    font-size: 12px;
    padding: 35px 15px;
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
    color: var(--tone-9dad8d, #9dad8d);
    margin: 0;
  }
  .check-label input {
    width: 14px;
    min-height: 14px;
    accent-color: var(--tone-7a9a65, #7a9a65);
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
      flex: initial;
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
