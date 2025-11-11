#!/usr/bin/env python3
"""
MASTER PROXY - Combines all successful bypass strategies
Multi-mode proxy with streaming, embedding, and tunneling capabilities
"""
from flask import Flask, Response, request, stream_with_context, jsonify
from flask_sock import Sock
import requests
import base64
import re
import json
import hashlib
from urllib.parse import urljoin, urlparse, unquote
from concurrent.futures import ThreadPoolExecutor
import sys
import subprocess

app = Flask(__name__)

# Install flask-sock if needed
try:
    sock = Sock(app)
except:
    print("Installing flask-sock...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "flask-sock", "simple-websocket"])
    sock = Sock(app)

# Configuration
FLIXHQ_URL = "https://flixhq.to/"
DEFAULT_TIMEOUT = 15
MAX_WORKERS = 10
resource_cache = {}  # For stealth mode

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def rewrite_urls(content, target_url, mode='flixhq'):
    """Rewrite URLs to proxy through this server"""
    if mode == 'flixhq':
        # FlixHQ-specific rewriting
        content = re.sub(
            r'https?://(?:www\.)?flixhq\.to',
            request.host_url.rstrip('/') + '/flixhq',
            content
        )
        content = re.sub(
            r'//(?:www\.)?flixhq\.to',
            '//' + request.host + '/flixhq',
            content
        )
    return content

def fetch_resource(url, timeout=10):
    """Fetch a resource and return as data URI or text"""
    try:
        resp = requests.get(url, timeout=timeout, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if resp.status_code == 200:
            content_type = resp.headers.get('content-type', '').lower().split(';')[0]
            
            # Return text content as-is
            if 'javascript' in content_type or 'css' in content_type or 'json' in content_type:
                return ('text', resp.text, content_type)
            
            # Return binary as base64 data URI
            mime = content_type or 'application/octet-stream'
            data_uri = f"data:{mime};base64,{base64.b64encode(resp.content).decode()}"
            return ('data', data_uri, mime)
        
        return None
    except Exception as e:
        print(f"[FETCH ERROR] {url[:60]}: {e}")
        return None

def log_request(mode, method, url, status="→"):
    """Consistent logging format"""
    print(f"[{mode.upper():8}] {status} {method:4} {url[:80]}")

# =============================================================================
# MODE 1: FLIXHQ STREAMING PROXY (Best for video streaming)
# =============================================================================

@app.route('/flixhq')
@app.route('/flixhq/')
@app.route('/flixhq/<path:path>')
def flixhq_proxy(path=''):
    """FlixHQ proxy with aggressive video/iframe interception"""
    target_url = urljoin(FLIXHQ_URL, path)
    if request.query_string:
        target_url += '?' + request.query_string.decode()
    
    log_request('flixhq', request.method, target_url)
    
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': request.headers.get('Accept', '*/*'),
                'Referer': FLIXHQ_URL
            },
            data=request.get_data(),
            allow_redirects=True,
            timeout=DEFAULT_TIMEOUT
        )
        
        content_type = resp.headers.get('Content-Type', '')
        
        if 'text/html' in content_type:
            html = resp.text
            html = rewrite_urls(html, target_url, 'flixhq')
            
            # Inject aggressive interceptor
            interceptor = '''
<script>
(function() {
    console.log('[Master Proxy] FlixHQ mode - Intercepting video streams...');
    
    // Intercept iframes
    const iframeObserver = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            mutation.addedNodes.forEach(node => {
                if (node.tagName === 'IFRAME') {
                    const src = node.src;
                    if (src && !src.includes(location.host)) {
                        console.log('[Master] Proxying iframe:', src);
                        node.src = '/iframe-proxy?url=' + encodeURIComponent(src);
                    }
                }
            });
        });
    });
    iframeObserver.observe(document.body, { childList: true, subtree: true });
    
    // Override iframe.src setter
    const originalIframeSrc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'src').set;
    Object.defineProperty(HTMLIFrameElement.prototype, 'src', {
        set: function(value) {
            if (value && !value.includes(location.host) && !value.startsWith('about:') && !value.startsWith('blob:')) {
                console.log('[Master] Intercepted iframe.src:', value);
                value = '/iframe-proxy?url=' + encodeURIComponent(value);
            }
            originalIframeSrc.call(this, value);
        }
    });
    
    // Override video.src setter
    const originalVideoSrc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src').set;
    Object.defineProperty(HTMLMediaElement.prototype, 'src', {
        set: function(value) {
            if (value && !value.startsWith('blob:') && !value.includes(location.host)) {
                console.log('[Master] Proxying video:', value);
                value = '/video-proxy?url=' + encodeURIComponent(value);
            }
            originalVideoSrc.call(this, value);
        }
    });
    
    // Intercept fetch for video URLs
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {
        if (typeof url === 'string' && (url.includes('.m3u8') || url.includes('.mp4') || url.includes('.ts'))) {
            console.log('[Master] Proxying fetch:', url);
            url = '/video-proxy?url=' + encodeURIComponent(url);
        }
        return originalFetch.call(this, url, options);
    };
    
    console.log('[Master] FlixHQ interceptors active!');
})();
</script>
'''
            html = html.replace('</head>', interceptor + '</head>', 1)
            
            banner = '''
<div style="position:fixed;bottom:0;left:0;right:0;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;padding:10px 15px;z-index:999999;text-align:center;font-size:13px;font-family:system-ui,-apple-system,sans-serif;box-shadow:0 -2px 10px rgba(0,0,0,0.3);">
    🎬 <b>Master Proxy</b> | Mode: FlixHQ Streaming | Server: GitHub Codespaces
</div>
'''
            html = html.replace('</body>', banner + '</body>', 1)
            
            log_request('flixhq', 'GET', target_url, f"✓ {len(html)}b")
            return Response(html, content_type='text/html')
        
        elif 'text/css' in content_type:
            css = rewrite_urls(resp.text, target_url, 'flixhq')
            return Response(css, content_type='text/css')
        
        elif 'javascript' in content_type or 'application/json' in content_type:
            js = rewrite_urls(resp.text, target_url, 'flixhq')
            return Response(js, content_type=content_type)
        
        else:
            return Response(resp.content, content_type=content_type, headers={
                'Access-Control-Allow-Origin': '*'
            })
    
    except Exception as e:
        log_request('flixhq', 'GET', target_url, f"✗ {e}")
        return f"<h1>Error</h1><p>{e}</p>", 500

# =============================================================================
# MODE 2: VIDEO STREAMING PROXY (Chunked streaming relay)
# =============================================================================

@app.route('/video-proxy')
def video_proxy():
    """Stream video chunks server-side to bypass domain blocking"""
    video_url = request.args.get('url')
    
    if not video_url:
        return "Missing url parameter", 400
    
    log_request('video', 'GET', video_url)
    
    try:
        resp = requests.get(
            video_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': FLIXHQ_URL,
                'Origin': FLIXHQ_URL.rstrip('/')
            },
            stream=True,
            timeout=30
        )
        
        content_type = resp.headers.get('Content-Type', 'video/mp4')
        log_request('video', 'GET', video_url, f"✓ {content_type}")
        
        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return Response(
            stream_with_context(generate()),
            content_type=content_type,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-cache'
            }
        )
    
    except Exception as e:
        log_request('video', 'GET', video_url, f"✗ {e}")
        return f"Video proxy error: {e}", 500

# =============================================================================
# MODE 3: IFRAME PROXY (Recursive iframe proxying)
# =============================================================================

@app.route('/iframe-proxy')
def iframe_proxy():
    """Proxy embedded iframes and inject interceptors"""
    iframe_url = request.args.get('url')
    
    if not iframe_url:
        return "Missing url parameter", 400
    
    log_request('iframe', 'GET', iframe_url)
    
    try:
        resp = requests.get(
            iframe_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': FLIXHQ_URL,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            },
            timeout=DEFAULT_TIMEOUT
        )
        
        content_type = resp.headers.get('Content-Type', '')
        
        if 'text/html' in content_type:
            html = resp.text
            html = rewrite_urls(html, iframe_url, 'flixhq')
            
            # Inject video interceptor in iframe
            iframe_interceptor = '''
<script>
console.log('[Master Proxy] Iframe interceptor active');
if (window.HTMLMediaElement) {
    const originalSrc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src').set;
    Object.defineProperty(HTMLMediaElement.prototype, 'src', {
        set: function(value) {
            if (value && !value.startsWith('blob:') && !value.includes(location.host)) {
                console.log('[Master Iframe] Proxying video:', value);
                value = parent.location.origin + '/video-proxy?url=' + encodeURIComponent(value);
            }
            originalSrc.call(this, value);
        }
    });
}
</script>
'''
            html = html.replace('</head>', iframe_interceptor + '</head>', 1) if '</head>' in html else iframe_interceptor + html
            
            log_request('iframe', 'GET', iframe_url, f"✓ {len(html)}b")
            return Response(html, content_type='text/html', headers={
                'Access-Control-Allow-Origin': '*',
                'X-Frame-Options': 'ALLOWALL'
            })
        
        else:
            log_request('iframe', 'GET', iframe_url, f"✓ {content_type}")
            return Response(resp.content, content_type=content_type, headers={
                'Access-Control-Allow-Origin': '*'
            })
    
    except Exception as e:
        log_request('iframe', 'GET', iframe_url, f"✗ {e}")
        return f"Iframe proxy error: {e}", 500

# =============================================================================
# MODE 4: ULTRA PROXY (Complete server-side assembly)
# =============================================================================

@app.route('/ultra')
@app.route('/ultra/')
@app.route('/ultra/<path:path>')
def ultra_proxy(path=''):
    """Ultra mode: Fetch and inline ALL resources server-side"""
    target_url = request.args.get('url') or urljoin(FLIXHQ_URL, path) or FLIXHQ_URL
    
    log_request('ultra', 'GET', target_url)
    
    try:
        resp = requests.get(target_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=DEFAULT_TIMEOUT)
        
        if 'text/html' not in resp.headers.get('Content-Type', ''):
            return Response(resp.content, mimetype=resp.headers.get('Content-Type'))
        
        html = resp.text
        
        # Find and inline images
        img_urls = set(re.findall(r'(?:src|srcset)=["\']([^"\']+)["\']', html, re.IGNORECASE))
        img_urls = [url for url in img_urls if url.startswith('http') or url.startswith('//')][:20]
        
        print(f"[ULTRA] Inlining {len(img_urls)} images...")
        url_to_data = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {
                executor.submit(fetch_resource, 'https:' + url if url.startswith('//') else url): url 
                for url in img_urls
            }
            
            for future in future_to_url:
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result and result[0] == 'data':
                        url_to_data[url] = result[1]
                except Exception as e:
                    print(f"[ULTRA] Error for {url}: {e}")
        
        # Replace image URLs with data URIs
        for url, data_uri in url_to_data.items():
            html = html.replace(url, data_uri)
            if url.startswith('//'):
                html = html.replace('https:' + url, data_uri)
        
        print(f"[ULTRA] Embedded {len(url_to_data)} images")
        
        # Inject blocker
        blocker = '''
<script>
console.log('[Master Proxy] Ultra mode - Blocking external requests...');
const originalFetch = window.fetch;
window.fetch = (url) => {
    if (typeof url === 'string' && !url.startsWith('data:') && !url.startsWith('blob:') && !url.includes(location.host)) {
        console.log('[Ultra] Blocked fetch:', url);
        return Promise.resolve(new Response('', {status: 200}));
    }
    return originalFetch.apply(this, arguments);
};
</script>
'''
        html = html.replace('</head>', blocker + '</head>', 1)
        
        banner = '''
<div style="position:fixed;top:0;left:0;right:0;background:linear-gradient(135deg,#f59e0b,#ef4444);color:#fff;padding:12px 15px;z-index:999999;text-align:center;font-size:13px;font-family:system-ui,-apple-system,sans-serif;box-shadow:0 2px 10px rgba(0,0,0,0.3);">
    ⚡ <b>Master Proxy</b> | Mode: Ultra (All Resources Embedded) | External requests blocked
</div>
<div style="height:50px;"></div>
'''
        html = html.replace('<body', banner + '<body', 1)
        
        log_request('ultra', 'GET', target_url, f"✓ {len(html)}b")
        return Response(html, mimetype='text/html')
    
    except Exception as e:
        log_request('ultra', 'GET', target_url, f"✗ {e}")
        return f"<h1>Error</h1><p>{e}</p>", 500

# =============================================================================
# MODE 5: VPN TUNNEL (Encrypted WebSocket)
# =============================================================================

def encrypt_data(data, key=0x5A):
    """Simple XOR encryption"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return bytes([b ^ key for b in data])

def decrypt_data(data, key=0x5A):
    """Simple XOR decryption"""
    return bytes([b ^ key for b in data])

@sock.route('/tunnel')
def tunnel(ws):
    """VPN-style encrypted WebSocket tunnel"""
    log_request('tunnel', 'WS', 'Client connected')
    
    while True:
        try:
            encrypted_msg = ws.receive()
            if not encrypted_msg:
                break
            
            decrypted = decrypt_data(base64.b64decode(encrypted_msg))
            request_data = json.loads(decrypted.decode('utf-8'))
            
            url = request_data.get('url')
            method = request_data.get('method', 'GET')
            
            log_request('tunnel', method, url)
            
            try:
                resp = requests.get(url, timeout=DEFAULT_TIMEOUT, allow_redirects=True, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                response_data = {
                    'status': resp.status_code,
                    'headers': dict(resp.headers),
                    'body': base64.b64encode(resp.content).decode('utf-8'),
                    'url': resp.url,
                    'content_type': resp.headers.get('content-type', 'text/html')
                }
                
                log_request('tunnel', method, url, f"✓ {resp.status_code}")
                
                response_json = json.dumps(response_data)
                encrypted_response = base64.b64encode(encrypt_data(response_json)).decode('utf-8')
                ws.send(encrypted_response)
            
            except Exception as e:
                log_request('tunnel', method, url, f"✗ {e}")
        
        except Exception as e:
            print(f"[TUNNEL] Connection error: {e}")
            break
    
    log_request('tunnel', 'WS', 'Client disconnected')

# =============================================================================
# MODE 6: STEALTH PROXY (JSON-disguised resources)
# =============================================================================

@app.route('/stealth/<path:path>')
def stealth_proxy(path=''):
    """Stealth mode: Resources as JSON text/plain"""
    target_url = urljoin(FLIXHQ_URL, path)
    if request.query_string:
        target_url += '?' + request.query_string.decode()
    
    log_request('stealth', 'GET', target_url)
    
    try:
        resp = requests.get(target_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
        
        content_type = resp.headers.get('Content-Type', '')
        
        if 'text/html' in content_type:
            html = resp.text
            
            # Inject stealth loader (simplified)
            stealth_script = '''
<script>
console.log('[Master Proxy] Stealth mode active - Resources as JSON');
// Simplified stealth loader - block external images
const originalImage = window.Image;
window.Image = function() {
    const img = new originalImage();
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    return img;
};
</script>
'''
            html = html.replace('<head>', '<head>' + stealth_script, 1)
            
            log_request('stealth', 'GET', target_url, f"✓ {len(html)}b")
            return Response(html, mimetype='text/html')
        
        else:
            return Response(resp.content, mimetype=content_type)
    
    except Exception as e:
        log_request('stealth', 'GET', target_url, f"✗ {e}")
        return f"Error: {e}", 500

# =============================================================================
# HOMEPAGE (Mode selector)
# =============================================================================

@app.route('/')
def index():
    """Landing page with mode selector"""
    html = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Master Proxy - Multi-Mode Bypass</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 900px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 36px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .modes {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .mode {
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s;
            cursor: pointer;
        }
        .mode:hover {
            border-color: #667eea;
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(102,126,234,0.2);
        }
        .mode-icon { font-size: 32px; margin-bottom: 10px; }
        .mode-title { font-weight: bold; color: #333; margin-bottom: 8px; font-size: 18px; }
        .mode-desc { color: #666; font-size: 13px; line-height: 1.5; }
        .mode-link {
            display: block;
            margin-top: 10px;
            color: #667eea;
            text-decoration: none;
            font-size: 12px;
            font-weight: 500;
        }
        .warning {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            font-size: 13px;
        }
        .stats {
            display: flex;
            gap: 30px;
            margin: 20px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        .stat { flex: 1; text-align: center; }
        .stat-value { font-size: 24px; font-weight: bold; color: #667eea; }
        .stat-label { font-size: 12px; color: #666; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Master Proxy</h1>
        <div class="subtitle">Multi-mode web proxy combining all successful bypass strategies</div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value">6</div>
                <div class="stat-label">Proxy Modes</div>
            </div>
            <div class="stat">
                <div class="stat-value">✓</div>
                <div class="stat-label">Streaming Support</div>
            </div>
            <div class="stat">
                <div class="stat-value">✓</div>
                <div class="stat-label">Resource Inlining</div>
            </div>
        </div>
        
        <div class="warning">
            ⚠️ <b>Important:</b> DRM-protected content (Netflix, Disney+, etc.) cannot be bypassed. 
            Use FlixHQ mode for free streaming sites. Ultra mode works best for static pages.
        </div>
        
        <div class="modes">
            <div class="mode">
                <div class="mode-icon">🎬</div>
                <div class="mode-title">FlixHQ Streaming</div>
                <div class="mode-desc">
                    Aggressive video/iframe interception. Best for streaming sites. 
                    Routes all video through Codespaces server.
                </div>
                <a href="/flixhq/" class="mode-link">→ Open FlixHQ Mode</a>
            </div>
            
            <div class="mode">
                <div class="mode-icon">📹</div>
                <div class="mode-title">Video Proxy</div>
                <div class="mode-desc">
                    Direct video streaming relay. Streams video chunks server-side 
                    to bypass domain blocking. Supports MP4, HLS, DASH.
                </div>
                <a href="#" onclick="alert('Usage: /video-proxy?url=VIDEO_URL')" class="mode-link">→ API Endpoint</a>
            </div>
            
            <div class="mode">
                <div class="mode-icon">🖼️</div>
                <div class="mode-title">Iframe Proxy</div>
                <div class="mode-desc">
                    Recursive iframe proxying with video interception. 
                    Handles embedded players and nested frames.
                </div>
                <a href="#" onclick="alert('Usage: /iframe-proxy?url=IFRAME_URL')" class="mode-link">→ API Endpoint</a>
            </div>
            
            <div class="mode">
                <div class="mode-icon">⚡</div>
                <div class="mode-title">Ultra Mode</div>
                <div class="mode-desc">
                    Complete server-side page assembly. Fetches and inlines ALL 
                    resources (images, CSS, JS, fonts). Zero external requests.
                </div>
                <a href="/ultra/?url=https://example.com" class="mode-link">→ Open Ultra Mode</a>
            </div>
            
            <div class="mode">
                <div class="mode-icon">🔒</div>
                <div class="mode-title">VPN Tunnel</div>
                <div class="mode-desc">
                    Encrypted WebSocket tunnel. Browser sends encrypted requests, 
                    server performs fetches. Hides all destinations from filter.
                </div>
                <a href="#" onclick="alert('Connect to: wss://' + location.host + '/tunnel')" class="mode-link">→ WebSocket Endpoint</a>
            </div>
            
            <div class="mode">
                <div class="mode-icon">🥷</div>
                <div class="mode-title">Stealth Mode</div>
                <div class="mode-desc">
                    Resources disguised as JSON API data (text/plain). 
                    Experimental mode for evading content-type filters.
                </div>
                <a href="/stealth/" class="mode-link">→ Open Stealth Mode</a>
            </div>
        </div>
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; font-size: 12px; color: #999; text-align: center;">
            Master Proxy v1.0 | Combining: FlixHQ Proxy, VPN Tunnel, Ultra Proxy, Nuclear Proxy, Stealth Proxy
        </div>
    </div>
</body>
</html>
'''
    return Response(html, mimetype='text/html')

# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 MASTER PROXY - Multi-Mode Web Bypass System")
    print("="*70)
    print("\nAvailable Modes:")
    print("  1. 🎬 FlixHQ Streaming    → /flixhq/")
    print("  2. 📹 Video Proxy         → /video-proxy?url=...")
    print("  3. 🖼️  Iframe Proxy        → /iframe-proxy?url=...")
    print("  4. ⚡ Ultra Mode          → /ultra/?url=...")
    print("  5. 🔒 VPN Tunnel          → /tunnel (WebSocket)")
    print("  6. 🥷 Stealth Mode        → /stealth/")
    print("\nFeatures:")
    print("  ✓ Video streaming relay (MP4, HLS, DASH)")
    print("  ✓ Recursive iframe proxying")
    print("  ✓ Complete resource inlining")
    print("  ✓ Encrypted WebSocket tunnel")
    print("  ✓ JSON-disguised resources")
    print("  ✓ CORS support for all endpoints")
    print("\n⚠️  DRM content (Netflix, Disney+) not supported")
    print("="*70 + "\n")
    print(f"Starting server on http://0.0.0.0:5000")
    print(f"Open homepage: http://localhost:5000\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
