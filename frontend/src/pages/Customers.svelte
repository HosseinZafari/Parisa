<script>
  import { modal } from '../lib/modal';
  import { onMount } from 'svelte';
  import { api, fa, money, date, navigate } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  import OrderTable from '../components/OrderTable.svelte';
  export let id, notify;
  let customers = [],
    search = '',
    error = '',
    loading = true,
    customer,
    editing = false,
    saving = false,
    form;
  async function load() {
    try {
      if (id) customer = await api('/customers/' + id);
      else customers = await api('/customers');
      error = '';
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
  onMount(load);
  $: filtered = customers.filter((c) => [c.name, c.username, c.phone].some((v) => v.includes(search)));
  function edit() {
    form = Object.fromEntries(
      ['name', 'phone', 'city', 'address', 'postal_code', 'notes'].map((k) => [k, customer[k]]),
    );
    editing = true;
  }
  async function save(e) {
    e.preventDefault();
    saving = true;
    try {
      await api('/customers/' + id, { method: 'PATCH', body: form });
      editing = false;
      notify('اطلاعات مشتری ذخیره شد.');
      await load();
    } catch (e) {
      notify(e.message, true);
    } finally {
      saving = false;
    }
  }
</script>

{#if error}<div class="error-banner" role="alert">{error}</div>{/if}
{#if id}<button class="text-button" onclick={() => navigate('/customers')}
    ><Icon name="chevron" size={14} />بازگشت به مشتری‌ها</button
  >{#if customer}<div class="page-heading customer-heading">
      <div class="customer-hero">
        <span class="avatar large-avatar">{customer.name.slice(0, 1)}</span>
        <div>
          <h1>{customer.name}</h1>
          <p dir="ltr">@{customer.username}</p>
        </div>
      </div>
      <button class="btn secondary" onclick={edit}><Icon name="edit" size={15} />ویرایش اطلاعات</button>
    </div>
    <div class="two-columns">
      <div class="page-stack">
        <section class="panel">
          <div class="panel-head">
            <h2>سفارش‌های پیشین</h2>
            <span class="pill-count">{fa(customer.total_orders)} سفارش</span>
          </div>
          <OrderTable orders={customer.orders} compact />
        </section>
      </div>
      <section class="panel">
        <div class="panel-head"><h2>دربارهٔ مشتری</h2></div>
        <div class="panel-body info-list">
          <div class="info-row"><span>همراه</span><bdi>{customer.phone || 'ثبت نشده'}</bdi></div>
          <div class="info-row"><span>شهر</span><strong>{customer.city || 'ثبت نشده'}</strong></div>
          <div class="info-row"><span>نشانی قبلی</span><strong>{customer.address || 'ثبت نشده'}</strong></div>
          <div class="info-row"><span>کد پستی</span><bdi>{customer.postal_code || 'ثبت نشده'}</bdi></div>
          <div class="info-row">
            <span>مجموع خرید آزمایشی</span><strong>{money(customer.total_paid)}</strong>
          </div>
          <div class="info-row">
            <span>آخرین گفتگو</span><span>{date(customer.last_interaction_at, true)}</span>
          </div>
          <hr />
          <h3>یادداشت مشتری</h3>
          <p class="muted notes">{customer.notes || 'یادداشتی ثبت نشده است.'}</p>
        </div>
      </section>
    </div>{/if}
{:else}<div class="page-heading">
    <div>
      <span class="eyebrow">آدم‌های پشت سفارش‌ها</span>
      <h1>مشتری‌های شما</h1>
      <p>سلیقه‌ها، سفارش‌های قبلی و چیزهای کوچکی که ارزش یادآوری دارند.</p>
    </div>
    <span class="tag"><Icon name="people" size={15} />{fa(customers.length)} همراه</span>
  </div>
  <div class="toolbar">
    <div class="search-box">
      <Icon name="search" size={17} /><input
        aria-label="جستجوی مشتری"
        bind:value={search}
        placeholder="نام، نام کاربری یا شمارهٔ همراه…"
      />
    </div>
  </div>
  <section class="panel">
    <div class="table-scroll">
      <table class="order-table">
        <thead
          ><tr
            ><th>مشتری</th><th>شمارهٔ همراه</th><th>سفارش‌ها</th><th>خرید آزمایشی</th><th>آخرین گفتگو</th><th
            ></th></tr
          ></thead
        ><tbody
          >{#each filtered as c, i}<tr
              ><td
                ><button class="customer-cell" onclick={() => navigate('/customers/' + c.id)}
                  ><span class="avatar tone-{i % 4}">{c.name.slice(0, 1)}</span><span
                    ><strong>{c.name}</strong><small dir="ltr">@{c.username}</small></span
                  ></button
                ></td
              ><td><bdi>{c.phone || '—'}</bdi></td><td>{fa(c.total_orders)} سفارش</td><td
                >{money(c.total_paid)}</td
              ><td>{date(c.last_interaction_at)}</td><td
                ><button
                  class="icon-button"
                  aria-label={'مشاهدهٔ ' + c.name}
                  onclick={() => navigate('/customers/' + c.id)}><Icon name="chevron" size={16} /></button
                ></td
              ></tr
            >{:else}<tr><td colspan="6"><div class="empty">مشتری‌ای پیدا نشد.</div></td></tr>{/each}</tbody
        >
      </table>
    </div>
  </section>{/if}
{#if loading}<div class="loading"><span class="spinner"></span>در حال دریافت اطلاعات…</div>{/if}
{#if editing}<div class="modal-backdrop" role="presentation">
    <dialog
      use:modal
      oncancel={() => (editing = false)}
      class="modal"
      aria-modal="true"
      aria-labelledby="customer-edit"
    >
      <div class="modal-header">
        <h2 id="customer-edit">ویرایش اطلاعات مشتری</h2>
        <button class="icon-button" aria-label="بستن" onclick={() => (editing = false)}
          ><Icon name="close" /></button
        >
      </div>
      <form class="modal-content" onsubmit={save}>
        <div class="form-grid">
          {#each [['name', 'نام مشتری'], ['phone', 'همراه'], ['city', 'شهر'], ['postal_code', 'کد پستی']] as [key, label]}<div
              class="field"
            >
              <label for={'customer-' + key}>{label}</label><input
                id={'customer-' + key}
                bind:value={form[key]}
                required={key === 'name'}
                maxlength="200"
              />
            </div>{/each}
          <div class="field full">
            <label for="customer-address">نشانی</label><textarea
              id="customer-address"
              bind:value={form.address}
              maxlength="1500"></textarea>
          </div>
          <div class="field full">
            <label for="customer-notes">یادداشت خصوصی</label><textarea
              id="customer-notes"
              bind:value={form.notes}
              maxlength="5000"></textarea>
          </div>
        </div>
        <div class="form-footer">
          <button type="button" class="btn secondary" onclick={() => (editing = false)}>انصراف</button><button
            class="btn"
            disabled={saving}>ذخیره</button
          >
        </div>
      </form>
    </dialog>
  </div>{/if}

<style>
  .customer-heading {
    margin-top: 23px;
  }
  .customer-hero {
    display: flex;
    align-items: center;
    gap: 18px;
  }
  .customer-hero p {
    text-align: right;
    font-size: 12px;
    color: var(--tone-a1b090, #a1b090);
  }
  .notes {
    white-space: pre-wrap;
    font-size: 12px;
  }
  .info-row strong {
    font-size: 11px;
    max-width: 70%;
  }
</style>
