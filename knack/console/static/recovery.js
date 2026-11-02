// The timeline fills top to bottom once, then the page is still. Under prefers-reduced-motion nothing moves: the final frame shows.
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
// On-screen movement: a strong ease-in-out, about 280 ms a step, done well inside a 5 s look.
const EASE_IN_OUT = "cubic-bezier(0.77, 0, 0.175, 1)";
const FILL = { delay: 240, duration: 1680 };

function fill(track) {
  // fill: "backwards" holds the empty track through the delay; after, the CSS frame is the final one.
  const frames = [{ transform: "scaleY(0)" }, { transform: "scaleY(1)" }];
  track.animate(frames, { ...FILL, easing: EASE_IN_OUT, fill: "backwards" });
}

const track = document.querySelector("[data-fill]");
if (track && !REDUCED) fill(track);
