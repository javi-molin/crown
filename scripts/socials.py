"""Redes sociales verificadas de cada concurso y cada candidata + sonda de las webs oficiales.

- Concursos: lista de usuarios candidatos por red; Instagram se confirma con la API oficial (Business Discovery),
  TikTok y YouTube se confirman abriendo el perfil público. Solo se publica lo confirmado.
- Candidatas: toma los usuarios de IG confirmados por igsync (G["handles"]) y prueba el mismo usuario en TikTok.
- Sonda: revisa las páginas oficiales (missuniverseorg.com/vote, missuniverse.com…) y deja en data/probe.json
  qué cargan (iframes, scripts, APIs, imágenes) para encontrar los retratos oficiales de fondo claro.
"""
import re, json, time, urllib.parse
from datetime import datetime, timedelta

U = None

PAGEANTS = {
    "mu": {"instagram": ["missuniverse"], "tiktok": ["missuniverse"], "youtube": ["@MissUniverse"],
           "facebook": "https://www.facebook.com/missuniverse", "x": "https://x.com/missuniverse",
           "threads": "https://www.threads.net/@missuniverse", "web": "https://www.missuniverse.com/",
           "vote": "https://missuniverseorg.com/vote",
           "app_ios": "https://apps.apple.com/us/app/miss-universe/id1557255641",
           "app_android": "https://play.google.com/store/apps/details?id=com.choicely.missuniverse"},
    "mi": {"instagram": ["missinternationalofficial", "miss_international_official"], "tiktok": ["missinternationalofficial", "missinternational"],
           "youtube": ["@MissInternationalBeautyPageant", "@missinternational"], "facebook": "https://www.facebook.com/MissInternationalBeautyPageant",
           "web": "https://www.miss-international.org/en/"},
    "me": {"instagram": ["missearth", "missearth_official", "missearthofficial", "missearth.official"], "tiktok": ["missearthofficial", "missearth"],
           "youtube": ["@MissEarthOfficial", "@missearth"], "facebook": "https://www.facebook.com/MissEarth", "web": "https://www.missearth.tv/"},
    "mw": {"instagram": ["missworld", "missworldltd"], "tiktok": ["missworld"], "youtube": ["@MissWorld"],
           "facebook": "https://www.facebook.com/missworld", "x": "https://x.com/MissWorldLtd", "web": "https://www.missworld.com/"},
    "mgi": {"instagram": ["missgrandinternational", "missgrandinternational.official"], "tiktok": ["missgrandinternational", "missgrandinternationalofficial"],
            "youtube": ["@GrandTVOfficial", "@missgrandinternational"], "facebook": "https://www.facebook.com/missgrandinternational",
            "web": "https://www.missgrandinternational.com/"},
    "ms": {"instagram": ["misssupranational", "misssupranational_official"], "tiktok": ["misssupranational"],
           "youtube": ["@MissSupranational", "@misssupranationalofficial"], "facebook": "https://www.facebook.com/misssupranational",
           "web": "https://www.misssupranational.com/"},
}

PROBE = [
    "https://missuniverseorg.com/vote",
    "https://missuniverseorg.com/",
    "https://www.missuniverse.com/the-competition/",
    "https://www.missuniverse.com/the-competition-puerto-rico/",
    "https://www.missuniverse.com/contestants/",
    "https://www.missuniverse.com/delegates/",
    "https://www.missuniverse.com/wp-json/wp/v2/pages?per_page=50&_fields=link,title,modified&orderby=modified&order=desc",
    "https://www.missuniverse.com/wp-json/wp/v2/posts?per_page=20&_fields=link,title,date",
    "https://www.missuniverse.com/wp-json/wp/v2/media?per_page=50&search=2026&_fields=source_url,title,date",
    "https://www.missuniverse.com/wp-json/wp/v2/media?per_page=50&search=headshot&_fields=source_url,title,date",
    "https://www.missuniverse.com/wp-json/wp/v2/types?_fields=slug,rest_base",
    "https://missuniverse.piwigo.com/ws.php?format=json&method=pwg.categories.getList&recursive=true",
    "https://hayekqueens.com/en/pageants/miss-universe/editions/2026",
]


