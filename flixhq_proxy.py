#!/usr/bin/env python3
"""
FlixHQ Streaming Proxy - Full video streaming support
Proxies both page content AND video streams
"""
from flask import Flask, Response, request, stream_with_context
import requests
import re
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

app = Flask(__name__)

TARGET_URL = "https://flixhq.to/"

def rewrite_urls(content, base_url):
    """Rewrite all URLs to go through our proxy"""
    
    # Replace absolute URLs
    content = re.sub(
        r'https?://(?:www\.)?flixhq\.to',
        request.host_url.rstrip('/'),
        content
    )
    
    # Replace protocol-relative URLs
    content = re.sub(
        r'//(?:www\.)?flixhq\.to',
        '//' + request.host.rstrip('/'),
        content
    )
    
    return content

@app.route('/iframe-proxy')
def iframe_proxy():
    """Proxy embedded iframes - handles video player embeds"""
    iframe_url = request.args.get('url')
    
    if not iframe_url:
        return "No iframe URL provided", 400
    
    print(f"\n{'='*70}")
    print(f"[IFRAME PROXY] Loading embedded iframe")
    print(f"[IFRAME PROXY] URL: {iframe_url}")
    print(f"{'='*70}\n")
    
    try:
        # Fetch the iframe content
        resp = requests.get(
            iframe_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': TARGET_URL,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            },
            timeout=15
        )
        
        content_type = resp.headers.get('Content-Type', '')
        
        # If it's HTML, rewrite it to proxy through us
        if 'text/html' in content_type:
            html = resp.text
            
            # Rewrite URLs in the iframe to go through our proxy
            html = rewrite_urls(html, iframe_url)
            
            # Inject the same interceptor
            interceptor = '''
<script>
console.log('[IFRAME] Proxy interceptor active in embedded frame');
if (window.HTMLMediaElement) {
    const originalSrc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src').set;
    Object.defineProperty(HTMLMediaElement.prototype, 'src', {
        set: function(value) {
            if (value && !value.startsWith('blob:') && !value.includes(location.host)) {
                console.log('[IFRAME] Proxying video in frame:', value);
                value = parent.location.origin + '/video-proxy?url=' + encodeURIComponent(value);
            }
            originalSrc.call(this, value);
        }
    });
}
</script>
'''
            html = html.replace('</head>', interceptor + '</head>', 1) if '</head>' in html else interceptor + html
            
            print(f"[IFRAME PROXY] ✓ Proxied iframe HTML ({len(html)} bytes)")
            return Response(html, content_type='text/html', headers={
                'Access-Control-Allow-Origin': '*',
                'X-Frame-Options': 'ALLOWALL'
            })
        
        # For non-HTML, just pass through
        else:
            print(f"[IFRAME PROXY] ✓ Passing through {content_type}")
            return Response(resp.content, content_type=content_type, headers={
                'Access-Control-Allow-Origin': '*'
            })
        
    except Exception as e:
        print(f"[IFRAME PROXY] ❌ Error: {e}")
        return f"Iframe proxy error: {e}", 500

@app.route('/video-proxy')
def video_proxy():
    """Proxy video streams - handles MP4, M3U8, etc."""
    video_url = request.args.get('url')
    
    if not video_url:
        return "No video URL provided", 400
    
    print(f"\n{'='*70}")
    print(f"[VIDEO PROXY] Attempting to stream video")
    print(f"[VIDEO PROXY] URL: {video_url}")
    print(f"{'='*70}\n")
    
    try:
        # Stream the video
        resp = requests.get(
            video_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://flixhq.to/',
                'Origin': 'https://flixhq.to'
            },
            stream=True,
            timeout=30
        )
        
        # Get content type
        content_type = resp.headers.get('Content-Type', 'video/mp4')
        
        print(f"[VIDEO PROXY] ✓ Streaming {content_type} - Status: {resp.status_code}")
        
        # Stream response
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
        print(f"[VIDEO PROXY] ❌ Error: {e}")
        return f"Video proxy error: {e}", 500

