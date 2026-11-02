// Opens a console page at one size and prints how far it runs: {height, width, verifyRight, hidden, smallest} in CSS px.
// fit <url> <width> <height>. Driven by test_argue_held_fit.py.
const { chromium } = await import(process.env.PLAYWRIGHT);
const [url, width, height] = process.argv.slice(2);

// The page's full size, and the right edge of the furthest thing in its verify row.
function extent() {
  const page = document.documentElement;
  const rights = [...document.querySelectorAll(".verify, .verify *")].map((n) => n.getBoundingClientRect().right);
  // How much of a column is scrolled out of sight inside it.
  const hidden = Math.max(0, ...[...document.querySelectorAll(".exchange, .rail, .steps")].map((n) => n.scrollHeight - n.clientHeight));
  // The smallest text drawn, so a phone layout never shrinks below the type floor.
  const sizes = [...document.querySelectorAll("body *")].filter((n) => n.childNodes.length && [...n.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())).map((n) => parseFloat(getComputedStyle(n).fontSize));
  return { height: page.scrollHeight, width: page.scrollWidth, verifyRight: Math.max(...rights), hidden, smallest: Math.min(...sizes) };
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: Number(width), height: Number(height) }, reducedMotion: "reduce" });
const page = await context.newPage();
await page.goto(url, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);
console.log(JSON.stringify(await page.evaluate(extent)));
await browser.close();
