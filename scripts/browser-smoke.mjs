import { chromium } from "playwright-core";
import AxeBuilder from "@axe-core/playwright";
import { readFile, mkdir, mkdtemp } from "node:fs/promises";
import { resolve } from "node:path";
const id = (await readFile("dist/extension-id.txt", "utf8")).trim();
const extension = resolve(process.env.LONGWAVE_EXTENSION ?? "dist/chromium");
await mkdir("artifacts", { recursive: true });
await mkdir(".runtime", { recursive: true });
// A fresh profile prevents Chromium from serving a previous build's cached worker.
const profile = await mkdtemp(resolve(".runtime/browser-smoke-"));
const browserPath =
  process.env.LONGWAVE_BROWSER ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const chromeBranded = browserPath.toLowerCase().endsWith("chrome.exe");
const context = await chromium.launchPersistentContext(profile, {
  executablePath:
    process.env.LONGWAVE_BROWSER ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
  viewport: { width: 1440, height: 1080 },
  ignoreDefaultArgs: ["--disable-extensions"],
  args: [
    ...(chromeBranded
      ? []
      : [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]),
    "--no-first-run",
    ...(chromeBranded ? ["--enable-unsafe-extension-debugging"] : []),
  ],
});
try {
  if (chromeBranded) {
    // Test-only CDP pipe in a fresh disposable profile; never set on a user's browser.
    const session = await context.browser().newBrowserCDPSession();
    await session.send("Extensions.loadUnpacked", { path: extension });
  }
  const page = await context.newPage();
  if (chromeBranded) {
    await page.goto("chrome://extensions");
    await page.evaluate(() =>
      chrome.developerPrivate.updateProfileConfiguration({ inDeveloperMode: true }),
    );
  }
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`chrome-extension://${id}/index.html`);
  await page.evaluate(async () => chrome.storage.local.set({ language: "en" }));
  await page.reload();
  await page.locator("#connection.online").waitFor({ timeout: 20000 });
  if (
    process.env.LONGWAVE_EXPECTED_OUTPUT &&
    (await page.locator("#destination").textContent()) !== process.env.LONGWAVE_EXPECTED_OUTPUT
  )
    throw new Error("The browser connected to a different companion installation.");
  await page.screenshot({ path: "artifacts/dashboard-en.png", fullPage: true });
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  if (accessibility.violations.length)
    console.log(
      JSON.stringify(
        {
          accessibility: accessibility.violations.map((v) => ({
            id: v.id,
            impact: v.impact,
            nodes: v.nodes.map((n) => ({ target: n.target, message: n.failureSummary })),
          })),
        },
        null,
        2,
      ),
    );
  if (await page.locator("#submit").isDisabled())
    throw new Error("Download button remained disabled after connection.");
  await page.locator("#language").click();
  if ((await page.locator("html").getAttribute("dir")) !== "rtl")
    throw new Error("Arabic direction was not applied.");
  await page.screenshot({ path: "artifacts/dashboard-ar.png", fullPage: true });
  const arabicAccessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  await page.locator("#connection").click();
  await page.locator("#setup-dialog").waitFor({ state: "visible" });
  await page.keyboard.press("Escape");
  if (await page.locator("#setup-dialog").isVisible())
    throw new Error("Setup dialog did not close with Escape.");
  await page.goto(`chrome-extension://${id}/popup.html`);
  await page.locator("#connection.online").waitFor();
  await page.setViewportSize({ width: 420, height: 800 });
  await page.screenshot({ path: "artifacts/popup-ar.png", fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  if (overflow) throw new Error("Popup has horizontal overflow.");
  const popupAccessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  const share = "https://on.soundcloud.com/Abc123";
  await page.locator("#url").fill(share);
  const workspaceOpened = context.waitForEvent("page");
  await page.locator("#open-workspace").click();
  const workspace = await workspaceOpened;
  await workspace.waitForLoadState();
  await workspace.locator("#connection.online").waitFor();
  if ((await workspace.locator("#url").inputValue()) !== share)
    throw new Error(`Opening the workspace lost the share link: ${workspace.url()}`);
  if (errors.length) throw new Error(errors.join("\n"));
  const violations = [
    ...accessibility.violations,
    ...arabicAccessibility.violations,
    ...popupAccessibility.violations,
  ];
  if (violations.length)
    throw new Error(
      `Accessibility checks found violations: ${violations.map((v) => v.id).join(", ")}`,
    );
  console.log(
    JSON.stringify(
      {
        ok: true,
        browser: context.browser()?.version(),
        nativeMessaging: true,
        checks: [
          "connected",
          "download control",
          "Arabic RTL",
          "dialog keyboard dismissal",
          "popup overflow",
          "share-link workspace handoff",
          "no page errors",
        ],
        accessibility: {
          scopes: ["English workspace", "Arabic workspace", "Arabic popup"],
          violations: 0,
          tags: ["wcag2a", "wcag2aa", "wcag21aa"],
        },
        screenshots: [
          "artifacts/dashboard-en.png",
          "artifacts/dashboard-ar.png",
          "artifacts/popup-ar.png",
        ],
      },
      null,
      2,
    ),
  );
} finally {
  await context.close();
}
