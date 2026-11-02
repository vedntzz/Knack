// The console: six scenes on one clock. ?scene=<name>&t=<ms> freezes any frame for capture.
(() => {
  const K = window.KNACK, M = window.Motion, G = window.Ground;
  const root = document.documentElement, stage = document.getElementById("stage");
  const $ = (s, el = document) => el.querySelector(s), $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const query = new URLSearchParams(location.search);
  const FIXED = query.has("t") ? Number(query.get("t")) : null;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SPRING = { type: "spring", stiffness: 180, damping: 24 };
  const SOFT = [0.2, 0.7, 0.2, 1];

  // Formatting: every visible value is a field of the frozen fixture, shaped only by these.
  const pad = (n) => String(n).padStart(2, "0");
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const clock = (iso) => { const [h, m] = iso.slice(11, 16).split(":").map(Number); return `${h % 12 || 12}:${pad(m)} ${h < 12 ? "am" : "pm"}`; };
  const stamp = (iso) => { const d = new Date(iso); return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}, ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`; };
  const FMT = {
    first: (v) => v.split(" (")[0], merger: (v) => v.split("merged by ")[1], pr: (v) => v.split("/").pop(),
    sentence: (v) => v.split(". ")[0] + ".", short: (v) => v.slice(0, 7), short8: (v) => v.slice(0, 8), clock, stamp,
    tail: (v) => v.split("/").slice(-3).join("/"), host: (v) => v.replace("https://", ""), repo: (v) => v.split("/").slice(3, 5).join("/"),
    hashpart: (v) => v.split(" ")[0], seeded: (v) => (v ? "Seeded" : "Not seeded"),
  };
  const at = (path) => path.split(".").reduce((o, k) => (o == null ? o : o[k]), K);
  const norm = (s) => String(s).replace(/[“”"`]/g, "").replace(/\s+/g, " ").trim();
  const holds = (el, value) => el.tagName === "PRE"
    ? el.textContent.split("\n").every((line) => norm(value).includes(norm(line.replace(/^\+/, ""))))
    : norm(value).includes(norm(el.textContent));

  // The truth audit: a shown value that is not in its source file is a bug, reported loudly.
  const audit = () => {
    const failed = $$("[data-src]").filter((el) => { const v = at(el.dataset.src); const f = el.dataset.fmt; return v == null || (f && !FMT[f]) || !holds(el, f ? FMT[f](v) : v); });
    failed.forEach((el) => console.error("truth: not in fixture", el.dataset.src, JSON.stringify(el.textContent)));
    window.__truth = { checked: $$("[data-src]").length, failed: failed.map((el) => el.dataset.src) };
  };

  // Layout mode: film is the 1920x1080 stage; anything narrower stacks.
  const film = () => innerWidth >= 900;
  const fitStage = () => {
    root.classList.toggle("film", film());
    root.style.setProperty("--k", Math.min(innerWidth / 1920, innerHeight / 1080));
  };
  const scale = () => Number(root.style.getPropertyValue("--k")) || 1;

  // The hour strip: 24 cells, a tick where today's commit landed, the hour of the frozen day breathing.
  const buildHours = () => {
    const hour = Number(K.day.events[0].time.slice(11, 13)), box = $("#hours");
    box.replaceChildren(...Array.from({ length: 24 }, (_, h) => { const i = document.createElement("i"); i.classList.toggle("has", h === hour); i.classList.toggle("now", h === hour); return i; }));
    if (FIXED != null) box.style.setProperty("--breath", `${-(FIXED % 6000) / 1000}s`);
  };

  // The agent's edit, parsed from run 3's diff: context, the struck line, the added lines it types.
  const DEDENT = 12;
  const parseHunk = () => {
    const body = K.diff.split("\n@@")[1].split("\n").slice(1), out = [];
    let no = 131;
    for (const raw of body) {
      const kind = raw[0] === "-" ? "del" : raw[0] === "+" ? "add" : "ctx", text = raw.slice(1 + DEDENT);
      out.push({ kind, text, no: kind === "del" ? "" : no++ });
      if (raw.includes("dynamic_depends")) break;
    }
    return out;
  };
  const LINES = parseHunk();
  const HITS = (K.block.matched.match(/line (\d+)/g) || []).map((s) => Number(s.slice(5)));
  const CHAR_MS = 24, TYPE_FROM = 500;
  const schedule = (() => { let t = TYPE_FROM; return LINES.map((l) => { const lead = l.text.match(/^ */)[0].length, start = t; if (l.kind === "add") t += (l.text.length - lead) * CHAR_MS + 140; return { lead, start }; }); })();
  const TYPE_END = schedule.reduce((end, s, i) => (LINES[i].kind === "add" ? Math.max(end, s.start + (LINES[i].text.length - s.lead) * CHAR_MS) : end), 0);

  const lineHTML = (l, shown) => {
    const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
    const full = shown.length === l.text.length && l.no === HITS[0];
    return full ? esc(shown).replace("DagRun.state", '<b class="tok" id="tok">DagRun.state</b>') : esc(shown);
  };
  const typed = (i, t) => { const l = LINES[i], s = schedule[i]; return l.kind !== "add" ? l.text.length : Math.max(0, Math.min(l.text.length, s.lead + Math.floor((t - s.start) / CHAR_MS))); };
  const renderCode = (t) => {
    let caretAt = -1;
    const spans = LINES.map((l, i) => {
      const n = typed(i, t), hidden = l.kind === "add" && n <= schedule[i].lead && t < schedule[i].start;
      if (l.kind === "add" && n > 0 && !hidden) caretAt = i;
      const cls = [l.kind, HITS.includes(l.no) ? "hit" : ""].join(" ");
      return hidden ? "" : `<span class="${cls}"><i class="ln">${l.no}</i>${lineHTML(l, l.text.slice(0, n))}${"\u0000"}</span>`;
    });
    const html = spans.map((s, i) => s.replace("\u0000", i === caretAt ? '<i class="caret"></i>' : "")).join("");
    if (html !== lastCode) $("#code").innerHTML = lastCode = html;
  };
  let lastCode = "";

  // The postmark: today rolls back to the day the decision merged, six steps 160 ms apart.
  const TODAY = Date.parse(K.day.date + "T12:00:00Z"), MERGED = Date.parse(K.root.merged_at);
  const DAYS = Math.round((TODAY - Date.parse(K.root.merged_at.slice(0, 10) + "T12:00:00Z")) / 864e5);
  const STEPS = 6, ROLL_AT = 300, ROLL_GAP = 160, ROLL_MS = 150;
  const stepDate = (i) => new Date(TODAY - Math.round((DAYS * i) / STEPS) * 864e5);
  const monthOf = (d) => `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  const ease = (x) => 1 - (1 - x) ** 3;
  const roll = (box, from, to, p) => {
    if (box.children.length < 2) box.append(document.createElement("span"));
    const [out, inn] = box.children, q = ease(p);
    out.textContent = from; inn.textContent = to;
    out.style.transform = `translateY(${-q * 100}%)`; out.style.opacity = from === to ? 0 : 1 - q;
    inn.style.transform = `translateY(${from === to ? 0 : (1 - q) * 72}%)`; inn.style.opacity = from === to ? 1 : q;
  };
  const renderPostmark = (t) => {
    const k = Math.max(0, Math.min(STEPS, Math.floor((t - ROLL_AT) / ROLL_GAP) + 1));
    const p = k === 0 ? 1 : Math.min(1, (t - ROLL_AT - (k - 1) * ROLL_GAP) / ROLL_MS);
    const a = stepDate(Math.max(0, k - 1)), b = stepDate(k);
    roll($("#pm-day"), String(a.getUTCDate()), String(b.getUTCDate()), p);
    roll($("#pm-month"), monthOf(a), monthOf(b), p);
    const back = Math.round((DAYS * k) / STEPS);
    $("#pm-ago").textContent = k === 0 ? "today" : `${back} days ago, merged ${pad(new Date(MERGED).getUTCHours())}:${pad(new Date(MERGED).getUTCMinutes())} UTC`;
  };

  // The thread: from the rejected phrase in the quote to the token in the agent's line.
  const THREAD_AT = 1600, THREAD_MS = 480;
  const renderThread = (t) => {
    const tok = $("#tok"), rej = $("#rej"), path = $("#thread path");
    if (!tok || !rej) return;
    const s = stage.getBoundingClientRect(), k = scale(), a = rej.getBoundingClientRect(), b = tok.getBoundingClientRect();
    const X = (v) => (v - s.left) / k, Y = (v) => (v - s.top) / k;
    const yA = Y(a.bottom) + 2, yB = Y(b.bottom) + 1, x1 = X(a.right), x2 = X(b.left);
    path.setAttribute("d", `M${X(a.left)} ${yA} L${x1} ${yA} C${x1 + 170} ${yA}, ${x2 - 170} ${yB}, ${x2} ${yB} L${X(b.right)} ${yB}`);
    const len = path.getTotalLength(), p = ease(Math.max(0, Math.min(1, (t - THREAD_AT) / THREAD_MS)));
    path.style.strokeDasharray = len; path.style.strokeDashoffset = len * (1 - p);
  };

  // Each scene: who speaks, the keys, what the ground does, and its Motion timeline.
  const decider = FMT.first(K.root.decided_by);
  const commits = K.day.events.filter((e) => e.type === "commit").length;
  const SCENES = {
    day: { pillar: "keeper", keys: ["space"], amp: 10, line: `I read ${commits === 1 ? "one commit" : commits + " commits"} on ${K.day.branch} today; pull requests need a token. Space starts.` },
    typing: { pillar: "guard", keys: ["esc"], amp: 15, line: "I'm watching run 3 edit dags.py; I answer before it writes. Esc returns." },
    block: { pillar: "guard", keys: ["a", "enter", "r", "esc"], frozen: true, sheet: "#sheet", line: `I denied the edit in ${K.block.verdict_ms} ms, quoting ${decider}. A to argue.` },
    argue: { pillar: "reader", keys: ["p", "enter", "r", "esc"], frozen: true, sheet: "#sheet", line: `I read the objection against ${decider}’s words: ${K.hold.decision}. P asks a person.` },
    held: { pillar: "keeper", keys: ["enter", "r", "esc"], frozen: true, sheet: "#sheet", line: `I held receipt ${K.escalate.receipt_hash.slice(0, 8)} for a person. Copy the command, then Enter.` },
    miss: { pillar: "prover", keys: ["r", "esc"], amp: 10, sheet: "#miss", line: `I recompiled ${K.miss.root.id.replace(/-1$/, "")} until every gate passed; replay now denies the slip. Esc.` },
  };
  const KEYS = { space: ["Space", "start", "typing"], a: ["A", "argue", "argue"], p: ["P", "ask a person", "held"], enter: ["Enter", "acknowledge", "ack"], r: ["R", "replay", "replay"], esc: ["Esc", "day", "ack"] };
  const PREV = { day: null, typing: "day", block: "typing", argue: "block", held: "argue", miss: "day" };
  // Per scene, each plane's pull in stage px: the speaking actor's plane comes to the sheet, teal leaves text it would wash out.
  const PULL = { day: [[0, 0], [0, 0], [0, 0]], typing: [[0, 0], [0, 0], [0, 0]], block: [[-60, 150], [-300, 90], [0, 0]], argue: [[150, -150], [-300, 90], [0, 0]], held: [[-60, 150], [-300, 90], [0, 0]], miss: [[-60, 150], [0, 0], [-110, -40]] };

  const fill = () => $("#seat-decider .fill");
  const words = () => $$(".quote .w");
  const TIMELINES = {
    day: () => [[".day", { opacity: [0, 1] }, { duration: 0.35, at: 0 }], [fill(), { scale: 0 }, { duration: 0.2, at: 0 }]],
    typing: () => [[".day", { opacity: 1 }, { duration: 0.01, at: 0 }], [".agent", { opacity: [0, 1], x: [18, 0] }, { duration: 0.45, ease: SOFT, at: 0 }], [fill(), { scale: 0 }, { duration: 0.01, at: 0 }]],
    block: () => [
      [".agent", { opacity: 1 }, { duration: 0.01, at: 0 }],
      ["#stop", { opacity: [0, 1], scale: [1.5, 1] }, { duration: 0.2, ease: [0.3, 1.4, 0.5, 1], at: 0 }],
      [".day", { opacity: [1, 0] }, { duration: 0.24, at: 0.12 }],
      ["#sheet", { opacity: [0, 1], y: [80, 0] }, { ...SPRING, at: 0.12 }],
      [words(), { opacity: [0, 1], y: [16, 0] }, { duration: 0.6, ease: SOFT, delay: M.stagger(0.016), at: 0.9 }],
      [fill(), { scale: [0, 1] }, { ...SPRING, at: 0.95 }],
      [".said .attrib, .said .honest", { opacity: [0, 1] }, { duration: 0.4, at: 1.3 }],
      [".blocked .ch", { opacity: [0, 1], y: [10, 0] }, { duration: 0.14, ease: SOFT, delay: M.stagger(0.03), at: 1.78 }],
      [".ms", { opacity: [0, 1] }, { duration: 0.3, at: 2.1 }],
    ],
    argue: () => [
      ["#sheet", { opacity: 1, y: 0 }, { duration: 0.01, at: 0 }], ["#stop", { opacity: 1 }, { duration: 0.01, at: 0 }], [".agent", { opacity: 1 }, { duration: 0.01, at: 0 }],
      [".objection[data-in='argue']", { opacity: [0, 1], y: [10, 0] }, { duration: 0.4, ease: SOFT, at: 0 }],
      [".answer[data-in='argue'] > *", { opacity: [0, 1], y: [14, 0] }, { duration: 0.55, ease: SOFT, delay: M.stagger(0.18), at: 0.6 }],
      [fill(), { scale: [0, 1] }, { ...SPRING, at: 0.6 }],
    ],
    held: () => [
      ["#sheet", { opacity: 1, y: 0 }, { duration: 0.01, at: 0 }], ["#stop", { opacity: 1 }, { duration: 0.01, at: 0 }], [".agent", { opacity: 1 }, { duration: 0.01, at: 0 }],
      [".objection[data-in='held']", { opacity: [0, 1], y: [10, 0] }, { duration: 0.4, ease: SOFT, at: 0 }],
      [fill(), { scale: 0 }, { duration: 0.2, at: 0 }],
      [".seat.nobody", { opacity: [0, 1] }, { duration: 0.4, at: 0.3 }],
      [".answer[data-in='held'] > *", { opacity: [0, 1], y: [14, 0] }, { duration: 0.55, ease: SOFT, delay: M.stagger(0.16), at: 0.5 }],
    ],
    miss: () => [
      [fill(), { scale: 0 }, { duration: 0.01, at: 0 }],
      ["#miss", { opacity: [0, 1], y: [56, 0] }, { ...SPRING, at: 0.1 }],
      [".rail", { scaleY: [0, 1] }, { duration: 2.0, ease: [0.4, 0, 0.2, 1], at: 0.45 }],
      [".steps li:not(.rail)", { opacity: [0, 1], y: [10, 0] }, { duration: 0.45, ease: SOFT, delay: M.stagger(0.4), at: 0.45 }],
    ],
  };
  const DURATION = { day: 400, typing: TYPE_END + 600, block: 2600, argue: 1800, held: 1600, miss: 2800 };

  // State and the one clock.
  let scene = "day", started = 0, controls = null, driftS = 0, lastNow = 0;
  let pullFrom = [[0, 0], [0, 0], [0, 0]], pullAt = 0, shiftFrom = 0, timers = [];
  let pointer = [0, 0], pointerGoal = [0, 0];
  const sceneTime = (now) => (FIXED != null ? FIXED : reduced || !film() ? DURATION[scene] : now - started);
  const later = (ms, fn) => timers.push(setTimeout(fn, ms));
  const pullTarget = (name) => {
    const k = scale();
    return (PULL[name] || PULL.day).map(([x, y]) => [x * k, y * k]);
  };
  const SHIFT_STEP = -30;
  const shiftAt = (t) => {
    if (scene === "argue" || scene === "held") return STEPS * SHIFT_STEP * scale();
    if (scene !== "block") return shiftFrom * (1 - ease(Math.min(1, t / 400)));
    let s = 0;
    for (let i = 0; i < STEPS; i++) s += ease(Math.max(0, Math.min(1, (t - ROLL_AT - i * ROLL_GAP) / ROLL_MS)));
    return s * SHIFT_STEP * scale();
  };
  const pullAtTime = (t) => { const to = pullTarget(scene), q = ease(Math.min(1, (t - pullAt) / 900)); return to.map((v, i) => [pullFrom[i][0] + (v[0] - pullFrom[i][0]) * q, pullFrom[i][1] + (v[1] - pullFrom[i][1]) * q]); };

  const sheetFrame = () => {
    const sel = SCENES[scene].sheet, el = sel && film() && $(sel);
    return el ? { sheet: el.getBoundingClientRect(), alpha: Number(getComputedStyle(el).opacity) } : { sheet: null, alpha: 0 };
  };
  const drawGround = (t, now) => {
    const sc = SCENES[scene], dt = Math.min(64, now - lastNow); lastNow = now;
    if (!sc.frozen && FIXED == null && !reduced) driftS += dt / 1000;
    if (!sc.frozen && FIXED == null && !reduced) pointer = pointer.map((v, i) => v + (pointerGoal[i] - v) * 0.06);
    const stir = scene === "typing" ? 4 * Math.sin(driftS * 1.7) : 0;
    G.draw({ driftS: FIXED != null ? (sc.frozen ? 0 : t / 1000) : driftS, amp: (sc.amp || 10) + stir, pull: pullAtTime(t), shift: shiftAt(t), pointer, k: scale(), pillar: sc.pillar, ...sheetFrame() });
  };

  const frames = [];
  window.__frames = frames;
  const tick = (now) => {
    const t = sceneTime(now);
    if (controls) controls.time = Math.min(t, DURATION[scene]) / 1000;
    if (scene === "typing" || scene === "block" || scene === "argue" || scene === "held") renderCode(scene === "typing" ? t : Infinity);
    if (scene !== "miss") renderPostmark(scene === "block" ? t : scene === "argue" || scene === "held" ? Infinity : -1);
    if (scene === "block") renderThread(t);
    drawGround(t, now);
    if (frames.length < 20000 && FIXED == null) frames.push([now, scene]);
    requestAnimationFrame(tick);
  };

  // Switching scenes: hand the ground its new pull, rebuild the timeline, speak, offer the keys.
  const renderKeys = () => {
    $("#keys").replaceChildren(...SCENES[scene].keys.map((id) => {
      const [k, label, act] = KEYS[id], b = document.createElement("button");
      b.className = "key"; b.type = "button"; b.dataset.act = act; b.innerHTML = `<kbd>${k}</kbd>${label}`; return b;
    }));
  };
  const speak = () => {
    const sc = SCENES[scene];
    $("#voice-who").textContent = sc.pillar[0].toUpperCase() + sc.pillar.slice(1);
    $("#voice-line").textContent = sc.line;
    $("#voice-models").textContent = sc.pillar === "reader" ? `${K.models.reader} and ${K.models.corroborator}` : "";
    $$(".pillar").forEach((p) => p.setAttribute("aria-current", String(p.dataset.p === sc.pillar)));
  };
  const timeline = () => {
    if (controls) controls.cancel();
    controls = M ? M.animate(TIMELINES[scene]()) : null;
    if (controls) controls.pause();
  };
  const go = (name, opts = {}) => {
    const now = performance.now(), cur = FIXED != null ? pullTarget(PREV[name]) : pullAtTime(sceneTime(now));
    shiftFrom = FIXED != null ? 0 : shiftAt(sceneTime(now));
    timers.forEach(clearTimeout); timers = [];
    scene = name; started = now; pullFrom = cur; pullAt = 0;
    root.dataset.scene = name; stage.toggleAttribute("data-blocked", name !== "typing" && name !== "day" && name !== "miss");
    $("#agent-state").textContent = name === "typing" ? "editing" : "not written";
    timeline(); speak(); renderKeys();
    if (!opts.keepUrl && FIXED == null) history.replaceState(null, "", `?scene=${name}`);
    if (name === "typing" && FIXED == null && film()) later(reduced ? 1200 : DURATION.typing, () => go("block"));
  };

  // Exit on Enter or Esc: everything leaves in 300 ms, then the day; the edit is never authorised.
  const acknowledge = () => {
    if (scene === "day") return;
    if (reduced || !M) return go("day");
    const leaving = [$("#sheet"), $("#miss"), $("#stop"), $(".agent"), $("#thread")].filter((el) => el && getComputedStyle(el).display !== "none");
    if (controls) controls.complete();
    controls = null;
    M.animate(leaving, { opacity: 0, y: 18 }, { duration: 0.3, ease: [0.4, 0, 1, 1] }).then(() => { leaving.forEach((el) => (el.style.transform = "")); go("day"); });
  };
  const act = (name) => {
    if (name === "ack") return acknowledge();
    if (name === "replay") return go(scene);
    if (name === "typing" && scene !== "day") return;
    if (name === "argue" && scene !== "block") return;
    if (name === "held" && scene !== "argue") return;
    go(name);
  };

  const onKey = (e) => {
    const map = { " ": "typing", a: "argue", A: "argue", p: "held", P: "held", r: "replay", R: "replay", Escape: "ack" };
    if ((e.key === "Enter" || e.key === " ") && e.target instanceof Element && e.target.closest("button, a")) return;
    const name = e.key === "Enter" ? "ack" : map[e.key];
    if (!name || e.metaKey || e.ctrlKey) return;
    e.preventDefault(); act(name);
  };
  const ORDER = ["day", "typing", "block", "argue", "held", "miss"];
  const onClick = (e) => {
    const el = e.target instanceof Element ? e.target.closest("[data-act], [data-go], #copy") : null;
    if (el && el.id === "copy") return copy(el);
    if (el && el.dataset.go) { e.preventDefault(); return go(el.dataset.go); }
    if (el) return act(el.dataset.act);
    if (!film() && !(e.target instanceof Element && e.target.closest("a, button"))) go(ORDER[(ORDER.indexOf(scene) + 1) % ORDER.length]);
  };
  const copy = (btn) => {
    const text = $("#cmd").textContent;
    const done = () => { btn.textContent = "Copied"; later(1600, () => (btn.textContent = "Copy")); };
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(done, () => { getSelection().selectAllChildren($("#cmd")); btn.textContent = "Selected"; });
  };

  // The quote and the word Blocked are split for their rises; the text stays the same.
  const splitWords = (el) => {
    const walk = (node) => [...node.childNodes].forEach((n) => {
      if (n.nodeType === 3) n.replaceWith(...(n.textContent.match(/\s+|\S+\s*/g) || []).map((w) => (/^\s+$/.test(w) ? document.createTextNode(w) : Object.assign(document.createElement("span"), { className: "w", textContent: w }))));
      else if (n.tagName === "CODE") n.classList.add("w");
      else if (n.tagName !== "BR") walk(n);
    });
    walk(el);
  };
  const splitChars = (el) => el.replaceChildren(...[...el.textContent].map((c) => Object.assign(document.createElement("span"), { className: "ch", textContent: c })));

  const start = () => {
    audit(); fitStage(); buildHours(); splitWords($("#the-quote")); splitChars($("#blocked-word"));
    if (FIXED != null) root.classList.add("still-capture");
    const first = query.get("scene");
    go(SCENES[first] ? first : "day", { keepUrl: true });
    requestAnimationFrame((now) => { lastNow = now; tick(now); });
    requestAnimationFrame(() => requestAnimationFrame(() => (window.__ready = true)));
  };
  root.classList.add("js");
  fitStage();
  addEventListener("resize", fitStage);
  addEventListener("keydown", onKey);
  addEventListener("click", onClick);
  addEventListener("pointermove", (e) => { pointerGoal = [(e.clientX / innerWidth - 0.5) * 2, (e.clientY / innerHeight - 0.5) * 2]; });
  document.fonts.ready.then(start);
})();
