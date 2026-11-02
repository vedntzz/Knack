// Capture site/ as GitHub Pages serves it: 1080p first screen and full page, 390 first screen and full page, 720p reduced motion.
// Run: PLAYWRIGHT=<playwright/index.mjs> [CHANNEL=chrome] node mockups/tools/capture_site.mjs  → mockups/shots/landing/site-*
// Also writes site-report.json: per width, every text node failing AA, overflow, console errors, outside requests, the smallest type.
import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { extname, join, resolve } from "node:path";

const { chromium } = await import(process.env.PLAYWRIGHT);
const REPO = resolve(new URL("../..", import.meta.url).pathname);
const SHOTS = join(REPO, "mockups/shots/landing");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2", ".png": "image/png", ".txt": "text/plain" };

const server = createServer(async (req, res) => {
  const path = join(REPO, "site", decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/\/$/, "/index.html"));
  try { res.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream" }); res.end(await readFile(path)); }
  catch { res.writeHead(404); res.end(); }
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const URL_ = `http://127.0.0.1:${server.address().port}/`;

// Every visible text node, its colour against the first opaque background behind it.
const measure = () => {
  const rgb = (s) => (s.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => [r, g, b].map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }).reduce((a, c, i) => a + c * [0.2126, 0.7152, 0.0722][i], 0);
  const bg = (el) => { for (; el; el = el.parentElement) { const c = rgb(getComputedStyle(el).backgroundColor); if (c.length >= 3 && (c[3] ?? 1) === 1) return c; } return [11, 12, 14]; };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const fails = []; let nodes = 0, min = Infinity, lowest = Infinity;
  for (let n; (n = walker.nextNode());) {
    const el = n.parentElement, text = n.textContent.trim();
    if (!text || !el.offsetParent && getComputedStyle(el).position !== "fixed" || el.closest("[hidden]")) continue;
    const s = getComputedStyle(el), size = parseFloat(s.fontSize), [a, b] = [lum(rgb(s.color)), lum(bg(el))];
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05), need = size >= 24 || (size >= 18.66 && +s.fontWeight >= 600) ? 3 : 4.5;
    nodes++; min = Math.min(min, size); lowest = Math.min(lowest, ratio);
    if (ratio < need) fails.push({ text: text.slice(0, 40), ratio: +ratio.toFixed(2), need });
  }
  const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  return { nodes, fails, minPx: min, lowestRatio: +lowest.toFixed(2), overflow, h1Lines: Math.round(document.querySelector("h1").getBoundingClientRect().height / parseFloat(getComputedStyle(document.querySelector("h1")).lineHeight)) };
};

const browser = await chromium.launch({ channel: process.env.CHANNEL || undefined });
const report = {};
const shoot = async (name, viewport, extra = {}) => {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, ...extra });
  const page = await context.newPage(), errors = [], outside = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => !r.url().startsWith(URL_) && !r.url().startsWith("data:") && outside.push(r.url()));
  await page.goto(URL_, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(900);
  await page.screenshot({ path: join(SHOTS, `site-${name}.png`) });
  await page.screenshot({ path: join(SHOTS, `site-${name}-fullpage.png`), fullPage: true });
  report[name] = { ...(await page.evaluate(measure)), errors, outside, fonts: await page.evaluate(() => [...document.fonts].filter((f) => f.status === "loaded").map((f) => `${f.family} ${f.weight}`)) };
  await context.close();
};
await shoot("1080p", { width: 1920, height: 1080 });
await shoot("720p", { width: 1280, height: 720 });
await shoot("390", { width: 390, height: 844 }, { isMobile: true, hasTouch: true });
await shoot("720p-reduced", { width: 1280, height: 720 }, { reducedMotion: "reduce" });
await writeFile(join(SHOTS, "site-report.json"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 1));
await browser.close();
server.close();
