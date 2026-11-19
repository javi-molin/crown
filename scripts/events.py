"""
CROWN · detector de eventos, campañas y micro-eventos.

- Fuentes extra: Bing Noticias (links directos + imagen), artículos (og:image, fotos, posts de IG/TikTok
  incrustados), búsqueda de imágenes de Bing, Wikimedia Commons, estadísticas de YouTube (RSS),
  estadísticas públicas de TikTok/Instagram cuando la plataforma las expone.
- Detecta eventos por: (1) eventos semilla conocidos, (2) agenda oficial, (3) frases entre comillas o
  en MAYÚSCULAS que se repiten en varias fuentes, (4) actividades (sesión de fotos, desfile, gala…)
  que aparecen en varias fuentes en una ventana de 3 días.
- Escribe data/events.json, data/articles.json (caché) y data/social.json (caché).
Todo es tolerante a fallos: si una fuente cae, el resto sigue.
"""
import json, re, html, time, urllib.parse, hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

U = None  # módulo update (get, note, norm, load, save, NOW, uid, tag_item…)

TRIGGERS = [
    ("Sesión de fotos oficial", r"retratos? oficial|sesion (de )?fotos|photo ?shoot|official (photos|portraits)|fotos oficiales|behind the scenes of the official|portrait"),
    ("Desfile de moda", r"runway|fashion show|desfile de moda|pasarela de moda|fashion week|desfile de disenadores"),
    ("Traje de baño", r"traje(s)? de bano|swimsuit|bikini|beauty (at|on) the beach"),
    ("Trajes típicos", r"traje(s)? tipico|national costume|natcos|traje(s)? nacional|traje de fantasia"),
    ("Preliminar", r"preliminar|preliminary"),
    ("Gala / cena", r"\bgala\b|\bcena\b|dinner|banquet|coctel|cocktail"),
    ("Tour / visita", r"\btour\b|visita|\bvisit|recorrido|safari|excursion"),
    ("Ensayos", r"ensayo|rehearsal"),
    ("Entrevistas", r"entrevista|interview|closed.door|media day|rueda de prensa|press conference"),
    ("Llegada / bienvenida", r"llegad|arriv|bienvenida|welcome|sashing|bandas"),
    ("Campaña / marca", r"campana|campaign|sponsor|patrocin|cosmetics|maquillaje|skincare|colaboracion|collab"),
    ("Causa / caridad", r"benefic|charity|hospital|caridad|voluntari|fundacion|beauty with a purpose|ods|sdg"),
    ("Votación", r"\bvot(o|ar|e|ing|aciones)\b|people.s choice"),
    ("Talento / reto", r"\btalent|challenge|\breto\b|desafio|sports? day|deportiv"),
]
MODIFIERS = {"retro": r"\bretro\b|vintage|antigu|clasic|1950|anos 50|anos cincuenta|old.?school|\bmarfil\b|\bivory\b",
             "playa": r"playa|beach|arena", "polémica": r"polemic|controvers|caida|cae|tropez|trip|fell|caos|mess"}
EVENT_NOUNS = r"\b(runway|beach|show|gala|parade|tour|night|party|shoot|photoshoot|dinner|ball|challenge|talk|costume|walk|desfile|noche|fiesta|pasarela|cena|sesion|fotos?|day|dia|experience|confidential|tea|brunch|awards?)\b"
STOP_PHRASES = {"miss universe", "miss universo", "miss universe 2026", "miss universo 2026", "miss international",
                "miss earth", "miss world", "miss grand international", "miss supranational", "miss universe organization",
                "top 30", "top 12", "top 5", "top 10", "top 20", "live", "en vivo", "full show", "vote now", "official"}

