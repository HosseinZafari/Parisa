<script>
  import { modal } from '../lib/modal';
  import { onMount } from 'svelte';
  import { api, fa, money } from '../lib/api';
  import Icon from '../components/Icon.svelte';
  export let notify;
  let products = [],
    search = '',
    error = '',
    loading = true,
    editing = null,
    saving = false,
    aliases = '',
    formError = '';
  const icons = { شمع: 'candle', صابون: 'flower', پوشاک: 'dress', هنر: 'art', خوراکی: 'cookie' };
  const blank = () => ({
    name: '',
    description: '',
    category: 'سایر',
    price: 0,
    inventory: 0,
    shipping_cost: 0,
    preparation_days: 3,
    enabled: true,
    color: 'sage',
    aliases: [],
    requirements: [],
  });
  async function load() {
    try {
      products = await api('/products');
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
  onMount(load);
  $: filtered = products.filter((p) => [p.name, p.category, ...p.aliases].some((v) => v.includes(search)));
  function edit(product) {
    editing = structuredClone(product || blank());
    aliases = editing.aliases.join('، ');
    formError = '';
  }
  function addRequirement() {
    editing = {
      ...editing,
      requirements: [
        ...editing.requirements,
        {
          key: 'field_' + (editing.requirements.length + 1),
          label: '',
          required: true,
          allowed_values: [],
          price_adjustments: {},
        },
      ],
    };
  }
  async function save(e) {
    e.preventDefault();
    saving = true;
    formError = '';
    try {
      const { id, ...payload } = editing;
      payload.aliases = aliases
        .split(/[,،\n]/)
        .map((v) => v.trim())
        .filter(Boolean);
      await api('/products' + (id ? '/' + id : ''), { method: id ? 'PUT' : 'POST', body: payload });
      notify('محصول ذخیره شد.');
      editing = null;
      await load();
    } catch (e) {
      formError = e.message;
    } finally {
      saving = false;
    }
  }
  async function toggle(p) {
    try {
      const { id, ...body } = p;
      await api('/products/' + id, { method: 'PUT', body: { ...body, enabled: !p.enabled } });
      await load();
      notify(p.enabled ? 'محصول غیرفعال شد.' : 'محصول فعال شد.');
    } catch (e) {
      notify(e.message, true);
    }
  }
  function setOptions(index, text) {
    const allowed = text
      .split(/[,،]/)
      .map((v) => v.trim())
      .filter(Boolean);
    editing.requirements[index].allowed_values = allowed;
    editing.requirements[index].price_adjustments = Object.fromEntries(
      Object.entries(editing.requirements[index].price_adjustments).filter(([k]) => allowed.includes(k)),
    );
    editing = { ...editing };
  }
</script>

<div class="page-heading">
  <div>
    <span class="eyebrow">چیزهایی که با عشق می‌سازی</span>
    <h1>محصولات فروشگاه</h1>
    <p>قیمت، موجودی و سؤال‌های هر محصول از همین‌جا مدیریت می‌شوند.</p>
  </div>
  <button class="btn" onclick={() => edit(null)}><Icon name="plus" size={17} />محصول تازه</button>
</div>
<div class="toolbar">
  <div class="search-box">
    <Icon name="search" size={17} /><input
      aria-label="جستجوی محصول"
      bind:value={search}
      placeholder="نام محصول یا دسته‌بندی…"
    />
  </div>
  <span class="spacer"></span><span class="muted">{fa(filtered.length)} محصول</span>
</div>
{#if error}<div class="error-banner">{error}</div>{/if}
{#if loading}<div class="loading"><span class="spinner"></span>در حال چیدن محصولات…</div>{:else}<div
    class="product-grid"
  >
    {#each filtered as product}<article class="panel product-card" class:disabled={!product.enabled}>
        <div class="product-visual {product.color}">
          <div class="visual-ring"></div>
          <Icon name={icons[product.category] || 'box'} size={67} stroke={0.85} /><span
            >{product.category}</span
          >{#if !product.enabled}<b>غیرفعال</b>{/if}
        </div>
        <div class="product-content">
          <div class="product-title">
            <h2>{product.name}</h2>
            <button class="icon-button" aria-label={'ویرایش ' + product.name} onclick={() => edit(product)}
              ><Icon name="edit" size={16} /></button
            >
          </div>
          <p>{product.description}</p>
          <div class="product-meta">
            <strong>{money(product.price)}</strong><span>{fa(product.inventory)} عدد موجود</span>
          </div>
          <div class="product-details">
            <span><Icon name="clock" size={13} />{fa(product.preparation_days)} روز آماده‌سازی</span><span
              ><Icon name="truck" size={13} />{money(product.shipping_cost)}</span
            >
          </div>
          <div class="product-footer">
            <span>{fa(product.requirements.filter((r) => r.required).length)} مشخصهٔ الزامی</span><button
              class="text-button"
              onclick={() => toggle(product)}>{product.enabled ? 'غیرفعال کردن' : 'فعال کردن'}</button
            >
          </div>
        </div>
      </article>{:else}<div class="panel empty">
        <Icon name="box" size={34} /><strong>محصولی پیدا نشد.</strong><button
          class="btn secondary"
          onclick={() => edit(null)}>ساخت اولین محصول</button
        >
      </div>{/each}
  </div>{/if}
{#if editing}<div class="modal-backdrop" role="presentation">
    <dialog
      use:modal
      oncancel={() => (editing = null)}
      class="modal product-modal"
      aria-modal="true"
      aria-labelledby="product-title"
    >
      <div class="modal-header">
        <h2 id="product-title">{editing.id ? 'ویرایش محصول' : 'محصول تازه'}</h2>
        <button class="icon-button" aria-label="بستن" onclick={() => (editing = null)}
          ><Icon name="close" /></button
        >
      </div>
      <form class="modal-content" onsubmit={save}>
        {#if formError}<div class="error-banner" role="alert">{formError}</div>{/if}
        <div class="form-grid">
          <div class="field">
            <label for="product-name">نام محصول</label><input
              id="product-name"
              bind:value={editing.name}
              required
              minlength="2"
              maxlength="200"
            />
          </div>
          <div class="field">
            <label for="category">دسته‌بندی</label><input
              id="category"
              bind:value={editing.category}
              required
              maxlength="100"
            />
          </div>
          <div class="field full">
            <label for="description">توضیحات</label><textarea
              id="description"
              rows="2"
              bind:value={editing.description}
              maxlength="3000"></textarea>
          </div>
          <div class="field">
            <label for="price">قیمت پایه (تومان)</label><input
              id="price"
              type="number"
              min="1"
              max="100000000"
              bind:value={editing.price}
              required
            />
          </div>
          <div class="field">
            <label for="inventory">موجودی قابل سفارش</label><input
              id="inventory"
              type="number"
              min="0"
              max="100000"
              bind:value={editing.inventory}
              required
            />
          </div>
          <div class="field">
            <label for="shipping">هزینهٔ ارسال (تومان)</label><input
              id="shipping"
              type="number"
              min="0"
              max="10000000"
              bind:value={editing.shipping_cost}
              required
            />
          </div>
          <div class="field">
            <label for="preparation">زمان آماده‌سازی (روز)</label><input
              id="preparation"
              type="number"
              min="0"
              max="365"
              bind:value={editing.preparation_days}
              required
            />
          </div>
          <div class="field full">
            <label for="aliases">نام‌های دیگر و کلیدواژه‌ها</label><input
              id="aliases"
              bind:value={aliases}
              placeholder="با ویرگول جدا کنید؛ مثلاً شمع، آوا"
            />
          </div>
          <div class="field">
            <label for="color">رنگ کارت محصول</label><select id="color" bind:value={editing.color}
              ><option value="sage">سبز</option><option value="sand">شنی</option><option value="rose"
                >صورتی</option
              ><option value="blue">آبی</option><option value="lilac">یاسی</option></select
            >
          </div>
          <label class="checkbox-label"
            ><input type="checkbox" bind:checked={editing.enabled} />قابل سفارش باشد</label
          >
        </div>
        <hr />
        <div class="requirements-heading">
          <h3>مشخصات و سؤال‌های محصول</h3>
          <button type="button" class="text-button" onclick={addRequirement}
            ><Icon name="plus" size={15} />افزودن مشخصه</button
          >
        </div>
        <p class="field-hint">
          مشتری فقط دربارهٔ اطلاعاتی که نداده است سؤال دریافت می‌کند. افزایش قیمت هر گزینه به قیمت واحد افزوده
          می‌شود.
        </p>
        {#each editing.requirements as requirement, i}<div class="requirement-editor">
            <div class="req-title">
              <strong>مشخصهٔ {fa(i + 1)}</strong><button
                class="icon-button"
                type="button"
                aria-label="حذف مشخصه"
                onclick={() =>
                  (editing = { ...editing, requirements: editing.requirements.filter((_, n) => n !== i) })}
                ><Icon name="close" size={15} /></button
              >
            </div>
            <div class="form-grid">
              <div class="field">
                <label for={'req-key-' + i}>شناسهٔ فنی</label><input
                  id={'req-key-' + i}
                  dir="ltr"
                  bind:value={requirement.key}
                  required
                  pattern="[a-z][a-z0-9_]*"
                  maxlength="50"
                />
              </div>
              <div class="field">
                <label for={'req-label-' + i}>عنوان سؤال</label><input
                  id={'req-label-' + i}
                  bind:value={requirement.label}
                  required
                  maxlength="100"
                />
              </div>
              <div class="field full">
                <label for={'req-options-' + i}>گزینه‌ها (جداشده با ویرگول؛ خالی برای پاسخ آزاد)</label><input
                  id={'req-options-' + i}
                  value={requirement.allowed_values.join('، ')}
                  onchange={(e) => setOptions(i, e.currentTarget.value)}
                />
              </div>
              <label class="checkbox-label"
                ><input type="checkbox" bind:checked={requirement.required} />پاسخ الزامی</label
              >
            </div>
            {#each requirement.allowed_values as option, j}<div class="adjustment">
                <label for={'adjustment-' + i + '-' + j}>افزایش قیمت «{option}»</label><input
                  id={'adjustment-' + i + '-' + j}
                  type="number"
                  min="0"
                  max="100000000"
                  value={requirement.price_adjustments[option] || 0}
                  onchange={(e) => {
                    requirement.price_adjustments = {
                      ...requirement.price_adjustments,
                      [option]: +e.currentTarget.value,
                    };
                    editing = { ...editing };
                  }}
                /><small>تومان</small>
              </div>{/each}
          </div>{/each}
        <div class="form-footer">
          <button type="button" class="btn secondary" onclick={() => (editing = null)}>انصراف</button><button
            class="btn"
            disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیرهٔ محصول'}</button
          >
        </div>
      </form>
    </dialog>
  </div>{/if}

<style>
  .product-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 22px;
  }
  .product-visual {
    height: 160px;
    background: var(--tone-f3eee4, #f3eee4);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
    color: var(--tone-b6a58b, #b6a58b);
  }
  .product-visual.sage {
    background: var(--tone-edf1e7, #edf1e7);
    color: var(--tone-a2b294, #a2b294);
  }
  .product-visual.rose {
    background: var(--tone-f3eae5, #f3eae5);
    color: var(--tone-bf9e91, #bf9e91);
  }
  .product-visual.lilac {
    background: var(--tone-edeaf2, #edeaf2);
    color: var(--tone-aaa0bb, #aaa0bb);
  }
  .product-visual.blue {
    background: var(--tone-e8eff1, #e8eff1);
    color: var(--tone-9db1b7, #9db1b7);
  }
  .product-visual > :global(svg) {
    z-index: 1;
  }
  .visual-ring {
    height: 180px;
    width: 180px;
    position: absolute;
    border: 1px solid currentColor;
    border-radius: 50%;
    opacity: 0.16;
    bottom: -85px;
    left: -30px;
    box-shadow:
      0 0 0 25px var(--tone-ffffff0d, #ffffff0d),
      0 0 0 50px var(--tone-ffffff22, #ffffff22);
  }
  .product-visual > span {
    position: absolute;
    right: 18px;
    top: 15px;
    font-size: 10px;
    border: 1px solid var(--tone-ffffff80, #ffffff80);
    background: var(--tone-ffffff45, #ffffff45);
    border-radius: 5px;
    padding: 3px 9px;
  }
  .product-visual b {
    position: absolute;
    left: 16px;
    top: 15px;
    font-size: 9px;
    color: var(--tone-9e998c, #9e998c);
    background: var(--tone-ffffffaa, #ffffffaa);
    padding: 4px 9px;
    border-radius: 4px;
    font-weight: 400;
  }
  .product-card.disabled {
    opacity: 0.65;
  }
  .product-content {
    padding: 17px 21px 0;
  }
  .product-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 5px;
  }
  .product-title h2 {
    font-size: 14px;
  }
  .product-content > p {
    font-size: 10px;
    color: var(--tone-9ca68f, #9ca68f);
    min-height: 42px;
    margin: 8px 0 20px;
  }
  .product-meta {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    align-items: center;
  }
  .product-meta strong {
    font-size: 14px;
    color: var(--tone-5c794b, #5c794b);
    font-weight: 500;
  }
  .product-meta > span {
    font-size: 9px;
    color: var(--tone-a4b095, #a4b095);
  }
  .product-details {
    display: flex;
    gap: 15px;
    margin: 18px 0;
    font-size: 9px;
    color: var(--tone-a9b29b, #a9b29b);
  }
  .product-details > span {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .product-footer {
    border-top: 1px solid var(--line);
    padding: 14px 0;
    display: flex;
    justify-content: space-between;
    gap: 10px;
  }
  .product-footer > span {
    font-size: 9px;
    color: var(--tone-9fac92, #9fac92);
  }
  .product-footer button {
    font-size: 9px;
  }
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    align-self: center;
    margin: 0;
    font-size: 11px;
    color: var(--tone-879877, #879877);
  }
  .checkbox-label input {
    width: 15px;
    min-height: 15px;
    accent-color: var(--tone-61854e, #61854e);
  }
  .requirements-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 10px;
  }
  .requirements-heading .text-button {
    font-size: 10px;
  }
  .requirement-editor {
    background: var(--tone-f1f4ec, #f1f4ec);
    border: 1px solid var(--tone-e5ebdd, #e5ebdd);
    border-radius: 10px;
    padding: 17px;
    margin-top: 15px;
  }
  .req-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }
  .req-title strong {
    font-size: 11px;
    color: var(--tone-94a183, #94a183);
  }
  .adjustment {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 15px;
  }
  .adjustment label {
    flex: 1;
    margin: 0;
    font-size: 10px;
  }
  .adjustment input {
    max-width: 130px;
    min-height: 36px;
    font-size: 11px;
    padding: 7px;
  }
  .adjustment small {
    color: var(--tone-a9b59a, #a9b59a);
    font-size: 9px;
  }
  @media (min-width: 1550px) {
    .product-grid {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
  }
  @media (max-width: 1150px) {
    .product-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (max-width: 580px) {
    .product-grid {
      grid-template-columns: 1fr;
    }
    .product-visual {
      height: 150px;
    }
    .requirement-editor {
      padding: 13px;
    }
  }
</style>
