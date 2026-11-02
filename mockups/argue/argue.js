// The argue screen, bound from the frozen fixtures only; a missing value renders "<label> not recorded".
const K = window.KNACK || {}, B = window.BLOCK || {};
const Q = new URLSearchParams(location.search);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
// One move per beat (ms from load), then dead still. No stamp: the argument is not a second block.
const BEATS = { reply: 160, ruling: 760, word: 1360, fix: 2000 };
const OUTCOMES = { hold: "Hold", escalate: "Escalate" };
const TICKED = /`([^`]+)`/;
const $ = (id) => document.getElementById(id);

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const gap = (label) => `<span class="gap">${esc(label)} not recorded</span>`;
const has = (v) => v !== undefined && v !== null && v !== "";
const tail = (path, parts = 3) => path.split("/").slice(-parts).join("/");
const lines = ([a, b]) => (a === b ? `line ${a}` : `lines ${a}–${b}`);
const cap = (s) => s[0].toUpperCase() + s.slice(1);
const month = (d) => d.toLocaleString("en", { month: "short", timeZone: "UTC" });
const day = (iso) => { const d = new Date(iso); return `${month(d)} ${d.getUTCDate()} ${d.getUTCFullYear()}`; };
const clock = (iso) => new Date(iso).toISOString().slice(11, 19);
const stamp = (iso) => `${day(iso)}, ${clock(iso)} UTC`;

const outcome = Q.get("outcome") || "hold";
const ruling = OUTCOMES[outcome] ? K[outcome] : null;
const root = K.root, where = B.where || {}, rows = B.attempted?.rows || [];
const prNumber = root?.source_url?.match(/\/pull\/(\d+)/)?.[1];
const pr = prNumber ? `#${prNumber}` : null;

// The quote's code spans that the matched code spells: the gold link's two ends.
function linkedNames() {
  const matched = (B.attempted?.matched || []).map((m) => m.text).join(" ");
  const ticked = (root?.quote || "").split(TICKED).filter((_, i) => i % 2);
  return ticked.filter((name) => matched.includes(name)).sort((a, b) => b.length - a.length);
}

function marked(text, names) {
  if (!names.length) return esc(text);
  const pattern = new RegExp(`(${names.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`);
  return text.split(pattern).map((p, i) => (i % 2 ? `<mark>${esc(p)}</mark>` : esc(p))).join("");
}

function spoken(text, linked) {
  // Backticked spans become code, as GitHub rendered them; linked ones carry the gold underline.
  return text.split(TICKED).map((p, i) => {
    if (!(i % 2)) return esc(p);
    const code = `<code>${esc(p)}</code>`;
    return linked.includes(p) ? `<mark>${code}</mark>` : code;
  }).join("");
}

function bar() {
  const branch = has(where.branch) ? esc(where.branch) : gap("Branch");
  $("where").innerHTML = has(where.file)
    ? `${esc(where.repo)} <i>/</i> ${branch} <i>/</i> <b>${esc(tail(where.file))}</b>`
    : gap("File");
  $("when").innerHTML = ruling
    ? `<code>${esc(ruling.receipt_hash.slice(0, 12))}</code> <time>${esc(stamp(ruling.time))}</time>`
    : gap("Ruling");
}

function blocked() {
  const hit = rows.filter((r) => r.kind === "add" && (where.lines || []).includes(r.new));
  const names = linkedNames();
  $("path").textContent = has(where.file) ? tail(where.file, 6) : "";
  $("from").innerHTML = has(B.proof?.receipt)
    ? `Blocked, receipt <code>${esc(B.proof.receipt.slice(0, 8))}</code>`
    : gap("Block receipt");
  $("code").innerHTML = hit.length
    ? hit.map((r) => `<div class="line"><span class="n">${r.new}</span><span class="sign">+</span><code>${marked(r.code, names)}</code></div>`).join("")
    : `<p class="path">${gap("The blocked lines")}</p>`;
}

