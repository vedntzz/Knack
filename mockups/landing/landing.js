// The landing page, bound from scenes.js, block.js and readme.js only; a missing value renders "<label> not recorded".
const K = window.KNACK || {}, B = window.BLOCK || {}, R = window.README || {};
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const T = new URLSearchParams(location.search).has("t") ? Number(new URLSearchParams(location.search).get("t")) : null;
const TICKED = /`([^`]+)`/;
const $ = (id) => document.getElementById(id);

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const gap = (label) => `<span class="gap">${esc(label)} not recorded</span>`;
const has = (v) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length);
const nowrap = (s) => `<span class="nowrap">${s}</span>`;
const day = (iso) => { const d = new Date(iso); return `${d.toLocaleString("en", { month: "short", timeZone: "UTC" })} ${d.getUTCDate()} ${d.getUTCFullYear()}`; };

const proof = B.proof || {}, grid = proof.grid || K.grid || {}, root = K.root || {};
const gates = grid.gates || [], passed = gates.filter((g) => grid.cells?.[g] === "PASS");
const pr = root.source_url?.match(/\/pull\/(\d+)/)?.[1];
const REPRODUCE = K.readme?.verify, RECEIPTS = "knack receipts verify";

function copyButton(text, label) {
  return `<button type="button" class="copy" data-copy-text="${esc(text)}" aria-live="polite" aria-label="Copy ${esc(label || text)}">Copy</button>`;
}

function command(text, label) {
  return text ? `<p class="well"><code>${esc(text)}</code>${copyButton(text, label)}</p>` : `<p class="well">${gap(label || "Command")}</p>`;
}

function lines(text, label) {
  // A multi-line command, one line per README line; Copy takes all of it.
  return text ? `<p class="well"><code>${text.split("\n").map(esc).join("<br>")}</code>${copyButton(text, label)}</p>` : `<p class="well">${gap(label)}</p>`;
}

function repoLink() {
  return has(R.repo) ? `<a href="${esc(R.repo)}">${esc(R.repo)}</a>` : gap("Repo link");
}

function hero() {
  $("act").innerHTML = `<span>Reproduce every number on this page:</span>${command(REPRODUCE, "Reproduce command")}`;
  // The capture is its own run; its receipt is named so it is never read as block.js's receipt.
  $("shot-caption").innerHTML = `The block page as served, from its own demo run (receipt <code>5e8a44648bd0</code>, as the capture shows). The figures below come from the recorded block, receipt <code>${esc((proof.receipt || "").slice(0, 12))}</code>.`;
}

function spoken(text, linked) {
  return text.split(TICKED).map((p, i) => (i % 2 ? (linked.includes(p) ? `<mark><code>${esc(p)}</code></mark>` : `<code>${esc(p)}</code>`) : esc(p))).join("");
}

function linkedNames() {
  const matched = (B.attempted?.matched || []).map((m) => m.text).join(" ");
  return (root.quote || "").split(TICKED).filter((_, i) => i % 2).filter((n) => matched.includes(n));
}

function read() {
  // The root's recorded quote, complete as the root holds it, on paper because a person wrote it.
  const who = has(B.person?.name) ? `<b>${esc(B.person.name)}</b>` : gap("Author");
  const link = pr ? `<a href="${esc(root.source_url)}">#${esc(pr)}</a>` : gap("PR");
  const when = has(root.merged_at) ? nowrap(`merged ${esc(day(root.merged_at))}`) : gap("Merge date");
  $("read").innerHTML = has(root.quote)
    ? `<figure class="note paper"><blockquote cite="${esc(root.source_url || "")}"><p>“${spoken(root.quote, linkedNames())}”</p></blockquote><figcaption>${who} · ${link} · ${when}</figcaption></figure>`
    : gap("A quote");
}

function prove() {
  const rule = has(B.where?.rule) ? `<code>${esc(B.where.rule)}</code>` : gap("Rule");
  const list = gates.map((g) => `<li class="${grid.cells?.[g] === "PASS" ? "" : "gap"}">${esc(g)}</li>`).join("");
  const when = has(grid.evidence) ? `<p class="small">Stored by <code>${esc(grid.evidence.replace(/ \d{4}-\d\d-\d\d$/, ""))}</code> on ${esc(day(grid.evidence.match(/\d{4}-\d\d-\d\d/)?.[0] || ""))}.</p>` : "";
  $("prove").innerHTML = gates.length
    ? `<p>Rule ${rule} passed <b>${passed.length} of ${gates.length}</b> gates before it could block:</p><ul class="gates">${list}</ul>${when}`
    : gap("Gates");
}

function stop() {
  const names = linkedNames();
  const rows = (B.attempted?.rows || []).filter((r) => r.kind === "add" && (B.where?.lines || []).includes(r.new));
  const marked = (code) => names.reduce((s, n) => s.replace(esc(n), `<mark>${esc(n)}</mark>`), esc(code));
  const code = rows.map((r) => `<div class="line"><span class="n">${r.new}</span><span class="sign">+</span><code>${marked(r.code.trim())}</code></div>`).join("");
  const time = has(proof.verdict_ms) ? `${nowrap(`${esc(proof.verdict_ms)}&#8239;ms`)} to decide, by ${esc(proof.scan)}. ${nowrap(esc(proof.no_model || ""))}` : gap("Timing");
  $("stop").innerHTML = `<p class="stamp"><span class="seal">Blocked</span><span>${rows.length ? `lines ${rows[0].new}–${rows.at(-1).new}` : ""}</span></p>`
    + `<div class="blocked"><div class="code">${code || gap("The blocked lines")}</div></div><p>${time}</p>`;
}

