import requests
import base64
import re
from flask import Flask, Response
from urllib.parse import urljoin
import concurrent.futures

app = Flask(__name__)

TARGET_URL = "https://www.netflix.com/"

def fetch_and_encode_resource(url, resource_type='image'):
    """Fetch a resource and convert to base64 data URI or inline content"""
    try:
        print(f"[FETCH] {url}")
        resp = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if resp.status_code == 200:
            # Detect content type
            content_type = resp.headers.get('content-type', '').split(';')[0]
            if not content_type:
                # Guess from extension
                if url.endswith('.jpg') or url.endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif url.endswith('.png'):
                    content_type = 'image/png'
                elif url.endswith('.gif'):
                    content_type = 'image/gif'
                elif url.endswith('.webp'):
                    content_type = 'image/webp'
                elif url.endswith('.woff2'):
                    content_type = 'font/woff2'
                elif url.endswith('.woff'):
                    content_type = 'font/woff'
                elif url.endswith('.ttf'):
                    content_type = 'font/ttf'
                elif url.endswith('.js'):
                    content_type = 'application/javascript'
                elif url.endswith('.css'):
                    content_type = 'text/css'
                else:
                    content_type = 'application/octet-stream'
            
            # For JavaScript and CSS, return raw content to inline
            if resource_type in ['js', 'css']:
                print(f"[INLINE] {url} -> {len(resp.text)} chars")
                return resp.text
            
            # For everything else, encode as base64
            encoded = base64.b64encode(resp.content).decode('utf-8')
            data_uri = f"data:{content_type};base64,{encoded}"
            print(f"[EMBED] {url} -> {len(data_uri)} chars")
            return data_uri
        else:
            print(f"[FAIL] {url} -> {resp.status_code}")
            return None
    except Exception as e:
        print(f"[ERROR] {url} -> {e}")
        return None

@app.route('/')
def index():
    return proxy_page('/')

