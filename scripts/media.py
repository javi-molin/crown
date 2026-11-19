"""
CROWN · galería por candidata y categoría.

1) Instagram (fuente principal), por vías permitidas:
   a) Graph API oficial de Instagram (Business Discovery) si se configuran los secretos IG_TOKEN e IG_USER_ID:
      fotos, carruseles, likes y comentarios de cuentas públicas profesionales (oficiales y candidatas).
   b) Posts públicos encontrados con búsqueda web; el panel los muestra con el embed oficial de Instagram. Cada post se asigna a una candidata (por @, nombre o país
   en el texto) y a una categoría (retrato oficial, traje de baño, traje típico, gala, runway…).
2) Descubrimiento de la cuenta de IG de cada candidata (búsqueda web), con confianza.
3) Respaldo: Bing Imágenes por candidata × categoría, validando que el resultado nombre a la candidata.
Escribe data/gallery.json. Todo es incremental y tolerante a fallos.
"""
import json, re, time, html, os, urllib.parse
from datetime import datetime, timezone, timedelta

U = None
DIAG = []
CATS = [
    ("retrato", "Retrato oficial", "official portrait", r"official (portrait|photo)|portrait|retrato|photo ?shoot|sesion (de )?fotos|headshot|giannina|1950|diamond|75 ?(th|years|anos)|cetro|scepter"),
    ("bano", "Traje de baño", "swimsuit", r"swimsuit|traje de bano|bikini|beach|playa|swimwear|banador"),
    ("tipico", "Traje típico", "national costume", r"national costume|traje (tipico|nacional)|natcos|costume|fantasia"),
    ("gala", "Vestido de gala", "evening gown", r"evening gown|gown|vestido de gala|traje de gala|gala"),
    ("runway", "Runway to the Universe", "Runway to the Universe", r"runway to the universe|runway|pasarela de moda|fashion show"),
]
CAT_ORDER = [c[0] for c in CATS]
BASE_ACCOUNTS = [("missuniverse", "mu", "oficial"), ("missinternationalofficial", "mi", "oficial"),
                 ("missuniversechileof", "mu", "org. nacional"), ("themissuniverseph", "mu", "org. nacional"),
                 ("missuniverse.mexico", "mu", "org. nacional")]
BAD_IMG = re.compile(r"ytimg\.com|youtube\.com|bing\.com/th|gstatic\.com|/logo|favicon|placeholder|avatar|sprite|\.svg|\.gif", re.I)
BAD_HANDLES = {"p", "reel", "reels", "explore", "accounts", "stories", "tv", "about", "legal", "direct", "missuniverse",
               "missinternationalofficial", "instagram", "developer", "web", "tags", "locations", "popular"}


def ig_graph(user, known=frozenset(), max_pages=1):
    """Instagram Graph API oficial (Business Discovery). Requiere los secretos IG_TOKEN e IG_USER_ID.
    Pagina hacia atrás hasta encontrar posts ya conocidos o agotar max_pages (50 posts por página)."""
    import os
    tok, me = os.environ.get("IG_TOKEN"), os.environ.get("IG_USER_ID")
    if not (tok and me):
        raise RuntimeError("sin credenciales")
    posts, after, meta = [], None, {}
    for _ in range(max_pages):
        media = "media" + (f".after({after})" if after else "") + ".limit(50)"
        fields = ("business_discovery.username(%s){name,followers_count,media_count,profile_picture_url,%s"
                  "{caption,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count,media_type,children{media_url,media_type}}}") % (user, media)
        d = json.loads(U.get(f"https://graph.facebook.com/v21.0/{me}?fields={urllib.parse.quote(fields)}&access_token={tok}", timeout=40))["business_discovery"]
        meta = {"name": d.get("name"), "followers": d.get("followers_count"), "media_count": d.get("media_count"), "pic": d.get("profile_picture_url")}
        stop = False
        for m in d.get("media", {}).get("data", []):
            kids = [c for c in m.get("children", {}).get("data", []) if c.get("media_url") and c.get("media_type") != "VIDEO"]
            imgs = [c["media_url"] for c in kids] or ([m.get("thumbnail_url")] if m.get("media_type") == "VIDEO" else [m.get("media_url")])
            imgs = [u for u in imgs if u and ".mp4" not in u]
            code = re.search(r"/(?:p|reel|tv)/([\w-]+)", m["permalink"]).group(1)
            if code in known:
                stop = True
            posts.append({"code": code, "url": m["permalink"], "owner": user, "images": [i for i in imgs if i][:10],
                          "thumb": m.get("thumbnail_url") or (imgs[0] if imgs else None), "caption": (m.get("caption") or "")[:1500],
                          "likes": m.get("like_count"), "comments": m.get("comments_count"), "is_video": m.get("media_type") == "VIDEO",
                          "taken": m["timestamp"].replace("+0000", "+00:00")})
        after = d.get("media", {}).get("paging", {}).get("cursors", {}).get("after")
        if stop or not after:
            break
        time.sleep(0.5)
    return {"handle": user, **meta, "posts": posts}


def ig_search_posts(c):
    """Encuentra posts públicos de Instagram sobre la candidata usando resultados de búsqueda web."""
    base = {"mu": "Miss Universe", "mi": "Miss International"}.get(c["contest"], "Miss")
    q = f'site:instagram.com "{c["name"]}" {base} 2026'
    page = U.get("https://www.bing.com/search?setlang=es&count=30&q=" + urllib.parse.quote(q))
    out = []
    for m in re.finditer(r'<li class="b_algo".*?</li>', page, re.S):
        blk = m.group(0)
        u = re.search(r'href="(https://www\.instagram\.com/(?:[\w.]+/)?(?:p|reel)/[\w-]+/?)"', blk)
        if not u:
            continue
        txt = html.unescape(re.sub("<[^>]+>", " ", blk))
        code = re.search(r"/(?:p|reel)/([\w-]+)", u.group(1)).group(1)
        out.append({"code": code, "url": f"https://www.instagram.com/p/{code}/", "owner": None, "images": [], "caption": re.sub(r"\s+", " ", txt)[:400],
                    "taken": None, "via": "búsqueda web"})
    return out[:8]


def classify(text):
    t = U.norm(text)
    return [cid for cid, _, _, rx in CATS if re.search(rx, t)]


