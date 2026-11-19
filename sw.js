/* CROWN · service worker: abre al instante (app guardada) y siempre trae datos frescos. */
const V = "crown-v4";
const SHELL = ["./", "index.html", "assets/styles.css", "assets/app.js", "manifest.webmanifest", "assets/icons/icon-192.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V && !k.startsWith("crown-img")).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  // datos: red primero (siempre frescos), caché si no hay señal
  if (u.pathname.includes("/data/")) {
    e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(V).then(x => x.put(e.request, c)); return r; }).catch(() => caches.match(e.request, { ignoreSearch: true })));
    return;
  }
  // fotos del espejo propio: caché primero (no cambian)
  if (u.host === "raw.githubusercontent.com" && u.pathname.includes("/media/")) {
    e.respondWith(caches.open("crown-img").then(c => c.match(e.request).then(hit => hit || fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }))));
    return;
  }
  // app: caché y actualización en segundo plano
  if (u.origin === location.origin) {
    e.respondWith(caches.match(e.request).then(hit => { const net = fetch(e.request).then(r => { caches.open(V).then(c => c.put(e.request, r.clone())); return r; }).catch(() => hit); return hit || net; }));
  }
});
