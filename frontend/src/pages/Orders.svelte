<script>
  import { onMount } from 'svelte';
  import { api, statuses, fa, navigate } from '../lib/api';
  import OrderTable from '../components/OrderTable.svelte';
  import Icon from '../components/Icon.svelte';
  let orders = [],
    loading = true,
    error = '',
    search = '',
    status = new URLSearchParams(location.search).get('status') || '',
    deadline = '';
  $: filtered = orders.filter(
    (o) =>
      (!status || o.status === status) &&
      (!search ||
        [o.customer_name, o.customer_username, o.product_name, String(1000 + o.id)].some((v) =>
          v.includes(search),
        )) &&
      (!deadline || (deadline === 'late' && o.overdue) || (deadline === 'none' && !o.deadline)),
  );
  onMount(async () => {
    try {
      orders = await api('/orders');
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });
</script>

<div class="page-heading">
  <div>
    <span class="eyebrow">از اولین سلام تا رسیدن بسته</span>
    <h1>دفتر سفارش‌ها</h1>
    <p>همهٔ سفارش‌ها، با جزئیاتی که هیچ‌وقت گم نمی‌شوند.</p>
  </div>
  <button class="btn" onclick={() => navigate('/chat')}><Icon name="plus" size={17} />سفارش آزمایشی</button>
</div>
<div class="toolbar">
  <div class="search-box">
    <Icon name="search" size={17} /><input
      aria-label="جستجوی سفارش"
      bind:value={search}
      placeholder="نام مشتری، محصول یا شمارهٔ سفارش…"
    />
  </div>
  <select aria-label="وضعیت سفارش" bind:value={status}
    ><option value="">همهٔ وضعیت‌ها</option>{#each Object.entries(statuses) as [key, label]}<option
        value={key}>{label}</option
      >{/each}</select
  ><select aria-label="موعد سفارش" bind:value={deadline}
    ><option value="">همهٔ موعدها</option><option value="late">از موعد گذشته</option><option value="none"
      >بدون موعد مشخص</option
    ></select
  ><span class="spacer"></span><span class="muted">{fa(filtered.length)} سفارش</span>
</div>
{#if error}<div class="error-banner">{error}</div>{/if}
{#if loading}<div class="loading"><span class="spinner"></span>در حال دریافت سفارش‌ها…</div>{:else}<section
    class="panel"
  >
    <OrderTable orders={filtered} />
    <div class="table-footer">
      <span>تمام مبلغ‌ها به تومان هستند.</span><span>{fa(filtered.length)} نتیجه</span>
    </div>
  </section>{/if}
