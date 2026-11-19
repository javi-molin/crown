"""
CROWN · sincronización con Instagram (API oficial de Meta) + espejo de imágenes.

- Hashtags oficiales (ig_hashtag_search → recent_media / top_media).
- Descubre las cuentas de las candidatas y de las organizaciones nacionales a partir de las menciones (@) en los
  posts y las verifica con Business Discovery (nombre/biografía). Luego las sigue en rotación.
- Espejo: copia optimizada (Pillow) de cada foto de Instagram en la rama `media` del repo, para que el panel
  pueda mostrarlas y descargarlas siempre (Instagram no permite mostrarlas incrustadas en otros sitios y sus
  enlaces caducan). Se sirven desde raw.githubusercontent.com.
"""
import os, re, sys, json, time, subprocess, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

U = None
HASHTAGS = [("missuniverse2026", "mu"), ("missuniverse", "mu"), ("missuniverso2026", "mu"), ("missinternational2026", "mi")]
BASE_ORGS = {"missuniversechileof": "mu|Chile", "themissuniverseph": "mu|Philippines", "missuniverse.mexico": "mu|Mexico"}
OFFICIAL = {"missuniverse", "missinternationalofficial"}
RAW = "https://raw.githubusercontent.com/javi-molin/crown/media/"


class RateLimited(Exception):
    pass


def graph(path, **params):
    tok, me = os.environ.get("IG_TOKEN"), os.environ.get("IG_USER_ID")
    params = {k: v.replace("{ME}", me) if isinstance(v, str) else v for k, v in params.items()}
    url = f"https://graph.facebook.com/v21.0/{path.replace('{ME}', me)}?" + urllib.parse.urlencode({**params, "access_token": tok})
    try:
        return json.loads(U.get(url, timeout=40))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        if any(f'"code":{c}' in body.replace(" ", "") for c in (4, 17, 32, 613)):
            raise RateLimited(body)
        raise RuntimeError(f"{e.code} {body}")


MEDIA_FIELDS = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count,children{media_url,media_type}"


def to_post(m, owner, contest, kind):
    kids = [c for c in (m.get("children") or {}).get("data", []) if c.get("media_url") and c.get("media_type") != "VIDEO"]
    imgs = [c["media_url"] for c in kids] or ([m["media_url"]] if m.get("media_url") and m.get("media_type") != "VIDEO" else [m["thumbnail_url"]] if m.get("thumbnail_url") else [])
    code = re.search(r"/(?:p|reel|tv)/([\w-]+)", m.get("permalink", "")) if m.get("permalink") else None
    code = code.group(1) if code else "h" + str(m.get("id"))
    return {"code": code, "url": m.get("permalink") or "", "owner": owner, "images": imgs[:10], "thumb": imgs[0] if imgs else None,
            "caption": (m.get("caption") or "")[:1500], "likes": m.get("like_count"), "comments": m.get("comments_count"),
            "is_video": m.get("media_type") == "VIDEO", "taken": (m.get("timestamp") or U.NOW.isoformat()).replace("+0000", "+00:00"),
            "contest": contest, "kind": kind}


def hashtag_sync(G, now):
    ids = G.setdefault("hashtag_ids", {})
    n = 0
    blk = G.get("hashtag_blocked")
    if blk and (now - datetime.fromisoformat(blk)).total_seconds() < 6 * 3600:
        return 0  # Meta exige "Public Content Access": reintenta cada 6 h sin gastar cuota
    for tag, cid in HASHTAGS:
        try:
            if tag not in ids:
                d = graph("ig_hashtag_search", user_id="{ME}", q=tag)
                ids[tag] = (d.get("data") or [{}])[0].get("id")
            if not ids.get(tag):
                continue
            for edge in ("recent_media", "top_media"):
                d = graph(f"{ids[tag]}/{edge}", user_id="{ME}", fields=MEDIA_FIELDS, limit=50)
                for m in d.get("data", []):
                    p = to_post(m, None, cid, "hashtag")
                    p["via"] = "#" + tag
                    prev = G["ig_posts"].get(p["code"], {})
                    G["ig_posts"][p["code"]] = {**p, **{k: v for k, v in prev.items() if k in ("owner", "who", "kind") and v}, "seen": now.isoformat()}
                    n += 1
                time.sleep(0.4)
        except RateLimited:
            U.note("Instagram · hashtags", False, n, err="límite de la API de Meta alcanzado; se reintenta en la próxima vuelta")
            return n
        except Exception as e:
            G.setdefault("hashtag_err", {})[tag] = str(e)[:200]
            if "Public Content Access" in str(e):
                G["hashtag_blocked"] = now.isoformat()
                break
    U.note("Instagram · hashtags oficiales (#missuniverse2026, #missuniverse…)", True, n,
           err=("; ".join(f"#{k}: {v[:90]}" for k, v in (G.get("hashtag_err") or {}).items()) or None))
    G["hashtag_err"] = {}
    return n


