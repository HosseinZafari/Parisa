<script>
  import { onMount, tick } from 'svelte';
  import { api, date, money, fa, navigate } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  import Status from '../components/Status.svelte';
  let chat,
    products = [],
    message = '',
    sending = false,
    error = '',
    log,
    loading = true;
  let pendingMessage = null;
  const examples = [
    'دو عدد شمع آوا، رایحه وانیل، بزرگ، بسته‌بندی هدیه',
    'یک عدد صابون باران، نوع زیتون، بسته‌بندی معمولی',
    'فروشنده',
  ];
  async function scroll() {
    await tick();
    if (log) log.scrollTop = log.scrollHeight;
  }
  async function start() {
    error = '';
    try {
      chat = await api('/chat/start', { method: 'POST', body: {} });
      localStorage.setItem('parisa-chat', chat.token);
      await scroll();
    } catch (e) {
      error = e.message;
    }
  }
  onMount(() => {
    let alive = true;
    const init = async () => {
      try {
        products = await api('/catalog');
        const token = localStorage.getItem('parisa-chat');
        if (token) {
          try {
            chat = await api('/chat/' + token);
          } catch {
            await start();
          }
        } else await start();
        await scroll();
      } catch (e) {
        error = e.message;
      } finally {
        loading = false;
      }
    };
    init();
    const poll = setInterval(async () => {
      if (!chat || sending) return;
      try {
        const state = await api('/chat/' + chat.token);
        if (alive) {
          const changed = state.messages.length !== chat.messages.length;
          chat = state;
          if (changed) scroll();
        }
      } catch {}
    }, 7000);
    return () => {
      alive = false;
      clearInterval(poll);
    };
  });
  async function send(text = message) {
    if (!text.trim() || sending || !chat) return;
    sending = true;
    error = '';
    const actual = text.trim();
    if (!pendingMessage || pendingMessage.text !== actual)
      pendingMessage = { text: actual, client_id: crypto.randomUUID() };
    try {
      chat = await api('/chat/' + chat.token + '/messages', { method: 'POST', body: pendingMessage });
      message = '';
      pendingMessage = null;
      await scroll();
    } catch (e) {
      error = e.message;
    } finally {
      sending = false;
    }
  }
  function submit(e) {
    e.preventDefault();
    send();
  }
</script>

