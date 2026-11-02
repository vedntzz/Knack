// Live switch, the arrival beats, the gold thread and the copy button. Content never waits on this file.
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
// A stamp accelerates into the paper and stops dead; it is an impact, not a UI response.
const SEAL_IN = "cubic-bezier(0.5, 0, 0.75, 0)";
const SVG = "http://www.w3.org/2000/svg";
const $ = (selector) => document.querySelector(selector);

// One move per beat (ms from load), then dead still.
// The fix lands last, so the frame you remember is the human's instruction, not a number.
const BEATS = { seal: 120, note: 520, thread: 1000, figures: 1560, fix: 2160 };

function listen() {
  // A deny landing anywhere switches this tab to it.
  const url = document.body.dataset.events;
  if (!url || !("EventSource" in window)) return;
  new EventSource(url).addEventListener("deny", (event) => {
    const next = `/verdict/${event.data}`;
    if (location.pathname !== next) location.assign(next);
  });
}

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

function box(node, frame) {
  const r = node.getBoundingClientRect();
  return { left: r.left - frame.left, right: r.right - frame.left, top: r.top - frame.top, bottom: r.bottom - frame.top };
}

function threadPoints() {
  // From under the gold gutter, down the margin, along the note's top, onto the linked word.
  const main = $(".verdict"), hits = document.querySelectorAll(".line.hit"), note = $(".note"), word = $(".note mark");
  if (!main || !hits.length || !note || !word) return null;
  const frame = main.getBoundingClientRect(), last = box(hits[hits.length - 1], frame);
  // The note's linked word carries a bottom border; the thread runs into it at that height.
  const paper = box(note, frame), x = last.left + 1.5, line = word.getClientRects()[0];
  const width = parseFloat(getComputedStyle(word).borderBottomWidth), y = line.bottom - frame.top - width / 2;
  return { x, from: last.bottom, y, edge: paper.left, to: line.left - frame.left };
}

function segment(svg, cls, d) {
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("class", cls);
  path.setAttribute("d", d);
  svg.append(path);
  return path;
}

function thread(animate) {
  document.querySelector(".thread")?.remove();
  const p = threadPoints();
  if (!p) return;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "thread");
  svg.setAttribute("aria-hidden", "true");
  $(".verdict").append(svg);
  const dark = segment(svg, "on-dark", `M${p.x} ${p.from}V${p.y}H${p.edge}`);
  const light = segment(svg, "on-paper", `M${p.edge} ${p.y}H${p.to}`);
  if (animate) draw(dark, light);
}

function draw(dark, light) {
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

function copy() {
  // The argue command, copied as shown; the label confirms, then returns.
  document.querySelectorAll("[data-copy], [data-copy-text]").forEach((button) => {
    button.addEventListener("click", async () => {
      const text = button.dataset.copyText ?? document.getElementById(button.dataset.copy).textContent;
      await navigator.clipboard?.writeText(text);
      button.textContent = "Copied";
      setTimeout(() => { button.textContent = "Copy"; }, 1600);
    });
  });
}

function arrival() {
  seal();
  play($("[data-beat=figures]"), [{ opacity: 0 }, { opacity: 1 }], BEATS.figures, 160, "linear");
  arrive("[data-beat=note]", BEATS.note);
  arrive("[data-beat=fix]", BEATS.fix);
  document.querySelectorAll("[data-count]").forEach(countUp);
}

function start() {
  listen();
  copy();
  if (!$(".verdict")) return;
  const moving = !REDUCED && document.body.classList.contains("deny");
  // Measure the thread before the note's start frame moves it, so it lands on the underline.
  document.fonts.ready.then(() => { thread(moving); if (moving) arrival(); });
  addEventListener("resize", () => thread(false));
}

start();
