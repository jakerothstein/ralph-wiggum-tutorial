import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

/**
 * End-to-end happy path for the Research Paper Comprehension Tutor.
 *
 * Runs against the full stack (Flask + Vite) with the deterministic fake AI
 * client (USE_FAKE_AI=1, exported by the Playwright webServer), so the flow is
 * hermetic — no GitHub Models token or network is needed. We exercise the three
 * user-facing stages end to end: upload → analysis → a tutor turn with a visible
 * comprehension score.
 */
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_PDF = path.join(__dirname, 'fixtures', 'sample-paper.pdf');

test.describe('Research Paper Comprehension Tutor', () => {
  test('renders the upload home page (legacy game is gone)', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Comprehension Tutor/i);
    await expect(page.locator('[data-island="upload"]')).toBeVisible();
    await expect(page.locator('[data-island="game"]')).toHaveCount(0);
    await expect(page.locator('canvas')).toHaveCount(0);
  });

  test('upload → analysis → tutor turn happy path', async ({ page }) => {
    await page.goto('/');

    // Upload the fixture PDF via the hidden file input the island renders.
    await page.locator('input[type="file"]').setInputFiles(FIXTURE_PDF);

    // The upload island redirects to the paper workspace on success.
    await page.waitForURL(/\/papers\/\d+/, { timeout: 30_000 });

    // The original PDF is previewed inline next to the chat.
    await expect(page.locator('iframe[title^="PDF preview"]')).toBeVisible();

    // The tutor speaks first: a guiding question is seeded into the chat.
    const messageList = page.getByTestId('message-list');
    await expect(messageList.locator('.prose').first()).toBeVisible({
      timeout: 15_000,
    });

    // Analysis is hidden by default behind a toggle; revealing it renders the
    // structured analysis island.
    const analysis = page.locator('[data-island="analysis"]');
    await expect(analysis).not.toBeVisible();
    await page.getByText('Show paper analysis').click();
    await expect(analysis).toBeVisible();
    await expect(analysis.getByText('Paper Analysis')).toBeVisible();
    await expect(analysis.getByText('Summary')).toBeVisible();

    // Chat island: send one message and assert a tutor reply + score meter.
    const input = page.getByLabel('Message the tutor');
    await expect(input).toBeEnabled({ timeout: 15_000 });
    await input.fill('I think the paper is about attention-based models.');
    await page.getByRole('button', { name: 'Send' }).click();

    await expect(
      messageList.getByText('I think the paper is about attention-based models.'),
    ).toBeVisible();
    // The fake tutor echoes the user text; any assistant bubble + score proves the loop.
    await expect(page.getByRole('progressbar', { name: 'Comprehension score' })).toBeVisible();
    await expect(page.getByTestId('score-value')).toContainText('/100');

    // Capture evidence of the working workspace.
    await page.screenshot({ path: 'e2e/paper-workspace.png', fullPage: true });
  });
});
