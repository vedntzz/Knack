// The record's squares: one fade by week, the day's line on hover or focus, arrow keys between days.
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
// Week n starts at n × STEP_MS, so the 53rd ends at 52 × 7 + 220 = 584 ms: once, under 600.
const STEP_MS = 7;
const FADE_MS = 220;
// Up and down move a day; left and right a week, as the columns run.
const MOVES = { ArrowUp: -1, ArrowDown: 1, ArrowLeft: -7, ArrowRight: 7 };
const graph = document.querySelector("[data-graph]");

function fade() {
  // Opacity only: the record does not travel. Reduced motion shows the final frame.
  if (REDUCED) return;
  graph.querySelectorAll(".week").forEach((week, n) => {
    week.animate([{ opacity: 0 }, { opacity: 1 }], { delay: n * STEP_MS, duration: FADE_MS, easing: EASE_OUT, fill: "backwards" });
  });
}

function show(cell) {
  // Above the cell, kept inside the graph; it appears at once, never animated.
  const tip = graph.querySelector(".tip"), box = graph.getBoundingClientRect(), at = cell.getBoundingClientRect();
  tip.textContent = cell.getAttribute("aria-label");
  tip.hidden = false;
  const left = Math.max(0, Math.min(at.left - box.left, graph.clientWidth - tip.offsetWidth));
  tip.style.transform = `translate(${left}px, ${at.top - box.top - tip.offsetHeight - 8}px)`;
}

function hide() {
  graph.querySelector(".tip").hidden = true;
}

function move(event) {
  // One tab stop for the whole record; the arrows carry it from day to day, never past a week's ends.
  const cells = [...graph.querySelectorAll(".cell")], at = cells.indexOf(event.target), by = MOVES[event.key];
  if (at < 0 || by === undefined) return;
  event.preventDefault();
  const next = Math.abs(by) === 1 && Math.floor((at + by) / 7) !== Math.floor(at / 7) ? null : cells[at + by];
  if (next) { event.target.tabIndex = -1; next.tabIndex = 0; next.focus(); }
}

function openOnToday() {
  // On a phone the record scrolls sideways; it opens at the right end, where today is.
  graph.scrollLeft = graph.scrollWidth;
}

function listen() {
  const cellOf = (event) => event.target.closest?.(".cell");
  graph.addEventListener("pointerover", (event) => cellOf(event) && show(cellOf(event)));
  graph.addEventListener("pointerleave", hide);
  graph.addEventListener("focusin", (event) => cellOf(event) && show(cellOf(event)));
  graph.addEventListener("focusout", hide);
  graph.addEventListener("keydown", move);
}

if (graph) { openOnToday(); fade(); listen(); }
