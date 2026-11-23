import { chromium, webkit, devices } from "playwright-core";
import AxeBuilder from "@axe-core/playwright";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { createInterface } from "node:readline";
import assert from "node:assert/strict";

const server = spawn(process.env.LONGWAVE_TEST_PYTHON || "python", ["scripts/phone_fixture.py"], {
  stdio: ["pipe", "pipe", "inherit"],
});
const timeout = setTimeout(() => server.kill(), 90000);
let browser;
try {
  const reader = createInterface({ input: server.stdout });
  const { value: line } = await reader[Symbol.asyncIterator]().next();
  const { origin, code, sha256 } = JSON.parse(line);
  const useWebKit = process.env.PHONE_ENGINE === "webkit";
  browser = await (useWebKit ? webkit : chromium).launch({
    executablePath: process.env.LONGWAVE_BROWSER,
    headless: true,
  });
  const context = await browser.newContext({
    ...devices[useWebKit ? "iPhone 13" : "Pixel 7"],
    locale: "en-US",
    acceptDownloads: true,
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(origin);
  await page.getByLabel("Pairing code").fill(code);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByText("Test recording", { exact: true }).waitFor();
  const saved = page.waitForEvent("download");
  await page.getByRole("link", { name: "Save to phone" }).click();
  const download = await saved;
  assert.equal(download.suggestedFilename(), "Longwave test.wav");
  assert.equal(
    createHash("sha256")
      .update(await readFile(await download.path()))
      .digest("hex"),
    sha256,
  );
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("audio").currentTime > 0);
  await page.getByLabel("Playback speed").selectOption("2");
  assert.equal(await page.locator("audio").evaluate((a) => a.playbackRate), 2);
  await page.getByRole("button", { name: "العربية", exact: true }).click();
  assert.equal(await page.locator("html").getAttribute("dir"), "rtl");
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  assert.deepEqual(
    violations.map((item) => item.id),
    [],
  );
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify({
      engine: useWebKit ? "WebKit" : "Chromium",
      version: browser.version(),
      pair: true,
      downloadSha256: sha256,
      playbackRate: 2,
      rtl: true,
      axeViolations: 0,
    }),
  );
} finally {
  server.stdin.end();
  try {
    await browser?.close();
  } finally {
    clearTimeout(timeout);
  }
}
