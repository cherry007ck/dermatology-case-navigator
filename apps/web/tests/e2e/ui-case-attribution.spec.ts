import { expect, type Page, test } from "@playwright/test";

// S4 presentation checks for the case card, attribution module and source drawer.
// Runs against the labelled fixture mock (synthetic collection only). The published
// attribution path cannot be exercised until Luffy adds a published example and the
// generated `CaseCard.attribution` field; nothing here fakes article metadata.
// Set UI_SCREENSHOT_DIR to save review screenshots (outside the repo).

const LIVE = process.env.E2E_API_MODE === "live";
const SHOTS = process.env.UI_SCREENSHOT_DIR;
const MAIN = [
  "My hands have been itchy for weeks. I tried a cream, but it didn't help.",
  "I don't remember the name. I used it for a few days.",
  "I started using a new hand soap before this began.",
];

async function openDoctorBrief(page: Page) {
  await page.goto("/intake");
  await page.getByLabel("Demo access code").fill(LIVE ? (process.env.E2E_DEMO_CODE ?? "local-demo") : "mock-demo");
  await page.getByRole("button", { name: "Load collections" }).click();
  await page.getByRole("button", { name: "Start intake" }).click();
  await expect(page.getByRole("heading", { name: "Patient intake" })).toBeVisible();
  for (const line of MAIN) {
    await page.getByLabel(/In your own words|Your answer/).fill(line);
    await page.getByRole("button", { name: /^Send/ }).click();
  }
  await page.getByRole("button", { name: "Confirm and open doctor brief" }).click();
  await expect(page.getByRole("heading", { name: "Doctor workspace" })).toBeVisible();
}

async function shot(page: Page, name: string, project: string, fullPage = true) {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${project}-${name}.png`, fullPage });
}

test.beforeEach(() => {
  test.skip(LIVE, "presentation checks use the shared synthetic fixtures");
});

test("case card shows comparison, case record and honest synthetic source labels", async ({ page }, info) => {
  await openDoctorBrief(page);
  const card = page.getByTestId("case-card").first();
  await expect(card.getByRole("heading", { level: 3 })).toContainText("Fictional demonstration case");

  for (const heading of ["Comparison with this intake", "Shared features", "Important differences", "Fictional case record", "Fictional recorded actions", "Fictional recorded outcomes"]) {
    await expect(card.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
  await expect(card).toContainText("Shared reported site: hands.");

  const labels = card.getByTestId("case-review-labels");
  await expect(labels).toContainText("Synthetic · fictional");
  await expect(labels).toContainText("Fixture consistency check only");
  await expect(labels).toContainText("Not clinically reviewed");
  await expect(labels).not.toContainText("Developer source-reviewed");

  // Synthetic: fictional label, no article link, no citation and no invented identifiers.
  const source = card.getByTestId("case-attribution");
  await expect(source).toContainText("Fictional demonstration case — not published evidence");
  await expect(card.getByRole("link")).toHaveCount(0);
  await expect(source).not.toContainText(/PMID|PMCID|DOI|Licence/);

  // No scores, percentages or match strength anywhere in the cases panel.
  const casesText = await page.getByTestId("cases-panel").innerText();
  expect(casesText).not.toMatch(/\d+\s*%|score|probability|case match/i);

  await shot(page, "doctor-workspace", info.project.name);
  await card.scrollIntoViewIfNeeded();
  if (SHOTS) await card.screenshot({ path: `${SHOTS}/${info.project.name}-case-card.png` });
});

test("source drawer shows the exact quote, locator and passage hash, then returns focus", async ({ page }, info) => {
  await openDoctorBrief(page);
  const chip = page.getByTestId("case-card").first().getByRole("button", { name: /Case passage quote/ }).first();
  const quote = ((await chip.textContent()) ?? "").replace(/^Case passage quote: /, "").replace(/^“|”$/g, "");
  expect(quote.length).toBeGreaterThan(0);
  await chip.focus();
  await page.keyboard.press("Enter");

  const drawer = page.getByTestId("source-drawer");
  await expect(drawer.getByRole("heading", { name: "Fictional case passage" })).toBeVisible();
  await expect(drawer.getByTestId("drawer-quote")).toHaveText(`“${quote}”`);
  await expect(drawer.locator("mark")).toHaveText(quote);
  await expect(drawer).toContainText("team-authored fictional fixture/");
  await expect(drawer).toContainText(/SHA-256 [0-9a-f]{16}…/);
  await expect(drawer).toContainText("Not clinically reviewed.");
  await expect(drawer.getByRole("link")).toHaveCount(0);
  await shot(page, "source-drawer-case", info.project.name, false);

  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(chip).toBeFocused();

  const patientChip = page.getByTestId("brief-panel").getByRole("button", { name: /Patient quote/ }).first();
  await patientChip.click();
  await expect(drawer.getByRole("heading", { name: "Patient statement" })).toBeVisible();
  await expect(drawer.getByTestId("drawer-quote")).toBeVisible();
  await shot(page, "source-drawer-patient", info.project.name, false);
});

test("390px: case card and clinician assessment fit the viewport", async ({ page }, info) => {
  test.skip(info.project.name !== "phone-390", "layout check runs on the 390px project");
  await openDoctorBrief(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  for (const id of ["case-card", "clinician-notes", "brief-panel", "comparison-history"]) {
    const box = await page.getByTestId(id).first().boundingBox();
    expect(box, id).not.toBeNull();
    expect(box!.x, id).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width, id).toBeLessThanOrEqual(390);
  }
  await expect(page.getByLabel("Assessment note")).toBeVisible();
});
