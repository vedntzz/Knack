// Prints how the first match of a selector is painted: {color, ink, background, paper} as computed rgb.
// paint <url> <width> <height> <selector>. Driven by test_day_note_paint.py.
const { chromium } = await import(process.env.PLAYWRIGHT);
const [url, width, height, selector] = process.argv.slice(2);

// The text colour, the first opaque background behind it, and the two tokens resolved the same way.
function paint(selector) {
  const opaque = (c) => c !== "rgba(0, 0, 0, 0)" && c !== "transparent";
  const behind = (el) => { for (; el; el = el.parentElement) { const c = getComputedStyle(el).backgroundColor; if (opaque(c)) return c; } return ""; };
  const token = (name) => { const probe = document.body.appendChild(document.createElement("i")); probe.style.color = `var(${name})`; const c = getComputedStyle(probe).color; probe.remove(); return c; };
  const node = document.querySelector(selector);
  return { color: getComputedStyle(node).color, ink: token("--ink"), background: behind(node), paper: token("--paper") };
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: Number(width), height: Number(height) }, reducedMotion: "reduce" });
const page = await context.newPage();
await page.goto(url, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);
console.log(JSON.stringify(await page.evaluate(paint, selector)));
await browser.close();
