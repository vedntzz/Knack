// Capture this page: PLAYWRIGHT=<playwright/index.mjs> node mockups/landing/capture.mjs  → mockups/shots/landing/
// The shared capture takes the first screen at 1080p and 720p; a scrolling page also needs its full length at both.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, resolve } from "node:path";

process.argv.splice(2, Infinity, "landing", "view=landing", "0,300,600");
await import("../tools/capture_page.mjs");

const { chromium } = await import(process.env.PLAYWRIGHT);
const REPO = resolve(new URL("../..", import.meta.url).pathname);
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2", ".png": "image/png" };
const server = createServer(async (req, res) => {
  const path = join(REPO, decodeURIComponent(new URL(req.url, "http://x").pathname));
  try { res.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream" }); res.end(await readFile(path)); } catch { res.writeHead(404); res.end(); }
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const browser = await chromium.launch();
for (const [size, viewport] of [["1080p", { width: 1920, height: 1080 }], ["720p", { width: 1280, height: 720 }]]) {
  const page = await browser.newPage({ viewport });
  await page.goto(`http://127.0.0.1:${server.address().port}/mockups/landing/index.html`);
  await page.waitForFunction(() => window.__ready === true);
  await page.waitForTimeout(900);
  await page.screenshot({ path: join(REPO, `mockups/shots/landing/landing-${size}-fullpage.png`), fullPage: true });
  await page.close();
}
await browser.close();
server.close();
