import { test as setup, expect } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loginAsAdmin } from './helpers/auth';

const authFile = path.join(path.dirname(fileURLToPath(import.meta.url)), '.auth', 'admin.json');

setup('authenticate as admin', async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page).toHaveURL(/\/(dashboard|change-password)/);
  // Soft-launch may force password change; still persist session for subsequent smoke checks.
  await page.context().storageState({ path: authFile });
});
