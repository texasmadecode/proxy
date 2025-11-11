# 🚀 Master Proxy - Multi-Mode Web Bypass System

A comprehensive proxy server combining **6 successful bypass strategies** developed through extensive testing against Lightspeed Filter Agent and similar device-level filtering systems.

## 🎯 Purpose

Built specifically for bypassing school/enterprise web filters (like Lightspeed Filter Agent) that perform:
- SSL decryption and inspection
- Device-level request blocking
- Domain and content-type filtering
- Request interception before network transmission

## ✨ Features

- **6 Proxy Modes**: FlixHQ Streaming, Video Proxy, Iframe Proxy, Ultra Mode, VPN Tunnel, Stealth Mode
- **Video Streaming**: Server-side relay for MP4, HLS (.m3u8), DASH streaming
- **Resource Inlining**: Complete server-side assembly of pages (images, CSS, JS, fonts)
- **Encrypted Tunnel**: WebSocket-based VPN-style encrypted routing
- **CORS Support**: All endpoints allow cross-origin requests
- **Clean Logging**: Structured console output for debugging

## 🚀 Quick Start

### Installation

```bash
# Clone or navigate to the proxy directory
cd /workspaces/proxy

# Install dependencies (flask-sock will auto-install on first run)
pip3 install flask requests flask-sock simple-websocket

# Run the master proxy
python3 master_proxy.py
```

The server will start on `http://0.0.0.0:5000`

### Access

Open in your browser:
```
http://localhost:5000
```

You'll see a homepage with all 6 proxy modes and their descriptions.

## 📖 Proxy Modes

### 1. 🎬 FlixHQ Streaming Mode
**Best for: Free streaming sites (FlixHQ, similar)**

```
http://localhost:5000/flixhq/
http://localhost:5000/flixhq/tv-show/the-big-bang-theory-39481
```

**How it works:**
- Proxies all FlixHQ pages with aggressive URL rewriting
- Injects JavaScript to intercept ALL iframe and video sources
- Routes video streams through `/video-proxy` endpoint
- Routes embedded players through `/iframe-proxy` endpoint
- Browser only contacts allowed domain (your Codespaces host)

**What's intercepted:**
- `iframe.src` assignments (embedded players)
- `video.src` / `audio.src` assignments
- `fetch()` calls for .m3u8, .mp4, .ts files
- Dynamic iframe creation via MutationObserver

---

### 2. 📹 Video Proxy
**Best for: Direct video streaming**

```
http://localhost:5000/video-proxy?url=VIDEO_URL
```

**Example:**
```
http://localhost:5000/video-proxy?url=https://example.com/video.mp4
```

**How it works:**
- Server fetches video stream from remote host
- Streams chunks to browser via chunked transfer encoding
- Supports MP4, HLS (.m3u8), DASH, and .ts segments
- Browser sees: single allowed domain (your server)
- Filter sees: outbound HTTPS from your server (not blocked)

**Use case:**
- Bypass domain-level video blocking
- Re-stream content from blocked hosts
- Handle certificate errors server-side

---

### 3. 🖼️ Iframe Proxy
**Best for: Embedded player frames**

```
http://localhost:5000/iframe-proxy?url=IFRAME_URL
```

**Example:**
```
http://localhost:5000/iframe-proxy?url=https://player.example.com/embed/12345
```

**How it works:**
- Recursively proxies iframe content
- Rewrites URLs inside iframe to route through proxy
- Injects video interceptor into iframe
- Handles nested iframes (frames within frames)

**Use case:**
- Proxy embedded video players
- Handle third-party player hosts
- Recursive proxying for multi-level embeds

---

### 4. ⚡ Ultra Mode
**Best for: Static pages, image-heavy sites**

```
http://localhost:5000/ultra/?url=TARGET_URL
```

**Example:**
```
http://localhost:5000/ultra/?url=https://example.com
```

**How it works:**
- Fetches HTML from target
- Finds ALL external resources (images, CSS, JS, fonts)
- Fetches them in parallel (ThreadPoolExecutor)
- Inlines everything as data URIs or inline scripts/styles
- Blocks all client-side external requests via JavaScript
- Browser receives: ONE HTML file, makes ZERO external requests

