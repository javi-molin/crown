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


MEDIA_FIELDS = "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count,children{media_url,media_type}"


def to_post(m, owner, contest, kind):
    kids = [c for c in (m.get("children") or {}).get("data", []) if c.get("media_url") and c.get("media_type") != "VIDEO"]
    imgs = [c["media_url"] for c in kids] or ([m["media_url"]] if m.get("media_url") and m.get("media_type") != "VIDEO" else [])
    code = re.search(r"/(?:p|reel|tv)/([\w-]+)", m.get("permalink", "")) if m.get("permalink") else None
    code = code.group(1) if code else "h" + str(m.get("id"))
    return {"code": code, "url": m.get("permalink") or "", "owner": owner, "images": imgs[:10], "thumb": imgs[0] if imgs else None,
            "caption": (m.get("caption") or "")[:1500], "likes": m.get("like_count"), "comments": m.get("comments_count"),
            "is_video": m.get("media_type") == "VIDEO", "taken": (m.get("timestamp") or U.NOW.isoformat()).replace("+0000", "+00:00"),
            "contest": contest, "kind": kind}


def hashtag_sync(G, now):
    ids = G.setdefault("hashtag_ids", {})
    n = 0
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
    U.note("Instagram · hashtags oficiales (#missuniverse2026, #missuniverse…)", True, n,
           err=("; ".join(f"#{k}: {v[:90]}" for k, v in (G.get("hashtag_err") or {}).items()) or None))
    G["hashtag_err"] = {}
    return n


def discover(G, cs, budget=10):
    """Busca @menciones en posts ya asignados a una sola candidata y verifica la cuenta con Business Discovery."""
    names = {c["contest"] + "|" + c["country"]: c for c in cs}
    counts = {}
    for p in G["ig_posts"].values():
        who = p.get("who") or []
        if len(who) != 1:
            continue
        for h in set(re.findall(r"@([A-Za-z0-9_.]{3,30})", p.get("caption", ""))):
            h = h.lower().strip(".")
            if h in OFFICIAL or h == p.get("owner"):
                continue
            counts[(who[0], h)] = counts.get((who[0], h), 0) + 1
    tried = G.setdefault("mention_tried", {})
    orgs = G.setdefault("orgs", dict(BASE_ORGS))
    done = 0
    for (k, h), n in sorted(counts.items(), key=lambda x: -x[1]):
        if done >= budget:
            break
        c = names.get(k)
        if not c or tried.get(f"{k}|{h}") or h in orgs or any(v.get("handle") == h for v in G["handles"].values()):
            continue
        if G["handles"].get(k, {}).get("conf") == "verificada" and not re.search(r"miss|univers", h):
            continue
        tried[f"{k}|{h}"] = U.NOW.isoformat()
        done += 1
        try:
            d = graph("{ME}", fields=f"business_discovery.username({h}){{username,name,biography,followers_count}}")["business_discovery"]
        except RateLimited:
            break
        except Exception:
            continue  # cuenta personal o inexistente: Business Discovery solo ve cuentas profesionales
        txt = U.norm(" ".join([d.get("username", ""), d.get("name") or "", d.get("biography") or ""]))
        parts = [p for p in re.split(r"[^a-z]+", U.norm(c["name"])) if len(p) >= 4]
        ctry = [t for t in {U.norm(c["country"]), U.norm(c.get("country_es") or "")} if t]
        if re.search(r"miss|univers|organiza|pageant|reina", txt) and any(t in txt for t in ctry) and not any(p in U.norm(h) for p in parts):
            orgs[h] = k
        elif any(p in txt for p in parts):
            G["handles"][k] = {"handle": h, "conf": "verificada", "name": c["name"], "followers": d.get("followers_count"), "via": "mención + API"}
        time.sleep(0.4)
    return done


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
            mp[key] = {"f": RAW + "ig/" + key + ".jpg", "t": RAW + "ig/t/" + key + ".jpg", "w": im.width, "h": im.height}
            n += 1
        except Exception:
            fails += 1
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
