// Capture the block page for the one-story receipt, as served by the README's console command, for site/: 1080p, and 390 at 2x.
// Run with the console up: PLAYWRIGHT=<playwright/index.mjs> node mockups/tools/capture_block.mjs
import { resolve } from "node:path";

const { chromium } = await import(process.env.PLAYWRIGHT);
const REPO = resolve(new URL("../..", import.meta.url).pathname);
const BLOCK = "http://127.0.0.1:7655/verdict/0e7ab608386631d65da47ec1bd194f45a335f49a0a8750635fc608f6559e65a9";
const browser = await chromium.launch({ channel: process.env.CHANNEL || undefined });
// Reduced motion shows the final frame, as DESIGN.md requires. A phone gets the console's own 390 layout, at 2x.
const shoot = async (file, viewport, scale) => {
  const context = await browser.newContext({ viewport, deviceScaleFactor: scale, reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.goto(BLOCK, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${REPO}/site/${file}` });
  await context.close();
};
await shoot("block-0e7ab6083866-1080p.png", { width: 1920, height: 1080 }, 1);
await shoot("block-0e7ab6083866-390.png", { width: 390, height: 844 }, 2);
await browser.close();
