/**
 * TEMPLATE — capture the same flows against one build, for a before/after pair.
 *
 * Both sides run this identical script — same viewport, same input, same waits
 * — so any difference in the images is the code and nothing else.
 *
 *   EVIDENCE_EMAIL=... EVIDENCE_PASSWORD=... \
 *     node capture-pair.mjs <baseURL> <outDir> <label>
 *
 * `label` is the filename prefix ("problem" or "solution").
 *
 * MUST live inside a worktree, not a scratch directory: run from anywhere else
 * and node cannot resolve `@playwright/test`. Run with `unset DISPLAY`.
 *
 * Everything above "FLOWS" is reusable as-is once the sign-in selectors match
 * your app. Replace the flows with your own, and keep the two habits that make
 * the images checkable: screenshot at each decisive moment, and `console.log`
 * the same fact read straight from the DOM so the run log corroborates the
 * pixels.
 */
import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

const [baseURL, outDir, label] = process.argv.slice(2);
if (!baseURL || !outDir || !label) {
  console.error('usage: capture-pair.mjs <baseURL> <outDir> <label>');
  process.exit(1);
}

/** Never hardcode these — the file is committed, the credentials are not. */
const { EVIDENCE_EMAIL: EMAIL, EVIDENCE_PASSWORD: PASSWORD } = process.env;
if (!EMAIL || !PASSWORD) {
  console.error('set EVIDENCE_EMAIL and EVIDENCE_PASSWORD to the account to sign in as');
  process.exit(1);
}

const VIEWPORT = { width: 1440, height: 900 };
/** Fixed so both sides type the identical value; the point is the round trip. */
const NEW_VALUE = 'EVIDENCE_001';

const shot = async (page, name) => {
  await page.screenshot({ path: `${outDir}/${label}-${name}.png` });
  console.log(`  saved ${label}-${name}.png`);
};

/** The on-screen error text, printed so the run log corroborates the image.
 *  Add your app's error class alongside [role="alert"] if it does not use one. */
const alerts = (page) =>
  page.evaluate(() =>
    Array.from(document.querySelectorAll('[role="alert"]'))
      .map((el) => el.textContent?.trim())
      .filter(Boolean),
  );

await mkdir(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: VIEWPORT });

console.log(`[${label}] ${baseURL}`);

// ---- sign in ---- (selectors are the common shape; adjust to your app)
await page.goto(`${baseURL}/login`, { timeout: 60_000 });
await page.locator('input[type="email"]').fill(EMAIL);
await page.locator('input[name="password"]').fill(PASSWORD);
await page.locator('button:has-text("Sign In")').click();
await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 60_000 });

// ---- pick a subject: the first row that already carries the field under test ----
await page.goto(`${baseURL}/items`, { timeout: 60_000 });
await page.locator('table tbody tr').first().waitFor({ state: 'visible', timeout: 60_000 });
const subject = await page.evaluate(() => {
  const row = document.querySelector('table tbody tr');
  const cells = row ? Array.from(row.querySelectorAll('td')).map((c) => c.textContent?.trim()) : [];
  return { id: cells[0], reference: cells[1] };
});
console.log(`  subject ${subject.id} currently holds "${subject.reference}"`);

// ============================================================
// FLOWS — replace everything below with your own.
// What follows is a worked example of the commonest shape: a field that is
// edited, saved, and then silently discarded, and a Save that refuses in
// silence.
// ============================================================

// Flow 1 — does an edited value survive a reload?
await page.goto(`${baseURL}/items?item=${subject.id}&mode=edit`, { timeout: 60_000 });
await page.locator('[data-testid="edit-form"]').waitFor({ state: 'visible', timeout: 60_000 });

await page.locator('role=textbox[name="Reference"]').fill(NEW_VALUE);
await page.waitForTimeout(600);
await shot(page, '1-typed');

await page.locator('[role="dialog"] button:has-text("Save Changes")').click();
await page.waitForTimeout(1000);
await page.locator('role=button[name=/^Confirm/]').click();
await page.waitForTimeout(1200);
await shot(page, '2-saved');

// Reload and look the record up by its own id, so the row is on screen either
// way and the Reference column is the only thing that differs.
await page.goto(`${baseURL}/items?search=${subject.id}`, { timeout: 60_000 });
await page.locator('table tbody tr').first().waitFor({ state: 'visible', timeout: 60_000 });
await page.waitForTimeout(1500);
const readBack = await page.evaluate(() => {
  const cells = Array.from(document.querySelectorAll('table tbody tr')[0].querySelectorAll('td'));
  return cells.map((c) => c.textContent?.trim()).slice(0, 3);
});
console.log(`  row after reload reads: ${JSON.stringify(readBack)}`);
console.log(`  persisted: ${readBack.includes(NEW_VALUE)}`);
await shot(page, '3-after-reload');

// ============================================================
// Flow 2 — Save with a change the backend will reject
// ============================================================
await page.goto(`${baseURL}/items?item=${subject.id}&mode=edit`, { timeout: 60_000 });
await page.locator('[data-testid="edit-form"]').waitFor({ state: 'visible', timeout: 60_000 });

await page.locator('[data-testid="edit-form"] select').selectOption({ index: 1 });
await page.waitForTimeout(1200);

await page.locator('[role="dialog"] button:has-text("Save Changes")').click();
await page.waitForTimeout(1500);
console.log(`  on-screen alerts after Save: ${JSON.stringify(await alerts(page))}`);
await shot(page, '4-rejected-save');

await browser.close();
console.log(`[${label}] done`);
