// The held screen, bound from the frozen fixtures only; a missing value renders "<label> not recorded".
const K = window.KNACK || {}, B = window.BLOCK || {};
const Q = new URLSearchParams(location.search);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const SVG = "http://www.w3.org/2000/svg";
// One move on this screen: the empty answer's outline draws once, like a pen, then stays.
const DRAW = { at: 400, ms: 900 };
const TICKED = /`([^`]+)`/;
const $ = (id) => document.getElementById(id);

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const gap = (label) => `<span class="gap">${esc(label)} not recorded</span>`;
const has = (v) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length);
const tail = (path, parts = 3) => path.split("/").slice(-parts).join("/");
const month = (d) => d.toLocaleString("en", { month: "short", timeZone: "UTC" });
const day = (iso) => { const d = new Date(iso); return `${month(d)} ${d.getUTCDate()} ${d.getUTCFullYear()}`; };
const stamp = (iso) => `${day(iso)}, ${new Date(iso).toISOString().slice(11, 19)} UTC`;

const outcome = Q.get("outcome") || "escalate";
const ruling = outcome === "escalate" ? K.escalate : null;
const root = K.root, where = B.where || {}, rows = B.attempted?.rows || [];
const prNumber = root?.source_url?.match(/\/pull\/(\d+)/)?.[1];
const pr = prNumber ? `#${prNumber}` : null;

function linkedNames() {
  // The quote's code spans that the matched code spells: the gold link's two ends.
  const matched = (B.attempted?.matched || []).map((m) => m.text).join(" ");
  const ticked = fullQuote().join(" ").split(TICKED).filter((_, i) => i % 2);
  return [...new Set(ticked.filter((name) => matched.includes(name)))].sort((a, b) => b.length - a.length);
}

function marked(text, names) {
  if (!names.length) return esc(text);
  const pattern = new RegExp(`(${names.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`);
  return text.split(pattern).map((p, i) => (i % 2 ? `<mark>${esc(p)}</mark>` : esc(p))).join("");
}

function spoken(text, linked) {
  return text.split(TICKED).map((p, i) => {
    if (!(i % 2)) return esc(p);
    const code = `<code>${esc(p)}</code>`;
    return linked.includes(p) ? `<mark>${code}</mark>` : code;
  }).join("");
}

function fullQuote() {
  // The full verbatim paragraph: every sentence the fixtures hold.
  const q = B.quote || {};
  const said = [...(q.sentences || []), ...(has(q.not_recorded) ? [q.not_recorded] : [])];
  return said.length ? said : root?.quote ? [root.quote] : [];
}

function modelName(id) {
  return id === K.spark?.model ? "Muse Spark" : id === K.spark_open?.model ? "Muse Spark Open" : null;
}

function bar() {
  const branch = has(where.branch) ? esc(where.branch) : gap("Branch");
  $("where").innerHTML = has(where.file) ? `${esc(where.repo)} <i>/</i> ${branch} <i>/</i> <b>${esc(tail(where.file))}</b>` : gap("File");
  $("when").innerHTML = ruling
    ? `<code>${esc(ruling.receipt_hash.slice(0, 12))}</code> <time>${esc(stamp(ruling.time))}</time>`
    : gap("Ruling");
}

function blocked() {
  // These lines are the block fixture's; its receipt is named here because the ruling's receipt differs.
  const hit = rows.filter((r) => r.kind === "add" && (where.lines || []).includes(r.new));
  $("from").innerHTML = has(B.proof?.receipt) ? `Blocked, receipt <code>${esc(B.proof.receipt.slice(0, 8))}</code>` : gap("Block receipt");
  $("code").innerHTML = hit.length
    ? hit.map((r) => `<div class="line"><span class="n">${r.new}</span><span class="sign">+</span><code>${marked(r.code, linkedNames())}</code></div>`).join("")
    : `<p class="path">${gap("The blocked lines")}</p>`;
}

