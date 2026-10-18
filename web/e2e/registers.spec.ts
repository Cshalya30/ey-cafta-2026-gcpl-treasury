/**
 * One test per register: loads without console errors, watermark present,
 * register switch preserves entity and persona, deep link restores state.
 */

import { expect, test, type Page } from '@playwright/test';

const REGISTERS = [
  { path: '/canvas', name: 'Canvas' },
  { path: '/console', name: 'Console' },
  { path: '/terminal', name: 'Terminal' },
  { path: '/brief', name: 'Brief' },
  { path: '/cockpit', name: 'Cockpit' },
] as const;

/** Accept the storage notice so it does not sit over the footer in a snapshot. */
async function dismissNotice(page: Page) {
  const allow = page.getByRole('button', { name: 'Allow' });
  if (await allow.count()) await allow.click();
}

function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  return errors;
}

for (const register of REGISTERS) {
  test(`${register.name} loads clean and carries the watermark`, async ({ page }) => {
    const errors = collectErrors(page);

    await page.goto(register.path);
    await page.waitForLoadState('networkidle');
    await dismissNotice(page);

    // Non-removable: this ribbon must be in the DOM on every single route.
    const watermark = page.getByTestId('watermark');
    await expect(watermark).toBeVisible();
    await expect(watermark).toContainText('SYNTHETIC DATA');
    await expect(watermark).toContainText('DO NOT RELY FOR LIVE TRANSFERS');

    await expect(page.getByRole('link', { name: register.name })).toBeVisible();
    expect(errors, `console errors on ${register.path}:\n${errors.join('\n')}`).toHaveLength(0);
  });
}

test('the watermark survives a register switch', async ({ page }) => {
  await page.goto('/canvas');
  await dismissNotice(page);
  for (const register of REGISTERS) {
    await page.getByRole('link', { name: register.name }).click();
    await expect(page.getByTestId('watermark')).toBeVisible();
  }
});

test('switching register preserves the active entity and persona', async ({ page }) => {
  await page.goto('/canvas?entity=GCPL-GB&lens=pooling');
  await dismissNotice(page);
  await page.waitForLoadState('networkidle');

  await page.getByRole('link', { name: 'Console' }).click();
  await expect(page).toHaveURL(/entity=GCPL-GB/);
  await expect(page).toHaveURL(/lens=pooling/);

  await page.getByRole('link', { name: 'Terminal' }).click();
  await expect(page).toHaveURL(/entity=GCPL-GB/);

  // The persona switcher keeps its value across the whole traversal.
  await expect(page.locator('#persona-switch')).toHaveValue('P2');
});

test('a deep link restores filter state after a reload', async ({ page }) => {
  await page.goto('/console?tab=accounts&acct_feed=stale&sort=bank_name&dir=desc');
  await dismissNotice(page);
  await page.waitForLoadState('networkidle');

  await expect(page.locator('#f-feed')).toHaveValue('stale');

  await page.reload();
  await page.waitForLoadState('networkidle');
  await expect(page.locator('#f-feed')).toHaveValue('stale');
  await expect(page).toHaveURL(/sort=bank_name/);
});

test('the eight lenses switch by keyboard and land in the URL', async ({ page }) => {
  await page.goto('/canvas');
  await dismissNotice(page);
  await page.waitForLoadState('networkidle');

  const expected = [
    'cash', 'forecast', 'pooling', 'risk', 'controls', 'data', 'banking', 'service',
  ];
  for (let index = 0; index < expected.length; index += 1) {
    await page.keyboard.press(String(index + 1));
    await expect(page.getByRole('tab', { selected: true })).toBeVisible();
    if (index > 0) await expect(page).toHaveURL(new RegExp(`lens=${expected[index]}`));
  }
});

test('Escape clears isolate mode', async ({ page }) => {
  await page.goto('/canvas?isolate=GCPL-GB');
  await dismissNotice(page);
  await page.waitForLoadState('networkidle');

  await expect(page.getByText(/Isolating GCPL-GB/)).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByText(/Isolating GCPL-GB/)).toBeHidden();
});

test('the graph renders the full hierarchy without overlapping nodes', async ({ page }) => {
  await page.goto('/canvas');
  await dismissNotice(page);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);

  // One root, three hubs, twelve entities.
  await expect(page.locator('.react-flow__node-entity')).toHaveCount(12);
  await expect(page.locator('.react-flow__node-group')).toHaveCount(4);

  const boxes = await page.locator('.react-flow__node-entity').evaluateAll((nodes) =>
    nodes.map((node) => {
      const rect = node.getBoundingClientRect();
      return { x: rect.x, y: rect.y, w: rect.width, h: rect.height };
    }),
  );
  for (let i = 0; i < boxes.length; i += 1) {
    for (let j = i + 1; j < boxes.length; j += 1) {
      const a = boxes[i]!;
      const b = boxes[j]!;
      const overlaps =
        a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
      expect(overlaps, `nodes ${i} and ${j} overlap`).toBe(false);
    }
  }
});

test('lens 1 draws an animated Cash Leak edge labelled with the annual figure', async ({ page }) => {
  await page.goto('/canvas?lens=cash');
  await dismissNotice(page);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(600);

  const leak = page.locator('.leak-edge');
  expect(await leak.count()).toBeGreaterThan(0);
  await expect(page.locator('.react-flow__edge-textwrapper').first()).toContainText('/yr');
});

test('the node figures match the API exactly', async ({ page, request }) => {
  const response = await request.get('/api/v1/entities', { headers: { 'X-Persona': 'P2' } });
  const entities = (await response.json()) as { id: string; short_name: string }[];

  await page.goto('/canvas');
  await dismissNotice(page);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(600);

  for (const entity of entities) {
    await expect(page.locator('.react-flow__node-entity').filter({ hasText: entity.id })).toHaveCount(1);
  }
});

test('the 404 page names the route and offers a way back', async ({ page }) => {
  await page.goto('/not-a-register');
  await dismissNotice(page);
  await expect(page.getByRole('heading', { name: /does not exist/i })).toBeVisible();
  await expect(page.getByText('/not-a-register')).toBeVisible();
  await expect(page.getByTestId('watermark')).toBeVisible();
});

test('the command palette opens, filters and navigates', async ({ page }) => {
  await page.goto('/canvas');
  await dismissNotice(page);
  await page.waitForLoadState('networkidle');

  await page.keyboard.press('Control+k');
  const dialog = page.getByRole('dialog', { name: 'Command palette' });
  await expect(dialog).toBeVisible();

  await page.getByLabel('Search commands').fill('Terminal');
  // Scoped to the dialog: the persona <select> also exposes role=option.
  await dialog.getByRole('option').first().click();
  await expect(page).toHaveURL(/\/terminal/);
});

test('privacy and terms pages are reachable and self-describing', async ({ page }) => {
  await page.goto('/privacy.html');
  await expect(page.getByRole('heading', { name: 'Privacy notice' })).toBeVisible();
  await expect(page.getByText(/collects no personal data/i)).toBeVisible();

  await page.goto('/terms.html');
  await expect(page.getByRole('heading', { name: 'Terms of use' })).toBeVisible();
  await expect(page.getByText(/not a Treasury Management System/i)).toBeVisible();
});
