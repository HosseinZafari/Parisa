import { test, expect } from '@playwright/test';

const stamp = '2026-11-04T12:00:00Z';
const summary = (id, name, extra = {}) => ({
  id,
  customer_name: name,
  customer_username: 'test_' + id,
  customer_id: id,
  order_id: null,
  handover: false,
  channel: 'local',
  updated_at: stamp,
  last_message: 'آخرین پیام',
  attention_status: 'none',
  attention_priority: 'normal',
  handover_reason: '',
  ...extra,
});
const message = (id, role, text) => ({ id, role, text, created_at: stamp, delivery_status: 'saved' });
const detail = (id, messages, extra = {}) => ({
  id,
  handover: false,
  order_id: null,
  attention_status: 'none',
  attention_priority: 'normal',
  handover_reason: '',
  messages,
  ...extra,
});

async function mockPanel(page, list, handleDetail, handleAttention) {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 1, name: 'پریسا', username: 'seller' } });
    if (path === '/api/notifications') return route.fulfill({ json: [] });
    if (path === '/api/conversations') return route.fulfill({ json: list });
    if (path.endsWith('/attention')) return handleAttention(route);
    const id = Number(path.split('/').at(-1));
    return handleDetail(route, id);
  });
}

test('تمام نقش‌ها دیده می‌شوند و پاسخ تازهٔ دستیار همراه پیش‌نویس فروشنده در دید می‌ماند', async ({
  page,
}) => {
  await page.clock.install();
  const messages = Array.from({ length: 16 }, (_, i) =>
    message(
      i + 1,
      i % 2 ? 'assistant' : 'customer',
      'پیام نمونهٔ سابقه ' + i + '\n' + 'جزئیات سفارش و گفتگو. '.repeat(8),
    ),
  );
  messages.push(message(17, 'seller', 'پاسخ قبلی فروشنده'));
  const list = [summary(1, 'سارا آزمایشی')];
  await mockPanel(page, list, (route) => route.fulfill({ json: detail(1, messages) }));
  await page.goto('/conversations?id=1');
  await expect(page.getByRole('heading', { name: 'سارا آزمایشی', exact: true })).toBeVisible();
  await expect(page.locator('[data-message-role="assistant"]')).toHaveCount(8);
  await expect(page.getByText('دستیار هوش مصنوعی', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('پاسخ قبلی فروشنده', { exact: true })).toBeInViewport();
  await page.getByLabel('پاسخ شما به مشتری', { exact: true }).fill('پیش‌نویس پاسخ من');
  messages.push(message(18, 'assistant', 'پاسخ تازهٔ ربات دربارهٔ بسته‌بندی'));
  await page.clock.runFor(8100);
  await expect(page.getByText('پاسخ تازهٔ ربات دربارهٔ بسته‌بندی', { exact: true })).toBeInViewport();
  await expect(page.getByLabel('پاسخ شما به مشتری', { exact: true })).toHaveValue('پیش‌نویس پاسخ من');
  await expect(page.locator('.conversation-row.active')).toContainText('سارا آزمایشی');

  await page.locator('.conversation-messages').evaluate((node) => {
    node.scrollTop = 0;
  });
  messages.push(message(19, 'assistant', 'پاسخ دیگری که هنگام خواندن سابقه رسید'));
  await page.clock.runFor(8100);
  await expect(page.getByRole('button', { name: /۱ پیام تازه/ })).toBeVisible();
  expect(await page.locator('.conversation-messages').evaluate((node) => node.scrollTop)).toBe(0);
  await page.getByRole('button', { name: /۱ پیام تازه/ }).click();
  await expect(page.getByText('پاسخ دیگری که هنگام خواندن سابقه رسید', { exact: true })).toBeInViewport();
  await page.screenshot({ path: '../artifacts/seller-conversations-bot-visible.png', fullPage: true });
});

test('پاسخ دیررس گفتگوی قبلی با گفتگوی انتخاب‌شدهٔ تازه قاطی نمی‌شود', async ({ page }) => {
  const list = [summary(1, 'سارا آزمایشی'), summary(2, 'نگار آزمایشی')];
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  await mockPanel(page, list, async (route, id) => {
    if (id === 1) await gate;
    await route.fulfill({
      json: detail(id, [
        message(id * 10, 'assistant', id === 1 ? 'پاسخ دستیار برای سارا' : 'پاسخ دستیار برای نگار'),
      ]),
    });
  });
  await page.goto('/conversations');
  await page.locator('.conversation-row').filter({ hasText: 'سارا آزمایشی' }).click();
  await page.locator('.conversation-row').filter({ hasText: 'نگار آزمایشی' }).click();
  await expect(page.getByText('پاسخ دستیار برای نگار', { exact: true })).toBeVisible();
  release();
  await expect(page.getByRole('heading', { name: 'نگار آزمایشی', exact: true })).toBeVisible();
  await expect(page.getByText('پاسخ دستیار برای سارا', { exact: true })).toHaveCount(0);
  await expect(page).toHaveURL(/\?id=2$/);
});

test('ارجاع فوری در بالای صف و از پیوند مستقیم باز می‌شود و رسیدگی‌شده پایین می‌رود', async ({ page }) => {
  const list = [
    summary(1, 'رسیدگی‌شده', { handover: true, attention_status: 'resolved' }),
    summary(2, 'نیازمند پاسخ', { attention_status: 'open' }),
    summary(3, 'مشتری فوری', {
      attention_status: 'open',
      attention_priority: 'urgent',
      handover_reason: 'مشکل جدی سفارش گزارش شده است.',
    }),
  ];
  const requests = [];
  await mockPanel(
    page,
    list,
    (route, id) =>
      route.fulfill({
        json: detail(
          id,
          [message(1, 'assistant', 'موضوع برای فروشنده ثبت شد.')],
          list.find((c) => c.id === id),
        ),
      }),
    async (route) => {
      const body = route.request().postDataJSON();
      requests.push(body);
      expect(route.request().headers()['idempotency-key']).toBeTruthy();
      Object.assign(list[2], { attention_status: 'resolved', handover: true, attention_resolved_at: stamp });
      await route.fulfill({ json: detail(3, [], list[2]) });
    },
  );
  await page.goto('/conversations?id=3');
  await expect(page.locator('.conversation-row').first()).toContainText('مشتری فوری');
  await expect(page.getByText('این گفتگو به رسیدگی فوری نیاز دارد.', { exact: true })).toBeVisible();
  await expect(page.getByText('مشکل جدی سفارش گزارش شده است.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'رسیدگی شد', exact: true }).click();
  await expect(page.locator('.conversation-row').first()).toContainText('نیازمند پاسخ');
  await expect(page.getByRole('heading', { name: 'مشتری فوری', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'فعال‌کردن دستیار', exact: true })).toBeVisible();
  expect(requests).toEqual([{ action: 'resolve', resume_bot: false }]);
});