function fullQuote() {
  // The full verbatim paragraph, as the block page shows it: every sentence the fixtures hold.
  const q = B.quote || {};
  const said = [...(q.sentences || []), ...(has(q.not_recorded) ? [q.not_recorded] : [])];
  return said.length ? said : root?.quote ? [root.quote] : [];
}

function note() {
  const said = fullQuote();
  if (!said.length) return ($("note").innerHTML = gap("The decision"));
  const person = B.person || {};
  const who = has(person.name) ? `<b>${esc(person.name)}</b>` : gap("Decider");
  const merged = has(person.approved_by) ? `merged by ${esc(person.approved_by)}` : gap("Merged by");
  const when = has(root.merged_at) ? esc(day(root.merged_at)) : gap("Merge date");
  const link = pr ? `<a href="${esc(root.source_url)}">${esc(pr)}</a>` : gap("PR");
  const cited = ruling?.cited_quotes || [];
  const sentences = said.map((t) => (cited.includes(t) ? `<span class="cited">${spoken(t, linkedNames())}</span>` : spoken(t, linkedNames())));
  $("note").innerHTML = `<blockquote cite="${esc(root?.source_url || "")}"><p>“${sentences.join(" ")}”</p></blockquote>`
    + `<figcaption>${[who, merged, when, link].join(" · ")}</figcaption>`;
}

function reply() {
  const said = ruling && has(ruling.objection) ? `<p>“${esc(ruling.objection)}”</p>` : `<p>${gap("The objection")}</p>`;
  const agent = has(ruling?.agent) ? `<b>${esc(ruling.agent)}</b>, the agent, objected` : `<b>The agent</b> objected · ${gap("Agent name")}`;
  $("reply").innerHTML = `<figcaption class="who">${agent}</figcaption><blockquote>${said}</blockquote>`;
}

function modelName(id) {
  // The model the ruling names, as the client file that called it names it.
  return id === K.spark?.model ? "Muse Spark" : id === K.spark_open?.model ? "Muse Spark Open" : null;
}

function rulingNote() {
  if (!ruling) return ($("ruling").innerHTML = gap("The ruling"));
  const name = modelName(ruling.model) || esc(ruling.model);
  const cited = ruling.cited_quotes || [];
  const quotes = cited.length
    ? cited.map((q) => `<blockquote class="slip paper" cite="${esc(root?.source_url || "")}"><p>“${spoken(q, [])}”</p></blockquote>`).join("")
    : `<p class="only">${gap("A cited quote")}</p>`;
  $("ruling").innerHTML = `<figcaption class="who">${rulingLine(name, cited)}</figcaption>` + quotes + replyLine(cited);
}

function rulingLine(name, cited) {
  // Which of the human's sentences it cited, counted from the fixtures, never assumed.
  const said = fullQuote(), at = cited.map((q) => said.indexOf(q)).filter((i) => i >= 0);
  const decision = has(ruling.decision) ? `<b>${esc(ruling.decision)}</b>` : gap("Decision");
  const which = at.length === 1 && said.length > 1 ? `sentence ${at[0] + 1} of ${said.length} in ${esc(pr || "the record")}` : esc(pr || "the record");
  return `<b>${name}</b> ruled ${decision}, citing ${which}:`;
}

function replyLine(cited) {
  // The reply is shown only when it says more than the cited sentence.
  if (!has(ruling.reply)) return `<p class="only">${gap("Reply")}</p>`;
  return cited.includes(ruling.reply) ? "" : `<p class="only">“${esc(ruling.reply)}”</p>`;
}

function outcomeCard() {
  $("outcome-word").innerHTML = ruling ? OUTCOMES[outcome] : gap("Outcome");
  const asksFor = /alias/i.test(ruling?.objection || "") && /^alias/i.test(root?.rejected_alternative || "");
  const stay = has(where.lines) ? `${cap(lines([where.lines[0], where.lines.at(-1)]))} stay blocked.` : "";
  const merged = has(root?.rejected_alternative) ? ` ${esc(pr)} offered that alias and merged without it.` : "";
  $("why").innerHTML = outcome === "hold" && asksFor ? `${stay}${merged}` : has(ruling?.reply) ? esc(ruling.reply) : gap("Why");
}

