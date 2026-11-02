// The recovery screen, bound from scenes.js `miss` only; a missing value renders "<label> not recorded".
const K = window.KNACK || {}, M = K.miss || {};
const Q = new URLSearchParams(location.search);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
// One move: the timeline fills top to bottom once, then stays.
const FILL = { at: 300, ms: 1400, easing: "cubic-bezier(0.77, 0, 0.175, 1)" };
const $ = (id) => document.getElementById(id);

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const gap = (label) => `<span class="gap">${esc(label)} not recorded</span>`;
const has = (v) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length);
const nowrap = (s) => `<span class="nowrap">${s}</span>`;
const month = (d) => d.toLocaleString("en", { month: "short", timeZone: "UTC" });
const day = (iso) => { const d = new Date(iso); return `${month(d)} ${d.getUTCDate()} ${d.getUTCFullYear()}`; };
const stamp = (iso) => `${day(iso)}, ${new Date(iso).toISOString().slice(11, 19)} UTC`;

const root = M.root || {}, log = M.bar2_log || "";
const pr = root.source_url?.match(/github\.com\/([^/]+\/[^/]+)\/pull\/(\d+)/);
const caseFile = log.match(/-> (data\/registry\/cases\/\S+\.json)/)?.[1];
const caseId = log.match(/\[([0-9a-f]{12})\]/)?.[1];
const recompiler = log.match(/recompiling with (\S+)/)?.[1];
const installed = log.match(/installed (\S+) -> (\S+) \((\d+) attempt/);
const ruleId = installed?.[1] || log.match(/for (\S+) ->/)?.[1];
const rulePath = installed?.[2]?.replace("data/registry/../", "data/");

function gates(text) {
  // Every "PASS name: result" line, verbatim; the local cache path in parentheses is dropped.
  return [...text.matchAll(/^(PASS|FAIL) ([^:]+): (.*)$/gm)].map(([, pass, name, said]) => ({ pass, name, said: said.replace(/ \(\/[^)]*\)$/, "") }));
}

function compiledAt() {
  // The candidate file's own timestamp, the one moment the log records for the recompile.
  const t = log.match(/candidate-(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)Z/);
  return t ? `${t[1]}-${t[2]}-${t[3]}T${t[4]}:${t[5]}:${t[6]}Z` : null;
}

function modelName(id) {
  return id === K.spark?.model ? "Muse Spark" : id === K.spark_open?.model ? "Muse Spark Open" : null;
}

function hostOf(id) {
  return id === K.spark?.model ? K.spark.host : id === K.spark_open?.model ? K.spark_open.host : null;
}

function bar() {
  const repo = pr ? esc(pr[1]) : gap("Repo");
  const file = has(M.edit_file) ? `<b>${esc(M.edit_file.split("/").slice(-2).join("/"))}</b>` : gap("File");
  $("where").innerHTML = `${repo} <i>/</i> ${gap("Branch")} <i>/</i> ${file}`;
  const at = compiledAt();
  $("when").innerHTML = `${gap("Receipt")} ${at ? `<time>${esc(stamp(at))}</time>` : gap("Time")}`;
}

function slipped() {
  // The edit's lines that set the cache size, numbered as in the rebuilt file.
  const lines = (M.edit_after || "").split("\n").map((code, i) => ({ n: i + 1, code })).filter((l) => /_CALLABLE_CACHE_SIZE\b/.test(l.code));
  const shown = lines.slice(0, 1);
  $("code").innerHTML = shown.length
    ? shown.map((l) => `<div class="line"><span class="n">${l.n}</span><span class="sign"></span><code>${esc(l.code)}</code></div>`).join("")
    : `<p class="more">${gap("The edit")}</p>`;
  const first = (M.edit_note || "").match(/^.*?\.(?=\s)/)?.[0];
  $("rebuilt").innerHTML = first ? esc(first) : gap("Where the edit came from");
}

function recompiled() {
  const name = modelName(recompiler), host = hostOf(recompiler);
  $("recompiled-title").innerHTML = recompiler ? `Recompiled by ${esc(name || recompiler)}` : `Recompiled · ${gap("Model")}`;
  $("recompiled-by").innerHTML = recompiler
    ? `<code>${esc(recompiler)}</code> at ${host ? esc(host) : gap("Host")}, from case <code>${esc(caseId || "")}</code>.`
    : gap("Recompile");
  $("earlier").innerHTML = earlierRuns();
}

function earlierRuns() {
  // The two runs before the one that installed: each kept the old rule, and the log names the gate that failed.
  const runs = [M.run1_log, M.run2_log].filter(has).map((t) => gates(t).find((g) => g.pass === "FAIL")?.name).filter(Boolean);
  if (!runs.length) return "";
  return `${runs.length === 2 ? "Two" : "One"} earlier ${runs.length === 2 ? "runs" : "run"} kept the old rule: ${runs.map((n) => `<b>${esc(n)}</b>`).join(", then ")} failed.`;
}

function unbroken(text) {
  // Hyphenated gate names never split across lines.
  return esc(text).replace(/\S+-\S+/g, (word) => nowrap(word));
}

function proven() {
  const shown = gates(log).filter((g) => g.name !== "cases");
  const passed = shown.every((g) => g.pass === "PASS");
  $("proven-title").textContent = shown.length ? `Proven by ${["", "one", "two", "three", "four", "five"][shown.length] || shown.length} gates${passed ? "" : ", not all passed"}` : "Proven";
  $("gates").innerHTML = shown.length
    ? shown.map((g) => `<li><b>${esc(g.name)}</b> <span>${g.pass === "PASS" ? "passed" : "failed"}:</span> ${unbroken(g.said)}</li>`).join("")
    : `<li>${gap("Gates")}</li>`;
}

