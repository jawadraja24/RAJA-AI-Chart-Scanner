const CACHE_VERSION = "roadpulse-v22-smooth-map-1";
const APP_CACHE = `${CACHE_VERSION}-app`;
const CDN_CACHE = `${CACHE_VERSION}-cdn`;

const APP_SHELL = [
  "/",
  "/assets/styles.css?v=webv22smooth1",
  "/assets/app.js?v=webv22smooth1",
  "/assets/pwa.js?v=webv22smooth1",
  "/manifest.webmanifest?v=webv22smooth1",
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
          .filter(key => key.startsWith("roadpulse-") && !key.startsWith(CACHE_VERSION))
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Authentication, routing, traffic and report APIs must always be live.
  if (
    url.origin === self.location.origin &&
    url.pathname.startsWith("/api/")
  ){
    return;
  }

  // HTML: network first so a deployment is visible immediately, with an
  // offline fallback to the last successful app shell.
  if (request.mode === "navigate"){
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok){
            event.waitUntil(
              caches.open(APP_CACHE)
                .then(cache => cache.put("/", response.clone()))
                .catch(()=>{})
            );
          }
          return response;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }

  // Core app code: network first avoids stale JavaScript/CSS after an update.
  if (
    url.origin === self.location.origin &&
    (
      url.pathname === "/assets/app.js" ||
      url.pathname === "/assets/styles.css" ||
      url.pathname === "/assets/pwa.js" ||
      url.pathname === "/manifest.webmanifest"
    )
  ){
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok){
            event.waitUntil(
              caches.open(APP_CACHE)
                .then(cache => cache.put(request, response.clone()))
                .catch(()=>{})
            );
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Same-origin static images/icons: cache first, then network and store.
  if (
    url.origin === self.location.origin &&
    url.pathname.startsWith("/assets/")
  ){
    event.respondWith(
      caches.open(APP_CACHE).then(async cache => {
        const cached = await cache.match(request);
        if (cached) return cached;

        const response = await fetch(request);
        if (response.ok){
          event.waitUntil(cache.put(request, response.clone()).catch(()=>{}));
        }
        return response;
      })
    );
    return;
  }

  // Leaflet library files can be cached. Map tiles intentionally stay network
  // controlled to avoid huge/off-policy tile caches.
  if (url.hostname === "unpkg.com"){
    event.respondWith(
      caches.open(CDN_CACHE).then(async cache => {
        const cached = await cache.match(request);
        if (cached) return cached;

        const response = await fetch(request);
        if (response.ok || response.type === "opaque"){
          event.waitUntil(cache.put(request, response.clone()).catch(()=>{}));
        }
        return response;
      })
    );
  }
});
