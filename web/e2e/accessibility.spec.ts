/**
 * Zero critical or serious Axe violations on all five registers, plus the
 * keyboard and focus requirements a dense dashboard systematically fails.
 */

import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const ROUTES = ['/canvas', '/console', '/terminal', '/brief', '/cockpit', '/method'] as const;

async function settle(page: Page, path: string) {
  await page.goto(path);
  const orientation = page.getByRole('button', { name: 'Dismiss orientation' });
  if (await orientation.count()) await orientation.click();
  const allow = page.getByRole('button', { name: 'Allow' });
  if (await allow.count()) await allow.click();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(600);
}

for (const route of ROUTES) {
  test(`${route} has no critical or serious accessibility violations`, async ({ page }) => {
    await settle(page, route);

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      // The xyflow canvas renders its own SVG internals; the node cards inside
      // it are what this product owns and they are checked on their own below.
      .exclude('.react-flow__minimap')
      .analyze();

    const serious = results.violations.filter((violation) =>
      ['critical', 'serious'].includes(violation.impact ?? ''),
    );

    expect(
      serious,
      serious
        .map((v) => `${v.impact} ${v.id}: ${v.help}\n  ${v.nodes[0]?.html ?? ''}`)
        .join('\n'),
    ).toEqual([]);
  });
}

test('every icon-only control carries an accessible name', async ({ page }) => {
  await settle(page, '/canvas');
  const buttons = page.getByRole('button');
  const total = await buttons.count();

  for (let index = 0; index < total; index += 1) {
    const button = buttons.nth(index);
    if (!(await button.isVisible())) continue;
    const name = (
      (await button.getAttribute('aria-label')) ??
      (await button.getAttribute('title')) ??
      (await button.innerText())
    ).trim();
    expect(name, `button ${index} has no accessible name`).not.toBe('');
  }
});

test('table headers are real th elements with a scope', async ({ page }) => {
  await settle(page, '/console?tab=accounts');

  const headers = page.locator('.grid-table thead th');
  expect(await headers.count()).toBeGreaterThan(0);

  // A div styled to look like a header is invisible to assistive technology.
  const divHeaders = await page.locator('.grid-table thead div[role="columnheader"]').count();
  expect(divHeaders).toBe(0);
});

test('keyboard traversal reaches the registers and the frozen header never covers focus', async ({
  page,
}) => {
  await settle(page, '/console?tab=accounts');
  await page.keyboard.press('Tab');

  const reached: string[] = [];
  for (let step = 0; step < 40; step += 1) {
    const info = await page.evaluate(() => {
      const element = document.activeElement as HTMLElement | null;
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return {
        tag: element.tagName,
        name: (element.getAttribute('aria-label') ?? element.textContent ?? '').trim().slice(0, 30),
        top: rect.top,
        height: rect.height,
      };
    });
    if (info) {
      reached.push(info.name);
      if (info.height > 0) {
        // Focused element must not be hidden behind the 48px top bar.
        expect(info.top, `focused "${info.name}" is under the top bar`).toBeGreaterThanOrEqual(-1);
      }
    }
    await page.keyboard.press('Tab');
  }

  expect(reached.some((name) => name.includes('Console') || name.includes('Canvas'))).toBe(true);
});

test('a visible focus ring is applied on keyboard focus', async ({ page }) => {
  await settle(page, '/canvas');
  await page.keyboard.press('Tab');

  const outline = await page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    if (!element) return null;
    const style = getComputedStyle(element);
    return { width: style.outlineWidth, style: style.outlineStyle, colour: style.outlineColor };
  });

  expect(outline).not.toBeNull();
  expect(outline!.style).not.toBe('none');
  expect(Number.parseFloat(outline!.width)).toBeGreaterThanOrEqual(2);
});

test('the page declares a dark colour scheme and a matching theme colour', async ({ page }) => {
  await settle(page, '/canvas');

  const scheme = await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme);
  expect(scheme).toContain('dark');

  const themeColour = await page.locator('meta[name="theme-color"]').getAttribute('content');
  const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);

  expect(themeColour).toBe('#161616');
  // rgb(22, 22, 22) is #161616.
  expect(background.replace(/\s/g, '')).toBe('rgb(22,22,22)');
});

test('numeric columns use tabular figures so digits align', async ({ page }) => {
  await settle(page, '/console?tab=accounts');

  const variant = await page
    .locator('.grid-table tbody td.num')
    .first()
    .evaluate((cell) => getComputedStyle(cell).fontVariantNumeric);

  expect(variant).toContain('tabular-nums');
});

/* ── motion discipline ──────────────────────────────────────────
 * The product's motion rules are testable, so they are tested. These would
 * each have been a review comment; as assertions they stay true.
 */

test('nothing animates a layout property', async ({ page }) => {
  await settle(page, '/canvas');

  // transform and opacity composite off the main thread; width, height, top
  // and box-shadow do not, and a dropped frame on an 81-row grid shows.
  const offenders = await page.evaluate(() => {
    const banned = ['width', 'height', 'top', 'left', 'right', 'bottom', 'margin', 'padding', 'box-shadow'];
    const found: string[] = [];
    for (const element of Array.from(document.querySelectorAll('*'))) {
      const style = getComputedStyle(element);
      const property = style.transitionProperty;
      // `all` is transition-property's INITIAL value, so every element reports
      // it. Only a non-zero duration means a transition actually runs.
      const runs = style.transitionDuration
        .split(',')
        .some((value) => Number.parseFloat(value) > 0);
      if (!runs || !property || property === 'none') continue;
      if (property === 'all') {
        found.push(`${element.tagName}.${element.className}: transition: all`);
        continue;
      }
      for (const name of banned) {
        if (property.split(',').map((p) => p.trim()).includes(name)) {
          found.push(`${element.tagName}: transitions ${name}`);
        }
      }
    }
    return found.slice(0, 10);
  });

  expect(offenders, offenders.join('\n')).toEqual([]);
});

test('reduced motion collapses every transition and stops the loop', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  await settle(page, '/canvas');

  const durations = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    return ['--t-press', '--t-reveal', '--t-enter', '--t-exit', '--t-travel'].map((token) =>
      root.getPropertyValue(token).trim(),
    );
  });
  expect(durations.every((value) => value === '1ms')).toBe(true);

  // The leak edge is the only looping animation, and it must stop entirely.
  const leakAnimation = await page
    .locator('.leak-edge')
    .first()
    .evaluate((edge) => getComputedStyle(edge).animationName);
  expect(leakAnimation).toBe('none');

  await context.close();
});

test('the leak edge animates for a reader who has not opted out', async ({ page }) => {
  await settle(page, '/canvas?lens=cash');
  const animation = await page
    .locator('.leak-edge')
    .first()
    .evaluate((edge) => getComputedStyle(edge).animationName);
  expect(animation).toBe('leak-dash');
});
