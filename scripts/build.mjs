import { createHash, generateKeyPairSync } from "node:crypto";
import { existsSync } from "node:fs";
import { readFile, writeFile, mkdir, cp } from "node:fs/promises";
import { deflateSync } from "node:zlib";

await mkdir("dist/chromium", { recursive: true });
const keyPath = "extension/public-key.json";
if (!existsSync(keyPath)) {
  const { publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  await writeFile(
    keyPath,
    JSON.stringify(
      { key: publicKey.export({ type: "spki", format: "der" }).toString("base64") },
      null,
      2,
    ) + "\n",
  );
}
const { key } = JSON.parse(await readFile(keyPath, "utf8"));
const extensionId = [
  ...createHash("sha256").update(Buffer.from(key, "base64")).digest().subarray(0, 16),
]
  .flatMap((byte) => [byte >> 4, byte & 15])
  .map((n) => String.fromCharCode(97 + n))
  .join("");
const manifest = {
  manifest_version: 3,
  name: "Longwave — SoundCloud audio",
  version: JSON.parse(await readFile("package.json", "utf8")).version.split("-")[0],
  version_name: JSON.parse(await readFile("package.json", "utf8")).version,
  description:
    "Save public audio locally, with a companion built for long listening. No third-party conversion servers.",
  key,
  permissions: ["nativeMessaging", "activeTab", "storage"],
  background: { service_worker: "background.js", type: "module" },
  action: { default_popup: "popup.html", default_title: "Longwave" },
  icons: { 16: "icons/16.png", 48: "icons/48.png", 128: "icons/128.png" },
  content_security_policy: {
    extension_pages: "script-src 'self'; object-src 'none'; base-uri 'none'; connect-src 'none'",
  },
};
await cp("extension/public", "dist/chromium", { recursive: true });
await cp("extension/public/index.html", "dist/chromium/popup.html");
await writeFile("dist/chromium/manifest.json", JSON.stringify(manifest, null, 2) + "\n");
await writeFile("dist/extension-id.txt", extensionId + "\n");
// Small deterministic PNG icons. No runtime image dependencies or remote assets.
function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(name, data) {
  const type = Buffer.from(name);
  const header = Buffer.alloc(4);
  header.writeUInt32BE(data.length);
  const check = Buffer.alloc(4);
  check.writeUInt32BE(crc32(Buffer.concat([type, data])));
  return Buffer.concat([header, type, data, check]);
}
await mkdir("dist/chromium/icons", { recursive: true });
for (const size of [16, 48, 128]) {
  const pixels = Buffer.alloc((size * 4 + 1) * size);
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const offset = y * (size * 4 + 1) + 1 + x * 4;
      const bar = Math.floor((x / size) * 9) - 2;
      const heights = [0.25, 0.45, 0.65, 0.45, 0.25];
      const inBar =
        bar >= 0 &&
        bar < 5 &&
        x % (size / 9) < size / 18 &&
        Math.abs(y / size - 0.5) < heights[bar] / 2;
      const color = inBar ? (bar === 2 ? [236, 141, 87] : [192, 217, 177]) : [21, 46, 43];
      pixels.set([...color, 255], offset);
    }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size);
  header.writeUInt32BE(size, 4);
  header[8] = 8;
  header[9] = 6;
  await writeFile(
    `dist/chromium/icons/${size}.png`,
    Buffer.concat([
      Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
      chunk("IHDR", header),
      chunk("IDAT", deflateSync(pixels)),
      chunk("IEND", Buffer.alloc(0)),
    ]),
  );
}
console.log(`Built dist/chromium\nExtension ID: ${extensionId}`);