def discover(G, cs, budget=25):
    """Cuentas mencionadas en posts asignados a una sola candidata. Meta entrega los textos SIN la '@',
    así que se buscan palabras con forma de usuario que contengan el nombre de la candidata (o @menciones explícitas).
    Se confirman con Business Discovery; si la cuenta es personal (la API no la ve) queda como 'mencionada'."""
    names = {c["contest"] + "|" + c["country"]: c for c in cs}
    counts, src = {}, {}
    for p in G["ig_posts"].values():
        who = p.get("who") or []
        if len(who) != 1 or who[0] not in names:
            continue
        c = names[who[0]]
        parts = [x for x in re.split(r"[^a-z]+", U.norm(c["name"])) if len(x) >= 4]
        cap = p.get("caption", "")
        toks = {h.lower().strip(".") for h in re.findall(r"@([A-Za-z0-9_.]{3,30})", cap)}
        for h in re.findall(r"(?<![#\w])([A-Za-z0-9_.]{5,30})", cap):
            hl = h.lower().strip(".")
            if parts and any(x in hl for x in parts) and (re.search(r"[_.\d]", hl) or sum(x in hl for x in parts) >= 2 or len(hl) > max(map(len, parts)) + 2):
                toks.add(hl)
        for h in toks:
            if h in OFFICIAL or h == p.get("owner") or h.startswith("vote"):
                continue
            score = (5 if parts and any(x in h for x in parts) else 0) + 1
            counts[(who[0], h)] = counts.get((who[0], h), 0) + score
            src.setdefault((who[0], h), p.get("owner"))
    tried = G.setdefault("mention_tried", {})
    orgs = G.setdefault("orgs", dict(BASE_ORGS))
    done = 0
    for (k, h), n in sorted(counts.items(), key=lambda x: -x[1]):
        if done >= budget:
            break
        c = names.get(k)
        cur = G["handles"].get(k, {})
        if tried.get(f"{k}|{h}") or h in orgs or any(v.get("handle") == h for v in G["handles"].values()):
            continue
        if cur.get("conf") == "verificada" and not re.search(r"miss|univers", h):
            continue
        tried[f"{k}|{h}"] = U.NOW.isoformat()
        done += 1
        parts = [x for x in re.split(r"[^a-z]+", U.norm(c["name"])) if len(x) >= 4]
        try:
            d = graph("{ME}", fields=f"business_discovery.username({h}){{username,name,biography,followers_count}}")["business_discovery"]
        except RateLimited:
            break
        except Exception:
            # cuenta personal o inexistente: si lleva su nombre y su organización la menciona, se guarda como enlace
            if any(x in h for x in parts) and n >= 6 and cur.get("conf") not in ("verificada", "mencionada"):
                G["handles"][k] = {"handle": h, "conf": "mencionada", "name": c["name"], "via": f"mencionada por @{src.get((k, h))} (cuenta personal: la API no muestra sus fotos)"}
            continue
        txt = U.norm(" ".join([d.get("username", ""), d.get("name") or "", d.get("biography") or ""]))
        ctry = [t for t in {U.norm(c["country"]), U.norm(c.get("country_es") or "")} if t]
        if re.search(r"miss|univers|organiza|pageant|reina", txt) and any(t in txt for t in ctry) and not any(x in U.norm(h) for x in parts):
            orgs[h] = k
        elif any(x in txt for x in parts):
            G["handles"][k] = {"handle": h, "conf": "verificada", "name": c["name"], "followers": d.get("followers_count"), "via": f"mencionada por @{src.get((k, h))} + API"}
        time.sleep(0.4)
    return done


