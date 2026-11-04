<script>
  import { onMount, tick } from 'svelte';
  import { api, date, money, fa, navigate } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  import Status from '../components/Status.svelte';
  import ChatPending from '../components/ChatPending.svelte';
  let chat,
    products = [],
    message = '',
    sending = false,
    error = '',
    log,
    loading = true;
  let pendingMessage = null,
    failedMessage = null,
    starting = false,
    requestVersion = 0,
    composer;
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
    if (sending || starting) return;
    starting = true;
    requestVersion += 1;
    error = '';
    try {
      chat = await api('/chat/start', { method: 'POST', body: {} });
      failedMessage = null;
      localStorage.setItem('parisa-chat', chat.token);
      await scroll();
    } catch (e) {
      error = e.message;
    } finally {
      starting = false;
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
      if (!chat || sending || starting || failedMessage) return;
      const token = chat.token,
        version = requestVersion;
      try {
        const state = await api('/chat/' + token);
        if (
          alive &&
          !sending &&
          !starting &&
          !failedMessage &&
          version === requestVersion &&
          token === chat?.token
        ) {
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
  async function send(text = message, retry = null) {
    if (!text.trim() || sending || starting || !chat || (failedMessage && !retry)) return;
    const request = retry || { text: text.trim(), client_id: crypto.randomUUID() };
    sending = true;
    requestVersion += 1;
    error = '';
    pendingMessage = request;
    failedMessage = null;
    if (!retry && message.trim() === request.text) message = '';
    composer?.focus({ preventScroll: true });
    scroll();
    try {
      chat = await api('/chat/' + chat.token + '/messages', { method: 'POST', body: request });
      pendingMessage = null;
      await scroll();
    } catch (e) {
      failedMessage = request;
      error = e.message;
    } finally {
      pendingMessage = null;
      sending = false;
      await scroll();
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
    ><button class="btn secondary small" disabled={sending || starting || loading} onclick={start}
      >گفتگوی تازه<Icon name="plus" size={15} /></button
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
        {#if loading}<ChatPending label="در حال باز کردن گفتگو…" />{/if}
        {#each chat?.messages || [] as m}<div class="message-wrap" class:customer={m.role === 'customer'}>
            <div class="message-bubble">
              <p>{m.text}</p>
              <small>{m.role === 'seller' ? 'فروشنده · ' : ''}{date(m.created_at, true)}</small>
            </div>
          </div>{/each}
        {#if chat?.summary && !chat.order}<details class="chat-summary" open={chat.ready_to_confirm}>
            <summary class="summary-heading">
              <Icon name="orders" size={18} /><strong
                >{chat.ready_to_confirm ? 'خلاصهٔ سفارش شما' : 'پیش‌نویس سفارش شما'}</strong
              ><span>مشاهدهٔ جزئیات</span><Icon name="down" size={14} />
            </summary>
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
          </details>{/if}
        {#if chat?.order}<div class="chat-summary">
            <div class="summary-heading">
              <Icon name="check" size={18} /><strong
                >سفارش <bdi>#{fa(1000 + chat.order.id)}</bdi> ثبت شد.</strong
              >
            </div>
            <Status status={chat.order.status} />
            {#if chat.order.changes?.some((change) => change.status === 'pending')}
              <p class="summary-missing">
                درخواست تغییر شما منتظر تأیید فروشنده است. مشخصات فعلی تا زمان تأیید حفظ می‌شوند.
              </p>
            {/if}
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
        {#if pendingMessage || failedMessage}
          <div class="message-wrap customer optimistic-message">
            <div class="message-bubble" class:delivery-uncertain={!!failedMessage}>
              <p>{(pendingMessage || failedMessage).text}</p>
              <small>{failedMessage ? 'ارسال پیام تأیید نشد' : 'همین الان'}</small>
              {#if failedMessage}
                <div class="retry-actions">
                  <button class="text-button" onclick={() => send(failedMessage.text, failedMessage)}
                    >تلاش دوباره</button
                  >
                  <button
                    class="text-button"
                    onclick={() => {
                      failedMessage = null;
                      error = '';
                    }}>ادامه بدون تلاش دوباره</button
                  >
                </div>
              {/if}
            </div>
          </div>
        {/if}
        {#if sending}<ChatPending />{/if}
      </div>
      {#if error}<div class="chat-error error-banner" role="alert">{error}</div>{/if}
      {#if chat?.suggested_replies?.length}
        <div class="quick-choices" role="group" aria-label="گزینه‌های پیشنهادی پاسخ">
          {#each chat.suggested_replies as choice}
            <button type="button" disabled={sending || !!failedMessage} onclick={() => send(choice)}
              >{choice}</button
            >
          {/each}
        </div>
      {:else if chat?.messages.length < 3}<div class="quick-examples">
          {#each examples as example}<button disabled={sending} onclick={() => send(example)}
              >{example}</button
            >{/each}
        </div>{/if}
      <form class="chat-compose" onsubmit={submit}>
        <textarea
          bind:this={composer}
          bind:value={message}
          aria-label="پیام شما"
          rows="2"
          maxlength="2000"
          placeholder="پیامت را اینجا بنویس…"
          onkeydown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
              e.preventDefault();
              send();
            }
          }}></textarea><button
          class="send-button"
          disabled={sending || starting || !!failedMessage || !message.trim() || !chat}
          aria-label="ارسال پیام"><Icon name="send" size={21} /></button
        >
      </form>
      <div class="compose-hint">
        {#if sending}<span class="draft-hint"
            >می‌توانی پیام بعدی را بنویسی؛ بعد از دریافت پاسخ، ارسالش کن.</span
          >{/if}
        نام و نشانی را می‌توانی با این قالب بفرستی: نام: سارا؛ شهر: تهران؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی:
        ۱۱۱۱۱۱۱۱۱۱
      </div>
    </section>
  </main>
</div>

<style>
  .quick-choices {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    padding: 12px 20px;
    border-top: 1px solid var(--line);
  }
  .quick-choices button {
    min-height: 38px;
    padding: 8px 17px;
    border: 1px solid var(--line);
    background: var(--mint);
    color: var(--green);
    border-radius: 20px;
    font-size: 12px;
  }
  .chat-page {
    min-height: 100vh;
    background: var(--tone-f6f8f2, #f6f8f2);
  }
  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--tone-e5ebdd, #e5ebdd);
    padding: 20px max(25px, 5vw);
    background: var(--tone-fdfefa, #fdfefa);
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
    color: var(--tone-a2af93, #a2af93);
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
    color: var(--tone-9ba88e, #9ba88e);
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
    background: var(--tone-fff, #fff);
    border: 1px solid var(--tone-e7ebdf, #e7ebdf);
    border-radius: 10px;
    text-align: right;
  }
  .product-symbol {
    width: 42px;
    height: 45px;
    background: var(--tone-f3eee3, #f3eee3);
    color: var(--tone-c0b18d, #c0b18d);
    display: grid;
    place-items: center;
    border-radius: 9px;
  }
  .product-symbol.sage {
    background: var(--tone-eef3e7, #eef3e7);
    color: var(--tone-9db38c, #9db38c);
  }
  .product-symbol.rose {
    background: var(--tone-f6ebe6, #f6ebe6);
    color: var(--tone-c8a99a, #c8a99a);
  }
  .product-symbol.lilac {
    background: var(--tone-efecf5, #efecf5);
    color: var(--tone-b3a6c8, #b3a6c8);
  }
  .chat-products strong {
    display: block;
    font-size: 11px;
  }
  .chat-products small {
    display: block;
    color: var(--tone-a0ae91, #a0ae91);
    font-size: 10px;
    margin-top: 5px;
  }
  .chat-products button > :global(svg) {
    margin-right: auto;
    color: var(--tone-b1bda6, #b1bda6);
  }
  .chat-safety {
    display: flex;
    gap: 10px;
    margin: 30px 0 24px;
    padding: 15px;
    background: var(--tone-eff3e7, #eff3e7);
    color: var(--tone-9ba98c, #9ba98c);
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
    background: var(--tone-fff, #fff);
    border: 1px solid var(--tone-e4eadb, #e4eadb);
    border-radius: 16px;
    display: flex;
    flex-direction: column;
    height: calc(100vh - 160px);
    min-height: 600px;
    max-height: 1000px;
    overflow: hidden;
    box-shadow: 0 10px 40px var(--tone-42632804, #42632804);
  }
  .chat-window-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 19px 23px;
    border-bottom: 1px solid var(--tone-edf0e6, #edf0e6);
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
    color: var(--tone-a0af91, #a0af91);
    margin-top: 4px;
  }
  .chat-window-head small i {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--tone-9db585, #9db585);
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
    background: linear-gradient(var(--tone-fdfefa, #fdfefa), var(--tone-fff, #fff));
  }
  .chat-date {
    text-align: center;
    font-size: 9px;
    color: var(--tone-bac3ae, #bac3ae);
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
    background: var(--tone-eef3e6, #eef3e6);
    border: 1px solid var(--tone-e7eddf, #e7eddf);
    padding: 13px 17px;
    border-radius: 12px 3px 12px 12px;
  }
  .customer .message-bubble {
    background: var(--tone-f7f4ee, #f7f4ee);
    border: 1px solid var(--tone-f0ece4, #f0ece4);
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
    color: var(--tone-acb89e, #acb89e);
    margin-top: 8px;
    text-align: left;
  }
  .chat-compose {
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 16px 19px 10px;
    border-top: 1px solid var(--tone-edf0e6, #edf0e6);
    background: var(--tone-fff, #fff);
  }
  .chat-compose textarea {
    border: 0;
    background: var(--tone-f7f9f2, #f7f9f2);
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
    background: var(--tone-678750, #678750);
    color: var(--tone-fff, #fff);
    border-radius: 12px;
  }
  .send-button:disabled {
    background: var(--tone-c6d3ba, #c6d3ba);
  }
  .compose-hint {
    font-size: 8px;
    color: var(--tone-aeb8a2, #aeb8a2);
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
    border: 1px solid var(--tone-e6eddd, #e6eddd);
    background: var(--tone-fbfdf7, #fbfdf7);
    color: var(--tone-95a581, #95a581);
  }
  .chat-summary {
    background: var(--tone-fff, #fff);
    border: 1px solid var(--tone-dce6d1, #dce6d1);
    border-radius: 12px;
    padding: 21px;
    margin: 20px 0;
    max-width: 100%;
    box-shadow: 0 4px 18px var(--tone-526e3105, #526e3105);
  }
  .summary-heading {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 20px;
    color: var(--tone-789363, #789363);
    font-size: 12px;
  }
  summary.summary-heading {
    cursor: pointer;
    list-style: none;
  }
  summary.summary-heading::-webkit-details-marker {
    display: none;
  }
  summary.summary-heading > span {
    margin-inline-start: auto;
    font-size: 10px;
  }
  details.chat-summary:not([open]) .summary-heading {
    margin-bottom: 0;
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
    color: var(--tone-a3b092, #a3b092);
    flex-shrink: 0;
  }
  .summary-item strong {
    text-align: left;
    overflow-wrap: anywhere;
  }
  .summary-item.total {
    padding-top: 14px;
    border-top: 1px dashed var(--tone-dce6d1, #dce6d1);
    color: var(--tone-63834c, #63834c);
    margin: 18px 0 20px;
    font-size: 13px;
  }
  .summary-item.total > span {
    color: var(--tone-81966d, #81966d);
  }
  .summary-missing {
    font-size: 10px;
    color: var(--tone-b39b70, #b39b70);
    background: var(--tone-faf5e9, #faf5e9);
    padding: 10px;
    border-radius: 7px;
  }
  .chat-summary > .btn {
    width: 100%;
  }
  .summary-hint {
    display: block;
    color: var(--tone-a8b69a, #a8b69a);
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
  .delivery-uncertain {
    border-style: dashed;
  }
  .retry-actions {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 12px;
  }
  .retry-actions .text-button {
    font-size: 11px;
    min-height: 30px;
  }
  .draft-hint {
    display: block;
    font-size: 10px;
    color: var(--green);
    margin-bottom: 5px;
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