function modelRow(name, where, job, trace) {
  return `<tr><th scope="row">${name}</th><td>${where}</td><td>${job}</td><td>${trace}</td></tr>`;
}

function sparkTraces() {
  // Every place the fixtures show Spark at work, counted, never assumed.
  const id = K.spark?.model, seen = [];
  if (K.hold?.model === id) seen.push("ruled <b>hold</b>");
  if (K.escalate?.model === id) seen.push("ruled <b>escalate</b>");
  if ((K.miss?.bar2_log || "").includes(`recompiling with ${id}`)) seen.push("recompiled fastapi-16062");
  if ((K.miss?.root?.models || []).includes(id)) seen.push("extracted fastapi-16062-1");
  return seen.length ? `${seen.join("; ")}.` : gap("A Spark trace");
}

function models() {
  const hook = has(B.where?.hook) ? `The block's trace records the <code>${esc(B.where.hook)}</code> hook on <code>${esc(B.where.tool)}</code>. ${gap("The agent's name")}.` : gap("A hook trace");
  const spark = K.spark ? `${esc(K.spark.host)}<br><code>${esc(K.spark.model)}</code>` : gap("Host");
  const open = K.spark_open ? `Baseten, ${esc(K.spark_open.host)}<br><code>${esc(K.spark_open.model)}</code>` : gap("Host");
  const block = has(proof.scan) ? `${esc(proof.no_model)} ${esc(proof.scan)}, ${nowrap(`${esc(proof.verdict_ms)}&#8239;ms`)} to decide, ${nowrap(`${esc(proof.round_trip_ms)}&#8239;ms`)} round trip.` : gap("Timing");
  $("model-rows").innerHTML = [
    modelRow("Muse Code", gap("Host"), "Hosts the hooks the agent's edits pass through.", hook),
    modelRow("Muse Spark", spark, "Extracts decisions from PRs, compiles them into rules, answers the agent's arguments.", sparkTraces()),
    modelRow("Muse Spark Open", open, "Corroborates rules and attacks them with fresh cases.", `${gap("Spark Open run")}. These fixtures freeze only its client's model and host.`),
    modelRow("The block itself", "On your machine", "<b>Runs no model.</b>", block),
  ].join("");
}

function figure(big, small, line) {
  return `<div class="figure"><p class="big">${big}<span>${small}</span></p><p>${line}</p></div>`;
}

function check() {
  const fp = has(K.proof?.fp) ? K.proof.fp : proof.fp, release = K.proof?.old_release || proof.old_release;
  const receipts = K.receipts_verify?.match(/^(\d+) receipts, (.*)$/);
  $("figures").innerHTML = [
    gates.length ? figure(`${passed.length}`, `/${gates.length}`, `gates passed by rule <code>${esc(B.where?.rule || "")}</code>`) : gap("Gates"),
    has(fp) ? figure(`${esc(fp)}`, "", `false alarms on Airflow’s current tree and ${nowrap(`release ${esc(release || "")}`)}`) : gap("False alarms"),
    receipts ? figure(`${esc(receipts[1])}`, "", `receipts, ${esc(receipts[2])}`) : gap("Receipts"),
  ].join("");
  $("run").innerHTML = `<div><h3>Regenerate the gates and false alarms</h3>${command(REPRODUCE, "Reproduce command")}</div>`
    + `<div><h3>Check the receipt chain</h3>${command(RECEIPTS)}</div>`
    + `<div><h3>Install</h3>${lines(R.install, "Install command")}</div>`;
}

function foot() {
  $("foot").innerHTML = `${repoLink()} · fonts IBM Plex, SIL Open Font License`;
  $("repo").innerHTML = repoLink();
}

function copies() {
  document.querySelectorAll("[data-copy-text]").forEach((button) => button.addEventListener("click", async () => {
    await navigator.clipboard?.writeText(button.dataset.copyText);
    button.textContent = "Copied";
    setTimeout(() => { button.textContent = "Copy"; }, 1600);
  }));
}

function arrive() {
  // The one move on the page: the hero picture rises in the first time it is seen, then stays.
  const shot = $("shot");
  if (REDUCED || !("IntersectionObserver" in window)) return;
  shot.classList.add("waiting");
  const seen = new IntersectionObserver(([entry]) => {
    if (!entry.isIntersecting) return;
    seen.disconnect();
    const rise = shot.animate([{ opacity: 0, transform: "translateY(1.5rem)" }, { opacity: 1, transform: "none" }], { duration: 600, easing: "cubic-bezier(0.23, 1, 0.32, 1)" });
    shot.classList.remove("waiting");
    // Capture only: ?t=<ms> holds the rise at one moment.
    if (T !== null) { rise.pause(); rise.currentTime = Math.min(T, 600); }
  }, { threshold: 0.2 });
  seen.observe(shot);
}

[hero, read, prove, stop, models, check, foot, copies].forEach((step) => step());
document.fonts.ready.then(() => {
  arrive();
  // Ready after one frame, so the observer has reported the hero's first sighting.
  requestAnimationFrame(() => requestAnimationFrame(() => { window.__ready = true; }));
});
