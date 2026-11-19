#!/usr/bin/env python3
"""
CROWN — robot de actualización.
Corre en GitHub Actions (servidores de GitHub con internet abierto) cada ~10 min.
Solo usa la librería estándar de Python. Cada fuente falla de forma aislada:
si una cae, las demás siguen y el estado queda registrado en data/status.json.

Genera:
  data/feed.json      noticias + videos etiquetados (concurso, candidata, polémica, looks, resultados)
  data/videos.json    últimos videos de canales oficiales y búsqueda de YouTube
  data/channels.json  IDs de canales de YouTube resueltos (para embeds en vivo)
  data/wiki.json      foto de la sección de resultados de Wikipedia (se actualiza en vivo la noche de la final)
  data/contestants_auto.json  lista de candidatas leída desde Wikipedia
  data/status.json    salud de cada fuente
"""
import json, os, re, sys, time, hashlib, html, unicodedata
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
NOW = datetime.now(timezone.utc)
STATUS = {"run_at": NOW.isoformat(), "sources": []}
MAX_ITEMS = 900
MAX_AGE_DAYS = 30


def load(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def get(url, timeout=25, accept=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
        **({"Accept": accept} if accept else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def note(source, ok, n=0, err=None):
    STATUS["sources"].append({"source": source, "ok": ok, "items": n, "error": (str(err)[:200] if err else None)})


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def uid(link):
    return hashlib.sha1(link.encode()).hexdigest()[:14]


# ---------------------------------------------------------------- configuración
PAGEANTS = load("pageants.json", {"pageants": []})["pageants"]
COUNTRIES = load("countries.json", {})
SEED = load("contestants.json", {"contestants": []})["contestants"]

CONTEST_WORDS = {
    "mu": ["miss universe", "miss universo", "missuniverse", "mu 2026", "75th miss universe", "fatima bosch", "fátima bosch"],
    "mi": ["miss international", "miss internacional", "catalina duque"],
    "me": ["miss earth", "miss tierra", "puskinova", "puškinová"],
    "mw": ["miss world", "miss mundo"],
    "mgi": ["miss grand"],
    "ms": ["miss supranational"],
}

TAGS = {
    "polemica": ["polemic", "controvers", "escandal", "scandal", "renunci", "withdr", "retir", "destitu", "denunci", "acus",
                 "critic", "backlash", "fake", "falso", "sabotaj", "fraude", "rigged", "arreglad", "demand", "lawsuit",
                 "investig", "drama", "pelea", "rivalidad", "bullying", "boicot", "boycott", "abuch", "booed", "rumor",
                 "desmient", "responde", "explota", "furia", "indign", "viral"],
    "looks": ["look", "vestido", "gown", "traje", "costume", "outfit", "atuendo", "desfile", "pasarela", "swimsuit",
              "bikini", "bano", "natcos", "national costume", "tipico", "disenador", "designer", "moda", "fashion",
              "maquillaje", "makeup", "peinado", "glam", "red carpet", "alfombra", "style", "estilo"],
    "resultados": ["top ", "gana", "gano", "winner", "wins", "crowned", "corona", "placement", "clasific", "semifinal",
                   "finalist", "prelim", "puntaj", "score", "ranking", "hot pick", "favorit", "predic", "pronostic",
                   "runner-up", "finalista", "virreina", "resultado", "result"],
}

GN = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
LOC_ES = dict(hl="es-419", gl="CL", ceid="CL:es-419")
LOC_EN = dict(hl="en-US", gl="US", ceid="US:en")
NEWS_QUERIES = [
    ("mu", "\"Miss Universo 2026\"", LOC_ES), ("mu", "\"Miss Universe 2026\"", LOC_EN),
    ("mu", "Miss Universo polémica", LOC_ES), ("mu", "Miss Universe controversy", LOC_EN),
    ("mu", "Miss Universo looks traje típico", LOC_ES), ("mu", "Miss Universe national costume gown", LOC_EN),
    ("mu", "Miss Universe Puerto Rico preliminary", LOC_EN), ("mu", "\"Dominga López\" Miss Universo", LOC_ES),
    ("mu", "Miss Universo favoritas", LOC_ES), ("mu", "Miss Universe hot picks", LOC_EN),
    ("mi", "\"Miss International 2026\"", LOC_EN), ("mi", "\"Miss Internacional 2026\"", LOC_ES),
    ("me", "\"Miss Earth 2026\"", LOC_EN), ("me", "Miss Earth Philippines December", LOC_EN),
    ("mw", "\"Miss World\" Joheirry Mola", LOC_EN), ("mgi", "\"Miss Grand International\" 2026", LOC_EN),
    ("ms", "\"Miss Supranational\" 2027", LOC_EN),
    (None, "certamen de belleza", LOC_ES), (None, "beauty pageant", LOC_EN),
]

YT_CHANNELS = [  # (concurso, handle o "search:consulta|palabra esperada en el nombre", etiqueta)
    ("mu", "search:Miss Universe official|miss universe", "Miss Universe (oficial)"),
    ("mi", "search:Miss International Beauty Pageant|miss international", "Miss International (oficial)"),
    ("me", "search:Miss Earth official|miss earth", "Miss Earth (oficial)"),
    ("mw", "@MissWorld", "Miss World (oficial)"),
    ("mgi", "search:GrandTV Miss Grand International|grand", "GrandTV / Miss Grand"),
    ("ms", "search:Miss Supranational|supranational", "Miss Supranational (oficial)"),
    ("mu", "search:Telemundo Miss Universo|telemundo", "Telemundo"),
]
YT_SEARCHES = [("mu", "Miss Universe 2026"), ("mu", "Miss Universo 2026"), ("mi", "Miss International 2026"),
               ("me", "Miss Earth 2026"), ("mu", "Miss Universe 2026 national costume"), ("mu", "Miss Universe 2026 preliminary")]

WIKI_PAGES = {p["id"]: p["wiki"] for p in PAGEANTS if p.get("wiki")}


# ---------------------------------------------------------------- etiquetado
def build_matchers(contestants):
    ms = []
    for c in contestants:
        name = c.get("name") or ""
        parts = [p for p in re.split(r"\s+", norm(name)) if len(p) > 2]
        pats = []
        if len(parts) >= 2:
            pats.append(re.escape(norm(name)))
            pats.append(re.escape(parts[0]) + r"\W+(?:\w+\W+)?" + re.escape(parts[-1]))
        country_terms = {norm(c["country"]), norm(c.get("country_es", ""))}
        if c["contest"] == "mu":
            for t in country_terms:
                if t:
                    pats += [r"miss univers[eo] " + re.escape(t), r"miss " + re.escape(t) + r"\b"]
        elif c["contest"] == "mi":
            for t in country_terms:
                if t:
                    pats += [r"miss international " + re.escape(t)]
        if pats:
            ms.append((re.compile("|".join(pats)), c))
    return ms


def tag_item(it, matchers):
    text = norm(it.get("title", "") + " " + it.get("summary", ""))
    contests = set(it.get("contests", []))
    for cid, words in CONTEST_WORDS.items():
        if any(w in text for w in words):
            contests.add(cid)
    it["contests"] = sorted(contests)
    tags = set(it.get("tags", []))
    for t, words in TAGS.items():
        if any(w in text for w in words):
            tags.add(t)
    it["tags"] = sorted(tags)
    found = []
    for rx, c in matchers:
        if rx.search(text) and (not contests or c["contest"] in contests):
            found.append({"contest": c["contest"], "country": c["country"], "name": c["name"]})
    it["who"] = found[:6]
    return it


# ---------------------------------------------------------------- fuentes
def google_news():
    items = []
    for cid, q, loc in NEWS_QUERIES:
        url = GN.format(q=urllib.parse.quote(q), **loc)
        try:
            root = ET.fromstring(get(url))
            n = 0
            for i in root.iter("item"):
                link = (i.findtext("link") or "").strip()
                title = html.unescape(i.findtext("title") or "")
                src_el = i.find("source")
                src = src_el.text if src_el is not None else ""
                if src and title.endswith(" - " + src):
                    title = title[: -len(src) - 3]
                try:
                    pub = parsedate_to_datetime(i.findtext("pubDate"))
                except Exception:
                    pub = NOW
                items.append({"id": uid(link), "type": "news", "title": title.strip(), "link": link,
                              "source": src, "published": iso(pub), "lang": loc["hl"][:2],
                              "contests": [cid] if cid else [], "tags": [], "query": q})
                n += 1
            note("Google News · " + q, True, n)
        except Exception as e:
            note("Google News · " + q, False, err=e)
        time.sleep(1.5)
    return items


def initial_data(page):
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", page, re.S)
    if not m:
        raise ValueError("sin ytInitialData")
    return json.loads(m.group(1))


def find_key(o, key, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                out.append(v)
            else:
                find_key(v, key, out)
    elif isinstance(o, list):
        for x in o:
            find_key(x, key, out)
    return out


def resolve_channel(handle, cache):
    if handle in cache:
        return cache[handle]
    if handle.startswith("search:"):
        q, expect = handle[7:].split("|")
        data = initial_data(get("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) + "&sp=EgIQAg%253D%253D"))
        for ch in find_key(data, "channelRenderer", []):
            title = ch.get("title", {}).get("simpleText", "")
            if expect in norm(title):
                subs = ch.get("videoCountText", {}).get("simpleText", "") or ch.get("subscriberCountText", {}).get("simpleText", "")
                cache[handle] = {"id": ch["channelId"], "title": title, "subs": subs}
                return cache[handle]
        raise ValueError("canal no encontrado en búsqueda")
    page = get("https://www.youtube.com/" + handle.lstrip("/"))
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', page) \
        or re.search(r'"externalId":"(UC[\w-]{22})"', page) or re.search(r'"channelId":"(UC[\w-]{22})"', page)
    if not m:
        raise ValueError("sin channelId")
    title = re.search(r'<meta property="og:title" content="([^"]+)"', page)
    cache[handle] = {"id": m.group(1), "title": html.unescape(title.group(1)) if title else handle}
    return cache[handle]


def yt_rss(channel_id):
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "media": "http://search.yahoo.com/mrss/"}
    root = ET.fromstring(get("https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id))
    out = []
    for e in root.findall("a:entry", ns):
        vid = e.findtext("yt:videoId", namespaces=ns)
        st = e.find(".//media:statistics", ns)
        rt = e.find(".//media:starRating", ns)
        out.append({"vid": vid, "title": e.findtext("a:title", namespaces=ns),
                    "published": e.findtext("a:published", namespaces=ns),
                    "views_n": int(st.get("views", 0)) if st is not None else None,
                    "likes_n": int(rt.get("count", 0)) if rt is not None else None,
                    "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"})
    return out


def yt_search(q):
    # resultados ordenados por fecha de subida (sp=CAI%3D)
    page = get("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) + "&sp=CAI%253D")
    data = initial_data(page)
    out = []

    def walk(o):
        if isinstance(o, dict):
            if "videoRenderer" in o:
                v = o["videoRenderer"]
                title = "".join(r.get("text", "") for r in v.get("title", {}).get("runs", []))
                ch = "".join(r.get("text", "") for r in v.get("ownerText", {}).get("runs", []))
                ago = v.get("publishedTimeText", {}).get("simpleText", "")
                views = v.get("viewCountText", {}).get("simpleText", "") or "".join(
                    r.get("text", "") for r in v.get("viewCountText", {}).get("runs", []))
                live = any("LIVE" in json.dumps(b) for b in v.get("badges", []))
                out.append({"vid": v.get("videoId"), "title": title, "channel": ch, "ago": ago, "views": views,
                            "live": live, "thumb": f"https://i.ytimg.com/vi/{v.get('videoId')}/hqdefault.jpg"})
            else:
                for x in o.values():
                    walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(data)
    return out[:20]


def youtube():
    cache = load("channels.json", {})
    resolved, videos, items = {}, {"official": [], "search": []}, []
    for cid, handle, label in YT_CHANNELS:
        key = cid if cid not in resolved else cid + "_" + str(len(resolved))
        try:
            ch = resolve_channel(handle, cache)
            vids = yt_rss(ch["id"])
            if "telemundo" in norm(label):  # el canal mezcla realities: solo lo de concursos
                vids = [v for v in vids if re.search(r"miss|reina|univers|corona|certamen", norm(v["title"]))]
            resolved[key] = {"handle": handle, "label": label, "contest": cid, **ch}
            for v in vids:
                v.update({"contest": cid, "channel": ch["title"]})
                videos["official"].append(v)
                link = "https://www.youtube.com/watch?v=" + v["vid"]
                items.append({"id": uid(link), "type": "video", "title": v["title"], "link": link,
                              "source": "YouTube · " + ch["title"], "published": v["published"],
                              "contests": [cid], "tags": ["video"], "thumb": v["thumb"], "official": True})
            note("YouTube oficial " + handle, True, len(vids))
        except Exception as e:
            note("YouTube oficial " + handle, False, err=e)
    for cid, q in YT_SEARCHES:
        try:
            res = yt_search(q)
            for v in res:
                v.update({"contest": cid, "query": q})
            videos["search"] += res
            note("YouTube búsqueda · " + q, True, len(res))
        except Exception as e:
            note("YouTube búsqueda · " + q, False, err=e)
        time.sleep(0.8)
    seen = set()
    videos["search"] = [v for v in videos["search"] if not (v["vid"] in seen or seen.add(v["vid"]))]
    save("channels.json", cache)
    return resolved, videos, items


def reddit():
    items = []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for sub in ["pageants", "MissUniverse"]:
        try:
            root = ET.fromstring(get(f"https://www.reddit.com/r/{sub}/new/.rss?limit=40"))
            n = 0
            for e in root.findall("a:entry", ns):
                link = e.find("a:link", ns).get("href")
                items.append({"id": uid(link), "type": "social", "title": e.findtext("a:title", namespaces=ns), "link": link,
                              "source": f"Reddit r/{sub}", "published": e.findtext("a:updated", namespaces=ns),
                              "contests": [], "tags": ["comunidad"]})
                n += 1
            note("Reddit r/" + sub, True, n)
        except Exception as e:
            note("Reddit r/" + sub, False, err=e)
    for q in ["miss universe", "miss universo"]:
        try:
            d = json.loads(get("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?sort=latest&limit=40&q=" + urllib.parse.quote(q)))
            n = 0
            for p in d.get("posts", []):
                rk = p["uri"].split("/")[-1]
                link = f"https://bsky.app/profile/{p['author']['handle']}/post/{rk}"
                txt = (p.get("record", {}).get("text") or "").replace("\n", " ")
                if len(txt) < 25:
                    continue
                items.append({"id": uid(link), "type": "social", "title": txt[:220], "link": link,
                              "source": "Bluesky · @" + p["author"]["handle"], "published": p.get("indexedAt"),
                              "contests": [], "tags": ["comunidad"], "score": p.get("likeCount", 0), "comments": p.get("replyCount", 0)})
                n += 1
            note("Bluesky · " + q, True, n)
        except Exception as e:
            note("Bluesky · " + q, False, err=e)
    return items


def wiki_raw(page):
    url = ("https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content|timestamp&rvslots=main"
           "&format=json&formatversion=2&titles=" + urllib.parse.quote(page))
    d = json.loads(get(url))
    rev = d["query"]["pages"][0]["revisions"][0]
    return rev["slots"]["main"]["content"], rev["timestamp"]


def strip_wiki(s):
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\{(?:flagicon|flagu|flag|flagcountry)\|([^|}]+)[^}]*\}\}", r"\1", s, flags=re.I)
    s = re.sub(r"\{\{sortname\|([^|}]+)\|([^|}]+)[^}]*\}\}", r"\1 \2", s, flags=re.I)
    s = re.sub(r"\{\{sort\|[^|}]*\|([^|}]+)[^}]*\}\}", r"\1", s, flags=re.I)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"^[A-Z]{3}\s+(?=[A-Z][a-z])", "", html.unescape(s).strip())
    return s.strip()


def section(text, names):
    for nm in names:
        m = re.search(r"^==+\s*" + nm + r"\s*==+\s*$", text, re.M | re.I)
        if m:
            rest = text[m.end():]
            lvl = len(re.match(r"^(=+)", text[m.start():]).group(1))
            end = re.search(r"^={2," + str(lvl) + r"}[^=].*?={2," + str(lvl) + r"}\s*$", rest, re.M)
            return rest[: end.start()] if end else rest
    return ""


def parse_table_rows(block):
    rows = []
    for chunk in re.split(r"\n\|-.*", block):
        cells = []
        for line in chunk.splitlines():
            line = line.strip()
            if not line or line.startswith(("{|", "|}", "!", "|+")):
                continue
            if line.startswith("|"):
                for cell in re.split(r"\|\|", line[1:]):
                    if "|" in cell and not cell.strip().startswith("[[") and "=" in cell.split("|")[0]:
                        cell = cell.split("|", 1)[1]  # quita atributos tipo style=...
                    cells.append(strip_wiki(cell))
        cells = [c for c in cells if c != ""]
        if len(cells) >= 2:
            rows.append(cells)
    return rows


def wikipedia(seed_by_contest):
    out, auto = load("wiki.json", {}), []
    for cid, page in WIKI_PAGES.items():
        try:
            text, ts = wiki_raw(page)
            res = section(text, ["Results", "Placements", "Final results"])
            res_lines = [" — ".join(r) for r in parse_table_rows(res)]
            res_lines += [strip_wiki(l.lstrip("* ")) for l in res.splitlines() if l.strip().startswith("*")]
            res_lines = [l for l in res_lines if len(l) > 2][:120]
            prev = out.get(cid, {})
            changed = prev.get("results_hash") != hashlib.sha1("\n".join(res_lines).encode()).hexdigest()
            out[cid] = {"page": page, "revision": ts, "results": res_lines,
                        "results_hash": hashlib.sha1("\n".join(res_lines).encode()).hexdigest(),
                        "results_changed_at": NOW.isoformat() if (changed and res_lines and prev.get("results_hash")) else prev.get("results_changed_at")}
            n = 0
            if cid in ("mu", "mi", "me"):
                cont = section(text, ["Contestants", "Delegates", "Confirmed contestants"])
                known = {norm(c["country"]): c for c in seed_by_contest.get(cid, [])}
                known.update({norm(c["country_es"]): c for c in seed_by_contest.get(cid, [])})
                known.update({"iso:" + c["iso"]: c for c in seed_by_contest.get(cid, []) if c.get("iso") and c["iso"] != "US"})
                for r in parse_table_rows(cont):
                    country, name = r[0], r[1]
                    age = next((int(x) for x in r[2:4] if re.fullmatch(r"\d{2}", x)), None)
                    town = r[3] if len(r) > 3 else (r[2] if len(r) > 2 and not r[2].isdigit() else None)
                    if len(country) > 40 or len(name) > 60 or not re.search(r"[A-Za-zÀ-ÿ]", name):
                        continue
                    info = COUNTRIES.get(country) or COUNTRIES.get(country.replace("&", "and")) or [country, "", ""]
                    base = known.get(norm(country)) or (known.get("iso:" + info[1]) if info[1] and info[1] != "US" else None) or {}
                    auto.append({**{k: v for k, v in base.items() if k not in ("name", "age", "hometown")},
                                 "contest": cid, "country": base.get("country", country),
                                 "country_es": base.get("country_es", info[0]), "iso": base.get("iso", info[1]),
                                 "region": base.get("region", info[2]), "name": name, "age": age, "hometown": town,
                                 "from_wiki": True})
                    n += 1
            note("Wikipedia · " + page, True, n + len(res_lines))
        except Exception as e:
            note("Wikipedia · " + page, False, err=e)
    save("wiki.json", out)
    # solo se publica la lista automática si se ve sana (evita romper el panel si cambia el formato)
    by = {}
    for a in auto:
        by.setdefault(a["contest"], []).append(a)
    healthy = {cid: lst for cid, lst in by.items() if len(lst) >= 0.6 * max(1, len(seed_by_contest.get(cid, [])))}
    if healthy:
        save("contestants_auto.json", {"updated": NOW.isoformat(), "contestants": [c for l in healthy.values() for c in l]})
    return out


# ---------------------------------------------------------------- principal
def main():
    seed_by = {}
    for c in SEED:
        seed_by.setdefault(c["contest"], []).append(c)
    auto = load("contestants_auto.json", {"contestants": []})["contestants"]
    all_c = SEED + [a for a in auto if not any(s["contest"] == a["contest"] and s["country"] == a["country"] for s in SEED)]
    matchers = build_matchers(all_c)

    old = {i["id"]: i for i in load("feed.json", {"items": []}).get("items", [])}
    fresh = google_news()
    yt_resolved, videos, yt_items = youtube()
    fresh += yt_items
    try:
        import events
        fresh += events.bing_news(sys.modules[__name__])
    except Exception as e:
        note("Bing Noticias", False, err=repr(e))
    wiki = wikipedia(seed_by)

    for cid, w in wiki.items():
        if w.get("results_changed_at") == NOW.isoformat():
            link = f"https://en.wikipedia.org/wiki/{w['page']}#Results"
            fresh.append({"id": uid(link + NOW.strftime('%Y%m%d%H%M')), "type": "alert", "contests": [cid],
                          "title": f"Wikipedia actualizó los RESULTADOS de {w['page'].replace('_', ' ')}",
                          "link": link, "source": "Wikipedia (edición en vivo)", "published": NOW.isoformat(),
                          "tags": ["resultados", "alerta"]})

    new_count = 0
    for it in fresh:
        it = tag_item(it, matchers)
        if it["id"] in old:
            prev = old[it["id"]]
            prev["contests"] = sorted(set(prev.get("contests", [])) | set(it["contests"]))
            prev["tags"] = sorted(set(prev.get("tags", [])) | set(it["tags"]))
            prev["who"] = it["who"] or prev.get("who", [])
            for k in ("score", "comments"):
                if k in it:
                    prev[k] = it[k]
        else:
            it["first_seen"] = NOW.isoformat()
            old[it["id"]] = it
            new_count += 1

    cutoff = NOW - timedelta(days=MAX_AGE_DAYS)

    def ts(i):
        try:
            return datetime.fromisoformat(i.get("published") or i.get("first_seen"))
        except Exception:
            return NOW
    items = [i for i in old.values() if ts(i) >= cutoff]
    items.sort(key=ts, reverse=True)
    items = items[:MAX_ITEMS]

    save("feed.json", {"updated": NOW.isoformat(), "new_this_run": new_count, "count": len(items), "items": items})
    save("videos.json", {"updated": NOW.isoformat(), "channels": yt_resolved, **videos})
    try:
        import events
        events.run(sys.modules[__name__], items, videos)
    except Exception as e:
        note("Eventos (detector)", False, err=repr(e))
    STATUS["new_items"] = new_count
    STATUS["total_items"] = len(items)
    save("status.json", STATUS)
    ok = sum(1 for s in STATUS["sources"] if s["ok"])
    print(f"fuentes ok {ok}/{len(STATUS['sources'])} · nuevos {new_count} · total {len(items)}")


if __name__ == "__main__":
    main()
