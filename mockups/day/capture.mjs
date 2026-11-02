// Capture this page: PLAYWRIGHT=<playwright/index.mjs> node mockups/day/capture.mjs  → mockups/shots/day/
process.argv.splice(2, Infinity, "day", "view=day", "0,150,300,600");
await import("../tools/capture_page.mjs");
