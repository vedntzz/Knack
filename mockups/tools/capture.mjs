// Capture: stills of every scene at a fixed t, a contact sheet, a 12 s video, and frame timing of the arrival.
// Run: PLAYWRIGHT=<path to playwright/index.mjs> node mockups/tools/capture.mjs [stills|video|timing|all] [--software]
import { createServer } from "node:http";
import { readFile, writeFile, mkdir, rename, readdir, rm } from "node:fs/promises";
import { extname, join, resolve } from "node:path";

const { chromium } = await import(process.env.PLAYWRIGHT);
const ROOT = resolve(new URL("..", import.meta.url).pathname);
const SHOTS = join(ROOT, "shots");
const W = 1920, H = 1080;
const SCENES = [["day", 3000], ["typing", 2300], ["block", 2600], ["argue", 1800], ["held", 1600], ["miss", 2800]];
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".woff2": "font/woff2", ".png": "image/png", ".json": "application/json" };
const mode = process.argv[2] || "all", software = process.argv.includes("--software");

// A loopback server so fonts load the same way they would from any static host; nothing leaves the machine.
const serve = () => new Promise((ok) => {
  const server = createServer(async (req, res) => {
    const path = join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
    try { res.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream" }); res.end(await readFile(path)); }
    catch { res.writeHead(404); res.end(); }
  });
  server.listen(0, "127.0.0.1", () => ok(server));
});

const launch = () => chromium.launch({ args: software ? ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] : ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"] });

const open = async (browser, url, extra = {}) => {
  const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, ...extra });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => !r.url().startsWith("http://127.0.0.1") && !r.url().startsWith("data:") && errors.push("network: " + r.url()));
  await page.goto(url);
  await page.waitForFunction(() => window.__ready === true && document.fonts.status === "loaded");
  return { context, page, errors };
};

const stills = async (base) => {
  const browser = await launch();
  const report = [];
  for (const [scene, t] of SCENES) {
    const { context, page, errors } = await open(browser, `${base}/final.html?scene=${scene}&t=${t}`);
    await page.waitForTimeout(300);
    const truth = await page.evaluate(() => window.__truth);
    const fonts = await page.evaluate(() => ["Gambetta", "Switzer", "Geist Mono"].map((f) => [f, document.fonts.check(`18px "${f}"`)]));
    await page.screenshot({ path: join(SHOTS, `${scene}.png`) });
    report.push({ scene, t, truth, fonts, errors });
    await context.close();
  }
  await browser.close();
  return report;
};

const contact = async (base) => {
  const browser = await launch();
  const page = await (await browser.newContext({ viewport: { width: 1920, height: 760 }, deviceScaleFactor: 1 })).newPage();
  const cells = SCENES.map(([s]) => `<figure><img src="shots/${s}.png"><figcaption>${s}</figcaption></figure>`).join("");
  const html = `<!doctype html><style>body{margin:0;background:#0b0f12;display:grid;grid-template-columns:repeat(3,1fr);gap:24px;padding:40px;font:16px system-ui;color:#cfcac0}figure{margin:0}img{width:100%;display:block;border-radius:6px}figcaption{margin-top:8px}</style>${cells}`;
  await writeFile(join(ROOT, ".contact.html"), html);
  await page.goto(`${base}/.contact.html`);
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: join(SHOTS, "contact.png"), fullPage: true });
  await rm(join(ROOT, ".contact.html"));
  await browser.close();
};

// 12 s, live: typing from its first keystroke, the arrival, then A to argue.
const video = async (base) => {
  const browser = await launch();
  const dir = join(SHOTS, ".video");
  const { context, page } = await open(browser, `${base}/final.html?scene=typing`, { recordVideo: { dir, size: { width: W, height: H } } });
  const t0 = Date.now();
  await page.waitForFunction(() => document.documentElement.dataset.scene === "block");
  await page.waitForTimeout(3300);
  await page.keyboard.press("a");
  await page.waitForTimeout(Math.max(0, 12000 - (Date.now() - t0)));
  await context.close();
  const [file] = await readdir(dir);
  await rename(join(dir, file), join(SHOTS, "typing-block-argue.webm"));
  await rm(dir, { recursive: true });
  await browser.close();
};

// rAF intervals across the arrival, from the moment the block lands to 2.6 s later.
const timing = async (base) => {
  const browser = await launch();
  const { context, page } = await open(browser, `${base}/final.html?scene=typing`);
  await page.waitForFunction(() => document.documentElement.dataset.scene === "block");
  await page.waitForTimeout(2800);
  const out = await page.evaluate(() => {
    const f = window.__frames.filter(([, s]) => s === "block").map(([t]) => t), start = f[0];
    const d = f.slice(1).map((t, i) => t - f[i]).filter((_, i) => f[i + 1] - start <= 2600).sort((a, b) => a - b);
    const q = (p) => d[Math.min(d.length - 1, Math.floor(p * d.length))];
    return { frames: d.length, median_ms: q(0.5), p95_ms: q(0.95), max_ms: d[d.length - 1], over_20ms: d.filter((x) => x > 20).length, renderer: window.Ground.stats.renderer, software: window.Ground.stats.software, dpr: devicePixelRatio, window: `${innerWidth}x${innerHeight}`, ua: navigator.userAgent };
  });
  out.browser = browser.version();
  await context.close();
  await browser.close();
  return out;
};

const server = await serve();
const base = `http://127.0.0.1:${server.address().port}`;
await mkdir(SHOTS, { recursive: true });
const result = {};
if (mode === "stills" || mode === "all") { result.stills = await stills(base); await contact(base); }
if (mode === "video" || mode === "all") await video(base);
if (mode === "timing" || mode === "all") result.timing = await timing(base);
console.log(JSON.stringify(result, null, 2));
server.close();
