// Capture one mockup page at 1080p and 720p, its arrival beats, a 4 s video, and the measured contrast of every text node.
// Run: PLAYWRIGHT=<path to playwright/index.mjs> node mockups/tools/capture_page.mjs <page> <query> [beat ms,...]
//   e.g. argue outcome=hold 0,500,1100,1500,2400   ·   held outcome=escalate 0,600,900,1400
import { createServer } from "node:http";
import { readFile, mkdir, readdir, rename, rm, writeFile } from "node:fs/promises";
import { extname, join, resolve } from "node:path";

const { chromium } = await import(process.env.PLAYWRIGHT);
const REPO = resolve(new URL("../..", import.meta.url).pathname);
const [name = "argue", query = "outcome=hold", beats = "0,500,1100,1500,2400"] = process.argv.slice(2);
const SHOTS = join(REPO, `mockups/shots/${name}`);
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2" };
const PAGE = `/mockups/${name}/index.html?${query}`;

const serve = () => new Promise((ok) => {
  const server = createServer(async (req, res) => {
    const path = join(REPO, decodeURIComponent(new URL(req.url, "http://x").pathname));
    try { res.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream" }); res.end(await readFile(path)); }
    catch { res.writeHead(404); res.end(); }
  });
  server.listen(0, "127.0.0.1", () => ok(server));
});

const open = async (browser, url, viewport, extra = {}) => {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, ...extra });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => !r.url().startsWith("http://127.0.0.1") && !r.url().startsWith("data:") && errors.push("network: " + r.url()));
  await page.goto(url);
  await page.waitForFunction(() => window.__ready === true);
  return { context, page, errors };
};

// Every visible text node, its colour against the first opaque background behind it.
const measure = () => {
  const rgb = (s) => (s.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => [r, g, b].map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }).reduce((a, c, i) => a + c * [0.2126, 0.7152, 0.0722][i], 0);
  const bg = (el) => { for (; el; el = el.parentElement) { const c = rgb(getComputedStyle(el).backgroundColor); if (c.length >= 3 && (c[3] ?? 1) === 1) return c; } return [11, 12, 14]; };
  const out = [];
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = walk.nextNode());) {
    const el = n.parentElement, text = n.textContent.trim();
    if (!text || !el.getClientRects().length) continue;
    const s = getComputedStyle(el), a = lum(rgb(s.color)), b = lum(bg(el));
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const px = parseFloat(s.fontSize), large = px >= 24 || (px >= 18.66 && Number(s.fontWeight) >= 600);
    out.push({ text: text.slice(0, 40), px, ratio: Math.round(ratio * 100) / 100, pass: ratio >= (large ? 3 : 4.5) });
  }
  const over = document.documentElement.scrollHeight - innerHeight, wide = document.documentElement.scrollWidth - innerWidth;
  return { nodes: out.length, failing: out.filter((x) => !x.pass), lowest: out.sort((x, y) => x.ratio - y.ratio).slice(0, 6), minPx: Math.min(...out.map((x) => x.px)), overflowY: over, overflowX: wide };
};

const server = await serve();
const base = `http://127.0.0.1:${server.address().port}`;
await mkdir(SHOTS, { recursive: true });
const browser = await chromium.launch();
const report = {};
for (const [size, viewport] of [["1080p", { width: 1920, height: 1080 }], ["720p", { width: 1280, height: 720 }]]) {
  const { context, page, errors } = await open(browser, `${base}${PAGE}&t=3000`, viewport);
  await page.screenshot({ path: join(SHOTS, `${name}-${size}.png`) });
  report[size] = { ...(await page.evaluate(measure)), errors };
  await context.close();
}
// The beats at 720p, so a frozen frame can be checked to make sense on its own.
for (const t of beats.split(",").map(Number)) {
  const { context, page } = await open(browser, `${base}${PAGE}&t=${t}`, { width: 1280, height: 720 });
  await page.screenshot({ path: join(SHOTS, `beat-720p-${String(t).padStart(4, "0")}ms.png`) });
  await context.close();
}
const reduced = await open(browser, `${base}${PAGE}`, { width: 1280, height: 720 }, { reducedMotion: "reduce" });
await reduced.page.screenshot({ path: join(SHOTS, `${name}-720p-reduced.png`) });
await reduced.context.close();
const phone = await open(browser, `${base}${PAGE}&t=3000`, { width: 390, height: 844 });
await phone.page.screenshot({ path: join(SHOTS, `${name}-390-fullpage.png`), fullPage: true });
report.phone = await phone.page.evaluate(measure);
await phone.context.close();
const dir = join(SHOTS, ".video");
const film = await open(browser, `${base}${PAGE}`, { width: 1280, height: 720 }, { recordVideo: { dir, size: { width: 1280, height: 720 } } });
await film.page.waitForTimeout(4000);
await film.context.close();
const [clip] = await readdir(dir);
await rename(join(dir, clip), join(SHOTS, "arrival-720p-4s.webm"));
await rm(dir, { recursive: true });
await browser.close();
server.close();
await writeFile(join(SHOTS, "report.json"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));
