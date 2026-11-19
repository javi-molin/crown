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
import json, re, time, html, urllib.parse
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
BAD_HANDLES = {"p", "reel", "reels", "explore", "accounts", "stories", "tv", "about", "legal", "direct", "missuniverse",
               "missinternationalofficial", "instagram", "developer", "web", "tags", "locations", "popular"}


def ig_graph(user):
    """Instagram Graph API oficial (Business Discovery). Requiere los secretos IG_TOKEN e IG_USER_ID
    de una cuenta profesional de Instagram conectada a una app de Meta. Lee cuentas públicas profesionales."""
    import os
    tok, me = os.environ.get("IG_TOKEN"), os.environ.get("IG_USER_ID")
    if not (tok and me):
        raise RuntimeError("sin credenciales")
    fields = ("business_discovery.username(%s){name,followers_count,profile_picture_url,media.limit(25)"
              "{caption,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count,media_type,children{media_url}}}") % user
    d = json.loads(U.get(f"https://graph.facebook.com/v21.0/{me}?fields={urllib.parse.quote(fields)}&access_token={tok}"))["business_discovery"]
    posts = []
    for m in d.get("media", {}).get("data", []):
        imgs = [c.get("media_url") for c in m.get("children", {}).get("data", []) if c.get("media_url")] or [m.get("media_url") or m.get("thumbnail_url")]
        code = re.search(r"/(?:p|reel|tv)/([\w-]+)", m["permalink"]).group(1)
        posts.append({"code": code, "url": m["permalink"], "owner": user, "images": [i for i in imgs if i][:10],
                      "thumb": m.get("thumbnail_url") or m.get("media_url"), "caption": (m.get("caption") or "")[:1200],
                      "likes": m.get("like_count"), "comments": m.get("comments_count"), "is_video": m.get("media_type") == "VIDEO",
                      "taken": m["timestamp"].replace("+0000", "+00:00")})
    return {"handle": user, "name": d.get("name"), "followers": d.get("followers_count"), "pic": d.get("profile_picture_url"), "posts": posts}


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
    """Fotos de prensa y miniaturas de YouTube atribuidas a cada candidata (la nota/video la nombra)."""
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
        if it.get("type") == "video":
            m = re.search(r"v=([\w-]{11})", it.get("link", ""))
            if m:
                imgs.append({"url": f"https://i.ytimg.com/vi/{m.group(1)}/maxresdefault.jpg", "thumb": f"https://i.ytimg.com/vi/{m.group(1)}/hqdefault.jpg",
                             "via": "YouTube", "credit": it.get("source", "").replace("YouTube · ", "")})
        a = arts.get(it.get("link"), {})
        for u in a.get("images", [])[:4]:
            imgs.append({"url": u, "via": "Prensa", "credit": it.get("source")})
        if it.get("thumb") and it.get("type") == "news":
            imgs.append({"url": it["thumb"], "via": "Prensa (miniatura)", "credit": it.get("source")})
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


def run(mod, contestants, deadline_s=200):
    global U
    U = mod
    t0 = time.time()
    G = U.load("gallery.json", {"cells": {}, "handles": {}, "ig_posts": {}, "accounts": {}})
    for k in ("cells", "handles", "ig_posts", "accounts"):
        G.setdefault(k, {})
    now = U.NOW
    cs = [c for c in contestants if c.get("contest") in ("mu", "mi") and c.get("name")]
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
        if h.get("tried") and h.get("name") == c["name"]:
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
    cand_acc = [(v["handle"], k.split("|")[0], "candidata") for k, v in G["handles"].items() if v.get("handle") and v.get("conf") in ("alta", "verificada")]
    cand_acc.sort(key=lambda a: G["accounts"].get(a[0], {}).get("fetched", ""))
    import os
    if os.environ.get("IG_TOKEN") and os.environ.get("IG_USER_ID"):
        ok = 0
        for handle, cid, kind in accounts + cand_acc[:40]:
            if time.time() - t0 > deadline_s * 0.5:
                break
            try:
                p = ig_graph(handle)
                G["accounts"][handle] = {"name": p["name"], "followers": p["followers"], "pic": p["pic"], "contest": cid, "kind": kind, "fetched": now.isoformat()}
                for post in p["posts"]:
                    post["contest"], post["kind"] = cid, kind
                    G["ig_posts"][post["code"]] = {**G["ig_posts"].get(post["code"], {}), **post, "seen": now.isoformat()}
                ok += 1
            except Exception as e:
                G["accounts"].setdefault(handle, {})["error"] = str(e)[:100]
            time.sleep(0.5)
        U.note("Instagram · Graph API oficial (cuentas leídas)", True, ok)
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
    matchers = []
    for c in cs:
        nm = U.norm(c["name"])
        pats = [re.escape(nm)] + ([re.escape(nm.split()[0]) + r"\W+(?:\w+\W+)?" + re.escape(nm.split()[-1])] if len(nm.split()) > 1 else [])
        for t in {U.norm(c["country"]), U.norm(c.get("country_es") or "")}:
            if t:
                pats.append(r"miss (?:universe |universo |international |internacional )?" + re.escape(t) + r"\b")
        matchers.append((re.compile("|".join(pats)), c))
    cutoff = now - timedelta(days=40)
    for code, p in list(G["ig_posts"].items()):
        if datetime.fromisoformat(p.get("taken") or p.get("seen")) < cutoff:
            G["ig_posts"].pop(code)
            continue
        cap = U.norm(p.get("caption", ""))
        who = []
        if p.get("owner") in by_handle:
            who.append(by_handle[p["owner"]])
        if p.get("hint") and not who:
            who.append(p["hint"])
        for rx, c in matchers:
            if c["contest"] == p.get("contest") and rx.search(cap):
                who.append(c["contest"] + "|" + c["country"])
        p["who"] = sorted(set(who))[:3]
        p["cats"] = classify(p.get("caption", ""))

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
    n = press_images(G, cs)
    U.note("Galería · fotos de prensa y video atribuidas a candidatas", True, n)
    G["cats"] = [{"id": a, "label": b} for a, b, _, _ in CATS] + [{"id": "otras", "label": "Más fotos"}]
    G["updated"] = now.isoformat()
    U.save("gallery.json", G)
