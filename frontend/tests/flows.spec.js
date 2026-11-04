import { test, expect } from '@playwright/test';

async function login(page) {
  await page.goto('/dashboard');
  await expect(
    page.getByLabel('گذرواژه', { exact: true }).or(page.getByRole('heading', { name: /سلام پریسا/ })),
  ).toBeVisible();
  if (await page.getByLabel('گذرواژه', { exact: true }).isVisible()) {
    await page.getByLabel('نام کاربری', { exact: true }).fill(process.env.E2E_USERNAME || 'parisa');
    await page.getByLabel('گذرواژه', { exact: true }).fill(process.env.E2E_PASSWORD || 'parisa-demo-1405');
    await page.getByRole('button', { name: 'ورود به دفتر', exact: true }).click();
  }
  await expect(page.getByRole('heading', { name: /سلام پریسا/ })).toBeVisible();
}

test('میز کار، کاتالوگ و نمایش موبایل', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await login(page);
  await expect(page.getByRole('heading', { name: /اول از کجا شروع کنم/ })).toBeVisible();
  await page.screenshot({ path: '../artifacts/dashboard-desktop.png', fullPage: true });
  await page.getByRole('link', { name: 'محصولات', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'محصولات فروشگاه' })).toBeVisible();
  await page.getByRole('button', { name: 'محصول تازه', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: /سلام پریسا/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: /اول از کجا شروع کنم/ })).toBeVisible();
  await page.screenshot({ path: '../artifacts/dashboard-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole('button', { name: 'باز کردن فهرست' }).click();
  await page.getByRole('link', { name: 'مشتری‌ها', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'مشتری‌های شما', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('گفتگو، اصلاح، خلاصه، پرداخت تکراری، تغییر با پرداخت تکمیلی و ارسال', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/chat');
  const input = page.getByRole('textbox', { name: 'پیام شما' });
  await expect(page.getByText('سلام! خوش آمدید', { exact: false })).toBeVisible();
  async function send(text) {
    await input.fill(text);
    const pending = page.waitForResponse(
      (r) => /\/api\/chat\/.*\/messages$/.test(r.url()) && r.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'ارسال پیام', exact: true }).click();
    const response = await pending;
    expect(response.ok()).toBeTruthy();
    return response.json();
  }
  await send('دو عدد شمع آوا، وانیل، کوچک، معمولی');
  await send('اصلاح تعداد: ۱');
  const summary = await send(
    'نام: سارا آزمایشی؛ شهر: تهران؛ تلفن: ۰۹۱۲۰۰۰۰۰۰۰؛ آدرس: خیابان نمونه پلاک ۱۲؛ کد پستی: ۱۱۱۱۱۱۱۱۱۱',
  );
  expect(summary.ready_to_confirm).toBeTruthy();
  await page.screenshot({ path: '../artifacts/chat-summary.png', fullPage: true });
  const response = page.waitForResponse(
    (r) => /\/api\/chat\/.*\/messages$/.test(r.url()) && r.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'تأیید خلاصه و دریافت پیوند پرداخت' }).click();
  const state = await (await response).json();
  expect(state.order.status).toBe('awaiting_payment');
  const orderId = state.order.id;
  const trackingUrl = state.tracking_url;
  await page.getByRole('link', { name: 'پرداخت آزمایشی', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'یک قدم تا ثبت پرداخت آزمایشی' })).toBeVisible();
  await page.getByRole('button', { name: 'شبیه‌سازی پرداخت موفق' }).click();
  await expect(page.getByRole('heading', { name: 'پرداخت آزمایشی موفق بود' })).toBeVisible();
  await page.getByRole('button', { name: 'آزمایش تأیید تکراری پرداخت' }).click();
  await expect(page.getByText('این رویداد قبلاً ثبت شده است', { exact: false })).toBeVisible();
  await login(page);
  await page.goto('/chat');
  await send('تغییر تعداد: ۲');
  await page.goto('/orders/' + orderId);
  await expect(page.getByText('درخواست تغییر در انتظار بررسی است', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'ثبت تحویل و ارسال' })).toBeDisabled();
  await page.getByRole('button', { name: 'بررسی مبلغ و موعد تازه' }).click();
  await page.getByRole('button', { name: 'تأیید نهایی تغییر' }).click();
  await expect(page.getByText('ماندهٔ پرداخت', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'ساخت / باز کردن پرداخت آزمایشی' }).click();
  await page.getByRole('button', { name: 'شبیه‌سازی پرداخت موفق' }).click();
  await expect(page.getByRole('heading', { name: 'پرداخت آزمایشی موفق بود' })).toBeVisible();
  await page.goto('/orders/' + orderId);
  for (const status of ['in_preparation', 'ready_to_ship']) {
    await page.getByLabel('تغییر وضعیت').selectOption(status);
    await page.getByRole('button', { name: 'ذخیرهٔ وضعیت', exact: true }).click();
    await expect(page.getByLabel('تغییر وضعیت')).toHaveValue('');
  }
  await page.getByLabel('کد رهگیری', { exact: true }).fill('123456789012345678901234');
  await page.getByRole('button', { name: 'ثبت تحویل و ارسال' }).click();
  await expect(page.getByText('ارسال در ', { exact: false }).first()).toBeVisible();
  await page.getByLabel('یادداشت خصوصی فروشنده').fill('بسته به پست تحویل داده شد؛ رسید نگهداری شود.');
  await page.getByRole('button', { name: 'ذخیرهٔ اطلاعات', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('تغییرات ذخیره شد.');
  await page.goto(new URL(trackingUrl).pathname);
  await expect(page.getByText('بسته به پست تحویل داده شد.', { exact: true })).toBeVisible();
  await expect(page.getByText('123456789012345678901234', { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('ایجاد و ویرایش محصول با مشخصات و تغییر موجودی', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'محصولات', exact: true }).click();
  await page.getByRole('button', { name: 'محصول تازه', exact: true }).click();
  const name = 'محصول آزمایشی ' + Date.now();
  await page.getByLabel('نام محصول', { exact: true }).fill(name);
  await page.getByLabel('دسته‌بندی', { exact: true }).fill('آزمایشی');
  await page.getByLabel('قیمت پایه (تومان)', { exact: true }).fill('45000');
  await page.getByLabel('موجودی قابل سفارش', { exact: true }).fill('9');
  await page.getByLabel('هزینهٔ ارسال (تومان)', { exact: true }).fill('5000');
  await page.getByRole('button', { name: 'افزودن مشخصه', exact: true }).click();
  await page.getByLabel('شناسهٔ فنی', { exact: true }).fill('color');
  await page.getByLabel('عنوان سؤال', { exact: true }).fill('رنگ');
  await page.getByLabel('گزینه‌ها', { exact: false }).fill('آبی، سبز');
  await page.getByLabel('عنوان سؤال', { exact: true }).focus();
  await page.getByRole('button', { name: 'ذخیرهٔ محصول', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByLabel('جستجوی محصول').fill(name);
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'ویرایش ' + name, exact: true }).click();
  await page.getByLabel('موجودی قابل سفارش', { exact: true }).fill('7');
  await page.getByRole('button', { name: 'ذخیرهٔ محصول', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByText('۷ عدد موجود', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'غیرفعال کردن', exact: true }).click();
  await expect(page.getByRole('button', { name: 'فعال کردن', exact: true })).toBeVisible();
});