@app.route('/<path:path>')
def proxy_page(path=''):
    """Fetch Netflix page and embed ALL images as data URIs server-side"""
    
    target_url = urljoin(TARGET_URL, path)
    
    print(f"\n[PROXY] Fetching page: {target_url}")
    
    try:
        resp = requests.get(
            target_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=15,
            allow_redirects=True
        )
        
        if 'text/html' not in resp.headers.get('Content-Type', ''):
            return Response(resp.content, mimetype=resp.headers.get('Content-Type'))
        
        html = resp.text
        
        # Find all image URLs
        img_urls = set()
        
        # Match src="..." and srcset="..."
        for match in re.finditer(r'(?:src|srcset)=["\']([^"\']+)["\']', html, re.IGNORECASE):
            url = match.group(1)
            
            # Handle srcset (multiple URLs)
            if ',' in url and 'w' in url:
                for part in url.split(','):
                    img_url = part.strip().split()[0]
                    if img_url.startswith('http') or img_url.startswith('//'):
                        img_urls.add(img_url)
            else:
                if url.startswith('http') or url.startswith('//'):
                    img_urls.add(url)
        
        print(f"[PROXY] Found {len(img_urls)} image URLs to embed")
        
        # Fetch and embed images in parallel (faster)
        url_to_data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(fetch_and_encode_resource, 
                            'https:' + url if url.startswith('//') else url): url 
                            for url in img_urls}
            
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    data_uri = future.result()
                    if data_uri:
                        url_to_data[url] = data_uri
                except Exception as e:
                    print(f"[EMBED] Error for {url}: {e}")
        
        print(f"[PROXY] Successfully embedded {len(url_to_data)} images")
        
        # Replace all image URLs with data URIs
        for url, data_uri in url_to_data.items():
            html = html.replace(url, data_uri)
            # Also replace with https: prefix
            if url.startswith('//'):
                html = html.replace('https:' + url, data_uri)
        
        # Find and inline external JavaScript files
        print("[PROXY] Inlining external JavaScript files...")
        js_pattern = r'<script[^>]*src=["\']([^"\']+\.js[^"\']*)["\'][^>]*></script>'
        js_matches = re.findall(js_pattern, html)
        
        for js_url in js_matches:
            if any(domain in js_url for domain in ['nflximg.net', 'nflxext.com', 'nflxvideo.net', 'netflix.com']):
                full_url = js_url if js_url.startswith('http') else ('https:' + js_url if js_url.startswith('//') else urljoin(TARGET_URL, js_url))
                js_content = fetch_and_encode_resource(full_url, 'js')
                if js_content:
                    # Replace script tag with inline version
                    old_tag = f'<script src="{js_url}"'
                    new_script = f'<script data-original="{js_url}">{js_content}</script>'
                    html = html.replace(f'{old_tag}></script>', new_script)
                    print(f"[INLINE] Inlined JS: {js_url}")
        
        # Find and inline external CSS files
        print("[PROXY] Inlining external CSS files...")
        css_pattern = r'<link[^>]*href=["\']([^"\']+\.css[^"\']*)["\'][^>]*>'
        css_matches = re.findall(css_pattern, html)
        
        for css_url in css_matches:
            if any(domain in css_url for domain in ['nflximg.net', 'nflxext.com', 'nflxvideo.net', 'netflix.com']):
                full_url = css_url if css_url.startswith('http') else ('https:' + css_url if css_url.startswith('//') else urljoin(TARGET_URL, css_url))
                css_content = fetch_and_encode_resource(full_url, 'css')
                if css_content:
                    # Find and embed fonts in CSS
                    font_pattern = r'url\(["\']?([^"\')\s]+\.(?:woff2|woff|ttf))["\']?\)'
                    font_urls = re.findall(font_pattern, css_content)
                    for font_url in font_urls:
                        font_full_url = font_url if font_url.startswith('http') else ('https:' + font_url if font_url.startswith('//') else urljoin(full_url, font_url))
                        font_data = fetch_and_encode_resource(font_full_url, 'font')
                        if font_data:
                            css_content = css_content.replace(font_url, font_data)
                            print(f"[INLINE] Embedded font in CSS: {font_url}")
                    
                    # Replace link tag with style tag
                    link_tag_pattern = f'<link[^>]*href=["\']' + re.escape(css_url) + '["\'][^>]*>'
                    new_style = f'<style data-original="{css_url}">{css_content}</style>'
                    html = re.sub(link_tag_pattern, new_style, html)
                    print(f"[INLINE] Inlined CSS: {css_url}")
        
        # Inject JavaScript to intercept dynamic resource loading
        interceptor = '''
<script>
(function() {
    console.log('[NUCLEAR] Intercepting all fetch/XHR requests...');
    
    // Intercept fetch API
    const originalFetch = window.fetch;
    window.fetch = async function(url, options) {
        const urlStr = typeof url === 'string' ? url : (url ? url.toString() : '');
        
        // Block images, fonts, analytics, logging
        if (urlStr.includes('image') || urlStr.includes('.jpg') || urlStr.includes('.png') || 
            urlStr.includes('.webp') || urlStr.includes('.gif') || urlStr.includes('.woff') ||
            urlStr.includes('logs.netflix.com') || urlStr.includes('analytics') || 
            urlStr.includes('.woff2') || urlStr.includes('.ttf')) {
            console.log('[NUCLEAR] Blocking fetch to:', urlStr);
            return new Response(null, { status: 200 });
        }
        return originalFetch.apply(this, arguments);
    };
    
    // Intercept XMLHttpRequest
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        const urlStr = typeof url === 'string' ? url : (url ? url.toString() : '');
        
        if (urlStr.includes('image') || urlStr.includes('.jpg') || urlStr.includes('.png') || 
            urlStr.includes('.webp') || urlStr.includes('.gif') || urlStr.includes('.woff') ||
            urlStr.includes('logs.netflix.com') || urlStr.includes('analytics') ||
            urlStr.includes('.woff2') || urlStr.includes('.ttf')) {
            console.log('[NUCLEAR] Blocking XHR to:', urlStr);
            this._blocked = true;
        }
        return originalOpen.apply(this, arguments);
    };
    
    const originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function() {
        if (this._blocked) {
            return;
        }
        return originalSend.apply(this, arguments);
    };
    
    // Block dynamic Image() loading
    const OriginalImage = window.Image;
    window.Image = function() {
        const img = new OriginalImage();
        const originalSrcSet = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src').set;
        Object.defineProperty(img, 'src', {
            set: function(value) {
                if (value && !value.startsWith('data:')) {
                    console.log('[NUCLEAR] Blocking dynamic Image src:', value);
                    return;
                }
                originalSrcSet.call(this, value);
            }
        });
        return img;
    };
    
    console.log('[NUCLEAR] Interception active!');
})();
</script>
'''
        
        # Add banner
        banner = '''
<div style="position:fixed;top:0;left:0;right:0;background:#0a0;color:#fff;padding:15px;z-index:999999;text-align:center;font-family:monospace;">
    ✅ ULTRA-STEALTH MODE: All images embedded as base64 data URIs directly in HTML!<br>
    Zero external requests for images - everything is inline. Filter sees: just HTML text.
</div>
<div style="height:70px;"></div>
'''
        html = html.replace('<head>', '<head>' + interceptor, 1)
        html = html.replace('<body', banner + '<body', 1)
        
        return Response(html, mimetype='text/html')
        
    except Exception as e:
        print(f"[PROXY] Error: {e}")
        return f"<h1>Error</h1><p>{e}</p>", 500

if __name__ == '__main__':
    print("\n" + "="*70)
    print("ULTRA-STEALTH PROXY - ALL images embedded inline")
    print("="*70)
    print("\nStrategy: NUCLEAR OPTION")
    print("  • Fetch ALL images server-side")
    print("  • Convert to base64 data URIs")
    print("  • Embed directly in HTML")
    print("  • Zero external image requests")
    print("  • Filter sees: Single HTML document with text data")
    print("\n⚠️  First load will be SLOW (downloading all images)")
    print("="*70 + "\n")
    print("Starting server on port 5000...\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
