import { test, expect } from '@playwright/test';

const initialState = () => ({
  token: 'local-feedback-test',
  handover: false,
  channel: 'local',
  messages: [
    { id: 1, role: 'assistant', text: 'سلام، چه سفارشی می‌خواهید؟', created_at: '2026-11-04T12:00:00Z' },
  ],
  summary: null,
  order: null,
  payment: null,
  tracking_url: null,
  ready_to_confirm: false,
});

async function mockChat(page, handleMessage) {
  let state = initialState();
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/auth/me') return route.fulfill({ status: 401, json: { detail: 'ورود لازم است.' } });
    if (path === '/api/catalog') return route.fulfill({ json: [] });
    if (path.endsWith('/messages'))
      return handleMessage(route, (next) => {
        state = next;
      });
    return route.fulfill({ json: state });
  });
  await page.goto('/chat');
  await expect(page.getByText(initialState().messages[0].text, { exact: true })).toBeVisible();
}

for (const mode of ['desktop', 'mobile-dark']) {
  test(`انتظار پاسخ بدون قفل صفحه و حفظ پیش‌نویس بعدی؛ ${mode}`, async ({ page }) => {
    if (mode === 'mobile-dark') {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
    }
    let release;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    const requests = [];
    let navigations = 0;
    page.on('framenavigated', (frame) => {
      if (frame === page.mainFrame()) navigations++;
    });
    await mockChat(page, async (route, setState) => {
      const payload = route.request().postDataJSON();
      requests.push(payload);
      await gate;
      const response = {
        ...initialState(),
        messages: [
          ...initialState().messages,
          { id: 2, role: 'customer', text: payload.text, created_at: '2026-11-04T12:01:00Z' },
          { id: 3, role: 'assistant', text: 'چه رایحه‌ای دوست دارید؟', created_at: '2026-11-04T12:01:01Z' },
        ],
      };
      setState(response);
      await route.fulfill({ json: response });
    });
    const input = page.getByRole('textbox', { name: 'پیام شما', exact: true });
    const send = page.getByRole('button', { name: 'ارسال پیام', exact: true });
    await input.fill('دو عدد شمع می‌خواهم.');
    await send.click();
    await expect(page.getByRole('status')).toHaveText('در حال آماده‌کردن پاسخ…');
    await expect(page.getByText('دو عدد شمع می‌خواهم.', { exact: true })).toBeVisible();
    await expect(input).toHaveValue('');
    await expect(input).toBeFocused();
    await input.fill('رایحهٔ وانیل باشد.');
    await input.press('Enter');
    await expect.poll(() => requests.length).toBe(1);
    expect(await send.evaluate((node) => getComputedStyle(node).cursor)).toBe('default');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({ path: `../artifacts/chat-wait-${mode}.png`, fullPage: true });
    release();
    await expect(page.getByText('چه رایحه‌ای دوست دارید؟', { exact: true })).toBeVisible();
    await expect(page.getByRole('status')).toHaveCount(0);
    await expect(page.getByText('دو عدد شمع می‌خواهم.', { exact: true })).toHaveCount(1);
    await expect(input).toHaveValue('رایحهٔ وانیل باشد.');
    await expect(send).toBeEnabled();
    expect(navigations).toBe(1);
  });
}

test('تلاش دوباره پس از خطای شبکه شناسهٔ همان پیام و پیش‌نویس بعدی را حفظ می‌کند', async ({ page }) => {
  const requests = [];
  await mockChat(page, async (route) => {
    const payload = route.request().postDataJSON();
    requests.push(payload);
    if (requests.length === 1) return route.abort('failed');
    return route.fulfill({
      json: {
        ...initialState(),
        messages: [
          ...initialState().messages,
          { id: 2, role: 'customer', text: payload.text, created_at: '2026-11-04T12:01:00Z' },
          { id: 3, role: 'assistant', text: 'پیام شما دریافت شد.', created_at: '2026-11-04T12:01:01Z' },
        ],
      },
    });
  });
  const input = page.getByRole('textbox', { name: 'پیام شما', exact: true });
  await input.fill('دو عدد شمع می‌خواهم.');
  await page.getByRole('button', { name: 'ارسال پیام', exact: true }).click();
  await expect(page.getByText('ارسال پیام تأیید نشد', { exact: true })).toBeVisible();
  await input.fill('این متن بعدی است.');
  await page.getByRole('button', { name: 'تلاش دوباره', exact: true }).click();
  await expect(page.getByText('پیام شما دریافت شد.', { exact: true })).toBeVisible();
  expect(requests).toHaveLength(2);
  expect(requests[1].client_id).toBe(requests[0].client_id);
  await expect(input).toHaveValue('این متن بعدی است.');
  await expect(page.getByText('دو عدد شمع می‌خواهم.', { exact: true })).toHaveCount(1);
});
