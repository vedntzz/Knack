// Capture this page: PLAYWRIGHT=<playwright/index.mjs> node mockups/held/capture.mjs  → mockups/shots/held/
process.argv.splice(2, Infinity, "held", "outcome=escalate", "0,400,900,1400");
await import("../tools/capture_page.mjs");