SEED = [
    {"id": "retratos-oficiales-75", "contest": "mu", "name": "Retratos oficiales del 75° aniversario (trajes de baño de los años 50)",
     "kind": "campaña oficial", "date": "2026-11-12",
     "keywords": [r"retratos? oficial|official (photos|portraits)|fotos oficiales|behind the scenes of the official", r"giannina azar|1950|anos 50|\bmarfil\b|\bivory\b|\bretro\b|\bvintage\b|\bcetro\b"],
     "match": "any",
     "desc": "Trajes de baño de una pieza en marfil, inspirados en los años 50 y diseñados por la dominicana Giannina Azar. Las candidatas posaron con el cetro.",
     "refs": ["https://cdn.com.do/?p=260949335", "https://www.radioagricultura.cl/entretencion/la-foto-de-dominga-lopez-que-conquista-redes-de-miss-universo_20261114/"],
     "image_query": "Miss Universe 2026 official portraits swimsuit Giannina Azar"},
    {"id": "runway-to-the-universe", "contest": "mu", "name": "Runway to the Universe (desfile de moda)", "kind": "evento oficial",
     "date": "2026-11-17", "keywords": [r"runway to the universe|desfile de moda.*(miss univers|puerto rico)|monic perez|27 disenadores"], "match": "any",
     "desc": "Desfile de moda oficial del 75° aniversario con 27 diseñadores de Puerto Rico. Animadora: Monic Pérez.",
     "refs": ["https://www.primerahora.com/entretenimiento/reinas-belleza/notas/monic-perez-sera-la-animadora-del-desfile-de-moda-runway-to-the-universe/"],
     "image_query": "Runway to the Universe Miss Universe 2026"},
    {"id": "beauty-at-the-beach", "contest": "mu", "name": "Beauty at the Beach (pasarela sobre la arena)", "kind": "evento (no oficial de MUO)",
     "date": "2026-11-13", "keywords": [r"beauty (at|on|and) the beach|caribe hilton|magali febles|pasarela.*arena"], "match": "any",
     "desc": "Pasarela de traje de baño sobre la arena del Caribe Hilton. Varias candidatas casi se caen; MUO se desligó y la productora pidió disculpas.",
     "refs": ["https://www.hola.com/us/entertainment/20261116935333/miss-universe-runway-event-contestants-at-risk/"],
     "image_query": "Miss Universe 2026 Beauty at the Beach Caribe Hilton"},
    {"id": "bienvenida-aguadilla", "contest": "mu", "name": "Bienvenida oficial en Aguadilla (pasarela de 200 pies)", "kind": "evento oficial",
     "date": "2026-11-11", "keywords": [r"aguadilla|welcome parade|desfile de bienvenida"], "match": "any",
     "desc": "Bienvenida oficial a las candidatas con una pasarela de 200 pies.", "refs": ["https://www.metro.pr/tv/el-universo-desfilo-por-aguadilla-12dfddfe-466d-4d1b-8b28-32abf237a928"],
     "image_query": "Miss Universe 2026 Aguadilla welcome parade"},
    {"id": "voto-top30", "contest": "mu", "name": "Voto del público: pase directo al Top 30", "kind": "campaña oficial", "date": "2026-10-16",
     "keywords": [r"\bvot(o|ar|e|ing|aciones)\b.*(top 30|semifinal)|(top 30|semifinal).*\bvot|people.s choice|vote now"], "match": "any",
     "desc": "La candidata más votada en missuniverseorg.com/vote o en la app MU Fan entra directo al Top 30. También se vota mejor traje típico, traje de baño y gala.",
     "refs": ["https://www.elnuevodia.com/entretenimiento/farandula/notas/miss-universe-abre-votaciones-para-seleccion-de-una-de-las-30-semifinalistas-asi-puedes-apoyar-a-tu-favorita/"],
     "image_query": "Miss Universe 2026 vote top 30"},
    {"id": "mi-natcos", "contest": "mi", "name": "Miss International · Trajes típicos", "kind": "evento oficial", "date": "2026-11-14",
     "keywords": [r"national costume.*miss international|miss international.*national costume|miss internacional.*traje"], "match": "any",
     "desc": "Desfile de trajes típicos de Miss International 2026 (premiere en YouTube).", "refs": [], "image_query": "Miss International 2026 national costume"},
]


