/* Quals Lingo service worker: makes the app load offline and install to a phone's home screen.
   Pages and config are fetched fresh when online (so updates arrive at once); versioned app files are cached. */
const VERSION = "ql-__VERSION__";
const ASSETS = __ASSETS__;
self.addEventListener("install", e => {
  self.skipWaiting();
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(ASSETS)).catch(() => {}));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith("ql-") && k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;           // Supabase and fonts go straight to the network
  const fresh = req.mode === "navigate" || /\/(index\.html|config\.js|manifest\.webmanifest)?$/.test(url.pathname) || url.pathname.endsWith("config.js");
  if (fresh) {
    e.respondWith(fetch(req).then(r => { const c = r.clone(); caches.open(VERSION).then(x => x.put(req, c)); return r; })
      .catch(() => caches.match(req).then(r => r || caches.match("index.html"))));
  } else {
    e.respondWith(caches.match(req).then(r => r || fetch(req).then(n => { const c = n.clone(); caches.open(VERSION).then(x => x.put(req, c)); return n; })));
  }
});
