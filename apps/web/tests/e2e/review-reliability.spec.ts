import { expect, type Page, test } from "@playwright/test";

// S3 review, correction, failure-state and clinician-note flows.
// Mock mode: skip and correction use the labelled MOCK-ONLY transport behaviour (the S0
// backend stub returns STUB_NOT_IMPLEMENTED), and failures are injected with the mock's
// "dcn.mock-fail" hook. Those tests are skipped in live mode; they are UI checks, not
// proof of the backend correction/skip pipeline.

const LIVE = process.env.E2E_API_MODE === "live";
const MAIN = [
  "My hands have been itchy for weeks. I tried a cream, but it didn't help.",
  "I don't remember the name. I used it for a few days.",
  "I started using a new hand soap before this began.",
];

async function startEncounter(page: Page) {
  await page.goto("/intake");
  await page.getByLabel("Demo access code").fill(LIVE ? (process.env.E2E_DEMO_CODE ?? "local-demo") : "mock-demo");
  await page.getByRole("button", { name: "Load collections" }).click();
  await page.getByRole("button", { name: "Start intake" }).click();
  await expect(page.getByRole("heading", { name: "Patient intake" })).toBeVisible();
  await expect(page.getByTestId("story-panel")).toBeVisible(); // snapshot loaded before typing
}

async function say(page: Page, text: string) {
  const box = page.getByLabel(/In your own words|Your answer/);
  await box.fill(text);
  await expect(box).toHaveValue(text);
  await page.getByRole("button", { name: /^Send/ }).click();
}

async function reachReview(page: Page) {
  await startEncounter(page);
  for (const line of MAIN) await say(page, line);
  await expect(page.getByTestId("review-panel")).toBeVisible();
}

async function confirmToDoctor(page: Page) {
  await page.getByRole("button", { name: "Confirm and open doctor brief" }).click();
  await expect(page.getByRole("heading", { name: "Doctor workspace" })).toBeVisible();
}

const mockOnly = () => test.skip(LIVE, "uses MOCK-ONLY skip/correction or failure injection; backend not implemented yet");

test("review step takes focus, then confirms the reviewed revision", async ({ page }) => {
  await reachReview(page);
  await expect(page.getByRole("heading", { name: "Review your statement" })).toBeFocused();
  await expect(page.getByTestId("review-panel")).toContainText("at revision 3");
  await expect(page.getByTestId("voice-paused")).toHaveCount(0); // voice not configured in tests
  await confirmToDoctor(page);
  await expect(page.getByText("Patient confirmed revision 3")).toBeVisible();
});

test("late words during review block the stale confirmation (A11)", async ({ page }) => {
  mockOnly();
  await reachReview(page);
  // Simulate a late finalized transcript landing server-side after the review screen was shown.
  await page.evaluate(() => {
    const store = JSON.parse(sessionStorage.getItem("dcn.mock-sessions")!);
    const [id] = Object.keys(store);
    const snap = store[id];
    snap.turns.push({
      turn_id: "voice-late-patient-9", role: "patient", origin: "voice_transcript", text: "Also my wrists.",
      reply_to_question_id: null, supersedes_turn_id: null, sequence: snap.turns.length + 1, created_at: "2026-11-13T12:09:00Z",
    });
    snap.revision += 1;
    snap.state = "intake";
    sessionStorage.setItem("dcn.mock-sessions", JSON.stringify(store));
  });
  await page.getByRole("button", { name: "Confirm and open doctor brief" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Your statement changed while you were reviewing" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Doctor workspace" })).toHaveCount(0);
  await expect(page.getByTestId("story-turns").getByText("Also my wrists.")).toBeVisible();
});

test("correction after confirmation keeps the original and invalidates confirmation (A09)", async ({ page }) => {
  mockOnly();
  await reachReview(page);
  await confirmToDoctor(page);
  const doctorUrl = page.url();
  await page.goto(doctorUrl.replace("/doctor/", "/intake/"));

  // Keyboard only: open the correction, cancel with Escape (focus returns), reopen and save.
  const correctButton = page.getByRole("button", { name: /^Correct: My hands have been itchy/ });
  await correctButton.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Correct what you said")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(correctButton).toBeFocused();
  await page.keyboard.press("Enter");
  await page.getByLabel("Correct what you said").fill("My hands and wrists have been itchy for weeks. I tried a cream, but it didn't help.");
  await page.getByRole("button", { name: "Save correction" }).click();

  const first = page.getByTestId("statement").first();
  await expect(first).toContainText("My hands and wrists have been itchy");
  await expect(first).toContainText("Your correction");
  await first.getByText(/Earlier version/).click();
  await expect(first.getByTestId("replaced-history")).toContainText("My hands have been itchy for weeks.");
  await expect(page.getByTestId("confirmation-invalidated")).toContainText("Your confirmation of revision 3 no longer applies");
  await expect(page.getByText("Revision 4")).toBeVisible();
  // The mock cannot recompute: the UI says so instead of reusing the old brief.
  await expect(page.getByRole("alert").filter({ hasText: "processing failed" })).toBeVisible();

  await page.goto(doctorUrl);
  await expect(page.getByTestId("doctor-awaiting")).toContainText("changed their statement after confirming revision 3");
  await expect(page.getByTestId("brief-panel")).toHaveCount(0);
});

