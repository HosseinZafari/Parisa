export async function api(path, options = {}) {
  const method = options.method || 'GET';
  const response = await fetch('/api' + path, {
    credentials: 'same-origin',
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(method !== 'GET' ? { 'Idempotency-Key': options.key || crypto.randomUUID() } : {}),
      ...options.headers,
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
  });
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error('پاسخ سرور قابل خواندن نیست.');
  }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/'))
      window.dispatchEvent(new Event('session-expired'));
    throw new Error(
      typeof body.detail === 'string' ? body.detail : 'درخواست انجام نشد؛ اطلاعات را بررسی کنید.',
    );
  }
  return body;
}

export const fa = (value) => new Intl.NumberFormat('fa-IR').format(value ?? 0);
export const money = (value) => fa(value) + ' تومان';
export const date = (value, withTime = false) =>
  value
    ? new Intl.DateTimeFormat('fa-IR', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
        timeZone: 'Asia/Tehran',
      }).format(new Date(value.length === 10 ? value + 'T12:00:00Z' : value))
    : 'تعیین نشده';
export const shortDate = (value) =>
  new Intl.DateTimeFormat('fa-IR', { weekday: 'short', timeZone: 'Asia/Tehran' }).format(
    new Date(value + 'T12:00:00Z'),
  );
export const statuses = {
  awaiting_payment: 'در انتظار پرداخت',
  paid_awaiting_preparation: 'منتظر آماده‌سازی',
  in_preparation: 'در حال آماده‌سازی',
  ready_to_ship: 'آمادهٔ ارسال',
  change_requested: 'درخواست تغییر',
  awaiting_seller_approval: 'منتظر تأیید شما',
  shipped: 'ارسال‌شده',
  canceled: 'لغوشده',
};
export const changeLabels = {
  pending: 'منتظر بررسی',
  approved: 'تأییدشده',
  rejected: 'ردشده',
  manual: 'پیگیری دستی',
};
export const paymentLabels = {
  pending: 'در انتظار پرداخت',
  success: 'موفق',
  failed: 'ناموفق',
  canceled: 'لغوشده',
  expired: 'منقضی‌شده',
};
export function navigate(path) {
  history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
export async function copy(text) {
  await navigator.clipboard.writeText(text);
}
