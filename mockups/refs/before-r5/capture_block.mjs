// Block capture: 1080p (1280×720 at DPR 1.5), 720p (DPR 1), truth report, and frame-stepped film frames.
// Run: PLAYWRIGHT=<playwright/index.mjs> CHROME=<chromium> node mockups/fixtures/capture_block.mjs [stills|film] [--out shots/r4]
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { extname, join, resolve } from "node:path";

const { chromium } = await import(process.env.PLAYWRIGHT);
const ROOT = resolve(new URL("..", import.meta.url).pathname);
const arg = (name, dflt) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : dflt; };
const OUT = join(ROOT, arg("--out", "shots/r4"));
const QUERY = arg("--query", "");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".woff2": "font/woff2", ".png": "image/png", ".json": "application/json" };
const mode = process.argv[2] || "stills";

const serve = () => new Promise((ok) => {
  const server = createServer(async (req, res) => {
    const path = join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
    const body = await readFile(path).catch(() => null);
    if (!body) return res.writeHead(404).end();
    res.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream" }).end(body);
  });
  server.listen(0, "127.0.0.1", () => ok(server));
});

async function open(browser, url, scale, extra = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: scale, ...extra });
  const page = await context.newPage(), errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => !r.url().startsWith("http://127.0.0.1") && !r.url().startsWith("data:") && errors.push("network: " + r.url()));
  await page.goto(url);
  await page.waitForFunction(() => window.__ready === true);
  return { context, page, errors };
}

const server = await serve(), base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined });
await mkdir(OUT, { recursive: true });
if (mode === "stills") {
  for (const [name, scale, extra] of [["block-1080p", 1.5, {}], ["block-720p", 1, {}], ["block-reduced-1080p", 1.5, { reducedMotion: "reduce" }]]) {
    const { context, page, errors } = await open(browser, `${base}/final.html?${QUERY}`, scale, extra);
    await page.waitForTimeout(2600);
    await page.screenshot({ path: join(OUT, `${name}.png`) });
    const truth = await page.evaluate(() => window.__truth);
    const overflow = await page.evaluate(() => [...document.querySelectorAll(".screen *")].filter((e) => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== "visible").map((e) => e.className).slice(0, 5));
    const bottom = await page.evaluate(() => Math.max(...[...document.querySelectorAll(".diff, .rail")].map((e) => e.getBoundingClientRect().bottom)));
    console.log(JSON.stringify({ name, checked: truth.checked, missing: truth.missing, errors, overflow, contentBottom: Math.round(bottom) }));
    await context.close();
  }
}
if (mode === "film") {
  const frames = join(OUT, "frames"), fps = 30, ms = 5000;
  await mkdir(frames, { recursive: true });
  const { context, page, errors } = await open(browser, `${base}/final.html?film=1`, 1.5);
  for (let i = 0; i < (ms / 1000) * fps; i++) {
    await page.evaluate((t) => window.__film(t), (i * 1000) / fps);
    await page.screenshot({ path: join(frames, `f${String(i).padStart(4, "0")}.png`) });
  }
  console.log(JSON.stringify({ frames: (ms / 1000) * fps, errors }));
  await context.close();
}
await browser.close();
server.close();
