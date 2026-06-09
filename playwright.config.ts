import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'list' : 'html',

  use: {
    baseURL: 'http://localhost:5000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    headless: true,
  },

  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],

  webServer: {
    command: 'script/server',
    url: 'http://localhost:5000',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    // Run the app against the deterministic fake AI client so the E2E flow is
    // hermetic (no GitHub Models token or network). script/server only sets
    // vars from .env that aren't already in the environment, so this wins.
    env: { USE_FAKE_AI: '1' },
  },
});
