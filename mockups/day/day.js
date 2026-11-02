// The day screen, bound from scenes.js only (day, root, grid, receipts_verify); a missing value renders "<label> not recorded".
const K = window.KNACK || {}, D = K.day || {};
const Q = new URLSearchParams(location.search);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
// One move: the cells fade in a week at a time, left to right, all done inside 600 ms.
const FADE = { step: 7, ms: 220 };
const WEEKS = 52, DAY_MS = 864e5;
const $ = (id) => document.getElementById(id);

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const gap = (label) => `<span class="gap">${esc(label)} not recorded</span>`;
const has = (v) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length);
const nowrap = (s) => `<span class="nowrap">${s}</span>`;
const month = (d) => d.toLocaleString("en", { month: "short", timeZone: "UTC" });
const dayOf = (d) => `${month(d)} ${d.getUTCDate()} ${d.getUTCFullYear()}`;
const clock = (iso) => `${new Date(iso).toISOString().slice(11, 19)} UTC`;
const key = (d) => d.toISOString().slice(0, 10);
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

const today = has(D.date) ? new Date(`${D.date}T00:00:00Z`) : null;
const seats = D.seats || [], events = D.events || [];
const blocks = events.filter((e) => e.type === "receipt" && e.kind === "block");
const resolves = events.filter((e) => e.type === "receipt" && e.kind === "resolve");
const lastBlock = blocks.at(-1);

function byDay(list, when) {
  // Index anything dated by its UTC day.
  const map = new Map();
  list.filter((x) => has(when(x))).forEach((x) => { const k = when(x).slice(0, 10); map.set(k, [...(map.get(k) || []), x]); });
  return map;
}

const DECIDED = byDay(seats, (s) => s.merged_at);
const BLOCKED = byDay(blocks, (b) => new Date(b.time).toISOString());
const RESOLVED = byDay(resolves, (r) => new Date(r.time).toISOString());

function bar() {
  const branch = has(D.branch) ? esc(D.branch) : gap("Branch");
  $("where").innerHTML = has(D.repo) ? `<b>${esc(D.repo)}</b> <i>/</i> ${branch}` : gap("Repo");
  const last = events.filter((e) => e.type === "receipt").at(-1);
  $("when").innerHTML = last ? `<code>${esc(last.receipt_hash.slice(0, 12))}</code> <time>${esc(dayOf(new Date(last.time)))}, ${esc(clock(last.time))}</time>` : gap("Receipt");
}

function head() {
  $("title").innerHTML = has(D.repo) ? `${esc(D.repo)} remembers ${nowrap(plural(seats.length, "decision", "decisions"))}.` : gap("Repo");
  const onToday = lastBlock && today && key(new Date(lastBlock.time)) === key(today);
  $("sub").innerHTML = !lastBlock ? "Nothing blocked today." : `Last block ${onToday ? "today" : esc(dayOf(new Date(lastBlock.time)))}, ${nowrap(esc(clock(lastBlock.time)))}.`;
}

function counts() {
  // One line of real counts; what the day feed does not carry is named, not zeroed.
  const blockedToday = blocks.length ? `${plural(blocks.length, "block", "blocks")} today` : "no blocks today";
  $("counts").innerHTML = `<b>${plural(seats.length, "confirmed decision", "confirmed decisions")}</b> in ${WEEKS} weeks · ${blockedToday} · ${gap("Earlier blocks")}`;
  $("legend").innerHTML = `<li class="steps"><span class="swatch s1"></span><span class="swatch s2"></span><span class="swatch s3"></span>1, 2, 3+ decisions</li>`
    + `<li><span class="mark block"></span>a block</li><li><span class="mark person"></span>${resolves.length ? "a person resolved a held edit" : gap("Resolved by a person")}</li>`;
}

function days() {
  // Every day from the Sunday 52 weeks back to today, a column a week.
  if (!today) return [];
  const start = new Date(today.getTime() - (WEEKS * 7 + today.getUTCDay()) * DAY_MS);
  return Array.from({ length: Math.round((today - start) / DAY_MS) + 1 }, (_, i) => new Date(start.getTime() + i * DAY_MS));
}

function describe(d) {
  const k = key(d), decided = DECIDED.get(k) || [], blocked = BLOCKED.get(k) || [], resolved = RESOLVED.get(k) || [];
  const parts = [dayOf(d), decided.length ? plural(decided.length, "decision", "decisions") : "no decisions recorded"];
  decided.forEach((s) => parts.push(`#${s.pr}`, s.decided_by));
  if (blocked.length) parts.push(plural(blocked.length, "block", "blocks"));
  if (resolved.length) parts.push(`${resolved.length} resolved by a person`);
  return parts.join(" · ");
}

function cell(d, i) {
  const k = key(d), n = (DECIDED.get(k) || []).length;
  const marks = (BLOCKED.has(k) ? `<span class="mark block"></span>` : "") + (RESOLVED.has(k) ? `<span class="mark person"></span>` : "");
  const isToday = k === key(today);
  return `<button type="button" class="cell s${Math.min(n, 3)}" data-week="${Math.floor(i / 7)}" data-i="${i}" tabindex="${isToday ? 0 : -1}" aria-label="${esc(describe(d))}"${isToday ? ' aria-current="date"' : ""}>${marks}</button>`;
}

