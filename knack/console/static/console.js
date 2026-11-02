// The gold thread and the copy button. Content never waits on this file; motion.js animates what it draws.
const SVG = "http://www.w3.org/2000/svg";
const $ = (selector) => document.querySelector(selector);

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

function thread() {
  // Drawn whole and still; returns its two segments, or null when there is nothing to link.
  document.querySelector(".thread")?.remove();
  const p = threadPoints();
  if (!p) return null;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "thread");
  svg.setAttribute("aria-hidden", "true");
  $(".verdict").append(svg);
  const dark = segment(svg, "on-dark", `M${p.x} ${p.from}V${p.y}H${p.edge}`);
  const light = segment(svg, "on-paper", `M${p.edge} ${p.y}H${p.to}`);
  return { dark, light };
}

function copy() {
  // The argue command, copied as shown; the label confirms, then returns.
  document.querySelectorAll("[data-copy], [data-copy-text]").forEach((button) => {
    button.addEventListener("click", async () => {
      const text = button.dataset.copyText ?? document.getElementById(button.dataset.copy).textContent;
      const label = (button.dataset.label ??= button.textContent);
      await navigator.clipboard?.writeText(text);
      button.textContent = "Copied";
      setTimeout(() => { button.textContent = label; }, 1600);
    });
  });
}

function start() {
  copy();
  if (!$(".verdict")) return;
  // Measured before any arrival frame applies, then handed to motion.js to animate.
  document.fonts.ready.then(() => document.dispatchEvent(new CustomEvent("knack:thread", { detail: thread() })));
  addEventListener("resize", () => thread());
}

start();
