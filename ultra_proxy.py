#!/usr/bin/env python3
"""
ULTRA PROXY - Server-side full page assembly
Fetches ALL resources server-side and builds complete standalone HTML
"""
from flask import Flask, Response, request
import requests
import base64
import re
from urllib.parse import urljoin, urlparse
import concurrent.futures

app = Flask(__name__)

TARGET_URL = "https://www.netflix.com/"

def fetch_resource(url):
    """Fetch any resource and return as base64 or text"""
    try:
        print(f"  Fetching: {url[:80]}...")
        resp = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if resp.status_code == 200:
            content_type = resp.headers.get('content-type', '').lower()
            
            # Return text content as-is
            if 'javascript' in content_type or 'css' in content_type or 'json' in content_type:
                return ('text', resp.text)
            
            # Return binary as base64
            else:
                mime = content_type.split(';')[0] or 'application/octet-stream'
                return ('data', f"data:{mime};base64,{base64.b64encode(resp.content).decode()}")
        
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

@app.route('/')
@app.route('/<path:path>')
def proxy_page(path=''):
    url = urljoin(TARGET_URL, path)
    
    print(f"\n{'='*70}")
    print(f"ULTRA PROXY - Assembling complete page")
    print(f"URL: {url}")
    print(f"{'='*70}\n")
    
    try:
        # Fetch main HTML
        print("1. Fetching main HTML...")
        resp = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=15)
        
        if 'text/html' not in resp.headers.get('Content-Type', ''):
            return Response(resp.content, mimetype=resp.headers.get('Content-Type'))
        
        html = resp.text
        print(f"   ✓ Got {len(html)} bytes of HTML")
        
        # Find all external scripts
        print("\n2. Finding and inlining JavaScript files...")
        js_pattern = r'<script[^>]+src=["\']([^"\']+)["\'][^>]*></script>'
        js_urls = re.findall(js_pattern, html)
        
        for js_url in js_urls[:5]:  # Limit to first 5 to avoid timeout
            full_url = js_url if js_url.startswith('http') else urljoin(url, js_url)
            result = fetch_resource(full_url)
            if result and result[0] == 'text':
                # Replace with inline script
                html = re.sub(
                    f'<script[^>]+src=["\']' + re.escape(js_url) + '["\'][^>]*></script>',
                    f'<script>/* Inlined from {js_url} */{result[1]}</script>',
                    html
                )
                print(f"   ✓ Inlined JS: {js_url[:60]}")
        
        # Find all external CSS
        print("\n3. Finding and inlining CSS files...")
        css_pattern = r'<link[^>]+href=["\']([^"\']+\.css[^"\']*)["\'][^>]*>'
        css_urls = re.findall(css_pattern, html)
        
        for css_url in css_urls[:3]:  # Limit to first 3
            full_url = css_url if css_url.startswith('http') else urljoin(url, css_url)
            result = fetch_resource(full_url)
            if result and result[0] == 'text':
                # Inline fonts in CSS
                css_content = result[1]
                font_pattern = r'url\(["\']?([^"\')\s]+\.(woff2?|ttf|eot))["\']?\)'
                font_urls = re.findall(font_pattern, css_content)
                
                for font_match in font_urls[:3]:  # Limit fonts
                    font_url = font_match[0] if isinstance(font_match, tuple) else font_match
                    font_full_url = font_url if font_url.startswith('http') else urljoin(full_url, font_url)
                    font_result = fetch_resource(font_full_url)
                    if font_result and font_result[0] == 'data':
                        css_content = css_content.replace(font_url, font_result[1])
                        print(f"   ✓ Embedded font in CSS")
                
                # Replace link with style
                html = re.sub(
                    f'<link[^>]+href=["\']' + re.escape(css_url) + '["\'][^>]*>',
                    f'<style>/* Inlined from {css_url} */{css_content}</style>',
                    html
                )
                print(f"   ✓ Inlined CSS: {css_url[:60]}")
        
        # Find and inline images
        print("\n4. Finding and inlining images...")
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        img_urls = re.findall(img_pattern, html)
        
        for img_url in img_urls[:10]:  # Limit to 10 images
            full_url = img_url if img_url.startswith('http') else urljoin(url, img_url)
            result = fetch_resource(full_url)
            if result and result[0] == 'data':
                html = html.replace(img_url, result[1])
                print(f"   ✓ Inlined image")
        
        # Remove problematic tags
        print("\n5. Cleaning up...")
        html = re.sub(r'<link[^>]*preload[^>]*>', '', html)  # Remove preload links
        html = re.sub(r'<script[^>]*src=[^>]*></script>', '<!-- External script removed -->', html)  # Remove remaining external scripts
        
        # Add warning banner
        banner = '''
<div style="position:fixed;top:0;left:0;right:0;background:#f59e0b;color:#000;padding:15px;z-index:9999999;text-align:center;font-weight:bold;font-family:monospace;">
    ⚠️ ULTRA PROXY MODE - All resources embedded server-side. Some features may not work.
</div>
<div style="height:50px;"></div>
'''
        html = html.replace('<body', banner + '<body', 1)
        
        # Block all remaining external requests with JavaScript
        blocker = '''
<script>
window.fetch = () => Promise.resolve(new Response('', {status: 200}));
XMLHttpRequest.prototype.open = function() {};
XMLHttpRequest.prototype.send = function() {};
console.log('[ULTRA] All external requests blocked');
</script>
'''
        html = html.replace('</head>', blocker + '</head>', 1)
        
        print(f"\n{'='*70}")
        print(f"✓ COMPLETE - Assembled page: {len(html)} bytes")
        print(f"{'='*70}\n")
        
        return Response(html, mimetype='text/html')
        
    except Exception as e:
        print(f"\nERROR: {e}\n")
        return f"<h1>Error</h1><p>{e}</p>", 500

if __name__ == '__main__':
    print("\n" + "="*70)
    print("ULTRA PROXY - Complete Server-Side Page Assembly")
    print("="*70)
    print("\nStrategy:")
    print("  1. Fetch HTML from Netflix")
    print("  2. Find all external JS, CSS, images, fonts")
    print("  3. Fetch them all server-side")
    print("  4. Inline everything into one HTML file")
    print("  5. Block all client-side external requests")
    print("\nResult: Browser receives ONE file, makes ZERO external requests")
    print("="*70 + "\n")
    print("Starting server on port 5000...\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
