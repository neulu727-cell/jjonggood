/* Service Worker — 쫑굿 예약관리 PWA */

const CACHE_NAME = 'jjonggood-v59';
const OFFLINE_URL = '/offline.html';

// 프리캐시: SW 설치 시 즉시 캐시할 리소스
const PRECACHE_URLS = [
  OFFLINE_URL,
];

/* ── Install: 오프라인 페이지 프리캐시 ── */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

/* ── Activate: 구버전 캐시 정리 ── */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

/* ── Fetch: 전략 분기 ── */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // http/https가 아닌 요청 (chrome-extension:// 등) → 무시
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // POST 등 GET 이외 → 캐시 불가, 패스스루
  if (request.method !== 'GET') {
    return;
  }

  // API / SSE → network-only (패스스루)
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Navigation (HTML 페이지) → network-first, offline fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // 성공 시 캐시에 저장
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          return response;
        })
        .catch(() =>
          caches.match(request).then((cached) => cached || caches.match(OFFLINE_URL))
        )
    );
    return;
  }

  // manifest, 아이콘 → network-first (항상 최신)
  if (url.pathname === '/manifest.json' || url.pathname.startsWith('/static/icons/')) {
    event.respondWith(
      fetch(request).then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        return response;
      }).catch(() => caches.match(request))
    );
    return;
  }

  // Static assets (CSS/JS/이미지/폰트, ?v=hash 포함) → cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // 그 외 → network-first
  event.respondWith(
    fetch(request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        return response;
      })
      .catch(() => caches.match(request))
  );
});
