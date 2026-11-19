"""Sonda de diagnóstico: revisa cómo responden algunas fuentes desde GitHub Actions."""
import json, re, urllib.request, urllib.parse
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
T = ["https://missuniverseorg.com/vote", "https://missuniverseorg.com/", "https://www.missuniverse.com/",
     "https://www.missuniverse.com/delegates", "https://missuniverseorg.com/delegates",
     "https://www.bing.com/images/search?q=Dominga+L%C3%B3pez+Miss+Universe+2026",
     "https://duckduckgo.com/?q=Dominga+Lopez+Miss+Universe+2026&iax=images&ia=images"]
out = {}
for u in T:
    r = {}
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "es-CL,es;q=0.9"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            b = resp.read().decode("utf-8", "replace"); r["status"] = resp.status; r["final"] = resp.geturl()
        r["len"] = len(b); r["title"] = (re.search(r"<title>(.*?)</title>", b, re.S) or [None, ""])[1][:120]
        r["scripts"] = re.findall(r'<script[^>]+src="([^"]+)"', b)[:25]
        r["imgs"] = list(dict.fromkeys(re.findall(r'https?://[^"\'\s>]+\.(?:jpe?g|png|webp)(?:\?[^"\'\s>]*)?', b)))[:40]
        r["apis"] = list(dict.fromkeys(re.findall(r'https?://[^"\'\s>]*(?:api|graphql|wp-json|contestant|delegate)[^"\'\s>]*', b, re.I)))[:30]
        r["vqd"] = (re.search(r'vqd=["\']?([\d-]+)', b) or [None, None])[1]
        r["next"] = "__NEXT_DATA__" in b; r["nuxt"] = "__NUXT__" in b
        r["head"] = b[:1500]; r["sample"] = b[len(b)//2: len(b)//2 + 1500]
    except Exception as e:
        r["error"] = str(e)[:200]
    out[u] = r
json.dump(out, open("data/_probe.json", "w"), ensure_ascii=False, indent=1)
