import { test, expect } from '@playwright/test';
import { gotoAuthenticated } from './helpers/auth';

test.describe('Resource Planning', () => {
  test('loads hierarchy tabs: Forecast and Reports', async ({ page }) => {
    await gotoAuthenticated(page, '/resource-planning');
    const main = page.getByRole('main');
    // Page title is h5; sidebar also has an h6 "Resource Planning" link title.
    await expect(main.getByRole('heading', { name: 'Resource Planning', level: 5 })).toBeVisible();

    await expect(main.getByRole('tab', { name: 'Capacity & projects' })).toBeVisible();
    await expect(main.getByRole('tab', { name: 'Shifts & people' })).toBeVisible();
    await expect(main.getByRole('tab', { name: 'Computers & software' })).toBeVisible();
    await expect(main.getByRole('tab', { name: 'Forecast' })).toBeVisible();
    await expect(main.getByRole('tab', { name: 'Reports' })).toBeVisible();
    await expect(main.getByRole('tab', { name: 'Data quality' })).toBeVisible();

    await main.getByRole('tab', { name: 'Forecast' }).click();
    await expect(main.getByText('Capacity what-if')).toBeVisible();
    await expect(main.getByText('Hire impact forecast')).toBeVisible();

    await main.getByRole('tab', { name: 'Reports' }).click();
    await expect(main.getByText('IT readiness report')).toBeVisible();
    await expect(main.getByText('Data quality summary')).toBeVisible();
  });

  test('shifts calendar exposes Day / Week / Month modes', async ({ page }) => {
    await gotoAuthenticated(page, '/resource-planning');
    const main = page.getByRole('main');

    await main.getByRole('tab', { name: 'Shifts & people' }).click();
    // Scope to main — nav also has a "Calendar" link to /calendar.
    await main.getByRole('button', { name: 'Calendar' }).click();
    await expect(main.getByRole('heading', { name: 'Shift calendar' })).toBeVisible({
      timeout: 20_000,
    });

    await expect(main.getByRole('button', { name: 'Day' })).toBeVisible();
    await expect(main.getByRole('button', { name: 'Week' })).toBeVisible();
    await expect(main.getByRole('button', { name: 'Month' })).toBeVisible();
  });
});