def slug(s):
    s = U.norm(s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def pub(i):
    try:
        return datetime.fromisoformat((i.get("published") or i.get("first_seen")).replace("Z", "+00:00"))
    except Exception:
        return U.NOW


# ------------------------------------------------------------------ fuentes
def bing_news(mod):
    global U
    U = mod
    out = []
    qs = [("mu", "Miss Universe 2026", "es-CL"), ("mu", "Miss Universe 2026", "en-US"), ("mu", "Miss Universo 2026 sesión de fotos", "es-CL"),
          ("mu", "Miss Universe 2026 runway fashion", "en-US"), ("mi", "Miss International 2026", "en-US"), ("me", "Miss Earth 2026", "en-US")]
    for cid, q, mkt in qs:
        try:
            xml = U.get(f"https://www.bing.com/news/search?q={urllib.parse.quote(q)}&format=rss&mkt={mkt}&qft=sortbydate%3d%221%22")
            root = ET.fromstring(xml)
            n = 0
            for it in root.iter("item"):
                link = it.findtext("link") or ""
                qd = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                real = qd.get("url", [link])[0]
                img = src = None
                for ch in it:
                    tag = ch.tag.split("}")[-1].lower()
                    if tag == "image":
                        img = (ch.text or "").strip()
                    elif tag == "source":
                        src = (ch.text or "").strip()
                try:
                    from email.utils import parsedate_to_datetime
                    p = parsedate_to_datetime(it.findtext("pubDate"))
                except Exception:
                    p = U.NOW
                if img and img.startswith("/"):
                    img = "https://www.bing.com" + img
                out.append({"id": U.uid(real), "type": "news", "title": html.unescape(it.findtext("title") or "").strip(),
                            "summary": html.unescape(re.sub("<[^>]+>", "", it.findtext("description") or ""))[:300],
                            "link": real, "direct": True, "source": src or urllib.parse.urlparse(real).netloc.replace("www.", ""),
                            "published": U.iso(p), "lang": mkt[:2], "contests": [cid], "tags": [], "thumb": img, "query": q})
                n += 1
            U.note("Bing Noticias · " + q + " · " + mkt, True, n)
        except Exception as e:
            U.note("Bing Noticias · " + q + " · " + mkt, False, err=e)
        time.sleep(0.5)
    return out


IMG_BAD = re.compile(r"logo|icon|avatar|sprite|placeholder|blank|pixel|1x1|\.svg|\.gif|ads?[/_-]|banner|favicon", re.I)


def enrich_articles(items, budget=35):
    cache = U.load("articles.json", {})
    todo = [i for i in items if i.get("type") == "news" and i.get("direct") and i["link"] not in cache][:budget]
    ok = 0
    for i in todo:
        url = i["link"]
        rec = {"fetched": U.NOW.isoformat(), "images": [], "social": []}
        try:
            page = U.get(url, timeout=15)
            metas = re.findall(r'<meta[^>]+(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image(?::src)?)["\'][^>]*content=["\']([^"\']+)', page, re.I)
            metas += re.findall(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\']', page, re.I)
            figs = re.findall(r'<figure[^>]*>.*?<img[^>]+(?:data-src|src)=["\']([^"\']+)["\']', page, re.I | re.S)
            srcset = re.findall(r'<img[^>]+srcset=["\']([^"\']+)["\']', page, re.I)
            big = [s.split(",")[-1].strip().split(" ")[0] for s in srcset]
            imgs = []
            for u in metas + figs + big:
                u = html.unescape(u.strip())
                if u.startswith("//"):
                    u = "https:" + u
                if u.startswith("/"):
                    u = urllib.parse.urljoin(url, u)
                if u.startswith("http") and not IMG_BAD.search(u) and u not in imgs:
                    imgs.append(u)
            rec["images"] = imgs[:10]
            soc = set(re.findall(r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[\w-]+', page))
            soc |= set(re.findall(r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+', page))
            soc |= set("https://www.youtube.com/watch?v=" + v for v in re.findall(r'youtube\.com/embed/([\w-]{11})', page))
            rec["social"] = sorted(soc)[:12]
            title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)', page, re.I)
            rec["title"] = html.unescape(title.group(1)) if title else i["title"]
            ok += 1
        except Exception as e:
            rec["error"] = str(e)[:120]
        cache[url] = rec
        time.sleep(0.3)
    # poda: 1500 artículos máx.
    if len(cache) > 1500:
        for k in sorted(cache, key=lambda k: cache[k].get("fetched", ""))[: len(cache) - 1500]:
            cache.pop(k)
    U.save("articles.json", cache)
    U.note("Artículos (imágenes y posts incrustados)", True, ok)
    return cache


def social_stats(urls, budget=25):
    cache = U.load("social.json", {})
    stale = [u for u in urls if u not in cache or
             (U.NOW - datetime.fromisoformat(cache[u].get("fetched", "2000-01-01T00:00:00+00:00"))).total_seconds() > 3600]
    n = 0
    for u in stale[:budget]:
        rec = {"fetched": U.NOW.isoformat(), "url": u}
        try:
            if "tiktok.com" in u:
                rec["platform"] = "TikTok"
                try:
                    o = json.loads(U.get("https://www.tiktok.com/oembed?url=" + urllib.parse.quote(u)))
                    rec.update({"title": o.get("title"), "author": o.get("author_name"), "thumb": o.get("thumbnail_url")})
                except Exception:
                    pass
                page = U.get(u, timeout=15)
                for k, f in [("views", "playCount"), ("likes", "diggCount"), ("comments", "commentCount"), ("shares", "shareCount")]:
                    m = re.search(r'"%s":\s*"?(\d+)' % f, page)
                    if m:
                        rec[k] = int(m.group(1))
            elif "instagram.com" in u:
                rec["platform"] = "Instagram"
                code = re.search(r"/(?:p|reel|tv)/([\w-]+)", u).group(1)
                page = U.get(f"https://www.instagram.com/p/{code}/embed/captioned/", timeout=15)
                m = re.search(r'"edge_liked_by":\{"count":(\d+)', page) or re.search(r'([\d.,]+)\s+(?:likes|Me gusta)', page)
                if m:
                    rec["likes"] = int(re.sub(r"[.,]", "", m.group(1)))
                m = re.search(r'"video_view_count":(\d+)', page)
                if m:
                    rec["views"] = int(m.group(1))
                m = re.search(r'class="Caption"[^>]*>.*?<a[^>]*>([^<]+)</a>(.*?)</div>', page, re.S)
                if m:
                    rec["author"] = m.group(1).strip()
                    rec["title"] = re.sub("<[^>]+>", " ", m.group(2)).strip()[:200]
                im = re.search(r'class="EmbeddedMediaImage"[^>]+src="([^"]+)"', page)
                if im:
                    rec["thumb"] = html.unescape(im.group(1))
            elif "youtube.com" in u:
                rec["platform"] = "YouTube"
                page = U.get(u, timeout=15)
                m = re.search(r'"viewCount":"(\d+)"', page)
                if m:
                    rec["views"] = int(m.group(1))
                t = re.search(r'<meta name="title" content="([^"]+)"', page)
                rec["title"] = html.unescape(t.group(1)) if t else None
                vid = re.search(r"v=([\w-]{11})", u)
                rec["thumb"] = f"https://i.ytimg.com/vi/{vid.group(1)}/hqdefault.jpg" if vid else None
            n += 1
        except Exception as e:
            rec["error"] = str(e)[:120]
        prev = cache.get(u, {})
        cache[u] = {**prev, **{k: v for k, v in rec.items() if v is not None}}
        time.sleep(0.4)
    U.save("social.json", cache)
    got = sum(1 for u in urls if any(k in cache.get(u, {}) for k in ("views", "likes")))
    U.note("Estadísticas de publicaciones (IG/TikTok/YouTube)", True, got)
    return cache


def bing_images(q, n=14):
    page = U.get("https://www.bing.com/images/search?form=HDRSC2&first=1&q=" + urllib.parse.quote(q))
    out = []
    for raw in re.findall(r'\bm="(\{[^"]+\})"', page):
        try:
            d = json.loads(html.unescape(raw))
        except Exception:
            continue
        u, pg = d.get("murl"), d.get("purl")
        if u and not IMG_BAD.search(u) and u not in [o["url"] for o in out]:
            out.append({"url": u, "page": pg, "via": "Bing Imágenes", "credit": urllib.parse.urlparse(pg or u).netloc.replace("www.", ""),
                        "alt": d.get("turl")})
        if len(out) >= n:
            break
    if not out:
        raise ValueError("sin resultados (formato cambió o bloqueo)")
    return out


def commons(q, n=10):
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=%d"
           "&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=1600&gsrsearch=%s") % (n, urllib.parse.quote(q))
    d = json.loads(U.get(url))
    out = []
    for p in (d.get("query", {}).get("pages", {}) or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        out.append({"url": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl"), "via": "Wikimedia Commons",
                    "license": (meta.get("LicenseShortName") or {}).get("value"),
                    "credit": re.sub("<[^>]+>", "", (meta.get("Artist") or {}).get("value", ""))[:80]})
    return [o for o in out if o["url"]]


# ------------------------------------------------------------------ detección
def phrases(title, official=False):
    out = set()
    for m in re.finditer(r'[“"‘\']([^“”"‘’\']{4,60})[”"’\']', title):
        out.add(m.group(1))
    for m in re.finditer(r"\b([A-Z][A-Z'&]+(?:\s+[A-Z][A-Z'&]+){1,5})\b", title):
        out.add(m.group(1))
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|to|the|at|on|of|de|la|el|del|and|y|en))+\s+[A-Z][a-z]+)\b", title):
        out.add(m.group(1))
    res = []
    for p in out:
        n = U.norm(p).strip(" .!?:-")
        w = n.split()
        if not (2 <= len(w) <= 7) or n in STOP_PHRASES or n.startswith(("miss ", "mister ", "mr ")):
            continue
        if not re.search(EVENT_NOUNS, n):
            continue
        res.append(n)
    return res


def detect(items, videos, contestant_names):
    official_vids = videos.get("official", [])
    pool = []
    for i in items:
        if i.get("type") == "alert":
            continue
        pool.append({"id": i["id"], "title": i.get("title", ""), "text": U.norm(i.get("title", "") + " " + i.get("summary", "")),
                     "src": i.get("source", ""), "pub": pub(i), "contest": (i.get("contests") or ["?"])[0],
                     "official": bool(i.get("official")), "type": i.get("type")})
    names = {U.norm(n) for n in contestant_names if n}
    ev = {}

    def add(key, name, contest, it, kind, label=None):
        e = ev.setdefault(key, {"key": key, "name": name, "contest": contest, "kind": kind, "labels": set(), "items": {}, "srcs": set(), "official": False})
        e["items"][it["id"]] = it
        e["srcs"].add(it["src"])
        e["official"] |= it["official"]
        if label:
            e["labels"].add(label)

    for it in pool:
        # semillas
        for s in SEED:
            hits = [bool(re.search(k, it["text"])) for k in s["keywords"]]
            if (s.get("match") == "all" and all(hits)) or (s.get("match", "any") == "any" and any(hits)):
                add("seed:" + s["id"], s["name"], s["contest"], it, s["kind"])
        # frases
        for ph in phrases(it["title"], it["official"]):
            if any(ph in n or n in ph for n in names if len(n) > 6):
                continue
            add("p:" + ph, ph.title(), it["contest"], it, "detectado")
        # disparadores
        for label, rx in TRIGGERS:
            if re.search(rx, it["text"]):
                mods = [m for m, mrx in MODIFIERS.items() if re.search(mrx, it["text"])]
                day = it["pub"].date()
                bucket = day - timedelta(days=(day.toordinal() % 3))
                add(f"t:{it['contest']}:{label}:{bucket}", label, it["contest"], it, "detectado", label)
                for m in mods:
                    add(f"t:{it['contest']}:{label}+{m}:{bucket}", f"{label} · {m}", it["contest"], it, "detectado", label)

    keep = {}
    for k, e in ev.items():
        n, s = len(e["items"]), len(e["srcs"])
        if k.startswith("seed:") and n >= 1:
            keep[k] = e
        elif k.startswith("p:") and (s >= 2 or e["official"] or n >= 3):
            keep[k] = e
        elif k.startswith("t:") and n >= 3 and s >= 2:
            keep[k] = e
    # fusionar: lo que se solapa mucho con un evento semilla o frase se absorbe
    order = sorted(keep, key=lambda k: (0 if k.startswith("seed:") else 1 if k.startswith("p:") else 2, -len(keep[k]["items"])))
    final = {}
    for k in order:
        e = keep[k]
        ids = set(e["items"])
        host = None
        for fk, fe in final.items():
            inter = len(ids & set(fe["items"]))
            if inter and inter / max(1, min(len(ids), len(fe["items"]))) >= 0.5:
                host = fe
                break
            if k.startswith("p:") and fk.startswith("p:"):
                a, b = set(k[2:].split()), set(fk[2:].split())
                if len(a & b) / len(a | b) >= 0.6:
                    host = fe
                    break
        if host:
            host["items"].update(e["items"])
            host["srcs"] |= e["srcs"]
            host["labels"] |= e["labels"]
            host["official"] |= e["official"]
        else:
            final[k] = e
    return final


def run(mod, items, videos):
    global U
    U = mod
    contestants = U.load("contestants.json", {"contestants": []})["contestants"] + U.load("contestants_auto.json", {"contestants": []})["contestants"]
    by_id = {i["id"]: i for i in items}
    found = detect(items, videos, [c.get("name") for c in contestants])

    prev = {e["key"]: e for e in U.load("events.json", {"events": []}).get("events", [])}
    arts = enrich_articles(items)

    # vistas de YouTube por id de video
    yt = {}
    for v in videos.get("official", []):
        yt[v["vid"]] = {"vid": v["vid"], "title": v["title"], "channel": v.get("channel"), "views": v.get("views_n"),
                        "likes": v.get("likes_n"), "published": v.get("published"), "official": True}
    for v in videos.get("search", []):
        n = re.sub(r"[^\d]", "", (v.get("views") or "").split(" ")[0])
        cur = yt.get(v["vid"])
        if cur:
            if cur.get("views") is None and n:
                cur["views"] = int(n)
        else:
            yt[v["vid"]] = {"vid": v["vid"], "title": v["title"], "channel": v.get("channel"), "views": int(n) if n else None,
                            "ago": v.get("ago"), "official": False}

    events = []
    for k, e in found.items():
        p = prev.get(k, {})
        ids = list(dict.fromkeys(list(e["items"]) + [x for x in p.get("item_ids", []) if x in by_id]))
        its = [by_id[x] for x in ids if x in by_id]
        if not its:
            continue
        dates = sorted(pub(i) for i in its)
        seed = next((s for s in SEED if "seed:" + s["id"] == k), None)
        vids = []
        for i in its:
            if i.get("type") == "video":
                m = re.search(r"v=([\w-]{11})", i["link"])
                if m and m.group(1) in yt:
                    vids.append(yt[m.group(1)])
        # videos de la búsqueda de YouTube que hablan del mismo evento
        pats = (seed["keywords"][:1] if seed else [re.escape(k[2:])] if k.startswith("p:") else [])
        for v in yt.values():
            if pats and any(re.search(px, U.norm(v["title"] or "")) for px in pats) and v["vid"] not in [x["vid"] for x in vids]:
                vids.append(v)
        imgs, social = [], []
        for v in vids:
            imgs.append({"url": f"https://i.ytimg.com/vi/{v['vid']}/maxresdefault.jpg", "alt": f"https://i.ytimg.com/vi/{v['vid']}/hqdefault.jpg",
                         "page": "https://www.youtube.com/watch?v=" + v["vid"], "via": "YouTube (miniatura)", "credit": v.get("channel")})
        for i in its:
            if i.get("thumb") and i.get("type") == "video":
                vid = re.search(r"/vi/([\w-]{11})/", i["thumb"])
                if vid:
                    imgs.append({"url": f"https://i.ytimg.com/vi/{vid.group(1)}/maxresdefault.jpg", "alt": f"https://i.ytimg.com/vi/{vid.group(1)}/hqdefault.jpg",
                                 "page": i["link"], "via": "YouTube (miniatura)", "credit": i.get("source")})
            a = arts.get(i.get("link"), {})
            for u in a.get("images", []):
                imgs.append({"url": u, "page": i["link"], "via": i.get("source"), "credit": i.get("source")})
            if i.get("thumb") and i.get("type") == "news":
                imgs.append({"url": i["thumb"], "page": i["link"], "via": "Bing (miniatura)", "credit": i.get("source")})
            social += a.get("social", [])
        nm = e["name"]
        if k.startswith("t:"):
            b = datetime.fromisoformat(k.rsplit(":", 1)[1])
            nm = f"{e['name']} · {b.day}–{(b + timedelta(days=2)).day} {['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][b.month-1]}"
        events.append({"key": k, "id": seed["id"] if seed else slug(k)[:50] + "-" + hashlib.sha1(k.encode()).hexdigest()[:5],
                       "name": nm if not seed else seed["name"], "contest": e["contest"] if not seed else seed["contest"],
                       "kind": ("oficial" if e["official"] else e["kind"]) if not seed else seed["kind"],
                       "labels": sorted(e["labels"]), "desc": seed.get("desc") if seed else None, "refs": seed.get("refs", []) if seed else [],
                       "first_seen": p.get("first_seen") or U.NOW.isoformat(), "start": (seed or {}).get("date") or dates[0].isoformat(),
                       "last_activity": dates[-1].isoformat(), "item_ids": ids[:120], "sources": sorted({i.get("source", "") for i in its})[:40],
                       "n_items": len(its), "n_sources": len({i.get("source", "") for i in its}),
                       "videos": sorted(vids, key=lambda v: -(v.get("views") or 0))[:20],
                       "views_total": sum(v.get("views") or 0 for v in vids),
                       "images": imgs, "social_urls": sorted(set(social))[:30],
                       "image_query": (seed or {}).get("image_query") or f"{e['name']} {U.norm(e['contest']) == 'mu' and 'Miss Universe 2026' or ''}",
                       "extra_images": p.get("extra_images", []), "extra_at": p.get("extra_at")})

    # agenda oficial como eventos (aunque aún no tengan notas)
    for pg in U.load("pageants.json", {"pageants": []})["pageants"]:
        for a in pg.get("events", []):
            k = "agenda:" + pg["id"] + ":" + slug(a["name"])
            if any(x["key"] == k for x in events):
                continue
            rx = {"Trajes": r"traje(s)? tipico|national costume", "Preliminar": r"preliminar|preliminary", "FINAL": r"\bfinal\b|coronac|crowned|corona"}
            pat = next((v for kk, v in rx.items() if kk.lower() in a["name"].lower()), None)
            its = [i for i in items if pat and pg["id"] in (i.get("contests") or []) and re.search(pat, U.norm(i.get("title", "")))
                   and pub(i) >= datetime.fromisoformat(a["start"]) - timedelta(days=1)] if pat else []
            events.append({"key": k, "id": slug(k), "name": f"{pg['name'].replace(' 2026', '')} · {a['name']}", "contest": pg["id"], "kind": "agenda oficial",
                           "labels": [], "desc": None, "refs": [], "first_seen": U.NOW.isoformat(), "start": a["start"], "last_activity": a["start"],
                           "item_ids": [i["id"] for i in its][:120], "sources": sorted({i.get("source", "") for i in its}), "n_items": len(its),
                           "n_sources": len({i.get("source", "") for i in its}), "videos": [], "views_total": 0, "images": [], "social_urls": [],
                           "image_query": f"{pg['name']} {a['name']}", "extra_images": prev.get(k, {}).get("extra_images", []),
                           "extra_at": prev.get(k, {}).get("extra_at"), "upcoming": datetime.fromisoformat(a["start"]) > U.NOW})

    # imágenes extra (Bing Imágenes + Commons) para los eventos más activos; se refresca cada 3 h
    def act(e):
        return datetime.fromisoformat(e["last_activity"].replace("Z", "+00:00"))
    ranked = sorted([e for e in events if not e.get("upcoming")], key=lambda e: (e["key"].startswith("seed:"), act(e), e["n_items"]), reverse=True)
    done = 0
    for e in ranked:
        if done >= 8:
            break
        if e.get("extra_at") and (U.NOW - datetime.fromisoformat(e["extra_at"])).total_seconds() < 3 * 3600 and e.get("extra_images"):
            continue
        ex = []
        try:
            ex += bing_images(e["image_query"])
        except Exception as err:
            U.note("Bing Imágenes · " + e["name"][:40], False, err=err)
        try:
            ex += commons(e["image_query"], 6)
        except Exception:
            pass
        e["extra_images"], e["extra_at"] = ex, U.NOW.isoformat()
        done += 1
        time.sleep(0.6)
    U.note("Imágenes por evento (Bing Imágenes / Commons)", True, done)

    # estadísticas sociales: posts incrustados en artículos + data/watch.json
    watch = U.load("watch.json", {"posts": []}).get("posts", [])
    urls = sorted({u for e in events for u in e["social_urls"]} | {w["url"] for w in watch if w.get("url")})
    soc = social_stats(urls)
    for w in watch:
        for e in events:
            if w.get("event") in (e["id"], e["key"]) and w["url"] not in e["social_urls"]:
                e["social_urls"].append(w["url"])
    for e in events:
        posts = [soc.get(u, {"url": u}) for u in e["social_urls"]]
        e["social"] = posts
        e["social_totals"] = {k: sum(p.get(k) or 0 for p in posts) for k in ("views", "likes", "comments", "shares")}
        seen, out = set(), []
        for im in e["images"] + e["extra_images"]:
            key = re.sub(r"[?#].*$", "", im["url"])
            if key in seen:
                continue
            seen.add(key)
            out.append(im)
        e["images"] = out[:40]
        e["score"] = e["n_items"] + 2 * e["n_sources"] + (e["views_total"] // 20000) + 3 * (e["kind"] != "detectado")

    # poda: 45 días
    cutoff = U.NOW - timedelta(days=45)
    events = [e for e in events if act(e) >= cutoff or e.get("upcoming")]
    events.sort(key=lambda e: (act(e), e["score"]), reverse=True)
    U.save("events.json", {"updated": U.NOW.isoformat(), "count": len(events), "events": events})
    U.note("Eventos detectados", True, len(events))