function note() {
  const said = fullQuote();
  if (!said.length) return ($("note").innerHTML = gap("The decision"));
  const person = B.person || {};
  const who = has(person.name) ? `<b>${esc(person.name)}</b>` : gap("Decider");
  const merged = has(person.approved_by) ? `merged by ${esc(person.approved_by)}` : gap("Merged by");
  const when = has(root?.merged_at) ? `<span class="nowrap">${esc(day(root.merged_at))}</span>` : gap("Merge date");
  const link = pr ? `<a href="${esc(root.source_url)}">${esc(pr)}</a>` : gap("PR");
  const cited = ruling?.cited_quotes || [];
  const sentences = said.map((t) => (cited.includes(t) ? `<span class="cited">${spoken(t, linkedNames())}</span>` : spoken(t, linkedNames())));
  $("note").innerHTML = `<blockquote cite="${esc(root?.source_url || "")}"><p>“${sentences.join(" ")}”</p></blockquote>`
    + `<figcaption>${[who, merged, when, link].join(" · ")}</figcaption>`;
}

function reply() {
  const said = has(ruling?.objection) ? `<p>“${esc(ruling.objection)}”</p>` : `<p>${gap("The objection")}</p>`;
  const agent = has(ruling?.agent) ? `<b>${esc(ruling.agent)}</b>, the agent, objected` : `<b>The agent</b> objected · ${gap("Agent name")}`;
  $("reply").innerHTML = `<figcaption class="who">${agent}</figcaption><blockquote>${said}</blockquote>`;
}

function rulingCard() {
  // The tool's words stay dark; the cited sentence is already set in full ink in the note above.
  if (!ruling) return ($("ruling").innerHTML = gap("The ruling"));
  const name = modelName(ruling.model) || esc(ruling.model);
  const said = fullQuote(), at = (ruling.cited_quotes || []).map((q) => said.indexOf(q)).filter((i) => i >= 0);
  const which = at.length === 1 && said.length > 1 ? `, citing sentence ${at[0] + 1} of ${said.length} in ${esc(pr || "the record")}` : "";
  const done = { escalate: "escalated", hold: "held" }[ruling.decision];
  const decision = done ? `<b>${done}</b>` : has(ruling.decision) ? `ruled <b>${esc(ruling.decision)}</b>` : gap("Decision");
  const words = has(ruling.reply) ? `<p class="only">“${esc(ruling.reply)}”</p>` : `<p class="only">${gap("Reply")}</p>`;
  $("ruling").innerHTML = `<figcaption class="who"><b>${name}</b> ${decision}${which}:</figcaption>${words}`;
}

function command() {
  const receipt = ruling?.receipt_hash, shape = K.readme?.resolve;
  if (!receipt || !shape?.includes("allow|retire")) return ($("choices").innerHTML = `<li>${gap("Resolve command")}</li>`);
  // The README's command shown once, as the README writes it; each Copy takes one runnable form with the full receipt.
  const run = (verb) => `${shape.replace("<receipt>", receipt).replace("allow|retire", verb)} "…"`;
  const does = { allow: "lets this exact edit through.", retire: "drops the decision’s rule." };
  $("well").innerHTML = `<code>${esc(shape.replace("<receipt>", receipt)).replace(/ --reason$/, "")} <span class="nowrap">--reason "…"</span></code>`;
  $("choices").innerHTML = ["allow", "retire"].map((verb) => `<li><button type="button" class="copy-paper" data-copy-text="${esc(run(verb))}" aria-live="polite" aria-label="Copy the ${verb} command">Copy <code>${verb}</code></button>`
    + `<p>${does[verb]}</p></li>`).join("");
}

