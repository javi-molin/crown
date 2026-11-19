/* CROWN · panel de concursos de belleza */
const REPO_RAW = "https://raw.githubusercontent.com/javi-molin/crown/main/";
const TZ = "America/Santiago";
const REFRESH_MS = 60000;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = encodeURIComponent;
const store = {
  get(k, d) { try { const v = localStorage.getItem("crown:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("crown:" + k, JSON.stringify(v)); } catch { } }
};
const S = { pageants: [], contestants: [], feed: { items: [] }, videos: {}, wiki: {}, status: {}, estudio: null, contenido: null,
  fContest: "", fTag: "", q: "", shown: 40, lastSeen: store.get("lastSeen", Date.now() - 6 * 3600e3), knownIds: null };
const ICON = { news: "📰", video: "▶️", social: "💬", alert: "🚨" };
const TAGL = { polemica: "Polémica", looks: "Looks", resultados: "Resultados", video: "Video", comunidad: "Comunidad", alerta: "Alerta" };

async function getJSON(name) {
  const bust = "?t=" + Math.floor(Date.now() / 30000);
  for (const base of [REPO_RAW + "data/", "data/"]) {
    try { const r = await fetch(base + name + bust, { cache: "no-store" }); if (r.ok) return await r.json(); } catch { }
  }
  return null;
}
const flag = iso => !iso || iso.length !== 2 ? "🏳️" : String.fromCodePoint(...[...iso.toUpperCase()].map(c => 127397 + c.charCodeAt()));
const fmt = (d, o) => new Intl.DateTimeFormat("es-CL", { timeZone: TZ, hourCycle: "h23", ...o }).format(new Date(d));
function ago(d) {
  const s = (Date.now() - new Date(d)) / 1000;
  if (s < 60) return "recién"; if (s < 3600) return Math.floor(s / 60) + " min";
  if (s < 86400) return Math.floor(s / 3600) + " h"; return Math.floor(s / 86400) + " d";
}
const pName = id => (S.pageants.find(p => p.id === id) || {}).name || id;
const pColor = id => (S.pageants.find(p => p.id === id) || {}).color || "#999";
const shortP = id => ({ mu: "Universe", mi: "International", me: "Earth", mw: "World", mgi: "Grand", ms: "Supra" }[id] || id);

/* ---------------- carga ---------------- */
async function loadAll(first) {
  const [p, c, ca, f, v, w, st, es, co] = await Promise.all(["pageants.json", "contestants.json", "contestants_auto.json", "feed.json",
    "videos.json", "wiki.json", "status.json", "estudio.json", "contenido.json"].map(getJSON));
  if (p) S.pageants = p.pageants;
  if (c) {
    // Wikipedia (lista automática) manda; lo manual aporta notas, IG y hot picks.
    const seed = c.contestants, auto = (ca && ca.contestants) || [];
    const key = x => x.contest + "|" + x.country;
    const autoContests = new Set(auto.map(x => x.contest));
    const seedMap = new Map(seed.map(x => [key(x), x]));
    const out = auto.map(a => ({ ...(seedMap.get(key(a)) || {}), ...a }));
    const inAuto = new Set(auto.map(key));
    for (const x of seed) if (!inAuto.has(key(x))) out.push(autoContests.has(x.contest) ? { ...x, no_wiki: true } : x);
    S.contestants = out;
  }
  if (f) {
    const prevIds = S.knownIds;
    S.feed = f; S.knownIds = new Set(f.items.map(i => i.id));
    if (prevIds && $("#notif").checked) notifyNew(f.items.filter(i => !prevIds.has(i.id)));
  }
  if (v) S.videos = v; if (w) S.wiki = w; if (st) S.status = st; if (es) S.estudio = es; if (co) S.contenido = co;
  renderPulse();
  if (first) { renderPageants(); renderContestFilters(); renderLooksStatic(); renderEstudio(); }
  renderHero(); renderAgenda(); renderChips(); renderFeed(); renderWiki(); renderBuzz(); renderCandidatas(); renderVideos();
  renderPolemicas(); renderContenido(); renderStatus();
}

function renderPulse() {
  const run = S.status.run_at || S.feed.updated;
  const el = $("#pulse");
  if (!run) { $("#pulseText").textContent = "esperando la primera corrida del robot"; el.classList.add("stale"); return; }
  const mins = (Date.now() - new Date(run)) / 60000;
  el.classList.toggle("stale", mins > 40);
  $("#pulseText").textContent = `robot: hace ${ago(run)} · ${S.feed.count || 0} notas · panel revisa cada 60 s`;
}

/* ---------------- en vivo ---------------- */
function upcoming() {
  const evs = [];
  for (const p of S.pageants) for (const e of p.events || []) evs.push({ ...e, pid: p.id, pname: p.name });
  return evs.sort((a, b) => new Date(a.start) - new Date(b.start));
}
function renderHero() {
  const now = Date.now();
  const next = upcoming().filter(e => new Date(e.end || e.start) > now - 3 * 3600e3);
  const mains = next.filter(e => e.main).slice(0, 1);
  const others = next.filter(e => !mains.includes(e)).slice(0, 2);
  const box = (e, big) => `<div class="cd ${big ? "" : "small"}" style="${big ? "" : "border-top:3px solid " + pColor(e.pid)}">
    <div class="lbl">${esc(e.pname)}</div><div class="ev">${esc(e.name)}</div>
    <div class="clock" data-t="${e.start}">--</div>
    <div class="when">${fmt(e.start, { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })} hora Chile${e.tbc ? " · hora por confirmar" : ""}</div></div>`;
  $("#hero").innerHTML = mains.map(e => box(e, true)).join("") + others.map(e => box(e)).join("");
  tick();
}
function tick() {
  for (const el of $$(".clock")) {
    let d = (new Date(el.dataset.t) - Date.now()) / 1000;
    if (d <= 0) { el.textContent = d > -4 * 3600 ? "● EN CURSO" : "terminado"; continue; }
    const D = Math.floor(d / 86400), H = Math.floor(d % 86400 / 3600), M = Math.floor(d % 3600 / 60), s = Math.floor(d % 60);
    el.textContent = (D ? D + "d " : "") + String(H).padStart(2, "0") + ":" + String(M).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }
}
function renderAgenda() {
  const now = Date.now();
  $("#agenda").innerHTML = upcoming().filter(e => new Date(e.start) > now - 5 * 86400e3).slice(0, 14).map(e =>
    `<li class="${new Date(e.end || e.start) < now ? "past" : ""}"><span class="d">${fmt(e.start, { day: "2-digit", month: "short" })}<br>${fmt(e.start, { hour: "2-digit", minute: "2-digit" })}</span>
     <span><b style="color:${pColor(e.pid)}">${shortP(e.pid)}</b> · ${esc(e.name)}${e.tbc ? " <small>hora por confirmar</small>" : ""}</span></li>`).join("");
}
function renderChips() {
  const items = S.feed.items || [];
  const cnt = (fn) => items.filter(fn).length;
  const cs = [["", "Todos", items.length], ...S.pageants.map(p => [p.id, shortP(p.id), cnt(i => (i.contests || []).includes(p.id))])];
  $("#chipsContest").innerHTML = cs.map(([id, l, n]) => `<button class="chip ${S.fContest === id ? "on" : ""}" data-c="${id}">${l}<i>${n}</i></button>`).join("");
  const ts = [["", "Todo"], ...Object.entries(TAGL)];
  $("#chipsTag").innerHTML = ts.map(([id, l]) => `<button class="chip ${S.fTag === id ? "on" : ""}" data-t="${id}">${l}${id ? `<i>${cnt(i => (i.tags || []).includes(id))}</i>` : ""}</button>`).join("");
}
function filtered(extra) {
  const q = (S.q || "").toLowerCase();
  return (S.feed.items || []).filter(i =>
    (!S.fContest || (i.contests || []).includes(S.fContest)) && (!S.fTag || (i.tags || []).includes(S.fTag)) &&
    (!q || (i.title + " " + i.source + " " + (i.who || []).map(w => w.name + " " + w.country).join(" ")).toLowerCase().includes(q)) &&
    (!extra || extra(i)));
}
function itemHTML(i) {
  const isNew = new Date(i.first_seen || i.published) > S.lastSeen;
  const who = (i.who || []).map(w => `<span class="who">${flag((S.contestants.find(c => c.country === w.country && c.contest === w.contest) || {}).iso)} ${esc(w.name)}</span>`).join(" ");
  const tags = (i.tags || []).map(t => `<span class="tag ${t}">${TAGL[t] || t}</span>`).join("");
  const cs = (i.contests || []).map(c => `<span class="tag c" style="color:${pColor(c)}">${shortP(c)}</span>`).join("");
  const thumb = i.thumb ? `<img src="${esc(i.thumb)}" loading="lazy" alt="">` : `<div class="ico">${ICON[i.type] || "📰"}</div>`;
  return `<a class="it ${isNew ? "new" : ""}" href="${esc(i.link)}" target="_blank" rel="noopener">${thumb}
    <div><div class="t">${esc(i.title)}</div>
    <div class="m"><span>${esc(i.source || "")}</span><span>· ${i.published ? ago(i.published) : ""}</span>${i.score != null ? `<span>· ▲${i.score} 💬${i.comments}</span>` : ""}</div>
    <div class="m">${cs}${tags}${who}</div></div></a>`;
}
function renderFeed() {
  const list = filtered();
  $("#feed").innerHTML = list.slice(0, S.shown).map(itemHTML).join("") || `<div class="empty">Aún no hay notas para este filtro. El robot corre cada ~10 min.</div>`;
  $("#more").style.display = list.length > S.shown ? "block" : "none";
}
function renderWiki() {
  const order = ["mu", "mi", "me"];
  $("#wiki").innerHTML = order.map(id => {
    const w = S.wiki[id]; if (!w) return "";
    const rows = (w.results || []).slice(0, 40);
    return `<p><b style="color:${pColor(id)}">${shortP(id)}</b> <small class="hint">rev. ${w.revision ? ago(w.revision) : "?"}</small></p>` +
      (rows.length ? rows.map(r => `<div class="row">${esc(r)}</div>`).join("") : `<div class="hint">Sin resultados publicados todavía. La noche de la final esta caja se llena sola.</div>`);
  }).join("") || `<div class="hint">Se activa con la primera corrida del robot.</div>`;
}
function mentions() {
  const m = {};
  for (const i of S.feed.items || []) for (const w of i.who || []) { const k = w.contest + "|" + w.country; m[k] = (m[k] || 0) + 1; }
  return m;
}
function renderBuzz() {
  const m = mentions();
  const top = Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 12);
  $("#buzz").innerHTML = top.map(([k, n]) => { const [c, country] = k.split("|"); const x = S.contestants.find(y => y.contest === c && y.country === country) || {};
    return `<li>${flag(x.iso)} <b>${esc(x.name || country)}</b> <span class="hint">${esc(x.country_es || country)} · ${shortP(c)}</span> — ${n}</li>`; }).join("") || `<li class="hint">Sin datos aún.</li>`;
}
function notifyNew(list) {
  const hot = list.filter(i => (i.tags || []).some(t => ["polemica", "alerta", "resultados"].includes(t)));
  if (!hot.length || !("Notification" in window) || Notification.permission !== "granted") return;
  hot.slice(0, 3).forEach(i => new Notification("👑 " + ((i.tags || []).includes("polemica") ? "Polémica" : "Novedad"), { body: i.title }));
}

/* ---------------- concursos ---------------- */
function renderPageants() {
  const stl = { en_curso: "● en curso", proximo: "próximo", finalizado: "finalizado 2026" };
  $("#pageants").innerHTML = S.pageants.map(p => `<div class="pg" style="--pc:${p.color}">
    <div class="st">${stl[p.status] || p.status} · ${esc(p.edition || "")}</div><h3>${esc(p.name)}</h3>
    <dl><dt>Sede</dt><dd>${esc(p.host)} · ${esc(p.venue)}</dd>
    ${p.reigning ? `<dt>Reina saliente</dt><dd>${esc(p.reigning)}</dd>` : ""}
    ${p.winner ? `<dt>Ganadora</dt><dd><b>${esc(p.winner)}</b></dd>` : ""}
    ${p.runnersup ? `<dt>Finalistas</dt><dd>${esc(p.runnersup)}</dd>` : ""}
    ${p.broadcast ? `<dt>Dónde ver</dt><dd>${esc(p.broadcast)}</dd>` : ""}
    ${p.format ? `<dt>Formato</dt><dd>${esc(p.format)}</dd>` : ""}
    ${p.entrants ? `<dt>Candidatas</dt><dd>${esc(p.entrants)}</dd>` : ""}
    <dt>Fechas</dt><dd>${(p.events || []).map(e => `${fmt(e.start, { day: "numeric", month: "short" })}: ${esc(e.name)}`).join("<br>")}</dd></dl>
    ${(p.controversies || []).length ? `<b>Polémicas</b><ul>${p.controversies.map(c => `<li>${esc(c.t)} <a href="${esc(c.src)}" target="_blank">fuente</a></li>`).join("")}</ul>` : ""}
    <div class="links">${Object.entries(p.official || {}).map(([k, u]) => `<a href="${esc(u)}" target="_blank">${k}</a>`).join("")}
      <a href="https://en.wikipedia.org/wiki/${esc(p.wiki)}" target="_blank">wikipedia</a>
      <a href="https://news.google.com/search?q=${enc(p.name)}&hl=es-419" target="_blank">noticias</a>
      ${["mu", "mi", "me"].includes(p.id) ? `<a href="#" data-goto="${p.id}">ver candidatas →</a>` : ""}</div></div>`).join("");
}

/* ---------------- candidatas ---------------- */
function renderContestFilters() {
  const ids = [...new Set(S.contestants.map(c => c.contest))];
  $("#cContest").innerHTML = ids.map(id => `<option value="${id}">${esc(pName(id))} (${S.contestants.filter(c => c.contest === id).length})</option>`).join("");
  const regs = [...new Set(S.contestants.map(c => c.region).filter(Boolean))].sort();
  $("#cRegion").innerHTML = `<option value="">Todas las regiones</option>` + regs.map(r => `<option>${r}</option>`).join("");
}
function links(c) {
  const pn = { mu: "Miss Universe", mi: "Miss International", me: "Miss Earth" }[c.contest] || "Miss";
  const nm = c.name || "";
  const q1 = `${nm} ${pn} ${c.country}`, q2 = `${pn} ${c.country_es || c.country} 2026`;
  return [
    c.ig ? ["IG", `https://www.instagram.com/${c.ig}/`] : ["IG", `https://www.google.com/search?q=${enc(`site:instagram.com "${nm}"`)}`],
    ["TikTok", `https://www.tiktok.com/search?q=${enc(nm + " " + pn)}`],
    ["Looks", `https://www.google.com/search?tbm=isch&tbs=qdr:w&q=${enc(q1)}`],
    ["YouTube", `https://www.youtube.com/results?search_query=${enc(q1)}&sp=CAI%253D`],
    ["Noticias", `https://news.google.com/search?q=${enc('"' + nm + '"')}&hl=es-419`],
    ["X", `https://x.com/search?q=${enc(q2)}&f=live`],
    ["Pinterest", `https://www.pinterest.com/search/pins/?q=${enc(q1)}`],
  ];
}
function renderCandidatas() {
  if (!S.contestants.length) return;
  const cid = $("#cContest").value || "mu", reg = $("#cRegion").value, q = ($("#cQ").value || "").toLowerCase(), onlyFav = $("#cFav").checked;
  const favs = store.get("favs", {}), ranks = store.get("ranks", {}), m = mentions();
  let list = S.contestants.filter(c => c.contest === cid && (!reg || c.region === reg) &&
    (!q || (c.name + " " + c.country + " " + c.country_es + " " + (c.hometown || "")).toLowerCase().includes(q)));
  const key = c => c.contest + "|" + c.country;
  if (onlyFav) list = list.filter(c => favs[key(c)]);
  list.sort((a, b) => (ranks[key(a)] || 999) - (ranks[key(b)] || 999) || (a.hot || 99) - (b.hot || 99) || a.country_es.localeCompare(b.country_es));
  $("#clist").innerHTML = list.map(c => { const k = key(c);
    return `<div class="cc ${favs[k] ? "fav" : ""}" data-k="${esc(k)}">
    <div class="h"><span class="flag">${flag(c.iso)}</span><div class="act">${c.hot ? `<span class="hotb">HOT #${c.hot}</span>` : ""}
      <input class="rank" type="number" min="1" placeholder="#" value="${ranks[k] || ""}" title="tu ranking"><button class="star" title="favorita">★</button></div></div>
    <div class="n">${esc(c.name)}</div>
    <div class="p">${esc(c.country_es)}${c.age ? " · " + c.age + " años" : ""}${c.hometown ? " · " + esc(c.hometown) : ""}</div>
    ${m[k] ? `<a class="ment" href="#" data-ment="${esc(k)}">${m[k]} menciones en noticias →</a>` : ""}
    ${c.no_wiki ? `<div class="nt" style="border-color:var(--rose)">Ya no figura en la lista de Wikipedia: posible retiro o reemplazo. Verificar.</div>` : ""}
    ${c.nota ? `<div class="nt">${esc(c.nota)}${c.fuente ? ` <a href="${esc(c.fuente)}" target="_blank">fuente</a>` : ""}${c.verificar ? " · <i>por confirmar</i>" : ""}</div>` : ""}
    <div class="lk">${links(c).map(([l, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener">${l}</a>`).join("")}</div></div>`; }).join("")
    || `<div class="empty">Sin resultados.</div>`;
}
function showMentions(k) {
  const [c, country] = k.split("|");
  const x = S.contestants.find(y => y.contest === c && y.country === country) || {};
  const its = (S.feed.items || []).filter(i => (i.who || []).some(w => w.contest === c && w.country === country));
  openModal(`<h2>${flag(x.iso)} ${esc(x.name)}</h2><p class="hint">${esc(x.country_es)} · ${esc(pName(c))}</p><div class="feed">${its.map(itemHTML).join("")}</div>`);
}
function exportRank() {
  const ranks = store.get("ranks", {}), cid = $("#cContest").value || "mu";
  const top = Object.entries(ranks).filter(([k]) => k.startsWith(cid + "|")).sort((a, b) => a[1] - b[1]).slice(0, 15);
  if (!top.length) { alert("Primero ponle número de ranking a tus favoritas."); return; }
  const lines = top.map(([k, n]) => { const x = S.contestants.find(y => y.contest + "|" + y.country === k) || {}; return { n, x }; });
  const txt = `MI TOP ${lines.length} DE ${pName(cid).toUpperCase()}\n\n[HOOK] Este es mi top ${lines.length} de ${pName(cid)}… y la número 1 te va a sorprender.\n\n` +
    lines.slice().reverse().map(({ n, x }) => `#${n} — ${x.country_es}: ${x.name}.\n(Por qué: …)`).join("\n\n") +
    `\n\n[CIERRE] ¿Quién falta en mi top? Te leo en comentarios. Sígueme para el minuto a minuto de la final.`;
  navigator.clipboard?.writeText(txt); addScript("Mi top " + pName(cid), txt); alert("Guion copiado y enviado a la pestaña Grabar.");
}

/* ---------------- looks y videos ---------------- */
function renderLooksStatic() {
  const q = [["Looks Miss Universe (24 h)", "https://www.google.com/search?tbm=isch&tbs=qdr:d&q=Miss+Universe+2026"],
    ["Trajes típicos MU 2026", "https://www.google.com/search?tbm=isch&q=Miss+Universe+2026+national+costume"],
    ["Vestidos de gala MU 2026", "https://www.google.com/search?tbm=isch&q=Miss+Universe+2026+evening+gown"],
    ["#missuniverse2026 en IG", "https://www.instagram.com/explore/tags/missuniverse2026/"],
    ["#missuniverso2026 en TikTok", "https://www.tiktok.com/tag/missuniverso2026"],
    ["#missuniverse2026 en TikTok", "https://www.tiktok.com/tag/missuniverse2026"],
    ["Miss International (24 h)", "https://www.google.com/search?tbm=isch&tbs=qdr:d&q=Miss+International+2026"],
    ["#missinternational2026 IG", "https://www.instagram.com/explore/tags/missinternational2026/"],
    ["Miss Earth 2026", "https://www.google.com/search?tbm=isch&tbs=qdr:w&q=Miss+Earth+2026"],
    ["Pinterest MU 2026", "https://www.pinterest.com/search/pins/?q=miss%20universe%202026"],
    ["Reels oficiales @missuniverse", "https://www.instagram.com/missuniverse/reels/"],
    ["X en vivo #MissUniverse", "https://x.com/search?q=%23MissUniverse&f=live"]];
  $("#quickLooks").innerHTML = q.map(([l, u]) => `<a href="${u}" target="_blank" rel="noopener">${l}</a>`).join("");
  $("#tt").innerHTML = `<blockquote class="tiktok-embed" cite="https://www.tiktok.com/@missuniverse" data-unique-id="missuniverse" data-embed-type="creator" style="max-width:780px;min-width:288px"><section><a target="_blank" href="https://www.tiktok.com/@missuniverse">@missuniverse</a></section></blockquote>`;
  const s = document.createElement("script"); s.src = "https://www.tiktok.com/embed.js"; s.async = true; document.body.appendChild(s);
}
function vCard(v) {
  return `<div class="v" data-vid="${esc(v.vid)}"><img src="${esc(v.thumb)}" loading="lazy" alt=""><div>${v.live ? '<span class="tag alerta">EN VIVO</span> ' : ""}${esc(v.title)}
  <small>${esc(v.channel || "")}${v.ago ? " · " + esc(v.ago) : v.published ? " · " + ago(v.published) : ""}${v.views ? " · " + esc(v.views) : ""}</small></div></div>`;
}
function renderVideos() {
  const off = (S.videos.official || []).slice().sort((a, b) => new Date(b.published) - new Date(a.published)).slice(0, 16);
  $("#vOfficial").innerHTML = off.map(vCard).join("") || `<div class="empty">Se llena con la primera corrida del robot.</div>`;
  $("#vSearch").innerHTML = (S.videos.search || []).slice(0, 24).map(vCard).join("") || `<div class="empty">Se llena con la primera corrida del robot.</div>`;
  const mu = (S.videos.channels || {}).mu;
  if (mu && !$("#live iframe")) $("#live").innerHTML = `<iframe src="https://www.youtube.com/embed/live_stream?channel=${mu.id}" allowfullscreen></iframe>`;
  else if (!mu) $("#live").innerHTML = `<div class="empty">Esperando que el robot resuelva el canal oficial.</div>`;
}

/* ---------------- polémicas ---------------- */
function renderPolemicas() {
  $("#polCurated").innerHTML = S.pageants.flatMap(p => (p.controversies || []).map(c => `<div class="card"><small style="color:${p.color}">${esc(p.name)}</small><p>${esc(c.t)}</p><a href="${esc(c.src)}" target="_blank">fuente</a>
    <div class="btns" style="margin-top:8px"><button class="ghost" data-script="${esc(c.t)}" data-pname="${esc(p.name)}">→ guion</button></div></div>`)).join("");
  $("#polFeed").innerHTML = (S.feed.items || []).filter(i => (i.tags || []).includes("polemica")).slice(0, 60).map(itemHTML).join("") || `<div class="empty">Nada detectado aún.</div>`;
}

/* ---------------- estudio y contenido ---------------- */
function md(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>"); }
function table(t) {
  return `<div class="tbl"><table><thead><tr>${t.cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${t.rows.map(r => `<tr>${r.map(x => `<td>${md(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function renderEstudio() {
  const e = S.estudio;
  if (!e) { $("#estudioBody").innerHTML = `<div class="empty">Fase 2 en preparación: auditoría de cuentas del nicho.</div>`; return; }
  $("#estudioBody").innerHTML = `<div class="doc"><h2>${esc(e.title)}</h2><p>${md(e.intro)}</p>
   <div class="kpis">${(e.kpis || []).map(k => `<div class="kpi"><b>${esc(k.v)}</b><span>${esc(k.l)}</span></div>`).join("")}</div>
   ${(e.sections || []).map(s => `<h3>${esc(s.title)}</h3>${s.text ? `<p>${md(s.text)}</p>` : ""}${s.table ? table(s.table) : ""}${s.bullets ? `<ul>${s.bullets.map(b => `<li>${md(b)}</li>`).join("")}</ul>` : ""}`).join("")}
   ${e.sources ? `<h3>Fuentes</h3><ul>${e.sources.map(s => `<li><a href="${esc(s.u)}" target="_blank">${esc(s.t)}</a></li>`).join("")}</ul>` : ""}</div>`;
}
function autoScripts() {
  const pick = (S.feed.items || []).filter(i => !["video", "alert"].includes(i.type) && (i.tags || []).some(t => ["polemica", "looks", "resultados"].includes(t))).slice(0, 10);
  return pick.map(i => {
    const w = (i.who || [])[0]; const who = w ? `${w.name} (${(S.contestants.find(c => c.country === w.country) || {}).country_es || w.country})` : "esta candidata";
    const t = (i.tags || []).includes("polemica") ? "polemica" : (i.tags || []).includes("looks") ? "looks" : "resultados";
    const hook = { polemica: `¿Viste lo que está pasando con ${who}? Te lo explico en 30 segundos.`, looks: `Este look de ${who} está dividiendo a todo el mundo… ¿10 o 4?`, resultados: `Ojo con esto que acaba de pasar en ${pName((i.contests || [])[0] || "mu")}.` }[t];
    return { id: "auto-" + i.id, title: i.title, format: "Reacción / noticia rápida (30–45 s)", platform: "TikTok + Reels", pillar: "Al minuto", auto: true,
      guion: `[HOOK 0–3 s] ${hook}\n\n[CONTEXTO] ${i.title}. (Fuente: ${i.source})\n\n[TU OPINIÓN] Para mí… (di qué piensas y por qué, en una frase clara).\n\n[PREGUNTA] ¿Tú qué opinas? ¿Team sí o team no?\n\n[CTA] Sígueme: cubro ${shortP((i.contests || [])[0] || "mu")} minuto a minuto.`,
      link: i.link };
  });
}
function ideaHTML(x) {
  return `<div class="idea"><div class="top2"><div><div class="meta">${esc(x.pillar || "")} · ${esc(x.format || "")} · ${esc(x.platform || "")}${x.when ? " · " + esc(x.when) : ""}${x.priority ? " · prioridad " + esc(x.priority) : ""}</div><h4>${esc(x.title)}</h4></div></div>
   ${x.why ? `<p class="hint">${md(x.why)}</p>` : ""}<pre>${esc(x.guion || "")}</pre>
   ${x.broll ? `<p><b>Tomas / B-roll:</b> ${esc(x.broll.join(" · "))}</p>` : ""}
   ${x.caption ? `<p><b>Caption:</b> ${esc(x.caption)}</p>` : ""}${x.hashtags ? `<p class="hint">${esc(x.hashtags)}</p>` : ""}
   <div class="btns"><button class="ghost" data-copy="${esc(x.id)}">Copiar</button><button data-tp="${esc(x.id)}">→ Teleprompter</button>${x.link ? `<a href="${esc(x.link)}" target="_blank">ver fuente</a>` : ""}</div></div>`;
}
let IDEAS = {};
function renderContenido() {
  const co = S.contenido || {}; const auto = autoScripts();
  const ideas = (co.ideas || []);
  IDEAS = Object.fromEntries([...ideas, ...auto].map(x => [x.id, x]));
  const pillars = [...new Set(ideas.map(i => i.pillar))];
  const f = store.get("pillar", "");
  $("#contenidoBody").innerHTML = `<div class="doc">
    <h2>${esc(co.title || "Propuestas de contenido")}</h2>${co.intro ? `<p>${md(co.intro)}</p>` : ""}
    ${co.calendar ? `<h3>Calendario de esta semana</h3>${table(co.calendar)}` : ""}
    <h3>Guiones automáticos con lo de hoy</h3><p class="hint">Se regeneran solos con las notas más nuevas de polémicas, looks y resultados.</p>
    ${auto.map(ideaHTML).join("") || `<div class="empty">Aparecen cuando el robot traiga noticias.</div>`}
    ${ideas.length ? `<h3>Banco de ideas</h3><div class="sel">${["", ...pillars].map(p => `<button class="chip ${f === p ? "on" : ""}" data-pillar="${esc(p)}">${esc(p || "Todas")}</button>`).join("")}</div>
    ${ideas.filter(i => !f || i.pillar === f).map(ideaHTML).join("")}` : `<div class="empty">Banco de ideas en preparación (fase 2).</div>`}
    ${co.extras ? co.extras.map(s => `<h3>${esc(s.title)}</h3>${s.text ? `<p>${md(s.text)}</p>` : ""}${s.table ? table(s.table) : ""}${s.bullets ? `<ul>${s.bullets.map(b => `<li>${md(b)}</li>`).join("")}</ul>` : ""}`).join("") : ""}
  </div>`;
  const sel = $("#tpPick"); const cur = sel.value;
  const mine = store.get("scripts", []);
  sel.innerHTML = `<option value="">Elegir guion…</option>` + mine.map((m, ix) => `<option value="mine-${ix}">✎ ${esc(m.t)}</option>`).join("") +
    Object.values(IDEAS).map(x => `<option value="${esc(x.id)}">${x.auto ? "⚡ " : ""}${esc(x.title)}</option>`).join("");
  sel.value = cur;
}
function addScript(t, txt) { const m = store.get("scripts", []); m.unshift({ t, txt }); store.set("scripts", m.slice(0, 30)); renderContenido(); }

/* ---------------- teleprompter ---------------- */
const TP = { y: 0, run: false, last: 0 };
function tpLoad(txt) { $("#tpText").value = txt; $("#tpInner").textContent = txt; TP.y = 0; tpApply(); }
function tpApply() { const inner = $("#tpInner"); inner.style.fontSize = $("#tpSize").value + "px"; inner.style.transform = `translateY(${-TP.y}px)` + ($("#tpMirror").checked ? " scaleX(-1)" : ""); }
function tpLoop(t) {
  if (!TP.run) return; const dt = TP.last ? (t - TP.last) / 1000 : 0; TP.last = t;
  TP.y += dt * $("#tpSpeed").value * 12; tpApply(); requestAnimationFrame(tpLoop);
}
function tpToggle() { TP.run = !TP.run; TP.last = 0; $("#tpGo").textContent = TP.run ? "❚❚ Pausa" : "▶ Iniciar"; if (TP.run) requestAnimationFrame(tpLoop); }

/* ---------------- fuentes ---------------- */
function renderStatus() {
  const st = S.status; if (!st.sources) { $("#status").innerHTML = `<div class="empty">El robot todavía no corre. Revisa la pestaña Actions del repositorio.</div>`; return; }
  const ok = st.sources.filter(s => s.ok).length;
  $("#status").innerHTML = `<div class="kpis"><div class="kpi"><b>${ago(st.run_at)}</b><span>última corrida</span></div><div class="kpi"><b>${ok}/${st.sources.length}</b><span>fuentes OK</span></div>
   <div class="kpi"><b>${st.new_items ?? 0}</b><span>notas nuevas en la última corrida</span></div><div class="kpi"><b>${st.total_items ?? 0}</b><span>notas en memoria (30 días)</span></div></div>
   ${table({ cols: ["Fuente", "Estado", "Ítems", "Detalle"], rows: st.sources.map(s => [s.source, s.ok ? "✅" : "⚠️", String(s.items || 0), s.error || ""]) })}`;
}

/* ---------------- modal / eventos ---------------- */
function openModal(h) { $("#mbody").innerHTML = h; $("#modal").hidden = false; }
document.addEventListener("click", e => {
  const t = e.target.closest("[data-tab],[data-c],[data-t],[data-goto],.star,[data-ment],.v,[data-copy],[data-tp],[data-pillar],[data-script]");
  if (!t) return;
  if (t.dataset.tab) { $$(".tabs button").forEach(b => b.classList.toggle("on", b === t)); $$(".tab").forEach(s => s.classList.toggle("on", s.id === t.dataset.tab)); location.hash = t.dataset.tab; if (t.dataset.tab === "vivo") markSeenSoon(); return; }
  if (t.dataset.c !== undefined) { S.fContest = t.dataset.c; S.shown = 40; renderChips(); renderFeed(); return; }
  if (t.dataset.t !== undefined) { S.fTag = t.dataset.t; S.shown = 40; renderChips(); renderFeed(); return; }
  if (t.dataset.goto) { e.preventDefault(); $("#cContest").value = t.dataset.goto; $('[data-tab="candidatas"]').click(); renderCandidatas(); return; }
  if (t.classList.contains("star")) { const k = t.closest(".cc").dataset.k, f = store.get("favs", {}); f[k] = !f[k]; store.set("favs", f); renderCandidatas(); return; }
  if (t.dataset.ment) { e.preventDefault(); showMentions(t.dataset.ment); return; }
  if (t.classList.contains("v")) { openModal(`<div class="ratio"><iframe src="https://www.youtube.com/embed/${t.dataset.vid}?autoplay=1" allow="autoplay; fullscreen" allowfullscreen></iframe></div><p><a href="https://www.youtube.com/watch?v=${t.dataset.vid}" target="_blank">abrir en YouTube</a></p>`); return; }
  if (t.dataset.copy) { navigator.clipboard?.writeText(IDEAS[t.dataset.copy].guion); t.textContent = "¡Copiado!"; return; }
  if (t.dataset.tp) { tpLoad(IDEAS[t.dataset.tp].guion); $('[data-tab="grabar"]').click(); return; }
  if (t.dataset.pillar !== undefined) { store.set("pillar", t.dataset.pillar); renderContenido(); return; }
  if (t.dataset.script) { const txt = `[HOOK] Nadie te está contando esto de ${t.dataset.pname}…\n\n[CONTEXTO] ${t.dataset.script}\n\n[MI OPINIÓN] …\n\n[PREGUNTA] ¿Crees que esto afecta el resultado?\n\n[CTA] Sígueme para el minuto a minuto.`; addScript("Polémica · " + t.dataset.pname, txt); tpLoad(txt); $('[data-tab="grabar"]').click(); }
});
$("#mx").onclick = () => { $("#modal").hidden = true; $("#mbody").innerHTML = ""; };
$("#modal").onclick = e => { if (e.target.id === "modal") $("#mx").click(); };
$("#q").oninput = e => { S.q = e.target.value; renderFeed(); };
$("#more").onclick = () => { S.shown += 40; renderFeed(); };
$("#notif").onchange = e => { if (e.target.checked && "Notification" in window) Notification.requestPermission(); };
["cContest", "cRegion", "cFav"].forEach(id => $("#" + id).onchange = renderCandidatas);
$("#cQ").oninput = renderCandidatas;
$("#clist").addEventListener("change", e => { if (!e.target.classList.contains("rank")) return; const k = e.target.closest(".cc").dataset.k, r = store.get("ranks", {}); const v = parseInt(e.target.value); if (v) r[k] = v; else delete r[k]; store.set("ranks", r); });
$("#exportRank").onclick = exportRank;
$("#tpPick").onchange = e => { const v = e.target.value; if (!v) return; if (v.startsWith("mine-")) tpLoad(store.get("scripts", [])[+v.slice(5)].txt); else tpLoad(IDEAS[v].guion); };
$("#tpText").oninput = e => { $("#tpInner").textContent = e.target.value; };
$("#tpGo").onclick = tpToggle; ["tpSize", "tpMirror"].forEach(id => $("#" + id).oninput = () => { tpApply(); $("#tp").classList.toggle("mirror", $("#tpMirror").checked); });
$("#tpFull").onclick = () => $("#tp").requestFullscreen?.();
document.addEventListener("keydown", e => {
  if (!$("#grabar").classList.contains("on") || e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
  if (e.code === "Space") { e.preventDefault(); tpToggle(); }
  if (e.code === "ArrowUp") $("#tpSpeed").value = +$("#tpSpeed").value + 1;
  if (e.code === "ArrowDown") $("#tpSpeed").value = +$("#tpSpeed").value - 1;
});
function markSeenSoon() { setTimeout(() => { S.lastSeen = Date.now(); store.set("lastSeen", S.lastSeen); }, 15000); }

/* ---------------- arranque ---------------- */
(async () => {
  const h = location.hash.slice(1); if (h && $(`[data-tab="${h}"]`)) $(`[data-tab="${h}"]`).click();
  await loadAll(true); markSeenSoon();
  setInterval(tick, 1000);
  setInterval(() => loadAll(false), REFRESH_MS);
})();
