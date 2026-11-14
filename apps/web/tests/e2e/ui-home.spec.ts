import { expect, type Page, test } from "@playwright/test";

// Homepage layout across widths and browser zoom, plus both entry routes.
// Browser zoom is emulated the way Chrome applies it to layout: at Z% zoom on a
// 1280×720 window, the page sees a CSS viewport of (1280/Z)×(720/Z) at Z device pixels
// per CSS pixel. Set UI_SCREENSHOT_DIR to save review screenshots (outside the repo).

const LIVE = process.env.E2E_API_MODE === "live";
const SHOTS = process.env.UI_SCREENSHOT_DIR;
const CODE = LIVE ? (process.env.E2E_DEMO_CODE ?? "local-demo") : "mock-demo";
const HERO = 'img[src^="/home/stethoscope"]';

type Box = { x: number; y: number; width: number; height: number };
const intersects = (a: Box, b: Box) =>
  a.x < b.x + b.width - 1 && b.x < a.x + a.width - 1 && a.y < b.y + b.height - 1 && b.y < a.y + a.height - 1;

async function box(page: Page, selector: string): Promise<Box> {
  const b = await page.locator(selector).first().boundingBox();
  expect(b, selector).not.toBeNull();
  return b!;
}

async function checkLayout(page: Page, width: number, layout: "stacked" | "two" | "four") {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Every story deserves a closer look." })).toBeVisible();
  await expect(page.locator(HERO)).toBeVisible();
  await page.waitForFunction((sel) => (document.querySelector(sel) as HTMLImageElement | null)?.complete, HERO);

  // No horizontal page scrolling.
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);

  // The homepage ends after the two entries: no legacy setup block.
  for (const gone of ["Demo access code", "Load collections", "Mock API", "Dermatology Case Navigator", "Fictional demonstration only"]) {
    await expect(page.getByTestId("home").getByText(gone)).toHaveCount(0);
  }
  expect(await page.getByTestId("home").locator(":scope > *").count()).toBe(1);

  // No text or label is clipped horizontally.
  const clipped = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-testid="home"] :is(h1,h2,p,a,button)'))
      .filter((el) => el.scrollWidth > el.clientWidth + 1)
      .map((el) => el.textContent),
  );
  expect(clipped).toEqual([]);

  const h1 = await box(page, "h1");
  const art = await box(page, HERO);
  const patient = await box(page, 'section[aria-labelledby="home-patient-title"]');
  const doctor = await box(page, 'section[aria-labelledby="home-doctor-title"]');
  const patientCta = await box(page, '[data-testid="home-patient-cta"]');
  const doctorCta = await box(page, '[data-testid="home-doctor-cta"]');

  // Nothing overlaps; the artwork keeps its proportions and stays fully inside the page width.
  expect(intersects(h1, art), "headline vs artwork").toBe(false);
  expect(intersects(art, patient), "artwork vs patient").toBe(false);
  expect(intersects(art, doctor), "artwork vs doctor").toBe(false);
  expect(intersects(patient, doctor), "patient vs doctor").toBe(false);
  expect(Math.abs(art.width / art.height - 640 / 460)).toBeLessThan(0.02);
  for (const b of [art, patientCta, doctorCta]) {
    expect(b.x).toBeGreaterThanOrEqual(0);
    expect(b.x + b.width).toBeLessThanOrEqual(width + 0.5);
  }

  if (layout === "four") {
    expect(patient.x + patient.width).toBeLessThanOrEqual(art.x + 1);
    expect(doctor.x).toBeGreaterThanOrEqual(art.x + art.width - 1);
    expect(Math.abs(patient.y - doctor.y)).toBeLessThan(2);
  } else if (layout === "two") {
    expect(art.y + art.height).toBeLessThanOrEqual(patient.y + 1);
    expect(Math.abs(patient.y - doctor.y)).toBeLessThan(2);
  } else {
    expect(h1.y + h1.height).toBeLessThanOrEqual(art.y);
    expect(art.y + art.height).toBeLessThanOrEqual(patient.y + 1);
    expect(patient.y + patient.height).toBeLessThanOrEqual(doctor.y + 1);
  }
  return { patientCta, doctorCta };
}

