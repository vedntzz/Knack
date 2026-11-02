// The /events listener. A block page switches to any new deny; a ruled page follows its own block in place.
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
const RISE = [{ opacity: 0, transform: "translateY(0.75rem)" }, { opacity: 1, transform: "none" }];
const { events: url, block } = document.body.dataset;
const regions = () => [...document.querySelectorAll("[data-live]")];
// Each region's HTML as the server sent it; console.js may touch the live copy, never this.
const served = regions().map((region) => region.innerHTML);

function switchToDeny(event) {
  const next = `/verdict/${event.data}`;
  if (location.pathname !== next) location.assign(next);
}

async function follow(event) {
  // The server renders the new record; this page only swaps what differs.
  if (JSON.parse(event.data).block !== block) return;
  const response = await fetch(location.pathname, { headers: { accept: "text/html" } });
  if (response.ok) swap(new DOMParser().parseFromString(await response.text(), "text/html"));
}

function swap(next) {
  // A quiet in-place change: every differing region swaps, and only what newly arrived moves, once.
  const before = new Set([...document.querySelectorAll("[data-arrives]")].map((node) => node.outerHTML));
  const fresh = [...next.querySelectorAll("[data-live]")];
  const changed = regions().filter((region, i) => fresh[i] && replaced(region, i, fresh[i]));
  const arrived = [...document.querySelectorAll("[data-arrives]")].find((node) => !before.has(node.outerHTML));
  if (changed.length) rise(arrived ?? changed[0]);
}

function replaced(region, i, fresh) {
  if (served[i] === fresh.innerHTML) return false;
  served[i] = fresh.innerHTML;
  region.replaceChildren(...fresh.childNodes);
  return true;
}

function rise(node) {
  // The one move; under prefers-reduced-motion the change simply shows.
  if (!REDUCED) node.animate(RISE, { duration: 420, easing: EASE_OUT });
}

if (url && "EventSource" in window) {
  const source = new EventSource(url);
  if (block) ["ruling", "resolution"].forEach((name) => source.addEventListener(name, follow));
  else source.addEventListener("deny", switchToDeny);
}
