import { test, expect } from '@playwright/test';
import { gotoAuthenticated } from './helpers/auth';

test.describe('IT Computers', () => {
  test('computers page loads and exposes NIC management affordance when permitted', async ({
    page,
  }) => {
    await gotoAuthenticated(page, '/it/computers');
    await expect(page.getByText(/computer/i).first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole('button', { name: 'View as inventory' })).toBeVisible();

    // Grid or empty state should render; NICs button appears for manage-capable users on rows.
    const nics = page.getByRole('button', { name: 'NICs' });
    if (await nics.count()) {
      await nics.first().click();
      await expect(page.getByRole('dialog')).toBeVisible();
      await expect(page.getByText(/Network interfaces/i)).toBeVisible();
      await page.getByRole('button', { name: 'Close' }).click();
    }
  });

  test('inventory Computers tab shows computer columns and no top-level Network hub', async ({
    page,
  }) => {
    await gotoAuthenticated(page, '/it/assets?category=computer');
    const main = page.getByRole('main');
    await expect(main.getByRole('tab', { name: 'Computers' })).toBeVisible({ timeout: 20_000 });
    await expect(main.getByRole('columnheader', { name: 'Computer' })).toBeVisible();
    await expect(main.getByRole('columnheader', { name: 'IP' })).toBeVisible();
    await expect(main.getByRole('columnheader', { name: 'User' })).toBeVisible();

    await expect(page.getByRole('link', { name: 'Assets & Inventory' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Network / IP' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: /^Networks$/ })).toHaveCount(0);
  });

  test('software installations tab is reachable from the software hub', async ({ page }) => {
    await gotoAuthenticated(page, '/it/software?tab=installations');
    const main = page.getByRole('main');
    await expect(main.getByRole('tab', { name: 'Installations' })).toBeVisible({ timeout: 20_000 });
  });
});
