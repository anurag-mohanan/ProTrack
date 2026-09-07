import { expect, type Page } from '@playwright/test';

export const E2E_EMAIL = process.env.E2E_EMAIL || 'admin@prosohm.com';
export const E2E_PASSWORD = process.env.E2E_PASSWORD || 'Password@123';

/** Fill login form and wait until we leave /login. */
export async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: /Welcome to/i })).toBeVisible();
  // MUI required fields expose accessible name as "Email *" / "Password *".
  await page.getByLabel(/Email/i).fill(E2E_EMAIL);
  await page.locator('input[type="password"]').fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Sign In' }).click();
  try {
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 30_000 });
  } catch (err) {
    const alert = page.getByRole('alert');
    if (await alert.count()) {
      throw new Error(`Login failed for ${E2E_EMAIL}: ${await alert.first().innerText()}`);
    }
    throw err;
  }
}

export async function gotoAuthenticated(page: Page, path: string): Promise<void> {
  await page.goto(path);
  if (page.url().includes('/login')) {
    await loginAsAdmin(page);
    await page.goto(path);
  }
  await expect(page).not.toHaveURL(/\/login/);
}
