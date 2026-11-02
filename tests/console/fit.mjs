// Opens a console page at one size and prints how far it runs: {height, width, verifyRight, hidden} in CSS px.
// fit <url> <width> <height>. Driven by test_argue_held_fit.py.
const { chromium } = await import(process.env.PLAYWRIGHT);
const [url, width, height] = process.argv.slice(2);

// The page's full size, and the right edge of the furthest thing in its verify row.
function extent() {
  const page = document.documentElement;
  const rights = [...document.querySelectorAll(".verify, .verify *")].map((n) => n.getBoundingClientRect().right);
  // How much of a column is scrolled out of sight inside it.
  const hidden = Math.max(0, ...[...document.querySelectorAll(".exchange, .rail")].map((n) => n.scrollHeight - n.clientHeight));
  return { height: page.scrollHeight, width: page.scrollWidth, verifyRight: Math.max(...rights), hidden };
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: Number(width), height: Number(height) }, reducedMotion: "reduce" });
const page = await context.newPage();
await page.goto(url, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);
console.log(JSON.stringify(await page.evaluate(extent)));
await browser.close();