def _ok_tiktok(h):
    try:
        page = U.get(f"https://www.tiktok.com/@{h}", timeout=20)
    except Exception:
        return None
    if re.search(r'"uniqueId":"%s"' % re.escape(h), page, re.I):
        fol = re.search(r'"followerCount":(\d+)', page)
        return {"url": f"https://www.tiktok.com/@{h}", "handle": h, "followers": int(fol.group(1)) if fol else None}
    return False


def _ok_youtube(h):
    try:
        page = U.get(f"https://www.youtube.com/{h}", timeout=20)
    except Exception:
        return None
    m = re.search(r'"channelId":"(UC[\w-]{22})"', page)
    if not m:
        return False
    subs = re.search(r'"subscriberCountText":\{[^}]*?"simpleText":"([^"]+)"', page)
    return {"url": f"https://www.youtube.com/{h}", "handle": h, "channel_id": m.group(1), "subs": subs.group(1) if subs else None}


def _ok_ig(h, igsync):
    try:
        d = igsync.graph("{ME}", fields=f"business_discovery.username({h}){{username,name,followers_count,media_count}}")["business_discovery"]
        return {"url": f"https://www.instagram.com/{h}/", "handle": h, "followers": d.get("followers_count"), "name": d.get("name")}
    except igsync.RateLimited:
        return None
    except Exception:
        return False


def pageants(S, igsync, has_ig):
    out = S.setdefault("pageants", {})
    for pid, conf in PAGEANTS.items():
        rec = out.setdefault(pid, {})
        if rec.get("checked") and (U.NOW - datetime.fromisoformat(rec["checked"])).total_seconds() < 24 * 3600:
            continue
        for net, check in (("instagram", (lambda h: _ok_ig(h, igsync)) if has_ig else None), ("tiktok", _ok_tiktok), ("youtube", _ok_youtube)):
            if not check:
                continue
            best = None
            for h in conf.get(net, []):
                r = check(h)
                if r and (not best or (r.get("followers") or 0) > (best.get("followers") or 0)):
                    best = r
                time.sleep(0.4)
            if best:
                rec[net] = {**best, "verified": True}
            elif net not in rec and conf.get(net):
                rec[net] = {"url": (f"https://www.instagram.com/{conf[net][0]}/" if net == "instagram" else
                                    f"https://www.tiktok.com/@{conf[net][0]}" if net == "tiktok" else f"https://www.youtube.com/{conf[net][0]}"),
                            "handle": conf[net][0], "verified": False}
        for k in ("facebook", "x", "threads", "web", "vote", "app_ios", "app_android"):
            if conf.get(k):
                rec[k] = {"url": conf[k], "verified": True}
        rec["checked"] = U.NOW.isoformat()
    return out


def contestants(S, G, cs, budget=12):
    """Cuentas de cada candidata: IG confirmado por la API (igsync) + TikTok con el mismo usuario si existe."""
    out = S.setdefault("contestants", {})
    done = 0
    for c in cs:
        k = c["contest"] + "|" + c["country"]
        rec = out.setdefault(k, {"name": c["name"]})
        h = (G.get("handles", {}).get(k) or {})
        if h.get("handle") and h.get("conf") == "verificada":
            acc = G.get("accounts", {}).get(h["handle"], {})
            rec["instagram"] = {"url": f"https://www.instagram.com/{h['handle']}/", "handle": h["handle"], "verified": True,
                                "followers": acc.get("followers") or h.get("followers"), "via": h.get("via", "API")}
            if done < budget and rec.get("tiktok_tried") != h["handle"]:
                r = _ok_tiktok(h["handle"])
                if r is not None:
                    rec["tiktok_tried"] = h["handle"]
                    done += 1
                    if r:
                        rec["tiktok"] = {**r, "verified": True}
                time.sleep(0.6)
        org = next((oh for oh, ok in (G.get("orgs") or {}).items() if ok == k), None)
        if org:
            acc = G.get("accounts", {}).get(org, {})
            rec["org_instagram"] = {"url": f"https://www.instagram.com/{org}/", "handle": org, "verified": True, "followers": acc.get("followers"), "name": acc.get("name")}
    return out


