// The landing page's only script: Copy on every command, and one move per beat: each picture and board rises once, each figure counts up once.
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";

function copied(button) {
  button.textContent = "Copied";
  document.getElementById("status").textContent = `Copied: ${button.dataset.copyText.split("\n")[0]}`;
  setTimeout(() => { button.textContent = "Copy"; }, 1600);
}

function selectCode(button) {
  // No clipboard (an http page, an old browser): select the command so the visitor can copy it.
  const range = document.createRange();
  range.selectNodeContents(button.parentElement.querySelector("code"));
  getSelection().removeAllRanges();
  getSelection().addRange(range);
}

function wireCopy(button) {
  button.hidden = false;
  button.addEventListener("click", () => {
    const write = navigator.clipboard?.writeText(button.dataset.copyText);
    (write || Promise.reject()).then(() => copied(button), () => selectCode(button));
  });
}

function rise(node) {
  node.classList.remove("waiting");
  node.animate([{ opacity: 0, transform: "translateY(1.5rem)" }, { opacity: 1, transform: "none" }], { duration: 600, easing: EASE_OUT });
}

function countUp(node) {
  // From zero to the written figure, once, landing exactly on the text the page was served with.
  const final = node.textContent, target = Number(final), places = (final.split(".")[1] || "").length;
  const start = performance.now(), step = (now) => {
    const t = Math.min(1, (now - start) / 900), eased = 1 - (1 - t) ** 3;
    node.textContent = t < 1 ? (target * eased).toFixed(places) : final;
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function once(nodes, move, hide) {
  // Each node makes its move the first time it is seen, then stays; without script or with reduced motion it is simply there.
  if (REDUCED || !("IntersectionObserver" in window)) return;
  const seen = new IntersectionObserver((entries) => entries.filter((e) => e.isIntersecting).forEach((e) => { seen.unobserve(e.target); move(e.target); }), { threshold: 0.2 });
  nodes.forEach((node) => { if (hide) node.classList.add("waiting"); seen.observe(node); });
}

document.querySelectorAll("[data-copy-text]").forEach(wireCopy);
once([document.getElementById("shot"), ...document.querySelectorAll("[data-arrive]")], rise, true);
once([...document.querySelectorAll("[data-count]")], countUp, false);