def _slug(t):
    return re.sub(r"[^a-z0-9]", "", U.norm(t or ""))


def guesses(c):
    """Usuarios probables de la candidata y de su organización nacional."""
    parts = [p for p in re.split(r"[^a-z]+", U.norm(c["name"])) if len(p) >= 2]
    out = []
    if len(parts) >= 2:
        f, l = parts[0], parts[-1]
        out += [f + l, f + "." + l, f + "_" + l, f + l + "official", f + l + "_", f + "." + l + "_"]
        if len(parts) >= 3:
            out += [f + parts[1], f + "." + parts[1], "".join(parts)]
    orgs = []
    for ct in {_slug(c["country"]), _slug(c.get("country_es"))}:
        if not ct:
            continue
        if c["contest"] == "mu":
            orgs += ["missuniverse" + ct, "missuniverse." + ct, "missuniverse_" + ct, "missuniverse" + ct + "official",
                     "missuniverso" + ct, "missuniverso." + ct, "miss" + ct + "universe", "missuniverse" + ct + "org"]
        elif c["contest"] == "mi":
            orgs += ["missinternational" + ct, "miss" + ct + "international"]
    return [("c", h) for h in dict.fromkeys(out)] + [("o", h) for h in dict.fromkeys(orgs)]


def guess_sync(G, cs, budget=24):
    """Prueba usuarios probables con Business Discovery y solo acepta los que la API confirma."""
    tried = G.setdefault("guess_tried", {})
    orgs = G.setdefault("orgs", dict(BASE_ORGS))
    org_of = {}
    for h, k in orgs.items():
        org_of.setdefault(k, h)
    order = sorted(cs, key=lambda c: (0 if c.get("hot") else 1, c["contest"] != "mu"))
    done = found = 0
    plan = [(c, kind, h) for phase in ("o", "c") for c in order for kind, h in guesses(c) if kind == phase]
    for c, kind, h in plan:
        k = c["contest"] + "|" + c["country"]
        have_c = G["handles"].get(k, {}).get("conf") == "verificada"
        if True:
            if done >= budget:
                return done, found
            if (kind == "c" and have_c) or (kind == "o" and k in org_of) or tried.get(h):
                continue
            tried[h] = U.NOW.isoformat()
            done += 1
            try:
                d = graph("{ME}", fields=f"business_discovery.username({h}){{username,name,biography,followers_count}}")["business_discovery"]
            except RateLimited:
                return done, found
            except Exception:
                continue
            txt = U.norm(" ".join([d.get("username", ""), d.get("name") or "", d.get("biography") or ""]))
            parts = [p for p in re.split(r"[^a-z]+", U.norm(c["name"])) if len(p) >= 3]
            ctry = [t for t in {U.norm(c["country"]), U.norm(c.get("country_es") or "")} if t]
            signal = re.search(r"miss|univers|reina|queen|pageant", txt) or any(t in txt for t in ctry)
            if kind == "c" and len(parts) >= 2 and sum(p in txt for p in parts) >= 2 and signal:
                G["handles"][k] = {"handle": h, "conf": "verificada", "name": c["name"], "followers": d.get("followers_count"), "via": "API (usuario confirmado)"}
                found += 1
            elif kind == "o" and re.search(r"miss|univers|international", txt) and any(t in txt for t in ctry):
                orgs[h] = k
                org_of[k] = h
                found += 1
            time.sleep(0.3)
    return done, found


# ------------------------------------------------------------------ espejo de imágenes
def _git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd or U.ROOT, capture_output=True, text=True)