test("skip is recorded as skipped, not as a negative answer (A05)", async ({ page }) => {
  mockOnly();
  await startEncounter(page);
  await say(page, MAIN[0]);
  await expect(page.getByTestId("current-question")).toBeVisible();
  await page.getByRole("button", { name: "Skip" }).click();
  await expect(page.getByText("recorded as skipped, not as a “no”")).toBeVisible();
  await expect(page.getByTestId("question-list")).toContainText("Skipped");
  await expect(page.getByTestId("mode-banner")).toContainText("Mock API");
});

test("storage failure keeps saved words and recovers with Retry (A19)", async ({ page }) => {
  mockOnly();
  await startEncounter(page);
  await page.evaluate(() =>
    sessionStorage.setItem("dcn.mock-fail", JSON.stringify({
      op: "advance", status: 503, code: "STORAGE_UNAVAILABLE", message: "Storage is temporarily unavailable.", retryable: true,
    })),
  );
  await say(page, MAIN[0]);
  const alert = page.getByRole("alert").filter({ hasText: "processing failed" });
  await expect(alert).toContainText("Storage is temporarily unavailable. Anything already shown as saved is kept.");
  await expect(page.getByTestId("story-turns").getByRole("listitem")).toHaveCount(1);
  await alert.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("current-question")).toHaveText("Do you know the cream's name and how long you used it?");
});

test("offline state disables sending and recovers when back online", async ({ page, context }) => {
  await startEncounter(page);
  await page.getByLabel("In your own words").fill(MAIN[0]);
  await context.setOffline(true);
  await expect(page.getByText("You are offline.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
  await expect(page.getByLabel("In your own words")).toHaveValue(MAIN[0]); // typed text kept
  await context.setOffline(false);
  await expect(page.getByRole("button", { name: "Send" })).toBeEnabled();
});

test("clinician note is saved separately and never changes patient content (A17)", async ({ page }) => {
  await reachReview(page);
  await confirmToDoctor(page);
  const briefBefore = await page.getByTestId("brief-panel").innerText();
  const notes = page.getByTestId("clinician-notes");
  await notes.getByLabel("Author label").fill("Demo clinician");
  await notes.getByLabel("Assessment note").fill("Fictional note: discussed history; separate from patient words.");
  await expect(notes.getByText("Unsaved note")).toBeVisible();
  await notes.getByRole("button", { name: "Save note" }).click();
  await expect(notes.getByText("Note saved")).toBeVisible();
  await expect(notes.getByTestId("saved-notes")).toContainText("Demo clinician · patient revision 3");
  expect(await page.getByTestId("brief-panel").innerText()).toBe(briefBefore);

  await page.reload(); // persisted, not just local state
  await expect(page.getByTestId("saved-notes")).toContainText("Fictional note: discussed history");
  const intake = page.url().replace("/doctor/", "/intake/");
  await page.goto(intake);
  await expect(page.getByText("Fictional note: discussed history")).toHaveCount(0); // never shown to the patient
});

test("phone width has no horizontal overflow on intake, review and doctor views (A18)", async ({ page }, info) => {
  test.skip(info.project.name !== "phone-390", "layout check runs on the 390px project");
  const noOverflow = async () =>
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  await startEncounter(page);
  await noOverflow();
  for (const line of MAIN) await say(page, line);
  await expect(page.getByTestId("review-panel")).toBeVisible();
  await noOverflow();
  await confirmToDoctor(page);
  await noOverflow();
  await page.getByTestId("brief-panel").getByRole("button", { name: /Patient quote/ }).first().click();
  await expect(page.getByTestId("source-drawer")).toBeVisible();
  const box = await page.getByTestId("source-drawer").boundingBox();
  expect(box && box.width).toBeGreaterThanOrEqual(380); // drawer becomes full width on phones
});
