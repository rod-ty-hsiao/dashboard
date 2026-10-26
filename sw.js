/* Dashboard service worker:只快取網頁外殼,資料一律走網路(Google Drive) */
const CACHE = 'dashboard-shell-v2';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return; // Google API / 字體 / 地圖圖磚不經過這裡
  // 網路優先:有網路時永遠拿到最新版,離線才用快取
  e.respondWith(
    fetch(req, { cache: 'no-cache' })   // 一律向伺服器確認有沒有新版,不吃瀏覽器的 HTTP 快取
      .then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(req).then(r => r || caches.match('index.html')))
  );
});
