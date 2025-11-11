// Service Worker to intercept all requests and proxy them
// This runs at the browser level before content filters see requests

const PROXY_ORIGIN = self.location.origin;
const TARGET_DOMAINS = [
    'netflix.com',
    'nflxext.com',
    'nflxso.net',
    'nflxvideo.net',
    'nflximg.net'
];

self.addEventListener('install', (event) => {
    console.log('[SW] Service Worker installing...');
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('[SW] Service Worker activating...');
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // Skip if already going through proxy
    if (url.pathname.startsWith('/proxy')) {
        return;
    }
    
    // Check if this is a Netflix domain that should be proxied
    const shouldProxy = TARGET_DOMAINS.some(domain => url.hostname.includes(domain));
    
    if (shouldProxy && url.hostname !== PROXY_ORIGIN) {
        // Intercept and proxy the request
        const proxiedUrl = `${PROXY_ORIGIN}/proxy?url=${encodeURIComponent(event.request.url)}`;
        
        console.log('[SW] Proxying:', event.request.url, '->', proxiedUrl);
        
        event.respondWith(
            fetch(proxiedUrl, {
                method: event.request.method,
                headers: event.request.headers,
                credentials: 'omit'
            })
        );
    }
});