**Use case:**
- Complete bypass for static content
- Sites with many images
- Avoid triggering filter on resource requests

**Limitations:**
- Dynamic JavaScript that loads resources may break
- Large pages = slow first load (fetching everything)
- Not suitable for streaming video

---

### 5. 🔒 VPN Tunnel Mode
**Best for: Complete destination hiding**

**WebSocket endpoint:**
```
wss://your-codespaces-host/tunnel
```

**How it works:**
- Client connects via WebSocket
- Client sends **encrypted** JSON requests: `{url: "...", method: "GET"}`
- Server decrypts, performs fetch, encrypts response
- Server returns base64-encoded body + headers
- Filter sees: encrypted WebSocket data (destinations hidden)

**Encryption:** Simple XOR (key: 0x5A) - proof of concept, not production-grade

**Use case:**
- Hide destination URLs from filter
- VPN-like behavior in browser
- Route ALL requests through one encrypted channel

**Client implementation:**
```javascript
const ws = new WebSocket('wss://your-host/tunnel');
ws.onopen = () => {
    const request = {url: 'https://example.com', method: 'GET'};
    const encrypted = encrypt(JSON.stringify(request)); // XOR encrypt
    ws.send(btoa(encrypted));
};
ws.onmessage = (event) => {
    const decrypted = decrypt(atob(event.data));
    const response = JSON.parse(decrypted);
    console.log(response.body); // base64 encoded
};
```

---

### 6. 🥷 Stealth Mode
**Best for: Evading content-type filters (experimental)**

```
http://localhost:5000/stealth/
```

**How it works:**
- Resources requested as "text/plain" JSON API calls
- Images/fonts returned as base64-wrapped JSON
- Client-side JavaScript decodes and creates blob URLs
- Filter sees: text API data, not image/video files

**Status:** Partially successful in testing - some filters still block `/api/resource/*` endpoints

**Use case:**
- Disguise resource types
- Evade MIME-type-based blocking
- Experimental fallback method

---

## ⚙️ Configuration

Edit `master_proxy.py` to customize:

```python
FLIXHQ_URL = "https://flixhq.to/"  # Default target for FlixHQ mode
DEFAULT_TIMEOUT = 15               # Request timeout in seconds
MAX_WORKERS = 10                   # Parallel fetch workers for Ultra mode
```

---

## 🧪 Testing

### Homepage Test
```bash
curl http://localhost:5000/
```
Should return HTML with mode selector.

### Video Proxy Test
```bash
curl -I "http://localhost:5000/video-proxy?url=https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
```
Should return `HTTP/1.1 200` with `Content-Type: video/mp4`.

### FlixHQ Mode Test
```bash
curl http://localhost:5000/flixhq/ | head -50
```
Should return HTML with injected interceptor script.

### Ultra Mode Test
```bash
curl "http://localhost:5000/ultra/?url=https://example.com" | grep "Ultra"
```
Should show banner indicating Ultra mode active.

---

## ⚠️ Limitations

### What CANNOT be bypassed:

1. **DRM-protected content**
   - Netflix, Disney+, HBO Max, etc. use Widevine DRM
   - Cannot decrypt or proxy DRM content
   - **Solution:** Use free streaming sites (FlixHQ mode)

2. **Device-level filter with kernel hooks**
   - Some enterprise filters run at OS/kernel level
   - Can block ANY outbound traffic regardless of proxy
   - **Solution:** Use external VPS/VPN (outside device control)

3. **Certificate pinning**
   - Some apps pin specific SSL certificates
   - Proxy with different cert will be rejected
   - **Solution:** Use browser-based access (no pinning)

4. **WebRTC leaks**
   - Browser may leak real IP via WebRTC
   - Filter could detect and block
   - **Solution:** Disable WebRTC in browser settings

### What CAN be bypassed:

