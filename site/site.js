// The landing page's only script: Copy on every command, and the one move, the block page rising in once.
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

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

function rise(shot) {
  shot.classList.remove("waiting");
  shot.animate([{ opacity: 0, transform: "translateY(1.5rem)" }, { opacity: 1, transform: "none" }], { duration: 600, easing: "cubic-bezier(0.23, 1, 0.32, 1)" });
}

function arrive() {
  // The hero picture rises the first time it is seen, then stays; without script or with reduced motion it is simply there.
  const shot = document.getElementById("shot");
  if (REDUCED || !("IntersectionObserver" in window)) return;
  shot.classList.add("waiting");
  const seen = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) { seen.disconnect(); rise(shot); } }, { threshold: 0.2 });
  seen.observe(shot);
}

document.querySelectorAll("[data-copy-text]").forEach(wireCopy);
arrive();
