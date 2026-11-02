// Round 3 capture: stills, contact sheet, frame-stepped film frames, live frame timing.
// Run: PLAYWRIGHT=<path to playwright/index.mjs> [CHROME=<chromium binary>] node mockups/fixtures/capture.mjs [stills|film|timing|all] [--page final.html] [--out shots/r3]
import { createServer } from "node:http";
import { readFile, writeFile, mkdir, rm } from "node:fs/promises";
import { extname, join, resolve } from "node:path";

const { chromium } = await import(process.env.PLAYWRIGHT);
const ROOT = resolve(new URL("..", import.meta.url).pathname);
const arg = (name, dflt) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : dflt; };
const PAGE = arg("--page", "final.html");
const OUT = join(ROOT, arg("--out", "shots/r3"));
const W = 1920, H = 1080, FPS = 30, FILM_MS = 16000;
const STILLS = [
  ["day", "scene=day"], ["block", "scene=block&t=2000"], ["argue", "scene=argue&t=4000"],
  ["argue-hold", "scene=argue&ruling=hold&t=4000"], ["held", "scene=held&t=0"], ["recovery", "scene=recovery&t=0"],
];
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".woff2": "font/woff2", ".png": "image/png", ".json": "application/json" };
const mode = process.argv[2] || "all";

// Loopback only; any other request fails the capture.
const serve = () => new Promise((ok) => {
  const server = createServer(async (req, res) => {
    const path = join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
    try { res.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream" }); res.end(await readFile(path)); }
    catch { res.writeHead(404); res.end(); }
  });
  server.listen(0, "127.0.0.1", () => ok(server));
});
const launch = () => chromium.launch({ executablePath: process.env.CHROME || undefined, args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });

async function open(browser, url, extra = {}) {
  const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, ...extra });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => !r.url().startsWith("http://127.0.0.1") && !r.url().startsWith("data:") && errors.push("network: " + r.url()));
  await page.goto(url);
  await page.waitForFunction(() => window.__ready === true && document.fonts.status === "loaded");
  return { context, page, errors };
}

async function stills(base) {
  const browser = await launch(), report = [];
  for (const [name, query] of STILLS) {
    const { context, page, errors } = await open(browser, `${base}/${PAGE}?${query}`);
    await page.waitForTimeout(200);
    const truth = await page.evaluate(() => window.__truth);
    await page.screenshot({ path: join(OUT, `${name}.png`) });
    report.push({ name, checked: truth.checked, missing: truth.missing, errors });
    await context.close();
  }
  await browser.close();
  return report;
}

async function contact(base) {
  const browser = await launch();
  const page = await (await browser.newContext({ viewport: { width: 1920, height: 800 }, deviceScaleFactor: 1 })).newPage();
  const cells = STILLS.map(([s]) => `<figure><img src="${s}.png"><figcaption>${s}</figcaption></figure>`).join("");
  const html = `<!doctype html><style>body{margin:0;background:#141210;display:grid;grid-template-columns:repeat(3,1fr);gap:24px;padding:40px;font:18px system-ui;color:#d8d3cb}figure{margin:0}img{width:100%;display:block}figcaption{margin-top:8px}</style>${cells}`;
  await writeFile(join(OUT, ".contact.html"), html);
  const rel = OUT.slice(ROOT.length);
  await page.goto(`${base}${rel}/.contact.html`);
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: join(OUT, "contact.png"), fullPage: true });
  await rm(join(OUT, ".contact.html"));
  await browser.close();
}

// Frame-stepped: the page's own timeline at each 1/30 s, so every frame is exact.
async function film(base, query = "", dir = "film") {
  const browser = await launch();
  const { context, page, errors } = await open(browser, `${base}/${PAGE}?scene=block&${query}`);
  const frames = join(OUT, dir);
  await rm(frames, { recursive: true, force: true }); await mkdir(frames, { recursive: true });
  for (let i = 0; i < (FILM_MS / 1000) * FPS; i++) {
    await page.evaluate((ms) => window.__film(ms), (i * 1000) / FPS);
    await page.screenshot({ path: join(frames, `f${String(i).padStart(4, "0")}.png`) });
  }
  await context.close(); await browser.close();
  return { frames, errors };
}

// Live rAF intervals: block from load to 1.6 s, then argue's reveals 0–3.2 s.
async function timing(base) {
  const browser = await launch();
  const { context, page } = await open(browser, `${base}/${PAGE}?scene=block`);
  const sample = (ms) => page.evaluate((ms) => new Promise((done) => {
    const ts = []; const t0 = performance.now();
    const f = (t) => { ts.push(t); t - t0 < ms ? requestAnimationFrame(f) : done(ts.slice(1).map((x, i) => x - ts[i])); };
    requestAnimationFrame(f);
  }), ms);
  const block = await sample(1600);
  await page.keyboard.press("a");
  const argue = await sample(3200);
  const ua = await page.evaluate(() => navigator.userAgent);
  const gl = await page.evaluate(() => { const c = document.createElement("canvas").getContext("webgl"); const e = c && c.getExtension("WEBGL_debug_renderer_info"); return e ? c.getParameter(e.UNMASKED_RENDERER_WEBGL) : "n/a"; });
  await context.close(); await browser.close();
  const stats = (xs) => { const s = [...xs].sort((a, b) => a - b); const q = (p) => s[Math.min(s.length - 1, Math.floor(p * s.length))]; return { frames: s.length, median: q(0.5), p95: q(0.95), max: s[s.length - 1], over20: s.filter((x) => x > 20).length }; };
  return { ua, gl, block: stats(block), argue: stats(argue) };
}

await mkdir(OUT, { recursive: true });
const server = await serve();
const base = `http://127.0.0.1:${server.address().port}`;
const result = {};
if (mode === "stills" || mode === "all") { result.stills = await stills(base); await contact(base); }
if (mode === "film" || mode === "all") result.film = await film(base);
if (mode === "timing" || mode === "all") result.timing = await timing(base);
if (mode === "clip") result.clip = await film(base, arg("--query", ""), arg("--dir", "clip"));
server.close();
console.log(JSON.stringify(result, null, 2));