@app.route('/')
@app.route('/<path:path>')
def proxy_page(path=''):
    """Proxy FlixHQ pages"""
    
    # Build target URL
    if path:
        target_url = urljoin(TARGET_URL, path)
    else:
        target_url = TARGET_URL
    
    # Add query parameters
    if request.query_string:
        target_url += '?' + request.query_string.decode()
    
    print(f"\n[PROXY] {request.method} {target_url}")
    
    try:
        # Forward the request
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': request.headers.get('Accept', '*/*'),
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://flixhq.to/'
            },
            data=request.get_data(),
            allow_redirects=True,
            timeout=15
        )
        
        content_type = resp.headers.get('Content-Type', '')
        
        # Handle HTML pages
        if 'text/html' in content_type:
            html = resp.text
            
            # Rewrite URLs to go through proxy
            html = rewrite_urls(html, target_url)
            
            # Inject video proxy interceptor
            interceptor = '''
<script>
(function() {
    console.log('[FlixHQ Proxy] AGGRESSIVE MODE - Intercepting EVERYTHING...');
    
    // Intercept ALL iframe sources
    const iframeObserver = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.tagName === 'IFRAME') {
                    const originalSrc = node.src;
                    if (originalSrc && !originalSrc.includes(location.host)) {
                        console.log('[FlixHQ Proxy] Proxying iframe:', originalSrc);
                        node.src = '/iframe-proxy?url=' + encodeURIComponent(originalSrc);
                    }
                }
            });
        });
    });
    iframeObserver.observe(document.body, { childList: true, subtree: true });
    
    // Override iframe.src setter
    const originalIframeSrcSetter = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'src').set;
    Object.defineProperty(HTMLIFrameElement.prototype, 'src', {
        set: function(value) {
            if (value && !value.includes(location.host) && !value.startsWith('about:') && !value.startsWith('blob:')) {
                console.log('[FlixHQ Proxy] Intercepted iframe.src:', value);
                value = '/iframe-proxy?url=' + encodeURIComponent(value);
            }
            originalIframeSrcSetter.call(this, value);
        }
    });
    
    // Intercept video.src assignments
    const originalVideoSrcSetter = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src').set;
    Object.defineProperty(HTMLMediaElement.prototype, 'src', {
        set: function(value) {
            if (value && !value.startsWith('blob:') && !value.includes(location.host)) {
                console.log('[FlixHQ Proxy] Proxying video:', value);
                value = '/video-proxy?url=' + encodeURIComponent(value);
            }
            originalVideoSrcSetter.call(this, value);
        }
    });
    
    // Intercept fetch for video URLs
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {
        if (typeof url === 'string' && (url.includes('.m3u8') || url.includes('.mp4') || url.includes('.ts'))) {
            console.log('[FlixHQ Proxy] Proxying fetch:', url);
            url = '/video-proxy?url=' + encodeURIComponent(url);
        }
        return originalFetch.call(this, url, options);
    };
    
    console.log('[FlixHQ Proxy] AGGRESSIVE MODE ACTIVE!');
})();
</script>
'''
            html = html.replace('</head>', interceptor + '</head>', 1)
            
            # Add status banner
            banner = '''
<div style="position:fixed;bottom:0;left:0;right:0;background:linear-gradient(135deg,#10b981,#059669);color:#fff;padding:8px 15px;z-index:999999;text-align:center;font-size:12px;font-family:monospace;">
    🎬 FlixHQ Streaming Proxy Active - Videos streaming through GitHub Codespaces
</div>
'''
            html = html.replace('</body>', banner + '</body>', 1)
            
            print(f"[PROXY] ✓ Served HTML ({len(html)} bytes)")
            
            return Response(html, content_type='text/html')
        
        # Handle CSS
        elif 'text/css' in content_type:
            css = resp.text
            css = rewrite_urls(css, target_url)
            return Response(css, content_type='text/css')
        
        # Handle JavaScript
        elif 'javascript' in content_type or 'application/json' in content_type:
            js = resp.text
            
            # Log if this is a video source response
            if 'sources' in target_url or 'episode' in target_url:
                print(f"[DEBUG] Video source response: {js[:500]}")
            
            js = rewrite_urls(js, target_url)
            return Response(js, content_type=content_type)
        
        # Handle everything else (images, fonts, etc.)
        else:
            return Response(
                resp.content,
                content_type=content_type,
                headers={'Access-Control-Allow-Origin': '*'}
            )
        
    except Exception as e:
        print(f"[PROXY] Error: {e}")
        return f"<h1>Proxy Error</h1><p>{e}</p>", 500

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🎬 FlixHQ STREAMING PROXY")
    print("="*70)
    print("\nFeatures:")
    print("  ✓ Full page proxying with URL rewriting")
    print("  ✓ Video streaming support (MP4, M3U8, HLS)")
    print("  ✓ Intercepts and proxies all video URLs")
    print("  ✓ No DRM - works with free streaming sites")
    print("  ✓ Streams through GitHub Codespaces")
    print("\nTarget: FlixHQ.to")
    print("="*70 + "\n")
    print("Starting server on port 5000...\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
