import { expect, type Page, test } from "@playwright/test";

const MAIN = [
  "My hands have been itchy for weeks. I tried a cream, but it didn't help.",
  "I don't remember the name. I used it for a few days.",
  "I started using a new hand soap before this began.",
];
const NO_MATCH = "My scalp feels uncomfortable. I don't know when it began.";

const LIVE = process.env.E2E_API_MODE === "live";

async function startEncounter(page: Page) {
  await page.goto("/intake");
  await expect(page.getByText(LIVE ? "Live API" : "Mock API — shared fixture responses, no backend")).toBeVisible();
  await page.getByLabel("Demo access code").fill(LIVE ? (process.env.E2E_DEMO_CODE ?? "local-demo") : "mock-demo");
  await page.getByRole("button", { name: "Load collections" }).click();
  await expect(page.getByText("Synthetic — fictional demonstration cases")).toBeVisible();
  await page.getByRole("button", { name: "Start intake" }).click();
  await expect(page.getByRole("heading", { name: "Patient intake" })).toBeVisible();
  // The encounter snapshot must be loaded (hydrated) before typing, or the first keystrokes can be lost.
  await expect(page.getByTestId("story-panel")).toBeVisible();
}

async function say(page: Page, text: string) {
  const box = page.getByRole("textbox", { name: /In your own words|Your answer/ });
  await box.fill(text);
  await expect(box).toHaveValue(text);
  await page.getByRole("button", { name: /^Send/ }).click();
}

test("main typed story reaches a confirmed doctor brief with fictional cards", async ({ page }) => {
  await startEncounter(page);
  const banner = page.getByTestId("mode-banner");
  if (LIVE) {
    // Live mode reports whatever the API actually runs (e.g. Exasol + Meta), never the mock labels.
    await expect(banner.getByText(/Stored in Exasol|Development storage — not Exasol/)).toBeVisible();
    await expect(banner.getByText(/Meta model extraction|Demo extraction/)).toBeVisible();
  } else {
    await expect(banner.getByText("Development storage — not Exasol")).toBeVisible();
    await expect(banner.getByText("Demo extraction")).toBeVisible();
  }

  await say(page, MAIN[0]);
  await expect(page.getByTestId("current-question")).toHaveText("Do you know the cream's name and how long you used it?");
  await say(page, MAIN[1]);
  await expect(page.getByTestId("current-question")).toContainText("change in products, gloves, or activities");
  await say(page, MAIN[2]);

  // The patient pane never shows case content.
  await expect(page.getByTestId("review-panel")).toBeVisible();
  // getByRole skips routes kept hidden by Cache Components' <Activity>.
  const patientText = await page.getByRole("main").innerText();
  for (const caseContent of ["SYN-", "not published evidence", "hand symptoms and a new product", "arranged a review"]) {
    expect(patientText).not.toContain(caseContent);
  }
  await expect(page.getByTestId("story-turns").getByRole("listitem")).toHaveCount(3);

  await page.getByRole("button", { name: "Confirm and open doctor brief" }).click();
  await expect(page.getByRole("heading", { name: "Doctor workspace" })).toBeVisible();
  await expect(page.getByText("Patient confirmed revision 3")).toBeVisible();
  await expect(page.getByTestId("brief-panel")).toContainText("Patient reports itching on the hands.");
  const cards = page.getByTestId("case-card");
  await expect(cards).toHaveCount(1);
  await expect(cards.first()).toContainText("Fictional demonstration case — not published evidence");
  await expect(cards.first()).toContainText("Outcome not reported in the reviewed passages.");
  await expect(page.getByTestId("changes-panel")).toContainText("removed");

  // Before/after comes from the stored search versions: the new-soap answer removes case B.
  const history = page.getByTestId("comparison-history");
  await expect(history.getByLabel("Comparison step")).toHaveValue("2");
  await expect(history).toContainText("New patient details at this step");
  await expect(history).toContainText("exposure: new product");
  const removed = history.getByTestId("case-change").filter({ hasText: "removed" });
  await expect(removed).toContainText("hand symptoms without a new product");
  await expect(removed).toContainText("rank 2 → —");
  await expect(removed.getByRole("button", { name: /Case passage quote: “no new products”/ })).toBeVisible();
  // The earlier step (cream answer) did not change the order.
  await history.getByLabel("Comparison step").selectOption("1");
  await expect(history).toContainText("The order did not change at this step.");
  await expect(history).toContainText("Earlier step — not the current revision");
});

test("no-match story still yields a useful brief and an honest explanation", async ({ page }) => {
  await startEncounter(page);
  await say(page, NO_MATCH);
  await page.getByRole("button", { name: "Confirm and open doctor brief" }).click();
  // Mock replays the contract example wording; the live pipeline renders its own template.
  await expect(page.getByTestId("brief-panel")).toContainText(
    LIVE ? "Patient reports discomfort on the scalp." : "Patient reports scalp discomfort.",
  );
  await expect(page.getByTestId("no-match")).toContainText("same symptom at the same body site");
  await expect(page.getByTestId("case-card")).toHaveCount(0);
});

test("mock: wording outside the shared fixtures is an honest processing error", async ({ page }) => {
  test.skip(LIVE, "the labelled fixture mock cannot extract; the live API computes an honest brief instead");
  await startEncounter(page);
  await say(page, "Fictional text the fixture mock does not know.");
  await expect(page.getByRole("alert").filter({ hasText: "Your words were saved, but processing failed" })).toBeVisible();
  await expect(page.getByTestId("story-turns").getByRole("listitem")).toHaveCount(1);
});

test("live: unfamiliar wording without symptom or site gives an honest insufficient-information brief", async ({ page }) => {
  test.skip(!LIVE, "needs the live extraction pipeline");
  await startEncounter(page);
  await say(page, "I'd like to talk about something else entirely today, if that's okay.");
  await expect(page.getByRole("alert").filter({ hasText: "processing failed" })).toHaveCount(0);
  // One neutral checklist question for the missing detail, never a guess.
  await expect(page.getByTestId("current-question")).toHaveText("Where on your body is it?");
  await page.getByRole("button", { name: "I don't know" }).click();
  await page.getByRole("button", { name: "Confirm and open doctor brief" }).click();
  await expect(page.getByRole("heading", { name: "Doctor workspace" })).toBeVisible();
  await expect(page.getByTestId("no-match")).toContainText("Not enough shared, explicitly reported details");
  await expect(page.getByTestId("case-card")).toHaveCount(0);
  await expect(page.getByTestId("brief-panel")).toContainText("Symptom not provided.");
});

test("doctor route without this tab's token shows no data", async ({ page }) => {
  await page.goto("/doctor/SOMEONE-ELSE");
  await expect(page.getByText("This tab has no access to that encounter.")).toBeVisible();
});