const SIZES = [
  { name: "320", width: 320, height: 640, scale: 1, layout: "stacked" },
  { name: "390", width: 390, height: 844, scale: 1, layout: "stacked" },
  { name: "tablet-768", width: 768, height: 1024, scale: 1, layout: "two" },
  { name: "desktop-1280", width: 1280, height: 720, scale: 1, layout: "four" },
  { name: "desktop-zoom-80", width: 1600, height: 900, scale: 0.8, layout: "four" },
  { name: "desktop-zoom-125", width: 1024, height: 576, scale: 1.25, layout: "two" },
  { name: "desktop-zoom-200", width: 640, height: 360, scale: 2, layout: "stacked" },
] as const;

test.describe("homepage layout matrix", () => {
  for (const size of SIZES) {
    test.describe(size.name, () => {
      test.use({ viewport: { width: size.width, height: size.height }, deviceScaleFactor: size.scale });
      test(`${size.name}: reflows without overlap, clipping or sideways scrolling`, async ({ page }, info) => {
        test.skip(info.project.name !== "desktop", "the matrix sets its own viewports; run once");
        const { patientCta, doctorCta } = await checkLayout(page, size.width, size.layout);
        if (size.name === "desktop-1280") {
          // Both entry buttons are visible without scrolling at the reference desktop size.
          expect(patientCta.y + patientCta.height).toBeLessThanOrEqual(size.height);
          expect(doctorCta.y + doctorCta.height).toBeLessThanOrEqual(size.height);
        }
        if (SHOTS) {
          await page.screenshot({ path: `${SHOTS}/home-${size.name}.png` });
          await page.screenshot({ path: `${SHOTS}/home-${size.name}-full.png`, fullPage: true });
        }
      });
    });
  }
});

test("Start patient intake opens the intake start step, then the intake route", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("home-patient-cta").click();
  await expect(page).toHaveURL(/\/intake$/);
  await expect(page.getByRole("heading", { name: "Start patient intake" })).toBeVisible();
  await expect(page.getByText(LIVE ? "Live API" : "Mock API — shared fixture responses, no backend")).toBeVisible();
  await expect(page.getByText("Fictional demonstration only.", { exact: false })).toBeVisible();
  await page.getByLabel("Demo access code").fill(CODE);
  await page.getByRole("button", { name: "Load collections" }).click();
  await page.getByRole("button", { name: "Start intake", exact: true }).click();
  await expect(page).toHaveURL(/\/intake\/[^/]+$/);
  await expect(page.getByRole("heading", { name: "Patient intake" })).toBeVisible();
});

test("Open doctor workspace: explains first, then opens the doctor route for this tab's intake", async ({ page }) => {
  await page.goto("/");
  const disabled = page.getByTestId("home-doctor-cta");
  await expect(disabled).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByText("Share a patient intake first to review it here.")).toBeVisible();
  // Still reachable by keyboard, but it does not navigate anywhere without an intake.
  await disabled.focus();
  await expect(disabled).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/$/);

  await page.getByTestId("home-patient-cta").click();
  await page.getByLabel("Demo access code").fill(CODE);
  await page.getByRole("button", { name: "Load collections" }).click();
  await page.getByRole("button", { name: "Start intake", exact: true }).click();
  await expect(page).toHaveURL(/\/intake\/([^/]+)$/);
  const sessionId = page.url().split("/intake/")[1];

  await page.goto("/");
  const doctor = page.getByRole("link", { name: "Open doctor workspace" });
  await expect(doctor).toHaveAttribute("href", `/doctor/${sessionId}`);
  await doctor.click();
  await expect(page).toHaveURL(new RegExp(`/doctor/${sessionId}$`));
  await expect(page.getByRole("heading", { name: "Doctor workspace" })).toBeVisible();
  // Not yet confirmed and shared: the existing guard still withholds the brief.
  await expect(page.getByTestId("doctor-awaiting")).toBeVisible();
});
