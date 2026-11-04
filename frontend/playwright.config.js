import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 60000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    channel: process.env.PLAYWRIGHT_CHANNEL || (process.platform === 'win32' ? 'chrome' : undefined),
    baseURL: 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 1080 },
    locale: 'fa-IR',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
