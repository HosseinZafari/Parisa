<script>
  import { onMount } from 'svelte';
  import { api, fa, money, date, shortDate, navigate } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  import OrderTable from '../components/OrderTable.svelte';
  let data,
    error = '',
    filter = 'all',
    refreshing = false;
  async function load() {
    try {
      data = await api('/dashboard');
      error = '';
    } catch (e) {
      error = e.message;
    } finally {
      refreshing = false;
    }
  }
  onMount(() => {
    load();
    const poll = setInterval(load, 15000);
    return () => clearInterval(poll);
  });
  $: queue =
    data?.queue.filter(
      (o) =>
        filter === 'all' ||
        (filter === 'late' && o.overdue) ||
        (filter === 'today' && o.deadline === data.today) ||
        (filter === 'change' && o.pending_change),
    ) || [];
  $: maxDaily = Math.max(...(data?.daily.map((d) => d.orders) || [1]), 1);
  $: statusGroups = data
    ? [
        { label: 'در انتظار پرداخت', value: data.status_counts.awaiting_payment, color: '#d1b783' },
        { label: 'منتظر آماده‌سازی', value: data.status_counts.paid_awaiting_preparation, color: '#b3a4c5' },
        { label: 'در حال آماده‌سازی', value: data.status_counts.in_preparation, color: '#96aac7' },
        { label: 'آمادهٔ ارسال', value: data.status_counts.ready_to_ship, color: '#97b581' },
        { label: 'ارسال‌شده', value: data.status_counts.shipped, color: '#4e785a' },
        {
          label: 'درخواست تغییر',
          value: data.status_counts.change_requested + data.status_counts.awaiting_seller_approval,
          color: '#cfaa95',
        },
        { label: 'لغوشده', value: data.status_counts.canceled, color: '#d8dcd3' },
      ]
    : [];
</script>

<div class="page-heading">
  <div>
    <span class="eyebrow">یک روز تازه، چند قدم کوچک</span>
    <h1>سلام پریسا، روزت به‌خیر <span class="greeting-leaf">✧</span></h1>
    <p>سفارش‌ها اینجا مرتب‌اند؛ با خیال راحت به ساختن ادامه بده.</p>
  </div>
  <div class="heading-actions">
    <button
      class="btn secondary"
      onclick={() => {
        refreshing = true;
        load();
      }}
      disabled={refreshing}
      ><Icon name="refresh" size={15} />{refreshing ? 'در حال دریافت…' : 'به‌روزرسانی'}</button
    ><button class="btn" onclick={() => navigate('/chat')}><Icon name="plus" size={17} />سفارش آزمایشی</button
    >
  </div>