def find_handle(c):
    q = f'{c["name"]} Miss Universe {c["country"]} instagram' if c["contest"] == "mu" else f'{c["name"]} {c["country"]} instagram miss'
    page = U.get("https://www.bing.com/search?setlang=es&q=" + urllib.parse.quote(q))
    cands = {}
    for h in re.findall(r"instagram\.com/([A-Za-z0-9_.]{3,30})(?=[/\"?&<\s])", page):
        hl = h.lower().strip(".")
        if hl in BAD_HANDLES:
            continue
        cands[hl] = cands.get(hl, 0) + 1
    parts = [p for p in re.split(r"[^a-z]+", U.norm(c["name"])) if len(p) >= 3]
    best, conf = None, None
    for h, n in sorted(cands.items(), key=lambda x: -x[1]):
        hn = re.sub(r"[^a-z]", "", h)
        if any(p in hn for p in parts):
            return h, "alta"
        if best is None:
            best, conf = h, "baja"
    return best, conf


def bing_cell(c, cat):
    cid, label, en, _ = cat
    base = {"mu": "Miss Universe 2026", "mi": "Miss International 2026", "me": "Miss Earth 2026"}.get(c["contest"], "Miss Universe 2026")
    q = f'"{c["name"]}" {base.split(" 20")[0]} {en}'
    page = U.get("https://www.bing.com/images/search?form=HDRSC2&first=1&mkt=en-US&q=" + urllib.parse.quote(q))
    parts = [p for p in re.split(r"[^a-z]+", U.norm(c["name"])) if len(p) >= 4]
    cty = {U.norm(c["country"]), U.norm(c.get("country_es") or "")}
    out, raws, sample = [], re.findall(r'\bm="(\{[^"]+\})"', page), None
    for raw in raws:
        try:
            d = json.loads(html.unescape(raw))
        except Exception:
            continue
        u, pg, t = d.get("murl"), d.get("purl") or "", U.norm((d.get("t") or "") + " " + (d.get("desc") or "") + " " + urllib.parse.unquote(d.get("purl") or ""))
        if not u or re.search(r"logo|icon|\.svg|\.gif", u, re.I):
            continue
        who_ok = any(p in t for p in parts)
        sample = sample or t[:120]
        if not who_ok:
            continue
        out.append({"url": u, "thumb": d.get("turl"), "page": pg, "title": (d.get("t") or "")[:140], "via": "Bing Imágenes",
                    "credit": urllib.parse.urlparse(pg or u).netloc.replace("www.", ""), "from_ig": "instagram.com" in pg})
        if len(out) >= 6:
            break
    DIAG.append(f"{c['country']}/{cid}: {len(raws)} crudos, {len(out)} válidos; ej: {sample}; bytes={len(page)}")
    return out


DESIGNER_STYLES = {  # estilos conocidos de las series oficiales (se completan con lo observado)
    "gianninaazar": ("mu75-bano-marfil", "Sesión oficial 75° · traje de baño marfil (fondo verde menta)", "bano"),
}
COUNTRY_ALIAS = {"democratic republic of congo": "dr congo", "democratic republic of the congo": "dr congo", "reunion island": "reunion", "the bahamas": "bahamas",
                 "turks and caicos": "turks and caicos islands", "the netherlands": "netherlands", "the philippines": "philippines",
                 "ecuatorial guinea": "equatorial guinea", "saint-martin": "saint martin", "usa": "united states",
                 "us virgin islands": "united states virgin islands", "uk": "great britain", "dr congo": "democratic republic of the congo",
                 "czechia": "czech republic", "turkiye": "turkey", "curacao": "curacao", "korea": "south korea"}


def match_country(name, contestants, contest="mu"):
    import difflib
    n = U.norm(name).strip(" .!✨")
    n = COUNTRY_ALIAS.get(n, n)
    table = {}
    for c in contestants:
        if c["contest"] != contest:
            continue
        for t in {U.norm(c["country"]), U.norm(c.get("country_es") or "")}:
            if t:
                table[t] = c
    if n in table:
        return table[n]
    hit = difflib.get_close_matches(n, list(table), n=1, cutoff=0.82)
    return table[hit[0]] if hit else None


ENDI = "https://www.elnuevodia.com/entretenimiento/farandula/fotogalerias/miss-universe-2026-conoce-aqui-a-las-candidatas/"