function denied() {
  const cases = gates(log).find((g) => g.name === "cases");
  $("denied-by").innerHTML = cases
    ? `<b>cases</b> <span class="quiet">${cases.pass === "PASS" ? "passed" : "failed"}:</span> ${esc(cases.said)}.`
    : gap("A replay of the edit");
  const tier = has(M.tier) ? `<b>${esc(M.tier)}</b>` : gap("Tier");
  const status = has(root.status) ? esc(root.status) : gap("Decision label");
  const install = installed ? `Installed after ${esc(installed[3])} attempts. ` : `${gap("Install")}. `;
  $("live").innerHTML = `${install}A proof run, not a live retry. Live, the tier is ${tier} and the decision ${status}.`;
}

function note() {
  if (!has(root.quote)) return ($("note").innerHTML = gap("The decision"));
  const phrase = root.rejected_alternative, q = esc(root.quote);
  const marked = has(phrase) && root.quote.includes(phrase) ? q.replace(esc(phrase), `<mark>${esc(phrase)}</mark>`) : q;
  const who = has(root.decided_by) ? `<b>${esc(root.decided_by)}</b>` : gap("Decider");
  const when = has(root.merged_at) ? `merged ${nowrap(esc(day(root.merged_at)))}` : gap("Merge date");
  const link = pr ? `<a href="${esc(root.source_url)}">#${esc(pr[2])}</a>` : gap("PR");
  const label = has(root.status) ? nowrap(`${esc(root.status)}${root.seeded ? ", seeded" : ""}`) : gap("Label");
  $("note").innerHTML = `<blockquote cite="${esc(root.source_url || "")}"><p>“${marked}”</p></blockquote><figcaption>${[who, when].join(" · ")} · ${nowrap(`${link} · ${label}`)}</figcaption>`;
}

function rule() {
  // One plain sentence each, every clause taken from the edit note or the gate log.
  const constant = /sets 8192 through a module-level constant/.test(M.edit_note || "");
  const noMatch = /adds no new match/.test(log);
  $("before").innerHTML = constant && noMatch ? "Found no new match in this edit, which sets 8192 through a module-level constant." : gap("The old rule's behaviour");
  const cases = gates(log).find((g) => g.name === "cases" && g.pass === "PASS");
  const kept = gates(log).filter((g) => g.name.startsWith("held-out") || g.name.startsWith("fresh")).every((g) => /3\/3 compliant allowed/.test(g.said));
  $("after").innerHTML = cases ? `Denies this edit${M.cases?.length === 1 ? ", its one must-fail case," : ""} and allows every must-pass edit${kept ? " and 3/3 compliant edits in each held-out set" : ""}.` : gap("The new rule's behaviour");
}

function workers() {
  const name = modelName(recompiler), host = hostOf(recompiler);
  const spark = recompiler ? `<li><b>${esc(name || recompiler)}</b> <code>${esc(recompiler)}</code><br><span>at ${host ? esc(host) : gap("Host")}, recompiled the rule</span></li>` : `<li>${gap("Model")}</li>`;
  const fresh = gates(log).some((g) => g.name === "fresh cross-model") ? `<li>${gap("The fresh cross-model gate’s model")}</li>` : "";
  $("models").innerHTML = spark + fresh;
}

function verify() {
  // One command: the installed rule, at the path the install line names.
  const command = rulePath ? `cat ${rulePath}` : null;
  const check = command ? `<p><code>${esc(command)}</code>${copyButton(command)}</p>` : `<p>${gap("Rule file")}</p>`;
  const label = has(root.status) ? `decision ${esc(root.status.toLowerCase())}${root.seeded ? ", seeded" : ", not seeded"}` : gap("Decision");
  const plain = `<p>Rule ${ruleId ? esc(ruleId) : gap("Rule")} · ${label} · tier ${has(M.tier) ? esc(M.tier) : gap("Tier")}</p>`;
  $("checks").innerHTML = `<p>${gap("Receipt")}</p>` + check + plain;
}

function copyButton(text) {
  return `<button type="button" class="copy" data-copy-text="${esc(text)}" aria-live="polite" aria-label="Copy ${esc(text)}">Copy</button>`;
}

function copies() {
  document.querySelectorAll("[data-copy-text]").forEach((button) => button.addEventListener("click", async () => {
    await navigator.clipboard?.writeText(button.dataset.copyText);
    button.textContent = "Copied";
    setTimeout(() => { button.textContent = "Copy"; }, 1600);
  }));
}

function track() {
  // The fill runs from the first step to the top of the last recorded step; the gap below is never filled.
  const list = $("steps"), last = $("denied"), fill = list.querySelector(".fill") || list.appendChild(Object.assign(document.createElement("span"), { className: "fill" }));
  fill.setAttribute("aria-hidden", "true");
  fill.style.height = `${last.offsetTop + last.offsetHeight}px`;
  list.classList.add("tracked");
  return fill;
}

function fillOnce(fill) {
  fill.animate([{ transform: "scaleY(0)" }, { transform: "scaleY(1)" }], { delay: FILL.at, duration: FILL.ms, easing: FILL.easing, fill: "backwards" });
}

function freeze(ms) {
  document.getAnimations().forEach((a) => { a.pause(); a.currentTime = ms; });
}

[bar, slipped, recompiled, proven, denied, note, rule, workers, verify, copies].forEach((step) => step());
document.fonts.ready.then(() => {
  const fill = track();
  if (!REDUCED) fillOnce(fill);
  addEventListener("resize", track);
  if (Q.has("t")) freeze(Number(Q.get("t")));
  window.__ready = true;
});