<div class="chat-page">
  <header class="chat-header">
    <a
      href="/dashboard"
      onclick={(e) => {
        e.preventDefault();
        navigate('/dashboard');
      }}
      class="chat-brand"
      ><Icon name="leaf" size={26} /><strong>پریسا</strong><span>یک گفتگوی کوچک، یک سفارش مرتب</span></a
    ><button
      class="btn secondary small"
      onclick={() => {
        pendingMessage = null;
        start();
      }}>گفتگوی تازه<Icon name="plus" size={15} /></button
    >
  </header>
  <main class="chat-layout">
    <aside class="chat-catalog">
      <span class="eyebrow">با سلیقهٔ شما</span>
      <h1>از کجا شروع کنیم؟</h1>
      <p>محصولی انتخاب کن یا برایمان بنویس چه چیزی در ذهن داری.</p>
      <div class="chat-products">
        {#each products as product}<button
            onclick={() => send('می‌خواهم ' + product.name + ' سفارش بدهم')}
            disabled={sending}
            ><span class="product-symbol {product.color}"><Icon name="box" size={22} /></span><span
              ><strong>{product.name}</strong><small>{money(product.price)}</small></span
            ><Icon name="chevron" size={14} /></button
          >{/each}
      </div>
      <div class="chat-safety">
        <Icon name="lock" size={18} />
        <p>این فضا برای آزمایش است. از اطلاعات ساختگی استفاده کن. تمام پرداخت‌ها شبیه‌سازی می‌شوند.</p>
      </div>
      <button class="text-button" onclick={() => navigate('/dashboard')}
        >ورود به میز کار فروشنده<Icon name="arrow" size={14} /></button
      >
    </aside>
    <section class="chat-window">
      <div class="chat-window-head">
        <span class="avatar"><Icon name="leaf" size={20} /></span>
        <div>
          <strong>{chat?.handover ? 'گفتگو با فروشنده' : 'دستیار سفارش پریسا'}</strong><small
            ><i></i>{chat?.handover
              ? 'پیام‌ها برای فروشنده ذخیره می‌شوند'
              : 'همراه شما تا تکمیل سفارش'}</small
          >
        </div>
        <span class="tag">گفتگوی آزمایشی</span>
      </div>
      <div class="chat-log" bind:this={log} aria-live="polite" aria-relevant="additions">
        <div class="chat-date">امروز · یک شروع تازه</div>
        {#if loading}<div class="loading"><span class="spinner"></span>در حال آماده‌سازی گفتگو…</div>{/if}
        {#each chat?.messages || [] as m}<div class="message-wrap" class:customer={m.role === 'customer'}>
            <div class="message-bubble">
              <p>{m.text}</p>
              <small>{m.role === 'seller' ? 'فروشنده · ' : ''}{date(m.created_at, true)}</small>
            </div>
          </div>{/each}
        {#if chat?.summary && !chat.order}<div class="chat-summary">
            <div class="summary-heading">
              <Icon name="orders" size={18} /><strong>خلاصهٔ سفارش شما</strong>
            </div>
            <div class="summary-item">
              <span>{chat.summary.product_name}</span><strong>{fa(chat.summary.quantity)} عدد</strong>
            </div>
            {#each chat.summary.requirement_schema as r}{#if chat.summary.specifications[r.key]}<div
                  class="summary-item"
                >
                  <span>{r.label}</span><strong>{chat.summary.specifications[r.key]}</strong>
                </div>{/if}{/each}
            <hr />
            {#each [['name', 'گیرنده'], ['phone', 'همراه'], ['city', 'شهر'], ['address', 'نشانی'], ['postal_code', 'کد پستی'], ['notes', 'یادداشت ارسال']] as [key, label]}{#if chat.summary.delivery[key]}<div
                  class="summary-item"
                >
                  <span>{label}</span><strong>{chat.summary.delivery[key]}</strong>
                </div>{/if}{/each}
            <hr />
            <div class="summary-item">
              <span>قیمت واحد</span><strong>{money(chat.summary.unit_price)}</strong>
            </div>
            <div class="summary-item">
              <span>هزینهٔ ارسال</span><strong>{money(chat.summary.shipping_cost)}</strong>
            </div>
            <div class="summary-item">
              <span>موعد آماده‌سازی / ارسال</span><strong>{date(chat.summary.deadline)}</strong>
            </div>
            <div class="summary-item total">
              <span>مبلغ کل</span><strong>{money(chat.summary.total)}</strong>
            </div>
            {#if chat.summary.missing.length}<p class="summary-missing">
                اطلاعات باقی‌مانده: {chat.summary.missing.join('، ')}
              </p>{/if}{#if chat.ready_to_confirm}<button
                class="btn"
                disabled={sending}
                onclick={() => send('تأیید سفارش')}
                >تأیید خلاصه و دریافت پیوند پرداخت<Icon name="check" size={16} /></button
              ><small class="summary-hint">تأیید شما شامل مشخصات، نشانی و مبلغ بالا است.</small>{/if}
          </div>{/if}
        {#if chat?.order}<div class="chat-summary">
            <div class="summary-heading">
              <Icon name="check" size={18} /><strong
                >سفارش <bdi>#{fa(1000 + chat.order.id)}</bdi> ثبت شد.</strong
              >
            </div>
            <Status status={chat.order.status} />
            <div class="summary-item total">
              <span>مبلغ سفارش</span><strong>{money(chat.order.total)}</strong>
            </div>
            <div class="order-links">
              {#if chat.payment}<a class="btn" href={chat.payment.url}
                  >پرداخت آزمایشی<Icon name="wallet" size={15} /></a
                >{/if}{#if chat.tracking_url}<a class="btn secondary" href={chat.tracking_url}
                  >پیگیری خصوصی<Icon name="link" size={15} /></a
                >{/if}
            </div>
            <p class="summary-hint">
              برای اصلاح، مقدار تازه را بنویسید. برای سفارش تکراری، ابتدا «سفارش جدید» و سپس «تکرار سفارش» را
              بفرستید.
            </p>
          </div>{/if}
        {#if sending}<div class="typing"><span></span><span></span><span></span></div>{/if}
      </div>
      {#if error}<div class="chat-error error-banner" role="alert">{error}</div>{/if}
      {#if chat?.messages.length < 3}<div class="quick-examples">
          {#each examples as example}<button disabled={sending} onclick={() => send(example)}
              >{example}</button
            >{/each}
        </div>{/if}
      <form class="chat-compose" onsubmit={submit}>
        <textarea
          bind:value={message}
          aria-label="پیام شما"
          rows="2"
          maxlength="2000"
          placeholder="پیامت را اینجا بنویس…"
          onkeydown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}></textarea><button
          class="send-button"
          disabled={sending || !message.trim() || !chat}
          aria-label="ارسال پیام"><Icon name="send" size={21} /></button
        >
      </form>
      <div class="compose-hint">
        نام و نشانی را می‌توانی با این قالب بفرستی: نام: سارا؛ شهر: تهران؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد
        پستی: ۱۱۱۱۱۱۱۱۱۱
      </div>
    </section>
  </main>
</div>

<style>
  .chat-page {
    min-height: 100vh;
    background: #f6f8f2;
  }
  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #e5ebdd;
    padding: 20px max(25px, 5vw);
    background: #fdfefa;
  }
  .chat-brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .chat-brand strong {
    font-size: 23px;
  }
  .chat-brand > span {
    font-size: 10px;
    color: #a2af93;
    margin-right: 20px;
  }
  .chat-layout {
    max-width: 1220px;
    margin: auto;
    display: grid;
    grid-template-columns: 300px 1fr;
    gap: 45px;
    padding: 35px 25px;
  }
  .chat-catalog {
    padding: 20px 0;
  }
  .chat-catalog h1 {
    font-size: 25px;
  }
  .chat-catalog > p {
    font-size: 12px;
    color: #9ba88e;
    margin: 10px 0 25px;
  }
  .chat-products {
    display: grid;
    gap: 10px;
  }
  .chat-products button {
    display: flex;
    justify-content: flex-start;
    gap: 10px;
    padding: 14px;
    background: #fff;
    border: 1px solid #e7ebdf;
    border-radius: 10px;
    text-align: right;
  }
  .product-symbol {
    width: 42px;
    height: 45px;
    background: #f3eee3;
    color: #c0b18d;
    display: grid;
    place-items: center;
    border-radius: 9px;
  }
  .product-symbol.sage {
    background: #eef3e7;
    color: #9db38c;
  }
  .product-symbol.rose {
    background: #f6ebe6;
    color: #c8a99a;
  }
  .product-symbol.lilac {
    background: #efecf5;
    color: #b3a6c8;
  }
  .chat-products strong {
    display: block;
    font-size: 11px;
  }
  .chat-products small {
    display: block;
    color: #a0ae91;
    font-size: 10px;
    margin-top: 5px;
  }
  .chat-products button > :global(svg) {
    margin-right: auto;
    color: #b1bda6;
  }
  .chat-safety {
    display: flex;
    gap: 10px;
    margin: 30px 0 24px;
    padding: 15px;
    background: #eff3e7;
    color: #9ba98c;
    border-radius: 9px;
  }
  .chat-safety :global(svg) {
    flex-shrink: 0;
    margin-top: 3px;
  }
  .chat-safety p {
    font-size: 10px;
  }
  .chat-catalog > .text-button {
    font-size: 10px;
  }
  .chat-window {
    background: #fff;
    border: 1px solid #e4eadb;
    border-radius: 16px;
    display: flex;
    flex-direction: column;
    height: calc(100vh - 160px);
    min-height: 600px;
    max-height: 1000px;
    overflow: hidden;
    box-shadow: 0 10px 40px #42632804;
  }
  .chat-window-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 19px 23px;
    border-bottom: 1px solid #edf0e6;
  }
  .chat-window-head strong {
    font-size: 12px;
    display: block;
  }
  .chat-window-head small {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 9px;
    color: #a0af91;
    margin-top: 4px;
  }
  .chat-window-head small i {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #9db585;
  }
  .chat-window-head .tag {
    margin-right: auto;
    font-size: 8px;
  }
  .chat-log {
    padding: 23px 24px;
    flex: 1;
    overflow: auto;
    scroll-behavior: smooth;
    background: linear-gradient(#fdfefa, #fff);
  }
  .chat-date {
    text-align: center;
    font-size: 9px;
    color: #bac3ae;
    margin: 0 0 25px;
  }
  .message-wrap {
    display: flex;
    margin-bottom: 15px;
    justify-content: flex-start;
  }
  .message-wrap.customer {
    justify-content: flex-end;
  }
  .message-bubble {
    max-width: 88%;
    background: #eef3e6;
    border: 1px solid #e7eddf;
    padding: 13px 17px;
    border-radius: 12px 3px 12px 12px;
  }
  .customer .message-bubble {
    background: #f7f4ee;
    border: 1px solid #f0ece4;
    border-radius: 3px 12px 12px 12px;
  }
  .message-bubble p {
    font-size: 12px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    line-height: 2;
  }
  .message-bubble small {
    display: block;
    font-size: 8px;
    color: #acb89e;
    margin-top: 8px;
    text-align: left;
  }
  .chat-compose {
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 16px 19px 10px;
    border-top: 1px solid #edf0e6;
    background: #fff;
  }
  .chat-compose textarea {
    border: 0;
    background: #f7f9f2;
    border-radius: 10px;
    outline: none;
    font-size: 12px;
    resize: none;
    padding: 12px 15px;
  }
  .send-button {
    width: 46px;
    height: 46px;
    flex-shrink: 0;
    background: #678750;
    color: #fff;
    border-radius: 12px;
  }
  .send-button:disabled {
    background: #c6d3ba;
  }
  .compose-hint {
    font-size: 8px;
    color: #aeb8a2;
    padding: 0 22px 15px;
    line-height: 1.9;
  }
  .quick-examples {
    padding: 0 22px 14px;
    display: flex;
    gap: 7px;
    flex-wrap: wrap;
  }
  .quick-examples button {
    font-size: 9px;
    padding: 6px 9px;
    border-radius: 6px;
    border: 1px solid #e6eddd;
    background: #fbfdf7;
    color: #95a581;
  }
  .chat-summary {
    background: #fff;
    border: 1px solid #dce6d1;
    border-radius: 12px;
    padding: 21px;
    margin: 20px 0;
    max-width: 100%;
    box-shadow: 0 4px 18px #526e3105;
  }
  .summary-heading {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 20px;
    color: #789363;
    font-size: 12px;
  }
  .summary-item {
    display: flex;
    gap: 15px;
    justify-content: space-between;
    font-size: 11px;
    margin: 10px 0;
    line-height: 1.9;
  }
  .summary-item > span {
    color: #a3b092;
    flex-shrink: 0;
  }
  .summary-item strong {
    text-align: left;
    overflow-wrap: anywhere;
  }
  .summary-item.total {
    padding-top: 14px;
    border-top: 1px dashed #dce6d1;
    color: #63834c;
    margin: 18px 0 20px;
    font-size: 13px;
  }
  .summary-item.total > span {
    color: #81966d;
  }
  .summary-missing {
    font-size: 10px;
    color: #b39b70;
    background: #faf5e9;
    padding: 10px;
    border-radius: 7px;
  }
  .chat-summary > .btn {
    width: 100%;
  }
  .summary-hint {
    display: block;
    color: #a8b69a;
    font-size: 9px;
    margin-top: 13px;
    line-height: 1.9;
  }
  .order-links {
    display: flex;
    gap: 10px;
  }
  .order-links > a {
    flex: 1;
    font-size: 11px;
  }
  .chat-error {
    margin: 0 20px 10px;
    font-size: 10px;
  }
  .typing {
    display: flex;
    gap: 4px;
    margin: 15px;
  }
  .typing > span {
    width: 5px;
    height: 5px;
    background: #b3c2a4;
    border-radius: 50%;
    animation: spin 0.8s infinite;
  }
  @media (max-width: 900px) {
    .chat-layout {
      grid-template-columns: 240px 1fr;
      gap: 20px;
      padding: 25px 20px;
    }
    .chat-catalog h1 {
      font-size: 22px;
    }
    .chat-brand > span {
      display: none;
    }
  }
  @media (max-width: 700px) {
    .chat-layout {
      display: block;
      padding: 14px 12px;
    }
    .chat-catalog {
      display: none;
    }
    .chat-header {
      padding: 14px 18px;
    }
    .chat-header .btn {
      font-size: 10px;
    }
    .chat-window {
      height: calc(100dvh - 105px);
      min-height: 450px;
    }
    .chat-log {
      padding: 17px 14px;
    }
    .chat-window-head {
      padding: 15px;
    }
    .chat-window-head .tag {
      font-size: 7px;
      padding: 3px 5px;
    }
    .message-bubble {
      padding: 11px 13px;
      max-width: 94%;
    }
    .message-bubble p {
      font-size: 11px;
    }
    .chat-summary {
      padding: 17px;
    }
    .chat-compose {
      padding: 12px 12px 8px;
    }
    .compose-hint {
      padding: 0 15px 10px;
    }
    .summary-item {
      font-size: 10px;
    }
    .chat-brand strong {
      font-size: 21px;
    }
  }
</style>