def ensure_worktree():
    wt = os.path.join(U.ROOT, ".media")
    if os.path.isdir(os.path.join(wt, "ig")) or os.path.exists(os.path.join(wt, ".git")):
        _git("fetch", "-q", "--depth", "1", "origin", "media", cwd=wt)
        _git("reset", "-q", "--hard", "origin/media", cwd=wt)
        return wt
    has = _git("ls-remote", "--heads", "origin", "media").stdout.strip()
    if has:
        _git("fetch", "-q", "--depth", "1", "origin", "media:refs/remotes/origin/media")
        r = _git("worktree", "add", "-f", "-B", "media", wt, "origin/media")
    else:
        r = _git("worktree", "add", "-f", "--detach", wt)
        _git("checkout", "-q", "--orphan", "media", cwd=wt)
        _git("rm", "-rfq", ".", cwd=wt)
        os.makedirs(os.path.join(wt, "ig", "t"), exist_ok=True)
        open(os.path.join(wt, "README.md"), "w").write("Copias optimizadas de imágenes para el panel CROWN (uso editorial, con crédito).\n")
    if r.returncode != 0 and not os.path.isdir(wt):
        raise RuntimeError(r.stderr[:200])
    os.makedirs(os.path.join(wt, "ig", "t"), exist_ok=True)
    return wt


def pil():
    try:
        from PIL import Image
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pillow"], capture_output=True)
        from PIL import Image
    return Image


def bg_of(im):
    """Color del fondo: mediana del borde superior y laterales (zona alta). 'claro' = neutro claro (estudio blanco/gris/crema)."""
    import colorsys, statistics
    s = im.convert("RGB").resize((60, 80))
    px = [s.getpixel((x, y)) for y in range(0, 6) for x in range(60)] + [s.getpixel((x, y)) for y in range(6, 48) for x in (0, 1, 2, 57, 58, 59)]
    med = tuple(int(statistics.median(p[i] for p in px)) for i in range(3))
    sd = statistics.pstdev([sum(p) / 3 for p in px])
    h, sat, v = colorsys.rgb_to_hsv(*(c / 255 for c in med))
    if v > 0.70 and sat < 0.20:
        kind = "claro"
    elif v < 0.30:
        kind = "oscuro"
    elif 0.19 < h < 0.50 and sat > 0.12:
        kind = "verde"
    else:
        kind = "color"
    return {"bg": kind, "bgc": "#%02x%02x%02x" % med, "uni": round(sd, 1)}


def mirror(G, todo, budget=160, seconds=150):
    """todo: lista de (clave, url) en orden de prioridad. Guarda ig/<clave>.jpg (1080 px) e ig/t/<clave>.jpg (480 px)."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return 0
    import io
    Image = pil()
    wt = ensure_worktree()
    mp = G.setdefault("mirror", {})
    t0, n, fails = time.time(), 0, 0
    for key, url in todo:
        if key in mp or not url:
            continue
        if n >= budget or time.time() - t0 > seconds:
            break
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            for sub, size, q in (("", 1080, 84), ("t/", 480, 78)):
                c = im.copy()
                c.thumbnail((size, int(size * 1.6)))
                c.save(os.path.join(wt, "ig", sub + key + ".jpg"), "JPEG", quality=q, optimize=True, progressive=True)
            mp[key] = {"f": RAW + "ig/" + key + ".jpg", "t": RAW + "ig/t/" + key + ".jpg", "w": im.width, "h": im.height, **bg_of(im)}
            n += 1
        except Exception:
            fails += 1
    nb = 0
    for key, rec in mp.items():  # fondo de las copias antiguas (sin volver a descargarlas)
        if "bg" in rec or nb >= 800:
            continue
        try:
            rec.update(bg_of(Image.open(os.path.join(wt, "ig", "t", key + ".jpg"))))
            nb += 1
        except Exception:
            rec["bg"] = None
    if n:
        _git("add", "-A", cwd=wt)
        _git("commit", "-q", "-m", f"imágenes: +{n}", cwd=wt)
        for _ in range(3):
            if _git("push", "-q", "origin", "HEAD:media", cwd=wt).returncode == 0:
                break
            _git("pull", "-q", "--rebase", "origin", "media", cwd=wt)
            time.sleep(3)
    U.note("Espejo de imágenes (copias propias para mostrar y descargar)", fails < max(5, n), n,
           err=f"{len(mp)} imágenes en el espejo" + (f"; {fails} fallaron" if fails else ""))
    return n
