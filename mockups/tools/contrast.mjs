// Text contrast against the rendered ground: text hidden, background sampled under each text box.
// Run: PLAYWRIGHT=<path> node mockups/tools/contrast.mjs > report.json ; python3 mockups/tools/contrast.py
import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { extname, join, resolve } from "node:path";
const { chromium } = await import(process.env.PLAYWRIGHT);
const ROOT = resolve(new URL("..", import.meta.url).pathname), OUT = process.argv[2];
const SCENES = [["day", 3000], ["typing", 2300], ["block", 2600], ["argue", 1800], ["held", 1600], ["miss", 2800]];
const T = { ".html": "text/html", ".js": "text/javascript", ".woff2": "font/woff2" };
const server = createServer(async (q, r) => { try { const p = join(ROOT, decodeURIComponent(new URL(q.url, "http://x").pathname)); r.writeHead(200, { "content-type": T[extname(p)] || "x" }); r.end(await readFile(p)); } catch { r.writeHead(404); r.end(); } });
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const browser = await chromium.launch({ args: ["--use-angle=metal"] });
const all = [];
for (const [scene, t] of SCENES) {
  const page = await (await browser.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
  await page.goto(`http://127.0.0.1:${server.address().port}/final.html?scene=${scene}&t=${t}`);
  await page.waitForFunction(() => window.__ready); await page.waitForTimeout(300);
  const boxes = await page.evaluate(() => {
    const c = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
    const rgb = (col) => { c.clearRect(0, 0, 1, 1); c.fillStyle = col; c.fillRect(0, 0, 1, 1); return [...c.getImageData(0, 0, 1, 1).data].slice(0, 3); };
    const out = [];
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walk.nextNode()) {
      const n = walk.currentNode, el = n.parentElement;
      if (!n.textContent.trim() || !el || el.closest(".p-label")) continue;
      const cs = getComputedStyle(el); if (cs.visibility === "hidden" || el.checkVisibility && !el.checkVisibility({ opacityProperty: true })) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const b of r.getClientRects()) if (b.width > 2 && b.height > 2) out.push({ text: n.textContent.trim().slice(0, 40), color: rgb(cs.color), size: parseFloat(cs.fontSize), weight: cs.fontWeight, box: [b.left, b.top, b.width, b.height] });
    }
    return out;
  });
  await page.addStyleTag({ content: "*{color:transparent!important;text-decoration-color:transparent!important;caret-color:transparent!important} kbd,.tag,.btn,.cmd code{border-color:transparent!important} .thread{display:none!important}" });
  await page.waitForTimeout(100);
  const shot = join(OUT, `bg-${scene}.png`);
  await page.screenshot({ path: shot });
  all.push({ scene, shot, boxes });
  await page.close();
}
await writeFile(join(OUT, "contrast.json"), JSON.stringify(all));
await browser.close(); server.close();
