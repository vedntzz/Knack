// Shoots a console page, or counts the pixels two shots differ in. Driven by test_screenshot.py.
// shoot <url> <width> <height> <out.png>   ·   diff <a.png> <b.png> (prints the differing fraction)
import { readFile } from "node:fs/promises";

const { chromium } = await import(process.env.PLAYWRIGHT);
const [mode, ...args] = process.argv.slice(2);

// Reduced motion shows the final frame at once, so every shot is the same frame.
async function shoot(url, width, height, out) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: Number(width), height: Number(height) }, deviceScaleFactor: 1, reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.goto(url, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForSelector(".thread", { state: "attached" });
  await page.screenshot({ path: out, fullPage: true });
  await browser.close();
}

// Both images decoded by the same canvas, compared pixel by pixel.
function differing([a, b]) {
  const load = (src) => new Promise((ok) => { const img = new Image(); img.onload = () => ok(img); img.src = src; });
  const pixels = (img) => {
    const canvas = Object.assign(document.createElement("canvas"), { width: img.width, height: img.height });
    const context = canvas.getContext("2d");
    context.drawImage(img, 0, 0);
    return context.getImageData(0, 0, img.width, img.height).data;
  };
  return Promise.all([load(a), load(b)]).then(([x, y]) => {
    if (x.width !== y.width || x.height !== y.height) return 1;
    const p = pixels(x), q = pixels(y);
    let changed = 0;
    for (let i = 0; i < p.length; i += 4) changed += p[i] !== q[i] || p[i + 1] !== q[i + 1] || p[i + 2] !== q[i + 2] || p[i + 3] !== q[i + 3];
    return changed / (x.width * x.height);
  });
}

async function diff(a, b) {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const url = async (path) => `data:image/png;base64,${(await readFile(path)).toString("base64")}`;
  console.log(await page.evaluate(differing, [await url(a), await url(b)]));
  await browser.close();
}

await (mode === "shoot" ? shoot(...args) : diff(...args));
