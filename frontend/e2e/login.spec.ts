import { test, expect } from '@playwright/test';
import { E2E_EMAIL, E2E_PASSWORD } from './helpers/auth';

test.describe('Login', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('shows login form and rejects bad password', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: /Welcome to/i })).toBeVisible();
    await page.getByLabel(/Email/i).fill(E2E_EMAIL);
    await page.locator('input[type="password"]').fill('DefinitelyWrongPassword!');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 });
    await expect(page).toHaveURL(/\/login/);
  });

  test('signs in with valid credentials', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel(/Email/i).fill(E2E_EMAIL);
    await page.locator('input[type="password"]').fill(E2E_PASSWORD);
    await page.getByRole('button', { name: 'Sign In' }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 30_000 });
    await expect(page).not.toHaveURL(/\/login/);
  });
});
