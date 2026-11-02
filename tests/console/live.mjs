// Opens a ruled page, prints "ready" once it is still and listening, then waits for it to change in place.
// live <url> <selector> <text> <reduced 0|1>; prints {kept, moves, still, headline} as JSON.
const { chromium } = await import(process.env.PLAYWRIGHT);
const [url, selector, text, reduced] = process.argv.slice(2);

// Notes when the page's EventSource opens, so the test writes only after the stream listens.
function noteOpen() {
  const Source = window.EventSource;
  window.EventSource = class extends Source {
    constructor(...args) { super(...args); this.addEventListener("open", () => { window.knackOpen = true; }); }
  };
}

// Counts the animations running the moment the wanted text appears.
function watchFor([wanted, words]) {
  window.knackKept = true;
  const seen = () => [...document.querySelectorAll(wanted)].some((n) => n.textContent.includes(words));
  new MutationObserver(() => {
    if (seen() && !window.knackSeen) window.knackSeen = { moves: document.getAnimations().length };
  }).observe(document.body, { childList: true, subtree: true, characterData: true });
}

const browser = await chromium.launch();
const motion = reduced === "1" ? "reduce" : "no-preference";
const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, reducedMotion: motion });
const page = await context.newPage();
await page.addInitScript(noteOpen);
await page.goto(url, { waitUntil: "load" });
await page.waitForFunction(() => window.knackOpen && document.getAnimations().length === 0);
await page.waitForTimeout(400);
await page.evaluate(watchFor, [selector, text]);
console.log("ready");
await page.waitForFunction(() => window.knackSeen, null, { timeout: 15000 });
await page.waitForFunction(() => document.getAnimations().length === 0, null, { timeout: 5000 });
const result = await page.evaluate(() => ({
  kept: window.knackKept === true,
  moves: window.knackSeen.moves,
  still: document.getAnimations().length === 0,
  headline: document.querySelector("h1").textContent,
}));
console.log(JSON.stringify(result));
await browser.close();
