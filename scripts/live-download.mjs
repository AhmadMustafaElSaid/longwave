// Explicit integration run with a user-supplied public track. Leaves the job running.
import { chromium } from "playwright-core";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
const url = process.argv[2];
if (!url) throw new Error("Supply the SoundCloud track URL to test.");
const id = (await readFile("dist/extension-id.txt", "utf8")).trim();
const extension = resolve("dist/chromium");
const context = await chromium.launchPersistentContext(resolve(".runtime/browser-test"), {
  executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
  viewport: { width: 1440, height: 1080 },
  ignoreDefaultArgs: ["--disable-extensions"],
  args: [
    `--disable-extensions-except=${extension}`,
    `--load-extension=${extension}`,
    "--no-first-run",
  ],
});
try {
  const page = await context.newPage();
  await page.goto(`chrome-extension://${id}/index.html`);
  await page.locator("#connection.online").waitFor();
  await page.locator("#url").fill(url);
  await page.locator("#submit").click();
  await page.locator(".job").first().waitFor();
  await page.screenshot({ path: "artifacts/live-queued.png", fullPage: true });
  const result = await page.evaluate(async () =>
    chrome.runtime.sendMessage({ version: 1, command: "snapshot" }),
  );
  console.log(JSON.stringify(result, null, 2));
} finally {
  await context.close();
}
