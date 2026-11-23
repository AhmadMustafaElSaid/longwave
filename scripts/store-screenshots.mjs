import { chromium } from "playwright-core";
import { readFile } from "node:fs/promises";
import { extname, resolve } from "node:path";

// Capture the shipped UI with a local sample snapshot for the store listing.
// Keeping the destination generic avoids publishing a workstation username.
const version = JSON.parse(await readFile("package.json", "utf8")).version;
const browser = await chromium.launch({ executablePath: process.env.LONGWAVE_BROWSER });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const contentTypes = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".css": "text/css",
    ".png": "image/png",
  };
  await page.route("https://longwave.test/**", async (route) => {
    const relative = new URL(route.request().url()).pathname.slice(1);
    await route.fulfill({
      contentType: contentTypes[extname(relative)],
      body: await readFile(resolve("dist/chromium", relative)),
    });
  });
  await page.addInitScript((releaseVersion) => {
    window.chrome.storage = {
      local: { get: async () => ({ language: "en" }), set: async () => {} },
    };
    window.chrome.runtime = {
      sendMessage: async () => ({
        ok: true,
        data: {
          version: releaseVersion,
          protocol: 1,
          tools: { ffmpeg: true, ffprobe: true, extractor: true },
          outputDir: "Downloads/Longwave",
          jobs: [],
        },
      }),
    };
  }, version);
  await page.goto("https://longwave.test/index.html");
  await page.locator("#connection.online").waitFor();
  await page.screenshot({ path: "docs/images/dashboard.png" });
  await page.locator("#language").click();
  await page.screenshot({ path: "docs/images/dashboard-ar.png" });
} finally {
  await browser.close();
}