def _walk(o, out):
    if isinstance(o, dict):
        if o.get("type") == "image" and o.get("url"):
            out.append(o)
        for v in o.values():
            _walk(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk(v, out)


def now_utc():
    return datetime.now(timezone.utc)


def endi_render():
    """Abre la galería en Chromium (Playwright), recorre las 110 diapositivas y junta foto + pie de foto,
    tanto del JSON que carga la página como de lo que se ve en pantalla."""
    import subprocess, sys
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"], check=True, timeout=300)
        subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        from playwright.sync_api import sync_playwright
    found = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36")

        def on_resp(r):
            try:
                if "json" in (r.headers.get("content-type") or ""):
                    _walk(r.json(), found)
            except Exception:
                pass
        pg.on("response", on_resp)
        pg.goto(ENDI, wait_until="domcontentloaded", timeout=90000)
        pg.wait_for_timeout(8000)
        for t in ("Aceptar todo", "ACEPTAR"):  # banner de cookies
            try:
                pg.get_by_text(t, exact=True).first.click(timeout=2000)
                break
            except Exception:
                pass
        pg.wait_for_timeout(1500)
        seen, stale = set(), 0
        for _ in range(160):  # recorrer la galería con su flecha "siguiente"
            got = pg.evaluate("""() => [...document.querySelectorAll('[class*=gallery-track] img')].map(i => [i.currentSrc || i.src, i.alt || ''])""")
            new = [g for g in got if g[0].startswith("http") and g[0] not in seen]
            for u, alt in new:
                seen.add(u)
                found.append({"type": "image", "url": u, "caption": alt, "gallery": True})
            stale = 0 if new else stale + 1
            if stale >= 10:
                break
            btns = pg.query_selector_all("button.featured-gallery-controller")
            if not btns:
                break
            try:
                btns[-1].click(timeout=3000)
                pg.wait_for_timeout(450)
            except Exception:
                break
        found.append({"type": "_diag", "gallery_imgs": len(seen), "clicks_stale": stale})
        b.close()
    return found


def endi_official(G, cs):
    """Galería 'Conoce aquí a las candidatas' de El Nuevo Día (Puerto Rico, sede 2026): fotos oficiales con crédito
    'Suministrada/Organización Miss Universe'. Se leen del JSON de la página (Arc), se asignan por país/nombre del pie."""
    import hashlib
    html = U.get(ENDI, timeout=30)
    imgs, rdiag = [], None
    for mark in ("Fusion.globalContent=", "Fusion.globalContent ="):
        i = html.find(mark)
        if i >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(html[i + len(mark):].lstrip())
                _walk(obj, imgs)
            except Exception as e:
                G["endi_diag"] = {"error": repr(e)[:200]}
            break
    if len(imgs) < 20:  # la galería se carga con JavaScript: abrir la página como un navegador
        last = G.get("endi_render_at")
        wait = 600 if len(G.get("endi") or {}) < 20 else 6 * 3600
        if not last or U.load("roster.json", {}).get("v") != 3 or (now_utc() - datetime.fromisoformat(last)).total_seconds() > wait:
            G["endi_render_at"] = now_utc().isoformat()
            try:
                got = endi_render()
                rdiag = next((x for x in got if x.get("type") == "_diag"), None)
                imgs = [x for x in got if x.get("type") == "image" and x.get("gallery") and re.match(r"[^,]{3,40},\s*\S", x.get("caption") or "")]
            except Exception as e:
                G["endi_diag"] = {"render_error": repr(e)[:300]}
        elif len(G.get("endi") or {}) >= 20:
            return -1, len(G["endi"])
    if not imgs:  # respaldo: cualquier bloque JSON con imágenes de Arc
        for m in re.finditer(r'\{"_id":"[A-Z0-9]{20,}"[^{}]*?"type":"image"[^{}]*?"url":"(https?://[^"]+)"', html):
            imgs.append({"url": m.group(1), "caption": ""})
    import difflib
    mu = [c for c in cs if c["contest"] == "mu"]
    cmap = U.load("countries.json", {})
    es2 = {}
    for en, (es, iso, reg) in sorted(cmap.items(), key=lambda x: len(x[0])):  # nombre en inglés más corto primero
        es2.setdefault(U.norm(es), (en, es, iso, reg))
        es2.setdefault(U.norm(en), (en, es, iso, reg))
    names = {}
    for c in mu:
        for t in {U.norm(c.get("country_es") or ""), U.norm(c["country"])}:
            if t:
                names[t] = c

    def match(country, person):
        pn = [x for x in re.split(r"[^a-z]+", U.norm(person)) if len(x) >= 3]
        t = U.norm(country)
        t = {"republica democratica del congo": "rd congo", "gran bretana": "great britain", "islas de reunion": "reunion"}.get(t, t)
        if t in names:  # 1) país exacto (lo más confiable)
            return names[t]
        en = es2.get(t)
        if en:
            for c in mu:
                if c["country"] == en[0] or (en[2] and c.get("iso") == en[2]):
                    return c
        last = pn[-1] if pn else ""
        for c in mu:  # 2) nombre, exigiendo el apellido
            cn = re.split(r"[^a-z]+", U.norm(c["name"]))
            if last and last in cn and len(set(pn) & set(cn)) >= min(2, len(pn)):
                return c
        if len(last) >= 6:  # 3) apellido largo y único
            same = [c for c in mu if last in re.split(r"[^a-z]+", U.norm(c["name"]))]
            if len(same) == 1:
                return same[0]
        close = difflib.get_close_matches(t, list(names), n=1, cutoff=0.88)  # 4) país parecido
        return names[close[0]] if close else None

    out, roster, n_ok, seen = {}, [], 0, set()
    for im in imgs:
        u = im["url"]
        cap = (im.get("caption") or im.get("subtitle") or "").strip()
        m = re.match(r"([^,]{3,45}),\s*(.+)$", cap)
        if u in seen or not m:
            continue
        seen.add(u)
        country, person = m.group(1).strip(), m.group(2).strip()
        hit = match(country, person)
        if hit:
            k = hit["contest"] + "|" + hit["country"]
            roster.append({**{f: hit.get(f) for f in ("contest", "country", "country_es", "iso", "region", "age", "hometown")}, "name": person, "official": True})
        else:
            en = es2.get({"republica democratica del congo": "rd congo"}.get(U.norm(country), U.norm(country)))
            if not en:
                close = difflib.get_close_matches(U.norm(country), list(es2), n=1, cutoff=0.8)
                en = es2[close[0]] if close else (None, country, "", "")
            roster.append({"contest": "mu", "country": en[0] or country, "country_es": en[1] or country, "iso": en[2], "region": en[3], "name": person, "official": True, "new": True})
            k = "mu|" + (en[0] or country)
        out.setdefault(k, []).append({"url": u, "mkey": "endi_" + hashlib.md5(u.encode()).hexdigest()[:14], "page": ENDI,
                                      "via": "Organización Miss Universe (vía El Nuevo Día)", "credit": "Organización Miss Universe",
                                      "title": cap[:160], "date": im.get("created_date") or im.get("last_updated_date")})
        n_ok += 1
    if len(roster) >= 50:
        U.save("roster.json", {"v": 3, "updated": U.NOW.isoformat(), "source": ENDI, "mu": roster})
    G["endi"] = out
    G["endi_diag"] = {**G.get("endi_diag", {}), "found": len(imgs), "assigned": n_ok, "render": rdiag,
                      "sample": [{"url": i["url"], "cap": (i.get("caption") or i.get("subtitle") or "")[:80]} for i in imgs[:4]]}
    return len(imgs), len(out)


def ig_series(G, contestants):
    """Series oficiales de @missuniverse: 'From {país} to the Universe … Official M*U picture : fotógrafo  Designer : diseñador'.
    Cada serie (fotógrafo + diseñador) es un estilo de retrato distinto; cada foto del carrusel conserva su posición."""
    out, styles, unmatched = {}, {}, []
    roles = U.load("portrait_styles.json", {}).get("roles", {})
    for p in G["ig_posts"].values():
        if p.get("owner") != "missuniverse":
            continue
        cap = p.get("caption", "")
        m = re.search(r"from (.+?) to the universe", cap, re.I)
        if not m or not re.search(r"official m\W*u picture", cap, re.I):
            continue
        c = match_country(m.group(1), contestants)
        if not c:
            unmatched.append(m.group(1))
            continue
        ph = (re.search(r"picture\s*:\s*@?([\w.]+)", cap, re.I) or [None, ""])[1]
        de = (re.search(r"designer\s*:\s*@?([\w.]+)", cap, re.I) or [None, ""])[1]
        sid, label, cat = DESIGNER_STYLES.get(de.lower(), (f"mu-oficial-{slug_(de or ph)}", f"Sesión oficial · @{de or ph} (estilo nuevo, sin describir)", "otras"))
        meta = U.load("portrait_styles.json", {}).get("styles", {}).get(sid, {})
        label = meta.get("label", label)
        st = styles.setdefault(sid, {"id": sid, "label": label, "short": meta.get("short", label), "desc": meta.get("desc"), "cat": cat,
                                     "photographer": ph, "designer": de, "posts": 0, "roles": roles.get(sid, [])})
        st["posts"] += 1
        k = c["contest"] + "|" + c["country"]
        p["who"] = [k]
        p["style"] = sid
        for j, u in enumerate(p.get("images", [])):
            role = (roles.get(sid) or [])[j] if j < len(roles.get(sid) or []) else f"foto {j + 1} de {len(p['images'])}"
            out.setdefault(f"{k}|{cat}", []).append({
                "url": u, "thumb": u, "mkey": f"{p['code']}_{j}", "page": p["url"], "via": "Instagram @missuniverse (oficial)", "credit": f"Foto: @{ph} · Diseño: @{de}" if de else f"Foto: @{ph}",
                "title": f"{c['country_es']} · {label} · {role}", "style": sid, "style_label": label, "role": role, "role_n": j + 1,
                "likes": p.get("likes"), "comments": p.get("comments"), "date": p.get("taken"), "official": True, "ig": True})
    for k in out:
        out[k].sort(key=lambda x: (x["style"], x["role_n"]))
    return out, styles, unmatched


def slug_(s):
    return re.sub(r"[^a-z0-9]+", "-", U.norm(s or "x")).strip("-")[:30]


def wp_official(G, contestants, max_pages=12):
    """Biblioteca de medios oficial de missuniverse.com (API pública de WordPress, autorizada por Javi)."""
    import urllib.request
    base = "https://www.missuniverse.com/wp-json/wp/v2/media"
    since = G.get("wp_since") or "2026-08-01T00:00:00"
    items, page, pages = [], 1, 1
    while page <= min(pages, max_pages):
        url = (f"{base}?per_page=100&page={page}&orderby=date&order=desc&after={since}"
               "&_fields=id,date,source_url,title,alt_text,caption,media_details")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CROWN-panel (uso editorial)", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            pages = int(r.headers.get("X-WP-TotalPages") or 1)
            batch = json.loads(r.read().decode("utf-8", "replace"))
        items += batch
        page += 1
        time.sleep(1.0)
    lib = G.setdefault("wp_media", {})
    for m in items:
        sizes = (m.get("media_details") or {}).get("sizes") or {}
        thumb = (sizes.get("medium_large") or sizes.get("large") or sizes.get("medium") or {}).get("source_url")
        lib[str(m["id"])] = {"id": m["id"], "date": m["date"], "url": m["source_url"], "thumb": thumb or m["source_url"],
                             "title": html.unescape((m.get("title") or {}).get("rendered", "")),
                             "alt": m.get("alt_text") or "", "caption": re.sub("<[^>]+>", "", (m.get("caption") or {}).get("rendered", ""))[:200]}
    # asignar a candidata y categoría
    by_country = []
    for c in contestants:
        if c["contest"] != "mu":
            continue
        terms = {U.norm(c["country"]), U.norm(c.get("country_es") or "")}
        nm = U.norm(c["name"])
        pats = [re.escape(t).replace("\\ ", "[\\s_-]+") for t in terms if t] + [re.escape(p) for p in nm.split() if len(p) >= 5]
        by_country.append((re.compile(r"(?<![a-z])(" + "|".join(pats) + r")(?![a-z])"), c))
    off, unassigned = {}, []
    for m in lib.values():
        fn = urllib.parse.unquote(m["url"].rsplit("/", 1)[-1])
        text = U.norm(" ".join([m["title"], m["alt"], m["caption"], re.sub(r"[-_]+", " ", fn)]))
        hits = [c for rx, c in by_country if rx.search(text)]
        if len(hits) != 1:
            if not hits:
                unassigned.append(m["title"] or fn)
            continue
        c = hits[0]
        cats = classify(text) or ["otras"]
        k = c["contest"] + "|" + c["country"]
        for cat in cats[:2]:
            off.setdefault(f"{k}|{cat}", []).append({"url": m["url"], "thumb": m["thumb"], "page": m["url"], "via": "Miss Universe (oficial)",
                                                    "credit": "Miss Universe Organization", "title": m["title"] or fn, "date": m["date"], "official": True})
    for k in off:
        off[k].sort(key=lambda x: x["date"], reverse=True)
    for k, v in off.items():
        cur = G.setdefault("official", {}).setdefault(k, [])
        for x in v:
            if x["url"] not in [y["url"] for y in cur]:
                cur.append(x)
    G["wp_diag"] = {"total": len(lib), "nuevos": len(items), "asignadas": sum(len(v) for v in off.values()),
                    "sin_asignar_ejemplos": unassigned[:40], "titulos_recientes": [m["title"] for m in sorted(lib.values(), key=lambda x: x["date"], reverse=True)[:40]]}
    if items:
        G["wp_since"] = max(m["date"] for m in items)
    return len(items), sum(len(v) for v in off.values())


def muorg_official(G, contestants, max_pages=25):
    """Sitio oficial missuniverseorg.com (votación y perfiles). Constructor GoDaddy: las fotos viven en img1.wsimg.com
    y el contenido en scripts 'gpub'. Se recorren las páginas internas y se extraen imágenes con su texto cercano."""
    root = "https://missuniverseorg.com"
    seen, queue, found, pages_ok = set(), ["/vote", "/"], {}, 0
    while queue and len(seen) < max_pages:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        try:
            page = U.get(root + path, timeout=25)
        except Exception:
            continue
        pages_ok += 1
        for h in re.findall(r'href="(/[a-z0-9][a-z0-9/_-]{1,60})"', page, re.I):
            if h not in seen and h not in queue and not re.search(r"\.(css|js|png|jpe?g|svg)$", h, re.I):
                queue.append(h)
        blobs = [page]
        for sc in re.findall(r'<script[^>]+src="(//img1\.wsimg\.com/blobby/go/[^"]+/gpub/[^"]+)"', page)[:6]:
            try:
                blobs.append(U.get("https:" + sc, timeout=25))
            except Exception:
                pass
        for blob in blobs:
            txt = blob.replace("\\/", "/").replace("\\u002F", "/")
            for m in re.finditer(r"(?:https?:)?//img1\.wsimg\.com/isteam/ip/[0-9a-f-]{36}/([^\"'\s)\\]+?)(?=/:/|[\"'\s)\\])", txt):
                fn = urllib.parse.unquote(m.group(1))
                if re.search(r"logo|icon|favicon|thumbnail-", fn, re.I):
                    continue
                url = "https:" + m.group(0) if m.group(0).startswith("//") else m.group(0)
                ctx = re.sub(r"<[^>]+>|\\[nrt]", " ", txt[max(0, m.start() - 350): m.end() + 350])
                rec = found.setdefault(url, {"url": url, "fn": fn, "ctx": "", "page": root + path})
                rec["ctx"] = (rec["ctx"] + " " + ctx)[:900]
    matchers = []
    for c in contestants:
        if c["contest"] != "mu":
            continue
        terms = {U.norm(c["country"]), U.norm(c.get("country_es") or "")}
        pats = [re.escape(t).replace("\\ ", "[\\s_-]+") for t in terms if t] + [re.escape(p) for p in U.norm(c["name"]).split() if len(p) >= 5]
        matchers.append((re.compile(r"(?<![a-z])(" + "|".join(pats) + r")(?![a-z])"), c))
    off = G.setdefault("official", {})
    assigned, samples = 0, []
    for rec in found.values():
        fn_text = U.norm(re.sub(r"[-_.]+", " ", rec["fn"]))
        hits = [c for rx, c in matchers if rx.search(fn_text)] or [c for rx, c in matchers if rx.search(U.norm(rec["ctx"]))]
        samples.append(rec["fn"])
        if len(hits) != 1:
            continue
        c = hits[0]
        cats = classify(fn_text + " " + U.norm(rec["ctx"])) or ["retrato"]
        k = c["contest"] + "|" + c["country"]
        lst = off.setdefault(f"{k}|{cats[0]}", [])
        if rec["url"] not in [x["url"] for x in lst]:
            lst.insert(0, {"url": rec["url"] + "/:/rs=w:1600", "thumb": rec["url"] + "/:/rs=w:600", "page": rec["page"], "via": "missuniverseorg.com (oficial)",
                           "credit": "Miss Universe Organization", "title": rec["fn"], "official": True})
            assigned += 1
    G["muorg_diag"] = {"paginas": pages_ok, "visitadas": sorted(seen)[:40], "imagenes": len(found), "asignadas": assigned, "ejemplos": samples[:60]}
    return len(found), assigned


def press_images(G, contestants):
    """Fotos de notas de prensa que nombran a la candidata (sin miniaturas de YouTube ni de buscadores)."""
    feed = U.load("feed.json", {"items": []}).get("items", [])
    arts = U.load("articles.json", {})
    press = {}
    names = {c["contest"] + "|" + c["country"]: c for c in contestants}
    for it in feed:
        who = [w["contest"] + "|" + w["country"] for w in it.get("who", [])]
        if not who or len(who) > 2:
            continue
        text = it.get("title", "") + " " + it.get("summary", "")
        cats = classify(text) or ["otras"]
        imgs = []
        a = arts.get(it.get("link"), {})
        for u in a.get("images", [])[:4]:
            if not BAD_IMG.search(u):
                imgs.append({"url": u, "via": "Prensa", "credit": it.get("source")})
        for k in who:
            if k not in names:
                continue
            for cat in cats[:2]:
                lst = press.setdefault(f"{k}|{cat}", [])
                for im in imgs:
                    if im["url"] not in [x["url"] for x in lst]:
                        lst.append({**im, "page": it.get("link"), "title": it.get("title", "")[:140], "date": it.get("published")})
    press = {k: v for k, v in press.items() if v}
    for k in press:
        press[k] = sorted(press[k], key=lambda x: x.get("date") or "", reverse=True)[:24]
    G["press"] = press
    return sum(len(v) for v in press.values())


def apply_roster(cs):
    """Lista oficial (galería de la Organización MU): reemplaza a las de Miss Universe que no están y suma las que faltan."""
    r = U.load("roster.json", {}).get("mu") or []
    if len(r) < 50:
        return cs
    have = {c["contest"] + "|" + c["country"]: c for c in cs}
    mu = [{**have.get(x["contest"] + "|" + x["country"], {}), **{k: v for k, v in x.items() if v not in (None, "")}} for x in r]
    inr = {x["contest"] + "|" + x["country"] for x in mu}
    extra = [{**c, "no_roster": True} for c in cs if c["contest"] == "mu" and c["contest"] + "|" + c["country"] not in inr]
    return [c for c in cs if c["contest"] != "mu"] + mu + extra


def run(mod, contestants, deadline_s=200):
    global U
    U = mod
    t0 = time.time()
    G = U.load("gallery.json", {"cells": {}, "handles": {}, "ig_posts": {}, "accounts": {}})
    for k in ("cells", "handles", "ig_posts", "accounts"):
        G.setdefault(k, {})
    now = U.NOW
    cs_raw = [c for c in contestants if c.get("contest") in ("mu", "mi") and c.get("name")]
    cs = apply_roster(cs_raw)
    prio = lambda c: (0 if c.get("hot") or c["country"] in ("Chile",) else 1, 0 if c["contest"] == "mu" else 1)
    cs.sort(key=prio)

    # --- 1. cuentas de IG de candidatas (descubrimiento, 12 por corrida)
    found = 0
    for c in cs:
        if time.time() - t0 > deadline_s * 0.25 or found >= 6:
            break
        k = c["contest"] + "|" + c["country"]
        h = G["handles"].get(k, {})
        if c.get("ig"):
            G["handles"][k] = {**h, "handle": c["ig"].lower(), "conf": "verificada", "name": c["name"]}
            continue
        if h.get("conf") in ("verificada", "mencionada") or (h.get("tried") and h.get("name") == c["name"]):
            continue
        try:
            handle, conf = find_handle(c)
            G["handles"][k] = {"handle": handle, "conf": conf, "tried": now.isoformat(), "name": c["name"]}
            found += 1
        except Exception as e:
            G["handles"][k] = {**h, "tried": now.isoformat(), "name": c["name"], "error": str(e)[:80]}
        time.sleep(2.0)
    U.note("Instagram · cuentas de candidatas descubiertas", True, sum(1 for v in G["handles"].values() if v.get("handle")))

    # --- 2. Instagram
    #   a) Graph API oficial (si hay credenciales): cuentas oficiales + candidatas en rotación
    extra = U.load("instagram.json", {"accounts": []}).get("accounts", [])
    accounts = [(a, cid, kind) for a, cid, kind in BASE_ACCOUNTS] + [(x["handle"], x.get("contest", "mu"), x.get("kind", "manual")) for x in extra if x.get("handle")]
    for pid, rec in (U.load("socials.json", {}).get("pageants") or {}).items():
        ig = rec.get("instagram") or {}
        if ig.get("verified") and ig.get("handle") and ig["handle"] not in [a[0] for a in accounts]:
            accounts.append((ig["handle"], pid, "oficial"))
    import igsync
    igsync.U = U
    G.setdefault("orgs", dict(igsync.BASE_ORGS))
    cand_acc = [(v["handle"], k.split("|")[0], "candidata") for k, v in G["handles"].items() if v.get("handle") and v.get("conf") in ("alta", "verificada")]
    cand_acc += [(h, k.split("|")[0], "org. nacional") for h, k in G["orgs"].items() if h not in [a[0] for a in accounts]]
    cand_acc.sort(key=lambda a: G["accounts"].get(a[0], {}).get("fetched", ""))
    import os
    if os.environ.get("IG_TOKEN") and os.environ.get("IG_USER_ID"):
        try:  # primero descubrir cuentas (antes de gastar la cuota de la API leyendo cuentas)
            nd0 = igsync.discover(G, cs)
            U.note("Instagram · menciones revisadas antes de sincronizar", True, nd0)
        except Exception as e:
            U.note("Instagram · menciones", False, err=repr(e)[:200])
        cand_acc = [(v["handle"], k.split("|")[0], "candidata") for k, v in G["handles"].items() if v.get("handle") and v.get("conf") in ("alta", "verificada")] + cand_acc
        cand_acc = list(dict.fromkeys(cand_acc))
        ok = 0
        for handle, cid, kind in accounts + cand_acc[:14]:
            if time.time() - t0 > deadline_s * 0.5:
                break
            try:
                full = (now - datetime.fromisoformat(G["accounts"].get(handle, {}).get("full_at", "2000-01-01T00:00:00+00:00"))).total_seconds() > 12 * 3600
                known = frozenset() if full else frozenset(c for c, x in G["ig_posts"].items() if x.get("owner") == handle)
                p = ig_graph(handle, known, max_pages=(8 if kind == "oficial" else 2) if full else 1)
                G["accounts"][handle] = {"name": p.get("name"), "followers": p.get("followers"), "media_count": p.get("media_count"), "pic": p.get("pic"), "contest": cid, "kind": kind, "fetched": now.isoformat(),
                                      "full_at": now.isoformat() if full else G["accounts"].get(handle, {}).get("full_at")}
                for post in p["posts"]:
                    post["contest"], post["kind"] = cid, kind
                    G["ig_posts"][post["code"]] = {**G["ig_posts"].get(post["code"], {}), **post, "seen": now.isoformat()}
                ok += 1
            except Exception as e:
                G["accounts"].setdefault(handle, {})["error"] = str(e)[:100]
            time.sleep(0.5)
        U.note("Instagram · Graph API oficial (cuentas leídas)", True, ok,
               err=f"{len([a for a in G['accounts'].values() if a.get('fetched')])} cuentas sincronizadas en total · {sum(1 for v in G['handles'].values() if v.get('conf') == 'verificada')} candidatas · {len(G['orgs'])} organizaciones")
        try:
            igsync.hashtag_sync(G, now)
        except Exception as e:
            U.note("Instagram · hashtags", False, err=repr(e)[:200])
    else:
        U.note("Instagram · Graph API oficial: sin conectar (opcional)", True, 0)
    #   b) Siempre: posts públicos encontrados por búsqueda web (se muestran con el embed oficial de Instagram)
    n = 0
    order = sorted(cs, key=lambda c: G.get("igsearch", {}).get(c["contest"] + "|" + c["country"], ""))
    G.setdefault("igsearch", {})
    for c in order[:6]:
        if time.time() - t0 > deadline_s * 0.6:
            break
        k = c["contest"] + "|" + c["country"]
        try:
            for post in ig_search_posts(c):
                post["contest"], post["kind"], post["hint"] = c["contest"], "búsqueda", k
                prev = G["ig_posts"].get(post["code"], {})
                G["ig_posts"][post["code"]] = {**post, **{kk: vv for kk, vv in prev.items() if vv}, "seen": now.isoformat()}
                n += 1
        except Exception:
            pass
        G["igsearch"][k] = now.isoformat()
        time.sleep(2.0)
    U.note("Instagram · posts encontrados por búsqueda web", True, n)

    # asignar posts de IG a candidata + categoría
    by_handle = {v["handle"]: k for k, v in G["handles"].items() if v.get("handle") and v.get("conf") in ("alta", "verificada")}
    by_handle.update(G.get("orgs", {}))
    matchers = []
    for c in cs:
        nm = U.norm(c["name"])
        pats = [re.escape(nm)] + ([re.escape(nm.split()[0]) + r"\W+(?:\w+\W+)?" + re.escape(nm.split()[-1])] if len(nm.split()) > 1 else [])
        for t in {U.norm(c["country"]), U.norm(c.get("country_es") or "")}:
            if t:
                pats.append(r"miss (?:universe |universo |international |internacional )?" + re.escape(t) + r"\b")
        matchers.append((re.compile("|".join(pats)), c))
    cutoff = now - timedelta(days=90)
    for code, p in list(G["ig_posts"].items()):
        if datetime.fromisoformat(p.get("taken") or p.get("seen")) < cutoff:
            G["ig_posts"].pop(code)
            continue
        cap = U.norm(p.get("caption", ""))
        who = []
        if p.get("owner") in by_handle:
            who.append(by_handle[p["owner"]])
            p["kind"] = "candidata" if any(v.get("handle") == p["owner"] for v in G["handles"].values()) else "org. nacional"
        if p.get("hint") and not who:
            who.append(p["hint"])
        for rx, c in matchers:
            if p.get("owner") in by_handle and p.get("kind") == "candidata":
                break
            if c["contest"] == p.get("contest") and rx.search(cap):
                who.append(c["contest"] + "|" + c["country"])
        p["who"] = sorted(set(who))[:3]
        p["cats"] = classify(p.get("caption", ""))
    if os.environ.get("IG_TOKEN"):
        try:
            nd = igsync.discover(G, cs)
            ng, nf = igsync.guess_sync(G, cs)
            U.note("Instagram · búsqueda activa de cuentas (usuarios probables confirmados por la API)", True, nf,
                   err=f"{ng} usuarios probados en esta vuelta · {len(G.get('guess_tried', {}))} en total")
            U.note("Instagram · cuentas de candidatas y organizaciones (verificadas con la API)", True,
                   sum(1 for v in G["handles"].values() if v.get("conf") == "verificada"), err=f"{nd} menciones revisadas en esta vuelta; {len(G['orgs'])} organizaciones nacionales")
        except Exception as e:
            U.note("Instagram · descubrimiento de cuentas", False, err=repr(e)[:200])

    # --- 3. Respaldo: Bing por candidata × categoría (rotación, refresco cada 12 h)
    cats_by_contest = {"mu": CATS, "mi": [c for c in CATS if c[0] in ("retrato", "tipico", "gala")]}
    todo = []
    for c in cs:
        for cat in cats_by_contest.get(c["contest"], []):
            k = f'{c["contest"]}|{c["country"]}|{cat[0]}'
            cell = G["cells"].get(k, {})
            if cell.get("name") == c["name"] and cell.get("fetched") and (now - datetime.fromisoformat(cell["fetched"])).total_seconds() < (12 if cell.get("images") else 6) * 3600:
                continue
            todo.append((CAT_ORDER.index(cat[0]), prio(c), k, c, cat))
    todo.sort(key=lambda x: (x[1], x[0]))
    done, empties = 0, 0
    for _, _, k, c, cat in todo[:30]:
        if time.time() - t0 > deadline_s:
            break
        try:
            imgs = bing_cell(c, cat)
            if imgs:
                G["cells"][k] = {"name": c["name"], "fetched": now.isoformat(), "images": imgs}
                empties = 0
            else:
                empties += 1
        except Exception as e:
            empties += 1
        done += 1
        if empties >= 4:  # probable bloqueo: no insistir en esta corrida
            break
        time.sleep(2.5)
    total_cells = sum(len(cats_by_contest.get(c["contest"], [])) for c in cs)
    filled = sum(1 for v in G["cells"].values() if v.get("images"))
    zero = DIAG and all(" 0 crudos" in d for d in DIAG)
    U.note(f"Galería · Bing por candidata ({filled}/{total_cells} celdas)", not zero, done,
           err="Bing no entrega resultados de imágenes por candidata a los servidores de GitHub; se usan prensa, YouTube e Instagram" if zero else None)

    try:
        nw, asg = wp_official(G, cs)
        U.note("Galería · biblioteca oficial missuniverse.com", True, asg, err=f"{nw} medios nuevos; {G['wp_diag']['total']} en total")
    except Exception as e:
        U.note("Galería · biblioteca oficial missuniverse.com", False, err=repr(e)[:200])
    try:
        nf, asg = muorg_official(G, cs)
        U.note("Galería · missuniverseorg.com (oficial)", True, asg, err=f"{nf} imágenes encontradas en {G['muorg_diag']['paginas']} páginas")
    except Exception as e:
        U.note("Galería · missuniverseorg.com (oficial)", False, err=repr(e)[:200])
    G.pop("ytc", None)  # sin videos de YouTube por candidata: no sirven como fotos
    try:
        ne, ae = endi_official(G, cs_raw)
        U.note("Fotos oficiales Miss Universe · galería de candidatas (El Nuevo Día, crédito Organización Miss Universe)", ae > 0, ae,
               err=("en caché; se vuelve a leer cada 6 h" if ne == -1 else f"{ne} fotos leídas en la galería"))
    except Exception as e:
        U.note("Fotos oficiales Miss Universe · galería El Nuevo Día", False, err=repr(e)[:200])
    ser, styles, unm = ig_series(G, cs)
    G["ig_official"] = ser
    G["styles"] = styles
    U.note("Instagram · retratos oficiales por candidata", True, len({k.rsplit('|', 1)[0] for k in ser}),
           err=(f"sin país reconocido: {', '.join(sorted(set(unm))[:8])}" if unm else None))
    # fotos de Instagram de candidatas, organizaciones nacionales y hashtags → por candidata y categoría
    igc = {}
    posts = sorted(G["ig_posts"].values(), key=lambda p: p.get("taken") or "", reverse=True)
    start = {}
    for pg in U.load("pageants.json", {}).get("pageants", []):
        ev = [e for e in pg.get("events", []) if re.search(r"llegada|arrival", e.get("name", ""), re.I)]
        if ev:
            start[pg["id"]] = (datetime.fromisoformat(ev[0]["start"].replace("Z", "+00:00")) - timedelta(days=3)).isoformat()
    by_k = {c["contest"] + "|" + c["country"]: c for c in cs}
    rx_comp = re.compile(r"miss\s*universe|missuniverse|\bmu\s?75|#mu\b|puerto rico|miss universo|missuniverso|\buniverse\b|preliminar|national costume|traje t[ií]pico|rehearsal|ensayo", re.I)
    rx_promo = re.compile(r"\bvot(e|ez|a|en|ar|ing)\b|votaci[oó]n|soutenez|download|descarga|link in (the )?bio|enlace en (la )?bio|giveaway|sorteo|patrocin|sponsor|tickets?\b|boletos|entradas|countdown|cuenta regresiva|merch|discount|descuento|promo code|c[oó]digo", re.I)
    skipped = {"fuera de fecha": 0, "no habla de ella ni del concurso": 0, "hashtag / no oficial": 0, "promoción / votación / afiche": 0}
    for p in posts:
        who = p.get("who") or []
        if p.get("style") or len(who) != 1 or not p.get("images"):
            continue
        if p.get("kind") not in ("candidata", "org. nacional", "oficial"):
            skipped["hashtag / no oficial"] += 1
            continue
        c = by_k.get(who[0])
        if (p.get("taken") or "") < start.get(who[0].split("|")[0], (now - timedelta(days=45)).isoformat()):
            skipped["fuera de fecha"] += 1
            continue
        if p.get("kind") == "org. nacional" and c:
            cap = U.norm(p.get("caption") or "")
            parts = [x for x in re.split(r"[^a-z]+", U.norm(c["name"])) if len(x) >= 4]
            if not (any(x in cap for x in parts) or rx_comp.search(p.get("caption") or "")):
                skipped["no habla de ella ni del concurso"] += 1
                continue
        if rx_promo.search(p.get("caption") or ""):
            skipped["promoción / votación / afiche"] += 1
            continue
        p["images"] = [u for u in p["images"] if u and ".mp4" not in u]
        if not p["images"]:
            continue
        src = {"candidata": "Instagram de la candidata", "org. nacional": "Instagram de su organización nacional", "oficial": "Instagram oficial",
               "hashtag": "Instagram " + (p.get("via") or "#hashtag")}.get(p.get("kind"), "Instagram")
        for cat in (p.get("cats") or ["otras"])[:2]:
            lst = igc.setdefault(f"{who[0]}|{cat}", [])
            if len(lst) >= (12 if cat == "otras" else 30):
                continue
            for j, u in enumerate(p["images"][:6]):
                lst.append({"url": u, "thumb": u, "mkey": f"{p['code']}_{j}", "page": p.get("url"), "via": src, "credit": "@" + p["owner"] if p.get("owner") else src,
                            "title": (p.get("caption") or "")[:120], "likes": p.get("likes"), "comments": p.get("comments"), "date": p.get("taken"), "ig": True})
    G["ig_cand"] = igc
    U.note("Instagram · fotos y looks por candidata (filtradas)", True, sum(len(v) for v in igc.values()),
           err=f"{len({k.rsplit('|', 1)[0] for k in igc})} candidatas · descartadas: " + ", ".join(f"{n} {k}" for k, n in skipped.items()))
    # posts oficiales de grupo / del día (pasarelas, actividades): sirven para "outfits del día"
    evp = []
    cut = (now - timedelta(days=30)).isoformat()
    for p in posts:
        if p.get("kind") != "oficial" or p.get("style") or not p.get("images") or (p.get("taken") or "") < cut or len(p.get("who") or []) == 1:
            continue
        if re.search(r"\bvot(e|ing|a)\b|download|descarga|tickets?\b|boletos|sponsor|giveaway|link in bio|countdown", p.get("caption") or "", re.I):
            continue
        evp.append({"code": p["code"], "url": p.get("url"), "owner": p.get("owner"), "contest": p.get("contest"), "date": p.get("taken"),
                    "caption": (p.get("caption") or "")[:300], "who": p.get("who") or [], "likes": p.get("likes"), "comments": p.get("comments"),
                    "images": [{"url": u, "mkey": f"{p['code']}_{j}"} for j, u in enumerate(p["images"][:10])]})
    G["ig_event"] = evp[:80]
    import hashlib
    for v in (G.get("official") or {}).values():
        for x in v:
            x.setdefault("mkey", "web_" + hashlib.md5(x["url"].encode()).hexdigest()[:14])
    try:
        todo = [(x["mkey"], x["url"]) for v in (G.get("endi") or {}).values() for x in v]
        todo += [(x["mkey"], x["url"]) for v in (G.get("official") or {}).values() for x in v]
        todo += [(x["mkey"], x["url"]) for v in ser.values() for x in v]
        todo += [(im["mkey"], im["url"]) for e in evp[:40] for im in e["images"]]
        todo += [(x["mkey"], x["url"]) for v in sorted(igc.values(), key=lambda l: -(l[0].get("likes") or 0)) for x in v]
        igsync.mirror(G, todo, budget=220)
    except Exception as e:
        U.note("Espejo de imágenes", False, err=repr(e)[:200])
    # RETRATO OFICIAL = foto de estudio con fondo neutro claro, de la web oficial (o anunciada como retrato oficial por una cuenta oficial)
    mp = G.get("mirror") or {}
    ret, pend = {}, 0
    for key, v in (G.get("official") or {}).items():
        k = key.rsplit("|", 1)[0]
        for x in v:
            b = (mp.get(x["mkey"]) or {}).get("bg")
            if b == "claro":
                ret.setdefault(k, []).append({**x, "bg": b, "official": True, "src": "web oficial"})
            elif b is None:
                pend += 1
    for k, v in (G.get("endi") or {}).items():
        for x in v:
            m = mp.get(x["mkey"]) or {}
            b = m.get("bg")
            gris = b == "color" and m.get("bgc") and max(int(m["bgc"][i:i + 2], 16) for i in (1, 3, 5)) - min(int(m["bgc"][i:i + 2], 16) for i in (1, 3, 5)) < 18
            if b == "claro" or gris:  # fuente oficial: fondo neutro (claro o gris), nunca verde ni oscuro
                ret.setdefault(k, []).insert(0, {**x, "bg": "claro" if b == "claro" else "gris neutro", "official": True, "src": "web oficial"})
            elif b is None:
                pend += 1
    rx_head = re.compile(r"head\s?shot|official (portrait|photo)|retrato oficial|foto oficial", re.I)
    for p in posts:
        who = p.get("who") or []
        if len(who) != 1 or p.get("kind") not in ("oficial", "org. nacional") or not rx_head.search(p.get("caption") or ""):
            continue
        for j, u in enumerate(p.get("images") or []):
            m = mp.get(f"{p['code']}_{j}") or {}
            if m.get("bg") == "claro":
                ret.setdefault(who[0], []).append({"url": u, "mkey": f"{p['code']}_{j}", "page": p.get("url"), "via": "Instagram @" + (p.get("owner") or ""),
                                                   "credit": "@" + (p.get("owner") or ""), "title": (p.get("caption") or "")[:120], "date": p.get("taken"),
                                                   "bg": "claro", "official": p.get("kind") == "oficial", "ig": True, "src": "Instagram " + p.get("kind")})
    G["retrato"] = ret
    U.note("Retratos oficiales (fondo neutro claro, verificados por color)", True, len(ret),
           err=f"{pend} imágenes de la web oficial pendientes de revisar el fondo" if pend else None)
    try:
        import socials
        socials.run(U, G, cs, igsync, bool(os.environ.get("IG_TOKEN")))
    except Exception as e:
        U.note("Redes sociales", False, err=repr(e)[:200])
    n = press_images(G, cs)
    U.note("Galería · fotos de prensa y video atribuidas a candidatas", True, n)
    G["cats"] = [{"id": a, "label": b} for a, b, _, _ in CATS] + [{"id": "otras", "label": "Más fotos"}]
    G["updated"] = now.isoformat()
    U.save("gallery.json", G)
