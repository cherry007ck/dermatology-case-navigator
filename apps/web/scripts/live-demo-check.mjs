// Live demo verification in a real browser: web app (live mode) -> FastAPI (Exasol + Meta) -> published-derm-v1.
//
//   node scripts/live-demo-check.mjs [webBaseUrl] [screenshotDir]
//
// Defaults: http://localhost:3000, no screenshots. The demo access code comes from E2E_DEMO_CODE or
// ../../services/api/.env and is never printed. Fictional patient text only. Prints observations and a
// PASS/FAIL line per check; exit code 1 if any check fails. Not part of CI (needs live services).
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://localhost:3000";
const shots = process.argv[3];
if (shots && !existsSync(shots)) mkdirSync(shots, { recursive: true });
const envPath = new URL("../../../services/api/.env", import.meta.url);
const code = process.env.E2E_DEMO_CODE
  ?? (existsSync(envPath) ? readFileSync(envPath, "utf8").match(/^\s*DEMO_ACCESS_CODE\s*=\s*['"]?([^'"\r\n]+)/m)?.[1]?.trim() : undefined);
if (!code) throw new Error("Set E2E_DEMO_CODE (demo access code); it is never printed.");

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}
const flat = (s) => s.replace(/\s+/g, " ").trim();
async function shot(page, name) {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}

async function start(page) {
  await page.goto(`${base}/`);
  const intakeLink = page.getByRole("link", { name: /start|patient/i }).first();
  if (!(await page.getByLabel("Demo access code").count()) && (await intakeLink.count())) await intakeLink.click();
  if (!(await page.getByLabel("Demo access code").count())) await page.goto(`${base}/intake`);
  await page.getByLabel("Demo access code").fill(code);
  await page.getByRole("button", { name: "Load collections" }).click();
  await page.getByText("Published — source-reviewed cases").waitFor({ timeout: 30000 });
  const main = await page.getByRole("main").innerText();
  check("only the published collection is offered", !main.includes("Synthetic — fictional"));
  await page.getByRole("button", { name: "Start intake" }).click();
  await page.getByRole("heading", { name: "Patient intake" }).waitFor();
  await page.getByTestId("mode-banner").getByText("Stored in Exasol").waitFor({ timeout: 30000 }).catch(() => {});
  const banner = flat(await page.getByTestId("mode-banner").innerText());
  check("live modes shown (Exasol + Meta + published)", /Stored in Exasol/.test(banner) && /Meta model extraction/.test(banner)
    && /Published collection/.test(banner), banner.slice(0, 160));
}

async function settle(page) {
  await page.waitForTimeout(500);
  await page.waitForFunction(() => {
    const busy = document.body.innerText.includes("Saving and processing");
    const editing = [...document.querySelectorAll("button")].some((b) => b.textContent?.trim() === "Save correction");
    const stale = document.querySelector('[data-testid="brief-review-stale"]');
    return !busy && !editing && !stale;
  }, null, { timeout: 120000 });
  await page.waitForTimeout(800);
}

async function say(page, text) {
  await page.getByRole("textbox", { name: /In your own words|Your answer/ }).fill(text);
  await page.getByRole("button", { name: /^Send/ }).click();
  await settle(page);
}

async function patientHasNoCaseContent(page, label) {
  const text = await page.getByRole("main").innerText();
  const leaked = ["PUB-PMC", "Minoxidil 5%", "Contact Allergic Dermatitis", "Dyshidrotic", "Cureus", "Clinician assessment",
    "DEMO-NOTE"].filter((s) => text.includes(s));
  check(`${label}: patient view shows no case content or clinician notes`, leaked.length === 0, leaked.join(", "));
}

async function confirmToDoctor(page) {
  await page.getByRole("button", { name: "Confirm and open doctor brief" }).click();
  await page.getByRole("heading", { name: "Doctor workspace" }).waitFor({ timeout: 60000 });
  await page.waitForTimeout(1200);
}

const browser = await chromium.launch();
try {
  // ---------------------------------------------------------------- Story A: scalp itching + minoxidil
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await start(page);
  await say(page, "My scalp has been itching for several days. I used minoxidil foam around the time it started.");
  const review = flat(await page.getByTestId("brief-review").innerText());
  check("A: patient summary states the symptom at its site", review.includes("Patient reports itching on the scalp."));
  check("A: patient summary keeps the named product", review.includes("Patient mentions using minoxidil foam."));
  check("A: product not turned into treatment", !/Treatment you mentioned.*minoxidil/.test(review));
  await patientHasNoCaseContent(page, "A");
  await shot(page, "A1-patient-review");
  await confirmToDoctor(page);
  check("A: doctor sees confirmed revision 1", (await page.getByRole("main").innerText()).includes("Patient confirmed revision 1"));
  const brief = flat(await page.getByTestId("brief-panel").innerText());
  check("A: doctor brief includes the product", brief.includes("Patient mentions using minoxidil foam."));
  const cards = page.getByTestId("case-card");
  check("A: exactly one published card", (await cards.count()) === 1);
  const card = flat(await cards.first().innerText());
  check("A: minoxidil case retrieved", card.includes("A Case of Contact Allergic Dermatitis to Topical Minoxidil"));
  check("A: same-site evidence shown", card.includes("itching on the scalp") && card.includes("itchiness over the scalp"));
  check("A: no fictional label on a published card", !card.includes("Fictional demonstration case"));
  check("A: attribution and licence visible", /BinJadeed/.test(card) && /Cureus/.test(card) && /CC BY 3\.0/.test(card), card.slice(0, 0));
  const link = cards.first().getByRole("link", { name: /Original article|PMC7861115|article/i }).first();
  check("A: original article link", (await link.count()) > 0 && (await link.getAttribute("href")) === "https://pmc.ncbi.nlm.nih.gov/articles/PMC7861115/");
  const quote = cards.first().getByRole("button", { name: /Case passage quote/ }).first();
  await quote.click();
  const drawer = page.getByRole("dialog");
  await drawer.waitFor();
  const dtext = flat(await drawer.innerText());
  check("A: source drawer shows the exact passage and locator", dtext.includes("she reported itchiness over the scalp") && dtext.includes("PMC7861115"));
  await shot(page, "A2-doctor-source-drawer");
  await page.keyboard.press("Escape");
  const closed = await page.getByRole("dialog").waitFor({ state: "hidden", timeout: 5000 }).then(() => true, () => false);
  check("A: drawer closes with Escape", closed);
  await shot(page, "A3-doctor-workspace");

  // Clinician note stays separate.
  const author = page.getByLabel("Author label");
  if (await author.count()) {
    await author.fill("Demo clinician");
    await page.getByLabel("Assessment note").fill("DEMO-NOTE fictional assessment text.");
    await page.getByRole("button", { name: "Save note" }).click();
    await page.getByText("DEMO-NOTE fictional assessment text.").first().waitFor({ timeout: 30000 });
    check("A: clinician note saved in the doctor workspace", true);
  } else {
    check("A: clinician note panel present", false);
  }

  // Correction after confirmation: original kept, confirmation invalidated, summary recomputed.
  await page.goBack();
  await page.getByRole("heading", { name: "Patient intake" }).waitFor();
  await page.getByRole("button", { name: /^Correct:/ }).first().click();
  await page.getByLabel("Correct what you said").fill(
    "My scalp has been itching for about two weeks. I used minoxidil foam around the time it started.");
  await page.getByRole("button", { name: "Save correction" }).click();
  await settle(page);
  const after = await page.getByRole("main").innerText();
  check("A: correction invalidates the earlier confirmation", /no longer applies/.test(after));
  check("A: original words kept as replaced", (await page.getByTestId("replaced-history").count()) > 0);
  const review2 = flat(await page.getByTestId("brief-review").innerText());
  check("A: summary recomputed from the correction", review2.includes("weeks") && !review2.includes("“several days”"));
  await patientHasNoCaseContent(page, "A after correction");
  await shot(page, "A4-patient-after-correction");
  await confirmToDoctor(page);
  const main2 = await page.getByRole("main").innerText();
  check("A: doctor now sees confirmed revision 2", main2.includes("Patient confirmed revision 2"));
  check("A: doctor brief matches the corrected revision", flat(await page.getByTestId("brief-panel").innerText()).includes("weeks"));
  await shot(page, "A5-doctor-after-correction");
  await page.close();

  // ---------------------------------------------------------------- Story B: facial itching, skip, no-match
  const pageB = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await start(pageB);
  await say(pageB, "My face is itchy.");
  const q = pageB.getByTestId("current-question");
  check("B: a clarification is asked", (await q.count()) > 0, (await q.count()) ? await q.innerText() : "");
  await pageB.getByRole("button", { name: "Skip" }).click();
  await settle(pageB);
  const reviewB = flat(await pageB.getByTestId("brief-review").innerText());
  check("B: skip recorded as skipped (not a no)", reviewB.includes("Clarification skipped by the patient"));
  await shot(pageB, "B1-patient-skip-390px");
  await confirmToDoctor(pageB);
  const mainB = flat(await pageB.getByRole("main").innerText());
  check("B: honest no-match (no card)", (await pageB.getByTestId("case-card").count()) === 0 && /No qualifying case/.test(mainB));
  check("B: no-match wording uses the same-site rule", /same (body )?site/i.test(mainB), "");
  await shot(pageB, "B2-doctor-no-match-390px");
  await pageB.close();
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
