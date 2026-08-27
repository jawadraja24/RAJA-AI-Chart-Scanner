const CACHE_VERSION = "roadpulse-v141-pwa-1";
const APP_CACHE = `${CACHE_VERSION}-app`;
const CDN_CACHE = `${CACHE_VERSION}-cdn`;

const APP_SHELL = [
  "/",
  "/assets/styles.css?v=webv14pwa1",
  "/assets/app.js?v=webv13modes1",
  "/assets/pwa.js?v=webv141pwa1",
  "/assets/icons/icon-192.png",
  "/assets/icons/icon-512.png",
  "/assets/icons/apple-touch-icon.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(APP_CACHE)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => !key.startsWith(CACHE_VERSION))
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Never cache APIs, live traffic, auth, reports, routes, or search.
  if (url.origin === self.location.origin && url.pathname.startsWith("/api/")) {
    return;
  }

  // Navigation: network first, cached app shell only as an offline fallback.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then(response => {
          const copy = response.clone();
          caches.open(APP_CACHE).then(cache => cache.put("/", copy));
          return response;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }

  // Local static assets: cache first, refresh in background.
  if (
    url.origin === self.location.origin &&
    (
      url.pathname.startsWith("/assets/") ||
      url.pathname === "/manifest.webmanifest"
    )
  ) {
    event.respondWith(
      caches.match(request).then(cached => {
        const fresh = fetch(request)
          .then(response => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(APP_CACHE).then(cache => cache.put(request, copy));
            }
            return response;
          })
          .catch(() => cached);

        return cached || fresh;
      })
    );
    return;
  }

  // Cache Leaflet library resources, but do NOT cache map tiles.
  if (url.hostname === "unpkg.com") {
    event.respondWith(
      caches.open(CDN_CACHE).then(async cache => {
        const cached = await cache.match(request);
        if (cached) return cached;

        const response = await fetch(request);
        if (response.ok || response.type === "opaque") {
          cache.put(request, response.clone());
        }
        return response;
      })
    );
  }
});
