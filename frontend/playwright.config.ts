import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173';
const apiURL = process.env.E2E_API_URL || 'http://127.0.0.1:8000';
const reuse = !process.env.CI;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  globalSetup: './e2e/global-setup.ts',
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
  },
  projects: [
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: path.join('e2e', '.auth', 'admin.json'),
      },
      dependencies: ['setup'],
      testIgnore: /.*\.setup\.ts/,
    },
  ],
  webServer: [
    {
      command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: rootDir,
      url: `${apiURL}/health`,
      reuseExistingServer: reuse,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      url: baseURL,
      reuseExistingServer: reuse,
      timeout: 120_000,
    },
  ],
});
