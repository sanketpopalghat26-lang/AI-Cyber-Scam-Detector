/* Service Worker for AI Cyber Scam Detector PWA */
const CACHE_NAME = 'scam-detector-v1'
const RUNTIME_CACHE = 'scam-detector-runtime-v1'

// Core assets to precache on install
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icons/icon-192.svg',
  '/icons/icon-512.svg'
]

// Install: precache core assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  )
})

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE_NAME && key !== RUNTIME_CACHE).map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  )
})

// Helpers
function isApiRequest(url) {
  return url.pathname.startsWith('/api') ||
    url.pathname.startsWith('/predict') ||
    url.pathname.startsWith('/auth') ||
    url.pathname.startsWith('/dashboard') ||
    url.pathname.startsWith('/history') ||
    url.pathname.startsWith('/health')
}

function isStaticAsset(url) {
  return url.pathname.startsWith('/assets/') ||
    /\.(js|css|png|svg|woff2?|ico)$/i.test(url.pathname)
}

// Network-first for API requests (never serve stale API data)
async function networkFirst(request) {
  try {
    const response = await fetch(request)
    if (response.ok) {
      const cache = await caches.open(RUNTIME_CACHE)
      cache.put(request, response.clone())
    }
    return response
  } catch (error) {
    const cached = await caches.match(request)
    if (cached) return cached
    throw error
  }
}

// Cache-first for static assets (immutable, hashed)
async function cacheFirst(request) {
  const cached = await caches.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) {
    const cache = await caches.open(RUNTIME_CACHE)
    cache.put(request, response.clone())
  }
  return response
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(RUNTIME_CACHE)
  const cached = await cache.match(request)
  const network = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone())
      return response
    })
    .catch(() => cached)
  return cached || network
}

// Fetch handler
self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)

  // Only handle same-origin GET requests
  if (request.method !== 'GET' || url.origin !== self.location.origin) return

  // Skip API and health endpoints (network-first / no cache for auth)
  if (isApiRequest(url)) {
    if (url.pathname.startsWith('/health')) return
    event.respondWith(networkFirst(request))
    return
  }

  // Static hashed assets: cache-first
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request))
    return
  }

  // Navigation and HTML: stale-while-revalidate with network fallback
  event.respondWith(staleWhileRevalidate(request))
})