function graph() {
  const all = days();
  if (!all.length) return ($("cells").innerHTML = gap("Dates"));
  $("cells").innerHTML = all.map(cell).join("");
  $("cells").style.setProperty("--weeks", Math.ceil(all.length / 7));
  // Sparse month labels: every other month, placed over the week its first day falls in.
  $("months").innerHTML = all.filter((d) => d.getUTCDate() === 1 && d.getUTCMonth() % 2 === 0)
    .map((d) => `<span style="grid-column:${Math.floor(all.indexOf(d) / 7) + 1}">${month(d)}${d.getUTCMonth() === 0 ? ` ${d.getUTCFullYear()}` : ""}</span>`).join("");
  $("months").style.setProperty("--weeks", Math.ceil(all.length / 7));
}

function tip(button) {
  const t = $("tip"), box = $("graph").getBoundingClientRect(), r = button.getBoundingClientRect();
  t.textContent = button.getAttribute("aria-label");
  t.hidden = false;
  const left = Math.min(Math.max(r.left + r.width / 2 - box.left - t.offsetWidth / 2, 0), box.width - t.offsetWidth);
  Object.assign(t.style, { left: `${left}px`, top: `${r.top - box.top - t.offsetHeight - 8}px` });
}

function move(button, key) {
  // Up and down move a day, left and right a week, as the grid is drawn.
  const step = { ArrowUp: -1, ArrowDown: 1, ArrowLeft: -7, ArrowRight: 7 }[key];
  const next = step && document.querySelector(`.cell[data-i="${Number(button.dataset.i) + step}"]`);
  if (!next) return;
  button.tabIndex = -1;
  next.tabIndex = 0;
  next.focus();
}

function wire() {
  const cells = $("cells");
  cells.addEventListener("pointerover", (e) => e.target.closest(".cell") && tip(e.target.closest(".cell")));
  cells.addEventListener("pointerleave", () => ($("tip").hidden = true));
  cells.addEventListener("focusin", (e) => tip(e.target));
  cells.addEventListener("focusout", () => ($("tip").hidden = true));
  cells.addEventListener("keydown", (e) => { if (e.key.startsWith("Arrow")) { e.preventDefault(); move(e.target, e.key); } });
}

function seatRow(s) {
  // The decision in plain words exists only where the fixture holds that root; the grid only for that root's rule.
  const root = K.root?.id === s.root_id ? K.root : null;
  const words = root?.decision ? esc(root.decision) : gap("Decision text");
  const grid = root && K.grid?.cells ? Object.values(K.grid.cells) : [];
  const passed = grid.length ? `${nowrap(`${grid.filter((c) => c === "PASS").length} of ${grid.length} gates`)} · ${nowrap(`tier ${esc(K.grid.tier)}`)}` : gap("Proof");
  const pr = has(s.pr) && has(D.repo) ? `<a href="https://github.com/${esc(D.repo)}/pull/${esc(s.pr)}">#${esc(s.pr)}</a>` : gap("PR");
  const when = has(s.merged_at) ? nowrap(`merged ${esc(dayOf(new Date(s.merged_at)))}`) : gap("Merge date");
  return `<li><p class="words">${words}</p><p class="meta"><b>${esc(s.decided_by || "")}</b> · ${pr} · ${when} · ${passed}</p></li>`;
}

function decisions() {
  $("seats").innerHTML = seats.length ? seats.map(seatRow).join("") : `<li>${gap("Decisions")}</li>`;
}

function eventRow(e) {
  if (e.type === "commit") return `<li><time>${esc(clock(e.time))}</time><p>Commit <code>${esc(e.sha.slice(0, 8))}</code> “${esc(e.message)}” · ${esc(e.author)}</p></li>`;
  if (e.type === "receipt") return `<li><time>${esc(clock(e.time))}</time><p><span class="mark block" aria-hidden="true"></span>${esc(e.kind === "block" ? "Blocked" : e.kind)} an edit against <code>${esc(e.root_id)}</code></p></li>`;
  return "";
}

function todayList() {
  $("today").textContent = today ? `Today, ${dayOf(today)}` : "Today";
  const pulls = has(D.pulls_error) ? `<li><time></time><p>${gap("Pull requests")}: ${esc(D.pulls_error)}</p></li>` : "";
  $("events").innerHTML = (events.map(eventRow).join("") || `<li>${gap("Events")}</li>`) + pulls;
}

function verify() {
  const last = events.filter((e) => e.type === "receipt").at(-1), command = "knack receipts verify";
  const receipt = last ? `<p><span>Last receipt <code>${esc(last.receipt_hash.slice(0, 8))}</code></span>${copyButton(last.receipt_hash)}</p>` : `<p>${gap("Receipt")}</p>`;
  const result = has(K.receipts_verify) ? `<span>${esc(K.receipts_verify)}</span>` : gap("Result");
  const rule = K.root?.status ? `<p>${esc(K.root.id)}, ${esc(K.root.status.toLowerCase())}${K.root.seeded ? ", seeded" : ""}</p>` : "";
  $("checks").innerHTML = receipt + `<p><code>${command}</code>${copyButton(command)}${result}</p>` + rule;
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

function arrival() {
  document.querySelectorAll(".cell").forEach((c) => c.animate([{ opacity: 0 }, { opacity: 1 }], { delay: Number(c.dataset.week) * FADE.step, duration: FADE.ms, easing: "cubic-bezier(0.23, 1, 0.32, 1)", fill: "backwards" }));
}

function freeze(ms) {
  document.getAnimations().forEach((a) => { a.pause(); a.currentTime = ms; });
}

[bar, head, counts, graph, wire, decisions, todayList, verify, copies].forEach((step) => step());
document.fonts.ready.then(() => {
  // On a narrow screen the graph scrolls; it opens on today, where the record is.
  $("graph").scrollLeft = $("graph").scrollWidth;
  if (!REDUCED) arrival();
  if (Q.has("t")) freeze(Number(Q.get("t")));
  window.__ready = true;
});
