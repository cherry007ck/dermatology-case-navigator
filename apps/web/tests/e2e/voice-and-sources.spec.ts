import { expect, type Page, test } from "@playwright/test";

// Voice states and the source drawer, against the labelled fixture mock.
// Provider calls are never made here: /api/voice-* are intercepted where a
// configured server is simulated. A real ElevenLabs connection is verified manually.

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
}

async function say(page: Page, text: string) {
  await page.getByLabel(/In your own words|Your answer/).fill(text);
  await page.getByRole("button", { name: /^Send/ }).click();
}

function simulateConfiguredVoiceServer(page: Page) {
  return page.route("**/api/voice-status", (route) => route.fulfill({ json: { configured: true } }));
}

function stubMicrophone(page: Page, outcome: "deny" | "grant") {
  return page.addInitScript((mode) => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => {
          if (mode === "deny") throw new DOMException("Permission denied", "NotAllowedError");
          return { getTracks: () => [] } as unknown as MediaStream;
        },
      },
    });
  }, outcome);
}

test.describe("voice panel states", () => {
  test("unconfigured server offers typed intake only", async ({ page }) => {
    await startEncounter(page);
    await expect(page.getByTestId("voice-status")).toHaveText("Voice is not configured on this server. Typed intake is available.");
    await expect(page.getByRole("button", { name: "Start voice" })).toBeDisabled();
    await expect(page.getByTestId("mode-banner")).toContainText("Voice not configured — typed intake");
  });

  test("microphone denied keeps typed intake working", async ({ page }) => {
    await simulateConfiguredVoiceServer(page);
    await stubMicrophone(page, "deny");
    let sessionRequested = false;
    await page.route("**/api/voice-session", (route) => {
      sessionRequested = true;
      return route.abort();
    });
    await startEncounter(page);
    await page.getByRole("button", { name: "Start voice" }).click();
    await expect(page.getByTestId("voice-status")).toContainText("Microphone access was denied");
    await expect(page.getByTestId("mode-banner")).toContainText("Microphone denied — typed intake");
    expect(sessionRequested).toBe(false); // no signed URL requested without a microphone
    await say(page, MAIN[0]);
    await expect(page.getByTestId("story-turns").getByRole("listitem")).toHaveCount(1);
  });

  test("provider failure shows an honest error and reconnect", async ({ page }) => {
    await simulateConfiguredVoiceServer(page);
    await stubMicrophone(page, "grant");
    await page.route("**/api/voice-session", (route) =>
      route.fulfill({
        status: 502,
        json: {
          error: { code: "VOICE_PROVIDER_UNAVAILABLE", message: "The voice service could not start a session. Use typed intake or retry.", retryable: true },
          request_id: null,
        },
      }),
    );
    await startEncounter(page);
    await page.getByRole("button", { name: "Start voice" }).click();
    await expect(page.getByTestId("voice-panel").getByRole("alert")).toContainText("could not start a session");
    await expect(page.getByRole("button", { name: "Reconnect voice" })).toBeEnabled();
    await expect(page.getByTestId("mode-banner")).toContainText("Voice error — typed intake");
  });
});

test("source drawer shows exact quotes, closes on Escape and returns focus", async ({ page }) => {
  await startEncounter(page);
  for (const line of MAIN) await say(page, line);
  await page.getByRole("button", { name: "Confirm and open doctor brief" }).click();
  await expect(page.getByRole("heading", { name: "Doctor workspace" })).toBeVisible();

  // Patient quote from the brief.
  const patientChip = page.getByTestId("brief-panel").getByRole("button", { name: /Patient quote: “itchy”/ }).first();
  await patientChip.click();
  const drawer = page.getByTestId("source-drawer");
  await expect(drawer.getByRole("heading", { name: "Patient statement" })).toBeVisible();
  await expect(drawer.locator("mark")).toHaveText("itchy");
  await expect(drawer).toContainText(MAIN[0]);
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(patientChip).toBeFocused();

  // Case passage from a fictional card, opened with the keyboard.
  const caseChip = page.getByTestId("case-card").first().getByRole("button", { name: /Case passage quote/ }).first();
  await caseChip.focus();
  await page.keyboard.press("Enter");
  await expect(drawer.getByRole("heading", { name: "Fictional case passage" })).toBeVisible();
  await expect(drawer).toContainText("Fictional demonstration case — not published evidence");
  await expect(drawer).toContainText("Not clinically reviewed.");
  await expect(drawer.getByRole("link", { name: "Original article" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(caseChip).toBeFocused();
});

test.describe("voice-session server route guards", () => {
  const body = { session_id: "S-1", expected_revision: 0, request_id: "r-1" };

  test("rejects cross-origin and missing origin", async ({ request, baseURL }) => {
    const none = await request.post("/api/voice-session", { data: body });
    expect(none.status()).toBe(403);
    const cross = await request.post("/api/voice-session", { data: body, headers: { Origin: "https://evil.example" } });
    expect(cross.status()).toBe(403);
    expect((await cross.json()).error.code).toBe("FORBIDDEN_ORIGIN");
    expect(baseURL).toBeTruthy();
  });

  test("requires a bearer token and a contract-shaped body", async ({ request, baseURL }) => {
    const origin = new URL(baseURL!).origin;
    const noAuth = await request.post("/api/voice-session", { data: body, headers: { Origin: origin } });
    expect(noAuth.status()).toBe(401);
    const bad = await request.post("/api/voice-session", {
      data: { ...body, agent_id: "model-supplied" },
      headers: { Origin: origin, Authorization: "Bearer x" },
    });
    expect(bad.status()).toBe(422);
  });

  test("reports unconfigured voice without leaking configuration", async ({ request, baseURL }) => {
    const origin = new URL(baseURL!).origin;
    const res = await request.post("/api/voice-session", { data: body, headers: { Origin: origin, Authorization: "Bearer x" } });
    expect(res.status()).toBe(503);
    const json = await res.json();
    expect(json.error.code).toBe("VOICE_NOT_CONFIGURED");
    expect(JSON.stringify(json)).not.toMatch(/xi-api-key|agent_|elevenlabs\.io/i);
    expect((await (await request.get("/api/voice-status")).json())).toEqual({ configured: false });
  });
});
