<script>
  import Icon from './Icon.svelte';
  import Status from './Status.svelte';
  import { fa, money, date, navigate } from '../lib/api';
  export let orders = [];
  export let compact = false;
</script>

<div class="table-scroll desktop-orders">
  <table class="order-table">
    <thead
      ><tr
        ><th>سفارش / مشتری</th><th>محصول</th><th>وضعیت</th><th>موعد ارسال</th>{#if !compact}<th>مبلغ سفارش</th
          >{/if}<th>اقدام بعدی</th><th><span class="sr-only">جزئیات</span></th></tr
      ></thead
    >
    <tbody>
      {#each orders as order}
        <tr class:late={order.overdue}>
          <td
            ><button class="customer-cell" onclick={() => navigate('/orders/' + order.id)}
              ><span class="avatar tone-{order.id % 4}">{order.customer_name.slice(0, 1)}</span><span
                ><strong>{order.customer_name}</strong><small>سفارش <bdi>#{fa(1000 + order.id)}</bdi></small
                ></span
              ></button
            ></td
          >
          <td
            ><span class="product-cell">{order.product_name}</span><small>{fa(order.quantity)} عدد</small></td
          >
          <td><Status status={order.status} /></td>
          <td
            ><span class:danger-text={order.overdue} class="deadline"
              >{#if order.overdue}<Icon name="alert" size={14} />{/if}{date(order.deadline)}</span
            >{#if order.overdue}<small class="danger-text">از موعد گذشته</small>{/if}</td
          >
          {#if !compact}<td class="amount">{money(order.total)}</td>{/if}
          <td
            ><button class="action-link" onclick={() => navigate('/orders/' + order.id)}
              >{order.next_action}</button
            ></td
          >
          <td
            ><button
              class="icon-button row-arrow"
              aria-label={'جزئیات سفارش ' + fa(order.id)}
              onclick={() => navigate('/orders/' + order.id)}><Icon name="chevron" size={17} /></button
            ></td
          >
        </tr>
      {:else}<tr
          ><td colspan={compact ? 6 : 7}
            ><div class="empty">
              <Icon name="orders" size={34} /><strong>سفارشی با این شرایط پیدا نشد.</strong><span
                >فیلتر دیگری را امتحان کنید یا یک گفتگوی آزمایشی شروع کنید.</span
              >
            </div></td
          ></tr
        >{/each}
    </tbody>
  </table>
</div>

<div class="mobile-orders">
  {#each orders as order}
    <article class="mobile-order" class:late={order.overdue}>
      <div class="mobile-order-head">
        <button class="customer-cell" onclick={() => navigate('/orders/' + order.id)}>
          <span class="avatar tone-{order.id % 4}">{order.customer_name.slice(0, 1)}</span>
          <span
            ><strong>{order.customer_name}</strong><small>سفارش <bdi>#{fa(1000 + order.id)}</bdi></small
            ></span
          >
        </button>
        <Status status={order.status} />
      </div>
      <div class="mobile-product">
        <span>{order.product_name}</span><span
          >{fa(order.quantity)} عدد{#if !compact}
            · {money(order.total)}{/if}</span
        >
      </div>
      <div class="mobile-order-foot">
        <span class:danger-text={order.overdue}
          ><Icon name={order.overdue ? 'alert' : 'calendar'} size={13} />{date(
            order.deadline,
          )}{#if order.overdue}<small>از موعد گذشته</small>{/if}</span
        >
        <button class="btn secondary small" onclick={() => navigate('/orders/' + order.id)}
          >{order.next_action}<Icon name="chevron" size={13} /></button
        >
      </div>
    </article>
  {:else}
    <div class="empty"><Icon name="orders" size={30} /><strong>سفارشی با این شرایط پیدا نشد.</strong></div>
  {/each}
</div>

<style>
  .mobile-orders {
    display: none;
  }
  @media (max-width: 700px) {
    .desktop-orders {
      display: none;
    }
    .mobile-orders {
      display: grid;
    }
    .mobile-order {
      padding: 18px 16px;
      border-top: 1px solid var(--line);
    }
    .mobile-order.late {
      background: var(--tone-fffcf8, #fffcf8);
    }
    .mobile-order-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }
    .customer-cell {
      gap: 8px;
    }
    .customer-cell strong {
      font-size: 11px;
    }
    .customer-cell small {
      display: block;
      font-size: 9px;
      color: var(--tone-a0ad94, #a0ad94);
      margin-top: 4px;
    }
    .mobile-order-head :global(.status-badge) {
      font-size: 8px;
      padding: 5px 6px;
    }
    .mobile-product {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 10px;
      color: var(--tone-8c9c7b, #8c9c7b);
      margin: 18px 0;
    }
    .mobile-product > span:last-child {
      color: var(--tone-a8b39a, #a8b39a);
      font-size: 9px;
    }
    .mobile-order-foot {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }
    .mobile-order-foot > span {
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: 9px;
      flex-wrap: wrap;
    }
    .mobile-order-foot small {
      display: block;
      width: 100%;
      font-size: 8px;
      padding-right: 18px;
    }
    .mobile-order-foot .btn {
      font-size: 9px;
      min-height: 36px;
      padding: 8px 10px;
    }
  }
</style>
