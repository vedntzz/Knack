// The argue and held arrivals: each [data-at] card rises once at its beat (ms from load), then all is still.
// Under prefers-reduced-motion nothing moves; without this script every card is simply there.
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
const RISE = [{ opacity: 0, transform: "translateY(0.75rem)" }, { opacity: 1, transform: "none" }];

function arrive(node) {
  node.animate(RISE, { delay: Number(node.dataset.at), duration: 420, easing: EASE_OUT, fill: "backwards" });
}

if (!REDUCED) document.querySelectorAll("[data-at]").forEach(arrive);
