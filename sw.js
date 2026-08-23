const CACHE='raja-scanner-v5-shell-1';
const SHELL=['/','/manifest.json','/static/raja-ai-icon-192.png','/static/raja-ai-icon-512.png'];

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(c=>c.addAll(SHELL).catch(()=>{}))
      .then(()=>self.skipWaiting())
  )
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(
        keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))
      ))
      .then(()=>self.clients.claim())
  )
});

self.addEventListener('fetch',event=>{
  const req=event.request,
        url=new URL(req.url);

  if(
    req.method!=='GET' ||
    url.origin!==location.origin ||
    url.pathname.startsWith('/api/') ||
    url.pathname==='/share-target'
  ){
    return;
  }

  event.respondWith(
    fetch(req)
      .then(res=>{
        const copy=res.clone();

        if(res.ok){
          caches.open(CACHE)
            .then(c=>c.put(req,copy))
            .catch(()=>{});
        }

        return res;
      })
      .catch(()=>
        caches.match(req)
          .then(r=>r||caches.match('/'))
      )
  )
});