function answeredBy() {
  // Exactly the models on this ruling's trace; any other model is a gap, not a claim.
  const host = ruling?.model === K.spark?.model ? K.spark.host : ruling?.model === K.spark_open?.model ? K.spark_open.host : null;
  const seen = ruling ? `<li><b>${modelName(ruling.model) || esc(ruling.model)}</b> <code>${esc(ruling.model)}</code><br><span>at ${host ? esc(host) : gap("Host")}, from the recorded quote</span></li>` : `<li>${gap("Model")}</li>`;
  const block = has(B.proof?.scan) ? `<li><span>The block itself ran no model: ${esc(B.proof.scan)}, <span class="nowrap">${esc(B.proof.verdict_ms)}&#8239;ms</span>.</span></li>` : "";
  $("models").innerHTML = seen + block;
}

function verify() {
  const hash = ruling?.receipt_hash, check = "knack receipts verify";
  const receipt = hash ? `<p><span>Receipt <code>${esc(hash.slice(0, 8))}</code></span>${copyButton(hash)}</p>` : `<p>${gap("Receipt")}</p>`;
  const result = has(K.receipts_verify) ? `<span>${esc(K.receipts_verify)}</span>` : gap("Result");
  const label = has(root?.status) ? `decision ${esc(root.status.toLowerCase())}${root.seeded ? ", seeded" : ""}` : gap("Decision");
  const rule = `<p>Rule ${has(where.rule) ? esc(where.rule) : gap("Rule")} · ${label}</p>`;
  $("checks").innerHTML = receipt + `<p><code>${check}</code>${copyButton(check)}${result}</p>` + rule;
}

function copyButton(text) {
  return `<button type="button" class="copy" data-copy-text="${esc(text)}" aria-live="polite">Copy</button>`;
}

function copies() {
  document.querySelectorAll("[data-copy-text]").forEach((button) => button.addEventListener("click", async () => {
    await navigator.clipboard?.writeText(button.dataset.copyText);
    button.textContent = "Copied";
    setTimeout(() => { button.textContent = "Copy"; }, 1600);
  }));
}

function outline(animate) {
  // A dashed rectangle revealed by a solid stroke travelling once around it; the CSS border is the no-script fallback.
  // Sized from the border the browser actually laid out, so the stroke sits exactly where the CSS border was.
  const box = $("unanswered"), bw = parseFloat(getComputedStyle(box).borderTopWidth), w = box.offsetWidth, h = box.offsetHeight;
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize), r = `x="${bw / 2}" y="${bw / 2}" width="${w - bw}" height="${h - bw}"`;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("aria-hidden", "true");
  Object.assign(svg.style, { left: `${-bw}px`, top: `${-bw}px`, width: `${w}px`, height: `${h}px` });
  svg.innerHTML = `<defs><mask id="pen" maskUnits="userSpaceOnUse"><rect class="pen" ${r} fill="none" stroke="#fff" stroke-width="${bw * 4}"/></mask></defs>`
    + `<rect class="dash" ${r} rx="${rem * 0.125}" stroke-width="${bw}" stroke-dasharray="${rem * 0.5} ${rem * 0.375}" mask="url(#pen)"/>`;
  box.querySelector("svg")?.remove();
  box.append(svg);
  box.classList.add("drawn");
  if (animate) draw(svg.querySelector(".pen"), 2 * (w + h - 2 * bw));
}

function draw(pen, length) {
  pen.style.strokeDasharray = `${length} ${length}`;
  pen.animate([{ strokeDashoffset: length }, { strokeDashoffset: 0 }], { delay: DRAW.at, duration: DRAW.ms, easing: "linear", fill: "backwards" });
}

function freeze(ms) {
  document.getAnimations().forEach((a) => { a.pause(); a.currentTime = ms; });
}

[bar, blocked, note, reply, rulingCard, command, answeredBy, verify, copies].forEach((step) => step());
document.fonts.ready.then(() => {
  outline(!REDUCED);
  addEventListener("resize", () => outline(false));
  if (Q.has("t")) freeze(Number(Q.get("t")));
  window.__ready = true;
});