✅ Domain blocking (proxy hides destination)  
✅ Content-type filtering (ultra-embed, stealth mode)  
✅ Image/font blocking (inline as data URIs)  
✅ Video streaming from non-DRM sites (server relay)  
✅ SSL inspection (server performs SSL handshake)  
✅ Request-level blocking (server makes requests)  

---

## 🐛 Debugging

### Enable verbose logging:
```python
app.run(host='0.0.0.0', port=5000, debug=True)
```

### Check server logs:
All requests logged with structured format:
```
[MODE    ] STATUS METHOD URL
[FLIXHQ  ] ✓ 100676b GET  https://flixhq.to/
[VIDEO   ] ✓ video/mp4 GET  https://example.com/video.mp4
[IFRAME  ] → GET  https://player.example.com/embed/123
```

### Common issues:

**"Connection refused"**
- Server not running or wrong port
- Check: `ps aux | grep master_proxy`

**"Timeout" errors**
- Remote host slow or unreachable
- Increase `DEFAULT_TIMEOUT` in config

**Video not playing**
- Check browser console for errors
- Verify `/video-proxy` endpoint accessible
- Some hosts may block server IP (not your IP)

**Iframe blank**
- Iframe host may block embedding (X-Frame-Options)
- Try Ultra mode instead (fetches and inlines)

---

## 🔐 Security Considerations

### For educational/personal use only:

- **Respect Terms of Service** - Using proxies may violate site ToS
- **Copyright laws apply** - Don't pirate copyrighted content
- **School/work policies** - Bypassing filters may violate acceptable use policies
- **No warranty** - Use at your own risk

### Proxy security:

- **Encryption:** VPN tunnel uses toy XOR encryption (not secure for sensitive data)
- **Logging:** Server logs all URLs (visible to server host/admin)
- **HTTPS:** Use HTTPS for Codespaces URL to encrypt browser ↔ server traffic
- **Access control:** No authentication built in - anyone with URL can use proxy

### Recommendations:

- Run on **private Codespaces** or **personal VPS** (not public servers)
- Use **HTTPS** (Codespaces provides this by default)
- Implement **rate limiting** if exposing publicly
- Add **authentication** for shared environments
- **Monitor bandwidth** - video streaming uses significant data

---

## 📊 Performance

### Benchmarks (informal):

| Mode | First Load | Subsequent | Bandwidth | CPU |
|------|-----------|------------|-----------|-----|
| FlixHQ Streaming | ~2s | <1s | High (video) | Low |
| Video Proxy | ~1s | <1s | High | Low |
| Iframe Proxy | ~1.5s | <1s | Medium | Low |
| Ultra Mode | 5-15s | 5-15s | Very High | Medium |
| VPN Tunnel | ~2s | ~1s | Medium | Low |
| Stealth Mode | ~3s | ~2s | Medium | Low |

### Optimization tips:

1. **Caching** - Add Redis/Memcached for resource cache
2. **CDN** - Serve inlined resources from CDN
3. **Compression** - Enable gzip for HTML/CSS/JS
4. **Async fetching** - Use aiohttp for faster parallel requests
5. **Rate limiting** - Prevent abuse and server overload

---

## 🛠️ Extending the Proxy

### Add a new mode:

1. Create route in `master_proxy.py`:
```python
@app.route('/mymode/<path:path>')
def my_mode(path=''):
    # Your logic here
    return Response(content, mimetype='text/html')
```

2. Add to homepage mode selector
3. Add logging with `log_request('mymode', method, url, status)`

### Add caching:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def fetch_resource_cached(url):
    return fetch_resource(url)
```

### Add authentication:

```python
from flask import request, abort

@app.before_request
def check_auth():
    token = request.headers.get('Authorization')
    if token != 'Bearer YOUR_SECRET_TOKEN':
        abort(401)