</div>
{#if error}<div class="error-banner" role="alert">
    {error}<button class="text-button" onclick={load}>تلاش دوباره</button>
  </div>{/if}
{#if !data}<div class="loading"><span class="spinner"></span>در حال مرور سفارش‌ها…</div>{:else}
  <div class="stats-grid">
    <button class="stat-card" onclick={() => navigate('/orders')}
      ><div class="stat-top">
        <span>کل سفارش‌ها</span><span class="stat-icon sage"><Icon name="orders" size={18} /></span>
      </div>
      <strong>{fa(data.total_orders)}<small>سفارش</small></strong>
      <div class="stat-bottom">
        <span class="green-text">{fa(data.daily.reduce((a, d) => a + d.orders, 0))} سفارش</span><span
          >در هفت روز گذشته</span
        >
      </div></button
    >
    <button class="stat-card" onclick={() => navigate('/orders?status=paid_awaiting_preparation')}
      ><div class="stat-top">
        <span>منتظر آماده‌سازی</span><span class="stat-icon lilac"><Icon name="box" size={19} /></span>
      </div>
      <strong>{fa(data.status_counts.paid_awaiting_preparation)}<small>سفارش پرداخت‌شده</small></strong>
      <div class="stat-bottom">
        <span class="tiny-dot lilac"></span><span>آمادهٔ شروع کار شما</span>
      </div></button
    >
    <button
      class="stat-card"
      onclick={() => {
        filter = 'today';
        document.getElementById('work-queue')?.scrollIntoView({ behavior: 'smooth' });
      }}
      ><div class="stat-top">
        <span>ارسال‌های امروز</span><span class="stat-icon sand"><Icon name="truck" size={19} /></span>
      </div>
      <strong>{fa(data.due_today)}<small>سفارش</small></strong>
      <div class="stat-bottom">
        <span class="tiny-dot sand"></span><span
          >{data.due_today ? 'امروز به دست پست می‌رسند' : 'برای امروز ارسالی ندارید'}</span
        >
      </div></button
    >
    <div class="stat-card income">
      <div class="stat-top">
        <span>مجموع پرداخت‌های آزمایشی</span><span class="stat-icon"><Icon name="wallet" size={18} /></span>
      </div>
      <strong class="money-stat">{fa(data.paid_total)}<small>تومان</small></strong>
      <div class="stat-bottom"><Icon name="lock" size={12} /><span>بدون جابه‌جایی پول واقعی</span></div>
    </div>
  </div>
  <div class="attention-strip">
    <div class="attention-copy">
      <span class="attention-icon"><Icon name={data.overdue ? 'alert' : 'check'} size={19} /></span>
      <div>
        <strong
          >{data.overdue
            ? `${fa(data.overdue)} سفارش از موعد ارسال گذشته است.`
            : 'همه‌چیز برای یک روز مرتب آماده است.'}</strong
        >
        <p>
          {data.pending_changes
            ? `${fa(data.pending_changes)} درخواست تغییر هم منتظر بررسی شماست؛ بهتر است از اینجا شروع کنید.`
            : 'کارهای مهم‌تر، بالاتر از بقیه قرار گرفته‌اند.'}
        </p>
      </div>
    </div>
    <button
      class="text-button"
      onclick={() => {
        filter = data.overdue ? 'late' : 'change';
        document.getElementById('work-queue')?.scrollIntoView({ behavior: 'smooth' });
      }}>دیدن کارهای مهم<Icon name="arrow" size={15} /></button
    >
  </div>
  <section class="panel queue-panel" id="work-queue">
    <div class="panel-head">
      <div>
        <h2>اول از کجا شروع کنم؟ <span class="pill-count">{fa(data.queue.length)} کار</span></h2>
        <p>کارهای مهم، به ترتیب موعد و نیاز به رسیدگی</p>
      </div>
      <button class="text-button all-orders" onclick={() => navigate('/orders')}
        >همهٔ سفارش‌ها <Icon name="arrow" size={14} /></button
      >
    </div>
    <div class="queue-tabs">
      <div class="tabs">
        <button class:active={filter === 'all'} class="tab" onclick={() => (filter = 'all')}
          >همهٔ کارها</button
        ><button class:active={filter === 'late'} class="tab" onclick={() => (filter = 'late')}
          >از موعد گذشته <span class="count">{fa(data.overdue)}</span></button
        ><button class:active={filter === 'today'} class="tab" onclick={() => (filter = 'today')}
          >موعد امروز <span class="count">{fa(data.due_today)}</span></button
        ><button class:active={filter === 'change'} class="tab" onclick={() => (filter = 'change')}
          >درخواست تغییر <span class="count">{fa(data.pending_changes)}</span></button
        >
      </div>
      <span class="sort-label"><Icon name="filter" size={14} />اولویت رسیدگی</span>
    </div>
    <OrderTable orders={queue.slice(0, 5)} compact />
    <div class="table-footer">
      <span>نمایش {fa(Math.min(queue.length, 5))} از {fa(queue.length)} کار</span><button
        class="text-button"
        onclick={() => navigate('/orders')}>مشاهدهٔ همهٔ سفارش‌ها<Icon name="chevron" size={13} /></button
      >
    </div>
  </section>
  <div class="dashboard-bottom">
    <section class="panel chart-panel">
      <div class="panel-head">
        <div>
          <h2>نبض این هفته</h2>
          <p>تعداد سفارش‌ها در هفت روز گذشته</p>
        </div>
        <span class="tag"><Icon name="calendar" size={12} />۷ روز اخیر</span>
      </div>
      <div class="chart-summary">
        <strong>{fa(data.daily.reduce((a, d) => a + d.orders, 0))}</strong><span>سفارش ثبت‌شده</span>
        <div class="chart-legend"><i></i>سفارش‌ها</div>
      </div>
      <div
        class="bar-chart"
        role="img"
        aria-label={'نمودار سفارش‌های هفته: ' +
          data.daily.map((d) => date(d.date) + '، ' + fa(d.orders) + ' سفارش').join('؛ ')}
      >
        <div class="grid-lines">
          <span>{fa(maxDaily)}</span><span>{fa(Math.round(maxDaily / 2))}</span><span>۰</span>
        </div>
        {#each data.daily as d, i}<div class="bar-column">
            <div class="bar-track">
              <div
                class="bar"
                class:current={i === 6}
                style:height={Math.max(4, (d.orders / maxDaily) * 100) + '%'}
              >
                <span>{fa(d.orders)}</span>
              </div>
            </div>
            <span class:current-label={i === 6}>{shortDate(d.date)}</span>
          </div>{/each}
      </div>
    </section>
    <section class="panel status-panel">
      <div class="panel-head">
        <div>
          <h2>سفارش‌ها در چه مرحله‌اند؟</h2>
          <p>یک نگاه به مسیر سفارش‌ها</p>
        </div>
        <Icon name="orders" size={17} />
      </div>
      <div class="status-track" role="img" aria-label="توزیع وضعیت سفارش‌ها">
        {#each statusGroups as g}{#if g.value}<span
              style:background={g.color}
              style:flex={g.value}
              title={g.label + ': ' + fa(g.value)}
            ></span>{/if}{/each}
      </div>
      <div class="status-legend">
        {#each statusGroups.filter((g) => g.value) as group}<button onclick={() => navigate('/orders')}
            ><span class="legend-dot" style:background={group.color}></span><span>{group.label}</span><strong
              >{fa(group.value)}</strong
            ></button
          >{/each}
      </div>
      <div class="customer-total">
        <Icon name="people" size={15} /><span>{fa(data.total_customers)} مشتری، همراه فروشگاه شما</span>
      </div>
    </section>
    <section class="panel recent-panel">
      <div class="panel-head">
        <div>
          <h2>آخرین همراه‌ها</h2>
          <p>مشتری‌هایی با گفتگوی تازه</p>
        </div>
        <Icon name="people" size={17} />
      </div>
      <div class="recent-list">
        {#each data.recent_customers.slice(0, 4) as c, i}<button
            onclick={() => navigate('/customers/' + c.id)}
            ><span class="avatar tone-{i}">{c.name.slice(0, 1)}</span><span
              ><strong>{c.name}</strong><small dir="ltr">@{c.username}</small></span
            ><Icon name="chevron" size={13} /></button
          >{/each}
      </div>
      <button class="recent-all text-button" onclick={() => navigate('/customers')}
        >همهٔ مشتری‌ها<Icon name="arrow" size={14} /></button
      >
    </section>
  </div>
{/if}

<style>
  .greeting-leaf {
    font-size: 26px;
    font-weight: 400;
    color: #acb293;
    margin-right: 7px;
  }
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 17px;
    margin-bottom: 22px;
  }
  .stat-card {
    display: block;
    text-align: right;
    padding: 21px 22px;
    background: white;
    border: 1px solid var(--line);
    border-radius: 13px;
    transition: transform 0.15s;
  }
  .stat-card:hover {
    transform: translateY(-2px);
  }
  .stat-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 5px;
  }
  .stat-top > span:first-child {
    font-size: 10px;
    color: #8e9a83;
  }
  .stat-icon {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #e4ecd8;
    color: #7e9967;
  }
  .stat-icon.sage {
    background: #eff4e9;
    color: #96ac80;
  }
  .stat-icon.lilac {
    background: #f2eff7;
    color: #b2a3c2;
  }
  .stat-icon.sand {
    background: #faf4e7;
    color: #c8b38b;
  }
  .stat-card > strong {
    display: block;
    font-size: 31px;
    font-weight: 500;
    line-height: 1.3;
    margin: 16px 0;
  }
  .stat-card > strong small {
    font-size: 10px;
    font-weight: 400;
    color: #a0a995;
    margin-right: 9px;
  }
  .stat-bottom {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 9px;
    color: #a1ab97;
    min-height: 20px;
  }
  .stat-bottom .green-text {
    color: #849b70;
  }
  .stat-card.income {
    background: #edf2e5;
    border-color: #e2ead6;
  }
  .income .stat-top > span:first-child {
    color: #7f926d;
  }
  .stat-card > .money-stat {
    font-size: 25px;
    color: #537143;
    margin-top: 21px;
    margin-bottom: 18px;
  }
  .money-stat small {
    color: #8b9d7a !important;
  }
  .tiny-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    display: block;
    background: #b1a3c1;
  }
  .tiny-dot.sand {
    background: #c5b38e;
  }
  .attention-strip {
    background: #f4f0e5;
    border: 1px solid #eee7d4;
    border-radius: 10px;
    padding: 15px 21px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 25px;
  }
  .attention-copy {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .attention-copy strong {
    font-size: 11px;
    color: #978456;
  }
  .attention-copy p {
    font-size: 10px;
    color: #b2a47f;
    margin-top: 3px;
  }
  .attention-icon {
    color: #bea46c;
    display: flex;
  }
  .attention-strip > .text-button {
    color: #a49064;
    font-size: 10px;
    flex-shrink: 0;
  }
  .queue-tabs {
    padding: 0 23px 17px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .sort-label {
    font-size: 9px;
    color: #a0a997;
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .dashboard-bottom {
    display: grid;
    grid-template-columns: 1.4fr 1.05fr 0.95fr;
    gap: 20px;
    margin-top: 23px;
  }
  .dashboard-bottom h2 {
    font-size: 13px;
  }
  .dashboard-bottom .panel-head {
    padding: 21px 22px 13px;
  }
  .dashboard-bottom .panel-head p {
    font-size: 9px;
  }
  .dashboard-bottom .panel-head > :global(svg) {
    color: #a9b49b;
  }
  .chart-summary {
    padding: 0 24px;
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  .chart-summary strong {
    font-size: 26px;
    font-weight: 500;
  }
  .chart-summary > span {
    font-size: 9px;
    color: #a4ad97;
  }
  .chart-legend {
    margin-right: auto;
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 8px;
    color: #9eaa90;
  }
  .chart-legend i {
    width: 6px;
    height: 6px;
    border-radius: 2px;
    background: #9db38b;
  }
  .bar-chart {
    height: 155px;
    display: flex;
    gap: 16px;
    padding: 15px 24px 18px 22px;
    direction: rtl;
    position: relative;
  }
  .grid-lines {
    position: absolute;
    inset: 15px 20px 40px 21px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    z-index: 0;
    direction: ltr;
  }
  .grid-lines span {
    border-top: 1px dashed #edf0e8;
    width: 100%;
    font-size: 8px;
    color: #bec6b4;
  }
  .bar-column {
    flex: 1;
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }
  .bar-track {
    height: 110px;
    width: 65%;
    display: flex;
    align-items: flex-end;
  }
  .bar {
    background: #d8e3cd;
    width: 100%;
    border-radius: 4px 4px 0 0;
    position: relative;
    min-width: 12px;
  }
  .bar.current {
    background: #79996b;
  }
  .bar > span {
    position: absolute;
    top: -17px;
    left: 0;
    right: 0;
    text-align: center;
    color: #829674;
    font-size: 8px;
  }
  .bar-column > span {
    color: #aab59a;
    font-size: 8px;
    white-space: nowrap;
  }
  .bar-column > span.current-label {
    color: #678452;
  }
  .status-track {
    display: flex;
    height: 13px;
    border-radius: 4px;
    overflow: hidden;
    gap: 3px;
    margin: 10px 23px 20px;
  }
  .status-track span {
    border-radius: 2px;
    min-width: 3px;
  }
  .status-legend {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 13px 16px;
    padding: 0 23px;
  }
  .status-legend button {
    padding: 0;
    background: transparent;
    display: flex;
    gap: 6px;
    font-size: 8px;
    color: #9ba68e;
    justify-content: flex-start;
    white-space: nowrap;
  }
  .status-legend strong {
    margin-right: auto;
    color: #7f8f70;
    font-size: 9px;
    font-weight: 400;
  }
  .legend-dot {
    width: 6px;
    height: 6px;
    border-radius: 2px;
    flex-shrink: 0;
  }
  .customer-total {
    display: flex;
    align-items: center;
    gap: 7px;
    border-top: 1px solid var(--line);
    margin: 22px 23px 0;
    padding: 13px 0;
    color: #a7b198;
    font-size: 8px;
  }
  .recent-list {
    display: grid;
    gap: 14px;
    padding: 6px 22px 15px;
  }
  .recent-list button {
    background: transparent;
    padding: 0;
    display: flex;
    justify-content: flex-start;
    gap: 10px;
    text-align: right;
  }
  .recent-list strong {
    display: block;
    font-size: 10px;
    font-weight: 500;
    color: #7c8b70;
  }
  .recent-list small {
    display: block;
    color: #b0b9a4;
    font-size: 8px;
    margin-top: 4px;
    text-align: right;
  }
  .recent-list .avatar {
    height: 30px;
    width: 30px;
    font-size: 11px;
  }
  .recent-list :global(svg) {
    margin-right: auto;
    color: #aeba9f;
  }
  .recent-all {
    font-size: 9px;
    margin: 0 22px 20px;
    color: #80946b;
  }
  .queue-panel {
    scroll-margin-top: 20px;
  }
  @media (min-width: 1500px) {
    .dashboard-bottom {
      grid-template-columns: 1.4fr 1fr 1fr;
    }
    .bar-chart {
      height: 180px;
    }
    .bar-track {
      height: 130px;
    }
  }
  @media (max-width: 1250px) {
    .stats-grid {
      gap: 12px;
    }
    .stat-card {
      padding: 18px 16px;
    }
    .stat-card > .money-stat {
      font-size: 21px;
    }
    .dashboard-bottom {
      grid-template-columns: 1.3fr 1fr;
    }
    .recent-panel {
      grid-column: 1/-1;
    }
    .recent-list {
      grid-template-columns: repeat(4, 1fr);
    }
    .recent-all {
      display: flex;
      margin-right: auto;
      width: max-content;
    }
    .stat-card > strong small {
      font-size: 9px;
      margin-right: 5px;
    }
    .stat-bottom {
      font-size: 8px;
    }
  }
  @media (max-width: 1000px) {
    .stats-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .stat-card > strong {
      margin: 12px 0;
    }
    .stat-card > .money-stat {
      font-size: 27px;
      margin: 15px 0;
    }
    .stat-top > span:first-child {
      font-size: 11px;
    }
  }
  @media (max-width: 700px) {
    .dashboard-bottom {
      grid-template-columns: 1fr;
    }
    .recent-panel {
      grid-column: auto;
    }
    .recent-list {
      grid-template-columns: 1fr 1fr;
    }
    .stats-grid {
      gap: 10px;
    }
    .stat-card {
      padding: 15px 13px;
    }
    .stat-icon {
      width: 30px;
      height: 30px;
    }
    .stat-top > span:first-child {
      font-size: 9px;
    }
    .stat-card > strong {
      font-size: 27px;
    }
    .stat-card > .money-stat {
      font-size: 20px;
      margin: 16px 0;
    }
    .stat-card > strong small {
      font-size: 8px;
    }
    .attention-strip {
      padding: 13px 14px;
      align-items: flex-start;
      gap: 10px;
    }
    .attention-copy {
      gap: 10px;
    }
    .attention-copy strong {
      font-size: 10px;
    }
    .attention-copy p {
      font-size: 9px;
    }
    .attention-strip > .text-button {
      font-size: 9px;
      max-width: 65px;
      white-space: normal;
    }
    .queue-tabs {
      padding: 0 12px 14px;
    }
    .sort-label {
      display: none;
    }
    .all-orders {
      font-size: 10px;
    }
    .queue-panel .panel-head h2 {
      font-size: 14px;
    }
    .queue-panel .panel-head p {
      font-size: 9px;
    }
    .greeting-leaf {
      font-size: 22px;
    }
  }
</style>
