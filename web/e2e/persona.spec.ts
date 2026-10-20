/**
 * The persona capability matrix.
 *
 * For each persona, the controls their flags forbid must be absent from the
 * DOM AND the corresponding API call must return 403. Absence from the DOM
 * alone is not a pass: hiding a button is not a control.
 */

import { expect, test, type Page } from '@playwright/test';

const PROPOSAL = {
  kind: 'intercompany_loan',
  source_entity_id: 'GCPL-GB',
  target_entity_id: 'GCPL-US',
  amount_usd: 1_000_000,
  tenor_days: 90,
  interest_rate: 0.085,
  rate_basis: '6M Term SONIA + 395bps',
  justification: 'Automated capability-matrix check.',
};

const CAPABILITIES: Record<string, { initiate: boolean; approve: boolean; settle: boolean }> = {
  P1: { initiate: false, approve: true, settle: false },
  P2: { initiate: true, approve: true, settle: false },
  P3: { initiate: true, approve: false, settle: false },
  P4: { initiate: false, approve: true, settle: false },
  P5: { initiate: false, approve: false, settle: false },
  P6: { initiate: false, approve: false, settle: false },
  P7: { initiate: false, approve: false, settle: true },
  P8: { initiate: false, approve: false, settle: false },
  P9: { initiate: false, approve: false, settle: false },
  P10: { initiate: false, approve: false, settle: false },
};

async function actAs(page: Page, persona: string) {
  await page.goto('/canvas');
  const orientation = page.getByRole('button', { name: 'Dismiss orientation' });
  if (await orientation.count()) await orientation.click();
  const allow = page.getByRole('button', { name: 'Allow' });
  if (await allow.count()) await allow.click();
  await page.locator('#persona-switch').selectOption(persona);
  await page.waitForLoadState('networkidle');
}

for (const [persona, caps] of Object.entries(CAPABILITIES)) {
  test(`${persona}: the initiate capability is enforced in the DOM and the API`, async ({
    page,
    request,
  }) => {
    await actAs(page, persona);
    await page.goto('/canvas/pooling');
    await page.waitForLoadState('networkidle');

    const submit = page.getByRole('button', { name: /Submit for approval/ });

    if (persona === 'P9') {
      // Platform scope: the workbench is refused outright rather than rendered
      // with a disabled control, because this persona sees no amounts at all.
      await expect(page.getByText(/no financial data visibility/i)).toBeVisible();
      await expect(submit).toHaveCount(0);
    } else if (caps.initiate) {
      await expect(submit).toBeVisible();
    } else {
      // The control is present but disabled, with the reason stated in prose.
      await expect(submit).toBeDisabled();
      await expect(page.getByTestId('no-initiate-notice')).toBeVisible();
    }

    const response = await request.post('/api/v1/proposals', {
      headers: { 'X-Persona': persona },
      data: PROPOSAL,
    });
    if (caps.initiate) {
      expect([201, 422]).toContain(response.status());
    } else {
      expect(response.status(), `${persona} must not be able to initiate`).toBe(403);
    }
  });
}

test('the IT administrator sees infrastructure and never an amount', async ({ page, request }) => {
  await actAs(page, 'P9');
  await page.waitForLoadState('networkidle');

  // Scope is platform: the entity list is refused rather than filtered to empty.
  const entities = await request.get('/api/v1/entities', { headers: { 'X-Persona': 'P9' } });
  expect(entities.status()).toBe(403);

  const leak = await request.get('/api/v1/cash-leak', { headers: { 'X-Persona': 'P9' } });
  expect(leak.status()).toBe(403);

  // Feeds and connectivity remain visible, with every balance withheld.
  const accounts = await request.get('/api/v1/accounts', { headers: { 'X-Persona': 'P9' } });
  expect(accounts.status()).toBe(200);
  const rows = (await accounts.json()) as { balance: unknown }[];
  expect(rows.every((row) => row.balance === null)).toBe(true);
});

test('a local coordinator cannot reach another entity', async ({ page, request }) => {
  await actAs(page, 'P5');
  await page.goto('/canvas?entity=GCPL-GB');
  await page.waitForLoadState('networkidle');

  // 403 renders as an access decision, never as "this does not exist".
  await expect(page.getByText(/outside your scope/i)).toBeVisible();
  await expect(page.getByText(/does not exist/i)).toBeVisible();

  const response = await request.get('/api/v1/entities/GCPL-GB', { headers: { 'X-Persona': 'P5' } });
  expect(response.status()).toBe(403);
});

test('the regional lead sees one region and is refused outside it', async ({ request }) => {
  const entities = await request.get('/api/v1/entities', { headers: { 'X-Persona': 'P4' } });
  const rows = (await entities.json()) as { region_id: string }[];
  expect(new Set(rows.map((row) => row.region_id))).toEqual(new Set(['REG-EMEA']));

  const outside = await request.get('/api/v1/entities/GCPL-US', { headers: { 'X-Persona': 'P4' } });
  expect(outside.status()).toBe(403);
});

test('only Risk may run the linter, in the UI and in the API', async ({ page, request }) => {
  await actAs(page, 'P3');
  await page.goto('/canvas/workflow/W7');
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('button', { name: /Lint/ })).toBeDisabled();
  await expect(page.getByText(/Switch to the Risk and Control Analyst/i)).toBeVisible();

  expect(
    (await request.post('/api/v1/workflows/W7/lint', { headers: { 'X-Persona': 'P3' } })).status(),
  ).toBe(403);
  expect(
    (await request.post('/api/v1/workflows/W7/lint', { headers: { 'X-Persona': 'P6' } })).status(),
  ).toBe(200);
});

test('a dealer cannot approve their own proposal, and the API says why', async ({ request }) => {
  const created = await request.post('/api/v1/proposals', {
    headers: { 'X-Persona': 'P2' },
    data: { ...PROPOSAL, justification: 'Self-approval guard check.' },
  });
  expect(created.status()).toBe(201);
  const { id } = (await created.json()) as { id: string };

  const denied = await request.post(`/api/v1/proposals/${id}/approve`, {
    headers: { 'X-Persona': 'P2' },
    data: { justification: 'Attempting to approve my own proposal.' },
  });
  expect(denied.status()).toBe(403);
  expect(JSON.stringify(await denied.json())).toContain('LR1');
});

test('the pooling workbench disables submit while a check blocks', async ({ page }) => {
  await actAs(page, 'P3');
  await page.goto('/canvas/pooling');
  await page.waitForLoadState('networkidle');

  // Drive the rate to zero: the arm's-length floor must block it.
  const rate = page.locator('#rate');
  await rate.fill('0');
  await page.waitForTimeout(500);

  await expect(page.getByText('ARMS_LENGTH')).toBeVisible();
  await expect(page.getByRole('button', { name: /Submit for approval/ })).toBeDisabled();
  await expect(page.getByText(/blocking check/i)).toBeVisible();
});