```

---

## 📚 Related Files

- `flixhq_proxy.py` - Original FlixHQ streaming proxy
- `vpn_tunnel.py` - Original VPN tunnel implementation
- `ultra_proxy.py` - Original ultra-embed proxy
- `nuclear_proxy.py` - Image-embedding proxy
- `stealth_proxy.py` - JSON-disguise proxy
- `master_proxy.py` - **This consolidated proxy (use this!)**

---

## 🎓 How It Works (Technical Deep Dive)

### Problem: Device-level filtering

Lightspeed Filter Agent and similar tools:
1. Install as Chrome extension or system service
2. Intercept ALL requests before they leave browser
3. Perform SSL decryption (man-in-the-middle)
4. Block based on: domain, content-type, URL patterns, content inspection
5. Cannot be disabled by user (admin-enforced)

### Solution: Proxy strategies

#### Strategy 1: Domain hiding (FlixHQ, Video Proxy, Iframe Proxy)
- Browser requests: `your-server.com/video-proxy?url=blocked-site.com/video.mp4`
- Filter sees: request to `your-server.com` (allowed)
- Filter does NOT see: `blocked-site.com` (hidden in query parameter)
- Server fetches from `blocked-site.com` and streams to browser
- **Result:** Domain blocking bypassed ✅

#### Strategy 2: Resource inlining (Ultra Mode, Nuclear Proxy)
- Server fetches ALL external resources (images, CSS, JS, fonts)
- Server converts to data URIs: `data:image/png;base64,iVBORw0KG...`
- Server inlines into HTML
- Browser receives: ONE file with everything embedded
- Browser makes: ZERO external requests
- **Result:** No external requests to block ✅

#### Strategy 3: Content disguise (Stealth Mode)
- Images requested as: `/api/resource/abc123` (looks like API)
- Server returns: JSON with base64 data, MIME type: `text/plain`
- Filter sees: text API call (not image file)
- JavaScript decodes base64 and creates blob URL
- **Result:** Content-type filtering bypassed ✅ (partially)

#### Strategy 4: Encrypted tunnel (VPN Tunnel)
- Browser ↔ Server: encrypted WebSocket connection
- ALL requests routed through tunnel
- Filter sees: WebSocket frames (encrypted data)
- Filter does NOT see: destination URLs (encrypted)
- Server performs actual HTTP requests
- **Result:** Complete destination hiding ✅

---

## 🚦 Next Steps

### Immediate improvements:

1. **HLS manifest rewriting** - Rewrite .m3u8 playlist URLs to proxy chunks
2. **Certificate error handling** - Trust problematic hosts server-side
3. **Rate limiting** - Prevent abuse with Flask-Limiter
4. **Authentication** - Add token-based auth for shared instances
5. **Caching** - Cache fetched resources with Redis

### Advanced features:

1. **Ad blocking** - Integrate uBlock Origin filters
2. **JavaScript execution** - Use Playwright/Puppeteer for dynamic sites
3. **CAPTCHA solving** - Integrate 2captcha/Anti-Captcha
4. **Multi-region** - Deploy proxies in multiple regions for geo-blocking
5. **Browser extension** - Build Chrome extension for easier access

### Production deployment:

1. **WSGI server** - Use Gunicorn or uWSGI instead of Flask dev server
2. **Reverse proxy** - Put behind Nginx for SSL termination and caching
3. **Docker** - Containerize for easy deployment
4. **Load balancing** - Multiple instances behind load balancer
5. **Monitoring** - Add Prometheus metrics and Grafana dashboards

---

## 📝 Changelog

### v1.0 (Current)
- Initial release combining 6 proxy modes
- FlixHQ streaming with aggressive interception
- Video proxy with chunked streaming
- Iframe proxy with recursive proxying
- Ultra mode with complete inlining
- VPN tunnel with WebSocket encryption
- Stealth mode with JSON disguise
- Clean logging and CORS support

---

## 📄 License

Educational use only. No warranty provided. Use responsibly and respect all applicable laws and policies.

---

## 🙏 Acknowledgments

Built through iterative testing and refinement of multiple bypass strategies. Combines lessons learned from:
- FlixHQ Proxy (aggressive interception)
- VPN Tunnel (encrypted routing)
- Ultra Proxy (complete inlining)
- Nuclear Proxy (image embedding)
- Stealth Proxy (content disguise)

---

**Made with ☕ and determination to understand web filtering systems**
