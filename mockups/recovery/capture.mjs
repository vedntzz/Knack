// Capture this page: PLAYWRIGHT=<playwright/index.mjs> node mockups/recovery/capture.mjs  → mockups/shots/recovery/
process.argv.splice(2, Infinity, "recovery", "case=miss", "0,500,1000,1700");
await import("../tools/capture_page.mjs");