function answeredBy() {
  const host = ruling?.model === K.spark?.model ? K.spark.host : ruling?.model === K.spark_open?.model ? K.spark_open.host : null;
  const model = ruling ? `<li><b>${modelName(ruling.model) || esc(ruling.model)}</b> <code>${esc(ruling.model)}</code><br><span>at ${host ? esc(host) : gap("Host")}, from the recorded quote</span></li>` : `<li>${gap("Model")}</li>`;
  const block = has(B.proof?.scan) ? `<li><span>The block itself ran no model: ${esc(B.proof.scan)}, ${esc(B.proof.verdict_ms)}&thinsp;ms.</span></li>` : "";
  $("models").innerHTML = model + block;
}

function fix() {
  if (outcome !== "hold" || !has(where.lines)) return ($("fix").innerHTML = gap("The fix"));
  $("fix").textContent = `Delete ${lines([where.lines[0], where.lines.at(-1)])}.`;
  // Lines near the match that spell a name the decision uses: already right.
  const names = (root?.decision?.match(/\blast_run_\w+/g) || []);
  const right = rows.filter((r) => r.kind === "add" && names.some((n) => r.code.includes(`"${n}"`))).map((r) => r.new);
  $("kept").innerHTML = right.length ? `${cap(lines([right[0], right.at(-1)]))} already use the right names.` : gap("Lines with the right names");
}

function verify() {
  const hash = ruling?.receipt_hash, command = "knack receipts verify";
  const receipt = hash ? `<p><span>Receipt <code>${esc(hash.slice(0, 8))}</code></span>${copyButton(hash)}</p>` : `<p>${gap("Receipt")}</p>`;
  const result = has(K.receipts_verify) ? `<span>${esc(K.receipts_verify)}</span>` : gap("Result");
  const check = `<p><code>${command}</code>${copyButton(command)}${result}</p>`;
  const label = has(root?.status) ? `decision ${esc(root.status.toLowerCase())}${root.seeded ? ", seeded" : ""}` : gap("Decision");
  const rule = `<p>Rule ${has(where.rule) ? esc(where.rule) : gap("Rule")} · ${label}</p>`;
  $("checks").innerHTML = receipt + check + rule;
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

function play(node, frames, delay, duration) {
  if (node) node.animate(frames, { delay, duration, easing: EASE_OUT, fill: "backwards" });
}

function arrival() {
  // The reply slides in from the agent's side, the ruling rises, the outcome word lands, the fix arrives last.
  play($("reply"), [{ opacity: 0, transform: "translateX(-0.75rem)" }, { opacity: 1, transform: "none" }], BEATS.reply, 420);
  play($("ruling"), [{ opacity: 0, transform: "translateY(0.75rem)" }, { opacity: 1, transform: "none" }], BEATS.ruling, 420);
  play(document.querySelector("[data-beat=word]"), [{ opacity: 0, transform: "translateY(0.75rem)" }, { opacity: 1, transform: "none" }], BEATS.word, 320);
  play($("fixcard"), [{ opacity: 0, transform: "translateY(0.75rem)" }, { opacity: 1, transform: "none" }], BEATS.fix, 420);
}

function freeze(ms) {
  // Capture only: hold every animation at one moment.
  document.getAnimations().forEach((a) => { a.pause(); a.currentTime = ms; });
}

[bar, blocked, note, reply, rulingNote, outcomeCard, answeredBy, fix, verify, copies].forEach((step) => step());
document.fonts.ready.then(() => {
  if (!REDUCED) arrival();
  if (Q.has("t")) freeze(Number(Q.get("t")));
  window.__freeze = freeze;
  window.__ready = true;
});
