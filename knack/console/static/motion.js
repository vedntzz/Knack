// The arrival beats, only on a deny. Under prefers-reduced-motion nothing moves: the final frame shows.
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
// A stamp accelerates into the paper and stops dead; it is an impact, not a UI response.
const SEAL_IN = "cubic-bezier(0.5, 0, 0.75, 0)";
const $ = (selector) => document.querySelector(selector);

// One move per beat (ms from load), then dead still.
// The fix lands last, so the frame you remember is the human's instruction, not a number.
const BEATS = { seal: 120, note: 520, thread: 1000, figures: 1560, fix: 2160 };

function play(node, frames, delay, duration, easing) {
  if (node) node.animate(frames, { delay, duration, easing, fill: "backwards" });
}

function seal() {
  const frames = [{ opacity: 0, transform: "scale(1.35)" }, { opacity: 1, transform: "scale(1)" }];
  play($("[data-beat=seal]"), frames, BEATS.seal, 200, SEAL_IN);
}

function arrive(selector, at) {
  const frames = [{ opacity: 0, transform: "translateY(0.75rem)" }, { opacity: 1, transform: "none" }];
  play($(selector), frames, at, 420, EASE_OUT);
}

function draw({ dark, light }) {
  // Constant speed across both segments, like one pen stroke.
  const a = dark.getTotalLength(), b = light.getTotalLength(), total = 520;
  const split = Math.round((total * a) / (a + b));
  stroke(dark, a, BEATS.thread, split);
  stroke(light, b, BEATS.thread + split, total - split);
}

function stroke(path, length, delay, duration) {
  path.style.strokeDasharray = `${length} ${length}`;
  const frames = [{ strokeDashoffset: length }, { strokeDashoffset: 0 }];
  path.animate(frames, { delay, duration, easing: "linear", fill: "backwards" });
}

function countUp(node) {
  // Once, from zero, easing out; tabular figures keep the width still.
  const goal = Number(node.dataset.count), places = (node.dataset.count.split(".")[1] || "").length;
  const start = performance.now() + BEATS.figures, duration = 700;
  node.textContent = (0).toFixed(places);
  const tick = (now) => {
    const t = Math.min(1, Math.max(0, (now - start) / duration));
    node.textContent = (goal * (1 - Math.pow(1 - t, 3))).toFixed(places);
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function arrival() {
  seal();
  play($("[data-beat=figures]"), [{ opacity: 0 }, { opacity: 1 }], BEATS.figures, 160, "linear");
  arrive("[data-beat=note]", BEATS.note);
  arrive("[data-beat=fix]", BEATS.fix);
  document.querySelectorAll("[data-count]").forEach(countUp);
}

// console.js measures the thread first, so the note's start frame never moves it off the underline.
document.addEventListener("knack:thread", (event) => {
  if (REDUCED || !document.body.classList.contains("deny")) return;
  if (event.detail) draw(event.detail);
  arrival();
});