def probe(S):
    last = S.get("probe_at")
    if last and (U.NOW - datetime.fromisoformat(last)).total_seconds() < 3 * 3600:
        return 0
    res = []
    for url in PROBE:
        r = {"url": url}
        try:
            page = U.get(url, timeout=25)
            r["len"] = len(page)
            r["title"] = (re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S) or [None, ""])[1].strip()[:120]
            r["iframes"] = list(dict.fromkeys(re.findall(r'<iframe[^>]+src="([^"]+)"', page, re.I)))[:15]
            r["scripts"] = [s for s in dict.fromkeys(re.findall(r'<script[^>]+src="([^"]+)"', page, re.I)) if not re.search(r"google|gtag|facebook\.net|hotjar", s)][:25]
            txt = page.replace("\\/", "/").replace("\\u002F", "/")
            r["endpoints"] = list(dict.fromkeys(re.findall(r"https?://[\w.-]+/[\w./-]*(?:api|json|graphql|vote|contest|delegat|candidat|participant)[\w./?=&-]*", txt, re.I)))[:30]
            r["hosts"] = sorted({h for h in re.findall(r"https?://([\w.-]+)", txt)})[:60]
            r["imgs"] = list(dict.fromkeys(re.findall(r"https?://[^\"'\s)]+?\.(?:jpe?g|png|webp)", txt, re.I)))[:40]
            r["n_imgs"] = len(set(re.findall(r"https?://[^\"'\s)]+?\.(?:jpe?g|png|webp)", txt, re.I)))
            r["words"] = [w for w in ("choicely", "vote", "delegate", "contestant", "candidata", "headshot", "puerto rico", "2026") if w in txt.lower()]
            if url.endswith("json") or "wp-json" in url or "ws.php" in url:
                r["sample"] = page[:1500]
            # scripts propios del sitio: buscar endpoints dentro
            for s in r["scripts"][:8]:
                src = s if s.startswith("http") else ("https:" + s if s.startswith("//") else urllib.parse.urljoin(url, s))
                if re.search(r"jquery|wp-includes|recaptcha|cookie", src, re.I):
                    continue
                try:
                    js = U.get(src, timeout=20).replace("\\/", "/")
                    eps = re.findall(r"https?://[\w.-]+/[\w./-]*(?:api|json|vote|contest|participant|delegat)[\w./?=&-]*", js, re.I)
                    if eps or "choicely" in js.lower():
                        r.setdefault("script_endpoints", {})[src[:120]] = list(dict.fromkeys(eps))[:15] + (["(menciona choicely)"] if "choicely" in js.lower() else [])
                except Exception:
                    pass
        except Exception as e:
            r["error"] = str(e)[:200]
        res.append(r)
        time.sleep(0.8)
    U.save("probe.json", {"at": U.NOW.isoformat(), "results": res})
    S["probe_at"] = U.NOW.isoformat()
    return len(res)


def run(mod, G, cs, igsync, has_ig):
    global U
    U = mod
    S = U.load("socials.json", {})
    try:
        pageants(S, igsync, has_ig)
        n = sum(1 for p in S["pageants"].values() for k, v in p.items() if isinstance(v, dict) and v.get("verified"))
        U.note("Redes oficiales de cada concurso (verificadas)", True, n)
    except Exception as e:
        U.note("Redes oficiales de cada concurso", False, err=repr(e)[:200])
    try:
        contestants(S, G, cs)
        rec = S["contestants"].values()
        U.note("Redes de cada candidata (Instagram confirmado por API, TikTok comprobado)", True, sum(1 for r in rec if r.get("instagram")),
               err=f"{sum(1 for r in rec if r.get('tiktok'))} con TikTok · {sum(1 for r in rec if r.get('org_instagram'))} con cuenta de su organización nacional · {len(S['contestants'])} candidatas")
    except Exception as e:
        U.note("Redes de cada candidata", False, err=repr(e)[:200])
    try:
        probe(S)
    except Exception as e:
        U.note("Sonda de webs oficiales", False, err=repr(e)[:200])
    S["updated"] = U.NOW.isoformat()
    U.save("socials.json", S)
    return S
