const CACHE_VERSION = "roadpulse-v15-easy-map-1";
const APP_CACHE = `${CACHE_VERSION}-app`;
const CDN_CACHE = `${CACHE_VERSION}-cdn`;

const APP_SHELL = [
  "/",
  "/assets/styles.css?v=webv15easy1",
  "/assets/app.js?v=webv15easy1",
  "/assets/pwa.js?v=webv15pwa1",
  "/assets/icons/icon-192.png",
  "/assets/icons/icon-512.png",
  "/assets/icons/icon-512-maskable.png",
  "/assets/icons/apple-touch-icon.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(APP_CACHE)
      .then(cache => Promise.all(
        APP_SHELL.map(url =>
          cache.add(url).catch(err => {
            console.warn("RoadPulse cache skipped:", url, err);
          })
        )
      ))
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

  // Live APIs are always network-only.
  if (
    url.origin === self.location.origin &&
    url.pathname.startsWith("/api/")
  ){
    return;
  }

  if (request.mode === "navigate"){
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

  if (
    url.origin === self.location.origin &&
    (
      url.pathname.startsWith("/assets/") ||
      url.pathname === "/manifest.webmanifest"
    )
  ){
    event.respondWith(
      caches.match(request).then(cached => {
        const fresh = fetch(request)
          .then(response => {
            if (response.ok){
              caches.open(APP_CACHE)
                .then(cache => cache.put(request, response.clone()));
            }
            return response;
          })
          .catch(() => cached);

        return cached || fresh;
      })
    );
    return;
  }

  // Leaflet library files may be cached; map tiles stay live/network-only.
  if (url.hostname === "unpkg.com"){
    event.respondWith(
      caches.open(CDN_CACHE).then(async cache => {
        const cached = await cache.match(request);
        if (cached) return cached;

        const response = await fetch(request);
        if (response.ok || response.type === "opaque"){
          cache.put(request, response.clone());
        }
        return response;
      })
    );
  }
});
