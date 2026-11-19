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
const S = { events: [], idx: {}, pageants: [], contestants: [], feed: { items: [] }, videos: {}, wiki: {}, status: {}, estudio: null, contenido: null,
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
  const [p, c, ca, f, v, w, st, es, co, evs, gal] = await Promise.all(["pageants.json", "contestants.json", "contestants_auto.json", "feed.json",
    "videos.json", "wiki.json", "status.json", "estudio.json", "contenido.json", "events.json", "gallery.json"].map(getJSON));
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
  if (evs) S.events = evs.events || [];
  if (gal) S.gallery = gal;
  if (f) for (const i of f.items) S.idx["feed:" + i.id] = { type: i.type === "video" ? "video" : "nota", title: i.title, url: i.link, img: i.thumb || "", source: i.source, date: i.published };
  if (v) S.videos = v; if (w) S.wiki = w; if (st) S.status = st; if (es) S.estudio = es; if (co) S.contenido = co;
  renderPulse();
  if (first) { renderPageants(); renderContestFilters(); renderLooksStatic(); renderEstudio(); }
  renderHero(); renderAgenda(); renderChips(); renderFeed(); renderWiki(); renderBuzz(); renderCandidatas(); renderVideos();
  renderPolemicas(); renderContenido(); renderStatus(); renderEvents(); renderBasketBtn();
  if (first) initGallery(); renderGallery(); renderIG();
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
    <div class="lbl">${esc(e.pname)}</div><div class="evn">${esc(e.name)}</div>
    <div class="clock" data-t="${e.start}">--</div>
    <div class="when">${fmt(e.start, { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })} hora Chile${e.tbc ? " · hora por confirmar" : ""}</div></div>`;
  $("#hero").innerHTML = mains.map(e => box(e, true)).join("") + others.map(e => box(e)).join("");
  const nx = mains[0] || others[0];
  $("#nextChip").innerHTML = nx ? `${esc(shortP(nx.pid))} · ${esc(nx.name.replace(/ —.*/, ""))}<b class="clock" data-t="${nx.start}"></b>` : "";
  const its = S.feed.items || [], day = Date.now() - 864e5;
  const n24 = its.filter(i => new Date(i.first_seen || i.published) > day);
  const actEv = (S.events || []).filter(e => !e.upcoming && new Date(e.last_activity) > Date.now() - 2 * 864e5).length;
  $("#tiles").innerHTML = [["vivo", n24.length, "notas nuevas en 24 h", ""], ["polemicas", n24.filter(i => (i.tags || []).includes("polemica")).length, "polémicas en 24 h", ""],
    ["eventos", actEv, "eventos activos", ""], ["galeria", Object.values((S.gallery || {}).cells || {}).reduce((a, c) => a + (c.images || []).length, 0), "fotos en la galería", ""]]
    .map(([tab, n, l]) => `<button class="tile" data-tab="${tab}"><b>${n}</b><span>${l}</span></button>`).join("");
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
    <div class="m">${cs}${tags}${who}</div></div>${mkBtn("feed:" + i.id)}</a>`;
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
    return `<li data-prof="${esc(k)}">${flag(x.iso)} <b>${esc(x.name || country)}</b> <span class="hint">${esc(x.country_es || country)}</span><span class="n">${n}</span></li>`; }).join("") || `<li class="hint">Sin datos aún.</li>`;
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
  $("#clist").innerHTML = list.map(c => { const k = key(c), ph = photoOf(c);
    return `<div class="pc ${favs[k] ? "fav" : ""}" data-k="${esc(k)}" data-prof="${esc(k)}">
     <div class="ph">${ph ? imgTag(ph) : `<span class="bigflag">${flag(c.iso)}</span><span class="loading">buscando fotos…</span>`}${c.hot ? `<span class="cnt" style="background:var(--rose)">HOT #${c.hot}</span>` : ""}</div>
     <div class="info"><div class="n">${flag(c.iso)} ${esc(c.name)}</div><div class="p">${esc(c.country_es)}${c.age ? " · " + c.age : ""}${c.no_wiki ? " · <span style='color:var(--rose)'>verificar</span>" : ""}</div>
     <div class="row">${m[k] ? `<span class="ment">${m[k]} notas</span>` : "<span></span>"}<span><input class="rank" type="number" min="1" placeholder="#" value="${ranks[k] || ""}" title="Tu ranking"><button class="star" title="Favorita">★</button></span></div></div></div>`; }).join("")
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
  S.idx["yt:" + v.vid] = { type: "video", title: v.title, url: "https://www.youtube.com/watch?v=" + v.vid, img: v.thumb, source: v.channel, views: v.views || v.views_n || "" };
  return `<div class="v" data-vid="${esc(v.vid)}">${mkBtn("yt:" + v.vid)}<img src="${esc(v.thumb)}" loading="lazy" alt=""><div>${v.live ? '<span class="tag alerta">EN VIVO</span> ' : ""}${esc(v.title)}
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
  const m = e.target.closest(".mk");
  if (m) { e.preventDefault(); e.stopPropagation(); bToggle(m.dataset.mk); m.classList.toggle("on", bHas(m.dataset.mk)); m.textContent = bHas(m.dataset.mk) ? "★" : "☆"; return; }
  const t = e.target.closest("[data-tab],[data-c],[data-t],[data-goto],.star,[data-ment],.v,[data-copy],[data-tp],[data-pillar],[data-script]");
  if (!t) return;
  if (t.dataset.tab) { $("#moreMenu").hidden = true; $$(".tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === t.dataset.tab)); window.scrollTo({ top: 0 }); $$(".tab").forEach(s => s.classList.toggle("on", s.id === t.dataset.tab)); location.hash = t.dataset.tab; if (t.dataset.tab === "vivo") markSeenSoon(); return; }
  if (t.dataset.c !== undefined) { S.fContest = t.dataset.c; S.shown = 40; renderChips(); renderFeed(); return; }
  if (t.dataset.t !== undefined) { S.fTag = t.dataset.t; S.shown = 40; renderChips(); renderFeed(); return; }
  if (t.dataset.goto) { e.preventDefault(); $("#cContest").value = t.dataset.goto; $('[data-tab="candidatas"]').click(); renderCandidatas(); return; }
  if (t.classList.contains("star")) { e.stopPropagation(); const k = t.closest("[data-k]").dataset.k, f = store.get("favs", {}); f[k] = !f[k]; store.set("favs", f); renderCandidatas(); return; }
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
$("#clist").addEventListener("change", e => { if (!e.target.classList.contains("rank")) return; const k = e.target.closest("[data-k]").dataset.k, r = store.get("ranks", {}); const v = parseInt(e.target.value); if (v) r[k] = v; else delete r[k]; store.set("ranks", r); });
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

/* ================= EVENTOS · SELECCIÓN · HOT PICKS · EXPORTAR ================= */
const KIND = k => /agenda/.test(k) ? ["agenda", "Agenda oficial"] : /oficial|campaña/.test(k) ? ["oficial", k] : k === "propio" ? ["mio", "Mío"] : ["det", k === "detectado" ? "Detectado" : k];
const num = n => n == null || n === "" ? "–" : n >= 1e6 ? (n / 1e6).toFixed(1).replace(".0", "") + " M" : n >= 1e3 ? Math.round(n / 1e3) + " mil" : String(n);
const fname = s => (s || "x").normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-zA-Z0-9]+/g, "-").slice(0, 50).toLowerCase();
S.evFilter = { c: "", k: "" };

/* ---- selección (canasta) ---- */
function basket() { return store.get("basket", {}); }
function bHas(id) { return !!basket()[id]; }
function bToggle(id, obj) {
  const b = basket();
  if (b[id]) delete b[id]; else b[id] = { ...(obj || S.idx[id] || { title: id }), added: new Date().toISOString() };
  store.set("basket", b); renderBasketBtn();
}
function bAdd(id, obj) { const b = basket(); b[id] = { ...(obj || S.idx[id]), added: new Date().toISOString() }; store.set("basket", b); renderBasketBtn(); }
function mkBtn(id) { const on = bHas(id); return `<button class="mk ${on ? "on" : ""}" data-mk="${esc(id)}" title="Marcar para exportar">${on ? "★" : "☆"}</button>`; }
function renderBasketBtn() { const n = Object.keys(basket()).length; $("#basketN").textContent = n; }

/* ---- eventos propios ---- */
function myEvents() { return store.get("myEvents", []); }
function allEvents() { return [...myEvents().map(e => ({ ...e, kind: "propio" })), ...S.events]; }
function evById(id) { return allEvents().find(e => e.id === id); }

function renderEvents() {
  const evs = allEvents(), q = ($("#evQ").value || "").toLowerCase(), now = Date.now();
  const cs = [["", "Todos"], ...[...new Set(evs.map(e => e.contest))].map(c => [c, shortP(c)])];
  $("#evChipsC").innerHTML = cs.map(([id, l]) => `<button class="chip ${S.evFilter.c === id ? "on" : ""}" data-evc="${id}">${l}<i>${evs.filter(e => !id || e.contest === id).length}</i></button>`).join("");
  const ks = [["", "Todo"], ["oficial", "Oficiales y campañas"], ["det", "Detectados"], ["agenda", "Agenda / próximos"], ["mio", "Míos"]];
  $("#evChipsK").innerHTML = ks.map(([id, l]) => `<button class="chip ${S.evFilter.k === id ? "on" : ""}" data-evk="${id}">${l}</button>`).join("");
  const list = evs.filter(e => (!S.evFilter.c || e.contest === S.evFilter.c) && (!S.evFilter.k || KIND(e.kind)[0] === S.evFilter.k) && (!q || (e.name + " " + (e.labels || []).join(" ")).toLowerCase().includes(q)))
    .sort((a, b) => (KIND(a.kind)[0] === "agenda") - (KIND(b.kind)[0] === "agenda") || new Date(b.last_activity || b.start) - new Date(a.last_activity || a.start));
  const hp = store.get("hotpicks", {});
  $("#evList").innerHTML = list.map(e => {
    const [kc, kl] = KIND(e.kind), img = (e.images || [])[0];
    const st = e.social_totals || {};
    return `<div class="ev" style="--pc:${pColor(e.contest)}">
      <div class="cover" data-ev="${esc(e.id)}" style="background-image:${img ? `url('${esc(img.alt || img.url)}')` : "linear-gradient(135deg,#231a0e,#17121c)"}"><span class="kb k ${kc}">${esc(kl)}</span></div>
      <div class="b"><h4 data-ev="${esc(e.id)}">${esc(e.name)}</h4>
      <div class="d">${shortP(e.contest)} · ${e.upcoming ? "próximo: " + fmt(e.start, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "desde " + fmt(e.start || e.first_seen, { day: "numeric", month: "short" }) + " · última actividad hace " + ago(e.last_activity || e.start)}</div>
      <div class="met"><span>📰 <b>${e.n_items || 0}</b> notas</span><span>🗞 <b>${e.n_sources || 0}</b> medios</span><span>▶ <b>${num(e.views_total)}</b> vistas YT</span><span>🖼 <b>${(e.images || []).length}</b></span>${(e.social || []).length ? `<span>📱 <b>${e.social.length}</b> posts${st.likes ? " · ♥ " + num(st.likes) : ""}${st.views ? " · ▶ " + num(st.views) : ""}</span>` : ""}${(hp[e.id] || []).length ? `<span>👑 <b>${hp[e.id].length}</b> hot picks</span>` : ""}</div>
      <div class="act"><button data-ev="${esc(e.id)}">Abrir</button>${mkBtn("ev:" + e.id)}</div></div></div>`;
  }).join("") || `<div class="empty">Aún no hay eventos con este filtro.</div>`;
  for (const e of evs) S.idx["ev:" + e.id] = { type: "evento", title: e.name, url: location.href.split("#")[0] + "#ev=" + e.id, img: (e.images || [])[0]?.url || "", source: shortP(e.contest), views: e.views_total };
}

function openEvent(id) {
  const e = evById(id); if (!e) return;
  const items = (e.item_ids || []).map(i => (S.feed.items || []).find(x => x.id === i)).filter(Boolean);
  const manual = store.get("manualStats", {}), myPosts = store.get("myPosts", {})[id] || [];
  const posts = [...(e.social || []), ...myPosts.filter(u => !(e.social || []).some(p => p.url === u)).map(u => ({ url: u, platform: /tiktok/.test(u) ? "TikTok" : /instagram/.test(u) ? "Instagram" : /youtu/.test(u) ? "YouTube" : "Web", mine: true }))];
  (e.images || []).forEach((im, n) => S.idx[`img:${id}:${n}`] = { type: "imagen", title: `${e.name} · imagen ${n + 1}`, url: im.url, alt: im.alt, img: im.alt || im.url, source: im.via || im.credit, page: im.page, event: e.name });
  (e.videos || []).forEach(v => S.idx["yt:" + v.vid] = { type: "video", title: v.title, url: "https://www.youtube.com/watch?v=" + v.vid, img: `https://i.ytimg.com/vi/${v.vid}/hqdefault.jpg`, source: v.channel, views: v.views, event: e.name });
  posts.forEach(p => S.idx["post:" + p.url] = { type: "post", title: p.title || p.url, url: p.url, img: p.thumb || "", source: p.platform + (p.author ? " · @" + p.author : ""), views: p.views ?? manual[p.url]?.views, likes: p.likes ?? manual[p.url]?.likes, event: e.name });
  const [kc, kl] = KIND(e.kind);
  openDrawer(`<div class="evm" data-evid="${esc(id)}">
   <span class="kb ${kc}">${esc(kl)}</span> <span class="hint">${esc(pName(e.contest))}</span>
   <h2 style="margin:6px 0">${esc(e.name)}</h2>
   ${e.desc ? `<p>${esc(e.desc)}</p>` : ""}${(e.refs || []).length ? `<p class="hint">Fuentes: ${e.refs.map((r, n) => `<a href="${esc(r)}" target="_blank">${n + 1}</a>`).join(" · ")}</p>` : ""}
   <div class="met"><span>📰 <b>${e.n_items || items.length}</b> notas</span><span>🗞 <b>${e.n_sources || 0}</b> medios</span><span>▶ <b>${num(e.views_total)}</b> vistas en YouTube</span><span>🖼 <b>${(e.images || []).length}</b> imágenes</span><span>📱 <b>${posts.length}</b> publicaciones</span></div>
   <div class="toolbar"><button data-evzip="${esc(id)}">⬇ Exportar evento completo (ZIP)</button>${mkBtn("ev:" + id)} <span class="prog" id="prog"></span></div>

   <h3 class="sub">👑 Mis hot picks para este evento</h3><div id="hpBox"></div>

   <h3 class="sub">🖼 Imágenes listas para descargar</h3>
   <div class="toolbar"><button class="ghost" data-selall>Seleccionar todas</button><button data-dlsel>⬇ Descargar seleccionadas (ZIP)</button><button class="ghost" data-addsel>★ Marcar seleccionadas</button>
     <a href="https://www.google.com/search?tbm=isch&tbs=qdr:w&q=${enc(e.image_query || e.name)}" target="_blank">más en Google Imágenes →</a></div>
   <div class="igrid">${(e.images || []).map((im, n) => `<div class="ig" data-k="img:${esc(id)}:${n}"><input type="checkbox" class="isel"><img src="${esc(im.alt || im.url)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.closest('.ig').style.display='none'">
     <div class="tools"><a href="${esc(im.page || im.url)}" target="_blank" title="${esc(im.via || "")}">${esc((im.via || "fuente").slice(0, 16))}</a><span><button data-dl="img:${esc(id)}:${n}">⬇</button> ${mkBtn(`img:${id}:${n}`)}</span></div></div>`).join("") || `<div class="empty">Sin imágenes todavía: el robot las busca en la próxima corrida.</div>`}</div>
   <p class="hint">Imágenes de medios, miniaturas de YouTube, Bing Imágenes y Wikimedia Commons. Úsalas con crédito y para comentario editorial.</p>

   <h3 class="sub">📱 Publicaciones y estadísticas</h3>
   ${posts.map(p => { const m = manual[p.url] || {}; return `<div class="sp"><div><b>${esc(p.platform || "")}</b> ${p.author ? "@" + esc(p.author) : ""} <a href="${esc(p.url)}" target="_blank">abrir</a><br><small>${esc((p.title || p.url).slice(0, 140))}</small><br>
      <small>${p.views != null ? "▶ " + num(p.views) + " " : ""}${p.likes != null ? "♥ " + num(p.likes) + " " : ""}${p.comments != null ? "💬 " + num(p.comments) + " " : ""}${p.shares != null ? "↗ " + num(p.shares) : ""}${p.fetched ? " · leído " + ago(p.fetched) : p.mine ? " · agregado por ti" : ""}${p.error ? " · la plataforma no entregó datos" : ""}</small></div>
      <div>♥ <input data-ms="${esc(p.url)}|likes" placeholder="likes" value="${esc(m.likes || "")}"> ▶ <input data-ms="${esc(p.url)}|views" placeholder="vistas" value="${esc(m.views || "")}"> ${mkBtn("post:" + p.url)}</div></div>`; }).join("") || `<p class="hint">Todavía no hay publicaciones incrustadas en las notas de este evento.</p>`}
   <div class="toolbar"><input id="newPost" type="search" placeholder="Pega el link de un post de Instagram/TikTok/YouTube" style="flex:1"><button data-addpost="${esc(id)}">+ Agregar</button>
     <a href="https://github.com/javi-molin/crown/edit/main/data/watch.json" target="_blank">que el robot lo siga →</a></div>
   <p class="hint">TikTok y YouTube suelen entregar vistas y likes. Instagram casi nunca los muestra sin cuenta: puedes anotarlos a mano y se exportan igual. Para que el robot siga un post, agrégalo en <code>data/watch.json</code> como <code>{"url": "...", "event": "${esc(id)}"}</code>.</p>

   <h3 class="sub">▶ Videos (${(e.videos || []).length})</h3>
   <div class="vgrid">${(e.videos || []).map(v => vCard({ ...v, thumb: `https://i.ytimg.com/vi/${v.vid}/hqdefault.jpg`, views: v.views != null ? num(v.views) + " vistas" : "" })).join("") || `<p class="hint">Sin videos asociados.</p>`}</div>

   <h3 class="sub">📰 Notas (${items.length})</h3><div class="feed">${items.map(itemHTML).join("")}</div>
  </div>`);
  renderHotpicks(id);
  history.replaceState(null, "", "#ev=" + id);
}

/* ---- hot picks ---- */
function renderHotpicks(id) {
  const e = evById(id); const hp = store.get("hotpicks", {}); const list = hp[id] || [];
  const pool = S.contestants.filter(c => c.contest === e.contest);
  $("#hpBox").innerHTML = `
   ${list.map((x, n) => `<div class="hp"><b>${n + 1}</b><div>${flag(x.iso)} <b style="font:inherit;color:var(--ink)">${esc(x.name)}</b> <span class="hint">${esc(x.country || "")}</span><input data-hpnote="${n}" placeholder="por qué (aparece en el guion)" value="${esc(x.note || "")}"></div>
     <div class="ar"><button data-hpmv="${n}|-1">↑</button><button data-hpmv="${n}|1">↓</button><button data-hpdel="${n}">✕</button></div></div>`).join("") || `<p class="hint">Agrega candidatas en orden: la primera es tu #1.</p>`}
   <div class="toolbar"><input id="hpAdd" list="hpList" placeholder="Escribe país o nombre y presiona Enter" style="flex:1"><datalist id="hpList">${pool.map(c => `<option value="${esc(c.country_es)} — ${esc(c.name)}">`).join("")}</datalist>
    <button class="ghost" data-hpcopy="${esc(id)}">Copiar como guion</button><button class="ghost" data-hptp="${esc(id)}">→ Teleprompter</button><button class="ghost" data-hpstar="${esc(id)}">★ Marcar hot picks</button></div>`;
  const inp = $("#hpAdd");
  inp.onkeydown = ev => {
    if (ev.key !== "Enter" || !inp.value.trim()) return;
    const v = inp.value.trim(), c = pool.find(c => v === `${c.country_es} — ${c.name}`) || pool.find(c => c.country_es.toLowerCase() === v.toLowerCase() || c.name.toLowerCase() === v.toLowerCase());
    const all = store.get("hotpicks", {}); (all[id] = all[id] || []).push(c ? { name: c.name, country: c.country_es, iso: c.iso } : { name: v, country: "", iso: "" });
    store.set("hotpicks", all); renderHotpicks(id); renderEvents(); $("#hpAdd").focus();
  };
}
function hpText(id) {
  const e = evById(id), list = (store.get("hotpicks", {})[id] || []);
  if (!list.length) return "";
  return `HOT PICKS · ${e.name.toUpperCase()}\n\n[HOOK] Mis hot picks de ${e.name}… y la #1 te va a sorprender.\n\n` +
    list.slice().reverse().map((x, n) => `#${list.length - n} — ${x.country ? x.country + ": " : ""}${x.name}.${x.note ? " " + x.note : " (Por qué: …)"}`).join("\n\n") +
    `\n\n[CIERRE] ¿Quién falta en mis hot picks? Te leo en comentarios.`;
}
function hpEdit(fn) { const id = $(".evm").dataset.evid, all = store.get("hotpicks", {}); all[id] = fn(all[id] || []); store.set("hotpicks", all); renderHotpicks(id); renderEvents(); }

/* ---- descargas ---- */
async function fetchBlob(url) {
  for (const u of [url, "https://images.weserv.nl/?url=" + enc(url)]) {
    try { const r = await fetch(u, { mode: "cors", referrerPolicy: "no-referrer" }); if (r.ok) { const b = await r.blob(); if (b.size > 3000) return b; } } catch { }
  }
  return null;
}
function saveBlob(blob, name) { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); }
async function dlOne(k) {
  const it = S.idx[k]; if (!it) return;
  const b = (await fetchBlob(it.url)) || (it.alt && await fetchBlob(it.alt));
  if (b) saveBlob(b, fname(it.title) + "." + ((b.type.split("/")[1] || "jpg").replace("jpeg", "jpg")));
  else window.open(it.url, "_blank");
}
let zipLib;
async function JSZipLoad() {
  if (zipLib) return zipLib;
  await new Promise((ok, ko) => { const s = document.createElement("script"); s.src = "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"; s.onload = ok; s.onerror = ko; document.head.appendChild(s); });
  return (zipLib = window.JSZip);
}
const csvCell = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
function toCSV(rows) {
  const cols = ["tipo", "titulo", "evento", "fuente", "url", "vistas", "likes", "fecha", "marcado"];
  return "﻿" + [cols.join(","), ...rows.map(r => [r.type, r.title, r.event, r.source, r.url, r.views, r.likes, r.date, r.added].map(csvCell).join(","))].join("\n");
}
function pauta(rows) {
  const g = {}; rows.forEach(r => (g[r.type] = g[r.type] || []).push(r));
  const hp = store.get("hotpicks", {});
  let md = `# Mi selección CROWN · ${new Date().toLocaleString("es-CL", { timeZone: TZ })}\n\n`;
  for (const [t, rs] of Object.entries(g)) md += `## ${t[0].toUpperCase() + t.slice(1)}s (${rs.length})\n` + rs.map(r => `- ${r.title}${r.source ? " · " + r.source : ""}${r.views ? " · " + r.views + " vistas" : ""}${r.likes ? " · ♥ " + r.likes : ""}\n  ${r.url}`).join("\n") + "\n\n";
  const hps = Object.keys(hp).filter(k => hp[k].length && evById(k));
  if (hps.length) md += "## Hot picks\n\n" + hps.map(k => hpText(k)).join("\n\n---\n\n") + "\n";
  return md;
}
async function buildZip(rows, name) {
  const JSZip = await JSZipLoad(), zip = new JSZip(), fail = [];
  const imgs = rows.filter(r => r.type === "imagen" || (r.type !== "nota" && r.img));
  let n = 0;
  for (const r of imgs) {
    n++; $("#prog") && ($("#prog").textContent = `descargando ${n}/${imgs.length}…`);
    const src = r.type === "imagen" ? r.url : r.img;
    const b = (await fetchBlob(src)) || (r.alt && await fetchBlob(r.alt));
    if (b) zip.file(`imagenes/${String(n).padStart(2, "0")}-${fname(r.event || r.type)}-${fname(r.title).slice(0, 30)}.${(b.type.split("/")[1] || "jpg").replace("jpeg", "jpg")}`, b);
    else fail.push(src);
  }
  zip.file("seleccion.csv", toCSV(rows));
  zip.file("seleccion.json", JSON.stringify({ exportado: new Date().toISOString(), items: rows, hotpicks: store.get("hotpicks", {}), estadisticas_manuales: store.get("manualStats", {}) }, null, 1));
  zip.file("pauta.md", pauta(rows));
  if (fail.length) zip.file("no_descargadas.txt", "Estas imágenes no permitieron descarga directa; ábrelas y guárdalas a mano:\n\n" + fail.join("\n"));
  const blob = await zip.generateAsync({ type: "blob" });
  saveBlob(blob, name + ".zip");
  $("#prog") && ($("#prog").textContent = `listo: ${imgs.length - fail.length} imágenes${fail.length ? `, ${fail.length} solo como link` : ""}`);
}
function evRows(id) {
  const e = evById(id), man = store.get("manualStats", {});
  const rows = [{ type: "evento", title: e.name, url: location.href.split("#")[0] + "#ev=" + id, source: pName(e.contest), views: e.views_total, event: e.name }];
  (e.images || []).forEach((im, n) => rows.push({ ...S.idx[`img:${id}:${n}`] }));
  (e.videos || []).forEach(v => rows.push({ type: "video", title: v.title, url: "https://www.youtube.com/watch?v=" + v.vid, source: v.channel, views: v.views, event: e.name, img: `https://i.ytimg.com/vi/${v.vid}/hqdefault.jpg` }));
  (e.social || []).forEach(p => rows.push({ type: "post", title: p.title || p.url, url: p.url, source: p.platform, views: p.views ?? man[p.url]?.views, likes: p.likes ?? man[p.url]?.likes, event: e.name }));
  (e.item_ids || []).forEach(i => { const it = S.idx["feed:" + i]; if (it) rows.push({ ...it, event: e.name }); });
  return rows;
}

/* ---- panel de selección ---- */
function openBasket() {
  const b = basket(), rows = Object.entries(b).map(([k, v]) => ({ k, ...v }));
  const hp = store.get("hotpicks", {}), nHp = Object.values(hp).reduce((a, l) => a + l.length, 0);
  const g = {}; rows.forEach(r => g[r.type] = (g[r.type] || 0) + 1);
  openModal(`<h2>★ Mi selección</h2>
   <p class="hint">${rows.length} elementos marcados · ${Object.entries(g).map(([t, n]) => `${n} ${t}`).join(" · ") || "nada aún"} · ${nHp} hot picks en ${Object.keys(hp).filter(k => hp[k].length).length} eventos</p>
   <div class="toolbar"><button data-exp="zip">⬇ Todo en ZIP (imágenes + CSV + JSON + pauta)</button><button class="ghost" data-exp="csv">CSV</button><button class="ghost" data-exp="json">JSON</button><button class="ghost" data-exp="md">Copiar pauta</button><button class="ghost" data-exp="clear">Vaciar</button><span class="prog" id="prog"></span></div>
   ${rows.map(r => `<div class="bl"><img src="${esc(r.img || r.alt || "")}" referrerpolicy="no-referrer" onerror="this.style.visibility='hidden'"><div><b>${esc(r.type)}</b> · ${esc(r.title)}<br><small class="hint">${esc(r.event || r.source || "")}${r.views ? " · ▶ " + esc(r.views) : ""}${r.likes ? " · ♥ " + esc(r.likes) : ""}</small></div><button class="ghost" data-unmk="${esc(r.k)}">✕</button></div>`).join("") || `<div class="empty">Marca con ☆ notas, videos, imágenes, publicaciones o eventos completos.</div>`}`);
  $("#modal .mbox").classList.add("wide");
}
function basketRows() {
  const man = store.get("manualStats", {});
  return Object.values(basket()).map(r => ({ ...r, views: r.views || man[r.url]?.views || "", likes: r.likes || man[r.url]?.likes || "" }));
}

/* ---- eventos de UI ---- */
document.addEventListener("click", async e => {
  const t = e.target.closest("[data-ev],[data-evc],[data-evk],[data-evzip],[data-selall],[data-dlsel],[data-addsel],[data-dl],[data-addpost],[data-hpmv],[data-hpdel],[data-hpcopy],[data-hptp],[data-hpstar],[data-exp],[data-unmk],#basketBtn,#evNew");
  if (!t) return;
  const d = t.dataset;
  if (t.id === "basketBtn") return openBasket();
  if (t.id === "evNew") {
    const name = prompt("Nombre del evento (ej.: 'Sesión de fotos retro de MU')"); if (!name) return;
    const c = prompt("Concurso: mu, mi, me, mw, mgi o ms", "mu") || "mu";
    const m = myEvents(); m.unshift({ id: "mio-" + Date.now(), name, contest: c, start: new Date().toISOString(), last_activity: new Date().toISOString(), images: [], videos: [], item_ids: [], n_items: 0 });
    store.set("myEvents", m); renderEvents(); return;
  }
  if (d.ev) { e.preventDefault(); return openEvent(d.ev); }
  if (d.evc !== undefined) { S.evFilter.c = d.evc; return renderEvents(); }
  if (d.evk !== undefined) { S.evFilter.k = d.evk; return renderEvents(); }
  if (d.evzip) { const ev = evById(d.evzip); return buildZip(evRows(d.evzip), "crown-" + fname(ev.name)); }
  if (d.selall !== undefined) { const all = $$(".isel"); const on = !all.every(x => x.checked); all.forEach(x => { x.checked = on; x.closest(".ig").classList.toggle("sel", on); }); return; }
  if (d.dlsel !== undefined) { const ks = $$(".ig").filter(x => x.querySelector(".isel").checked).map(x => x.dataset.k); if (!ks.length) return alert("Selecciona imágenes primero."); return buildZip(ks.map(k => S.idx[k]), "crown-imagenes-" + fname($(".evm") ? evById($(".evm").dataset.evid).name : (S.idx[ks[0]] || {}).event || "perfil")); }
  if (d.addsel !== undefined) { $$(".ig").filter(x => x.querySelector(".isel").checked).forEach(x => bAdd(x.dataset.k)); $$(".ig .mk").forEach(m => { m.classList.toggle("on", bHas(m.dataset.mk)); m.textContent = bHas(m.dataset.mk) ? "★" : "☆"; }); return; }
  if (d.dl) return dlOne(d.dl);
  if (d.addpost) { const u = $("#newPost").value.trim(); if (!/^https?:\/\//.test(u)) return; const all = store.get("myPosts", {}); (all[d.addpost] = all[d.addpost] || []).push(u); store.set("myPosts", all); return openEvent(d.addpost); }
  if (d.hpmv) { const [n, dir] = d.hpmv.split("|").map(Number); return hpEdit(l => { const j = n + dir; if (j < 0 || j >= l.length) return l; [l[n], l[j]] = [l[j], l[n]]; return l; }); }
  if (d.hpdel) return hpEdit(l => (l.splice(+d.hpdel, 1), l));
  if (d.hpcopy) { navigator.clipboard?.writeText(hpText(d.hpcopy)); t.textContent = "¡Copiado!"; return; }
  if (d.hptp) { const txt = hpText(d.hptp); if (!txt) return; addScript("Hot picks · " + evById(d.hptp).name, txt); tpLoad(txt); $("#modal").hidden = true; $('[data-tab="grabar"]').click(); return; }
  if (d.hpstar) { bAdd("hp:" + d.hpstar, { type: "hot picks", title: "Hot picks · " + evById(d.hpstar).name, url: "", source: hpText(d.hpstar).split("\n").filter(l => l.startsWith("#")).join(" | "), event: evById(d.hpstar).name }); t.textContent = "★ Marcados"; return; }
  if (d.unmk) { bToggle(d.unmk); return openBasket(); }
  if (d.exp) {
    const rows = basketRows(), stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
    if (d.exp === "zip") return buildZip(rows, "crown-seleccion-" + stamp);
    if (d.exp === "csv") return saveBlob(new Blob([toCSV(rows)], { type: "text/csv" }), "crown-seleccion-" + stamp + ".csv");
    if (d.exp === "json") return saveBlob(new Blob([JSON.stringify({ items: rows, hotpicks: store.get("hotpicks", {}) }, null, 1)], { type: "application/json" }), "crown-seleccion-" + stamp + ".json");
    if (d.exp === "md") { navigator.clipboard?.writeText(pauta(rows)); t.textContent = "¡Copiada!"; return; }
    if (d.exp === "clear" && confirm("¿Vaciar la selección?")) { store.set("basket", {}); renderBasketBtn(); return openBasket(); }
  }
});
document.addEventListener("change", e => {
  if (e.target.classList.contains("isel")) e.target.closest(".ig").classList.toggle("sel", e.target.checked);
  if (e.target.dataset.ms) { const [u, k] = e.target.dataset.ms.split("|"), m = store.get("manualStats", {}); (m[u] = m[u] || {})[k] = e.target.value; store.set("manualStats", m); }
  if (e.target.dataset.hpnote !== undefined) { const n = +e.target.dataset.hpnote; hpEdit(l => (l[n].note = e.target.value, l)); }
});
$("#evQ").oninput = renderEvents;
window.addEventListener("load", () => { const m = location.hash.match(/^#ev=(.+)$/); if (m) setTimeout(() => { $('[data-tab="eventos"]').click(); openEvent(decodeURIComponent(m[1])); }, 1500); });

/* ================= GALERÍA · PERFIL · INSTAGRAM · DRAWER ================= */
const CATS = [["retrato", "Retrato oficial"], ["bano", "Traje de baño"], ["tipico", "Traje típico"], ["gala", "Vestido de gala"], ["runway", "Runway"], ["otras", "Más fotos"]];
S.gallery = S.gallery || { cells: {}, ig_posts: {}, handles: {}, accounts: {} };
S.gal = { cat: "retrato", sel: new Set(), mode: "fotos", icat: "", style: "", role: "" };

function imgTag(im) { const src = (im.thumb || im.alt || im.url || "").replace(/^http:\/\//, "https://"), alt2 = im.url !== src ? im.url : (src.includes("maxresdefault") ? src.replace("maxresdefault", "hqdefault") : ""); return `<img src="${esc(src)}" loading="lazy" referrerpolicy="no-referrer" alt="" ${alt2 ? `onerror="if(!this.dataset.r){this.dataset.r=1;this.src='${esc(alt2)}'}else{this.remove()}"` : `onerror="this.remove()"`}>`; }
function igPostsFor(c, cat) {
  const k = c.contest + "|" + c.country;
  return Object.values(S.gallery.ig_posts || {}).filter(p => (p.who || []).includes(k) && (!cat || (p.cats || []).includes(cat)));
}
function cellImgs(c, cat) {
  const out = [];
  for (const p of igPostsFor(c, cat).filter(p => !p.style)) for (const u of p.images || []) out.push({ url: u, thumb: p.thumb && p.images[0] === u ? p.thumb : u, page: p.url, via: "Instagram @" + (p.owner || ""), credit: "@" + (p.owner || ""), ig: true, likes: p.likes, comments: p.comments });
  for (const u of (store.get("myMedia", {})[`${c.contest}|${c.country}|${cat}`] || [])) out.push(/instagram\.com\/(p|reel)\//.test(u) ? { url: u, page: u, via: "Instagram (agregado por ti)", ig: true, post: true } : { url: u, page: u, via: "Agregada por ti", credit: "tú" });
  for (const im of ((S.gallery.ig_official || {})[`${c.contest}|${c.country}|${cat}`] || [])) out.push(im);
  for (const im of ((S.gallery.official || {})[`${c.contest}|${c.country}|${cat}`] || [])) out.push(im);
  for (const im of ((S.gallery.press || {})[`${c.contest}|${c.country}|${cat}`] || [])) out.push(im);
  for (const im of ((S.gallery.cells || {})[`${c.contest}|${c.country}|${cat}`] || {}).images || []) out.push({ ...im, ig: im.from_ig });
  const seen = new Set(); return out.filter(i => !seen.has(i.url) && seen.add(i.url));
}
function photoOf(c, cat) {
  for (const k of [cat || "retrato", ...CATS.map(x => x[0])]) { const im = cellImgs(c, k).find(i => !i.post); if (im) return im; }
  return null;
}

function initGallery() {
  const ids = [...new Set(S.contestants.map(c => c.contest))].filter(x => x !== "me");
  for (const sel of ["#gContest", "#iContest"]) $(sel).innerHTML = ids.map(id => `<option value="${id}">${esc(pName(id))}</option>`).join("");
  $("#gCat").innerHTML = CATS.map(([id, l]) => `<button data-gcat="${id}" class="${id === S.gal.cat ? "on" : ""}">${l}</button>`).join("");
  $("#iCat").innerHTML = [["", "Todo"], ...CATS].map(([id, l]) => `<button data-icat="${id}" class="${id === S.gal.icat ? "on" : ""}">${l}</button>`).join("");
  ["gContest", "gFav"].forEach(id => $("#" + id).onchange = () => { S.gal.sel.clear(); renderGallery(); });
  $("#gQ").oninput = renderGallery; $("#iQ").oninput = renderIG; $("#iContest").onchange = renderIG;
}
function renderGallery() {
  if (!S.contestants.length || !$("#gContest").value) return;
  const cid = $("#gContest").value, cat = S.gal.cat, q = ($("#gQ").value || "").toLowerCase(), favs = store.get("favs", {});
  let list = S.contestants.filter(c => c.contest === cid && (!q || (c.name + " " + c.country_es + " " + c.country).toLowerCase().includes(q)) && (!$("#gFav").checked || favs[c.contest + "|" + c.country]));
  const fimgs0 = c => cellImgs(c, cat).filter(i => !S.gal.style || (S.gal.style === "_otras" ? !i.style : i.style === S.gal.style));
  list.sort((a, b) => (fimgs0(b).length > 0) - (fimgs0(a).length > 0) || (a.hot || 99) - (b.hot || 99) || a.country_es.localeCompare(b.country_es));
  const styles = Object.values(S.gallery.styles || {}).filter(st => st.cat === cat);
  $("#gStyle").innerHTML = styles.length ? `<span class="hint">Estilo:</span> ` + [["", "Todas las fuentes"], ...styles.map(st => [st.id, `${st.label} (${st.posts})`]), ["_otras", "Otras fuentes"]]
    .map(([id, l]) => `<button class="chip ${S.gal.style === id ? "on" : ""}" data-gstyle="${id}">${esc(l)}</button>`).join("") +
    (S.gal.style && S.gal.style !== "_otras" ? ` <span class="hint">Foto:</span> ` + [["", "Todas"], ["1", "1"], ["2", "2"], ["3", "3"]].map(([r, l]) => `<button class="chip ${S.gal.role === r ? "on" : ""}" data-grole="${r}">${l}</button>`).join("") : "") : "";
  const fimgs = c => cellImgs(c, cat).filter(i => !S.gal.style || (S.gal.style === "_otras" ? !i.style : i.style === S.gal.style) && (!S.gal.role || String(i.role_n) === S.gal.role));
  const withImg = list.filter(c => fimgs(c).length).length;
  $("#gInfo").textContent = `${withImg} de ${list.length} candidatas ya tienen fotos de "${CATS.find(x => x[0] === cat)[1]}". El robot sigue buscando en cada corrida. Toca una foto para ver todas; marca ✓ para descargar varias.`;
  $("#gGrid").innerHTML = list.map(c => {
    const k = c.contest + "|" + c.country, ims = fimgs(c), im = ims[0], on = S.gal.sel.has(k);
    return `<div class="pc ${on ? "sel" : ""}" data-prof="${esc(k)}" data-pcat="${cat}">
      <div class="ph">${im ? imgTag(im) : `<span class="bigflag">${flag(c.iso)}</span><span class="loading">buscando…</span>`}
      ${ims.length ? `<button class="chk" data-gsel="${esc(k)}" title="Seleccionar">${on ? "✓" : ""}</button><span class="cnt">${ims.length}</span>` : ""}${im && im.ig ? `<span class="igb">${im.official ? "IG oficial" : "IG"}</span>` : ""}</div>
      <div class="info"><div class="n">${flag(c.iso)} ${esc(c.name)}</div><div class="p">${esc(c.country_es)}${im && im.likes != null ? ` · ♥ ${num(im.likes)}` : ""}</div>${im && im.role ? `<div class="p" style="color:var(--gold2)">${esc(im.role)}</div>` : ""}</div></div>`;
  }).join("") || `<div class="empty">Sin candidatas para este filtro.</div>`;
  updSelbar();
}
function updSelbar() {
  const n = S.gal.sel.size, cat = S.gal.cat;
  const imgs = [...S.gal.sel].reduce((a, k) => { const c = S.contestants.find(x => x.contest + "|" + x.country === k); return a + (c ? cellImgs(c, cat).length : 0); }, 0);
  $("#selbar").hidden = !n || !$("#galeria").classList.contains("on");
  $("#selN").textContent = `${n} candidata${n === 1 ? "" : "s"} · ${imgs} fotos`;
}
function selRows() {
  const cat = S.gal.cat, rows = [];
  for (const k of S.gal.sel) { const c = S.contestants.find(x => x.contest + "|" + x.country === k); if (!c) continue;
    cellImgs(c, cat).filter(i => !S.gal.style || (S.gal.style === "_otras" ? !i.style : i.style === S.gal.style) && (!S.gal.role || String(i.role_n) === S.gal.role)).forEach((im, n) => rows.push({ type: "imagen", title: `${c.country_es} ${c.name} ${im.style_label || CATS.find(x => x[0] === cat)[1]} ${im.role || n + 1}`, url: im.url, alt: im.thumb, img: im.thumb || im.url, source: im.via, page: im.page, event: `${c.country_es} · ${CATS.find(x => x[0] === cat)[1]}`, likes: im.likes })); }
  return rows;
}

function renderIG() {
  const posts = Object.values(S.gallery.ig_posts || {});
  const cid = $("#iContest").value || "mu", q = ($("#iQ").value || "").toLowerCase(), cat = S.gal.icat;
  const graph = Object.values(S.gallery.accounts || {}).some(a => a.fetched);
  $("#igCallout").innerHTML = graph
    ? `<b>Instagram conectado</b> mediante la API oficial: fotos, likes y comentarios de ${Object.values(S.gallery.accounts).filter(a => a.fetched).length} cuentas.`
    : `<b>Posts públicos de Instagram</b> encontrados por búsqueda para cada candidata. Toca "Ver post" para verlo aquí mismo con el embed oficial. Si quieres <b>fotos y likes automáticos</b>, conecta la API oficial de Instagram (guía paso a paso en Más → Fuentes y robot).`;
  const list = posts.filter(p => p.contest === cid && (!cat || (p.cats || []).includes(cat)) && (!q || ((p.caption || "") + " " + (p.who || []).join(" ") + " " + (p.owner || "")).toLowerCase().includes(q)))
    .sort((a, b) => new Date(b.taken || b.seen) - new Date(a.taken || a.seen)).slice(0, 200);
  $("#iGrid").innerHTML = list.map(p => {
    const who = (p.who || []).map(k => S.contestants.find(c => c.contest + "|" + c.country === k)).filter(Boolean);
    S.idx["post:" + p.url] = { type: "post", title: (p.caption || p.url).slice(0, 120), url: p.url, img: p.thumb || (p.images || [])[0] || "", source: "Instagram" + (p.owner ? " @" + p.owner : ""), likes: p.likes, views: p.views };
    return `<div class="igc"><div class="ph ${p.thumb ? "" : "noimg"}" ${p.thumb ? `style="background-image:url('${esc(p.thumb)}')"` : ""}>${p.thumb ? "" : "Instagram<br>" + esc(who.map(c => c.country_es).join(", "))}</div>
      <div class="b"><div>${who.map(c => `<span class="who" data-prof="${esc(c.contest + "|" + c.country)}" style="cursor:pointer">${flag(c.iso)} ${esc(c.name)}</span>`).join(" ")}</div>
      ${(p.cats || []).map(x => `<span class="tag looks">${esc((CATS.find(y => y[0] === x) || [x, x])[1])}</span>`).join(" ")}
      <div class="cap">${esc(p.caption || "")}</div>
      ${p.likes != null || p.comments != null ? `<div class="st">${p.likes != null ? "♥ " + num(p.likes) : ""} ${p.comments != null ? "💬 " + num(p.comments) : ""} ${p.views ? "▶ " + num(p.views) : ""}</div>` : ""}
      <div class="acts"><button class="ghost" data-igembed="${esc(p.url)}">Ver post</button><a href="${esc(p.url)}" target="_blank">abrir ↗</a>${mkBtn("post:" + p.url)}</div></div></div>`;
  }).join("") || `<div class="empty">Todavía no hay posts para este filtro. El robot busca 25 candidatas por corrida.</div>`;
}
function igEmbed(url) {
  openModal(`<blockquote class="instagram-media" data-instgrm-permalink="${esc(url)}" data-instgrm-version="14" style="max-width:540px;width:100%;margin:auto;background:#fff;border-radius:12px"></blockquote><p class="hint" style="text-align:center"><a href="${esc(url)}" target="_blank">Abrir en Instagram ↗</a></p>`);
  const go = () => window.instgrm && window.instgrm.Embeds.process();
  if (window.instgrm) go(); else { const s = document.createElement("script"); s.src = "https://www.instagram.com/embed.js"; s.async = true; s.onload = go; document.body.appendChild(s); }
}

/* ---- drawer ---- */
function openDrawer(h) { $("#dbody").innerHTML = h; $("#drawer").hidden = false; $(".dpanel").scrollTop = 0; document.body.style.overflow = "hidden"; }
function closeDrawer() { $("#drawer").hidden = true; $("#dbody").innerHTML = ""; document.body.style.overflow = ""; if (/^#(ev|c)=/.test(location.hash)) history.replaceState(null, "", "#"); }
$("#dx").onclick = closeDrawer;
$("#drawer").onclick = e => { if (e.target.id === "drawer") closeDrawer(); };
document.addEventListener("keydown", e => { if (e.key === "Escape") { if (!$("#modal").hidden) $("#mx").click(); else if (!$("#drawer").hidden) closeDrawer(); } });

function openProfile(k, cat) {
  const c = S.contestants.find(x => x.contest + "|" + x.country === k); if (!c) return;
  const h = (S.gallery.handles || {})[k] || {}, acc = h.handle ? (S.gallery.accounts || {})[h.handle] || {} : {};
  const ig = c.ig || (h.conf === "alta" || h.conf === "verificada" ? h.handle : null);
  const its = (S.feed.items || []).filter(i => (i.who || []).some(w => w.contest === c.contest && w.country === c.country));
  const favs = store.get("favs", {}), ranks = store.get("ranks", {});
  const counts = Object.fromEntries(CATS.map(([id]) => [id, cellImgs(c, id).length]));
  cat = cat || CATS.find(([id]) => counts[id])?.[0] || "retrato";
  const ph = photoOf(c, "retrato");
  const evs = allEvents().filter(e => e.contest === c.contest && !/agenda/.test(e.kind)).slice(0, 30);
  const L = links(c).filter(([l]) => l !== "IG");
  openDrawer(`<div class="profile" data-pk="${esc(k)}">
   <div class="prof"><div class="ph">${ph ? imgTag(ph) : flag(c.iso)}</div>
   <div><div class="hint">${esc(pName(c.contest))}${c.hot ? ` · <span class="hotb">HOT #${c.hot}</span>` : ""}</div>
    <h2>${flag(c.iso)} ${esc(c.name)}</h2>
    <div class="facts"><span><b>${esc(c.country_es)}</b></span>${c.age ? `<span><b>${c.age}</b> años</span>` : ""}${c.hometown ? `<span>${esc(c.hometown)}</span>` : ""}${c.region ? `<span>${esc(c.region)}</span>` : ""}
     ${ig ? `<span>IG <a href="https://www.instagram.com/${esc(ig)}/" target="_blank">@${esc(ig)}</a>${acc.followers ? ` · <b>${num(acc.followers)}</b> seguidores` : ""}</span>` : h.handle ? `<span>IG posible: <a href="https://www.instagram.com/${esc(h.handle)}/" target="_blank">@${esc(h.handle)}</a> (verificar)</span>` : ""}
     <span><b>${its.length}</b> notas</span></div>
    ${c.no_wiki ? `<div class="nt" style="border-color:var(--rose)">Ya no figura en la lista de Wikipedia: posible retiro o reemplazo.</div>` : ""}
    ${c.nota ? `<div class="nt">${esc(c.nota)}${c.fuente ? ` <a href="${esc(c.fuente)}" target="_blank">fuente</a>` : ""}</div>` : ""}
    <div class="toolbar"><button class="${favs[k] ? "" : "ghost"}" data-pfav="${esc(k)}">${favs[k] ? "★ Favorita" : "☆ Favorita"}</button>
     <label class="rng">Mi ranking <input class="rank" data-prank="${esc(k)}" type="number" min="1" value="${ranks[k] || ""}" style="width:64px"></label>
     <select data-php="${esc(k)}"><option value="">+ Agregar a hot picks de…</option>${evs.map(e => `<option value="${esc(e.id)}">${esc(e.name)}</option>`).join("")}</select></div>
    <div class="lk">${ig ? `<a href="https://www.instagram.com/${esc(ig)}/" target="_blank">Instagram</a>` : ""}${L.map(([l, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener">${l}</a>`).join("")}</div>
   </div></div>
   <div class="dtabs">${CATS.map(([id, l]) => `<button data-ptab="${id}" class="${id === cat ? "on" : ""}">${l}<i>${counts[id]}</i></button>`).join("")}<button data-ptab="ig" class="${cat === "ig" ? "on" : ""}">Instagram<i>${igPostsFor(c).length}</i></button><button data-ptab="news" class="${cat === "news" ? "on" : ""}">Noticias<i>${its.length}</i></button></div>
   <div id="pbody"></div></div>`);
  renderPTab(k, cat);
  history.replaceState(null, "", "#c=" + enc(k));
}
function renderPTab(k, cat) {
  const c = S.contestants.find(x => x.contest + "|" + x.country === k);
  $$("[data-ptab]").forEach(b => b.classList.toggle("on", b.dataset.ptab === cat));
  if (cat === "news") { const its = (S.feed.items || []).filter(i => (i.who || []).some(w => w.contest === c.contest && w.country === c.country)); $("#pbody").innerHTML = `<div class="feed">${its.map(itemHTML).join("") || `<div class="empty">Sin notas aún.</div>`}</div>`; return; }
  if (cat === "ig") {
    const ps = igPostsFor(c);
    $("#pbody").innerHTML = `<div class="iggrid">${ps.map(p => `<div class="igc"><div class="ph ${p.thumb ? "" : "noimg"}" ${p.thumb ? `style="background-image:url('${esc(p.thumb)}')"` : ""}>${p.thumb ? "" : "Instagram"}</div><div class="b"><div class="cap">${esc(p.caption || "")}</div>${p.likes != null ? `<div class="st">♥ ${num(p.likes)} ${p.comments != null ? "💬 " + num(p.comments) : ""}</div>` : ""}<div class="acts"><button class="ghost" data-igembed="${esc(p.url)}">Ver post</button><a href="${esc(p.url)}" target="_blank">abrir ↗</a></div></div></div>`).join("") || `<div class="empty">Aún no hay posts de Instagram para ella. <a href="https://www.google.com/search?q=${enc('site:instagram.com "' + c.name + '"')}" target="_blank">Buscar en Instagram ↗</a></div>`}</div>`;
    return;
  }
  const ims = cellImgs(c, cat), label = CATS.find(x => x[0] === cat)[1];
  ims.forEach((im, n) => S.idx[`pimg:${k}:${cat}:${n}`] = { type: "imagen", title: `${c.country_es} ${c.name} ${label} ${n + 1}`, url: im.url, alt: im.thumb, img: im.thumb || im.url, source: im.via, page: im.page, event: `${c.country_es} · ${label}`, likes: im.likes });
  $("#pbody").innerHTML = `<div class="toolbar"><button class="ghost" data-selall>Seleccionar todas</button><button data-dlsel>⬇ Descargar seleccionadas</button><button class="ghost" data-addsel>★ Marcar seleccionadas</button>
     <a href="https://www.google.com/search?tbm=isch&q=${enc(c.name + " Miss Universe 2026 " + label)}" target="_blank">buscar más ↗</a><span class="prog" id="prog"></span></div>
    <div class="toolbar"><input id="addMedia" placeholder="Pega el link de una foto o de un post de Instagram para guardarlo en esta categoría" style="flex:1"><button data-addmedia="${esc(k)}|${cat}">+ Agregar</button></div>
    ${[...new Set(ims.map(i => i.style_label || "Prensa, YouTube y otras fuentes"))].map(g => `<h4 style="margin:14px 0 8px;font-size:18px">${esc(g)}${ims.find(i => (i.style_label || "Prensa, YouTube y otras fuentes") === g && i.credit && i.style) ? ` <span class="hint" style="font-family:var(--sans)">${esc(ims.find(i => i.style_label === g).credit)}</span>` : ""}</h4>
    <div class="igrid">${ims.map((im, n) => (im.style_label || "Prensa, YouTube y otras fuentes") !== g ? "" : im.post ? `<div class="ig" style="display:grid;place-items:center;aspect-ratio:4/5;background:linear-gradient(45deg,#f58529,#dd2a7b,#8134af)"><button class="ghost" style="color:#fff;border-color:#fff" data-igembed="${esc(im.url)}">Ver post de IG</button></div>` : `<div class="ig" data-k="pimg:${esc(k)}:${cat}:${n}"><input type="checkbox" class="isel">${imgTag(im)}
     <div class="tools"><a href="${esc(im.page || im.url)}" target="_blank" title="${esc(im.title || im.via || "")}">${im.ig ? "📷 IG" : esc(im.credit || im.via || "fuente")}</a><span><button data-dl="pimg:${esc(k)}:${cat}:${n}">⬇</button> ${mkBtn(`pimg:${k}:${cat}:${n}`)}</span></div>${im.role ? `<span class="cnt" style="left:auto;right:8px">${esc(im.role)}${im.likes != null ? " · ♥ " + num(im.likes) : ""}</span>` : ""}</div>`).join("")}</div>`).join("") || `<div class="empty">El robot todavía no encuentra fotos de "${label}" para ${esc(c.name)}. Vuelve en unos minutos.</div>`}
    <p class="hint">Fuentes: fotos de notas y videos que la nombran (clasificadas por el texto), Instagram y lo que agregues tú. Usa las fotos con crédito.</p>`;
}

/* ---- eventos de UI de galería/perfil ---- */
document.addEventListener("click", e => {
  const t = e.target.closest("[data-gstyle],[data-grole],[data-gm],[data-gcat],[data-icat],[data-gsel],[data-prof],[data-ptab],[data-pfav],[data-igembed],[data-addmedia],#moreBtn,#selZip,#selMark,#selClear,[data-tab]");
  if (!t) { if (!e.target.closest(".more")) $("#moreMenu").hidden = true; return; }
  const d = t.dataset;
  if (t.id === "moreBtn") { $("#moreMenu").hidden = !$("#moreMenu").hidden; return; }
  if (d.tab) { setTimeout(updSelbar, 0); return; }
  if (d.gm) { S.gal.mode = d.gm; $$("#galMode button").forEach(b => b.classList.toggle("on", b === t)); $("#galFotos").hidden = d.gm !== "fotos"; $("#galIg").hidden = d.gm !== "ig"; $("#galVideos").hidden = d.gm !== "videos"; updSelbar(); return; }
  if (d.gstyle !== undefined) { S.gal.style = d.gstyle; S.gal.role = ""; return renderGallery(); }
  if (d.grole !== undefined) { S.gal.role = d.grole; return renderGallery(); }
  if (d.gcat) { S.gal.cat = d.gcat; S.gal.style = ""; S.gal.role = ""; S.gal.sel.clear(); $$("#gCat button").forEach(b => b.classList.toggle("on", b === t)); return renderGallery(); }
  if (d.icat !== undefined) { S.gal.icat = d.icat; $$("#iCat button").forEach(b => b.classList.toggle("on", b === t)); return renderIG(); }
  if (d.gsel) { e.stopPropagation(); S.gal.sel.has(d.gsel) ? S.gal.sel.delete(d.gsel) : S.gal.sel.add(d.gsel); return renderGallery(); }
  if (t.id === "selClear") { S.gal.sel.clear(); return renderGallery(); }
  if (t.id === "selZip") { const rows = selRows(); if (!rows.length) return; const pr = $("#prog"); return buildZip(rows, "crown-" + fname($("#gContest").selectedOptions[0].text + "-" + S.gal.cat)).then(() => { $("#selProg").textContent = "ZIP listo"; }); }
  if (t.id === "selMark") { selRows().forEach((r, n) => bAdd("sel:" + r.url, r)); $("#selProg").textContent = "marcadas ★"; return; }
  if (d.igembed) { e.preventDefault(); return igEmbed(d.igembed); }
  if (d.ptab) return renderPTab($(".profile").dataset.pk, d.ptab);
  if (d.addmedia) { const u = ($("#addMedia").value || "").trim(); if (!/^https?:\/\//.test(u)) return; const m = store.get("myMedia", {}); (m[d.addmedia] = m[d.addmedia] || []).unshift(u); store.set("myMedia", m); const [ct, co, cat] = d.addmedia.split("|"); renderPTab(ct + "|" + co, cat); renderGallery(); renderCandidatas(); return; }
  if (d.pfav) { const f = store.get("favs", {}); f[d.pfav] = !f[d.pfav]; store.set("favs", f); t.className = f[d.pfav] ? "" : "ghost"; t.textContent = f[d.pfav] ? "★ Favorita" : "☆ Favorita"; renderCandidatas(); return; }
  if (d.prof) {
    if (e.target.closest(".star,.rank,.chk,.mk,input,a")) return;
    e.preventDefault(); return openProfile(d.prof, d.pcat);
  }
});
document.addEventListener("change", e => {
  const d = e.target.dataset;
  if (d.prank) { const r = store.get("ranks", {}), v = parseInt(e.target.value); if (v) r[d.prank] = v; else delete r[d.prank]; store.set("ranks", r); renderCandidatas(); }
  if (d.php && e.target.value) {
    const c = S.contestants.find(x => x.contest + "|" + x.country === d.php), all = store.get("hotpicks", {});
    (all[e.target.value] = all[e.target.value] || []).push({ name: c.name, country: c.country_es, iso: c.iso });
    store.set("hotpicks", all); const ev = evById(e.target.value); e.target.value = ""; renderEvents();
    e.target.options[0].textContent = `✓ Agregada a hot picks de ${ev.name.slice(0, 40)}`;
  }
});
window.addEventListener("load", () => { const m = location.hash.match(/^#c=(.+)$/); if (m) setTimeout(() => openProfile(decodeURIComponent(m[1])), 1500); });
